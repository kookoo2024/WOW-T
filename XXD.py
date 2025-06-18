import sys
import locale
import json
import os
import re

# 设置默认编码为UTF-8
if sys.platform.startswith('win'):
    # Windows系统
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
else:
    # 其他系统
    if sys.stdout.encoding != 'UTF-8':
        sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
    if sys.stderr.encoding != 'UTF-8':
        sys.stderr = open(sys.stderr.fileno(), mode='w', encoding='utf-8', buffering=1)

# 设置locale
locale.setlocale(locale.LC_ALL, 'zh_CN.UTF-8' if sys.platform != 'win32' else 'Chinese')

import customtkinter as ctk
import cv2
import numpy as np
import pyautogui
import keyboard
import threading
import time
from PIL import Image, ImageTk
from skill_processor import HekiliProcessor, IconBinding
from pynput import keyboard as kb
from pynput import mouse
import tkinter as tk

class RegionSelector:
    def __init__(self, callback, size=50):
        self.callback = callback
        self.size = size
        self.overlay = None
        self.current_pos = None
        self.is_adjusting = False
        
    def start(self):
        """开始区域选择"""
        # 在新线程中启动选择器
        thread = threading.Thread(target=self._run_selector)
        thread.daemon = True
        thread.start()
        
    def _run_selector(self):
        """在新线程中运行选择器"""
        # 创建全屏透明窗口
        self.overlay = tk.Tk()
        self.overlay.attributes('-alpha', 0.3)
        self.overlay.attributes('-fullscreen', True)
        self.overlay.attributes('-topmost', True)
        
        # 创建画布
        self.canvas = tk.Canvas(self.overlay, highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        
        # 绑定鼠标事件
        self.canvas.bind('<Motion>', self.on_mouse_move)
        self.canvas.bind('<Button-1>', self.on_mouse_click)
        
        # 绑定键盘事件用于微调
        self.overlay.bind('<Left>', lambda e: self.adjust_position(-1, 0))
        self.overlay.bind('<Right>', lambda e: self.adjust_position(1, 0))
        self.overlay.bind('<Up>', lambda e: self.adjust_position(0, -1))
        self.overlay.bind('<Down>', lambda e: self.adjust_position(0, 1))
        self.overlay.bind('<Return>', lambda e: self.confirm_selection())  # 回车确认
        self.overlay.bind('<Escape>', lambda e: self.cancel())  # ESC取消
        
        # 添加提示文本
        self.guide_text_id = self.canvas.create_text(
            self.overlay.winfo_screenwidth() // 2,
            50,
            text="1. 移动鼠标到技能图标附近\n2. 点击鼠标左键进入微调模式\n3. 使用方向键微调位置\n4. 回车确认选择，ESC取消",
            fill="white",
            font=("Arial", 14)
        )
        
        # 添加预览窗口
        self.preview_frame = tk.Frame(self.overlay, bg='black')
        self.preview_frame.place(x=10, y=100)
        self.preview_label = tk.Label(self.preview_frame)
        self.preview_label.pack(padx=5, pady=5)
        
        self.overlay.mainloop()
        
    def on_mouse_move(self, event):
        """鼠标移动时更新选择框"""
        if self.is_adjusting:
            return
            
        x, y = event.x, event.y
        self.current_pos = (x, y)
        self.update_selection_box(x, y)
        self.update_preview()
        
    def on_mouse_click(self, event):
        """鼠标点击时进入微调模式"""
        if not self.is_adjusting:
            self.is_adjusting = True
            x, y = event.x, event.y
            self.current_pos = (x, y)
            self.update_selection_box(x, y)
            self.update_preview()
            
            # 更新提示文本
            self.canvas.itemconfig(
                self.guide_text_id,
                text="使用方向键微调位置\n按住Shift+方向键进行精确调整\n回车确认选择,ESC取消"
            )
            
            # 绑定Shift+方向键进行精确调整
            self.overlay.bind('<Shift-Left>', lambda e: self.adjust_position(-1, 0))
            self.overlay.bind('<Shift-Right>', lambda e: self.adjust_position(1, 0))
            self.overlay.bind('<Shift-Up>', lambda e: self.adjust_position(0, -1))
            self.overlay.bind('<Shift-Down>', lambda e: self.adjust_position(0, 1))
            
    def adjust_position(self, dx, dy):
        """微调选择框位置"""
        if not self.is_adjusting or not self.current_pos:
            return
            
        x, y = self.current_pos
        # 检查是否按下Shift键
        if self.overlay.focus_get() and self.overlay.focus_get().winfo_toplevel() == self.overlay:
            state = self.overlay.focus_get().winfo_toplevel().winfo_children()[0].winfo_toplevel().state()
            if state & 0x0001:  # Shift键被按下
                dx = dx * 0.2  # 精确调整
                dy = dy * 0.2
                
        x += dx
        y += dy
        self.current_pos = (int(x), int(y))
        self.update_selection_box(x, y)
        self.update_preview()
        
    def update_selection_box(self, x, y):
        """更新选择框显示"""
        half_size = self.size // 2
        x1 = x - half_size
        y1 = y - half_size
        x2 = x + half_size
        y2 = y + half_size
        
        # 更新选择框
        if hasattr(self, 'rect_id') and self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            x1, y1, x2, y2,
            outline='red',
            width=2
        )
        
        # 更新十字线
        if hasattr(self, 'crosshair'):
            for line_id in self.crosshair:
                self.canvas.delete(line_id)
        self.crosshair = [
            self.canvas.create_line(x, y1-10, x, y1, fill='red', width=2),  # 上
            self.canvas.create_line(x, y2, x, y2+10, fill='red', width=2),  # 下
            self.canvas.create_line(x1-10, y, x1, y, fill='red', width=2),  # 左
            self.canvas.create_line(x2, y, x2+10, y, fill='red', width=2)   # 右
        ]
        
        # 添加中心点
        if hasattr(self, 'center_point') and self.center_point:
            self.canvas.delete(self.center_point)
        self.center_point = self.canvas.create_oval(
            x-2, y-2, x+2, y+2,
            fill='red',
            outline='white'
        )
        
    def update_preview(self):
        """更新预览图像"""
        if not self.current_pos:
            return
            
        try:
            x, y = self.current_pos
            half_size = self.size // 2
            # 截取当前区域的截图
            screenshot = pyautogui.screenshot(region=(
                x - half_size,
                y - half_size,
                self.size,
                self.size
            ))
            
            # 放大显示
            preview_size = self.size * 4  # 放大4倍以便更清晰地查看
            screenshot = screenshot.resize((preview_size, preview_size), Image.LANCZOS)
            
            # 在预览图像上添加网格线
            img_draw = ImageTk.PhotoImage(screenshot)
            self.preview_label.configure(image=img_draw)
            self.preview_label.image = img_draw
            
            # 更新坐标信息
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
            print(f"更新预览时出错: {str(e)}")
            
    def confirm_selection(self):
        """确认选择"""
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
            
    def cancel(self):
        """取消选择"""
        self.overlay.destroy()
        if self.callback:
            self.callback(None, None, None, None)

class WoWSkillAssistant:
    def get_display_name(self, spec_name, max_length=6):
        """
        获取配置名称的显示版本
        对于中文名称，优先显示完整名称，如果太长则智能截取
        """
        if not spec_name:
            return ""

        # 检查是否包含中文字符
        import re
        has_chinese = bool(re.search(r'[\u4e00-\u9fff]', spec_name))

        if has_chinese:
            # 对于中文名称，如果长度合理就完整显示，否则截取前4个字符
            if len(spec_name) <= 6:
                return spec_name
            else:
                return spec_name[:4] + "..."
        else:
            # 对于英文名称，如果长度合理就完整显示，否则取后6个字符
            if len(spec_name) <= max_length:
                return spec_name
            else:
                return spec_name[-max_length:]

    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("孟子 - 加载中...")
        
        # 确保配置目录存在
        self.config_dir = "configs"
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)
        
        # 修改历史配置文件路径
        self.history_file = os.path.join(self.config_dir, "last_config.json")
        print("开始加载历史配置...")
        self.last_config = self.load_last_config()
        print(f"历史配置加载结果: {self.last_config}")
        
        # 初始化处理器
        self.processor = HekiliProcessor()
        
        # 先恢复所有设置
        if "settings" in self.last_config:
            self.processor.settings.update(self.last_config["settings"])
        
        # 恢复监控区域
        if "monitor_region" in self.last_config:
            self.processor.monitor_region = self.last_config["monitor_region"]
        
        # 加载所有可用配置
        self.specs = self.load_specs()
        print(f"可用配置列表: {self.specs}")
        
        # 从历史记录加载上次使用的配置
        self.current_spec = self.last_config.get("last_spec", "")
        print(f"尝试加载的配置: {self.current_spec}")
        if self.current_spec and self.current_spec in self.specs:
            print(f"正在加载上次使用的配置: {self.current_spec}")
            if not self.processor.load_config(spec_name=self.current_spec):
                print(f"加载配置失败: {self.current_spec}")
                self.current_spec = self.specs[0] if self.specs else ""
                if self.current_spec:
                    self.processor.load_config(spec_name=self.current_spec)
        elif self.specs:
            self.current_spec = self.specs[0]
            self.processor.load_config(spec_name=self.current_spec)
        else:
            self.current_spec = ""
        
        # 修改窗口位置加载逻辑
        window_config = self.last_config.get("window", {})
        if window_config:
            try:
                window_width = window_config.get("width", 145)
                window_height = window_config.get("height", 50)
                window_x = window_config.get("x", None)
                window_y = window_config.get("y", None)
                
                # 确保窗口位置在屏幕内
                screen_width = self.root.winfo_screenwidth()
                screen_height = self.root.winfo_screenheight()
                
                if all(v is not None for v in (window_x, window_y, window_width, window_height)):
                    # 确保窗口完全在屏幕内
                    window_x = max(0, min(window_x, screen_width - window_width))
                    window_y = max(0, min(window_y, screen_height - window_height))
                    
                    # 设置窗口位置和大小
                    geometry = f"{window_width}x{window_height}+{window_x}+{window_y}"
                    print(f"设置窗口位置: {geometry}")
                    self.root.geometry(geometry)
                    
                    # 强制更新
                    self.root.update_idletasks()
            except Exception as e:
                print(f"恢复窗口位置时出错: {str(e)}")
                self._set_default_window_position()
        else:
            self._set_default_window_position()
        
        # 设置窗口属性
        self.root.attributes('-topmost', True)
        if sys.platform.startswith('win'):
            self.root.attributes('-toolwindow', True)
        else:
            self.root.resizable(False, False)
        
        # 设置主题
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # 初始化其他属性
        self.running = False
        self.processor.set_status_callback(self.update_status_display)
        self.recent_keys = []
        self.max_recent_keys = 6
        self.last_ui_update = 0
        self.ui_update_interval = 1.0
        self.pending_update = False
        
        # 设置UI和热键
        self.setup_ui()
        self.setup_hotkeys()
        
        # 更新UI显示
        self.update_binding_list()
        self.update_region_info()
        if self.current_spec:
            self.status_label.configure(text=f"已加载配置: {self.current_spec}")
            self.spec_var.set(self.current_spec)
            self.root.title(f"孟子 - {self.get_display_name(self.current_spec)}")
        else:
            self.status_label.configure(text="请创建新的职业配置")
            self.spec_var.set("请创建配置")
            self.root.title("孟子 - 未选择配置")
        
        # 初始化标题
        self.update_title()
        
        # 绑定窗口关闭事件，确保保存状态
        self.root.protocol("WM_DELETE_WINDOW", self.quit_app)
        
        # 添加窗口移动事件绑定
        self.root.bind("<Configure>", self.on_window_configure)
        
        # 恢复自动保存
        self.start_auto_save()
        
    def _set_default_window_position(self):
        """设置默认窗口位置"""
        window_width = 145
        window_height = 50
        x = (self.root.winfo_screenwidth() - window_width) // 2
        y = 30
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.root.update_idletasks()
        
    def setup_ui(self):
        # 创建主框架
        self.main_frame = ctk.CTkFrame(self.root)
        self.main_frame.pack(fill="both", expand=True, padx=5, pady=5)  # 减小边距
        
        # 控制按钮行 - 合并区域设置和控制按钮
        control_frame = ctk.CTkFrame(self.main_frame)
        control_frame.pack(fill="x", padx=5, pady=2)  # 减小边距
        
        # 左侧按钮组
        left_btn_frame = ctk.CTkFrame(control_frame)
        left_btn_frame.pack(side="left", fill="x", expand=True)
        
        self.start_btn = ctk.CTkButton(
            left_btn_frame,
            text="开始监控",
            command=self.toggle_monitoring,
            width=120,
            height=28
        )
        self.start_btn.pack(side="left", padx=2)

        # 添加职业选择下拉框到开始按钮后
        self.spec_var = ctk.StringVar(value=self.current_spec if self.current_spec else "请创建配置")

        def on_spec_change(new_spec):
            """处理配置切换"""
            print(f"切换配置: 从 {self.current_spec} 到 {new_spec}")
            self.change_spec(new_spec)

        self.spec_dropdown = ctk.CTkOptionMenu(
            left_btn_frame,
            variable=self.spec_var,
            values=self.specs if self.specs else ["请创建配置"],
            command=on_spec_change,
            width=100
        )
        self.spec_dropdown.pack(side="left", padx=5)

        # 添加新建职业按钮
        add_spec_btn = ctk.CTkButton(
            left_btn_frame,
            text="新建",
            command=self.create_new_spec,
            width=60,
            height=24
        )
        add_spec_btn.pack(side="left", padx=2)

        # 添加删除职业按钮
        delete_spec_btn = ctk.CTkButton(
            left_btn_frame,
            text="删除",
            command=self.delete_spec,
            width=60,
            height=24,
            fg_color="#D35B58",
            hover_color="#C15856"
        )
        delete_spec_btn.pack(side="left", padx=2)
        
        # 右侧按钮组
        right_btn_frame = ctk.CTkFrame(control_frame)
        right_btn_frame.pack(side="right", fill="x")
        
        # 设区按钮移到右侧
        self.set_region_btn = ctk.CTkButton(
            right_btn_frame,
            text="设区",
            command=self.set_monitor_region,
            width=60,
            height=28
        )
        self.set_region_btn.pack(side="left", padx=2)
        
        self.preview_region_btn = ctk.CTkButton(
            right_btn_frame,
            text="预览",
            command=self.preview_monitor_region,
            width=60,
            height=28
        )
        self.preview_region_btn.pack(side="left", padx=2)

        # 设置按钮移到预览按钮之后
        self.settings_btn = ctk.CTkButton(
            right_btn_frame,
            text="设置",
            command=self.show_settings,
            width=60,
            height=28
        )
        self.settings_btn.pack(side="left", padx=2)

        # 隐藏添加技能按钮以减少空间
        # self.add_binding_btn = ctk.CTkButton(
        #     right_btn_frame,
        #     text="添加技能",
        #     command=self.quick_add_binding,
        #     width=80,
        #     height=28
        # )
        # self.add_binding_btn.pack(side="left", padx=2)
        
        # 绑定列表区域
        self.bindings_frame = ctk.CTkFrame(self.main_frame)
        self.bindings_frame.pack(fill="both", expand=True, padx=5, pady=1)  # pady从2改为1
        
        # 状态栏
        self.status_frame = ctk.CTkFrame(self.main_frame)
        self.status_frame.pack(fill="x", padx=5, pady=1)  # pady从2改为1
        
        self.status_label = ctk.CTkLabel(
            self.status_frame, 
            text="就绪",
            font=("Arial", 12)
        )
        self.status_label.pack(side="left", padx=5)
        
        # 更新绑定列表
        self.update_binding_list()
        
    def setup_hotkeys(self):
        """设置全局快捷键"""
        self.keyboard_listener = kb.Listener(on_press=self.on_key_press)
        self.keyboard_listener.start()
        
    def on_key_press(self, key):
        """处理快捷键"""
        try:
            if hasattr(key, 'char') and key.char == self.processor.settings['monitor_hotkey']:
                self.toggle_monitoring()
            elif key == kb.Key.f9:  # 使用F9作为切换自动添加的热键
                self.toggle_auto_add()
            elif key == kb.Key.f10:
                self.quick_add_binding()
            elif key == kb.Key.f11:
                self.set_monitor_region()
            elif key == kb.Key.f12:
                self.quit_app()
        except Exception as e:
            print(f"处理快捷键时出错: {str(e)}")
            
    def quick_add_binding(self):
        """快速添加技能绑定"""
        self.status_label.configure(text="请按下要绑定的快捷键...")
        
        def on_key(key):
            try:
                if hasattr(key, 'char'):
                    hotkey = key.char
                else:
                    hotkey = key.name
                    
                # 创建技能名称 (使用英文)
                skill_count = len(self.processor.icon_bindings) + 1
                # 找到未使用的技能编号
                while f"skill_{skill_count}" in self.processor.icon_bindings:
                    skill_count += 1
                name = f"skill_{skill_count}"
                
                # 最小化窗口并等待用户选择图标
                self.root.iconify()
                
                def on_icon_selected(x1, y1, x2, y2):
                    def restore_ui():
                        self.root.deiconify()
                        if all(v is not None for v in (x1, y1, x2, y2)):
                            template = self.processor.capture_icon_template(
                                x1, y1, x2, y2
                            )
                            
                            self.processor.add_icon_binding(name, hotkey, template)
                            self.update_binding_list()
                            self.status_label.configure(text=f"已添加绑定: {name} -> {hotkey}")
                        else:
                            self.status_label.configure(text="添加绑定已取消")
                    
                    # 在主线程中更新UI
                    self.root.after(0, restore_ui)
                
                # 使用相同的选择器来选择技能图标
                selector = RegionSelector(on_icon_selected, size=48)
                selector.start()
                
                return False
            except Exception as e:
                self.status_label.configure(text=f"添加绑定时出错: {str(e)}")
                return False
        
        # 在新线程中监听按键
        key_thread = threading.Thread(target=lambda: kb.Listener(on_press=on_key).start())
        key_thread.daemon = True
        key_thread.start()
        
    def set_monitor_region(self):
        """设置监控区域"""
        def on_region_selected(x1, y1, x2, y2):
            if None in (x1, y1, x2, y2):
                self.status_label.configure(text="已取消选择区域")
                return
            
            try:
                # 设置监控区域
                self.processor.monitor_region = (x1, y1, x2-x1, y2-y1)
                
                # 确保有当前配置并保存
                if self.current_spec:
                    # 保存到当前配置文件
                    if self.processor.save_config(spec_name=self.current_spec):
                        # 更新UI显示
                        self.update_region_info()
                        self.status_label.configure(text=f"已保存监控区域到配置: {self.current_spec}")
                    else:
                        self.status_label.configure(text="保存监控区域失败")
                else:
                    self.status_label.configure(text="请先创建或选择一个配置")
                    
            except Exception as e:
                self.status_label.configure(text=f"设置区域时出错: {str(e)}")
                print(f"设置区域时出错: {str(e)}")  # 添加日志输出
        
        # 停止当前监控
        was_running = self.running
        if was_running:
            self.toggle_monitoring()
        
        # 启动区域选择器
        selector = RegionSelector(callback=on_region_selected)
        selector.start()
        
    def preview_monitor_region(self):
        """预览当前监控区域"""
        if not self.processor.monitor_region:
            self.status_label.configure(text="请先设置监控区域")
            return
            
        x, y, w, h = self.processor.monitor_region
        
        # 创建预览窗口
        preview = tk.Toplevel(self.root)
        preview.title("监控区域预览")
        preview.attributes('-topmost', True)
        
        try:
            # 截取当前区域图像
            screenshot = pyautogui.screenshot(region=(x, y, w, h))
            # 放大显示
            screenshot = screenshot.resize((w*2, h*2), Image.LANCZOS)
            photo = ImageTk.PhotoImage(screenshot)
            
            # 显示图像
            label = tk.Label(preview, image=photo)
            label.image = photo  # 保持引用
            label.pack()
            
            # 添加坐标信息
            info_label = tk.Label(
                preview, 
                text=f"区域: ({x}, {y}) - {w}x{h}",
                font=("Arial", 10)
            )
            info_label.pack(pady=2)
            
            # 添加刷新按钮
            def refresh():
                try:
                    new_shot = pyautogui.screenshot(region=(x, y, w, h))
                    new_shot = new_shot.resize((w*2, h*2), Image.LANCZOS)
                    new_photo = ImageTk.PhotoImage(new_shot)
                    label.configure(image=new_photo)
                    label.image = new_photo
                except Exception as e:
                    print(f"刷新预览时出错: {str(e)}")
            
            refresh_btn = tk.Button(
                preview, 
                text="刷新预览", 
                command=refresh
            )
            refresh_btn.pack(pady=5)
            
            # 添加关闭按钮
            close_btn = tk.Button(
                preview, 
                text="关闭", 
                command=preview.destroy
            )
            close_btn.pack(pady=2)
            
        except Exception as e:
            preview.destroy()
            self.status_label.configure(text=f"预览失败: {str(e)}")
            print(f"预览区域时出错: {str(e)}")
        
    def update_region_info(self):
        """更新区域信息显示"""
        # 由于已移除region_info_label，此方法现在只更新状态栏
        if self.processor.monitor_region:
            x, y, w, h = self.processor.monitor_region
            # 可以选择在状态栏显示区域信息，或者什么都不做
            pass
        else:
            # 可以选择在状态栏显示未设置信息，或者什么都不做
            pass
        
    def update_binding_list(self):
        """优化后的绑定列表更新函数"""
        current_time = time.time()
        
        # 如果距离上次更新时间太短，设置待更新标志并返回
        if current_time - self.last_ui_update < self.ui_update_interval:
            if not self.pending_update:
                self.pending_update = True
                # 安排延迟更新
                self.root.after(int(self.ui_update_interval * 1000), self.delayed_update)
            return
        
        try:
            # 使用after_cancel取消所有待处理的更新
            if hasattr(self, '_pending_update_id'):
                self.root.after_cancel(self._pending_update_id)
            
            # 清除现有绑定列表的所有子组件
            for widget in self.bindings_frame.winfo_children():
                try:
                    widget.destroy()
                except Exception as e:
                    print(f"销毁控件时出错: {str(e)}")
                    continue
            
            # 创建三个框架
            frames = [
                ctk.CTkFrame(self.bindings_frame)
                for _ in range(3)
            ]
            
            for frame in frames:
                frame.pack(side="left", fill="both", expand=True, padx=2, pady=5)
            
            # 获取所有绑定并按text属性排序
            bindings = sorted(
                self.processor.icon_bindings.values(),
                key=lambda b: b.text
            )
            
            if not bindings:
                # 在每个框架中显示空状态
                for frame in frames:
                    self._create_binding_list(frame, [])
                return
            
            # 计算每组的大小
            chunk_size = max(1, (len(bindings) + 2) // 3)
            
            # 分组并填充
            for frame, start_idx in zip(frames, range(0, len(bindings), chunk_size)):
                chunk = bindings[start_idx:start_idx + chunk_size]
                self._create_binding_list(frame, chunk)
            
            self.last_ui_update = current_time
            self.pending_update = False
            
        except Exception as e:
            print(f"更新绑定列表时出错: {str(e)}")
            # 如果出错，设置一个延迟重试
            self._pending_update_id = self.root.after(1000, self.update_binding_list)
        
    def delayed_update(self):
        """延迟更新函数"""
        try:
            self.pending_update = False
            self.update_binding_list()
        except Exception as e:
            print(f"延迟更新时出错: {str(e)}")
        
    def _create_binding_list(self, parent_frame, bindings):
        """优化后的单个绑定列表创建函数"""
        # 创建标题行
        header_frame = ctk.CTkFrame(parent_frame)
        header_frame.pack(fill="x", padx=2, pady=2)
        
        # 使用字典存储标题配置
        headers = [
            {"text": "图标", "width": 32},
            {"text": "名称", "width": 55},
            {"text": "键", "width": 25},
            {"text": "统计", "width": 30}
        ]
        
        # 一次性创建所有标题标签
        for header in headers:
            ctk.CTkLabel(
                header_frame,
                text=header["text"],
                width=header["width"]
            ).pack(side="left", padx=2)
        
        # 预先创建和配置图标容器的样式
        icon_container_style = {
            "width": 32,
            "height": 32,
            "bg_color": "#2B2B2B" if ctk.get_appearance_mode() == "Dark" else "#DBDBDB"
        }
        
        # 批量创建绑定项
        for binding in bindings:
            binding_frame = ctk.CTkFrame(parent_frame, cursor="hand2")
            binding_frame.pack(fill="x", padx=2, pady=1)
            
            # 转换图标模板为预览图像
            icon_img = cv2.cvtColor(binding.template, cv2.COLOR_BGR2RGB)
            icon_img = Image.fromarray(icon_img)
            icon_img = icon_img.resize((24, 24), Image.Resampling.LANCZOS)
            icon_photo = ImageTk.PhotoImage(icon_img)
            
            # 保存引用
            binding_frame.icon_photo = icon_photo
            
            # 创建图标容器
            icon_container = ctk.CTkFrame(binding_frame, **icon_container_style)
            icon_container.pack(side="left", padx=2)
            icon_container.pack_propagate(False)
            
            # 显示图标
            icon_label = tk.Label(
                icon_container,
                image=icon_photo,
                bg=icon_container_style["bg_color"],
                cursor="hand2"
            )
            icon_label.place(relx=0.5, rely=0.5, anchor="center")
            
            # 一次性创建所有标签，使用text属性替代name
            labels = [
                ctk.CTkLabel(binding_frame, text=binding.text, width=60),  # 这里改用text
                ctk.CTkLabel(binding_frame, text=binding.hotkey, width=30),
                ctk.CTkLabel(binding_frame, text=binding.get_stats_str(), width=40)
            ]
            
            for label in labels:
                label.configure(cursor="hand2")
                label.pack(side="left", padx=2)
            
            # 绑定双击事件
            handler = lambda e, b=binding: self.show_edit_menu(e, b)
            for widget in [binding_frame, icon_label] + labels:
                widget.bind("<Double-Button-1>", handler)
        
    def show_edit_menu(self, event, binding):
        """显示编辑菜单"""
        menu = tk.Menu(self.root, tearoff=0)
        
        # 编辑名称
        def edit_name():
            try:
                dialog = ctk.CTkInputDialog(
                    text="请输入新的技能名称:",
                    title="编辑技能名称"
                )
                new_name = dialog.get_input()
                if new_name and new_name != binding.text:  # 使用text属性
                    old_text = binding.text
                    binding.text = new_name  # 更新text属性
                    if self.processor.save_config(spec_name=self.current_spec):
                        self.update_binding_list()
                        self.status_label.configure(text=f"已更新技能名称: {old_text} -> {new_name}")
                        print(f"成功保存技能名称修改: {old_text} -> {new_name}")
                    else:
                        self.status_label.configure(text="保存配置失败，请检查配置文件权限")
                        print("保存配置失败，技能名称未更新")
            except Exception as e:
                error_msg = f"编辑技能名称时出错: {str(e)}"
                self.status_label.configure(text=error_msg)
                print(error_msg)
        
        # 编辑按键
        def edit_hotkey():
            self.status_label.configure(text="请按下新的快捷键... (支持单键或ALT+数字组合)")
            
            alt_pressed = False
            
            def on_key(key):
                nonlocal alt_pressed
                try:
                    # 检测ALT键
                    if key == kb.Key.alt_l or key == kb.Key.alt_r:
                        alt_pressed = True
                        return True
                    
                    # 处理按键
                    if hasattr(key, 'char'):
                        if key.char and key.char.isdigit() and alt_pressed:
                            # ALT + 数字组合
                            new_hotkey = f"alt+{key.char}"
                        else:
                            # 普通字符键
                            new_hotkey = key.char
                    else:
                        # 功能键
                        new_hotkey = key.name
                    
                    # 如果是有效的按键，则保存
                    if new_hotkey and new_hotkey != binding.hotkey:
                        old_hotkey = binding.hotkey
                        binding.hotkey = new_hotkey
                        if self.processor.save_config(spec_name=self.current_spec):
                            self.update_binding_list()
                            self.status_label.configure(text=f"已更新快捷键: {old_hotkey} -> {new_hotkey}")
                            print(f"成功保存快捷键修改: {old_hotkey} -> {new_hotkey}")
                        else:
                            self.status_label.configure(text="保存配置失败，请检查配置文件权限")
                            print("保存配置失败，快捷键未更新")
                    return False
                
                except Exception as e:
                    error_msg = f"处理按键时出错: {str(e)}"
                    self.status_label.configure(text=error_msg)
                    print(error_msg)
                    return False
            
            def on_key_release(key):
                nonlocal alt_pressed
                if key == kb.Key.alt_l or key == kb.Key.alt_r:
                    alt_pressed = False
                return True
            
            # 在新线程中监听按键
            listener = kb.Listener(on_press=on_key, on_release=on_key_release)
            listener.start()
        
        menu.add_command(label="编辑名称", command=edit_name)
        menu.add_command(label="编辑按键", command=edit_hotkey)
        menu.add_separator()
        menu.add_command(label="删除", command=lambda: self.remove_binding(binding.name))
        
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        
    def remove_binding(self, binding_name):
        """删除绑定并保存配置"""
        if not self.current_spec:
            self.status_label.configure(text="请先选择一个配置")
            return
        
        self.processor.remove_icon_binding(binding_name)
        if self.processor.save_config(spec_name=self.current_spec):  # 添加配置名称
            self.update_binding_list()
            self.status_label.configure(text=f"已删除绑定: {binding_name}")
        else:
            self.status_label.configure(text="删除失败：无法保存配置")
        
    def toggle_monitoring(self):
        if not self.processor.monitor_region:
            self.status_label.configure(text="请先设置监控区域")
            return
            
        if not self.processor.icon_bindings:
            # 如果列表为空，自动触发添加技能功能
            self.status_label.configure(text="技能列表为空，正在等待添加新技能...")
            self.running = True
            self.processor.enabled = True
            self.start_btn.configure(
                text="停止监控 (~)",
                fg_color="#D35B58"  # 亮红色
            )
            self.monitoring_thread = threading.Thread(target=self.monitor_loop)
            self.monitoring_thread.start()
            return
            
        if not self.running:
            self.running = True
            self.processor.enabled = True
            self.start_btn.configure(
                text="停止监控 (~)",
                fg_color="#D35B58"  # 亮红色
            )
            self.status_label.configure(text="正在监控中...")
            self.monitoring_thread = threading.Thread(target=self.monitor_loop)
            self.monitoring_thread.start()
        else:
            self.running = False
            self.processor.enabled = False
            self.start_btn.configure(
                text="开始监控 (~)",
                fg_color="#3B8ED0"  # 恢复为默认的蓝灰色
            )
            self.status_label.configure(text="已停止")
            
    def monitor_loop(self):
        """监控循环"""
        monitor_thread = threading.Thread(target=self._monitor_worker)
        monitor_thread.daemon = True
        monitor_thread.start()
        
    def _monitor_worker(self):
        """监控工作线程"""
        while self.running:
            try:
                # 调用当前类的process_frame方法，而不是processor的方法
                self.process_frame()
                time.sleep(self.processor.settings['scan_interval'])
            except Exception as e:
                def update_ui():
                    self.status_label.configure(text=f"错误: {str(e)}")
                    self.running = False
                    self.start_btn.configure(
                        text="开始监控 (~)",
                        fg_color=None  # 确保错误时也恢复默认颜色
                    )
                
                # 在主线程中更新UI
                self.root.after(0, update_ui)
                break
                
    def quit_app(self):
        """退出应用"""
        try:
            print("正在保存程序状态...")
            # 停止监控
            self.running = False
            self.processor.enabled = False
            
            # 确保保存当前状态
            self.save_last_config()
            
            # 停止键盘监听
            if hasattr(self, 'keyboard_listener'):
                self.keyboard_listener.stop()
            
            # 退出程序
            self.root.quit()
            
        except Exception as e:
            print(f"程序退出时出错: {str(e)}")
            # 确保程序能够退出
            self.root.quit()
        
    def run(self):
        """运行程序"""
        # 启动主循环
        self.root.mainloop()

    def start_auto_save(self):
        """启动自动保存"""
        self.auto_save()

    def auto_save(self):
        """定期自动保存状态"""
        try:
            self.save_last_config()
            print("自动保存完成")
        except Exception as e:
            print(f"自动保存时出错: {str(e)}")
        finally:
            # 每1分钟保存一次
            self.root.after(60000, self.auto_save)

    def on_window_configure(self, event):
        """窗口位置或大小改变时的回调"""
        if event.widget == self.root:
            # 使用after来延迟保存，避免频繁保存
            if hasattr(self, '_save_timer'):
                self.root.after_cancel(self._save_timer)
            self._save_timer = self.root.after(1000, self.save_last_config)

    def update_status_display(self, status: str):
        """更新状态显示"""
        def _update():
            # 只更新状态栏
            self.status_label.configure(text=status)
        
        # 在主线程中更新UI
        self.root.after(0, _update)
        
    def show_settings(self):
        """显示设置窗口"""
        settings_window = ctk.CTkToplevel(self.root)
        settings_window.title("设置")
        settings_window.geometry("350x300")
        settings_window.attributes('-topmost', True)
        
        # 设置窗口位置为屏幕中央
        screen_width = settings_window.winfo_screenwidth()
        screen_height = settings_window.winfo_screenheight()
        
        window_width = 350
        window_height = 250
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        settings_window.geometry(f"{window_width}x{window_height}+{x}+{y}")
        settings_window.resizable(False, False)
        
        frame = ctk.CTkFrame(settings_window)
        frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 扫描间隔设置
        scan_frame = ctk.CTkFrame(frame)
        scan_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(scan_frame, text="扫描间隔(秒):").pack(side="left", padx=5)
        scan_var = ctk.StringVar(value=str(self.processor.settings['scan_interval']))
        scan_entry = ctk.CTkEntry(scan_frame, textvariable=scan_var, width=100)
        scan_entry.pack(side="left", padx=5)
        
        # 匹配阈值设置
        threshold_frame = ctk.CTkFrame(frame)
        threshold_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(threshold_frame, text="匹配阈值(0-1):").pack(side="left", padx=5)
        threshold_var = ctk.StringVar(value=str(self.processor.settings['threshold']))
        threshold_entry = ctk.CTkEntry(threshold_frame, textvariable=threshold_var, width=100)
        threshold_entry.pack(side="left", padx=5)
        
        # 按键延迟设置
        delay_frame = ctk.CTkFrame(frame)
        delay_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(delay_frame, text="按键延迟(秒):").pack(side="left", padx=5)
        delay_var = ctk.StringVar(value=str(self.processor.settings['key_press_delay']))
        delay_entry = ctk.CTkEntry(delay_frame, textvariable=delay_var, width=100)
        delay_entry.pack(side="left", padx=5)
        
        # 监控热键设置
        hotkey_frame = ctk.CTkFrame(frame)
        hotkey_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(hotkey_frame, text="监控热键:").pack(side="left", padx=5)
        hotkey_var = ctk.StringVar(value=self.processor.settings['monitor_hotkey'])
        hotkey_entry = ctk.CTkEntry(hotkey_frame, textvariable=hotkey_var, width=100)
        hotkey_entry.pack(side="left", padx=5)
        
        # 自动添加技能的开关
        auto_add_frame = ctk.CTkFrame(frame)
        auto_add_frame.pack(fill="x", padx=5, pady=5)
        
        auto_add_var = ctk.BooleanVar(value=self.processor.settings.get('auto_add_skills', True))
        auto_add_switch = ctk.CTkSwitch(
            auto_add_frame, 
            text="自动添加新技能",
            variable=auto_add_var
        )
        auto_add_switch.pack(side="left", padx=5)
        
        # 保存按钮
        def save_settings():
            try:
                new_settings = {
                    'scan_interval': float(scan_var.get()),
                    'threshold': float(threshold_var.get()),
                    'key_press_delay': float(delay_var.get()),
                    'monitor_hotkey': hotkey_var.get(),
                    'auto_add_skills': auto_add_var.get()
                }
                
                # 验证输入值
                if not (0 < new_settings['scan_interval'] <= 1):
                    raise ValueError("扫描间隔必须在0-1秒之间")
                if not (0 < new_settings['threshold'] <= 1):
                    raise ValueError("匹配阈值必须在0-1之间")
                if not (0 < new_settings['key_press_delay'] <= 1):
                    raise ValueError("按键延迟必须在0-1秒之间")
                if not new_settings['monitor_hotkey']:
                    raise ValueError("监控热键不能为空")
                    
                # 更新设置并保存到当前配置文件
                self.processor.settings.update(new_settings)
                if self.current_spec and self.processor.save_config(spec_name=self.current_spec):
                    settings_window.destroy()
                    self.status_label.configure(text=f"已保存设置到配置: {self.current_spec}")
                else:
                    self.status_label.configure(text="保存设置失败：请先选择一个配置")
                    
            except ValueError as e:
                self.status_label.configure(text=f"设置错误: {str(e)}")
            except Exception as e:
                self.status_label.configure(text=f"保存设置时出错: {str(e)}")
                
        save_btn = ctk.CTkButton(frame, text="保存", command=save_settings)
        save_btn.pack(pady=10)
        
        # 添加说明文本
        help_text = """
参数说明:
- 扫描间隔: 检查技能图标的时间间隔,越小反应越快,但CPU占用更高
- 匹配阈值: 图标匹配的精确度,越大越严格,建议0.8-0.9
- 按键延迟: 模拟按键的持续时间,太短可能识别不到,太长会影响连续施法
- 监控热键: 开始/停止监控的快捷键,默认为 ` (反引号)

快捷键:
- F9: 开启/关闭自动添加技能
- F10: 快速添加技能
- F11: 设置监控区域
- F12: 退出程序
        """
        help_label = ctk.CTkLabel(frame, text=help_text, justify="left")
        help_label.pack(pady=10)

    def add_recent_key(self, binding_text: str, hotkey: str):
        """添加最近按下的按键到记录"""
        print(f"添加按键记录: {binding_text} -> {hotkey}")
        self.recent_keys.append((binding_text, hotkey))  # 使用text属性
        if len(self.recent_keys) > self.max_recent_keys:
            self.recent_keys.pop(0)  # 移除最旧的记录
        print(f"当前按键记录: {self.recent_keys}")
        
        # 在主线程中更新标题
        self.root.after(0, self.update_title)
        
    def update_title(self):
        """更新窗口标题，显示最近的按键记录和配置名称"""
        try:
            title_parts = []
            
            # 添加配置名称和自动添加状态
            if self.current_spec:
                auto_add_status = "ON" if self.processor.settings.get('auto_add_skills', True) else "OFF"
                title_parts.append(f"孟子 - {self.get_display_name(self.current_spec)} [{auto_add_status}]")
            else:
                title_parts.append("孟子 - 未选择配置")
            
            # 添加按键记录
            if self.recent_keys:
                recent_three = []
                older_three = []
                
                for text, key in reversed(self.recent_keys[-6:]):
                    if len(recent_three) < 3:
                        recent_three.append(text)
                    else:
                        older_three.append(text)
                
                key_parts = []
                if recent_three:
                    key_parts.append(f"[{'-'.join(recent_three)}]")
                if older_three:
                    key_parts.append('-'.join(older_three))
                
                if key_parts:
                    title_parts.append(":" + "-".join(key_parts))
            
            self.root.title(" ".join(title_parts))
        except Exception as e:
            print(f"更新标题时出错: {str(e)}")
            self.root.title("孟子")
        
    def cast_skill_and_record(self, binding):
        """释放技能并记录"""
        success = self.processor.cast_skill(binding)
        if success:
            self.add_recent_key(binding.text, binding.hotkey)  # 使用text而不是name

    def process_frame(self):
        """处理当前帧,检查Hekili建议区域并释放技能"""
        if not self.processor.monitor_region or not self.running:
            return
            
        try:
            region = self.processor.monitor_region
            bindings = list(self.processor.icon_bindings.values())
            
            # 截取Hekili建议区域
            screenshot = pyautogui.screenshot(region=region)
            region_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            
            # 检查每个已绑定的图标
            found_icon = False
            max_match = 0
            
            # 如果没有绑定的图标，直接当作新图标处理
            if not bindings and self.current_spec:  # 确保有当前配置
                self.handle_new_icon(region_cv)
                return
            
            for binding in bindings:
                match_value, hamming = self.processor.find_icon_in_region_with_value(binding, region_cv)
                if match_value >= self.processor.settings['threshold']:
                    self.cast_skill_and_record(binding)
                    found_icon = True
                    break
                max_match = max(max_match, match_value)
            
            # 调整检测逻辑，添加更多调试信息
            if not found_icon and self.current_spec:  # 确保有当前配置
                print(f"未找到匹配图标，最大匹配值: {max_match}")
                if max_match < 0.77:
                    print("检测到可能的新图标")
                    gray = cv2.cvtColor(region_cv, cv2.COLOR_BGR2GRAY)
                    non_black = np.sum(gray > 30) / gray.size
                    if non_black > 0.1:
                        print(f"非黑色像素比例: {non_black}, 确认为新图标")
                        # 检查是否启用了自动添加
                        if self.processor.settings.get('auto_add_skills', True):
                            self.handle_new_icon(region_cv)
                        else:
                            print("自动添加新技能已禁用")
                    else:
                        print(f"非黑色像素比例过低: {non_black}, 可能是空白区域")
                    
        except Exception as e:
            error_msg = f"错误: {str(e)}"
            print(error_msg)
            self.status_label.configure(text=error_msg)

    def handle_new_icon(self, region_cv):
        """处理发现的新图标"""
        try:
            print("开始处理新图标...")
            # 暂停监控
            was_running = self.running
            self.running = False
            self.processor.enabled = False
            self.start_btn.configure(text="开始监控 (~)")
            
            # 创建预览窗口
            preview = ctk.CTkToplevel(self.root)
            preview.title("发现新技能图标")
            preview.attributes('-topmost', True)
            
            # 计算窗口位置使其居中
            window_width = 300
            window_height = 200
            screen_width = preview.winfo_screenwidth()
            screen_height = preview.winfo_screenheight()
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            preview.geometry(f"{window_width}x{window_height}+{x}+{y}")
            
            # 显示图标预览
            icon_img = cv2.cvtColor(region_cv, cv2.COLOR_BGR2RGB)
            icon_img = Image.fromarray(icon_img)
            icon_img = icon_img.resize((48, 48), Image.LANCZOS)
            photo = ImageTk.PhotoImage(icon_img)
            
            # 使用tk.Label而不是ctk.CTkLabel来显示图像
            label = tk.Label(preview, image=photo)
            label.image = photo  # 保持引用
            label.pack(pady=10)
            
            # 生成默认名称
            skill_count = len(self.processor.icon_bindings) + 1
            while f"S-{skill_count}" in self.processor.icon_bindings:
                skill_count += 1
            default_name = f"S-{skill_count}"
            
            # 提示文本
            ctk.CTkLabel(preview, text="发现新技能图标，请按下要绑定的按键").pack(pady=5)
            
            def on_key(key):
                try:
                    if hasattr(key, 'char'):
                        hotkey = key.char
                    else:
                        hotkey = key.name
                        
                    print(f"用户按下按键: {hotkey}")
                    
                    # 确保有当前配置
                    if not self.current_spec:
                        print("错误：没有选择配置文件")
                        self.status_label.configure(text="请先创建或选择一个配置")
                        preview.destroy()
                        return False
                    
                    # 添加新的图标绑定，传入默认名称作为text
                    template = region_cv.copy()
                    binding = self.processor.add_icon_binding(
                        name=default_name,
                        text=default_name,  # 使用相同的默认名称作为显示名称
                        hotkey=hotkey,
                        template_image=template
                    )
                    
                    # 保存到当前配置文件
                    if self.processor.save_config(spec_name=self.current_spec):
                        self.update_binding_list()
                        self.status_label.configure(text=f"已添加新绑定到 {self.current_spec}: {default_name} -> {hotkey}")
                        print(f"成功保存新绑定到配置: {self.current_spec}")
                    else:
                        self.status_label.configure(text="保存配置失败")
                        print("保存配置失败")
                    
                    # 关闭预览窗口
                    preview.destroy()
                    
                    # 如果之前在运行，则恢复监控
                    if was_running:
                        self.toggle_monitoring()
                    
                    return False
                except Exception as e:
                    print(f"处理按键时出错: {str(e)}")
                    self.status_label.configure(text=f"添加绑定时出错: {str(e)}")
                    preview.destroy()
                    return False
            
            # 在新线程中监听按键
            key_thread = threading.Thread(target=lambda: kb.Listener(on_press=on_key).start())
            key_thread.daemon = True
            key_thread.start()
            
        except Exception as e:
            print(f"处理新图标时出错: {str(e)}")
            self.status_label.configure(text=f"处理新图标时出错: {str(e)}")

    def load_specs(self):
        """加载所有已保存的职业专精配置"""
        specs = []
        try:
            config_dir = "configs"
            if os.path.exists(config_dir):
                for file in os.listdir(config_dir):
                    if file.endswith(".json"):
                        spec_name = file[:-5]  # 移除.json后缀
                        specs.append(spec_name)
        except Exception as e:
            print(f"加载职业配置时出错: {str(e)}")
        return specs
        
    def create_new_spec(self):
        """创建新的职业专精配置"""
        dialog = ctk.CTkInputDialog(
            text="请输入新职业专精名称:",
            title="新建职业专精"
        )
        new_spec = dialog.get_input()
        
        if new_spec and new_spec not in self.specs:
            # 保存当前配置
            if self.current_spec:
                self.processor.save_config(spec_name=self.current_spec)
            
            # 创建新的配置文件
            self.current_spec = new_spec
            self.specs.append(new_spec)
            self.processor.clear_bindings()  # 清除现有绑定
            self.processor.save_config(spec_name=new_spec)
            
            # 更新下拉框
            self.spec_dropdown.configure(values=self.specs)
            self.spec_var.set(new_spec)
            
            # 更新UI
            self.update_binding_list()
            self.status_label.configure(text=f"已创建新职业专精: {new_spec}")
            self.root.title(f"孟子 - {self.get_display_name(new_spec)}")

    def change_spec(self, spec_name):
        """切换职业专精"""
        print(f"change_spec 被调用: {spec_name}")
        if spec_name == self.current_spec or spec_name == "请创建配置":
            print(f"配置未改变或无效配置名: current={self.current_spec}, new={spec_name}")
            return
        
        try:
            # 清理现有预览图像
            self.clear_preview_images()
            
            # 保存当前配置
            if self.current_spec:
                print(f"保存当前配置: {self.current_spec}")
                self.processor.save_config(spec_name=self.current_spec)
                self.save_last_config()  # 保存历史记录
            
            # 加载新配置
            print(f"准备加载新配置: {spec_name}")
            self.current_spec = spec_name
            if self.processor.load_config(spec_name=spec_name):
                # 更新UI
                self.update_binding_list()
                self.update_region_info()
                self.status_label.configure(text=f"已切换到: {self.get_display_name(spec_name)}")
                # 更新窗口标题
                self.root.title(f"孟子 - {self.get_display_name(spec_name)}")
                # 立即保存最后使用的配置
                print(f"保存最新配置到历史记录: {spec_name}")
                self.save_last_config()
                print(f"配置切换完成: {spec_name}")
            else:
                print(f"加载配置失败: {spec_name}")
                self.status_label.configure(text=f"加载配置失败: {self.get_display_name(spec_name)}")
                self.root.title("孟子 - 配置加载失败")
        except Exception as e:
            print(f"切换配置时出错: {str(e)}")
            self.status_label.configure(text=f"切换配置时出错: {str(e)}")
            self.root.title("孟子 - 错误")

    def delete_spec(self):
        """删除当前职业专精配置"""
        if not self.current_spec:  # 删除默认配置的检查改为检查是否有选中的配置
            self.status_label.configure(text="请先选择要删除的配置")
            return
        
        # 创建确认对话框
        confirm = tk.messagebox.askyesno(
            "确认删除",
            f"确定要删除 {self.get_display_name(self.current_spec)} 的配置吗？\n此操作不可恢复！",
            icon='warning'
        )
        
        if confirm:
            try:
                # 停止监控
                was_running = self.running
                if was_running:
                    self.toggle_monitoring()
                
                # 清理现有预览图像
                self.clear_preview_images()
                
                spec_to_delete = self.current_spec
                
                # 删除配置
                if self.processor.delete_config(spec_to_delete):
                    # 从列表中移除
                    self.specs.remove(spec_to_delete)
                    
                    # 更新下拉框和配置
                    if self.specs:
                        # 切换到其他配置
                        new_spec = self.specs[0]
                        self.current_spec = new_spec
                        self.spec_dropdown.configure(values=self.specs)
                        self.spec_var.set(new_spec)  # 确保更新下拉框的值
                        
                        # 加载新配置
                        self.processor.load_config(spec_name=new_spec)
                        self.update_binding_list()
                        self.update_region_info()
                        # 保存新的历史记录
                        self.save_last_config()
                    else:
                        # 如果没有配置了
                        self.current_spec = ""
                        self.spec_dropdown.configure(values=["请创建配置"])
                        self.spec_var.set("请创建配置")
                        self.processor.clear_bindings()
                        self.update_binding_list()
                        # 删除历史记录文件
                        if os.path.exists(self.history_file):
                            os.remove(self.history_file)
                    
                    self.status_label.configure(text=f"已删除配置: {self.get_display_name(spec_to_delete)}")
                    # 更新窗口标题
                    if self.current_spec:
                        self.root.title(f"孟子 - {self.get_display_name(self.current_spec)}")
                    else:
                        self.root.title("孟子 - 未选择配置")
                else:
                    self.status_label.configure(text="删除配置失败")
                
            except Exception as e:
                self.status_label.configure(text=f"删除配置时出错: {str(e)}")
                print(f"删除配置时出错: {str(e)}")

    def clear_preview_images(self):
        """清理所有预览图像"""
        try:
            # 清除绑定框架中的所有内容
            for widget in self.bindings_frame.winfo_children():
                widget.destroy()
        except Exception as e:
            print(f"清理预览图像时出错: {str(e)}")



    def save_last_config(self):
        """保存最后使用的配置"""
        try:
            # 确保窗口已完全更新
            self.root.update_idletasks()
            
            # 获取窗口位置和大小
            geometry = self.root.geometry()
            print(f"当前窗口状态: {geometry}")
            match = re.match(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)", geometry)
            if not match:
                raise ValueError(f"无法解析窗口位置: {geometry}")
            
            width, height, x, y = map(int, match.groups())
            
            # 确保当前配置是有效的
            if self.current_spec and self.current_spec != "请创建配置":
                # 先保存当前配置文件
                self.processor.save_config(spec_name=self.current_spec)
                
                # 保存历史记录
                history = {
                    "last_spec": self.current_spec,
                    "window": {
                        "x": x,
                        "y": y,
                        "width": width,
                        "height": height
                    },
                    "monitor_region": self.processor.monitor_region,
                    "settings": self.processor.settings,
                    "auto_add_skills": self.processor.settings.get('auto_add_skills', False),
                    "last_update": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                
                # 确保配置目录存在
                os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
                
                # 使用临时文件保存，确保写入完整
                temp_file = self.history_file + '.tmp'
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(history, f, ensure_ascii=False, indent=2)
                
                # 安全替换文件
                if os.path.exists(temp_file):
                    if os.path.exists(self.history_file):
                        os.replace(temp_file, self.history_file)
                    else:
                        os.rename(temp_file, self.history_file)
                    
                print(f"已保存历史配置: {self.get_display_name(self.current_spec)}")
                print(f"窗口状态已保存: {history['window']}")
            
        except Exception as e:
            print(f"保存历史配置时出错: {str(e)}")

    def load_last_config(self):
        """加载最后使用的配置"""
        try:
            if os.path.exists(self.history_file):
                print(f"找到历史配置文件: {self.history_file}")
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    print(f"加载的历史配置内容: {config}")
                    return config
            else:
                print("未找到历史配置文件")
        except Exception as e:
            print(f"加载历史配置时出错: {str(e)}")
        return {}

    def toggle_auto_add(self):
        """切换自动添加技能开关"""
        try:
            current = self.processor.settings.get('auto_add_skills', True)
            self.processor.settings['auto_add_skills'] = not current
            
            # 保存设置
            self.save_last_config()
            
            # 更新状态显示
            status = "已开启自动添加技能" if self.processor.settings['auto_add_skills'] else "已关闭自动添加技能"
            self.status_label.configure(text=status)
            print(status)
            
            # 更新标题栏
            self.update_title()
            
        except Exception as e:
            print(f"切换自动添加技能时出错: {str(e)}")

if __name__ == "__main__":
    app = WoWSkillAssistant()
    app.run() 