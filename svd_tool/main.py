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


def main():
    """主函数"""
    # 创建应用
    app = QApplication(sys.argv)
    app.setApplicationName("SVD工具")
    app.setOrganizationName("SVDTool")
    
    # 创建主窗口
    window = MainWindow()
    window.show()
    
    # 运行应用
    sys.exit(app.exec())


if __name__ == "__main__":
    main()