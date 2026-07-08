"""
核心层单元测试 — ChipToSvdConverter 与 SVDVerifier。

不依赖外部 Parser 包，用轻量 stub 对象模拟 ChipData 结构
（只需具备同名字段即可，因为转换器用 getattr 访问）。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from svd_tool.core.data_model import DeviceInfo, Peripheral, Register, Field
from svd_tool.core.datasource.chip_to_svd_converter import ChipToSvdConverter
from svd_tool.core.datasource.svd_verifier import SVDVerifier, VerifyKind, VerifySeverity


# ════════════════════════════════════════════════════
# 轻量 stub（模拟 parser.models 的结构）
# ════════════════════════════════════════════════════

class StubBitField:
    def __init__(self, name, bit_pos, bit_width=1, access="RW", description="", confidence="high", enum_values=None):
        self.name = name
        self.bit_pos = bit_pos
        self.bit_width = bit_width
        self.access = access
        self.description = description
        self.confidence = confidence
        self.enum_values = enum_values or {}


class StubRegister:
    def __init__(self, name, address_offset="0x00", absolute_address="", reset_value="0x00000000", description="", confidence="high", fields=None):
        self.name = name
        self.address_offset = address_offset
        self.absolute_address = absolute_address
        self.reset_value = reset_value
        self.description = description
        self.confidence = confidence
        self.fields = fields or []


class StubPeripheralBlock:
    def __init__(self, name, base_address="0x40000000", bus="APB1", description="", registers=None):
        self.name = name
        self.base_address = base_address
        self.bus = bus
        self.description = description
        self.registers = registers or []


class StubChipData:
    def __init__(self, chip_name="TEST_MCU", core="Cortex-M0+", peripherals=None, interrupts=None):
        self.chip_name = chip_name
        self.core = core
        self.peripherals = peripherals or []
        self.interrupts = interrupts or []


# ════════════════════════════════════════════════════
# ChipToSvdConverter 测试
# ════════════════════════════════════════════════════

def test_basic_conversion():
    """基础转换：外设/寄存器/位域正确映射。"""
    chip = StubChipData(
        chip_name="W1251",
        core="Cortex-M0+",
        peripherals=[
            StubPeripheralBlock(
                name="GPIOA", base_address="0x40010000", bus="AHB",
                registers=[
                    StubRegister(
                        name="GPIO_MODER", address_offset="0x00", reset_value="0x00000000",
                        fields=[
                            StubBitField("MODE0", bit_pos=0, bit_width=2, access="RW"),
                            StubBitField("MODE1", bit_pos=2, bit_width=2, access="RW"),
                        ]),
                    StubRegister(
                        name="GPIO_ODR", address_offset="0x04", reset_value="0x000000FF",
                        fields=[StubBitField("OD0", bit_pos=0, access="RW")]),
                ]),
        ])

    converter = ChipToSvdConverter()
    device, report = converter.convert(chip)

    assert device.name == "W1251"
    assert device.cpu.name == "CM0+"
    assert "GPIOA" in device.peripherals
    periph = device.peripherals["GPIOA"]
    assert periph.base_address == "0x40010000"
    assert periph.group_name == "AHB"
    assert "GPIO_MODER" in periph.registers
    reg = periph.registers["GPIO_MODER"]
    assert reg.offset == "0x0"
    assert "MODE0" in reg.fields
    assert reg.fields["MODE0"].bit_offset == 0
    assert reg.fields["MODE0"].bit_width == 2
    assert reg.fields["MODE0"].access == "read-write"
    print("✅ test_basic_conversion passed")


def test_offset_inferred_from_absolute_address():
    """offset 缺失时由 absolute_address - base_address 推算。"""
    chip = StubChipData(
        peripherals=[
            StubPeripheralBlock(
                name="UART0", base_address="0x40011000",
                registers=[
                    StubRegister(name="UART_DR", address_offset="", absolute_address="0x40011004"),
                ]),
        ])
    converter = ChipToSvdConverter()
    device, report = converter.convert(chip)

    reg = device.peripherals["UART0"].registers["UART_DR"]
    assert reg.offset == "0x4", f"expected 0x4, got {reg.offset}"
    # 应有 offset_inferred 记录
    inferred = [i for i in report.issues if i.kind == "offset_inferred"]
    assert not inferred, "已用 absolute_address 推算，不应记 offset_inferred"
    print("✅ test_offset_inferred_from_absolute_address passed")


def test_offset_completely_missing():
    """offset 和 absolute_address 都缺失 → 置 0x0 并记 warning。"""
    chip = StubChipData(
        peripherals=[
            StubPeripheralBlock(
                name="SPI0", base_address="0x40013000",
                registers=[StubRegister(name="SPI_CR", address_offset="", absolute_address="")]),
        ])
    converter = ChipToSvdConverter()
    device, report = converter.convert(chip)

    reg = device.peripherals["SPI0"].registers["SPI_CR"]
    assert reg.offset == "0x0"
    inferred = [i for i in report.issues if i.kind == "offset_inferred"]
    assert len(inferred) == 1
    assert inferred[0].severity == "warning"
    print("✅ test_offset_completely_missing passed")


def test_access_enum_translation():
    """RW/RO/WO → read-write/read-only/write-only。"""
    chip = StubChipData(
        peripherals=[
            StubPeripheralBlock(name="T1", registers=[
                StubRegister(name="R1", fields=[
                    StubBitField("F_RW", bit_pos=0, access="RW"),
                    StubBitField("F_RO", bit_pos=1, access="RO"),
                    StubBitField("F_WO", bit_pos=2, access="WO"),
                ]),
            ]),
        ])
    converter = ChipToSvdConverter()
    device, _ = converter.convert(chip)
    fields = device.peripherals["T1"].registers["R1"].fields
    assert fields["F_RW"].access == "read-write"
    assert fields["F_RO"].access == "read-only"
    assert fields["F_WO"].access == "write-only"
    print("✅ test_access_enum_translation passed")


def test_enum_values_conversion():
    """enum_values dict → SVD list[{name,value,description}]。"""
    chip = StubChipData(
        peripherals=[
            StubPeripheralBlock(name="T1", registers=[
                StubRegister(name="R1", fields=[
                    StubBitField("MODE", bit_pos=0, bit_width=2,
                                 enum_values={"0": "input", "1": "output", "2": "alternate"}),
                ]),
            ]),
        ])
    converter = ChipToSvdConverter()
    device, _ = converter.convert(chip)
    f = device.peripherals["T1"].registers["R1"].fields["MODE"]
    assert len(f.enumerated_values) == 3
    ev0 = f.enumerated_values[0]
    assert ev0["value"] == "0"
    assert ev0["description"] == "input"
    assert "INPUT" in ev0["name"] or "0" in ev0["name"]
    print("✅ test_enum_values_conversion passed")


def test_merge_mode_skips_existing_peripheral():
    """并入模式：已存在的外设被跳过，不覆盖。"""
    target = DeviceInfo(name="EXISTING")
    target.peripherals["GPIOA"] = Peripheral(name="GPIOA", base_address="0xDEADBEEF")

    chip = StubChipData(
        peripherals=[
            StubPeripheralBlock(name="GPIOA", base_address="0x40010000"),
            StubPeripheralBlock(name="GPIOB", base_address="0x40010400"),
        ])
    converter = ChipToSvdConverter()
    device, report = converter.convert(chip, target=target, merge=True)

    # GPIOA 保持原样
    assert device.peripherals["GPIOA"].base_address == "0xDEADBEEF"
    # GPIOB 加入
    assert "GPIOB" in device.peripherals
    # 报告记录跳过
    skipped = [i for i in report.issues if i.kind == "skipped_peripheral"]
    assert any(i.peripheral == "GPIOA" for i in skipped)
    assert report.peripherals_skipped == 1
    assert report.peripherals_added == 1
    print("✅ test_merge_mode_skips_existing_peripheral passed")


def test_core_name_normalization():
    """Cortex-M0+ → CM0+，Cortex-M4 → CM4（带 FPU）。"""
    for raw, expected, fpu in [("Cortex-M0+", "CM0+", False),
                               ("cortex-m4", "CM4", True),
                               ("Cortex-M3", "CM3", False)]:
        chip = StubChipData(chip_name="X", core=raw)
        device, _ = ChipToSvdConverter().convert(chip)
        assert device.cpu.name == expected, f"{raw} → {device.cpu.name}"
        assert device.cpu.fpu_present == fpu
    print("✅ test_core_name_normalization passed")


def test_round_trip_via_from_dict():
    """转换结果能被 DeviceInfo.from_dict 往返（与 cmd_create 同款约定）。"""
    chip = StubChipData(
        peripherals=[
            StubPeripheralBlock(name="P1", base_address="0x40000000", registers=[
                StubRegister(name="R1", address_offset="0x0", fields=[
                    StubBitField("F1", bit_pos=0)])]),
        ])
    converter = ChipToSvdConverter()
    device, _ = converter.convert(chip)
    d = device.to_dict()
    restored = DeviceInfo.from_dict(d)
    assert "P1" in restored.peripherals
    assert "R1" in restored.peripherals["P1"].registers
    assert "F1" in restored.peripherals["P1"].registers["R1"].fields
    print("✅ test_round_trip_via_from_dict passed")


# ════════════════════════════════════════════════════
# SVDVerifier 测试
# ════════════════════════════════════════════════════

def _build_svd_device():
    """构造一个完整的 DeviceInfo 供核对。"""
    device = DeviceInfo(name="M1")
    device.peripherals["GPIOA"] = Peripheral(
        name="GPIOA", base_address="0x40010000",
        registers={
            "GPIO_MODER": Register(
                name="GPIO_MODER", offset="0x0", reset_value="0x00000000",
                fields={
                    "MODE0": Field(name="MODE0", bit_offset=0, bit_width=2, access="read-write"),
                }),
            "GPIO_ODR": Register(name="GPIO_ODR", offset="0x04", reset_value="0x000000FF"),
        })
    return device


def test_verify_no_diff():
    """完全一致 → 无差异项。"""
    device = _build_svd_device()
    chip = StubChipData(peripherals=[
        StubPeripheralBlock(name="GPIOA", base_address="0x40010000", registers=[
            StubRegister(name="GPIO_MODER", address_offset="0x0", reset_value="0x00000000",
                         fields=[StubBitField("MODE0", bit_pos=0, bit_width=2, access="RW")]),
            StubRegister(name="GPIO_ODR", address_offset="0x04", reset_value="0x000000FF"),
        ])])
    items = SVDVerifier().verify(device, chip)
    assert items == [], f"expected no diff, got {len(items)}: {[i.detail for i in items]}"
    print("✅ test_verify_no_diff passed")


def test_verify_missing_peripheral_in_svd():
    """源有外设、SVD 无 → PERIPH_MISSING_IN_SVD error。"""
    device = _build_svd_device()
    chip = StubChipData(peripherals=[
        StubPeripheralBlock(name="GPIOA", base_address="0x40010000"),
        StubPeripheralBlock(name="GPIOZ", base_address="0x40090000"),  # SVD 没有
    ])
    items = SVDVerifier().verify(device, chip)
    missing = [i for i in items if i.kind == VerifyKind.PERIPH_MISSING_IN_SVD.value]
    assert len(missing) == 1
    assert missing[0].peripheral == "GPIOZ"
    assert missing[0].severity == VerifySeverity.ERROR.value
    print("✅ test_verify_missing_peripheral_in_svd passed")


def test_verify_register_missing_in_svd():
    """源有寄存器、SVD 无 → REG_MISSING_IN_SVD warning。"""
    device = _build_svd_device()
    chip = StubChipData(peripherals=[
        StubPeripheralBlock(name="GPIOA", base_address="0x40010000", registers=[
            StubRegister(name="GPIO_MODER", address_offset="0x0"),
            StubRegister(name="GPIO_NEWREG", address_offset="0x10", confidence="high"),  # SVD 没有
        ])])
    items = SVDVerifier().verify(device, chip)
    missing = [i for i in items if i.kind == VerifyKind.REG_MISSING_IN_SVD.value]
    assert len(missing) == 1
    assert missing[0].register == "GPIO_NEWREG"
    assert missing[0].severity == "error"  # high confidence → error
    assert missing[0].suggested["offset"] == "0x10"
    print("✅ test_verify_register_missing_in_svd passed")


def test_verify_offset_mismatch():
    """寄存器偏移不符 → OFFSET_MISMATCH。"""
    device = _build_svd_device()
    chip = StubChipData(peripherals=[
        StubPeripheralBlock(name="GPIOA", base_address="0x40010000", registers=[
            StubRegister(name="GPIO_MODER", address_offset="0x08"),  # SVD 是 0x0
        ])])
    items = SVDVerifier().verify(device, chip)
    offset_diff = [i for i in items if i.kind == VerifyKind.OFFSET_MISMATCH.value]
    assert len(offset_diff) == 1
    assert offset_diff[0].svd_value == "0x0"
    assert offset_diff[0].source_value == "0x8"
    assert offset_diff[0].suggested["offset"] == "0x8"
    print("✅ test_verify_offset_mismatch passed")


def test_verify_low_confidence_demoted_to_warning():
    """低置信度的 mismatch 降为 warning（可能源错）。"""
    device = _build_svd_device()
    chip = StubChipData(peripherals=[
        StubPeripheralBlock(name="GPIOA", base_address="0x40010000", registers=[
            StubRegister(name="GPIO_MODER", address_offset="0x08", confidence="low"),  # 低置信度
        ])])
    items = SVDVerifier().verify(device, chip)
    offset_diff = [i for i in items if i.kind == VerifyKind.OFFSET_MISMATCH.value]
    assert len(offset_diff) == 1
    assert offset_diff[0].severity == "warning"  # low → warning 而非 error
    print("✅ test_verify_low_confidence_demoted_to_warning passed")


def test_verify_field_alignment_by_bit_pos():
    """位域名不同但位号相同 → 不报 missing（位号是最稳定主键）。"""
    device = _build_svd_device()
    chip = StubChipData(peripherals=[
        StubPeripheralBlock(name="GPIOA", base_address="0x40010000", registers=[
            StubRegister(name="GPIO_MODER", address_offset="0x0", fields=[
                StubBitField("MODE_0", bit_pos=0, bit_width=2, access="RW"),  # 名不同但 bit[0:1]
            ]),
        ])])
    items = SVDVerifier().verify(device, chip)
    missing = [i for i in items if i.kind == VerifyKind.FIELD_MISSING_IN_SVD.value]
    assert missing == [], f"位号相同不应报缺失: {[i.detail for i in missing]}"
    print("✅ test_verify_field_alignment_by_bit_pos passed")


def test_verify_width_mismatch():
    """位宽不符 → WIDTH_MISMATCH。"""
    device = _build_svd_device()
    chip = StubChipData(peripherals=[
        StubPeripheralBlock(name="GPIOA", base_address="0x40010000", registers=[
            StubRegister(name="GPIO_MODER", address_offset="0x0", fields=[
                StubBitField("MODE0", bit_pos=0, bit_width=4, access="RW"),  # SVD 是 2
            ]),
        ])])
    items = SVDVerifier().verify(device, chip)
    width = [i for i in items if i.kind == VerifyKind.WIDTH_MISMATCH.value]
    assert len(width) == 1
    assert width[0].svd_value == "2"
    assert width[0].source_value == "4"
    print("✅ test_verify_width_mismatch passed")


def test_verify_access_mismatch():
    """访问权限不符 → ACCESS_MISMATCH。"""
    device = _build_svd_device()
    chip = StubChipData(peripherals=[
        StubPeripheralBlock(name="GPIOA", base_address="0x40010000", registers=[
            StubRegister(name="GPIO_MODER", address_offset="0x0", fields=[
                StubBitField("MODE0", bit_pos=0, bit_width=2, access="RO"),  # SVD 是 read-write
            ]),
        ])])
    items = SVDVerifier().verify(device, chip)
    access = [i for i in items if i.kind == VerifyKind.ACCESS_MISMATCH.value]
    assert len(access) == 1
    assert access[0].suggested["access"] == "read-only"
    print("✅ test_verify_access_mismatch passed")


if __name__ == "__main__":
    test_basic_conversion()
    test_offset_inferred_from_absolute_address()
    test_offset_completely_missing()
    test_access_enum_translation()
    test_enum_values_conversion()
    test_merge_mode_skips_existing_peripheral()
    test_core_name_normalization()
    test_round_trip_via_from_dict()
    test_verify_no_diff()
    test_verify_missing_peripheral_in_svd()
    test_verify_register_missing_in_svd()
    test_verify_offset_mismatch()
    test_verify_low_confidence_demoted_to_warning()
    test_verify_field_alignment_by_bit_pos()
    test_verify_width_mismatch()
    test_verify_access_mismatch()
    print("\n🎉 全部核心层测试通过")
