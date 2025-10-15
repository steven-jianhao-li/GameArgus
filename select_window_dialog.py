# select_window_dialog.py

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QPushButton, QDialogButtonBox
import pygetwindow as gw

class SelectWindowDialog(QDialog):
    """一个让用户从列表中选择一个活动窗口的对话框。"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择游戏窗口")
        self.setModal(True)
        self.selected_window_title = None

        self.layout = QVBoxLayout(self)
        
        self.list_widget = QListWidget()
        self.refresh_windows()
        self.list_widget.itemDoubleClicked.connect(self.accept)
        
        # --- THIS SECTION HAS BEEN CORRECTED ---
        # 1. Create the button box with standard OK and Cancel buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        
        # 2. Create a custom Refresh button
        refresh_button = QPushButton("Refresh")
        
        # 3. Add the custom button to the box with an "Action" role
        self.button_box.addButton(refresh_button, QDialogButtonBox.ButtonRole.ActionRole)

        # 4. Connect all buttons to their functions
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        refresh_button.clicked.connect(self.refresh_windows) # Connect the new button

        self.layout.addWidget(self.list_widget)
        self.layout.addWidget(self.button_box)

    def refresh_windows(self):
        """刷新窗口列表。"""
        self.list_widget.clear()
        self.windows = [win for win in gw.getAllWindows() if win.title and win.visible]
        for win in self.windows:
            self.list_widget.addItem(win.title)

    def accept(self):
        """当用户点击OK或双击时调用。"""
        if self.list_widget.currentItem():
            self.selected_window_title = self.list_widget.currentItem().text()
            super().accept()