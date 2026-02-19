from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import json
import re

from utils.logger import get_logger

logger = get_logger()


@dataclass
class AppSettings:
    monitor_hotkey: str = '`'
    threshold: float = 0.90
    scan_interval: float = 0.33
    key_press_delay: float = 0.19
    auto_add_skills: bool = True
    new_skill_threshold: float = 0.72
    
    def validate(self) -> bool:
        if not 0 < self.scan_interval <= 1:
            raise ValueError("扫描间隔必须在0-1秒之间")
        if not 0 < self.threshold <= 1:
            raise ValueError("匹配阈值必须在0-1之间")
        if not 0 < self.key_press_delay <= 1:
            raise ValueError("按键延迟必须在0-1秒之间")
        if not 0 < self.new_skill_threshold < 1:
            raise ValueError("新技能阈值必须在0-1之间")
        if not self.monitor_hotkey:
            raise ValueError("监控热键不能为空")
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AppSettings':
        return cls(
            monitor_hotkey=data.get('monitor_hotkey', '`'),
            threshold=data.get('threshold', 0.90),
            scan_interval=data.get('scan_interval', 0.33),
            key_press_delay=data.get('key_press_delay', 0.19),
            auto_add_skills=data.get('auto_add_skills', True),
            new_skill_threshold=data.get('new_skill_threshold', 0.72)
        )


@dataclass
class IconBindingData:
    name: str
    hotkey: str
    text: str = ""
    threshold: float = 0.8
    
    def __post_init__(self):
        if not self.text:
            number = re.search(r'\d+', self.name)
            if number:
                self.text = f"S-{number.group()}"
            else:
                self.text = self.name
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'hotkey': self.hotkey,
            'text': self.text,
            'threshold': self.threshold
        }
    
    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> 'IconBindingData':
        return cls(
            name=name,
            hotkey=data.get('hotkey', ''),
            text=data.get('text', ''),
            threshold=data.get('threshold', 0.8)
        )


@dataclass
class SpecConfig:
    spec_name: str
    monitor_region: Optional[Tuple[int, int, int, int]] = None
    settings: AppSettings = field(default_factory=AppSettings)
    icon_bindings: Dict[str, IconBindingData] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'monitor_region': list(self.monitor_region) if self.monitor_region else None,
            'settings': self.settings.to_dict(),
            'icon_bindings': {
                name: binding.to_dict() 
                for name, binding in self.icon_bindings.items()
            }
        }
    
    @classmethod
    def from_dict(cls, spec_name: str, data: Dict[str, Any]) -> 'SpecConfig':
        monitor_region = data.get('monitor_region')
        if monitor_region:
            monitor_region = tuple(monitor_region)
        
        settings_data = data.get('settings', {})
        settings = AppSettings.from_dict(settings_data)
        
        bindings_data = data.get('icon_bindings', {})
        icon_bindings = {
            name: IconBindingData.from_dict(name, binding_data)
            for name, binding_data in bindings_data.items()
        }
        
        return cls(
            spec_name=spec_name,
            monitor_region=monitor_region,
            settings=settings,
            icon_bindings=icon_bindings
        )


class ConfigManager:
    def __init__(self, config_dir: Optional[Path] = None, template_dir: Optional[Path] = None):
        self.base_dir = Path(__file__).parent.parent
        self.config_dir = config_dir or self.base_dir / "configs"
        self.template_dir = template_dir or self.base_dir / "templates"
        self.history_file = self.config_dir / "last_config.json"
        
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.template_dir.mkdir(parents=True, exist_ok=True)
        
        self._current_spec: Optional[str] = None
        self._current_config: Optional[SpecConfig] = None
    
    def get_available_specs(self) -> list[str]:
        specs = []
        for config_file in self.config_dir.glob("*.json"):
            if config_file.stem != "last_config":
                specs.append(config_file.stem)
        return sorted(specs)
    
    def spec_exists(self, spec_name: str) -> bool:
        config_path = self.config_dir / f"{spec_name}.json"
        return config_path.exists()
    
    def load_spec(self, spec_name: str) -> Optional[SpecConfig]:
        config_path = self.config_dir / f"{spec_name}.json"
        
        if not config_path.exists():
            logger.warning(f"配置文件不存在: {config_path}")
            return None
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            config = SpecConfig.from_dict(spec_name, data)
            self._current_spec = spec_name
            self._current_config = config
            
            logger.info(f"成功加载配置: {spec_name}")
            return config
            
        except Exception as e:
            logger.error(f"加载配置失败 {spec_name}: {e}")
            return None
    
    def save_spec(self, config: SpecConfig) -> bool:
        config_path = self.config_dir / f"{config.spec_name}.json"
        
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config.to_dict(), f, ensure_ascii=False, indent=2)
            
            self._current_spec = config.spec_name
            self._current_config = config
            
            logger.info(f"配置已保存: {config_path}")
            return True
            
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            return False
    
    def delete_spec(self, spec_name: str) -> bool:
        config_path = self.config_dir / f"{spec_name}.json"
        
        try:
            if config_path.exists():
                config_path.unlink()
            
            for template_file in self.template_dir.glob(f"{spec_name}_*.png"):
                template_file.unlink()
            
            if self._current_spec == spec_name:
                self._current_spec = None
                self._current_config = None
            
            logger.info(f"已删除配置: {spec_name}")
            return True
            
        except Exception as e:
            logger.error(f"删除配置失败: {e}")
            return False
    
    def get_template_path(self, spec_name: str, binding_name: str) -> Path:
        safe_name = "".join(c for c in binding_name if c.isalnum() or c in ('_', '-'))
        return self.template_dir / f"{spec_name}_{safe_name}.png"
    
    def load_history(self) -> Dict[str, Any]:
        if not self.history_file.exists():
            return {}
        
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载历史配置失败: {e}")
            return {}
    
    def save_history(self, history: Dict[str, Any]) -> bool:
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"保存历史配置失败: {e}")
            return False
    
    @property
    def current_spec(self) -> Optional[str]:
        return self._current_spec
    
    @property
    def current_config(self) -> Optional[SpecConfig]:
        return self._current_config
