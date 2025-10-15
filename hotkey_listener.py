# hotkey_listener.py

from PyQt6.QtCore import QThread, pyqtSignal
from pynput import keyboard

class HotkeyListener(QThread):
    """在后台监听全局热键。"""
    
    # 信号：当热键被按下时发出
    hotkey_pressed = pyqtSignal()

    def __init__(self, hotkey_str, parent=None):
        super().__init__(parent)
        self.hotkey_str = hotkey_str.lower()
        self.listener = None

    def run(self):
        """启动键盘监听器。"""
        try:
            # 解析热键字符串
            # 这是一个简化的解析，仅支持 F1-F12 和单个字符
            if self.hotkey_str.startswith('f') and self.hotkey_str[1:].isdigit():
                key_to_listen = keyboard.Key[self.hotkey_str]
            else:
                key_to_listen = keyboard.KeyCode.from_char(self.hotkey_str)

            def on_press(key):
                if key == key_to_listen:
                    self.hotkey_pressed.emit()
            
            self.listener = keyboard.Listener(on_press=on_press)
            self.listener.start()
            self.listener.join() # 阻塞线程直到监听器停止
            
        except Exception as e:
            print(f"无法监听热键 '{self.hotkey_str}': {e}。请尝试其他按键。")

    def stop(self):
        """停止监听器。"""
        if self.listener:
            self.listener.stop()