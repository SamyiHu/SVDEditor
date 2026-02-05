#!/usr/bin/env python3
"""
SVD工具启动脚本
"""
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from svd_tool.main import main

if __name__ == "__main__":
    main()