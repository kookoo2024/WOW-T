import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


_loggers: dict[str, logging.Logger] = {}
MAX_LOG_LINES = 100


class LimitedFileHandler(logging.FileHandler):
    def __init__(self, filename, mode='a', encoding=None, delay=False, max_lines=MAX_LOG_LINES):
        super().__init__(filename, mode, encoding, delay)
        self.max_lines = max_lines
    
    def emit(self, record):
        super().emit(record)
        self._trim_file()
    
    def _trim_file(self):
        try:
            with open(self.baseFilename, 'r', encoding=self.encoding) as f:
                lines = f.readlines()
            
            if len(lines) > self.max_lines:
                with open(self.baseFilename, 'w', encoding=self.encoding) as f:
                    f.writelines(lines[-self.max_lines:])
        except Exception:
            pass


def setup_logger(
    name: str = "wow_helper",
    level: int = logging.INFO,
    log_to_file: bool = True,
    log_dir: Optional[Path] = None
) -> logging.Logger:
    if name in _loggers:
        return _loggers[name]
    
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers.clear()
    
    formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    if log_to_file:
        if log_dir is None:
            log_dir = Path(__file__).parent.parent / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = log_dir / f"wow_helper_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = LimitedFileHandler(
            log_file,
            encoding='utf-8',
            mode='a'
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    _loggers[name] = logger
    return logger


def get_logger(name: str = "wow_helper") -> logging.Logger:
    if name in _loggers:
        return _loggers[name]
    return setup_logger(name)
