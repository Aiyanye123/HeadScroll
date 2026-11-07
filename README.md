# HeadScroll：面部滚动控制器

用普通摄像头识别抬头和低头动作，双向滚动网页、文档和代码界面，适合阅读、演示、无障碍辅助等场景。

![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

---

## 功能亮点

- **双向滚动**：抬头 → 向上滚；低头 → 向下滚
- **三点标定**：抬头、自然姿势、低头快速校准
- **头部范围校准**：记录抬头与低头，由两端计算中心和控制范围
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
pip install -r requirements.txt
```

### 2) 运行

```powershell
cd src
python main.py
```

### 3) 使用流程

1. 点击 **启动** 打开摄像头
2. 点击 **标定** 完成抬头、自然姿势、低头三点标定，或在设置中用 **头部范围校准** 记录抬头、低头两端
3. 打开浏览器/文档/IDE
4. 抬头向上滚动，低头向下滚动

---

## 控制方式

| 动作           | 结果                 |
| -------------- | -------------------- |
| 抬头           | 向上滚动             |
| 低头           | 向下滚动             |
| 回到中间区域   | 离开触发区并经过退出停留后停止滚动 |
| 快捷键         | 暂停/恢复 / 紧急停止 |

恢复暂停或更新标定后，系统会从新采集的特征帧重新判断意图，并重新计算触发停留时间。

### 帧与滚动节奏

- 控制循环按 `scroll.tick_hz` 输出滚轮事件；滤波、意图状态机和目标速度只在新的特征帧到达时更新。
- 特征使用采集时间戳去重，并受 `filter.lost_face_timeout_ms` 限制。特征过期后会清除滤波、意图计时和当前速度；恢复滚动需要新帧重新完成停留时间。
- 控制循环错过节拍时会丢弃错过的输出节拍，不会集中补发滚轮事件。

---

## 配置说明

配置分两层：

- **默认配置**：`config/default_config.json`
- **用户配置**：`config/config.json`（优先级更高，推荐改它）

### 常用配置示例

下面数值仅用于说明配置字段；随包默认值以 `config/default_config.json` 为准。

```json
{
  "calibration": {
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

- **head_pitch_min/max**：相对中心的抬头/低头范围（弧度），范围越小越敏感
- **head_pitch_center**：中心偏移（弧度，正值整体向下）
- **th_on/th_off**：中间区域宽度与触发门槛
- **v_max/gamma**：滚动速度与曲线
- **injection.target**：滚轮注入目标（cursor / foreground / process）
- **injection.process_name**：`process` 模式下的目标可执行文件名；只向匹配进程的可见窗口发送。目标不存在或发送失败时，滚动控制会停止并报告错误，不会改发到其他窗口。
- **injection.smooth_scroll**：启用时以 1 个滚轮单位输出；关闭时以 120 个单位（一个标准滚轮刻度）输出。目标应用可能会把亚刻度事件合并或取整，因此细粒度效果取决于目标应用。
- 滚动要求有效且与当前标定算法匹配的头姿。三点和两点校准都会保存算法标记；缺少有效标记或更换头姿算法时需重新标定。
- 旧配置中的眼动、融合及眨眼设置会被忽略；旧眼动参考停用，已有有效头部参考继续使用。首次使用旧版无算法标记的头部数据时需重新标定。

---

## 打包（PyInstaller）

使用 spec：

```powershell
pyinstaller --noconfirm src\EyeScroll.spec
```

> 提示：spec 已避免全量 `collect_all(mediapipe)`，体积更小。

---

## 常见问题

- **不滚动**：确认状态是 `SCROLLING`；检查标定、注入目标和目标进程名称是否正确。暂停恢复、更新标定或特征过期后，需要新帧重新达到停留条件
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
└── src/
    ├── main.py
    ├── capture/
    ├── tracking/
    ├── calibration/
    ├── processing/
    ├── control/
    ├── injection/
    ├── ui/
    └── utils/
```

---

## 许可证

MIT License
