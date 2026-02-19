from typing import Callable, Optional, Tuple, List
import customtkinter as ctk

from core.config import AppSettings
from utils.logger import get_logger

logger = get_logger()


class SettingsDialog:
    def __init__(
        self,
        parent,
        settings: AppSettings,
        monitor_region: Optional[Tuple[int, int, int, int]],
        current_spec: str,
        available_specs: List[str],
        on_save: Callable[[dict, Optional[Tuple[int, int, int, int]]], None],
        on_preview_region: Callable[[int, int, int, int], None],
        on_spec_change: Callable[[str], None],
        on_create_spec: Callable[[], None],
        on_delete_spec: Callable[[], None],
        on_set_region: Callable[[], None]
    ):
        self.parent = parent
        self.settings = settings
        self.monitor_region = monitor_region
        self.current_spec = current_spec
        self.available_specs = available_specs
        self.on_save = on_save
        self.on_preview_region = on_preview_region
        self.on_spec_change = on_spec_change
        self.on_create_spec = on_create_spec
        self.on_delete_spec = on_delete_spec
        self.on_set_region = on_set_region
        
        self.window: Optional[ctk.CTkToplevel] = None
        self.spec_dropdown = None
        self.spec_var = None
    
    def update_specs(self, specs: List[str], current_spec: str):
        self.available_specs = specs
        self.current_spec = current_spec
        if self.spec_dropdown and self.spec_var:
            self.spec_dropdown.configure(values=specs or ["请创建配置"])
            if current_spec:
                self.spec_var.set(current_spec)
            elif specs:
                self.spec_var.set(specs[0])
            else:
                self.spec_var.set("请创建配置")
    
    def show(self):
        self.window = ctk.CTkToplevel(self.parent)
        self.window.title("设置")
        self.window.attributes('-topmost', True)
        
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        window_width = 320
        window_height = 320
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        self.window.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.window.resizable(False, False)
        
        self._create_widgets()
    
    def _create_widgets(self):
        main_frame = ctk.CTkFrame(self.window, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=8, pady=6)
        
        self._create_spec_section(main_frame)
        self._create_params_section(main_frame)
        self._create_region_section(main_frame)
        self._create_buttons(main_frame)
    
    def _create_section_header(self, parent, title: str):
        header_frame = ctk.CTkFrame(parent, fg_color="transparent")
        header_frame.pack(fill="x", pady=(4, 2))
        
        ctk.CTkLabel(
            header_frame,
            text=title,
            font=("Arial", 11, "bold"),
            text_color=("#1f6aa5", "#4a9eff")
        ).pack(side="left")
        
        separator = ctk.CTkFrame(header_frame, height=1, fg_color=("#e0e0e0", "#404040"))
        separator.pack(side="left", fill="x", expand=True, padx=(6, 0), pady=5)
    
    def _create_spec_section(self, parent):
        self._create_section_header(parent, "配置管理")
        
        spec_frame = ctk.CTkFrame(parent)
        spec_frame.pack(fill="x", padx=2, pady=2)
        
        inner_frame = ctk.CTkFrame(spec_frame, fg_color="transparent")
        inner_frame.pack(fill="x", padx=6, pady=4)
        
        ctk.CTkLabel(inner_frame, text="当前:", width=40).pack(side="left")
        
        self.spec_var = ctk.StringVar(value=self.current_spec if self.current_spec else "请选择配置")
        self.spec_dropdown = ctk.CTkOptionMenu(
            inner_frame,
            variable=self.spec_var,
            values=self.available_specs or ["请创建配置"],
            command=self._on_spec_change,
            width=100
        )
        self.spec_dropdown.pack(side="left", padx=2)
        
        btn_frame = ctk.CTkFrame(inner_frame, fg_color="transparent")
        btn_frame.pack(side="right")
        
        ctk.CTkButton(
            btn_frame,
            text="新建",
            command=self._on_create_spec,
            width=40,
            height=22
        ).pack(side="left", padx=2)
        
        ctk.CTkButton(
            btn_frame,
            text="删除",
            command=self._on_delete_spec,
            width=40,
            height=22,
            fg_color="#c95858",
            hover_color="#a84545"
        ).pack(side="left", padx=2)
    
    def _create_params_section(self, parent):
        self._create_section_header(parent, "监控参数")
        
        params_frame = ctk.CTkFrame(parent)
        params_frame.pack(fill="x", padx=2, pady=2)
        
        inner_frame = ctk.CTkFrame(params_frame, fg_color="transparent")
        inner_frame.pack(fill="x", padx=6, pady=4)
        
        row1 = ctk.CTkFrame(inner_frame, fg_color="transparent")
        row1.pack(fill="x", pady=1)
        
        ctk.CTkLabel(row1, text="扫描:", width=35).pack(side="left")
        self.scan_var = ctk.StringVar(value=str(self.settings.scan_interval))
        scan_entry = ctk.CTkEntry(row1, textvariable=self.scan_var, width=40)
        scan_entry.pack(side="left", padx=2)
        scan_entry.bind("<FocusOut>", lambda e: self._save_realtime())
        scan_entry.bind("<Return>", lambda e: self._save_realtime())
        ctk.CTkLabel(row1, text="秒", text_color="gray", width=10).pack(side="left")
        
        ctk.CTkLabel(row1, text="阈值:", width=30).pack(side="left", padx=(10, 0))
        self.threshold_var = ctk.StringVar(value=str(self.settings.threshold))
        threshold_entry = ctk.CTkEntry(row1, textvariable=self.threshold_var, width=40)
        threshold_entry.pack(side="left", padx=2)
        threshold_entry.bind("<FocusOut>", lambda e: self._save_realtime())
        threshold_entry.bind("<Return>", lambda e: self._save_realtime())
        
        row2 = ctk.CTkFrame(inner_frame, fg_color="transparent")
        row2.pack(fill="x", pady=1)
        
        ctk.CTkLabel(row2, text="延迟:", width=35).pack(side="left")
        self.delay_var = ctk.StringVar(value=str(self.settings.key_press_delay))
        delay_entry = ctk.CTkEntry(row2, textvariable=self.delay_var, width=40)
        delay_entry.pack(side="left", padx=2)
        delay_entry.bind("<FocusOut>", lambda e: self._save_realtime())
        delay_entry.bind("<Return>", lambda e: self._save_realtime())
        ctk.CTkLabel(row2, text="秒", text_color="gray", width=10).pack(side="left")
        
        ctk.CTkLabel(row2, text="热键:", width=30).pack(side="left", padx=(10, 0))
        self.hotkey_var = ctk.StringVar(value=self.settings.monitor_hotkey)
        hotkey_entry = ctk.CTkEntry(row2, textvariable=self.hotkey_var, width=40)
        hotkey_entry.pack(side="left", padx=2)
        hotkey_entry.bind("<FocusOut>", lambda e: self._save_realtime())
        hotkey_entry.bind("<Return>", lambda e: self._save_realtime())
        
        row3 = ctk.CTkFrame(inner_frame, fg_color="transparent")
        row3.pack(fill="x", pady=1)
        
        ctk.CTkLabel(row3, text="新技:", width=35).pack(side="left")
        self.new_skill_var = ctk.StringVar(value=str(self.settings.new_skill_threshold))
        new_skill_entry = ctk.CTkEntry(row3, textvariable=self.new_skill_var, width=40)
        new_skill_entry.pack(side="left", padx=2)
        new_skill_entry.bind("<FocusOut>", lambda e: self._save_realtime())
        new_skill_entry.bind("<Return>", lambda e: self._save_realtime())
        ctk.CTkLabel(row3, text="阈值", text_color="gray", width=10).pack(side="left")
        
        self.auto_add_var = ctk.BooleanVar(value=self.settings.auto_add_skills)
        auto_switch = ctk.CTkSwitch(
            row3,
            text="自动添加",
            variable=self.auto_add_var,
            command=self._save_realtime,
            width=80
        )
        auto_switch.pack(side="left", padx=(10, 0))
    
    def _create_region_section(self, parent):
        self._create_section_header(parent, "监控区域")
        
        region_frame = ctk.CTkFrame(parent)
        region_frame.pack(fill="x", padx=2, pady=2)
        
        inner_frame = ctk.CTkFrame(region_frame, fg_color="transparent")
        inner_frame.pack(fill="x", padx=6, pady=4)
        
        coord_frame = ctk.CTkFrame(inner_frame, fg_color="transparent")
        coord_frame.pack(fill="x", pady=2)
        
        current_region = self.monitor_region or (0, 0, 50, 50)
        x, y, w, h = current_region
        
        for label, var_name, val in [("X:", "x_var", x), ("Y:", "y_var", y), ("W:", "w_var", w), ("H:", "h_var", h)]:
            ctk.CTkLabel(coord_frame, text=label, width=18).pack(side="left")
            var = ctk.StringVar(value=str(val))
            setattr(self, var_name, var)
            entry = ctk.CTkEntry(coord_frame, textvariable=var, width=40)
            entry.pack(side="left", padx=(0, 4))
            entry.bind("<FocusOut>", lambda e: self._apply_coordinates())
            entry.bind("<Return>", lambda e: self._apply_coordinates())
        
        btn_frame = ctk.CTkFrame(inner_frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=2)
        
        ctk.CTkButton(
            btn_frame,
            text="设区",
            command=self._set_region,
            width=45,
            height=24,
            fg_color="#3d8bfd",
            hover_color="#2d7aed"
        ).pack(side="left", padx=2)
        
        ctk.CTkButton(
            btn_frame,
            text="预览",
            command=self._preview_coordinates,
            width=45,
            height=24
        ).pack(side="left", padx=2)
        
        ctk.CTkButton(
            btn_frame,
            text="应用",
            command=self._apply_and_save,
            width=45,
            height=24
        ).pack(side="left", padx=2)
        
        ctk.CTkButton(
            btn_frame,
            text="重置",
            command=self._get_current_coordinates,
            width=45,
            height=24
        ).pack(side="left", padx=2)
        
        ctk.CTkButton(
            btn_frame,
            text="关闭",
            command=self.window.destroy,
            width=45,
            height=24
        ).pack(side="left", padx=2)
        
        hotkey_text = "F9=自动添加  F11=设区"
        ctk.CTkLabel(
            btn_frame,
            text=hotkey_text,
            text_color="gray",
            font=("Arial", 9)
        ).pack(side="right", padx=2)
    
    def _create_buttons(self, parent):
        pass
    
    def _save_realtime(self):
        try:
            new_settings = {
                'scan_interval': float(self.scan_var.get()),
                'threshold': float(self.threshold_var.get()),
                'key_press_delay': float(self.delay_var.get()),
                'monitor_hotkey': self.hotkey_var.get(),
                'auto_add_skills': self.auto_add_var.get(),
                'new_skill_threshold': float(self.new_skill_var.get())
            }
            
            if not (0 < new_settings['scan_interval'] <= 1):
                return
            if not (0 < new_settings['threshold'] <= 1):
                return
            if not (0 < new_settings['key_press_delay'] <= 1):
                return
            if not (0 < new_settings['new_skill_threshold'] < 1):
                return
            if not new_settings['monitor_hotkey']:
                return
            
            self.on_save(new_settings, self.monitor_region)
            logger.info("设置已实时保存")
            
        except ValueError:
            pass
    
    def _on_spec_change(self, spec_name: str):
        if spec_name and spec_name != "请创建配置" and spec_name != "请选择配置":
            self.on_spec_change(spec_name)
            self.current_spec = spec_name
    
    def _on_create_spec(self):
        self.on_create_spec()
    
    def _on_delete_spec(self):
        spec_to_delete = self.spec_var.get()
        if spec_to_delete and spec_to_delete != "请创建配置" and spec_to_delete != "请选择配置":
            self.on_delete_spec(spec_to_delete)
    
    def _set_region(self):
        self.window.destroy()
        self.on_set_region()
    
    def _apply_coordinates(self):
        try:
            new_x = int(self.x_var.get())
            new_y = int(self.y_var.get())
            new_w = int(self.w_var.get())
            new_h = int(self.h_var.get())
            
            if new_w <= 0 or new_h <= 0:
                return
            if new_x < 0 or new_y < 0:
                return
            
            self.monitor_region = (new_x, new_y, new_w, new_h)
            logger.info(f"设置监控区域: {self.monitor_region}")
            
        except ValueError:
            pass
    
    def _apply_and_save(self):
        self._apply_coordinates()
        self._save_realtime()
    
    def _get_current_coordinates(self):
        if self.monitor_region:
            x, y, w, h = self.monitor_region
            self.x_var.set(str(x))
            self.y_var.set(str(y))
            self.w_var.set(str(w))
            self.h_var.set(str(h))
    
    def _preview_coordinates(self):
        try:
            x = int(self.x_var.get())
            y = int(self.y_var.get())
            w = int(self.w_var.get())
            h = int(self.h_var.get())
            
            if w <= 0 or h <= 0:
                raise ValueError("宽度和高度必须大于0")
            
            self.on_preview_region(x, y, w, h)
            
        except ValueError as e:
            logger.error(f"坐标错误: {e}")
