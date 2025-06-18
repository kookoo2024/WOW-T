# -*- coding: utf-8 -*-
import cv2
import numpy as np
import pyautogui
import keyboard
import time
import json
import os
import base64
import threading
from dataclasses import dataclass, asdict
from typing import Dict, Optional
from queue import Queue

@dataclass
class IconBinding:
    """技能图标与按键绑定"""
    name: str        # 内部名称，用于文件命名
    hotkey: str
    template: np.ndarray
    text: str = ""   # 显示名称，默认为空，后面会根据name生成
    threshold: float = 0.8
    last_cast: float = 0.0
    cooldown: float = 0.5
    match_count: int = 0
    total_similarity: float = 0.0
    max_similarity: float = 0.0
    min_similarity: float = 1.0

    def __post_init__(self):
        """在初始化后设置默认的text值"""
        if not self.text:
            # 如果没有提供text，使用name中的数字部分
            import re
            number = re.search(r'\d+', self.name)
            if number:
                self.text = f"S-{number.group()}"
            else:
                self.text = self.name

    def update_stats(self, similarity: float):
        """更新匹配度统计"""
        self.match_count += 1
        self.total_similarity += similarity
        self.max_similarity = max(self.max_similarity, similarity)
        self.min_similarity = min(self.min_similarity, similarity)

    def get_avg_similarity(self) -> float:
        """获取平均匹配度"""
        return self.total_similarity / self.match_count if self.match_count > 0 else 0.0

    def get_stats_str(self) -> str:
        """获取统计信息字符串"""
        if self.match_count == 0:
            return " "  # 使用空格
        return f"均{self.get_avg_similarity():.0%}"  # 只显示平均匹配度

    def to_dict(self):
        """转换为可序列化的字典"""
        data = asdict(self)
        # 移除不需要保存的字段
        data.pop('template')
        data.pop('match_count')
        data.pop('total_similarity')
        data.pop('max_similarity')
        data.pop('min_similarity')
        return data

    @classmethod
    def from_dict(cls, data: dict, template: np.ndarray):
        """从字典和模板图像创建实例"""
        return cls(
            name=data['name'],
            hotkey=data['hotkey'],
            template=template,
            text=data.get('text', ''),  # 如果没有text，会通过__post_init__设置默认值
            threshold=data.get('threshold', 0.8),
            last_cast=0.0,
            cooldown=data.get('cooldown', 0.5)
        )

class HekiliProcessor:
    def __init__(self):
        self.monitor_region = None
        self.icon_bindings: Dict[str, IconBinding] = {}
        self.enabled = False
        
        # 使用绝对路径保存配置和图标
        self.base_dir = os.path.abspath(os.path.dirname(__file__))
        
        self.lock = threading.Lock()
        self.event_queue = Queue()
        self.status_callback = None
        self.last_status = ""
        
        # 修改默认设置值，添加 auto_add_skills 默认为 True
        self.settings = {
            'monitor_hotkey': '`',      # 使用 ` 代表 ~ 键
            'threshold': 0.90,          # 匹配阈值改为0.90
            'scan_interval': 0.33,      # 扫描间隔改为0.33秒
            'key_press_delay': 0.19,    # 按键延迟改为0.19秒
            'auto_add_skills': True     # 自动添加技能默认开启
        }
        
        # 配置目录
        self.config_dir = "configs"
        
        # 确保配置目录存在
        os.makedirs(self.config_dir, exist_ok=True)
        os.makedirs("templates", exist_ok=True)
        
        self.last_match_value = 0.0
        
    def get_icon_path(self, name: str, spec_name: str) -> str:
        """获取图标文件路径"""
        # 直接使用 templates 目录和配置名称
        safe_name = "".join(c for c in name if c.isalnum() or c == '_')
        return os.path.join("templates", f"{spec_name}_{safe_name}.png")
        
    def save_icon_template(self, name: str, template: np.ndarray) -> bool:
        """保存图标模板到文件"""
        try:
            icon_path = self.get_icon_path(name)
            success = cv2.imwrite(icon_path, template)
            if success:
                print(f"保存图标模板成功: {icon_path}")
                return True
            else:
                print(f"保存图标模板失败: {icon_path}")
                return False
        except Exception as e:
            print(f"保存图标模板时出错: {str(e)}")
            return False
        
    def load_icon_template(self, name: str) -> Optional[np.ndarray]:
        """从文件加载图标模板"""
        try:
            icon_path = self.get_icon_path(name)
            if os.path.exists(icon_path):
                template = cv2.imread(icon_path)
                if template is not None:
                    binding = self.icon_bindings.get(name)
                    text = binding.text if binding else name
                    print(f"加载图标模板: {text}")  # 使用text
                    return template
                else:
                    print(f"图标模板读取失败: {icon_path}")
            else:
                print(f"图标模板不存在: {icon_path}")
        except Exception as e:
            print(f"加载图标模板失败: {str(e)}")
        return None
        
    def add_icon_binding(self, name: str, text: str, hotkey: str, template_image: np.ndarray):
        """添加技能图标与按键的绑定"""
        with self.lock:
            try:
                # 确保内部名称唯一
                base_name = name
                counter = 1
                while name in self.icon_bindings:
                    name = f"{base_name}_{counter}"
                    counter += 1
                    
                binding = IconBinding(
                    name=name,      # 内部名称
                    text=text,      # 显示名称
                    hotkey=hotkey,
                    template=template_image,
                    threshold=self.settings['threshold']
                )
                self.icon_bindings[name] = binding
                
                print(f"已添加技能绑定: {text} -> {hotkey}")  # 使用text
                return binding
                
            except Exception as e:
                print(f"添加技能绑定失败: {str(e)}")
                return None
                
    def remove_icon_binding(self, name: str) -> bool:
        """移除技能图标绑定"""
        with self.lock:
            try:
                # 查找实际的绑定名称
                actual_name = None
                binding_text = None
                for binding_name, binding in self.icon_bindings.items():
                    if binding.name == name:  # 使用显示名称比较
                        actual_name = binding_name
                        binding_text = binding.text
                        break
                        
                if actual_name:
                    # 删除绑定
                    del self.icon_bindings[actual_name]
                    print(f"已删除技能绑定: {binding_text}")  # 使用text
                    return True
                else:
                    print(f"未找到绑定: {name}")
                    return False
                
            except Exception as e:
                print(f"删除绑定时出错: {str(e)}")
                return False

    def save_config(self, spec_name):
        """保存配置到指定职业的配置文件"""
        try:
            # 确保配置目录存在
            if not os.path.exists(self.config_dir):
                os.makedirs(self.config_dir)
            
            # 确保模板目录存在
            template_dir = "templates"
            if not os.path.exists(template_dir):
                os.makedirs(template_dir)
            
            # 准备配置数据
            config = {
                'monitor_region': self.monitor_region,
                'settings': self.settings,
                'icon_bindings': {}
            }
            
            # 保存每个绑定的数据和模板
            for name, binding in self.icon_bindings.items():
                # 保存模板图像
                template_path = os.path.join(template_dir, f"{spec_name}_{name}.png")
                cv2.imwrite(template_path, binding.template)
                print(f"保存模板到: {template_path}")
                
                # 保存绑定数据，包括text属性
                config['icon_bindings'][name] = {
                    'hotkey': binding.hotkey,
                    'template_path': template_path,
                    'text': binding.text
                }
                print(f"保存技能绑定: {binding.text} -> {binding.hotkey}")  # 使用text
                
            # 保存配置文件
            config_path = os.path.join(self.config_dir, f"{spec_name}.json")
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            print(f"配置已保存到: {config_path}")
            return True
            
        except Exception as e:
            print(f"保存配置时出错: {str(e)}")
            return False
            
    def load_config(self, spec_name):
        """加载指定职业的配置文件"""
        try:
            # 确定配置文件路径
            config_path = os.path.join(self.config_dir, f"{spec_name}.json")
            if not os.path.exists(config_path):
                print(f"配置文件不存在: {config_path}")
                return False
            
            print(f"正在加载配置文件: {config_path}")
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 加载监控区域
            self.monitor_region = config.get('monitor_region')
            print(f"加载监控区域: {self.monitor_region}")
            
            # 加载设置
            saved_settings = config.get('settings', {})
            self.settings.update(saved_settings)
            print(f"加载设置: {self.settings}")
            
            # 清除现有绑定
            self.icon_bindings.clear()
            
            # 加载图标绑定
            bindings_data = config.get('icon_bindings', {})
            success_count = 0
            
            for name, binding_data in bindings_data.items():
                try:
                    # 构建模板文件路径
                    template_path = os.path.join("templates", f"{spec_name}_{name}.png")
                    print(f"尝试加载模板: {template_path}")
                    
                    if os.path.exists(template_path):
                        template = cv2.imread(template_path)
                        if template is not None:
                            # 创建新的绑定，包含text属性
                            binding = IconBinding(
                                name=name,
                                hotkey=binding_data['hotkey'],
                                template=template,
                                text=binding_data.get('text', name),  # 加载text属性，如果没有则使用name
                                threshold=self.settings['threshold']
                            )
                            self.icon_bindings[name] = binding
                            success_count += 1
                            print(f"成功加载技能绑定: {binding.text} ({name}) -> {binding_data['hotkey']}")
                        else:
                            print(f"无法读取模板图像: {template_path}")
                    else:
                        print(f"模板文件不存在: {template_path}")
                        
                except Exception as e:
                    print(f"加载绑定 {name} 时出错: {str(e)}")
                    continue
                
            print(f"成功加载 {success_count}/{len(bindings_data)} 个技能绑定")
            return success_count > 0
            
        except Exception as e:
            print(f"加载配置时出错: {str(e)}")
            return False

    def update_settings(self, new_settings: dict):
        """更新用户设置"""
        with self.lock:
            self.settings.update(new_settings)
            self.save_config()

    def set_monitor_region(self, x1: int, y1: int, x2: int, y2: int):
        """设置Hekili建议技能图标的监控区域"""
        with self.lock:
            self.monitor_region = (x1, y1, x2-x1, y2-y1)
            self.save_config()
        
    def find_icon_in_region(self, icon: IconBinding, region_img: np.ndarray) -> bool:
        """在指定区域内查找技能图标"""
        result = cv2.matchTemplate(region_img, icon.template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        return max_val >= self.settings['threshold']  # 使用配置的匹配阈值
        
    def cast_skill(self, binding: IconBinding) -> bool:
        """释放技能
        Returns:
            bool: 是否成功释放技能
        """
        current_time = time.time()
        if current_time - binding.last_cast >= binding.cooldown:
            try:
                keyboard.press(binding.hotkey)
                time.sleep(self.settings['key_press_delay'])
                keyboard.release(binding.hotkey)
                binding.last_cast = current_time
                binding.update_stats(self.last_match_value)
                self.update_status(f"释放技能 [{binding.name}] - 按键: {binding.hotkey}")
                return True
            except Exception as e:
                error_msg = f"按键模拟失败 [{binding.name}]: {str(e)}"
                self.update_status(error_msg)
                print(error_msg)
                return False
        return False

    def calculate_image_hash(self, image: np.ndarray, hash_size: int = 16) -> np.ndarray:
        """计算图像的感知哈希值"""
        # 转换为灰度图
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
            
        # 缩放到指定大小
        resized = cv2.resize(gray, (hash_size + 1, hash_size))
        
        # 计算差值
        diff = resized[:, 1:] > resized[:, :-1]
        
        # 转换为二进制字符串
        hash_str = ''.join(['1' if b else '0' for b in diff.flatten()])
        return diff, hash_str

    def calculate_hash_similarity(self, hash1: np.ndarray, hash2: np.ndarray) -> tuple:
        """计算两个哈希值的相似度和汉明距离"""
        if hash1.shape != hash2.shape:
            return 0.0, hash1.size
            
        # 计算汉明距离
        hamming_distance = np.sum(hash1 != hash2)
        max_distance = hash1.size
        
        # 转换为相似度
        similarity = 1 - (hamming_distance / max_distance)
        return similarity, hamming_distance

    def find_icon_in_region_with_value(self, binding: IconBinding, region_cv: np.ndarray) -> tuple[float, float]:
        """在区域中查找图标并返回匹配值"""
        try:
            # 转换为灰度图以减少颜色影响
            if len(region_cv.shape) == 3:
                region_gray = cv2.cvtColor(region_cv, cv2.COLOR_BGR2GRAY)
            else:
                region_gray = region_cv
            
            if len(binding.template.shape) == 3:
                template_gray = cv2.cvtColor(binding.template, cv2.COLOR_BGR2GRAY)
            else:
                template_gray = binding.template

            # 获取图标的哈希值
            icon_hash, _ = self.calculate_image_hash(template_gray)
            
            # 获取区域的大小
            h, w = region_gray.shape[:2]
            icon_h, icon_w = template_gray.shape[:2]
            
            max_similarity = 0.0
            min_hamming = icon_hash.size  # 最大可能的汉明距离
            
            # 在区域内滑动窗口，使用更小的步长以提高精度
            for y in range(0, h - icon_h + 1):
                for x in range(0, w - icon_w + 1):
                    # 提取当前窗口
                    window = region_gray[y:y+icon_h, x:x+icon_w]
                    
                    # 计算窗口的哈希值
                    window_hash, _ = self.calculate_image_hash(window)
                    
                    # 计算相似度和汉明距离
                    similarity, hamming = self.calculate_hash_similarity(icon_hash, window_hash)
                    
                    if similarity > max_similarity:
                        max_similarity = similarity
                        min_hamming = hamming
                        
                    # 如果找到足够相似的图标，提前返回
                    if similarity >= binding.threshold:
                        self.last_match_value = similarity  # 保存匹配值
                        if max_similarity >= binding.threshold:
                            print(f"找到技能: {binding.text}, 匹配度: {max_similarity:.2%}")  # 使用text属性
                        return max_similarity, hamming
            
            return max_similarity, min_hamming
            
        except Exception as e:
            print(f"查找图标时出错: {str(e)}")
            return 0.0, float('inf')

    def process_frame(self):
        """处理当前帧,检查Hekili建议区域并释放技能"""
        if not self.monitor_region or not self.enabled:
            return
            
        try:
            with self.lock:
                region = self.monitor_region
                bindings = list(self.icon_bindings.values())
            
            # 截取Hekili建议区域
            screenshot = pyautogui.screenshot(region=region)
            region_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            
            # 检查每个已绑定的图标
            found_icon = False
            for binding in bindings:
                match_value, hamming = self.find_icon_in_region_with_value(binding, region_cv)
                if match_value >= self.settings['threshold']:
                    self.update_status(
                        f"发现技能图标 [{binding.name}] - 相似度: {match_value:.1%} (汉明距离: {hamming})"
                    )
                    self.cast_skill(binding)
                    found_icon = True
                    break
                else:
                    # 显示最接近的匹配结果
                    self.update_status(
                        f"技能 [{binding.name}] - 最大相似度: {match_value:.1%} (汉明距离: {hamming})"
                    )
                    
            if not found_icon:
                self.update_status("监控中... 未发现匹配的技能图标")
                    
        except Exception as e:
            error_msg = f"处理帧时出错: {str(e)}"
            self.update_status(error_msg)
            print(error_msg)
            
    def capture_icon_template(self, x1: int, y1: int, x2: int, y2: int) -> np.ndarray:
        """捕获技能图标模板"""
        screenshot = pyautogui.screenshot(region=(x1, y1, x2-x1, y2-y1))
        return cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

    def set_status_callback(self, callback):
        """设置状态更新回调函数"""
        self.status_callback = callback
        
    def update_status(self, status: str):
        """更新状态信息"""
        self.last_status = status
        if self.status_callback:
            self.status_callback(status)
            
    def start_key_handler(self):
        """启动按键处理线程"""
        def key_handler():
            while self.enabled:
                try:
                    event_type, data = self.event_queue.get(timeout=0.1)
                    if event_type == 'press_key':
                        keyboard.press_and_release(data)
                except:
                    continue

        thread = threading.Thread(target=key_handler, daemon=True)
        thread.start()
        self.update_status("按键处理线程已启动")
        return thread

    def toggle_enabled(self):
        """切换启用状态"""
        self.enabled = not self.enabled
        if self.enabled:
            self.update_status("自动施法已开启")
        else:
            self.update_status("自动施法已关闭")
        return self.enabled 

    def clear_bindings(self):
        """清除所有图标绑定"""
        with self.lock:
            self.icon_bindings.clear() 

    def delete_config(self, spec_name):
        """删除指定职业的配置及其相关文件"""
        try:
            # 删除配置文件
            config_path = os.path.join(self.config_dir, f"{spec_name}.json")
            if os.path.exists(config_path):
                os.remove(config_path)
                print(f"已删除配置文件: {config_path}")
            
            # 删除相关的模板文件
            template_dir = "templates"
            if os.path.exists(template_dir):
                # 删除该职业的所有模板文件
                for file in os.listdir(template_dir):
                    if file.startswith(f"{spec_name}_"):
                        template_path = os.path.join(template_dir, file)
                        os.remove(template_path)
                        print(f"已删除模板文件: {template_path}")
                    
            return True
        except Exception as e:
            print(f"删除配置时出错: {str(e)}")
            return False 