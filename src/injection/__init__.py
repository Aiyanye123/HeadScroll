"""输入注入模块"""
import platform
from .base import InputInjector

# 根据平台选择实现
if platform.system() == "Windows":
    from .windows import WindowsInjector as PlatformInjector
else:
    # 其他平台暂时使用基类（空实现）
    PlatformInjector = InputInjector

__all__ = ["InputInjector", "PlatformInjector"]
