"""
实时预览独立窗口
"""
import logging
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal

from .components.realtime_preview import RealtimePreviewWidget


class PreviewWindow(QMainWindow):
    """实时预览独立窗口"""
    
    # 信号定义
    window_closed = pyqtSignal()
    
    def __init__(self, state_manager, coordinator=None, parent=None):
        """
        初始化预览窗口
        
        Args:
            state_manager: 状态管理器
            coordinator: 协调器
            parent: 父窗口
        """
        super().__init__(parent)
        self.logger = logging.getLogger("PreviewWindow")
        
        # 设置窗口属性
        self.setWindowTitle("SVD实时预览")
        self.setGeometry(200, 200, 800, 600)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建实时预览组件
        self.realtime_preview = RealtimePreviewWidget(
            state_manager=state_manager,
            coordinator=coordinator
        )
        layout.addWidget(self.realtime_preview)
        
        self.logger.info("预览窗口创建完成")
    
    def refresh_preview(self, immediate: bool = False):
        """刷新预览"""
        self.realtime_preview.refresh_preview(immediate=immediate)
    
    def highlight_element(self, selection):
        """高亮显示指定元素"""
        self.realtime_preview.highlight_element(selection)
    
    def jump_to_selection(self):
        """跳转到当前选中的元素"""
        self.realtime_preview.jump_to_selection()
    
    def showEvent(self, event):
        """窗口显示事件"""
        super().showEvent(event)
        # 自动刷新预览
        self.refresh_preview(immediate=True)
        self.logger.info("预览窗口已显示，自动刷新")
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        self.logger.info("预览窗口关闭")
        # 发射窗口关闭信号
        self.window_closed.emit()
        # 调用父类关闭事件
        super().closeEvent(event)
