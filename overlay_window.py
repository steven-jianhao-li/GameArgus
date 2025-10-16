# overlay_window.py

from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QPen
from PyQt6.QtCore import Qt, QRect
import ctypes

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
        
        # 使用Windows API确保鼠标完全穿透
        self._set_window_transparent_for_input()
        
        self.rects_to_draw = []
        self.pen = QPen(Qt.GlobalColor.red, 3) # 红框颜色和宽度

    def _set_window_transparent_for_input(self):
        """使用Windows API设置窗口对鼠标输入完全透明。"""
        try:
            hwnd = int(self.winId())
            # 获取当前窗口扩展样式
            GWL_EXSTYLE = -20
            WS_EX_LAYERED = 0x00080000
            WS_EX_TRANSPARENT = 0x00000020
            
            # 设置窗口为分层窗口，并使其对鼠标透明
            ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ex_style |= (WS_EX_LAYERED | WS_EX_TRANSPARENT)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)
        except Exception as e:
            print(f"设置窗口鼠标穿透失败: {e}")
    
    def update_rects(self, rects):
        """更新需要绘制的矩形框列表并触发重绘。"""
        # 只有当矩形列表真正改变时才更新
        if self._rects_equal(self.rects_to_draw, rects):
            return
        self.rects_to_draw = rects
        self.update() # 请求重绘
    
    def _rects_equal(self, rects1, rects2):
        """检查两个矩形列表是否相同。"""
        if len(rects1) != len(rects2):
            return False
        set1 = set((r.x(), r.y(), r.width(), r.height()) for r in rects1)
        set2 = set((r.x(), r.y(), r.width(), r.height()) for r in rects2)
        return set1 == set2

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