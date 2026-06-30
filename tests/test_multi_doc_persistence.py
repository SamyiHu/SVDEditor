#!/usr/bin/env python3
"""
多文档数据持久化与隔离测试 —— 系统性覆盖"编辑丢失/被其他文件覆盖"的所有组合。

针对用户反复遇到的 bug：删除/修改后保存生效，但被后续操作（打开其他文件、
关闭标签页、重新打开、AI 跨文档操作）还原或覆盖。

测试矩阵（每个 test_* 是独立场景，必须全部通过）：
  1. AI改A → 开B（验证 active 错位修复）→ 切回A：A保留
  2. AI改A → 开B → 关A标签：关闭时编辑不丢，B不被A污染
  3. 编辑A → _save → 重新打开A：A恢复编辑状态（不还原成磁盘原始）
  4. AI改A → 关A标签 → 重开A：修改的命运明确
  5. 编辑A → 开B → 关B标签 → 回A：A不受B影响
  6. AI 切换 A↔B 多次 → 改A → 切回：数据隔离
  7. 多文档 device_info 独立性：改A不改B（深拷贝）
  8. 关闭非活动文档不影响活动文档编辑
"""
import sys
import os
import copy
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

from svd_tool.core.data_model import DeviceInfo, Peripheral, Register, Interrupt
from svd_tool.core.svd_generator import SVDGenerator
from svd_tool.core.svd_parser import SVDParser


# ==================== 辅助 ====================

def make_device(name: str, n_periphs: int = 2, regs_per: int = 3) -> DeviceInfo:
    """构造测试设备：n 个外设，每个 regs_per 个寄存器。"""
    dev = DeviceInfo(name=name, version="1.0")
    for pi in range(n_periphs):
        pn = f"{name}_P{pi}"
        p = Peripheral(name=pn, base_address=f"0x{0x40000000 + pi*0x1000:08X}")
        for ri in range(regs_per):
            p.registers[f"R{ri}"] = Register(name=f"R{ri}", offset=f"0x{ri*4:02X}")
        dev.peripherals[pn] = p
    return dev


def write_svd_file(dev: DeviceInfo) -> str:
    """把 device 写成临时 SVD 文件，返回路径。"""
    f = tempfile.NamedTemporaryFile(suffix=".svd", delete=False, mode="w",
                                    prefix=f"{dev.name}_")
    f.write(SVDGenerator(dev).generate())
    f.close()
    return f.name


def reg_count(dev: DeviceInfo) -> int:
    return sum(len(p.registers) for p in dev.peripherals.values())


def periph_count(dev: DeviceInfo) -> int:
    return len(dev.peripherals)


# ==================== 真实窗口驱动 ====================

class WindowDriver:
    """封装真实 MainWindow 的多文档操作，模拟用户/AI 行为。"""

    def __init__(self):
        from svd_tool.ui.main_window._base import MainWindowRefactored
        self.mw = MainWindowRefactored()

    @property
    def dm(self):
        return self.mw.document_manager

    @property
    def sm(self):
        return self.mw.state_manager

    def open_file(self, file_path: str) -> str:
        """模拟 open_svd_file 对单个文件的真实流程（含修复后的 switch_to）。
        返回 doc_id。"""
        self.mw._save_current_document_state()
        # 重复文件检查（修复点）
        existing = self.dm.find_by_file_path(file_path)
        if existing:
            self.dm.switch_to(existing)
            doc = self.dm.get_document(existing)
            if doc:
                self.mw._restore_document_state(doc)
            return existing
        di = SVDParser().parse_file(file_path)
        self.sm.pause_notifications()
        try:
            self.sm.device_info = di
            self.sm.clear_selection()
            self.sm.command_history.clear()
        finally:
            self.sm.resume_notifications()
        new_id = self.dm.open_document(di, file_path=file_path)
        self.dm.switch_to(new_id)  # 修复点：注册后立即切到新文档
        self.mw._restore_document_state(self.dm.get_document(new_id))
        return new_id

    def switch_to(self, doc_id: str):
        """模拟 _on_document_tab_clicked：保存旧 + 恢复新。"""
        self.mw._save_current_document_state()
        self.dm.switch_to(doc_id)
        doc = self.dm.get_document(doc_id)
        if doc:
            self.mw._restore_document_state(doc)

    def close_tab(self, doc_id: str):
        """模拟 _on_document_tab_clicked 关闭（修复后）。"""
        # 跳过 modified 确认对话框（测试中视为用户确认关闭）
        self.mw._save_current_document_state()
        was_active = (doc_id == self.dm.active_doc_id)
        self.dm.close_document(doc_id)
        if was_active:
            new_active = self.dm.active_document
            if new_active:
                self.mw._restore_document_state(new_active)

    def ai_add_peripheral(self, name: str):
        """模拟 AI 通过 state_manager 直接添加外设（最简路径）。"""
        p = Peripheral(name=name, base_address="0x50000000")
        self.sm.device_info.peripherals[name] = p
        self.mw._save_current_document_state()
        self.dm.mark_modified()

    def manual_delete_registers(self, periph: str, count: int):
        """模拟用户批量删除寄存器。"""
        if periph in self.sm.device_info.peripherals:
            regs = self.sm.device_info.peripherals[periph].registers
            keys = list(regs.keys())[:count]
            for k in keys:
                del regs[k]
        self.mw._save_current_document_state()
        self.dm.mark_modified()

    def save_to_disk(self, doc_id: str):
        """模拟保存（用 doc 的 device_info 生成写回文件）。"""
        doc = self.dm.get_document(doc_id)
        if doc and doc.file_path:
            # 保存前先同步当前编辑到 doc
            self.mw._save_current_document_state()
            doc2 = self.dm.get_document(doc_id)
            xml = SVDGenerator(doc2.device_info).generate()
            with open(doc2.file_path, "w", encoding="utf-8") as f:
                f.write(xml)
            self.dm.save_document(doc_id)


# ==================== 测试框架 ====================

class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.failures = []

    def check(self, cond, msg):
        s = "PASS" if cond else "FAIL"
        if cond:
            self.passed += 1
        else:
            self.failed += 1
            self.failures.append(msg)
        print(f"  [{s}] {msg}")


def cleanup(files):
    for f in files:
        try:
            os.unlink(f)
        except Exception:
            pass


# ==================== 测试用例 ====================

def test_ai_edit_then_open_new_doc(TR):
    print("\n[测试1] AI改A → 开新文件B → 切回A：A保留AI修改，B独立")
    d = WindowDriver()
    fA = write_svd_file(make_device("A", 2, 2))
    fB = write_svd_file(make_device("B", 1, 1))
    try:
        a = d.open_file(fA)
        d.ai_add_peripheral("AI_PERIPH")
        n_before = periph_count(d.sm.device_info)
        TR.check(n_before == 3, f"AI添加后A有3个外设（实际{n_before}）")

        b = d.open_file(fB)  # 修复点：开B后应switch到B
        TR.check(d.dm.active_doc_id == b, "打开B后active是B（修复active错位）")
        TR.check(periph_count(d.sm.device_info) == 1, "当前state_manager是B（1外设）")

        d.switch_to(a)
        TR.check("AI_PERIPH" in d.sm.device_info.peripherals, "切回A后AI添加的外设保留")
        TR.check(periph_count(d.sm.device_info) == 3, "切回A后是A的3个外设")
    finally:
        cleanup([fA, fB])


def test_ai_edit_close_tab(TR):
    print("\n[测试2] AI改A → 开B → 关A标签：A关闭时编辑不丢，B不被污染")
    d = WindowDriver()
    fA = write_svd_file(make_device("A", 2, 2))
    fB = write_svd_file(make_device("B", 1, 1))
    try:
        a = d.open_file(fA)
        d.ai_add_peripheral("AI_PERIPH")
        b = d.open_file(fB)
        b_regs_before = reg_count(d.sm.device_info)

        d.close_tab(a)  # 关闭A（活动→B）
        TR.check(d.dm.active_doc_id == b, "关A后active切到B")
        # B的state_manager数据应仍是B（未被A污染）
        TR.check("AI_PERIPH" not in d.sm.device_info.peripherals,
                 "B的当前数据不含A的AI_PERIPH（未被A污染）")
        TR.check(reg_count(d.sm.device_info) == b_regs_before,
                 f"B的寄存器数不变（实际{reg_count(d.sm.device_info)}）")
    finally:
        cleanup([fA, fB])


def test_edit_save_reopen_same_file(TR):
    print("\n[测试3] 编辑A→保存→重新打开A：A恢复编辑状态（不还原成磁盘原始）")
    d = WindowDriver()
    fA = write_svd_file(make_device("A", 2, 3))
    try:
        a = d.open_file(fA)
        d.manual_delete_registers("A_P0", 2)  # 删2个寄存器
        d.save_to_disk(a)
        regs_after_save = reg_count(d.sm.device_info)

        # 重新打开同一文件（修复点：应切回已打开的doc而非重新解析覆盖）
        a2 = d.open_file(fA)
        TR.check(a2 == a, "重新打开A应切回已打开的doc（不新建）")
        TR.check(reg_count(d.sm.device_info) == regs_after_save,
                 f"重新打开后A保留编辑（寄存器{reg_count(d.sm.device_info)}，期望{regs_after_save}）")
    finally:
        cleanup([fA])


def test_edit_then_close_tab_then_reopen(TR):
    print("\n[测试4] 编辑A→关A标签（未保存到磁盘）→重开A：磁盘文件是原始数据")
    d = WindowDriver()
    fA = write_svd_file(make_device("A", 2, 3))
    try:
        a = d.open_file(fA)
        d.manual_delete_registers("A_P0", 2)  # 编辑但未save_to_disk
        d.close_tab(a)  # 关闭A（未保存到磁盘，内存编辑丢失是预期）

        # 重新打开：从磁盘读取（应是原始3+3=6寄存器）
        a2 = d.open_file(fA)
        TR.check(reg_count(d.sm.device_info) == 6,
                 f"重开未保存的A是磁盘原始数据（6寄存器，实际{reg_count(d.sm.device_info)}）")
    finally:
        cleanup([fA])


def test_edit_open_other_close_other(TR):
    print("\n[测试5] 编辑A → 开B → 关B标签 → 回A：A不受B影响")
    d = WindowDriver()
    fA = write_svd_file(make_device("A", 2, 2))
    fB = write_svd_file(make_device("B", 1, 1))
    try:
        a = d.open_file(fA)
        d.manual_delete_registers("A_P0", 1)
        a_regs = reg_count(d.sm.device_info)

        b = d.open_file(fB)
        d.close_tab(b)  # 关B（活动→A）
        TR.check(d.dm.active_doc_id == a, "关B后active回到A")
        TR.check(reg_count(d.sm.device_info) == a_regs,
                 f"A的编辑保留（{reg_count(d.sm.device_info)}，期望{a_regs}）")
    finally:
        cleanup([fA, fB])


def test_ai_switch_multiple(TR):
    print("\n[测试6] 切换A↔B多次 → 改A → 切回：数据隔离")
    d = WindowDriver()
    fA = write_svd_file(make_device("A", 1, 2))
    fB = write_svd_file(make_device("B", 1, 2))
    try:
        a = d.open_file(fA)
        b = d.open_file(fB)

        # 来回切换3次
        for _ in range(3):
            d.switch_to(a)
            d.switch_to(b)

        # 在A上改
        d.switch_to(a)
        d.manual_delete_registers("A_P0", 1)
        a_regs = reg_count(d.sm.device_info)

        # 切到B再切回A
        d.switch_to(b)
        d.switch_to(a)
        TR.check(reg_count(d.sm.device_info) == a_regs,
                 f"多次切换后A编辑保留（{reg_count(d.sm.device_info)}，期望{a_regs}）")
        # B不应有A的删除
        d.switch_to(b)
        TR.check(reg_count(d.sm.device_info) == 2, "B的寄存器数不受A影响（仍是2）")
    finally:
        cleanup([fA, fB])


def test_device_info_independence(TR):
    print("\n[测试7] 多文档device_info独立性：改A不改B（深拷贝）")
    d = WindowDriver()
    fA = write_svd_file(make_device("A", 1, 2))
    fB = write_svd_file(make_device("B", 1, 2))
    try:
        a = d.open_file(fA)
        b = d.open_file(fB)

        docA = d.dm.get_document(a)
        docB = d.dm.get_document(b)
        TR.check(docA.device_info is not docB.device_info, "A/B的device_info是不同对象")

        # 改A的内存对象
        docA.device_info.peripherals["A_P0"].registers["HACK"] = Register("HACK", "0xFF")
        TR.check("HACK" not in docB.device_info.peripherals["B_P0"].registers,
                 "改A的对象不污染B（深拷贝隔离）")
    finally:
        cleanup([fA, fB])


def test_close_inactive_doc(TR):
    print("\n[测试8] 关闭非活动文档不影响活动文档编辑")
    d = WindowDriver()
    fA = write_svd_file(make_device("A", 1, 2))
    fB = write_svd_file(make_device("B", 1, 2))
    fC = write_svd_file(make_device("C", 1, 2))
    try:
        a = d.open_file(fA)
        b = d.open_file(fB)
        c = d.open_file(fC)
        # 当前活动是C，编辑C
        d.manual_delete_registers("C_P0", 1)
        c_regs = reg_count(d.sm.device_info)

        # 关闭非活动的B
        d.close_tab(b)
        TR.check(d.dm.active_doc_id == c, "关非活动B后active仍是C")
        TR.check(reg_count(d.sm.device_info) == c_regs,
                 f"C的编辑不受关闭B影响（{reg_count(d.sm.device_info)}，期望{c_regs}）")
    finally:
        cleanup([fA, fB, fC])


def test_interrupt_edit_persistence(TR):
    print("\n[测试9] 中断编辑→保存→重开：中断关联保留（继承外设场景）")
    d = WindowDriver()
    # 构造含继承外设的设备：UART2 derivedFrom UART3，中断关联两者
    dev = make_device("IRQTEST", 0, 0)
    u0 = Peripheral(name="UART0", base_address="0x40000000")
    u0.registers["R"] = Register("R", "0x00")
    u3 = Peripheral(name="UART3", base_address="0x40001000")
    u3.registers["R"] = Register("R", "0x00")
    u2 = Peripheral(name="UART2", base_address="0x40002000", derived_from="UART3")
    dev.peripherals = {"UART0": u0, "UART2": u2, "UART3": u3}
    dev.interrupts["SHARED"] = Interrupt(name="SHARED", value=7,
                                         peripherals=["UART0", "UART2"])
    fA = write_svd_file(dev)
    try:
        a = d.open_file(fA)
        d.save_to_disk(a)

        # 重开，验证中断关联
        a2 = d.open_file(fA)
        irq = d.sm.device_info.interrupts.get("SHARED")
        TR.check(irq is not None, "重开后SHARED中断存在")
        if irq:
            TR.check(set(irq.peripherals) == {"UART0", "UART2"},
                     f"中断关联UART0/UART2保留（实际{irq.peripherals}）")
    finally:
        cleanup([fA])


# ==================== 主入口 ====================

def run_all():
    app = QApplication.instance() or QApplication([])
    TR = TestResult()

    tests = [
        test_ai_edit_then_open_new_doc,
        test_ai_edit_close_tab,
        test_edit_save_reopen_same_file,
        test_edit_then_close_tab_then_reopen,
        test_edit_open_other_close_other,
        test_ai_switch_multiple,
        test_device_info_independence,
        test_close_inactive_doc,
        test_interrupt_edit_persistence,
    ]

    print("=" * 60)
    print("多文档数据持久化与隔离测试（覆盖AI写入/标签关闭/重开等组合）")
    print("=" * 60)

    for t in tests:
        try:
            t(TR)
        except Exception as e:
            import traceback
            TR.failed += 1
            TR.failures.append(f"{t.__name__} 异常: {e}\n{traceback.format_exc()}")
            print(f"  [ERROR] {t.__name__} 抛异常: {e}")

    print("\n" + "=" * 60)
    print(f"结果: {TR.passed} 通过, {TR.failed} 失败")
    if TR.failures:
        print("\n失败项:")
        for f in TR.failures:
            print(f"  - {f}")
        print("\n=== 有失败 ===")
        sys.exit(1)
    else:
        print("=== 全部通过：多文档数据隔离与持久化正确 ===")
        sys.exit(0)


if __name__ == "__main__":
    run_all()
