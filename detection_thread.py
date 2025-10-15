# detection_thread.py

import cv2
import numpy as np
import mss
import time
from PyQt6.QtCore import QThread, pyqtSignal, QRect

class DetectionThread(QThread):
    """在后台线程中执行图像检测。"""
    
    # 信号：发出检测到的矩形框列表
    detection_signal = pyqtSignal(list)
    # 信号：报告错误消息
    error_signal = pyqtSignal(str)

    def __init__(self, window_rect, targets_cv, confidence, box_dims, delay, parent=None):
        super().__init__(parent)
        self.is_running = False
        self.window_rect = window_rect
        self.targets_cv = targets_cv
        self.confidence_threshold = confidence / 100.0
        self.box_dims = box_dims
        self.disappear_delay = delay
        self.sct = None
        self.last_seen_info = {} # {target_index: {'rect': QRect, 'time': float}}

    def run(self):
        """线程主循环。"""
        self.is_running = True
        self.sct = mss.mss()
        
        if not self.targets_cv:
            self.error_signal.emit("错误：没有设置任何监测目标图片。")
            return
            
        while self.is_running:
            try:
                # 1. 截取游戏窗口图像
                screenshot = self.sct.grab(self.window_rect)
                img = np.array(screenshot)
                img_gray = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)

                current_time = time.time()
                found_rects_this_frame = []
                
                # 2. 遍历所有目标图片进行模板匹配
                for i, template in enumerate(self.targets_cv):
                    if template is None:
                        continue
                    
                    w, h = template.shape[::-1]
                    res = cv2.matchTemplate(img_gray, template, cv2.TM_CCOEFF_NORMED)
                    
                    # 获取所有匹配度超过阈值的位置
                    locations = np.where(res >= self.confidence_threshold)
                    
                    # 使用非极大值抑制（NMS）去除重叠的框
                    rects = []
                    for pt in zip(*locations[::-1]):
                        rects.append([pt[0], pt[1], pt[0] + w, pt[1] + h])
                    
                    scores = [res[pt[1], pt[0]] for pt in zip(*locations[::-1])]
                    indices = cv2.dnn.NMSBoxes(rects, scores, self.confidence_threshold, 0.3)
                    
                    if len(indices) > 0:
                        # 对于每个唯一的目标，更新其最后出现时间和位置
                        for idx in indices.flatten():
                            x, y, x2, y2 = rects[idx]
                            box_w, box_h = self.box_dims['width'], self.box_dims['height']
                            
                            # 计算居中偏移
                            x_offset = (box_w - w) // 2
                            y_offset = (box_h - h) // 2
                            
                            final_rect = QRect(x - x_offset, y - y_offset, box_w, box_h)
                            found_rects_this_frame.append(final_rect)
                            self.last_seen_info[f"{i}-{idx}"] = {'rect': final_rect, 'time': current_time}

                # 3. 检查哪些旧框需要继续显示
                all_rects_to_draw = list(found_rects_this_frame)
                keys_to_delete = []
                for key, info in self.last_seen_info.items():
                    if info['rect'] not in found_rects_this_frame:
                        if current_time - info['time'] < self.disappear_delay:
                            all_rects_to_draw.append(info['rect']) # 继续显示
                        else:
                            keys_to_delete.append(key) # 超过时限，准备删除
                
                # 4. 清理过期的框
                for key in keys_to_delete:
                    del self.last_seen_info[key]

                # 5. 发送最终要绘制的矩形列表
                self.detection_signal.emit(all_rects_to_draw)

                time.sleep(0.05)  # 控制检测频率，避免CPU占用过高
            except Exception as e:
                self.error_signal.emit(f"检测线程出错: {e}")
                self.stop()

    def stop(self):
        """停止线程。"""
        self.is_running = False