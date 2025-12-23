"""
M9: 进程选择对话框
"""

import csv
import io
import subprocess
from typing import List, Tuple

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem
)
from PySide6.QtCore import Qt


class ProcessPickerDialog(QDialog):
    """进程选择对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择进程")
        self.setModal(True)
        self.setFixedSize(420, 360)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel("双击进程进行选择")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(title)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["进程名", "PID"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.refresh_btn = QPushButton("刷新")
        self.close_btn = QPushButton("取消")
        self.refresh_btn.clicked.connect(self._load_processes)
        self.close_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.refresh_btn)
        btn_row.addWidget(self.close_btn)
        layout.addLayout(btn_row)

        self.selected_process: str = ""
        self._load_processes()

    def _load_processes(self):
        processes = self._get_processes()
        self.table.setRowCount(len(processes))
        for i, (name, pid) in enumerate(processes):
            self.table.setItem(i, 0, QTableWidgetItem(name))
            self.table.setItem(i, 1, QTableWidgetItem(str(pid)))
        self.table.resizeColumnsToContents()

    def _get_processes(self) -> List[Tuple[str, int]]:
        """获取进程列表 (Windows tasklist)"""
        try:
            output = subprocess.check_output(
                ["tasklist", "/fo", "csv", "/nh"],
                text=True,
                encoding="utf-8",
                errors="ignore",
            )
        except Exception:
            return []

        reader = csv.reader(io.StringIO(output))
        processes: List[Tuple[str, int]] = []
        for row in reader:
            if not row:
                continue
            name = row[0].strip()
            pid_str = row[1].strip()
            try:
                pid = int(pid_str)
            except ValueError:
                continue
            processes.append((name, pid))
        return processes

    def _on_double_click(self):
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        if not item:
            return
        self.selected_process = item.text().strip()
        if self.selected_process:
            self.accept()
