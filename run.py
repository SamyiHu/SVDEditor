#!/usr/bin/env python3
"""
SVD工具启动脚本
支持 GUI 模式和 CLI 模式:
  - 无参数或 --gui: 启动 GUI 界面
  - 带子命令 (validate/export/generate/diff/info): 启动 CLI 模式
"""
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# CLI 子命令列表
CLI_COMMANDS = {"validate", "export", "generate", "diff", "info", "merge", "header", "conflicts", "extract"}


def is_cli_mode():
    """判断是否为 CLI 模式"""
    args = sys.argv[1:]
    if not args:
        return False
    # 第一个非 -v/--verbose 参数是子命令
    for arg in args:
        if arg.startswith("-"):
            continue
        if arg in CLI_COMMANDS:
            return True
        break
    return False


if __name__ == "__main__":
    if is_cli_mode():
        from svd_tool.cli import main as cli_main
        cli_main()
    else:
        from svd_tool.main import main
        main()
