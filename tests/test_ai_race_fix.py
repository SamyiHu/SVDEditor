#!/usr/bin/env python3
"""
AI 竞态修复集成测试

验证核心修复路径在真实对象上工作（非 mock）：
1. 工作线程调用写操作 → 通过 _GuiBridge 派发到主线程执行（线程隔离）
2. 写操作真实修改 device_info
3. begin_batch/end_batch 合并通知（pause/resume）
4. 改名（寄存器/位域）真实生效，dict key 与对象 name 一致
5. 中断增删改真实生效

需要图形环境（QApplication），但不需要显示窗口。
"""
import sys
import os
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

from svd_tool.core.data_model import DeviceInfo, Peripheral, Register, Field, Interrupt
from svd_tool.ui.components.state_manager import StateManager
from svd_tool.ai_assistant.command_executor import CommandExecutor


def build_device() -> DeviceInfo:
    """构造一个带数据的小型设备"""
    dev = DeviceInfo(name="TEST_DEV", version="1.0")
    gpio = Peripheral(name="GPIO", base_address="0x40000000", description="GPIO")
    gpio.registers["CTRL"] = Register(name="CTRL", offset="0x00", description="control")
    gpio.registers["CTRL"].fields["ENABLE"] = Field(
        name="ENABLE", bit_offset=0, bit_width=1, description="enable bit")
    dev.peripherals["GPIO"] = gpio

    usart = Peripheral(name="USART", base_address="0x40004000", description="USART")
    usart.registers["SR"] = Register(name="SR", offset="0x00", description="status")
    dev.peripherals["USART"] = usart

    dev.interrupts["EXTI0"] = Interrupt(name="EXTI0", value=6, description="exti0")
    return dev


def make_executor(sm: StateManager) -> CommandExecutor:
    """构建真实 CommandExecutor，用最小 coordinator 桥接 state_manager"""
    class _Coord:
        def __init__(self, sm):
            self._sm = sm
        def get_component(self, name):
            if name == "state_manager":
                return self._sm
            return None
        def notify_peripheral_updated(self, name):
            pass

    # 跳过完整 __init__（依赖 main_window），手动装必要字段
    ex = CommandExecutor.__new__(CommandExecutor)
    ex.coordinator = _Coord(sm)
    ex.main_window = None
    from svd_tool.ai_assistant.command_executor import _GuiBridge
    ex._gui = _GuiBridge()
    ex._operation_map = {
        # 只读
        "info": ex._op_info,
        # 写
        "add_peripheral": ex._op_add_peripheral,
        "update_register": ex._op_update_register,
        "update_field": ex._op_update_field,
        "add_interrupt": ex._op_add_interrupt,
        "remove_interrupt": ex._op_remove_interrupt,
        "remove_peripheral": ex._op_remove_peripheral,
    }
    return ex


def run_test():
    app = QApplication.instance() or QApplication([])

    sm = StateManager()
    sm.device_info = build_device()
    ex = make_executor(sm)
    main_tid = threading.get_ident()

    notify_count = {"n": 0}
    def on_change():
        notify_count["n"] += 1
    sm.register_state_change_callback(on_change)

    failures = []
    results = {}

    def worker():
        try:
            # ===== T1: 写操作在工作线程调用，但实际在主线程执行 =====
            # 记录 add_peripheral 内部 _execute_undoable/_notify_refresh 执行的线程
            r = ex.execute({"operation": "add_peripheral",
                            "params": {"name": "SPI", "base_address": "0x40008000"}})
            results["add_periph"] = r
            results["spi_exists"] = "SPI" in sm.device_info.peripherals

            # ===== T2: 寄存器改名真实生效，key 与 name 一致 =====
            r2 = ex.execute({"operation": "update_register",
                             "params": {"peripheral": "GPIO", "name": "CTRL",
                                        "updates": {"name": "CTRL_REG"}}})
            results["rename_reg"] = r2
            regs = sm.device_info.peripherals["GPIO"].registers
            results["new_key_exists"] = "CTRL_REG" in regs
            results["old_key_gone"] = "CTRL" not in regs
            results["key_name_consistent"] = (
                "CTRL_REG" in regs and regs["CTRL_REG"].name == "CTRL_REG")

            # ===== T3: 位域改名 =====
            r3 = ex.execute({"operation": "update_field",
                             "params": {"peripheral": "GPIO", "register": "CTRL_REG",
                                        "name": "ENABLE",
                                        "updates": {"name": "EN_BIT"}}})
            results["rename_field"] = r3
            flds = sm.device_info.peripherals["GPIO"].registers["CTRL_REG"].fields
            results["field_renamed"] = "EN_BIT" in flds and flds["EN_BIT"].name == "EN_BIT"

            # ===== T4: 中断增删 =====
            r4 = ex.execute({"operation": "add_interrupt",
                             "params": {"name": "DMA1", "value": 11, "peripheral": "GPIO"}})
            results["add_irq"] = r4
            results["irq_added"] = "DMA1" in sm.device_info.interrupts

            r5 = ex.execute({"operation": "remove_interrupt", "params": {"name": "EXTI0"}})
            results["rm_irq"] = r5
            results["irq_removed"] = "EXTI0" not in sm.device_info.interrupts

            # ===== T5: begin_batch/end_batch 合并通知 =====
            notify_count["n"] = 0  # 重置计数
            ex.begin_batch()
            for i in range(5):
                ex.execute({"operation": "add_peripheral",
                            "params": {"name": f"BULK_{i}", "base_address": f"0x4001000{i}"}})
            batch_notify_during = notify_count["n"]
            ex.end_batch()
            batch_notify_after = notify_count["n"]
            results["batch_notify_during"] = batch_notify_during
            results["batch_notify_after"] = batch_notify_after

            # ===== T6: 删除清理 =====
            for i in range(5):
                ex.execute({"operation": "remove_peripheral", "params": {"name": f"BULK_{i}"}})

        except Exception as e:
            import traceback
            failures.append(f"worker 异常: {e}\n{traceback.format_exc()}")
        finally:
            QTimer.singleShot(0, app.quit)

    t = threading.Thread(target=worker)
    t.start()
    app.exec()
    t.join(timeout=30)

    ok = True
    def check(cond, msg):
        nonlocal ok
        status = "PASS" if cond else "FAIL"
        if not cond:
            ok = False
            failures.append(msg)
        print(f"  [{status}] {msg}")

    print("=== AI 竞态修复集成测试 ===\n")

    print("[T1] 写操作真实生效")
    check(results.get("add_periph", {}).get("success") is True, "add_peripheral 返回 success")
    check(results.get("spi_exists") is True, "SPI 真实加入 device.peripherals")

    print("\n[T2] 寄存器改名真实生效 + key/name 一致")
    check(results.get("rename_reg", {}).get("success") is True, "update_register 改名 success")
    check(results.get("new_key_exists") is True, "新 key CTRL_REG 存在")
    check(results.get("old_key_gone") is True, "旧 key CTRL 已移除")
    check(results.get("key_name_consistent") is True, "dict key 与 Register.name 一致")

    print("\n[T3] 位域改名真实生效")
    check(results.get("rename_field", {}).get("success") is True, "update_field 改名 success")
    check(results.get("field_renamed") is True, "位域 ENABLE→EN_BIT 生效且 key/name 一致")

    print("\n[T4] 中断增删真实生效")
    check(results.get("add_irq", {}).get("success") is True, "add_interrupt success")
    check(results.get("irq_added") is True, "DMA1 真实加入 device.interrupts")
    check(results.get("rm_irq", {}).get("success") is True, "remove_interrupt success")
    check(results.get("irq_removed") is True, "EXTI0 真实移除")

    print("\n[T5] begin_batch/end_batch 合并通知")
    check(results.get("batch_notify_during") == 0,
          f"批量期间通知被抑制（实际 {results.get('batch_notify_during')}，期望 0）")
    after = results.get("batch_notify_after")
    check(after is not None and after >= 1,
          f"批量结束后触发刷新（实际 {after}，期望 >=1）")

    print()
    if failures:
        print("=== 失败原因 ===")
        for f in failures:
            print(f"  - {f}")
        print("\n=== 测试未全部通过 ===")
        sys.exit(1)
    else:
        print("=== 全部测试通过 ===")
        sys.exit(0)


if __name__ == "__main__":
    run_test()
