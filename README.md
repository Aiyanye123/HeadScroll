# HeadScroll：面部滚动控制器

用普通摄像头实现“看就能滚”的滚动控制。支持 **眼动模式** 和 **抬头/低头模式**，可双向滚动网页/文档/代码界面，适合阅读、演示、无障碍辅助等场景。

![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

---

## 功能亮点

- **双模式**：眼动 / 抬头低头（可切换，实际体验更稳定）
- **双向滚动**：看上方/抬头 → 向上滚；看下方/低头 → 向下滚
- **三点标定**：上/中/下快速校准
- **自动中心校准**：抬头一次 + 低头一次自动确定中心
- **滚轮注入目标**：鼠标窗口 / 前台窗口 / 指定进程（如浏览器）
- **快捷键可配置**：暂停/恢复、紧急停止
- **隐私优先**：本地处理，不上传视频

---

## 环境要求

- **系统**：Windows 10/11
- **Python**：3.10 - 3.12
- **摄像头**：普通 USB 或内置摄像头
- **推理**：CPU（无需 GPU）

---

## 快速开始

### 1) 安装依赖

```powershell
cd "Manga Scrolling Eye Recognition"
pip install -r requirements.txt
```

### 2) 运行

```powershell
cd src
python main.py
```

### 3) 使用流程

1. 点击 **启动** 打开摄像头
2. 设置里可以切换head/eye模式
3. 进行自动校准中心
4. 点击 **标定** 完成三点标定
5. 打开浏览器/文档/IDE
6. 看上方/抬头 → 上滑；看下方/低头 → 下滑

---

## 控制方式

| 动作           | 结果                 |
| -------------- | -------------------- |
| 看上方 / 抬头  | 向上滚动             |
| 看下方 / 低头  | 向下滚动             |
| 回到中间区域   | 停止滚动             |
| 长眨眼（可调） | 暂停/恢复            |
| 快捷键         | 暂停/恢复 / 紧急停止 |

---

## 配置说明

配置分两层：

- **默认配置**：`config/default_config.json`
- **用户配置**：`config/config.json`（优先级更高，推荐改它）

### 常用配置示例

```json
{
  "calibration": {
    "mode": "head",
    "head_pitch_min": -0.12,
    "head_pitch_max": 0.12,
    "head_pitch_center": 0.06
  },
  "thresholds": {
    "th_on": 0.45,
    "th_off": 0.35,
    "dwell_on_ms": 120,
    "dwell_off_ms": 80
  },
  "scroll": {
    "v_max": 3.0,
    "gamma": 1.8,
    "a_up": 8.0,
    "a_down": 16.0
  },
  "injection": {
    "target": "process",
    "process_name": "msedge.exe",
    "smooth_scroll": true
  }
}
```

### 参数要点

- **mode**：`eye` / `head`
- **head_pitch_min/max**：抬头/低头范围（弧度），范围越小越敏感
- **head_pitch_center**：中心偏移（弧度，正值整体向下）
- **th_on/th_off**：中间区域宽度与触发门槛
- **v_max/gamma**：滚动速度与曲线
- **injection.target**：滚轮注入目标（cursor / foreground / process）

---

## 打包（PyInstaller）

使用 spec：

```powershell
pyinstaller --noconfirm src\EyeScroll.spec
```

> 提示：spec 已避免全量 `collect_all(mediapipe)`，体积更小。

---

## 常见问题

- **不滚动**：确认状态是 `SCROLLING`；检查注入目标是否正确
- **太敏感/太慢**：调整 `thresholds` / `scroll`
- **抬头到不了顶部**：缩小 `head_pitch_min/max` 或调 `head_pitch_center`
- **滑块速度无变化**：确认已用新版本（速度滑块已绑定 v_max）

---

## 目录结构

```
├── requirements.txt
├── config/
│   ├── default_config.json
│   └── config.json
├── assets/
│   └── models/
│       └── face_landmarker.task
├── src/
│   ├── main.py
│   ├── capture/
│   ├── tracking/
│   ├── calibration/
│   ├── processing/
│   ├── control/
│   ├── injection/
│   ├── ui/
│   └── utils/
└── docs/
```

---

## 许可证

MIT License
