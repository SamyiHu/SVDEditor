#!/usr/bin/env python3
"""
多文档数据隔离测试 —— 复现并验证修复"后开文档覆盖先开文档"的 bug。

核心场景：开文档A → AI 改 A → 开文档B → 切回 A，A 的数据必须保持 AI 改后的状态，
不能被 B 覆盖，且 A/B 的 device_info 必须是独立对象（不共享引用）。
"""
import sys
import os
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

from svd_tool.core.data_model import DeviceInfo, Peripheral, Register
from svd_tool.core.document_manager import DocumentManager
from svd_tool.ui.components.state_manager import StateManager
from svd_tool.ai_assistant.command_executor import CommandExecutor


def make_device(name: str, periph: str) -> DeviceInfo:
    dev = DeviceInfo(name=name, version="1.0")
    p = Peripheral(name=periph, base_address="0x40000000", description=f"{periph} of {name}")
    p.registers["REG0"] = Register(name="REG0", offset="0x00")
    dev.peripherals[periph] = p
    return dev


def make_executor(sm: StateManager, dm: DocumentManager, mw) -> CommandExecutor:
    class _Coord:
        def __init__(self, sm): self._sm = sm
        def get_component(self, name):
            return self._sm if name == "state_manager" else None
        def notify_peripheral_updated(self, name): pass

    ex = CommandExecutor.__new__(CommandExecutor)
    ex.coordinator = _Coord(sm)
    ex.main_window = mw
    from svd_tool.ai_assistant.command_executor import _GuiBridge
    ex._gui = _GuiBridge()
    ex._operation_map = {
        "add_peripheral": ex._op_add_peripheral,
        "add_register": ex._op_add_register,
        "update_peripheral": ex._op_update_peripheral,
        "remove_peripheral": ex._op_remove_peripheral,
    }
    return ex


def run_test():
    app = QApplication.instance() or QApplication([])

    sm = StateManager()
    dm = DocumentManager()
    # main_window 只需暴露 document_manager
    mw = type("MW", (), {"document_manager": dm})()

    # 模拟打开文档A（真实流程：open_document 内部深拷贝，state_manager 指向原对象）
    devA = make_device("DEVICE_A", "GPIOA")
    docA_id = dm.open_document(devA, file_path="/tmp/A.svd")
    dm.switch_to(docA_id)  # 设为活动文档（mark_modified 依赖 _active_doc_id）
    docA = dm.get_document(docA_id)
    sm.device_info = devA  # state_manager 指向原对象（与 docA.device_info 不同）

    # 模拟 _save_current_document_state 的浅引用逻辑（复现真实行为）
    # 注意：open_document 已深拷贝，docA.device_info 是独立副本
    ex = make_executor(sm, dm, mw)

    failures = []
    results = {}

    def worker():
        import copy

        def save_state():
            """模拟 _save_current_document_state 的核心逻辑（modified 决定深/浅拷贝）"""
            doc = dm.active_document
            if not doc:
                return
            if doc.modified or doc.device_info is None:
                doc.device_info = copy.deepcopy(sm.device_info)
            else:
                doc.device_info = sm.device_info

        def restore_state(doc):
            """模拟 _restore_document_state 的核心逻辑"""
            if doc.modified:
                sm.device_info = copy.deepcopy(doc.device_info)
            else:
                sm.device_info = doc.device_info

        try:
            # ===== 步骤1: AI 在文档A上添加一个外设（触发 mark_modified）=====
            r = ex.execute({"operation": "add_peripheral",
                            "params": {"name": "AI_ADDED", "base_address": "0x40010000"}})
            results["ai_add"] = r
            results["docA_modified_after_ai"] = docA.modified

            # 切换前保存当前文档（真实流程切换文档会先 _save_current_document_state）
            save_state()
            results["docA_has_ai_added_before_switch"] = "AI_ADDED" in docA.device_info.peripherals

            # ===== 步骤2: 打开文档B（切换）=====
            devB = make_device("DEVICE_B", "USART")
            docB_id = dm.open_document(devB, file_path="/tmp/B.svd")
            dm.switch_to(docB_id)
            docB = dm.get_document(docB_id)
            sm.device_info = docB.device_info  # 切换到 B

            results["docB_is_different_obj"] = (docB.device_info is not docA.device_info)
            results["docB_name"] = docB.device_info.name

            # ===== 步骤3: 切回文档A =====
            dm.switch_to(docA_id)
            restore_state(docA)

            # ===== 验证：A 的数据应保持 AI 改后的状态，未被 B 覆盖 =====
            results["restored_A_name"] = sm.device_info.name
            results["restored_A_has_ai_added"] = "AI_ADDED" in sm.device_info.peripherals
            results["restored_A_lost_GPIOA"] = "GPIOA" not in sm.device_info.peripherals
            results["A_not_polluted_by_B"] = "USART" not in sm.device_info.peripherals

            # ===== 步骤4: 验证两个文档的 device_info 是独立对象 =====
            # AI 继续改 A，不应影响 B
            sm.device_info = copy.deepcopy(docA.device_info)  # 确保在 A 上
            ex.execute({"operation": "add_peripheral",
                        "params": {"name": "A_ONLY", "base_address": "0x40020000"}})
            # B 不应出现 A_ONLY（B 的 device_info 独立）
            results["B_unaffected_by_A_edit"] = "A_ONLY" not in docB.device_info.peripherals

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
        s = "PASS" if cond else "FAIL"
        if not cond:
            ok = False
            failures.append(msg)
        print(f"  [{s}] {msg}")

    print("=== 多文档数据隔离测试（修复后开覆盖先开 bug）===\n")

    print("[步骤1] AI 改文档A后应标记 modified")
    check(results.get("ai_add", {}).get("success") is True, "AI add_peripheral success")
    check(results.get("docA_modified_after_ai") is True,
          f"docA.modified 应为 True（实际 {results.get('docA_modified_after_ai')}）")

    print("\n[步骤2] 切换前后文档A保留AI修改")
    check(results.get("docA_has_ai_added_before_switch") is True, "切换前 docA 已含 AI_ADDED")

    print("\n[步骤3] 切回A后数据未被B覆盖")
    check(results.get("restored_A_name") == "DEVICE_A",
          f"恢复后设备名应为 DEVICE_A（实际 {results.get('restored_A_name')}）")
    check(results.get("restored_A_has_ai_added") is True, "恢复后 A 仍含 AI_ADDED")
    check(results.get("A_not_polluted_by_B") is True, "A 未被 B 的 USART 污染")

    print("\n[步骤4] A/B 的 device_info 完全独立")
    check(results.get("docB_is_different_obj") is True, "docB.device_info 是独立对象")
    check(results.get("B_unaffected_by_A_edit") is True, "改 A 不影响 B 的数据")

    print()
    if failures:
        print("=== 失败 ===")
        for f in failures:
            print(f"  - {f}")
        print("\n=== 测试未通过 ===")
        sys.exit(1)
    else:
        print("=== 全部测试通过：多文档隔离正确 ===")
        sys.exit(0)


if __name__ == "__main__":
    run_test()
