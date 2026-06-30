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
CLI_COMMANDS = {"validate", "export", "generate", "diff", "info", "merge", "header", "conflicts", "extract", "create", "add-peripheral", "remove-peripheral", "update-peripheral", "add-register", "update-register", "remove-register", "add-field", "update-field", "remove-field"}


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
        # ===== 诊断块：确认加载的是哪份代码（排查"修改不保存"）=====
        try:
            import logging
            _diag = logging.getLogger("svd_tool.IRQ_DIAG")
            _diag.info("=" * 60)
            _diag.info(f"[BOOT] Python: {sys.executable}")
            _diag.info(f"[BOOT] sys.path[0:3]: {sys.path[:3]}")
            import svd_tool
            _diag.info(f"[BOOT] svd_tool 加载自: {svd_tool.__file__}")
            import svd_tool.ui.components.state_manager as _sm
            _diag.info(f"[BOOT] state_manager 加载自: {_sm.__file__}")
            _sm_src = open(_sm.__file__, encoding='utf-8').read()
            _diag.info(f"[BOOT] state_manager 含 IRQ_DIAG 日志? {'IRQ_DIAG' in _sm_src}")
            _diag.info(f"[BOOT] state_manager 含 _sync_all_peripheral_interrupts? {'_sync_all_peripheral_interrupts' in _sm_src}")
            import svd_tool.core.svd_generator as _sg
            _sg_src = open(_sg.__file__, encoding='utf-8').read()
            _diag.info(f"[BOOT] svd_generator 加载自: {_sg.__file__}")
            _diag.info(f"[BOOT] svd_generator 含 _rebuild_peripheral_interrupts? {'_rebuild_peripheral_interrupts' in _sg_src}")
            _diag.info(f"[BOOT] svd_generator 含 IRQ_DIAG? {'IRQ_DIAG' in _sg_src}")
            _diag.info("=" * 60)
            # 同时打印到控制台，避免漏看
            print(f"[BOOT-DIAG] state_manager: {_sm.__file__}", flush=True)
            print(f"[BOOT-DIAG] 含 IRQ_DIAG? {'IRQ_DIAG' in _sm_src}", flush=True)
            print(f"[BOOT-DIAG] 含 _rebuild(sm)? {'_sync_all_peripheral_interrupts' in _sm_src}", flush=True)
            print(f"[BOOT-DIAG] svd_generator: {_sg.__file__}", flush=True)
            print(f"[BOOT-DIAG] 含 _rebuild(sg)? {'_rebuild_peripheral_interrupts' in _sg_src}", flush=True)
        except Exception as _e:
            print(f"[BOOT-DIAG] 诊断出错: {_e}", flush=True)
        # ============================================================
        from svd_tool.main import main
        main()
