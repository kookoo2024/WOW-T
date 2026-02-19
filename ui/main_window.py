import sys
import re
import threading
import time
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path

import customtkinter as ctk
import cv2
import numpy as np
import pyautogui
from PIL import Image, ImageTk
from pynput import keyboard as kb
import tkinter as tk

from core.config import ConfigManager, AppSettings
from core.processor import SkillProcessor, IconBinding
from core.matcher import ImageMatcher
from ui.region_selector import RegionSelector
from ui.settings_dialog import SettingsDialog
from utils.logger import get_logger

logger = get_logger()


class MainWindow:
    def __init__(self):
        self.config_manager = ConfigManager()
        self.processor = SkillProcessor(self.config_manager)
        self.matcher = ImageMatcher()
        
        self.root = ctk.CTk()
        self.root.title("孟子 - 加载中...")
        
        self._setup_encoding()
        self._setup_window_attributes()
        self._setup_theme()
        
        self.running = False
        self.auto_add_enabled = True
        self.adding_new_skill = False
        self._last_key_time = {}
        self._temp_status_until = 0
        self._settings_window = None
        self._settings_dialog = None
        self._window_initialized = False
        
        self._load_last_config()
        self._setup_ui()
        self._setup_hotkeys()
        
        self.root.protocol("WM_DELETE_WINDOW", self._quit_app)
        self.root.bind("<Configure>", self._on_window_configure)
        
        self._start_auto_save()
        
        self.root.after(500, self._mark_window_initialized)
    
    def _setup_encoding(self):
        if sys.platform.startswith('win'):
            if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
                sys.stdout.reconfigure(encoding='utf-8')
            if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
                sys.stderr.reconfigure(encoding='utf-8')
    
    def _setup_window_attributes(self):
        self.root.attributes('-topmost', True)
        if sys.platform.startswith('win'):
            self.root.attributes('-toolwindow', True)
        else:
            self.root.resizable(False, False)
    
    def _setup_theme(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
    
    def _load_last_config(self):
        history = self.config_manager.load_history()
        
        specs = self.config_manager.get_available_specs()
        self.current_spec = history.get("last_spec", "")
        
        if self.current_spec and self.current_spec in specs:
            self.processor.load_config(self.current_spec)
        elif specs:
            self.current_spec = specs[0]
            self.processor.load_config(self.current_spec)
        else:
            self.current_spec = ""
        
        if "settings" in history:
            if self.config_manager.current_config:
                self.config_manager.current_config.settings = AppSettings.from_dict(history["settings"])
        
        if "monitor_region" in history and history["monitor_region"] is not None:
            self.processor.monitor_region = tuple(history["monitor_region"])
        
        self.auto_add_enabled = self.processor.settings.auto_add_skills
        
        window_config = history.get("window", {})
        if window_config:
            self._restore_window_position(window_config)
        else:
            self._set_default_window_position()
    
    def _restore_window_position(self, window_config: dict):
        try:
            width = window_config.get("width", 207)
            height = window_config.get("height", 102)
            x = window_config.get("x", 572)
            y = window_config.get("y", 741)
            
            if all(v is not None for v in (x, y, width, height)):
                screen_width = self.root.winfo_screenwidth()
                screen_height = self.root.winfo_screenheight()
                x = max(0, min(x, screen_width - width))
                y = max(0, min(y, screen_height - height))
                
                self.root.geometry(f"{width}x{height}+{x}+{y}")
                self.root.update_idletasks()
        except Exception as e:
            logger.error(f"恢复窗口位置时出错: {e}")
            self._set_default_window_position()
    
    def _set_default_window_position(self):
        width = 207
        height = 102
        x = 572
        y = 741
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.update_idletasks()
    
    def _setup_ui(self):
        self.main_frame = ctk.CTkFrame(self.root)
        self.main_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self._create_control_buttons()
        self._create_status_bar()
        self._create_bindings_frame()
        
        self._update_binding_list()
        self._update_title()
    
    def _create_control_buttons(self):
        control_frame = ctk.CTkFrame(self.main_frame)
        control_frame.pack(fill="x", padx=5, pady=2)
        
        self.start_btn = ctk.CTkButton(
            control_frame,
            text="开始监控",
            command=self._toggle_monitoring,
            width=120,
            height=28
        )
        self.start_btn.pack(side="left", padx=2)
        
        ctk.CTkButton(
            control_frame,
            text="设置",
            command=self._show_settings,
            width=60,
            height=28
        ).pack(side="left", padx=2)
    
    def _create_bindings_frame(self):
        self.bindings_frame = ctk.CTkFrame(self.main_frame)
        self.bindings_frame.pack(fill="both", expand=True, padx=5, pady=1)
        
        self.bindings_grid = ctk.CTkFrame(self.bindings_frame, fg_color="transparent")
        self.bindings_grid.pack(fill="both", expand=True)
    
    def _create_status_bar(self):
        self.status_frame = ctk.CTkFrame(
            self.main_frame,
            fg_color="#4A5D23"
        )
        self.status_frame.pack(fill="x", side="bottom", padx=5, pady=1)
        
        self.status_label = ctk.CTkLabel(
            self.status_frame,
            text="就绪",
            font=("Arial", 12, "bold"),
            text_color="#FF8C00"
        )
        self.status_label.pack(side="left", padx=5)
    
    def _setup_hotkeys(self):
        self.keyboard_listener = kb.Listener(on_press=self._on_key_press)
        self.keyboard_listener.start()
        self.processor.set_status_callback(self._update_status_display)
    
    def _on_key_press(self, key):
        try:
            import time
            current_time = time.time()
            debounce_interval = 0.3  # 300ms 防抖间隔
            
            key_char = getattr(key, 'char', None)
            key_name = getattr(key, 'name', str(key))
            
            # 防抖检查
            key_id = key_char or key_name
            if key_id in self._last_key_time:
                if current_time - self._last_key_time[key_id] < debounce_interval:
                    return  # 忽略重复按键
            self._last_key_time[key_id] = current_time
            
            logger.debug(f"按键: char={key_char}, name={key_name}")
            
            if key_char and key_char == self.processor.settings.monitor_hotkey:
                logger.info(f"触发监控热键: {key_char}")
                self.root.after(0, self._toggle_monitoring)
            elif key == kb.Key.f9:
                logger.info("触发 F9: 切换自动添加")
                self.root.after(0, self._toggle_auto_add)
            elif key == kb.Key.f11:
                logger.info("触发 F11: 设置监控区域")
                self.root.after(0, self._set_monitor_region)
            elif key == kb.Key.f12:
                logger.info("触发 F12: 退出程序")
                self.root.after(0, self._quit_app)
        except Exception as e:
            logger.error(f"处理快捷键时出错: {e}")
    
    def _get_display_name(self, spec_name: str, max_length: int = 6) -> str:
        if not spec_name:
            return ""
        
        has_chinese = bool(re.search(r'[\u4e00-\u9fff]', spec_name))
        
        if has_chinese:
            if len(spec_name) <= 6:
                return spec_name
            return spec_name[:4] + "..."
        else:
            if len(spec_name) <= max_length:
                return spec_name
            return spec_name[-max_length:]
    
    def _update_title(self):
        if self.current_spec:
            auto_status = "ON" if self.auto_add_enabled else "OFF"
            self.root.title(f"孟子 - {self._get_display_name(self.current_spec)} [{auto_status}]")
        else:
            self.root.title("孟子 - 未选择配置")
    
    def _update_binding_list(self):
        for widget in self.bindings_grid.winfo_children():
            widget.destroy()
        
        if not self.processor.icon_bindings:
            ctk.CTkLabel(
                self.bindings_grid,
                text="暂无技能绑定",
                font=("Arial", 12)
            ).pack(pady=10)
            self._adjust_window_size(0)
            return
        
        bindings = list(self.processor.icon_bindings.values())
        cols = 3
        for idx, binding in enumerate(bindings):
            row = idx // cols
            col = idx % cols
            self._create_binding_item(binding, row, col)
        
        rows = (len(bindings) + cols - 1) // cols
        self._adjust_window_size(rows)
    
    def _adjust_window_size(self, rows: int):
        pass
    
    def _create_binding_item(self, binding: IconBinding, row: int, col: int):
        binding_frame = ctk.CTkFrame(self.bindings_grid)
        binding_frame.grid(row=row, column=col, padx=3, pady=2, sticky="nsew")
        
        self.bindings_grid.grid_columnconfigure(col, weight=1)
        
        try:
            template_rgb = cv2.cvtColor(binding.template, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(template_rgb)
            img = img.resize((28, 28), Image.LANCZOS)
            ctk_image = ctk.CTkImage(light_image=img, dark_image=img, size=(28, 28))
            
            icon_label = ctk.CTkLabel(binding_frame, image=ctk_image, text="")
            icon_label.image = ctk_image
            icon_label.pack(side="left", padx=3)
        except Exception as e:
            logger.error(f"显示图标时出错: {e}")
            icon_label = ctk.CTkLabel(binding_frame, text="[图标]", width=28)
            icon_label.pack(side="left", padx=3)
        
        hotkey_label = ctk.CTkLabel(
            binding_frame,
            text=binding.hotkey,
            font=("Arial", 12, "bold"),
            text_color="#FF8C00"
        )
        hotkey_label.pack(side="left", padx=3, expand=True)
        
        handler = lambda e, b=binding: self._show_edit_menu(e, b)
        for widget in [binding_frame, icon_label, hotkey_label]:
            widget.bind("<Double-Button-1>", handler)
    
    def _show_edit_menu(self, event, binding: IconBinding):
        menu = tk.Menu(self.root, tearoff=0)
        
        def edit_name():
            try:
                dialog = ctk.CTkInputDialog(
                    text="请输入新的技能名称:",
                    title="编辑技能名称"
                )
                new_name = dialog.get_input()
                if new_name and new_name != binding.text:
                    binding.text = new_name
                    if self.processor.save_config():
                        self._update_binding_list()
                        self.status_label.configure(text=f"已更新技能名称: {new_name}")
            except Exception as e:
                logger.error(f"编辑技能名称时出错: {e}")
        
        def edit_hotkey():
            self.status_label.configure(text="请按下新的快捷键...")
            
            alt_pressed = False
            
            def on_key(key):
                nonlocal alt_pressed
                try:
                    if key == kb.Key.alt_l or key == kb.Key.alt_r:
                        alt_pressed = True
                        return True
                    
                    if hasattr(key, 'char'):
                        if key.char and key.char.isdigit() and alt_pressed:
                            new_hotkey = f"alt+{key.char}"
                        else:
                            new_hotkey = key.char
                    else:
                        new_hotkey = key.name
                    
                    if new_hotkey and new_hotkey != binding.hotkey:
                        binding.hotkey = new_hotkey
                        if self.processor.save_config():
                            self._update_binding_list()
                            self.status_label.configure(text=f"已更新快捷键: {new_hotkey}")
                    return False
                except Exception as e:
                    logger.error(f"处理按键时出错: {e}")
                    return False
            
            def on_key_release(key):
                nonlocal alt_pressed
                if key == kb.Key.alt_l or key == kb.Key.alt_r:
                    alt_pressed = False
                return True
            
            listener = kb.Listener(on_press=on_key, on_release=on_key_release)
            listener.start()
        
        menu.add_command(label="编辑名称", command=edit_name)
        menu.add_command(label="编辑按键", command=edit_hotkey)
        menu.add_separator()
        menu.add_command(label="删除", command=lambda: self._remove_binding(binding.name))
        
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
    
    def _remove_binding(self, binding_name: str):
        if not self.current_spec:
            self.status_label.configure(text="请先选择一个配置")
            return
        
        self.processor.remove_icon_binding(binding_name)
        if self.processor.save_config():
            self._update_binding_list()
            self.status_label.configure(text=f"已删除绑定: {binding_name}")
    
    def _toggle_monitoring(self):
        if not self.processor.monitor_region:
            self.status_label.configure(text="请先设置监控区域")
            return
        
        if not self.processor.icon_bindings:
            self.status_label.configure(text="技能列表为空，正在等待添加新技能...")
            self.running = True
            self.processor.start()
            self.start_btn.configure(text="停止监控 (~)", fg_color="#D35B58")
            self._start_monitoring_thread()
            return
        
        if not self.running:
            self.running = True
            self.processor.start()
            self.start_btn.configure(text="停止监控 (~)", fg_color="#D35B58")
            self.status_label.configure(text="正在监控中...")
            self._start_monitoring_thread()
        else:
            self.running = False
            self.processor.stop()
            self.start_btn.configure(text="开始监控 (~)", fg_color="#3B8ED0")
            self.status_label.configure(text="已停止")
    
    def _start_monitoring_thread(self):
        thread = threading.Thread(target=self._monitor_loop, daemon=True)
        thread.start()
    
    def _monitor_loop(self):
        while self.running:
            try:
                self.processor.process_frame()
                
                if self.auto_add_enabled and self.processor.settings.auto_add_skills:
                    new_skill_img = self.processor.check_for_new_skill()
                    if new_skill_img is not None:
                        self._auto_add_skill(new_skill_img)
                
                time.sleep(self.processor.settings.scan_interval)
            except Exception as e:
                logger.error(f"监控循环出错: {e}")
                self.root.after(0, lambda: self._on_monitoring_error(str(e)))
                break
    
    def _on_monitoring_error(self, error_msg: str):
        self.status_label.configure(text=f"错误: {error_msg}")
        self.running = False
        self.processor.stop()
        self.start_btn.configure(text="开始监控 (~)", fg_color="#3B8ED0")
    
    def _auto_add_skill(self, template: np.ndarray):
        if self.adding_new_skill:
            return
        
        self.adding_new_skill = True
        
        skill_num = len(self.processor.icon_bindings) + 1
        while f"S-{skill_num}" in self.processor.icon_bindings:
            skill_num += 1
        default_name = f"S-{skill_num}"
        default_hotkey = "1"
        
        binding = self.processor.add_icon_binding(default_name, default_hotkey, template, default_name)
        if binding:
            self.processor.save_config()
            self.root.after(0, self._update_binding_list)
            self.status_label.configure(text=f"已添加技能: {binding.text} -> {default_hotkey}")
            logger.info(f"已添加新技能: {binding.text} -> {default_hotkey}")
        
        self.adding_new_skill = False
    
    def _toggle_auto_add(self):
        import time
        self.auto_add_enabled = not self.auto_add_enabled
        status = "开启" if self.auto_add_enabled else "关闭"
        color = "#00FF00" if self.auto_add_enabled else "#FF6600"
        logger.info(f"自动添加技能: {status}")
        
        if self.config_manager.current_config:
            self.config_manager.current_config.settings.auto_add_skills = self.auto_add_enabled
            self.config_manager.save_spec(self.config_manager.current_config)
        
        self._temp_status_until = time.time() + 2.0
        self.status_label.configure(text=f"自动添加技能: {status}", text_color=color)
        self._update_title()
    
    def _set_monitor_region(self):
        def callback(x1, y1, x2, y2):
            if all(v is not None for v in (x1, y1, x2, y2)):
                self.processor.set_monitor_region(x1, y1, x2, y2)
                self.processor.save_config()
                self.status_label.configure(text=f"已设置监控区域: ({x1},{y1},{x2-x1},{y2-y1})")
        
        selector = RegionSelector(callback)
        selector.start()
    
    def _preview_monitor_region(self):
        if not self.processor.monitor_region:
            self.status_label.configure(text="未设置监控区域")
            return
        
        x, y, w, h = self.processor.monitor_region
        self._show_preview_window(x, y, w, h)
    
    def _show_preview_window(self, x: int, y: int, w: int, h: int):
        preview = ctk.CTkToplevel(self.root)
        preview.title("区域预览")
        preview.attributes('-topmost', True)
        
        try:
            screenshot = pyautogui.screenshot(region=(x, y, w, h))
            img = screenshot.resize((w * 2, h * 2), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            
            label = ctk.CTkLabel(preview, image=photo, text="")
            label.image = photo
            label.pack(padx=10, pady=10)
            
            preview.geometry(f"{w * 2 + 20}x{h * 2 + 20}")
        except Exception as e:
            logger.error(f"预览区域时出错: {e}")
            preview.destroy()
    
    def _show_settings(self):
        if self._settings_window is not None:
            try:
                self._settings_window.focus()
                return
            except:
                self._settings_window = None
        
        def on_save(settings: dict, region: Optional[Tuple[int, int, int, int]]):
            if self.config_manager.current_config:
                new_settings = AppSettings.from_dict(settings)
                self.config_manager.current_config.settings = new_settings
                self.auto_add_enabled = new_settings.auto_add_skills
                if region:
                    self.processor.monitor_region = region
                    self.config_manager.current_config.monitor_region = list(region)
                self.config_manager.save_spec(self.config_manager.current_config)
                self.status_label.configure(text=f"已保存设置到配置: {self.current_spec}")
                logger.info(f"设置已更新: {settings}, 自动添加: {self.auto_add_enabled}")
        
        def on_preview_region(x: int, y: int, w: int, h: int):
            self._show_preview_window(x, y, w, h)
        
        def on_spec_change(spec_name: str):
            self._on_spec_change(spec_name)
        
        def on_create_spec():
            self._create_new_spec()
        
        def on_delete_spec(spec_name):
            self._delete_spec(spec_name)
        
        def on_set_region():
            self._set_monitor_region()
        
        def on_close():
            self._settings_window = None
        
        dialog = SettingsDialog(
            self.root,
            self.processor.settings,
            self.processor.monitor_region,
            self.current_spec,
            self.config_manager.get_available_specs(),
            on_save,
            on_preview_region,
            on_spec_change,
            on_create_spec,
            on_delete_spec,
            on_set_region
        )
        dialog.show()
        self._settings_window = dialog.window
        self._settings_dialog = dialog
        if self._settings_window:
            self._settings_window.protocol("WM_DELETE_WINDOW", lambda: (setattr(self, '_settings_window', None), setattr(self, '_settings_dialog', None), dialog.window.destroy()))
    
    def _on_spec_change(self, new_spec: str):
        if new_spec == self.current_spec:
            return
        
        self.running = False
        self.processor.stop()
        
        if self.processor.load_config(new_spec):
            self.current_spec = new_spec
            self._update_binding_list()
            self._update_title()
            self.start_btn.configure(text="开始监控 (~)", fg_color="#3B8ED0")
    
    def _create_new_spec(self):
        dialog = ctk.CTkInputDialog(
            text="请输入新配置名称:",
            title="新建配置"
        )
        spec_name = dialog.get_input()
        
        if spec_name:
            if self.config_manager.spec_exists(spec_name):
                self.status_label.configure(text=f"配置 '{spec_name}' 已存在")
                return
            
            from core.config import SpecConfig
            new_config = SpecConfig(
                spec_name=spec_name,
                monitor_region=self.processor.monitor_region
            )
            self.config_manager.save_spec(new_config)
            
            self.current_spec = spec_name
            self.processor.load_config(spec_name)
            self._update_binding_list()
            self._update_title()
            self.status_label.configure(text=f"已创建配置: {spec_name}")
    
    def _delete_spec(self, spec_name: str = None):
        target_spec = spec_name or self.current_spec
        if not target_spec:
            self.status_label.configure(text="请先选择一个配置")
            return
        
        if self.config_manager.delete_spec(target_spec):
            specs = self.config_manager.get_available_specs()
            
            if target_spec == self.current_spec:
                self.current_spec = specs[0] if specs else ""
                
                if self.current_spec:
                    self.processor.load_config(self.current_spec)
            
            self._update_spec_dropdown()
            self._update_binding_list()
            self._update_title()
            self._update_settings_dropdown()
            self.status_label.configure(text=f"已删除配置: {target_spec}")
    
    def _update_spec_dropdown(self):
        specs = self.config_manager.get_available_specs()
        self.spec_dropdown.configure(values=specs or ["请创建配置"])
        self.spec_var.set(self.current_spec if self.current_spec else "请创建配置")
    
    def _update_settings_dropdown(self):
        if self._settings_dialog and self._settings_window and self._settings_window.winfo_exists():
            specs = self.config_manager.get_available_specs()
            self._settings_dialog.update_specs(specs, self.current_spec)
    
    def _update_status_display(self, status: str):
        import time
        if time.time() < self._temp_status_until:
            return
        self.root.after(0, lambda: self.status_label.configure(text=status))
    
    def _on_window_configure(self, event):
        if event.widget == self.root and self._window_initialized:
            if hasattr(self, '_save_timer'):
                self.root.after_cancel(self._save_timer)
            self._save_timer = self.root.after(1000, self._save_last_config)
    
    def _mark_window_initialized(self):
        self._window_initialized = True
    
    def _save_last_config(self):
        history = {
            "last_spec": self.current_spec,
            "settings": self.processor.settings.to_dict(),
            "monitor_region": list(self.processor.monitor_region) if self.processor.monitor_region else None,
            "window": {
                "width": self.root.winfo_width(),
                "height": self.root.winfo_height(),
                "x": self.root.winfo_x(),
                "y": self.root.winfo_y()
            }
        }
        self.config_manager.save_history(history)
    
    def _start_auto_save(self):
        self._auto_save()
    
    def _auto_save(self):
        try:
            self._save_last_config()
        except Exception as e:
            logger.error(f"自动保存时出错: {e}")
        finally:
            self.root.after(60000, self._auto_save)
    
    def _quit_app(self):
        try:
            self.running = False
            self.processor.stop()
            self._save_last_config()
            
            if hasattr(self, 'keyboard_listener'):
                self.keyboard_listener.stop()
            
            self.root.quit()
        except Exception as e:
            logger.error(f"程序退出时出错: {e}")
            self.root.quit()
    
    def run(self):
        self.root.mainloop()
