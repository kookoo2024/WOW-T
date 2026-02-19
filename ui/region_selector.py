from typing import Callable, Optional, Tuple
import threading
import tkinter as tk
from PIL import Image, ImageTk
import pyautogui

from utils.logger import get_logger

logger = get_logger()


class RegionSelector:
    def __init__(
        self,
        callback: Callable[[Optional[int], Optional[int], Optional[int], Optional[int]], None],
        size: int = 50
    ):
        self.callback = callback
        self.size = size
        self.overlay: Optional[tk.Tk] = None
        self.current_pos: Optional[Tuple[int, int]] = None
        self.is_adjusting = False
    
    def start(self):
        thread = threading.Thread(target=self._run_selector, daemon=True)
        thread.start()
    
    def _run_selector(self):
        self.overlay = tk.Tk()
        self.overlay.attributes('-alpha', 0.3)
        self.overlay.attributes('-fullscreen', True)
        self.overlay.attributes('-topmost', True)
        
        self.canvas = tk.Canvas(self.overlay, highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        
        self.canvas.bind('<Motion>', self._on_mouse_move)
        self.canvas.bind('<Button-1>', self._on_mouse_click)
        
        self.overlay.bind('<Left>', lambda e: self._adjust_position(-1, 0))
        self.overlay.bind('<Right>', lambda e: self._adjust_position(1, 0))
        self.overlay.bind('<Up>', lambda e: self._adjust_position(0, -1))
        self.overlay.bind('<Down>', lambda e: self._adjust_position(0, 1))
        self.overlay.bind('<Return>', lambda e: self._confirm_selection())
        self.overlay.bind('<Escape>', lambda e: self._cancel())
        
        self.guide_text_id = self.canvas.create_text(
            self.overlay.winfo_screenwidth() // 2,
            50,
            text="1. 移动鼠标到技能图标附近\n2. 点击鼠标左键进入微调模式\n3. 使用方向键微调位置\n4. 回车确认选择，ESC取消",
            fill="white",
            font=("Arial", 14)
        )
        
        self.preview_frame = tk.Frame(self.overlay, bg='black')
        self.preview_frame.place(x=10, y=100)
        self.preview_label = tk.Label(self.preview_frame)
        self.preview_label.pack(padx=5, pady=5)
        
        self.overlay.mainloop()
    
    def _on_mouse_move(self, event):
        if self.is_adjusting:
            return
        
        x, y = event.x, event.y
        self.current_pos = (x, y)
        self._update_selection_box(x, y)
        self._update_preview()
    
    def _on_mouse_click(self, event):
        if not self.is_adjusting:
            self.is_adjusting = True
            x, y = event.x, event.y
            self.current_pos = (x, y)
            self._update_selection_box(x, y)
            self._update_preview()
            
            self.canvas.itemconfig(
                self.guide_text_id,
                text="使用方向键微调位置\n按住Shift+方向键进行精确调整\n回车确认选择,ESC取消"
            )
            
            self.overlay.bind('<Shift-Left>', lambda e: self._adjust_position(-1, 0))
            self.overlay.bind('<Shift-Right>', lambda e: self._adjust_position(1, 0))
            self.overlay.bind('<Shift-Up>', lambda e: self._adjust_position(0, -1))
            self.overlay.bind('<Shift-Down>', lambda e: self._adjust_position(0, 1))
    
    def _adjust_position(self, dx: int, dy: int):
        if not self.is_adjusting or not self.current_pos:
            return
        
        x, y = self.current_pos
        x += dx
        y += dy
        self.current_pos = (int(x), int(y))
        self._update_selection_box(x, y)
        self._update_preview()
    
    def _update_selection_box(self, x: int, y: int):
        half_size = self.size // 2
        x1 = x - half_size
        y1 = y - half_size
        x2 = x + half_size
        y2 = y + half_size
        
        if hasattr(self, 'rect_id') and self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            x1, y1, x2, y2,
            outline='red',
            width=2
        )
        
        if hasattr(self, 'crosshair'):
            for line_id in self.crosshair:
                self.canvas.delete(line_id)
        self.crosshair = [
            self.canvas.create_line(x, y1-10, x, y1, fill='red', width=2),
            self.canvas.create_line(x, y2, x, y2+10, fill='red', width=2),
            self.canvas.create_line(x1-10, y, x1, y, fill='red', width=2),
            self.canvas.create_line(x2, y, x2+10, y, fill='red', width=2)
        ]
        
        if hasattr(self, 'center_point') and self.center_point:
            self.canvas.delete(self.center_point)
        self.center_point = self.canvas.create_oval(
            x-2, y-2, x+2, y+2,
            fill='red',
            outline='white'
        )
    
    def _update_preview(self):
        if not self.current_pos:
            return
        
        try:
            x, y = self.current_pos
            half_size = self.size // 2
            screenshot = pyautogui.screenshot(region=(
                x - half_size,
                y - half_size,
                self.size,
                self.size
            ))
            
            preview_size = self.size * 4
            screenshot = screenshot.resize((preview_size, preview_size), Image.LANCZOS)
            
            img_draw = ImageTk.PhotoImage(screenshot)
            self.preview_label.configure(image=img_draw)
            self.preview_label.image = img_draw
            
            if hasattr(self, 'coord_label'):
                self.coord_label.destroy()
            self.coord_label = tk.Label(
                self.preview_frame,
                text=f"坐标: ({x}, {y})",
                bg='black',
                fg='white'
            )
            self.coord_label.pack()
            
        except Exception as e:
            logger.error(f"更新预览时出错: {e}")
    
    def _confirm_selection(self):
        if not self.current_pos:
            return
        
        x, y = self.current_pos
        half_size = self.size // 2
        x1 = x - half_size
        y1 = y - half_size
        x2 = x + half_size
        y2 = y + half_size
        
        self.overlay.destroy()
        if self.callback:
            self.callback(x1, y1, x2, y2)
    
    def _cancel(self):
        self.overlay.destroy()
        if self.callback:
            self.callback(None, None, None, None)
