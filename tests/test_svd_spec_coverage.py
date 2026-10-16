#!/usr/bin/env python3
"""CMSIS-SVD 规范覆盖测试（对齐 svdconv 能力）。

覆盖：
- P0 位域三种等价写法（bitOffset+bitWidth / lsb+msb / bitRange）
- P1a 高频元素真建模（alternateRegister/alternateGroup/dataType/
  modifiedWriteValues/readAction/prependToName/... 及设备级 vendorID/series 等）
- P1b 未知元素透传（writeConstraint/protection/dimName/vendorExtensions/CPU 扩展标志）
- P2 校验对齐（中断上限/枚举值/dim 一致性/C 标识符/alternateRegister 引用）
- MCP 编辑入口同步
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from svd_tool.core.data_model import DeviceInfo, Peripheral, Register, Field, Interrupt
from svd_tool.core.svd_generator import SVDGenerator
from svd_tool.core.svd_parser import SVDParser
from svd_tool.core.svd_schema_validator import SVDSchemaValidator

SPEC_SVD = """<?xml version="1.0" encoding="UTF-8"?>
<device schemaVersion="1.3">
  <vendor>TEST</vendor>
  <vendorID>TS</vendorID>
  <name>TEST_SPEC</name>
  <series>T1000</series>
  <version>2.0</version>
  <description>spec coverage test</description>
  <licenseText>MIT license</licenseText>
  <cpu>
    <name>CM4</name><revision>r0p1</revision><endian>little</endian>
    <mpuPresent>true</mpuPresent><fpuPresent>true</fpuPresent>
    <fpuDP>true</fpuDP><dspPresent>true</dspPresent>
    <nvicPrioBits>4</nvicPrioBits><vendorSystickConfig>false</vendorSystickConfig>
  </cpu>
  <headerSystemFilename>test_system.h</headerSystemFilename>
  <headerDefinitionsPrefix>TS_</headerDefinitionsPrefix>
  <addressUnitBits>8</addressUnitBits>
  <width>32</width>
  <peripherals>
    <peripheral>
      <name>PERI</name>
      <version>1.1</version>
      <description>Peripheral</description>
      <prependToName>P_</prependToName>
      <appendToName>_REG</appendToName>
      <headerStructName>PERI_T</headerStructName>
      <disableCondition>(%s &lt; 4)</disableCondition>
      <baseAddress>0x40000000</baseAddress>
      <addressBlock><offset>0x0</offset><size>0x100</size><usage>registers</usage></addressBlock>
      <registers>
        <register>
          <name>STAT</name>
          <description>Status register</description>
          <addressOffset>0x0</addressOffset>
          <fields>
            <field>
              <name>EN</name>
              <description>Enable</description>
              <bitOffset>0</bitOffset><bitWidth>1</bitWidth>
            </field>
          </fields>
        </register>
        <register>
          <name>CTRL</name>
          <description>Control register</description>
          <alternateGroup>CFG</alternateGroup>
          <addressOffset>0x4</addressOffset>
          <dataType>uint32_t</dataType>
          <modifiedWriteValues>oneToSet</modifiedWriteValues>
          <readAction>clear</readAction>
          <protection>s</protection>
          <writeConstraint><useEnumeratedValues>true</useEnumeratedValues></writeConstraint>
          <fields>
            <field>
              <name>MODE</name>
              <description>Mode</description>
              <lsb>3</lsb><msb>5</msb>
              <modifiedWriteValues>modify</modifiedWriteValues>
              <writeConstraint><range><minimum>0</minimum><maximum>5</maximum></range></writeConstraint>
            </field>
            <field>
              <name>RANGE</name>
              <description>Range</description>
              <bitRange>[15:8]</bitRange>
              <readAction>set</readAction>
            </field>
          </fields>
        </register>
        <register>
          <name>STAT_ALT</name>
          <description>Alternate view of STAT</description>
          <alternateRegister>STAT</alternateRegister>
          <addressOffset>0x0</addressOffset>
        </register>
        <register>
          <name>BUF[%s]</name>
          <description>Buffer array</description>
          <dim>4</dim>
          <dimIncrement>0x4</dimIncrement>
          <dimIndex>0-3</dimIndex>
          <dimName>BUF</dimName>
          <addressOffset>0x20</addressOffset>
        </register>
      </registers>
    </peripheral>
  </peripherals>
  <vendorExtensions><TESTEXT>42</TESTEXT></vendorExtensions>
</device>
"""


@pytest.fixture
def device():
    return SVDParser().parse_string(SPEC_SVD)


class TestBitStyles:
    """P0：位域三种等价写法统一换算为 bitOffset+bitWidth"""

    def test_three_styles_parsed(self, device):
        ctrl = device.peripherals["PERI"].registers["CTRL"]
        # bitOffset+bitWidth 在 STAT.EN
        assert device.peripherals["PERI"].registers["STAT"].fields["EN"].bit_offset == 0
        assert device.peripherals["PERI"].registers["STAT"].fields["EN"].bit_width == 1
        # lsb+msb：MODE [5:3]
        assert ctrl.fields["MODE"].bit_offset == 3
        assert ctrl.fields["MODE"].bit_width == 3
        # bitRange：RANGE [15:8]
        assert ctrl.fields["RANGE"].bit_offset == 8
        assert ctrl.fields["RANGE"].bit_width == 8

    def test_roundtrip_standardized(self, device):
        xml = SVDGenerator(device).generate(pretty_print=True)
        reparsed = SVDParser().parse_string(xml)
        ctrl = reparsed.peripherals["PERI"].registers["CTRL"]
        assert ctrl.fields["MODE"].bit_offset == 3
        assert ctrl.fields["MODE"].bit_width == 3
        assert ctrl.fields["RANGE"].bit_offset == 8
        assert ctrl.fields["RANGE"].bit_width == 8
        # 输出统一为 bitOffset/bitWidth 风格
        ctrl_block = xml.split("<name>CTRL</name>", 1)[1].split("</register>", 1)[0]
        assert "<bitOffset>3</bitOffset>" in ctrl_block
        assert "<lsb>" not in ctrl_block and "<bitRange>" not in ctrl_block


class TestModeledElements:
    """P1a：高频元素真建模（解析 + 生成 + 往返）"""

    def test_device_level(self, device):
        assert device.vendor_id == "TS"
        assert device.series == "T1000"
        assert device.license_text == "MIT license"
        assert device.header_system_filename == "test_system.h"
        assert device.header_definitions_prefix == "TS_"

    def test_peripheral_level(self, device):
        p = device.peripherals["PERI"]
        assert p.version == "1.1"
        assert p.prepend_to_name == "P_"
        assert p.append_to_name == "_REG"
        assert p.header_struct_name == "PERI_T"
        assert p.disable_condition == "(%s < 4)"

    def test_register_level(self, device):
        ctrl = device.peripherals["PERI"].registers["CTRL"]
        assert ctrl.alternate_group == "CFG"
        assert ctrl.alternate_register == ""
        stat_alt = device.peripherals["PERI"].registers["STAT_ALT"]
        assert stat_alt.alternate_register == "STAT"
        assert ctrl.data_type == "uint32_t"
        assert ctrl.modified_write_values == "oneToSet"
        assert ctrl.read_action == "clear"

    def test_field_level(self, device):
        ctrl = device.peripherals["PERI"].registers["CTRL"]
        assert ctrl.fields["MODE"].modified_write_values == "modify"
        assert ctrl.fields["RANGE"].read_action == "set"

    def test_roundtrip(self, device):
        xml = SVDGenerator(device).generate(pretty_print=True)
        for needle in ("<vendorID>TS</vendorID>", "<series>T1000</series>",
                       "<licenseText>MIT license</licenseText>",
                       "<headerSystemFilename>test_system.h</headerSystemFilename>",
                       "<headerDefinitionsPrefix>TS_</headerDefinitionsPrefix>",
                       "<prependToName>P_</prependToName>", "<appendToName>_REG</appendToName>",
                       "<headerStructName>PERI_T</headerStructName>",
                       "<alternateGroup>CFG</alternateGroup>",
                       "<alternateRegister>STAT</alternateRegister>",
                       "<dataType>uint32_t</dataType>",
                       "<modifiedWriteValues>oneToSet</modifiedWriteValues>",
                       "<readAction>clear</readAction>"):
            assert needle in xml, f"缺少: {needle}"

        reparsed = SVDParser().parse_string(xml)
        ctrl = reparsed.peripherals["PERI"].registers["CTRL"]
        assert ctrl.alternate_group == "CFG"
        assert ctrl.data_type == "uint32_t"
        assert ctrl.modified_write_values == "oneToSet"
        assert ctrl.fields["MODE"].modified_write_values == "modify"
        assert reparsed.vendor_id == "TS" and reparsed.series == "T1000"

    def test_element_order(self, device):
        xml = SVDGenerator(device).generate(pretty_print=True)
        dev_head = xml.split("<peripherals>", 1)[0]
        # 设备级规范顺序
        assert dev_head.index("<vendor>") < dev_head.index("<vendorID>") \
            < dev_head.index("<name>") < dev_head.index("<series>") \
            < dev_head.index("<version>") < dev_head.index("<description>")
        assert dev_head.index("<licenseText>") < dev_head.index("<cpu>") \
            < dev_head.index("<headerSystemFilename>") \
            < dev_head.index("<headerDefinitionsPrefix>") \
            < dev_head.index("<addressUnitBits>")
        # 寄存器级：description → alternateGroup → addressOffset
        ctrl_block = xml.split("<name>CTRL</name>", 1)[1].split("</register>", 1)[0]
        assert ctrl_block.index("<description>") < ctrl_block.index("<alternateGroup>") \
            < ctrl_block.index("<addressOffset>") < ctrl_block.index("<dataType>") \
            < ctrl_block.index("<modifiedWriteValues>") < ctrl_block.index("<readAction>")


class TestPassthrough:
    """P1b：未建模元素透传，往返不丢"""

    def test_register_write_constraint_and_protection(self, device):
        xml = SVDGenerator(device).generate(pretty_print=True)
        assert "<protection>s</protection>" in xml
        assert "<useEnumeratedValues>true</useEnumeratedValues>" in xml

    def test_field_write_constraint_range(self, device):
        xml = SVDGenerator(device).generate(pretty_print=True)
        compact = re.sub(r">\s+<", "><", xml)
        assert "<range><minimum>0</minimum><maximum>5</maximum></range>" in compact

    def test_dim_name_passthrough(self, device):
        xml = SVDGenerator(device).generate(pretty_print=True)
        assert "<dimName>BUF</dimName>" in xml

    def test_vendor_extensions(self, device):
        xml = SVDGenerator(device).generate(pretty_print=True)
        assert "<vendorExtensions>" in xml and "<TESTEXT>42</TESTEXT>" in xml

    def test_cpu_extension_flags(self, device):
        xml = SVDGenerator(device).generate(pretty_print=True)
        assert "<fpuDP>true</fpuDP>" in xml
        assert "<dspPresent>true</dspPresent>" in xml

    def test_double_roundtrip_stable(self, device):
        """透传内容二次往返仍稳定（第一次生成的输出再过一遍不膨胀）。"""
        xml1 = SVDGenerator(device).generate(pretty_print=True)
        dev2 = SVDParser().parse_string(xml1)
        xml2 = SVDGenerator(dev2).generate(pretty_print=True)
        assert xml2.count("<useEnumeratedValues>") == xml1.count("<useEnumeratedValues>")
        assert xml2.count("<TESTEXT>") == 1
        assert xml2.count("<fpuDP>") == 1


class TestValidatorAlignment:
    """P2：校验对齐 svdconv"""

    @staticmethod
    def _errors(device):
        v = SVDSchemaValidator()
        v.validate_all(device)
        return [i.message for i in v.get_errors()]

    @staticmethod
    def _warnings(device):
        v = SVDSchemaValidator()
        v.validate_all(device)
        return [i.message for i in v.get_warnings()]

    def test_irq_over_239(self, device):
        device.interrupts["BIG"] = Interrupt(name="BIG", value=250)
        errs = self._errors(device)
        assert any("239" in m for m in errs), errs

    def test_enum_missing_value_warns(self, device):
        stat = device.peripherals["PERI"].registers["STAT"]
        stat.fields["EN"].enumerated_values = [{"name": "OFF"}, {"name": "ON", "value": "1"}]
        warns = self._warnings(device)
        assert any("value" in m and "OFF" in m for m in warns), warns

    def test_enum_duplicate_value_errors(self, device):
        stat = device.peripherals["PERI"].registers["STAT"]
        stat.fields["EN"].enumerated_values = [
            {"name": "OFF", "value": "0"}, {"name": "ZERO", "value": "0"}]
        errs = self._errors(device)
        assert any("重复" in m for m in errs), errs

    def test_enum_overflow_errors(self, device):
        stat = device.peripherals["PERI"].registers["STAT"]
        stat.fields["EN"].enumerated_values = [{"name": "X", "value": "0x3"}]  # 1 位宽
        errs = self._errors(device)
        assert any("超出" in m for m in errs), errs

    def test_dim_without_placeholder(self, device):
        buf = device.peripherals["PERI"].registers["BUF[%s]"]
        buf.name = "BUF"
        device.peripherals["PERI"].registers = {"BUF": buf}
        errs = self._errors(device)
        assert any("%s" in m for m in errs), errs

    def test_dim_index_mismatch(self, device):
        device.peripherals["PERI"].registers["BUF[%s]"].dim_index = ["0", "1"]
        errs = self._errors(device)
        assert any("dimIndex" in m for m in errs), errs

    def test_dim_single_warns(self, device):
        device.peripherals["PERI"].registers["BUF[%s]"].dim = 1
        warns = self._warnings(device)
        assert any("dim=1" in m for m in warns), warns

    def test_invalid_c_identifier(self, device):
        p = device.peripherals["PERI"]
        p.registers["REG-A"] = Register(name="REG-A", offset="0x80")
        errs = self._errors(device)
        assert any("C 标识符" in m and "REG-A" in m for m in errs), errs

    def test_dim_placeholder_is_valid_identifier(self, device):
        errs = self._errors(device)
        assert not any("C 标识符" in m and "BUF" in m for m in errs), errs

    def test_alternate_register_self_reference(self, device):
        device.peripherals["PERI"].registers["STAT_ALT"].alternate_register = "STAT_ALT"
        errs = self._errors(device)
        assert any("alternateRegister" in m for m in errs), errs

    def test_alternate_register_missing(self, device):
        device.peripherals["PERI"].registers["STAT_ALT"].alternate_register = "GHOST"
        errs = self._errors(device)
        assert any("alternateRegister" in m for m in errs), errs

    def test_valid_fixture_has_no_new_check_errors(self, device):
        """对照组：规范合法的样例不触发新检查。"""
        errs = self._errors(device)
        assert not any("C 标识符" in m or "dimIndex" in m or "%s" in m
                       or "239" in m or "alternateRegister" in m for m in errs), errs


ENUM_SVD = """<?xml version="1.0" encoding="UTF-8"?>
<device schemaVersion="1.3">
  <name>TEST_ENUM</name>
  <version>1.0</version>
  <description>enum container coverage</description>
  <addressUnitBits>8</addressUnitBits>
  <width>32</width>
  <peripherals>
    <peripheral>
      <name>PERI</name>
      <description>Peripheral</description>
      <baseAddress>0x40000000</baseAddress>
      <addressBlock><offset>0x0</offset><size>0x10</size><usage>registers</usage></addressBlock>
      <registers>
        <register>
          <name>CFG</name>
          <description>Config</description>
          <addressOffset>0x0</addressOffset>
          <fields>
            <field>
              <name>MODE</name>
              <description>Mode</description>
              <bitOffset>0</bitOffset><bitWidth>2</bitWidth>
              <enumeratedValues>
                <name>MODE_Enum</name>
                <usage>read-write</usage>
                <enumeratedValue>
                  <name>OFF</name>
                  <description>Disabled</description>
                  <value>0</value>
                  <isDefault>true</isDefault>
                </enumeratedValue>
                <enumeratedValue>
                  <name>ON</name>
                  <description>Enabled</description>
                  <value>1</value>
                </enumeratedValue>
              </enumeratedValues>
              <enumeratedValues>
                <usage>read</usage>
                <enumeratedValue>
                  <name>R_OFF</name>
                  <value>0</value>
                </enumeratedValue>
              </enumeratedValues>
            </field>
          </fields>
        </register>
      </registers>
    </peripheral>
  </peripherals>
</device>
"""


class TestEnumeratedValues:
    """枚举值容器建模 + 多容器透传"""

    @pytest.fixture
    def enum_device(self):
        return SVDParser().parse_string(ENUM_SVD)

    def test_container_attrs_and_is_default(self, enum_device):
        fld = enum_device.peripherals["PERI"].registers["CFG"].fields["MODE"]
        assert fld.enumerated_values_name == "MODE_Enum"
        assert fld.enumerated_values_usage == "read-write"
        assert fld.enumerated_values[0]["name"] == "OFF"
        assert fld.enumerated_values[0]["is_default"] == "true"
        assert "is_default" not in fld.enumerated_values[1]
        # 第二个容器（usage=read）透传保留
        assert len(fld.extra_xml) == 1 and "<usage>read</usage>" in fld.extra_xml[0]

    def test_roundtrip(self, enum_device):
        import re as _re

        xml = SVDGenerator(enum_device).generate(pretty_print=True)
        compact = _re.sub(r">\s+<", "><", xml)
        for needle in ("<name>MODE_Enum</name>", "<usage>read-write</usage>",
                       "<isDefault>true</isDefault>"):
            assert needle in compact, f"缺少: {needle}"
        assert compact.count("<enumeratedValues>") == 2  # 建模 1 + 透传 1

        reparsed = SVDParser().parse_string(xml)
        fld = reparsed.peripherals["PERI"].registers["CFG"].fields["MODE"]
        assert fld.enumerated_values_name == "MODE_Enum"
        assert fld.enumerated_values[0]["is_default"] == "true"
        assert len(fld.extra_xml) == 1

        # 二次往返稳定（不膨胀）
        xml2 = SVDGenerator(reparsed).generate(pretty_print=True)
        compact2 = _re.sub(r">\s+<", "><", xml2)
        assert compact2.count("<enumeratedValues>") == 2
        assert compact2.count("<isDefault>") == 1

    def test_dict_roundtrip(self, enum_device):
        fld = enum_device.peripherals["PERI"].registers["CFG"].fields["MODE"]
        d = fld.to_dict()
        fld2 = Field.from_dict(d)
        assert fld2.enumerated_values_name == "MODE_Enum"
        assert fld2.enumerated_values_usage == "read-write"
        assert fld2.enumerated_values[0]["is_default"] == "true"
        assert len(fld2.extra_xml) == 1

    def test_mcp_get_field_exposes_enum(self, enum_device, tmp_path):
        from svd_tool.mcp_server.headless_workspace import HeadlessWorkspace

        svd_file = tmp_path / "enum.svd"
        svd_file.write_text(SVDGenerator(enum_device).generate(pretty_print=True),
                            encoding="utf-8")
        ws = HeadlessWorkspace()
        assert ws.open_document(str(svd_file))["success"]
        r = ws.get_field("PERI", "CFG", "MODE")
        assert r["success"]
        assert r["data"]["enumerated_values"][0]["is_default"] == "true"


class TestMcpSync:
    def test_update_register_and_field(self, device, tmp_path):
        from svd_tool.mcp_server.headless_workspace import HeadlessWorkspace

        svd_file = tmp_path / "spec.svd"
        svd_file.write_text(SVDGenerator(device).generate(pretty_print=True),
                            encoding="utf-8")
        ws = HeadlessWorkspace()
        assert ws.open_document(str(svd_file))["success"]

        r = ws.get_register("PERI", "CTRL")
        assert r["data"]["alternate_group"] == "CFG"
        assert r["data"]["read_action"] == "clear"

        # 改备选寄存器
        r = ws.update_register("PERI", "CTRL", {"alternate_register": "STAT"})
        assert r["success"], r["message"]
        assert ws.get_register("PERI", "CTRL")["data"]["alternate_register"] == "STAT"

        # 非法：不存在 / 自引用
        assert not ws.update_register("PERI", "CTRL", {"alternate_register": "GHOST"})["success"]
        assert not ws.update_register("PERI", "CTRL", {"alternate_register": "CTRL"})["success"]

        # 位域行为语义
        r = ws.update_field("PERI", "CTRL", "MODE", {"read_action": "clear"})
        assert r["success"]
        f = ws.get_field("PERI", "CTRL", "MODE")
        assert f["data"]["read_action"] == "clear"
        assert f["data"]["modified_write_values"] == "modify"

        # 保存往返后仍在
        out = tmp_path / "spec2.svd"
        assert ws.save_document(path=str(out))["success"]
        ws2 = HeadlessWorkspace()
        ws2.open_document(str(out))
        reg = ws2.get_register("PERI", "CTRL")
        assert reg["data"]["alternate_register"] == "STAT"
        fld = ws2.get_field("PERI", "CTRL", "MODE")
        assert fld["data"]["read_action"] == "clear"
