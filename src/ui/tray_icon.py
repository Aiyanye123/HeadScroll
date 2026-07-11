"""
M9: 系统托盘图标
托盘菜单与全局快捷键
"""

from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PySide6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor, QBrush
from PySide6.QtCore import Signal, QSize

from .styles import COLORS


def create_default_icon() -> QIcon:
    """创建默认图标"""
    pixmap = QPixmap(32, 32)
    pixmap.fill(QColor(0, 0, 0, 0))
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    # 简单手掌图标
    painter.setBrush(QBrush(QColor(COLORS["primary"])))
    painter.setPen(QColor(COLORS["primary_pressed"]))
    painter.drawRoundedRect(9, 13, 15, 14, 4, 4)
    for x, height in ((10, 9), (14, 6), (18, 5), (22, 8)):
        painter.drawRoundedRect(x, height, 3, 12, 1, 1)
    
    painter.end()
    return QIcon(pixmap)


class TrayIcon(QSystemTrayIcon):
    """系统托盘图标"""
    
    # 信号
    show_panel_clicked = Signal()
    start_clicked = Signal()
    stop_clicked = Signal()
    pause_clicked = Signal()
    exit_clicked = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setIcon(create_default_icon())
        self.setToolTip("HeadScroll 语音翻页与头部滚动")
        
        self._is_running = False
        self._is_paused = False
        
        self._setup_menu()
        
        # 点击托盘图标显示面板
        self.activated.connect(self._on_activated)
    
    def _setup_menu(self):
        """构建托盘菜单"""
        menu = QMenu()
        
        # 显示面板
        self.show_action = menu.addAction("显示面板")
        self.show_action.triggered.connect(self.show_panel_clicked.emit)
        
        menu.addSeparator()
        
        # 启动/停止
        self.start_action = menu.addAction("启动")
        self.start_action.triggered.connect(self._on_start_clicked)
        
        # 暂停/恢复
        self.pause_action = menu.addAction("暂停")
        self.pause_action.setEnabled(False)
        self.pause_action.triggered.connect(self._on_pause_clicked)
        
        menu.addSeparator()
        
        # 退出
        self.exit_action = menu.addAction("退出")
        self.exit_action.triggered.connect(self.exit_clicked.emit)
        
        self.setContextMenu(menu)
    
    def _on_activated(self, reason):
        """托盘图标被激活"""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_panel_clicked.emit()
    
    def _on_start_clicked(self):
        """启动/停止菜单点击"""
        if self._is_running:
            self._is_running = False
            self.start_action.setText("启动")
            self.pause_action.setEnabled(False)
            self.stop_clicked.emit()
        else:
            self._is_running = True
            self.start_action.setText("停止")
            self.pause_action.setEnabled(True)
            self.start_clicked.emit()
    
    def _on_pause_clicked(self):
        """暂停/恢复菜单点击"""
        self._is_paused = not self._is_paused
        self.pause_action.setText("恢复" if self._is_paused else "暂停")
        self.pause_clicked.emit()
    
    def set_running(self, running: bool):
        """设置运行状态"""
        self._is_running = running
        self.start_action.setText("停止" if running else "启动")
        self.pause_action.setEnabled(running)
    
    def set_paused(self, paused: bool):
        """设置暂停状态"""
        self._is_paused = paused
        self.pause_action.setText("恢复" if paused else "暂停")
    
    def show_message(self, title: str, message: str, icon: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.MessageIcon.Information):
        """显示托盘通知"""
        self.showMessage(title, message, icon, 3000)
