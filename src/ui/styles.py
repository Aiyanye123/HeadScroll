"""
UI 样式主题模块
提供统一的深色简约扁平化主题
"""

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor

# 调色板
COLORS = {
    "primary": "#3B82F6",
    "primary_hover": "#5EA2FF",
    "primary_pressed": "#2F6FE0",
    "success": "#22C55E",
    "danger": "#EF4444",
    "warning": "#F59E0B",
    "background": "#F7F8FA",
    "surface": "#FFFFFF",
    "surface_hover": "#F3F4F6",
    "border": "#E5E7EB",
    "text_primary": "#111827",
    "text_secondary": "#6B7280",
    "text_disabled": "#9CA3AF",
}


def get_global_stylesheet() -> str:
    """返回全局 QSS 样式表"""
    return f"""
/* ========== 全局设置 ========== */
QWidget {{
    background-color: {COLORS["background"]};
    color: {COLORS["text_primary"]};
    font-size: 10pt;
}}

/* ========== 分组框 ========== */
QGroupBox {{
    background-color: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 8px;
    margin-top: 12px;
    padding: 12px 8px 8px 8px;
    font-weight: bold;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    color: {COLORS["text_secondary"]};
}}

/* ========== 按钮 ========== */
QPushButton {{
    background-color: {COLORS["surface"]};
    color: {COLORS["text_primary"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 6px;
    padding: 8px 16px;
    min-height: 20px;
}}

QPushButton:hover {{
    background-color: {COLORS["surface_hover"]};
    border-color: {COLORS["primary"]};
}}

QPushButton:pressed {{
    background-color: {COLORS["surface_hover"]};
}}

QPushButton:checked {{
    background-color: {COLORS["primary"]};
    border-color: {COLORS["primary"]};
    color: #FFFFFF;
}}

QPushButton:disabled {{
    background-color: {COLORS["surface"]};
    color: {COLORS["text_disabled"]};
    border-color: {COLORS["border"]};
}}

QPushButton#primaryButton {{
    background-color: {COLORS["primary"]};
    border-color: {COLORS["primary"]};
    color: #FFFFFF;
}}

QPushButton#primaryButton:hover {{
    background-color: {COLORS["primary_hover"]};
}}

/* ========== 标签 ========== */
QLabel {{
    background-color: transparent;
    color: {COLORS["text_primary"]};
}}

QLabel[class="secondary"] {{
    color: {COLORS["text_secondary"]};
}}

/* ========== 进度条 ========== */
QProgressBar {{
    background-color: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 4px;
    text-align: center;
    color: {COLORS["text_primary"]};
}}

QProgressBar::chunk {{
    background-color: {COLORS["primary"]};
    border-radius: 3px;
}}

/* ========== 滑块 ========== */
QSlider::groove:horizontal {{
    background-color: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    height: 6px;
    border-radius: 3px;
}}

QSlider::handle:horizontal {{
    background-color: {COLORS["primary"]};
    border: none;
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}}

QSlider::handle:horizontal:hover {{
    background-color: {COLORS["primary_hover"]};
}}

QSlider::sub-page:horizontal {{
    background-color: {COLORS["primary"]};
    border-radius: 3px;
}}

/* ========== 输入框 ========== */
QLineEdit, QSpinBox, QDoubleSpinBox {{
    background-color: {COLORS["surface"]};
    color: {COLORS["text_primary"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 4px;
    padding: 6px 10px;
}}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {COLORS["primary"]};
}}

/* ========== 下拉框 ========== */
QComboBox {{
    background-color: {COLORS["surface"]};
    color: {COLORS["text_primary"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 4px;
    padding: 6px 10px;
    min-height: 20px;
}}

QComboBox:hover {{
    border-color: {COLORS["primary"]};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {COLORS["text_secondary"]};
    margin-right: 8px;
}}

QComboBox QAbstractItemView {{
    background-color: {COLORS["surface"]};
    color: {COLORS["text_primary"]};
    border: 1px solid {COLORS["border"]};
    selection-background-color: {COLORS["primary"]};
}}

/* ========== 表格 ========== */
QTableWidget {{
    background-color: {COLORS["surface"]};
    color: {COLORS["text_primary"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 4px;
    gridline-color: {COLORS["border"]};
}}

QTableWidget::item {{
    padding: 6px;
}}

QTableWidget::item:selected {{
    background-color: {COLORS["primary"]};
}}

QTableWidget::item:alternate {{
    background-color: {COLORS["surface_hover"]};
}}

QHeaderView::section {{
    background-color: {COLORS["surface"]};
    color: {COLORS["text_secondary"]};
    border: none;
    border-bottom: 1px solid {COLORS["border"]};
    padding: 8px;
    font-weight: bold;
}}

/* ========== 滚动条 ========== */
QScrollBar:vertical {{
    background-color: {COLORS["background"]};
    width: 10px;
    border-radius: 5px;
}}

QScrollBar::handle:vertical {{
    background-color: {COLORS["border"]};
    border-radius: 5px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {COLORS["text_secondary"]};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

/* ========== 对话框 ========== */
QDialog {{
    background-color: {COLORS["background"]};
}}

QMessageBox {{
    background-color: {COLORS["background"]};
}}

QMessageBox QLabel {{
    color: {COLORS["text_primary"]};
}}

/* ========== 快捷键编辑框 ========== */
QKeySequenceEdit {{
    background-color: {COLORS["surface"]};
    color: {COLORS["text_primary"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 4px;
    padding: 6px 10px;
}}

QKeySequenceEdit:focus {{
    border-color: {COLORS["primary"]};
}}
"""


def apply_theme(app: QApplication) -> None:
    """应用主题到 QApplication"""
    app.setStyleSheet(get_global_stylesheet())
    
    # 设置调色板
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(COLORS["background"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(COLORS["text_primary"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(COLORS["surface"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(COLORS["surface_hover"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(COLORS["text_primary"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(COLORS["surface"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(COLORS["text_primary"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(COLORS["primary"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    
    app.setPalette(palette)
