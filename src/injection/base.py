"""
M8: 输入注入模块 - 抽象基类
跨平台滚轮事件发送的抽象接口
"""

from abc import ABC, abstractmethod


class InputInjector(ABC):
    """跨平台输入注入抽象基类"""
    
    @abstractmethod
    def init(self) -> bool:
        """
        初始化注入器
        
        Returns:
            是否成功初始化
        """
        pass
    
    @abstractmethod
    def scroll(self, delta: int) -> bool:
        """
        发送滚轮事件
        
        Args:
            delta: 滚轮步进，正值向下滚，负值向上滚
            
        Returns:
            是否成功发送
        """
        pass
    
    @abstractmethod
    def shutdown(self) -> None:
        """关闭注入器，释放资源"""
        pass
    
    def __enter__(self):
        self.init()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()
        return False
