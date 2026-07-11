# HeadScroll：手势翻页与头部滚动控制器

HeadScroll 使用普通摄像头提供两种免手持控制方式：张开手掌左右挥动进行翻页，或通过抬头、低头连续上下滚动。识别完全在本机完成，不保存视频帧。

## 控制模式

### 手势翻页

| 动作 | 默认结果 |
| --- | --- |
| 张开手掌向左挥动 | 下一页（`Right`） |
| 张开手掌向右挥动 | 上一页（`Left`） |
| 握拳保持 700 ms | 暂停或恢复 |

识别会检查手掌稳定时间、横向位移、速度、垂直漂移、方向一致性和换手情况。翻页后必须收回手掌并等待冷却，避免连续误触发。

设置中可以选择由 MediaPipe Model Maker 导出的自定义 `.task` 手势模型，并填写用于启动挥动轨迹的类别名；留空时使用仓库内置的官方模型。

### 头部滚动

| 动作 | 结果 |
| --- | --- |
| 抬头 | 向上滚动 |
| 低头 | 向下滚动 |
| 回到自然姿势 | 停止滚动 |

首次使用头部模式必须完成“抬头—自然—低头”三点标定。人脸丢失、识别超时、暂停或注入失败都会立即停止滚动。

## 运行

要求 Windows 10/11 和 Python 3.10–3.12：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python src\main.py
```

将目标阅读程序置于前台或把鼠标放在目标窗口中。默认 `Esc` 紧急停止，`Ctrl+Shift+Space` 暂停或恢复。模式、灵敏度、翻页按键、滚动速度和快捷键可在设置中修改。

## 测试

```powershell
python -m unittest discover -s tests -v
python -m compileall -q src tests
```

测试覆盖手势轨迹、冷却、换手、握拳暂停、头部双向滚动、丢脸停止、正反向标定、配置校验和快捷键解析。

## 打包

```powershell
python -m pip install -r requirements-dev.txt
pyinstaller --noconfirm src\EyeScroll.spec
```

产物位于 `dist/HeadScroll/`。人脸与手势模型均随应用打包，正常运行不需要联网下载。

## 主要结构

```text
src/tracking/hand_gesture.py  手势与掌心轨迹
src/tracking/face_tracker.py  人脸关键点
src/control/page_turn_fsm.py  动态手势状态机
src/control/intent_fsm.py     头部滚动状态机
src/calibration/              头部三点标定
src/injection/windows.py      Windows 滚轮和按键注入
src/ui/                       双模式面板、托盘与设置
tests/                        无硬件核心逻辑测试
```
