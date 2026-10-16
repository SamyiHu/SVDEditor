#!/usr/bin/env python3
"""alternate 属性的 GUI 支持测试（离屏）。

覆盖：寄存器/外设编辑对话框的备选输入、重复地址先判 alternate 再报错、
校验结果单列 alternate 信息项。
"""
import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from PyQt6.QtWidgets import QApplication

from svd_tool.core.data_model import Peripheral, Register, Field, DeviceInfo
from svd_tool.core.svd_schema_validator import SVDSchemaValidator
from svd_tool.i18n.i18n import t

app = QApplication.instance() or QApplication(sys.argv)


def _regs():
    return {
        "STAT": Register(name="STAT", offset="0x0", description="status"),
        "CTRL": Register(name="CTRL", offset="0x4", description="control"),
    }


class TestRegisterDialog:
    def _make_dialog(self, register=None, is_edit=False):
        from svd_tool.ui.dialog_factories import RegisterEditDialog

        regs = _regs()
        return RegisterEditDialog(register=register, existing_registers=list(regs.keys()),
                                  existing_registers_data=regs, is_edit=is_edit)

    def test_duplicate_offset_conflicts_without_alternate(self):
        dlg = self._make_dialog()
        dlg.offset_edit.setText("0x0")  # 与 STAT 重复
        dlg._check_offset_conflict()
        assert dlg._has_offset_conflict is True

    def test_duplicate_offset_exempted_by_alternate(self):
        dlg = self._make_dialog()
        dlg.offset_edit.setText("0x0")
        # 选择备选寄存器 STAT → 冲突解除
        idx = dlg.alternate_register_combo.findText("STAT")
        assert idx >= 0
        dlg.alternate_register_combo.setCurrentIndex(idx)
        dlg._check_offset_conflict()
        assert dlg._has_offset_conflict is False

    def test_reverse_reference_also_exempted(self):
        """对方已指向本寄存器（编辑 STAT 时 STAT_ALT 指向它）→ 也豁免。"""
        regs = _regs()
        regs["STAT_ALT"] = Register(name="STAT_ALT", offset="0x0",
                                    alternate_register="STAT")
        from svd_tool.ui.dialog_factories import RegisterEditDialog

        dlg = RegisterEditDialog(register=regs["STAT"],
                                 existing_registers=list(regs.keys()),
                                 existing_registers_data=regs, is_edit=True)
        dlg.offset_edit.setText("0x0")  # 与 STAT_ALT 重复
        dlg._check_offset_conflict()
        assert dlg._has_offset_conflict is False

    def test_collect_and_load(self):
        regs = _regs()
        regs["STAT_ALT"] = Register(name="STAT_ALT", offset="0x0",
                                    alternate_register="STAT", alternate_group="CFG")
        dlg = self._make_dialog(register=regs["STAT_ALT"], is_edit=True)
        assert dlg.alternate_register_combo.currentText() == "STAT"
        assert dlg.alternate_group_edit.text() == "CFG"

        dlg.collect_data()
        assert dlg.result_data["alternate_register"] == "STAT"
        assert dlg.result_data["alternate_group"] == "CFG"

        # 清除备选
        dlg.alternate_register_combo.setCurrentIndex(0)  # "无"
        dlg.collect_data()
        assert dlg.result_data["alternate_register"] == ""


class TestPeripheralDialog:
    def _make_dialog(self, peripheral=None, is_edit=False):
        from svd_tool.ui.dialog_factories import PeripheralEditDialog

        periphs = {
            "USB": Peripheral(name="USB", base_address="0x4000A000"),
        }
        return PeripheralEditDialog(peripheral=peripheral,
                                    existing_peripherals=list(periphs.keys()),
                                    existing_peripherals_data=periphs,
                                    is_edit=is_edit)

    def test_duplicate_address_conflicts_without_alternate(self):
        dlg = self._make_dialog()
        dlg.name_edit.setText("USB2")
        dlg.base_addr_edit.setText("0x4000A000")  # 与 USB 重叠
        dlg.size_edit.setText("0x100")
        dlg._check_address_conflict()
        assert dlg._has_address_conflict is True

    def test_duplicate_address_exempted_by_alternate(self):
        dlg = self._make_dialog()
        dlg.name_edit.setText("USB2")
        dlg.base_addr_edit.setText("0x4000A000")
        dlg.size_edit.setText("0x100")
        idx = dlg.alternate_combo.findText("USB")
        assert idx >= 0
        dlg.alternate_combo.setCurrentIndex(idx)
        dlg._check_address_conflict()
        assert dlg._has_address_conflict is False

    def test_collect_and_load(self):
        usb = Peripheral(name="USB", base_address="0x4000A000")
        usb_alt = Peripheral(name="USB2", base_address="0x4000A000",
                             alternate_peripheral="USB")
        # load 需要 USB2 在 existing 列表外也能回填（悬空补项逻辑）
        dlg = self._make_dialog(peripheral=usb_alt, is_edit=True)
        assert dlg.alternate_combo.currentText() == "USB"

        dlg.alternate_combo.setCurrentIndex(0)
        dlg.collect_data()
        assert dlg.result_data["alternate_peripheral"] == ""


class TestValidatorInfoListing:
    def test_alternate_listed_as_info(self):
        dev = DeviceInfo(name="D", version="1.0")
        p = Peripheral(name="P", base_address="0x40000000")
        p.registers["STAT"] = Register(name="STAT", offset="0x0")
        p.registers["STAT_ALT"] = Register(name="STAT_ALT", offset="0x0",
                                           alternate_register="STAT")
        dev.peripherals["P"] = p

        usb = Peripheral(name="USB", base_address="0x4000A000")
        usb_alt = Peripheral(name="USB2", base_address="0x4000A000",
                             alternate_peripheral="USB")
        dev.peripherals["USB"] = usb
        dev.peripherals["USB2"] = usb_alt

        v = SVDSchemaValidator()
        v.validate_all(dev)
        infos = [i.message for i in v.results if i.severity.value == "info"]
        assert any("备选寄存器" in m and "STAT_ALT" in m for m in infos), infos
        assert any("备选外设" in m and "USB2" in m for m in infos), infos
        # 不产生错误
        errs = [i.message for i in v.get_errors()]
        assert not any("重叠" in m or "重复" in m for m in errs), errs
