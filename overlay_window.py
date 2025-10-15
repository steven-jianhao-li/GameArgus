# overlay_window.py

from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QPen
from PyQt6.QtCore import Qt, QRect

class OverlayWindow(QWidget):
    """用于绘制红框的透明、不可交互的覆盖窗口。"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.rects_to_draw = []
        self.pen = QPen(Qt.GlobalColor.red, 3) # 红框颜色和宽度

    def update_rects(self, rects):
        """更新需要绘制的矩形框列表并触发重绘。"""
        self.rects_to_draw = rects
        self.update() # 请求重绘

    def paintEvent(self, event):
        """当窗口需要重绘时调用，用于绘制所有红框。"""
        if not self.rects_to_draw:
            return
        
        painter = QPainter(self)
        painter.setPen(self.pen)
        for rect in self.rects_to_draw:
            painter.drawRect(rect)

    def clear(self):
        """清除所有红框。"""
        self.update_rects([])