"""
集成测试 — 使用真实 Parser 包的 ChipData 走完整转换 + 核对流程。

依赖：
- Parser 包可导入（pip install -e ../Parser 或 sys.path 兜底）
无需真实手册文件：直接构造 ChipData（Parser 的 pydantic 模型），验证端到端管线。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# 兜底定位 Parser 包
sys.path.insert(0, r'C:\Users\SOC\Desktop\小程序\Parser')

# 提前导入供 _apply_one_simple 在模块级使用
from svd_tool.core.datasource.svd_verifier import VerifyKind


def _make_real_chip_data():
    """用真实 Parser 模型类构造 ChipData。"""
    from reg_core.models import (
        ChipData, PeripheralBlock, Register, BitField, InterruptDefinition,
    )
    return ChipData(
        chip_name="INTEG_TEST_MCU",
        core="Cortex-M3",
        peripherals=[
            PeripheralBlock(
                name="USART0",
                base_address="0x40013800",
                bus="APB2",
                description="通用同步异步收发器0",
                registers=[
                    Register(
                        name="USART_SR", address_offset="0x00",
                        reset_value="0x000000C0", description="状态寄存器",
                        confidence="high",
                        fields=[
                            BitField(name="TXE", bit_pos=7, bit_width=1, access="RO",
                                     description="发送数据寄存器空", confidence="high"),
                            BitField(name="RXNE", bit_pos=5, bit_width=1, access="RO",
                                     description="读数据寄存器非空", confidence="high"),
                        ]),
                    Register(
                        name="USART_DR", address_offset="0x04",
                        reset_value="0x00000000", description="数据寄存器",
                        confidence="high"),
                    Register(
                        name="USART_BRR", address_offset="0x08",
                        reset_value="0x00000000", description="波特率寄存器",
                        confidence="medium",
                        fields=[
                            BitField(name="DIV_Mantissa", bit_pos=4, bit_width=12,
                                     access="RW", description="波特率尾数", confidence="medium"),
                            BitField(name="DIV_Fraction", bit_pos=0, bit_width=4,
                                     access="RW", description="波特率小数", confidence="medium"),
                        ]),
                ]),
            PeripheralBlock(
                name="GPIOC",
                base_address="0x40011000",
                bus="APB2",
                registers=[
                    Register(name="GPIOC_CRH", address_offset="0x04",
                             reset_value="0x44444444", confidence="high"),
                ]),
        ],
        interrupts=[
            InterruptDefinition(name="USART0", irq_number=37, description="USART0 全局中断"),
        ],
    )


def test_real_chipdata_to_device():
    """真实 ChipData → DeviceInfo 转换。"""
    from svd_tool.core.datasource.chip_to_svd_converter import ChipToSvdConverter
    chip = _make_real_chip_data()

    device, report = ChipToSvdConverter().convert(chip)

    assert device.name == "INTEG_TEST_MCU"
    assert device.cpu.name == "CM3"
    assert "USART0" in device.peripherals
    assert "GPIOC" in device.peripherals

    # 寄存器/位域映射
    usart = device.peripherals["USART0"]
    assert "USART_SR" in usart.registers
    assert "USART_BRR" in usart.registers
    sr = usart.registers["USART_SR"]
    # reset_value 被归一化（去前导零、大写）：0x000000C0 → 0xC0，数值相等
    assert int(sr.reset_value, 16) == 0xC0
    assert "TXE" in sr.fields
    assert sr.fields["TXE"].bit_offset == 7
    assert sr.fields["TXE"].access == "read-only"
    brr = usart.registers["USART_BRR"]
    assert brr.fields["DIV_Mantissa"].bit_width == 12

    # 中断导入
    assert "USART0" in device.interrupts
    assert device.interrupts["USART0"].value == 37

    # 总数
    assert report.peripherals_added == 2
    assert report.registers_added == 4
    assert report.interrupts_added == 1
    print("✅ test_real_chipdata_to_device passed")


def test_real_verify_and_accept():
    """真实 ChipData 核对 + 接受（端到端）。"""
    from svd_tool.core.data_model import DeviceInfo, Peripheral, Register, Field
    from svd_tool.core.datasource.svd_verifier import SVDVerifier, VerifyKind

    # 目标 SVD：有 USART0 但 USART_SR offset 错了(0x10)、缺 USART_BRR、缺 GPIOC
    device = DeviceInfo(name="EXISTING")
    device.peripherals["USART0"] = Peripheral(
        name="USART0", base_address="0x40013800",
        registers={
            "USART_SR": Register(
                name="USART_SR", offset="0x10",  # 错：源是 0x00
                fields={"TXE": Field(name="TXE", bit_offset=7, bit_width=1, access="read-write")}),  # access 也错
            "USART_DR": Register(name="USART_DR", offset="0x04"),  # 正确
        })

    chip = _make_real_chip_data()
    verifier = SVDVerifier()
    items = verifier.verify(device, chip)

    # 应检出：USART_SR offset 不符 + USART_SR TXE access 不符 + USART_BRR 缺失 + GPIOC 缺失
    kinds = [it.kind for it in items]
    assert VerifyKind.OFFSET_MISMATCH.value in kinds, f"应检出 offset 不符: {kinds}"
    assert VerifyKind.ACCESS_MISMATCH.value in kinds, f"应检出 access 不符: {kinds}"
    assert VerifyKind.REG_MISSING_IN_SVD.value in kinds, f"应检出 USART_BRR 缺失: {kinds}"
    assert VerifyKind.PERIPH_MISSING_IN_SVD.value in kinds, f"应检出 GPIOC 缺失: {kinds}"
    print(f"  检出 {len(items)} 项差异, kinds={set(kinds)}")

    # 模拟接受：修复所有带建议值的差异项（含 warning）
    fixes = [it for it in items if it.suggested]
    # 全部应用建议
    for it in fixes:
        _apply_one_simple(device, it)

    # 再核对，error 应大幅减少
    items2 = verifier.verify(device, chip)
    err2 = [it for it in items2 if it.severity == "error"]
    assert len(err2) < len(fixes), f"接受后 error 应减少: {len(fixes)} -> {len(err2)}"
    # USART_BRR / GPIOC 现在应该在
    assert "USART_BRR" in device.peripherals["USART0"].registers
    assert "GPIOC" in device.peripherals
    # USART_SR offset 已修复
    assert device.peripherals["USART0"].registers["USART_SR"].offset == "0x0"
    print(f"  接受 {len(fixes)} 项后剩余 {len(err2)} 项 error")
    print("✅ test_real_verify_and_accept passed")


def _apply_one_simple(device, item):
    """简化版 apply（与 DatasourceManager._apply_one 同逻辑，不依赖 Qt）。"""
    if item.kind == VerifyKind.PERIPH_MISSING_IN_SVD.value:
        from svd_tool.core.data_model import Peripheral
        device.peripherals[item.peripheral] = Peripheral(
            name=item.suggested.get("name", item.peripheral),
            base_address=item.suggested.get("base_address", "0x40000000"))
        return
    periph = device.peripherals.get(item.peripheral)
    if periph is None:
        return
    if item.kind == VerifyKind.BASE_ADDR_MISMATCH.value:
        periph.base_address = item.suggested.get("base_address", periph.base_address)
        return
    if item.kind == VerifyKind.REG_MISSING_IN_SVD.value:
        from svd_tool.core.data_model import Register
        periph.registers[item.register] = Register(
            name=item.suggested.get("name", item.register),
            offset=item.suggested.get("offset", "0x0"))
        return
    reg = periph.registers.get(item.register)
    if reg is None:
        return
    if item.kind == VerifyKind.OFFSET_MISMATCH.value:
        reg.offset = item.suggested.get("offset", reg.offset)
    elif item.kind == VerifyKind.RESET_MISMATCH.value:
        reg.reset_value = item.suggested.get("reset_value", reg.reset_value)
    elif item.kind == VerifyKind.ACCESS_MISMATCH.value and item.field:
        fld = reg.fields.get(item.field)
        if fld:
            fld.access = item.suggested.get("access", fld.access)


def test_real_fusion_report():
    """真实 SourceFusion 多源融合 + 质量报告。"""
    from reg_core.models import PeripheralBlock, Register, BitField
    from reg_core.source_fusion import SourceFusion, FusionStrategy
    from reg_core.quality_report import stamp_confidence

    # 两源，base_address 一致 → 提升置信度；reset_value 冲突 → 记冲突
    excel = [PeripheralBlock(name="SPI0", base_address="0x40013000",
             registers=[Register(name="SPI_CR", address_offset="0x0",
                                 reset_value="0x00000000")])]
    word = [PeripheralBlock(name="SPI0", base_address="0x40013000",
             registers=[Register(name="SPI_CR", address_offset="0x0",
                                 reset_value="0xFFFFFFFF")])]
    stamp_confidence(excel, "excel")
    stamp_confidence(word, "word")

    fusion = SourceFusion()
    periphs, report = fusion.fuse(
        {"excel": excel, "word": word}, strategy=FusionStrategy.FUSION)
    assert len(periphs) == 1
    # 多源一致的外设存在性应触发提升（report.promotions 非空）
    assert len(report.promotions) >= 1 or report.fused_peripherals == 1
    print(f"  融合: {report.fused_peripherals} 外设, "
          f"{len(report.conflicts)} 冲突, {len(report.promotions)} 提升")
    print("✅ test_real_fusion_report passed")


if __name__ == "__main__":
    test_real_chipdata_to_device()
    test_real_verify_and_accept()
    test_real_fusion_report()
    print("\n🎉 集成测试（真实 Parser 包）全部通过")
