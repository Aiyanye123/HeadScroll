"""Select an existing Windows process without an extra dependency."""

import csv
import io
import locale
import subprocess

from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)


class ProcessPickerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_process = ""
        self.setWindowTitle("选择进程")
        self.resize(420, 360)
        layout = QVBoxLayout(self)
        self.status = QLabel("双击进程进行选择")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["进程名", "PID"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.doubleClicked.connect(self._select_process)
        layout.addWidget(self.table)
        actions = QHBoxLayout()
        refresh = QPushButton("刷新")
        refresh.clicked.connect(self._load_processes)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        actions.addWidget(refresh)
        actions.addWidget(cancel)
        layout.addLayout(actions)
        self._load_processes()

    def _load_processes(self):
        try:
            result = subprocess.run(
                ["tasklist", "/fo", "csv", "/nh"],
                capture_output=True, text=True, encoding=locale.getpreferredencoding(False),
                check=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except (OSError, subprocess.SubprocessError, UnicodeError) as exc:
            self.status.setText(f"无法读取进程列表: {exc}")
            self.table.setRowCount(0)
            return
        rows = [row for row in csv.reader(io.StringIO(result.stdout)) if len(row) >= 2]
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            self.table.setItem(index, 0, QTableWidgetItem(row[0].strip()))
            self.table.setItem(index, 1, QTableWidgetItem(row[1].strip()))
        self.table.resizeColumnsToContents()
        self.status.setText("双击进程进行选择")

    def _select_process(self):
        item = self.table.item(self.table.currentRow(), 0)
        if item is not None:
            self.selected_process = item.text()
            self.accept()
