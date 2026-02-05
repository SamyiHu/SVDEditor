# svd_tool/core/command_history.py
from typing import Any, List, Callable, Optional
from dataclasses import dataclass


@dataclass
class Command:
    """命令对象"""
    execute: Callable[[], Any]  # 执行函数
    undo: Callable[[], Any]     # 撤消函数
    description: str = ""       # 命令描述


class CommandHistory:
    """命令历史管理器（支持撤消/重做）"""
    
    def __init__(self, max_history: int = 100):
        self.max_history = max_history
        self.history: List[Command] = []
        self.redo_stack: List[Command] = []
        self.current_index = -1
    
    def execute(self, command: Command) -> Any:
        """执行命令"""
        try:
            result = command.execute()
            self.history.append(command)
            
            # 限制历史记录大小
            if len(self.history) > self.max_history:
                self.history.pop(0)
            
            # 清空重做栈
            self.redo_stack.clear()
            self.current_index = len(self.history) - 1
            
            return result
        except Exception as e:
            print(f"执行命令失败: {e}")
            raise
    
    def undo(self) -> bool:
        """撤消上一个命令"""
        if not self.history or self.current_index < 0:
            return False
        
        try:
            command = self.history[self.current_index]
            command.undo()
            
            # 移动到前一个命令
            self.redo_stack.append(command)
            self.current_index -= 1
            
            return True
        except Exception as e:
            print(f"撤消命令失败: {e}")
            return False
    
    def redo(self) -> bool:
        """重做上一个撤消的命令"""
        if not self.redo_stack:
            return False
        
        try:
            command = self.redo_stack.pop()
            command.execute()
            
            # 添加回历史
            self.history.append(command)
            self.current_index = len(self.history) - 1
            
            return True
        except Exception as e:
            print(f"重做命令失败: {e}")
            return False
    
    def can_undo(self) -> bool:
        """检查是否可以撤消"""
        return self.current_index >= 0
    
    def can_redo(self) -> bool:
        """检查是否可以重做"""
        return len(self.redo_stack) > 0
    
    def clear(self):
        """清空历史"""
        self.history.clear()
        self.redo_stack.clear()
        self.current_index = -1
    
    def get_history_info(self) -> List[str]:
        """获取历史信息"""
        return [cmd.description for cmd in self.history]