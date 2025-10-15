# main.py

import sys
import os
import cv2
import pygetwindow as gw
import numpy as np
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QSlider, QLineEdit, QListWidget,
                             QListWidgetItem, QFileDialog, QAbstractItemView, QMessageBox)
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtCore import Qt, pyqtSlot

# 导入其他模块
from config_manager import ConfigManager
from detection_thread import DetectionThread
from overlay_window import OverlayWindow
from hotkey_listener import HotkeyListener
from select_window_dialog import SelectWindowDialog

class MainWindow(QMainWindow):
    """应用程序的主窗口。"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("游戏辅助脚本 by Gemini")
        self.setGeometry(150, 150, 500, 600)

        # 初始化核心组件
        self.config_manager = ConfigManager()
        self.overlay = OverlayWindow()
        self.detection_thread = None
        self.hotkey_listener = None
        
        self.is_detection_running = False
        self.target_cv_images = []
        self.selected_window = None

        self.init_ui()
        self.load_settings()
        self.setup_hotkey_listener()
        
    def init_ui(self):
        """初始化用户界面。"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # 1. 窗口选择
        window_layout = QHBoxLayout()
        self.window_label = QLabel("游戏窗口: 未选择")
        select_btn = QPushButton("选择窗口")
        select_btn.clicked.connect(self.select_window)
        window_layout.addWidget(self.window_label)
        window_layout.addWidget(select_btn)

        # 2. 目标图片列表
        self.target_list_widget = QListWidget()
        self.target_list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.target_list_widget.setAcceptDrops(True)
        self.target_list_widget.setDropIndicatorShown(True)
        self.target_list_widget.setToolTip("拖拽图片文件到此处添加，双击条目删除")
        self.target_list_widget.itemDoubleClicked.connect(self.remove_selected_image)
        
        img_btn_layout = QHBoxLayout()
        add_img_btn = QPushButton("添加图片")
        add_img_btn.clicked.connect(self.add_image_from_dialog)
        img_btn_layout.addWidget(add_img_btn)
        
        # 3. 参数设置
        # 置信度
        self.confidence_label = QLabel()
        self.confidence_slider = QSlider(Qt.Orientation.Horizontal)
        self.confidence_slider.setRange(50, 99)
        self.confidence_slider.valueChanged.connect(lambda v: self.confidence_label.setText(f"检测置信度: {v}%"))
        
        # 红框尺寸
        self.box_width_input = QLineEdit()
        self.box_height_input = QLineEdit()
        box_layout = QHBoxLayout()
        box_layout.addWidget(QLabel("红框宽:"))
        box_layout.addWidget(self.box_width_input)
        box_layout.addWidget(QLabel("高:"))
        box_layout.addWidget(self.box_height_input)
        
        # 消失延迟
        delay_layout = QHBoxLayout()
        self.delay_input = QLineEdit()
        delay_layout.addWidget(QLabel("红框消失延迟(秒):"))
        delay_layout.addWidget(self.delay_input)
        
        # 热键
        hotkey_layout = QHBoxLayout()
        self.hotkey_input = QLineEdit()
        hotkey_layout.addWidget(QLabel("启/停热键:"))
        hotkey_layout.addWidget(self.hotkey_input)
        
        # 4. 控制按钮
        self.toggle_button = QPushButton("启动监测")
        self.toggle_button.clicked.connect(self.toggle_detection)

        # 组装布局
        main_layout.addLayout(window_layout)
        main_layout.addWidget(QLabel("待监测图片列表:"))
        main_layout.addWidget(self.target_list_widget)
        main_layout.addLayout(img_btn_layout)
        main_layout.addSpacing(20)
        main_layout.addWidget(self.confidence_label)
        main_layout.addWidget(self.confidence_slider)
        main_layout.addLayout(box_layout)
        main_layout.addLayout(delay_layout)
        main_layout.addLayout(hotkey_layout)
        main_layout.addSpacing(20)
        main_layout.addWidget(self.toggle_button)

        self.setAcceptDrops(True)

    def load_settings(self):
        """从配置文件加载UI状态。"""
        config = self.config_manager.config
        self.confidence_slider.setValue(config['confidence'])
        self.box_width_input.setText(str(config['box_width']))
        self.box_height_input.setText(str(config['box_height']))
        self.delay_input.setText(str(config['disappear_delay']))
        self.hotkey_input.setText(config['hotkey'])

        for img_path in config['target_images']:
            self.add_image_to_list(img_path)
            
        if config['window_title']:
            try:
                wins = gw.getWindowsWithTitle(config['window_title'])
                if wins:
                    self.selected_window = wins[0]
                    self.window_label.setText(f"游戏窗口: {self.selected_window.title}")
            except Exception:
                self.window_label.setText("游戏窗口: (上次选择的已关闭)")
                self.selected_window = None

    def save_settings(self):
        """保存当前UI状态到配置文件。"""
        self.config_manager.set('confidence', self.confidence_slider.value())
        self.config_manager.set('box_width', int(self.box_width_input.text()))
        self.config_manager.set('box_height', int(self.box_height_input.text()))
        self.config_manager.set('disappear_delay', float(self.delay_input.text()))
        self.config_manager.set('hotkey', self.hotkey_input.text())
        self.config_manager.set('window_title', self.selected_window.title if self.selected_window else None)

    def select_window(self):
        """打开窗口选择对话框。"""
        dialog = SelectWindowDialog(self)
        if dialog.exec():
            title = dialog.selected_window_title
            try:
                self.selected_window = gw.getWindowsWithTitle(title)[0]
                self.window_label.setText(f"游戏窗口: {title}")
                self.config_manager.set('window_title', title)
            except IndexError:
                QMessageBox.warning(self, "错误", f"找不到标题为 '{title}' 的窗口。")

    def add_image_to_list(self, path):
        """将图片添加到UI列表和数据列表。"""
        if not os.path.exists(path): return
        
        for i in range(self.target_list_widget.count()):
            item = self.target_list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == path:
                return

        # --- THIS IS THE CORRECTED SECTION ---
        try:
            # 1. Read the file into a raw byte array just once
            with open(path, 'rb') as f:
                image_data = f.read()
            
            # 2. Create the OpenCV image for detection from the byte array
            numpy_array = np.frombuffer(image_data, np.uint8)
            img_cv = cv2.imdecode(numpy_array, cv2.IMREAD_GRAYSCALE)
            if img_cv is None:
                raise IOError("OpenCV could not decode the image.")

            # 3. Create the PyQt icon for display from the same byte array
            pixmap = QPixmap()
            pixmap.loadFromData(image_data)
            icon = QIcon(pixmap)
            
        except Exception as e:
            print(f"Error loading image {path}: {e}")
            return
        # --- END OF CORRECTION ---

        item = QListWidgetItem(icon, os.path.basename(path))
        item.setData(Qt.ItemDataRole.UserRole, path)
        self.target_list_widget.addItem(item)
        
        self.config_manager.add_target_image(path)
        self.target_cv_images.append(img_cv)

    def add_image_from_dialog(self):
        """通过文件对话框添加图片。"""
        files, _ = QFileDialog.getOpenFileNames(self, "选择图片", "", "Image Files (*.png *.jpg *.bmp)")
        for file in files:
            self.add_image_to_list(file)

    def remove_selected_image(self):
        """移除列表中选中的图片。"""
        for item in self.target_list_widget.selectedItems():
            path = item.data(Qt.ItemDataRole.UserRole)
            row = self.target_list_widget.row(item)
            self.target_list_widget.takeItem(row)
            self.config_manager.remove_target_image(path)
            if row < len(self.target_cv_images):
                del self.target_cv_images[row]
    
    @pyqtSlot()
    def toggle_detection(self):
        """启动或停止监测。"""
        if self.is_detection_running:
            if self.detection_thread:
                self.detection_thread.stop()
                self.detection_thread.wait()
            self.overlay.hide()
            self.overlay.clear()
            self.is_detection_running = False
            self.toggle_button.setText("启动监测")
        else:
            if not self.selected_window or self.selected_window not in gw.getAllWindows():
                QMessageBox.warning(self, "提示", "请先选择一个有效的游戏窗口！\n（可能已关闭，请重新选择）")
                return
            
            if not self.target_cv_images:
                QMessageBox.warning(self, "提示", "请至少添加一张待监测的图片！")
                return
            
            self.save_settings()
            
            rect = {
                'left': self.selected_window.left, 
                'top': self.selected_window.top, 
                'width': self.selected_window.width, 
                'height': self.selected_window.height
            }
            box_dims = {'width': int(self.box_width_input.text()), 'height': int(self.box_height_input.text())}

            self.detection_thread = DetectionThread(
                window_rect=rect,
                targets_cv=self.target_cv_images,
                confidence=self.confidence_slider.value(),
                box_dims=box_dims,
                delay=float(self.delay_input.text())
            )
            self.detection_thread.detection_signal.connect(self.overlay.update_rects)
            self.detection_thread.error_signal.connect(self.on_detection_error)
            
            self.overlay.setGeometry(rect['left'], rect['top'], rect['width'], rect['height'])
            self.overlay.show()
            self.detection_thread.start()
            
            self.is_detection_running = True
            self.toggle_button.setText("停止监测")

    @pyqtSlot(str)
    def on_detection_error(self, message):
        """处理检测线程中的错误。"""
        QMessageBox.critical(self, "检测错误", message)
        self.toggle_detection()

    def setup_hotkey_listener(self):
        """设置或重置热键监听器。"""
        if self.hotkey_listener:
            self.hotkey_listener.stop()
            self.hotkey_listener.wait()

        hotkey = self.hotkey_input.text()
        self.hotkey_listener = HotkeyListener(hotkey)
        self.hotkey_listener.hotkey_pressed.connect(self.toggle_detection)
        self.hotkey_listener.start()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if os.path.splitext(file_path.lower())[1] in ['.png', '.jpg', '.jpeg', '.bmp']:
                self.add_image_to_list(file_path)

    def closeEvent(self, event):
        """关闭程序前的清理工作。"""
        self.save_settings()
        
        if self.detection_thread and self.detection_thread.isRunning():
            self.detection_thread.stop()
            self.detection_thread.wait()
        
        if self.hotkey_listener:
            self.hotkey_listener.stop()
            self.hotkey_listener.wait()
            
        self.overlay.close()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())