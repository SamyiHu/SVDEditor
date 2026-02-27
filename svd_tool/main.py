# svd_tool/main.py
#!/usr/bin/env python3
"""
SVD工具主程序入口
"""
import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from svd_tool.ui.main_window_refactored import MainWindowRefactored as MainWindow
from svd_tool.utils.logger import get_logger

# 获取日志实例
logger = get_logger("main")


def main():
    """主函数"""
    # 创建应用
    app = QApplication(sys.argv)
    app.setApplicationName("SVD工具")
    app.setOrganizationName("SVDTool")
    
    # 创建主窗口
    logger.debug("开始创建主窗口...")
    window = MainWindow()
    logger.debug(f"主窗口创建完成，窗口大小: {window.size()}")
    
    # 延迟显示窗口，确保窗口完全初始化后再显示
    # 这样可以避免先显示小窗口，然后才调整到正确大小的问题
    from PyQt6.QtCore import QTimer
    def show_window():
        logger.debug(f"准备显示窗口，窗口大小: {window.size()}")
        window.show()
        logger.debug(f"窗口已显示，窗口大小: {window.size()}")
    
    QTimer.singleShot(100, show_window)
    
    # 运行应用
    sys.exit(app.exec())


if __name__ == "__main__":
    main()