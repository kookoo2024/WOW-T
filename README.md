# WOW技能助手

一个用于World of Warcraft的智能技能释放助手，基于图像识别技术自动识别Hekili插件的技能建议并执行相应的按键操作。

## 主要功能

- 智能技能识别和自动释放
- 多配置管理支持
- 实时状态显示
- 黄色粗体标题栏

## 安装使用

1. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

2. 启动程序：
   ```bash
   python XXD.py
   ```

## 快捷键

- **`** (反引号): 开始/停止监控
- **F9**: 切换自动添加技能开关
- **F10**: 快速添加技能绑定
- **F11**: 设置监控区域
- **F12**: 退出程序

## 项目结构

```
WOW/
├── XXD.py                # 主程序
├── skill_processor.py    # 核心模块
├── requirements.txt      # 依赖列表
├── README.md            # 说明文档
├── configs/             # 配置文件
└── templates/           # 技能图标
```

## 注意事项

本工具仅供学习研究使用，请遵守游戏相关规定。
