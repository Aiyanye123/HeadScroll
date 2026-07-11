# HeadScroll：语音翻页与头部滚动控制器

HeadScroll 提供两种免手持控制方式：通过中文语音指令左右翻页，或使用普通摄像头根据抬头、低头连续上下滚动。识别完全在本机完成，不上传录音或保存视频帧。

## 控制模式

### 语音翻页

| 指令 | 默认结果 |
| --- | --- |
| “左 / 左翻 / 向左 / 上一页 / 往前” | 上一页（`Left`） |
| “右 / 右翻 / 向右 / 下一页 / 往后” | 下一页（`Right`） |
| “暂停 / 停止” | 暂停翻页 |
| “继续 / 开始” | 恢复翻页 |

语音模式使用本地 Vosk 中文模型和限定词表。默认“均衡”档会在指令连续两次稳定识别后提前触发；“快速”档响应更快，“准确”档等待完整语句。设置中还可编辑同义词、启用“翻页”唤醒词、选择麦克风设备、调整冷却时间、交换左右按键或选择其他 Vosk 模型目录。

### 头部滚动

抬头向上滚动，低头向下滚动，回到自然姿势停止。首次使用必须完成“抬头—自然—低头”三点标定；人脸丢失、识别超时、暂停或注入失败会立即停止滚动。

## 运行

要求 Windows 10/11 和 Python 3.10–3.12：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python src\main.py
```

将目标阅读程序置于前台。默认 `Esc` 紧急停止，`Ctrl+Shift+Space` 暂停或恢复。模式、语音指令、翻页按键、滚动速度和快捷键可在设置中修改。

## 打包

```powershell
python -m pip install pyinstaller
pyinstaller --noconfirm src\EyeScroll.spec
```

产物位于 `dist/HeadScroll/`。人脸与中文语音模型均随应用打包，运行时不需要联网。

## 主要结构

```text
src/tracking/speech_recognizer.py  语音识别与指令解析
src/tracking/face_tracker.py       人脸关键点
src/control/intent_fsm.py          头部滚动状态机
src/calibration/                   头部三点标定
src/injection/windows.py           Windows 滚轮和按键注入
src/ui/                            双模式面板、托盘与设置
```
