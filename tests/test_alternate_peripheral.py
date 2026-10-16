#!/usr/bin/env python3
"""alternatePeripheral（备选外设）支持测试。

覆盖：解析 / 生成往返 / 数据模型序列化 / 校验器（引用+自引用+地址重叠豁免）/
冲突检测器（重叠与同基地址豁免、增量检测）/ MCP 工作区编辑 / diff。
"""
import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from svd_tool.core.address_conflict_detector import AddressConflictDetector, ConflictType
from svd_tool.core.data_model import DeviceInfo, Peripheral, Register, Field
from svd_tool.core.svd_differ import SVDDiffer, DiffType
from svd_tool.core.svd_generator import SVDGenerator
from svd_tool.core.svd_parser import SVDParser
from svd_tool.core.svd_schema_validator import SVDSchemaValidator

SVD_XML = """<?xml version="1.0" encoding="UTF-8"?>
<device schemaVersion="1.3">
  <vendor>TEST</vendor>
  <name>TEST_ALT</name>
  <version>1.0</version>
  <description>alternatePeripheral test</description>
  <addressUnitBits>8</addressUnitBits>
  <width>32</width>
  <size>0x20</size>
  <resetValue>0x00000000</resetValue>
  <resetMask>0xFFFFFFFF</resetMask>
  <peripherals>
    <peripheral>
      <name>USB</name>
      <description>USB controller</description>
      <groupName>USB</groupName>
      <baseAddress>0x4000A000</baseAddress>
      <addressBlock><offset>0x0</offset><size>0x400</size><usage>registers</usage></addressBlock>
      <registers>
        <register>
          <name>CTRL</name><description>Control register</description>
          <addressOffset>0x0</addressOffset><size>0x20</size>
          <fields>
            <field><name>EN</name><description>Enable</description>
              <bitOffset>0</bitOffset><bitWidth>1</bitWidth></field>
          </fields>
        </register>
      </registers>
    </peripheral>
    <peripheral>
      <name>USB_ALT</name>
      <description>USB alternate function</description>
      <alternatePeripheral>USB</alternatePeripheral>
      <groupName>USB</groupName>
      <baseAddress>0x4000A000</baseAddress>
      <addressBlock><offset>0x0</offset><size>0x400</size><usage>registers</usage></addressBlock>
      <registers>
        <register>
          <name>ACR</name><description>Alt control</description>
          <addressOffset>0x10</addressOffset><size>0x20</size>
          <fields>
            <field><name>MODE</name><description>Mode</description>
              <bitOffset>0</bitOffset><bitWidth>2</bitWidth></field>
          </fields>
        </register>
      </registers>
    </peripheral>
  </peripherals>
</device>
"""


@pytest.fixture
def device():
    return SVDParser().parse_string(SVD_XML)


class TestParseAndGenerate:
    def test_parse_alternate_peripheral(self, device):
        assert device.peripherals["USB"].alternate_peripheral == ""
        assert device.peripherals["USB_ALT"].alternate_peripheral == "USB"

    def test_generate_roundtrip_keeps_element(self, device):
        xml = SVDGenerator(device).generate(pretty_print=True)
        assert "<alternatePeripheral>USB</alternatePeripheral>" in xml

        reparsed = SVDParser().parse_string(xml)
        assert reparsed.peripherals["USB_ALT"].alternate_peripheral == "USB"

    def test_generate_element_order(self, device):
        """规范顺序：description 之后、groupName 之前。"""
        xml = SVDGenerator(device).generate(pretty_print=True)
        alt_block = xml.split("<name>USB_ALT</name>", 1)[1].split("</peripheral>", 1)[0]
        assert alt_block.index("<description>") < alt_block.index("<alternatePeripheral>") \
            < alt_block.index("<groupName>")

    def test_empty_not_generated(self, device):
        xml = SVDGenerator(device).generate(pretty_print=True)
        usb_block = xml.split("<name>USB</name>", 1)[1].split("</peripheral>", 1)[0]
        assert "alternatePeripheral" not in usb_block


class TestDataModel:
    def test_dict_roundtrip(self, device):
        p = device.peripherals["USB_ALT"]
        d = p.to_dict()
        assert d["alternate_peripheral"] == "USB"
        p2 = Peripheral.from_dict(d)
        assert p2.alternate_peripheral == "USB"

    def test_deepcopy(self, device):
        p2 = copy.deepcopy(device.peripherals["USB_ALT"])
        assert p2.alternate_peripheral == "USB"

    def test_device_dict_roundtrip(self, device):
        dev2 = DeviceInfo.from_dict(device.to_dict())
        assert dev2.peripherals["USB_ALT"].alternate_peripheral == "USB"


class TestValidator:
    def _texts(self, v):
        return [i.message for i in v.get_errors()]

    def test_valid_pair_no_overlap_error(self, device):
        """USB 与 USB_ALT 同地址块但互为 alternatePeripheral → 不报地址重叠。"""
        v = SVDSchemaValidator()
        v.validate_all(device)
        errs = self._texts(v)
        assert not any("重叠" in m and "USB" in m for m in errs), errs

    def test_overlap_error_without_alternate(self, device):
        """对照组：去掉 alternatePeripheral 后同样的布局必须报重叠。"""
        device.peripherals["USB_ALT"].alternate_peripheral = ""
        v = SVDSchemaValidator()
        v.validate_all(device)
        errs = self._texts(v)
        assert any("重叠" in m for m in errs), errs

    def test_dangling_reference(self, device):
        device.peripherals["USB_ALT"].alternate_peripheral = "NOPE"
        v = SVDSchemaValidator()
        v.validate_all(device)
        errs = self._texts(v)
        assert any("alternatePeripheral" in m for m in errs), errs

    def test_self_reference(self, device):
        device.peripherals["USB_ALT"].alternate_peripheral = "USB_ALT"
        v = SVDSchemaValidator()
        v.validate_all(device)
        errs = self._texts(v)
        assert any("alternatePeripheral" in m for m in errs), errs


class TestConflictDetector:
    def test_no_conflict_for_alternate_pair(self, device):
        d = AddressConflictDetector()
        found = d.detect_all(device)
        types = {c.conflict_type for c in found}
        assert ConflictType.PERIPHERAL_ADDRESS_OVERLAP not in types
        assert ConflictType.PERIPHERAL_BASE_DUPLICATE not in types

    def test_conflict_without_alternate(self, device):
        device.peripherals["USB_ALT"].alternate_peripheral = ""
        d = AddressConflictDetector()
        found = d.detect_all(device)
        types = {c.conflict_type for c in found}
        assert ConflictType.PERIPHERAL_ADDRESS_OVERLAP in types
        assert ConflictType.PERIPHERAL_BASE_DUPLICATE in types

    def test_incremental_detect_exempts_alternate(self, device):
        d = AddressConflictDetector()
        d.detect_all(device)
        # 增量检测 USB_ALT（模拟编辑后单外设重扫）
        found = d.detect_peripheral(device, "USB_ALT")
        types = {c.conflict_type for c in found}
        assert ConflictType.PERIPHERAL_ADDRESS_OVERLAP not in types

    def test_third_peripheral_same_base_still_conflicts(self, device):
        """与 alternate 对无关的第三个同地址外设仍要报冲突。"""
        device.peripherals["INTRUDER"] = Peripheral(
            name="INTRUDER", base_address="0x4000A000")
        d = AddressConflictDetector()
        found = d.detect_all(device)
        assert any(c.peripheral in ("INTRUDER", "USB", "USB_ALT")
                   and c.conflict_type == ConflictType.PERIPHERAL_ADDRESS_OVERLAP
                   for c in found)


class TestMcpWorkspace:
    def test_update_get_clear(self, device, tmp_path):
        from svd_tool.mcp_server.headless_workspace import HeadlessWorkspace

        svd_file = tmp_path / "alt.svd"
        svd_file.write_text(SVDGenerator(device).generate(pretty_print=True),
                            encoding="utf-8")

        ws = HeadlessWorkspace()
        assert ws.open_document(str(svd_file))["success"]

        r = ws.get_peripheral("USB_ALT")
        assert r["data"]["alternate_peripheral"] == "USB"

        # 改成 USB_ALT→USB 已是；改成新备选：先建一个新外设再指向它
        assert ws.add_peripheral("USB2", base_address="0x4000B000")["success"]
        r = ws.update_peripheral("USB_ALT", {"alternate_peripheral": "USB2"})
        assert r["success"], r["message"]
        assert ws.get_peripheral("USB_ALT")["data"]["alternate_peripheral"] == "USB2"

        # 清除
        r = ws.update_peripheral("USB_ALT", {"alternate_peripheral": ""})
        assert r["success"]
        assert ws.get_peripheral("USB_ALT")["data"]["alternate_peripheral"] == ""

        # 非法：不存在的备选
        r = ws.update_peripheral("USB_ALT", {"alternate_peripheral": "GHOST"})
        assert not r["success"]
        # 非法：自引用
        r = ws.update_peripheral("USB_ALT", {"alternate_peripheral": "USB_ALT"})
        assert not r["success"]


class TestDiff:
    def test_diff_detects_alternate_change(self, device):
        other = copy.deepcopy(device)
        other.peripherals["USB_ALT"].alternate_peripheral = "USB2"
        other.peripherals["USB2"] = Peripheral(name="USB2", base_address="0x4000B000")

        differ = SVDDiffer()
        diffs = differ.diff(device, other) or []

        def walk(items):
            for it in items:
                yield it
                yield from walk(getattr(it, "children", []))

        hits = [it for it in walk(diffs)
                if "alternate_peripheral" in str(getattr(it, "path", ""))
                and it.diff_type in (DiffType.MODIFIED, DiffType.ADDED)]
        assert hits
