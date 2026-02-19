from dataclasses import dataclass
from typing import Optional, Tuple, List
import cv2
import numpy as np
from pathlib import Path

from utils.logger import get_logger

logger = get_logger()


@dataclass
class MatchResult:
    found: bool
    confidence: float
    location: Optional[Tuple[int, int]] = None


class ImageMatcher:
    TM_CCOEFF_NORMED = cv2.TM_CCOEFF_NORMED
    TM_CCORR_NORMED = cv2.TM_CCORR_NORMED
    TM_SQDIFF_NORMED = cv2.TM_SQDIFF_NORMED
    
    def __init__(self, default_threshold: float = 0.90):
        self.default_threshold = default_threshold
        self._template_cache: dict[str, np.ndarray] = {}
    
    def load_template(self, path: Path) -> Optional[np.ndarray]:
        cache_key = str(path)
        
        if cache_key in self._template_cache:
            return self._template_cache[cache_key]
        
        if not path.exists():
            logger.warning(f"模板文件不存在: {path}")
            return None
        
        try:
            with open(path, 'rb') as f:
                img_data = f.read()
            img_array = np.frombuffer(img_data, np.uint8)
            template = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            
            if template is None:
                logger.error(f"无法解码模板图像: {path}")
                return None
            
            self._template_cache[cache_key] = template
            logger.debug(f"加载模板: {path}")
            return template
            
        except Exception as e:
            logger.error(f"加载模板失败 {path}: {e}")
            return None
    
    def save_template(self, path: Path, template: np.ndarray) -> bool:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            
            success, encoded_img = cv2.imencode('.png', template)
            if not success:
                logger.error(f"编码模板图像失败: {path}")
                return False
            
            with open(path, 'wb') as f:
                f.write(encoded_img.tobytes())
            
            cache_key = str(path)
            self._template_cache[cache_key] = template
            
            logger.debug(f"保存模板: {path}")
            return True
            
        except Exception as e:
            logger.error(f"保存模板失败 {path}: {e}")
            return False
    
    def match_template(
        self,
        image: np.ndarray,
        template: np.ndarray,
        threshold: Optional[float] = None,
        method: int = None
    ) -> MatchResult:
        if method is None:
            method = self.TM_CCOEFF_NORMED
        
        if threshold is None:
            threshold = self.default_threshold
        
        if image.shape[0] < template.shape[0] or image.shape[1] < template.shape[1]:
            return MatchResult(found=False, confidence=0.0)
        
        result = cv2.matchTemplate(image, template, method)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        
        if method in [self.TM_SQDIFF_NORMED]:
            confidence = 1 - min_val
            location = min_loc
        else:
            confidence = max_val
            location = max_loc
        
        found = confidence >= threshold
        return MatchResult(
            found=found,
            confidence=confidence,
            location=location if found else None
        )
    
    def match_template_multi_scale(
        self,
        image: np.ndarray,
        template: np.ndarray,
        threshold: Optional[float] = None,
        scales: Optional[List[float]] = None
    ) -> MatchResult:
        if threshold is None:
            threshold = self.default_threshold
        
        if scales is None:
            scales = [1.0, 0.95, 1.05]
        
        best_result = MatchResult(found=False, confidence=0.0)
        
        for scale in scales:
            if scale != 1.0:
                resized_template = cv2.resize(
                    template,
                    None,
                    fx=scale,
                    fy=scale,
                    interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR
                )
            else:
                resized_template = template
            
            if (image.shape[0] < resized_template.shape[0] or 
                image.shape[1] < resized_template.shape[1]):
                continue
            
            result = self.match_template(image, resized_template, threshold)
            
            if result.confidence > best_result.confidence:
                best_result = result
            
            if result.found:
                break
        
        return best_result
    
    def match_with_edge_detection(
        self,
        image: np.ndarray,
        template: np.ndarray,
        threshold: Optional[float] = None
    ) -> MatchResult:
        if threshold is None:
            threshold = self.default_threshold
        
        image_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY) if len(template.shape) == 3 else template
        
        image_edges = cv2.Canny(image_gray, 50, 150)
        template_edges = cv2.Canny(template_gray, 50, 150)
        
        return self.match_template(image_edges, template_edges, threshold)
    
    def calculate_perceptual_hash(
        self,
        image: np.ndarray,
        hash_size: int = 16
    ) -> Tuple[np.ndarray, str]:
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        resized = cv2.resize(gray, (hash_size + 1, hash_size))
        diff = resized[:, 1:] > resized[:, :-1]
        hash_str = ''.join(['1' if b else '0' for b in diff.flatten()])
        
        return diff, hash_str
    
    def calculate_hash_similarity(
        self,
        hash1: np.ndarray,
        hash2: np.ndarray
    ) -> Tuple[float, int]:
        if hash1.shape != hash2.shape:
            return 0.0, hash1.size
        
        hamming_distance = np.sum(hash1 != hash2)
        max_distance = hash1.size
        similarity = 1 - (hamming_distance / max_distance)
        
        return similarity, hamming_distance
    
    def is_skill_castable(self, icon_image: np.ndarray) -> bool:
        if icon_image is None or icon_image.size == 0:
            return True
        
        try:
            if len(icon_image.shape) == 3:
                hsv = cv2.cvtColor(icon_image, cv2.COLOR_BGR2HSV)
                saturation = hsv[:, :, 1]
            else:
                return True
            
            mean_saturation = np.mean(saturation) / 255.0
            
            if mean_saturation < 0.08:
                return False
            
            return True
                
        except Exception as e:
            logger.error(f"判断技能状态时出错: {e}")
            return True
    
    def clear_cache(self):
        self._template_cache.clear()
        logger.debug("模板缓存已清除")
    
    @staticmethod
    def screenshot_to_cv2(screenshot) -> np.ndarray:
        return cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
