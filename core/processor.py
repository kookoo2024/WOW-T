from dataclasses import dataclass, field
from typing import Optional, Dict, Callable, Tuple
from pathlib import Path
import threading
import time
import numpy as np
import cv2
import pyautogui
import keyboard

from core.config import ConfigManager, SpecConfig, IconBindingData, AppSettings
from core.matcher import ImageMatcher, MatchResult
from utils.logger import get_logger

logger = get_logger()


@dataclass
class IconBinding:
    name: str
    hotkey: str
    template: np.ndarray
    text: str = ""
    threshold: float = 0.8
    last_cast: float = 0.0
    cooldown: float = 0.5
    match_count: int = 0
    total_similarity: float = 0.0
    max_similarity: float = 0.0
    min_similarity: float = 1.0
    
    def __post_init__(self):
        if not self.text:
            import re
            number = re.search(r'\d+', self.name)
            if number:
                self.text = f"S-{number.group()}"
            else:
                self.text = self.name
    
    def update_stats(self, similarity: float):
        self.match_count += 1
        self.total_similarity += similarity
        self.max_similarity = max(self.max_similarity, similarity)
        self.min_similarity = min(self.min_similarity, similarity)
    
    def get_avg_similarity(self) -> float:
        return self.total_similarity / self.match_count if self.match_count > 0 else 0.0
    
    def get_stats_str(self) -> str:
        if self.match_count == 0:
            return " "
        return f"均{self.get_avg_similarity():.0%}"
    
    def can_cast(self) -> bool:
        return time.time() - self.last_cast >= self.cooldown


class SkillProcessor:
    def __init__(self, config_manager: Optional[ConfigManager] = None):
        self.config_manager = config_manager or ConfigManager()
        self.matcher = ImageMatcher()
        
        self.icon_bindings: Dict[str, IconBinding] = {}
        self.monitor_region: Optional[Tuple[int, int, int, int]] = None
        self.enabled = False
        
        self._lock = threading.RLock()
        self._status_callback: Optional[Callable[[str], None]] = None
        self._last_match_value = 0.0
    
    def set_status_callback(self, callback: Callable[[str], None]):
        self._status_callback = callback
    
    def update_status(self, message: str):
        logger.info(message)
        if self._status_callback:
            self._status_callback(message)
    
    @property
    def settings(self) -> AppSettings:
        if self.config_manager.current_config:
            return self.config_manager.current_config.settings
        return AppSettings()
    
    def load_config(self, spec_name: str) -> bool:
        with self._lock:
            config = self.config_manager.load_spec(spec_name)
            
            if config is None:
                logger.error(f"加载配置失败: {spec_name}")
                return False
            
            self.monitor_region = config.monitor_region
            
            self.icon_bindings.clear()
            success_count = 0
            
            for name, binding_data in config.icon_bindings.items():
                template_path = self.config_manager.get_template_path(spec_name, name)
                template = self.matcher.load_template(template_path)
                
                if template is not None:
                    binding = IconBinding(
                        name=name,
                        hotkey=binding_data.hotkey,
                        template=template,
                        text=binding_data.text,
                        threshold=config.settings.threshold
                    )
                    self.icon_bindings[name] = binding
                    success_count += 1
                    logger.debug(f"加载技能绑定: {binding.text} -> {binding.hotkey}")
                else:
                    logger.warning(f"无法加载模板: {template_path}")
            
            logger.info(f"成功加载 {success_count}/{len(config.icon_bindings)} 个技能绑定")
            return True
    
    def save_config(self) -> bool:
        with self._lock:
            spec_name = self.config_manager.current_spec
            if not spec_name:
                logger.error("没有当前配置")
                return False
            
            config = SpecConfig(
                spec_name=spec_name,
                monitor_region=self.monitor_region,
                settings=self.settings,
                icon_bindings={}
            )
            
            for name, binding in self.icon_bindings.items():
                template_path = self.config_manager.get_template_path(spec_name, name)
                
                if self.matcher.save_template(template_path, binding.template):
                    config.icon_bindings[name] = IconBindingData(
                        name=name,
                        hotkey=binding.hotkey,
                        text=binding.text,
                        threshold=binding.threshold
                    )
            
            return self.config_manager.save_spec(config)
    
    def add_icon_binding(
        self,
        name: str,
        hotkey: str,
        template: np.ndarray,
        text: str = ""
    ) -> Optional[IconBinding]:
        with self._lock:
            base_name = name
            counter = 1
            while name in self.icon_bindings:
                name = f"{base_name}_{counter}"
                counter += 1
            
            binding = IconBinding(
                name=name,
                hotkey=hotkey,
                template=template,
                text=text,
                threshold=self.settings.threshold
            )
            
            self.icon_bindings[name] = binding
            logger.info(f"添加技能绑定: {binding.text} -> {hotkey}")
            return binding
    
    def remove_icon_binding(self, name: str) -> bool:
        with self._lock:
            if name in self.icon_bindings:
                binding = self.icon_bindings.pop(name)
                logger.info(f"删除技能绑定: {binding.text}")
                return True
            return False
    
    def set_monitor_region(self, x1: int, y1: int, x2: int, y2: int):
        with self._lock:
            self.monitor_region = (x1, y1, x2 - x1, y2 - y1)
            logger.info(f"设置监控区域: {self.monitor_region}")
    
    def cast_skill(self, binding: IconBinding) -> bool:
        if not self.enabled:
            return False
        
        if not binding.can_cast():
            return False
        
        try:
            hotkey = binding.hotkey
            
            if hotkey.startswith('alt+'):
                key = hotkey[4:]
                keyboard.press('alt')
                time.sleep(0.01)
                keyboard.press(key)
                time.sleep(self.settings.key_press_delay)
                keyboard.release(key)
                keyboard.release('alt')
            else:
                keyboard.press(hotkey)
                time.sleep(self.settings.key_press_delay)
                keyboard.release(hotkey)
            
            binding.last_cast = time.time()
            binding.update_stats(self._last_match_value)
            self.update_status(f"释放技能 [{binding.text}] - 按键: {hotkey}")
            return True
            
        except Exception as e:
            logger.error(f"按键模拟失败 [{binding.text}]: {e}")
            return False
    
    def process_frame(self) -> Optional[str]:
        if not self.monitor_region or not self.enabled:
            return None
        
        try:
            with self._lock:
                region = self.monitor_region
                bindings = list(self.icon_bindings.values())
            
            screenshot = pyautogui.screenshot(region=region)
            region_cv = self.matcher.screenshot_to_cv2(screenshot)
            
            for binding in bindings:
                result = self._find_icon_with_hash(region_cv, binding)
                
                if result.found:
                    self._last_match_value = result.confidence
                    
                    if self.cast_skill(binding):
                        return binding.text
            
            return None
            
        except Exception as e:
            logger.error(f"处理帧时出错: {e}")
            return None
    
    def _find_icon_with_hash(self, region_cv: np.ndarray, binding: IconBinding) -> MatchResult:
        try:
            if len(region_cv.shape) == 3:
                region_gray = cv2.cvtColor(region_cv, cv2.COLOR_BGR2GRAY)
            else:
                region_gray = region_cv
            
            if len(binding.template.shape) == 3:
                template_gray = cv2.cvtColor(binding.template, cv2.COLOR_BGR2GRAY)
            else:
                template_gray = binding.template
            
            icon_hash, _ = self.matcher.calculate_perceptual_hash(template_gray)
            
            h, w = region_gray.shape[:2]
            icon_h, icon_w = template_gray.shape[:2]
            
            max_similarity = 0.0
            best_location = None
            
            for y in range(0, h - icon_h + 1):
                for x in range(0, w - icon_w + 1):
                    window = region_gray[y:y+icon_h, x:x+icon_w]
                    
                    window_hash, _ = self.matcher.calculate_perceptual_hash(window)
                    
                    similarity, _ = self.matcher.calculate_hash_similarity(icon_hash, window_hash)
                    
                    if similarity > max_similarity:
                        max_similarity = similarity
                        best_location = (x, y)
                    
                    if similarity >= binding.threshold:
                        icon_region = region_cv[y:y+icon_h, x:x+icon_w]
                        
                        if self.matcher.is_skill_castable(icon_region):
                            return MatchResult(found=True, confidence=similarity, location=(x, y))
            
            return MatchResult(found=False, confidence=max_similarity, location=best_location)
            
        except Exception as e:
            logger.error(f"查找图标时出错: {e}")
            return MatchResult(found=False, confidence=0.0)
    
    def _find_max_similarity(self, region_cv: np.ndarray, binding: IconBinding) -> float:
        try:
            if len(region_cv.shape) == 3:
                region_gray = cv2.cvtColor(region_cv, cv2.COLOR_BGR2GRAY)
            else:
                region_gray = region_cv
            
            if len(binding.template.shape) == 3:
                template_gray = cv2.cvtColor(binding.template, cv2.COLOR_BGR2GRAY)
            else:
                template_gray = binding.template
            
            icon_hash, _ = self.matcher.calculate_perceptual_hash(template_gray)
            
            h, w = region_gray.shape[:2]
            icon_h, icon_w = template_gray.shape[:2]
            
            max_similarity = 0.0
            
            for y in range(0, h - icon_h + 1):
                for x in range(0, w - icon_w + 1):
                    window = region_gray[y:y+icon_h, x:x+icon_w]
                    
                    window_hash, _ = self.matcher.calculate_perceptual_hash(window)
                    
                    similarity, _ = self.matcher.calculate_hash_similarity(icon_hash, window_hash)
                    
                    if similarity > max_similarity:
                        max_similarity = similarity
            
            return max_similarity
            
        except Exception as e:
            logger.error(f"检查图标相似度时出错: {e}")
            return 1.0
    
    def check_for_new_skill(self) -> Optional[np.ndarray]:
        if not self.monitor_region:
            return None
        
        try:
            screenshot = pyautogui.screenshot(region=self.monitor_region)
            region_cv = self.matcher.screenshot_to_cv2(screenshot)
            
            new_skill_threshold = self.settings.new_skill_threshold
            
            for binding in self.icon_bindings.values():
                max_sim = self._find_max_similarity(region_cv, binding)
                if max_sim >= new_skill_threshold:
                    return None
            
            return region_cv
            
        except Exception as e:
            logger.error(f"检查新技能时出错: {e}")
            return None
    
    def start(self):
        with self._lock:
            self.enabled = True
            logger.info("处理器已启动")
    
    def stop(self):
        with self._lock:
            self.enabled = False
            logger.info("处理器已停止")
    
    @property
    def is_running(self) -> bool:
        return self.enabled
