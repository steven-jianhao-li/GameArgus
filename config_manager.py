# config_manager.py

import json
import os

class ConfigManager:
    """负责加载和保存应用程序的配置。"""
    
    CONFIG_FILE = "config.json"
    
    DEFAULT_CONFIG = {
        "target_images": [],
        "confidence": 80,
        "box_width": 50,
        "box_height": 70,
        "disappear_delay": 2.0,
        "hotkey": "f9",
        "window_title": None
    }

    def __init__(self):
        self.config = self.load_config()

    def load_config(self):
        """从 JSON 文件加载配置，如果文件不存在则创建默认配置。"""
        if os.path.exists(self.CONFIG_FILE):
            try:
                with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 确保所有默认键都存在
                    for key, value in self.DEFAULT_CONFIG.items():
                        config.setdefault(key, value)
                    return config
            except (json.JSONDecodeError, TypeError):
                print(f"配置文件 '{self.CONFIG_FILE}' 格式错误, 将使用默认配置。")
                return self.DEFAULT_CONFIG.copy()
        else:
            return self.DEFAULT_CONFIG.copy()

    def save_config(self):
        """将当前配置保存到 JSON 文件。"""
        try:
            with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"保存配置失败: {e}")

    def get(self, key):
        """获取指定键的值。"""
        return self.config.get(key)

    def set(self, key, value):
        """设置指定键的值。"""
        self.config[key] = value
        self.save_config()

    def add_target_image(self, path):
        """添加一个目标图片路径到列表（如果不存在）。"""
        if path not in self.config["target_images"]:
            self.config["target_images"].append(path)
            self.save_config()

    def remove_target_image(self, path):
        """从列表中移除一个目标图片路径。"""
        if path in self.config["target_images"]:
            self.config["target_images"].remove(path)
            self.save_config()