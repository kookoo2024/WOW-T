import sys
import locale

if sys.platform.startswith('win'):
    if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
else:
    if sys.stdout and getattr(sys.stdout, 'encoding', None) != 'UTF-8' and hasattr(sys.stdout, 'fileno'):
        sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
    if sys.stderr and getattr(sys.stderr, 'encoding', None) != 'UTF-8' and hasattr(sys.stderr, 'fileno'):
        sys.stderr = open(sys.stderr.fileno(), mode='w', encoding='utf-8', buffering=1)

locale.setlocale(locale.LC_ALL, 'zh_CN.UTF-8' if sys.platform != 'win32' else 'Chinese')

from utils.logger import setup_logger
from ui.main_window import MainWindow

logger = setup_logger()


def main():
    logger.info("启动 WOW 技能辅助工具...")
    
    try:
        app = MainWindow()
        app.run()
    except Exception as e:
        logger.error(f"程序运行出错: {e}")
        raise
    finally:
        logger.info("程序已退出")


if __name__ == "__main__":
    main()
