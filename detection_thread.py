# detection_thread.py

import cv2
import numpy as np
import mss
import time
from PyQt6.QtCore import QThread, pyqtSignal, QRect
import multiprocessing

# --- Helper function for multiprocessing ---
def match_template_worker(args):
    """
    在独立进程中执行单个模板匹配。
    :param args: 包含 (主图像, 模板, 阈值, 模板索引) 的元组
    :return: 包含 (模板索引, 匹配结果矩形列表) 的元组
    """
    img_gray, template, threshold, template_index = args

    # 如果 template 为 None，返回占位的尺寸 0,0，保持返回值数量一致
    if template is None:
        return template_index, [], 0, 0

    # 模板宽高
    w, h = template.shape[::-1]

    # 执行模板匹配
    res = cv2.matchTemplate(img_gray, template, cv2.TM_CCOEFF_NORMED)
    locations = np.where(res >= threshold)

    rects = []  # boxes as [x, y, w, h]
    scores = []
    for pt in zip(*locations[::-1]):
        x, y = pt
        rects.append([int(x), int(y), int(w), int(h)])
        # res 的索引为 [row=y, col=x]
        scores.append(float(res[y, x]))

    # 如果没有找到匹配项，则返回空列表，但仍返回 w,h
    if not rects:
        return template_index, [], w, h

    # 使用 NMS 去除重叠
    try:
        indices = cv2.dnn.NMSBoxes(rects, scores, threshold, 0.3)
    except Exception:
        # 如果 NMS 调用失败，直接将所有 rects 作为最终结果
        return template_index, rects, w, h

    final_rects = []
    if len(indices) > 0:
        for idx in indices.flatten():
            final_rects.append(rects[idx])

    return template_index, final_rects, w, h

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
        self.pool = None
        self.last_seen_info = {} # {target_index: {'rect': QRect, 'time': float}}
        # 稳定性控制：需要连续N帧确认才显示/消失
        self.appear_frames = 1  # 1帧检测到就立即显示
        self.disappear_frames = 2  # 连续2帧未检测到才消失
        self.rect_frame_count = {}  # {rect_key: {'rect': QRect, 'appear_count': int, 'disappear_count': int, 'confirmed': bool}}
        self.current_confirmed_rects = []  # 当前已确认显示的矩形列表

    def run(self):
        """线程主循环。"""
        self.is_running = True
        self.sct = mss.mss()
        
        # 初始化进程池
        try:
            # 限制进程数量，避免CPU满载
            cpu_count = max(1, multiprocessing.cpu_count() - 1) 
            self.pool = multiprocessing.Pool(processes=cpu_count)
        except Exception as e:
            self.error_signal.emit(f"初始化进程池失败: {e}")
            return

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
                
                # 2. 构建多进程任务
                tasks = [(img_gray, template, self.confidence_threshold, i) for i, template in enumerate(self.targets_cv)]
                
                # 3. 并行执行模板匹配
                results = self.pool.map(match_template_worker, tasks)

                # 4. 处理匹配结果，构建本帧检测到的所有矩形
                for template_index, final_rects, w, h in results:
                    if not final_rects:
                        continue

                    for i, rect_coords in enumerate(final_rects):
                        # rect_coords is [x, y, w, h]
                        x, y, tw, th = rect_coords
                        box_w, box_h = self.box_dims['width'], self.box_dims['height']

                        x_offset = (box_w - tw) // 2
                        y_offset = (box_h - th) // 2

                        # QRect(x, y, width, height)
                        final_rect = QRect(int(x - x_offset), int(y - y_offset), int(box_w), int(box_h))
                        found_rects_this_frame.append(final_rect)

                # 5. 使用连续帧确认机制更新稳定的矩形列表
                self._update_stable_rects(found_rects_this_frame, current_time)

                # 6. 发送最终要绘制的矩形列表（仅在有变化时发送）
                self.detection_signal.emit(self.current_confirmed_rects)

            except Exception as e:
                self.error_signal.emit(f"检测线程出错: {e}")
                self.stop()

    def _rect_key(self, rect):
        """生成矩形的唯一键，用于跟踪（容忍小范围移动）。"""
        # 使用20像素网格对齐，使相近位置的矩形被视为同一个
        grid_size = 20
        x = (rect.x() // grid_size) * grid_size
        y = (rect.y() // grid_size) * grid_size
        return f"{x}_{y}_{rect.width()}_{rect.height()}"
    
    def _update_stable_rects(self, found_rects, current_time):
        """使用连续帧确认机制更新稳定的矩形列表。"""
        # 创建本帧检测到的矩形键集合
        found_keys = set()
        found_key_to_rect = {}
        for rect in found_rects:
            key = self._rect_key(rect)
            found_keys.add(key)
            found_key_to_rect[key] = rect
        
        # 更新所有跟踪的矩形计数
        keys_to_delete = []
        for key, info in self.rect_frame_count.items():
            if key in found_keys:
                # 本帧检测到：增加出现计数，重置消失计数
                info['appear_count'] = min(info['appear_count'] + 1, self.appear_frames)
                info['disappear_count'] = 0
                info['rect'] = found_key_to_rect[key]  # 更新位置
                info['time'] = current_time
                
                # 达到出现阈值，确认显示（一旦确认就保持）
                if info['appear_count'] >= self.appear_frames:
                    info['confirmed'] = True
            else:
                # 本帧未检测到：增加消失计数，不重置出现计数
                info['disappear_count'] += 1
                
                # 达到消失阈值才删除（一旦确认显示就保持到明确消失）
                if info['disappear_count'] >= self.disappear_frames:
                    if self.disappear_delay == 0 or current_time - info['time'] >= self.disappear_delay:
                        keys_to_delete.append(key)
                        continue
        
        # 删除过期的矩形
        for key in keys_to_delete:
            del self.rect_frame_count[key]
        
        # 添加新检测到的矩形
        for key in found_keys:
            if key not in self.rect_frame_count:
                self.rect_frame_count[key] = {
                    'rect': found_key_to_rect[key],
                    'appear_count': 1,
                    'disappear_count': 0,
                    'confirmed': False,
                    'time': current_time
                }
        
        # 更新当前确认的矩形列表
        new_confirmed = [info['rect'] for info in self.rect_frame_count.values() if info['confirmed']]
        
        # 只有当列表真正改变时才更新（减少不必要的重绘）
        if self._rects_changed(self.current_confirmed_rects, new_confirmed):
            self.current_confirmed_rects = new_confirmed
    
    def _rects_changed(self, old_rects, new_rects):
        """检查两个矩形列表是否不同。"""
        if len(old_rects) != len(new_rects):
            return True
        # 简单比较：检查是否所有矩形都相同
        old_set = set((r.x(), r.y(), r.width(), r.height()) for r in old_rects)
        new_set = set((r.x(), r.y(), r.width(), r.height()) for r in new_rects)
        return old_set != new_set

    def stop(self):
        """停止线程并清理资源。"""
        self.is_running = False
        if self.pool:
            self.pool.close()
            self.pool.join()
