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

抬头向上滚动，低头向下滚动，回到自然姿势停止。首次使用可完成“抬头—自然—低头”三点标定，也可先启动头部模式，再在设置中记录抬头、低头两个端点，以两者中间值作为自然位置。取消设置时不会应用新记录的两点范围。

控制仅使用头部姿态，不计算眼动或使用眨眼切换暂停。无效姿态、过期画面、暂停、停止和注入失败会清除滚动速度与触发计时；恢复后重新等待有效动作。标定参考绑定当前头姿算法，升级前未记录算法的参考需要重新标定。

设置中可选择鼠标所在窗口、前台窗口或指定进程作为滚轮目标，并通过进程列表选择程序。指定进程不存在或消息发送超时会停止控制并显示错误。默认启用亚刻度平滑滚动；兼容整格滚动的程序可在设置中关闭此项。语音翻页按键发送给当前前台窗口。

## 运行

要求 Windows 10/11 和 Python 3.10–3.12：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python src\main.py
```

将目标阅读程序置于前台。默认 `Esc` 紧急停止，`Ctrl+Shift+Space` 暂停或恢复。模式、语音指令、翻页按键、滚动速度和快捷键可在设置中修改。

## 测试与打包

```powershell
python -m unittest discover -s tests -v
python -m compileall -q src tests
python -m pip install -r requirements-dev.txt
pyinstaller --noconfirm src\EyeScroll.spec
```

产物位于 `dist/HeadScroll/`。人脸与中文语音模型均随应用打包，运行时不需要联网。

打包仅包含默认配置，个人配置保存在用户目录。构建规则排除从其他程序 PATH 中误收集的 ICU DLL，避免 Poppler 等工具的 ICU 版本影响启动。人工检查步骤见 [tests/README.md](tests/README.md)。

## 主要结构

```text
src/tracking/speech_recognizer.py  语音识别与指令解析
src/tracking/face_tracker.py       人脸关键点
src/control/intent_fsm.py          头部滚动状态机
src/calibration/                   头部三点标定
src/injection/windows.py           Windows 滚轮和按键注入
src/ui/                            双模式面板、托盘与设置
tests/                             无硬件核心逻辑测试
```

