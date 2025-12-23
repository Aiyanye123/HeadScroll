import sys
import os
from PySide6.QtGui import QImage, QPainter, QColor, QBrush, QPen, QRadialGradient, QIcon
from PySide6.QtCore import Qt, QPoint

def create_icon(size=256, output_path="assets/icon.ico"):
    # 创建图像
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    # 1. 背景：圆角矩形
    bg_color = QColor(70, 130, 180)  # SteelBlue
    painter.setBrush(QBrush(bg_color))
    painter.setPen(Qt.NoPen)
    rect_size = size * 0.9
    offset = (size - rect_size) / 2
    painter.drawRoundedRect(offset, offset, rect_size, rect_size, size * 0.2, size * 0.2)
    
    # 2. 眼睛主体（眼白）
    eye_width = size * 0.7
    eye_height = size * 0.5
    eye_x = (size - eye_width) / 2
    eye_y = (size - eye_height) / 2
    
    painter.setBrush(QBrush(Qt.white))
    painter.drawEllipse(eye_x, eye_y, eye_width, eye_height)
    
    # 3. 虹膜（蓝色渐变）
    iris_size = size * 0.35
    iris_x = (size - iris_size) / 2
    iris_y = (size - iris_size) / 2
    
    gradient = QRadialGradient(size/2, size/2, iris_size/2)
    gradient.setColorAt(0, QColor(100, 149, 237))  # CornflowerBlue
    gradient.setColorAt(1, QColor(25, 25, 112))    # MidnightBlue
    
    painter.setBrush(QBrush(gradient))
    painter.drawEllipse(iris_x, iris_y, iris_size, iris_size)
    
    # 4. 瞳孔
    pupil_size = size * 0.15
    pupil_x = (size - pupil_size) / 2
    pupil_y = (size - pupil_size) / 2
    
    painter.setBrush(QBrush(Qt.black))
    painter.drawEllipse(pupil_x, pupil_y, pupil_size, pupil_size)
    
    # 5. 高光
    highlight_size = size * 0.08
    highlight_x = size/2 - highlight_size
    highlight_y = size/2 - highlight_size
    
    painter.setBrush(QBrush(QColor(255, 255, 255, 200)))
    painter.drawEllipse(highlight_x, highlight_y, highlight_size, highlight_size)
    
    painter.end()
    
    # 确保目录存在
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # 保存为 ICO
    image.save(output_path)
    print(f"Icon saved to {output_path}")

if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)  # 需要 Application 实例才能加载某些图像插件
    create_icon()
