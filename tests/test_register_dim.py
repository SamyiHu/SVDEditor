"""
寄存器级 dim 属性支持测试。

验证 CMSIS-SVD 规范的 register dim/dimIncrement/dimIndex 三件套：
- 数据模型字段读写
- 解析器读取（含 dimIndex 范围语法 0-7）
- 生成器写出
- 完整往返（生成→解析→还原）
- 不带 dim 的寄存器不受影响（向后兼容）
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import copy
from svd_tool.core.data_model import DeviceInfo, Peripheral, Register, Field, CPUInfo
from svd_tool.core.svd_parser import SVDParser
from svd_tool.core.svd_generator import SVDGenerator


def _build_device_with_dim_reg():
    """构造一个带 dim 寄存器的设备。"""
    device = DeviceInfo(name='TEST_DIM', cpu=CPUInfo(name='CM4'))
    p = Peripheral(name='SPI0', base_address='0x40013000')
    # dim 寄存器数组：8 个 FIFO，每个间隔 4 字节
    reg = Register(
        name='TXBUF[%s]', offset='0x0', description='TX buffer',
        dim=8, dim_increment='0x4', dim_index=['0', '1', '2', '3', '4', '5', '6', '7'])
    reg.fields['TXE'] = Field(name='TXE', bit_offset=7, bit_width=1, description='empty')
    p.registers['TXBUF'] = reg
    # 普通寄存器（无 dim）
    p.registers['CTRL'] = Register(name='CTRL', offset='0x20', description='control')
    device.peripherals['SPI0'] = p
    return device


def test_data_model_dim_fields():
    """数据模型：dim 字段读写 + deepcopy。"""
    r = Register(name='A[%s]', offset='0x0', dim=4, dim_increment='0x8', dim_index=['0', '1', '2', '3'])
    d = r.to_dict()
    assert d['dim'] == 4
    assert d['dim_increment'] == '0x8'
    assert d['dim_index'] == ['0', '1', '2', '3']
    # from_dict 往返
    r2 = Register.from_dict(d)
    assert r2.dim == 4
    assert r2.dim_increment == '0x8'
    assert r2.dim_index == ['0', '1', '2', '3']
    # deepcopy
    r3 = copy.deepcopy(r)
    assert r3.dim == 4
    assert r3.dim_index == ['0', '1', '2', '3']
    # dim_index 是独立副本（改 r3 不影响 r）
    r3.dim_index.append('X')
    assert 'X' not in r.dim_index
    # 默认值
    r4 = Register(name='X', offset='0x0')
    assert r4.dim is None
    assert r4.dim_increment == '0x0'
    assert r4.dim_index == []
    print("✅ test_data_model_dim_fields passed")


def test_round_trip_generate_parse():
    """完整往返：生成 SVD → 重新解析 → dim 信息完整保留。"""
    device = _build_device_with_dim_reg()
    xml_str = SVDGenerator(device).generate()
    parsed = SVDParser().parse_string(xml_str)

    # dim 寄存器
    dim_reg = parsed.peripherals['SPI0'].registers['TXBUF[%s]']
    assert dim_reg.dim == 8, f"dim 应为 8，实际 {dim_reg.dim}"
    assert dim_reg.dim_increment == '0x4'
    assert dim_reg.dim_index == ['0', '1', '2', '3', '4', '5', '6', '7']
    assert dim_reg.name == 'TXBUF[%s]'

    # 普通寄存器（无 dim）
    ctrl = parsed.peripherals['SPI0'].registers['CTRL']
    assert ctrl.dim is None, f"CTRL 不应有 dim，实际 {ctrl.dim}"

    print("✅ test_round_trip_generate_parse passed")


def test_dimindex_range_syntax():
    """dimIndex 范围语法 '0-7' 自动展开为 0~7。"""
    svd = '''<?xml version="1.0" encoding="UTF-8"?>
<device schemaVersion="1.3">
  <name>TEST</name>
  <peripherals>
    <peripheral>
      <name>DMA</name>
      <baseAddress>0x40020000</baseAddress>
      <addressBlock><offset>0x0</offset><size>0x400</size><usage>registers</usage></addressBlock>
      <registers>
        <register>
          <name>CHANNEL[%s]</name>
          <dim>8</dim>
          <dimIncrement>0x20</dimIncrement>
          <dimIndex>0-7</dimIndex>
          <addressOffset>0x00</addressOffset>
          <size>0x20</size>
          <resetValue>0x00000000</resetValue>
        </register>
      </registers>
    </peripheral>
  </peripherals>
</device>'''
    device = SVDParser().parse_string(svd)
    reg = device.peripherals['DMA'].registers['CHANNEL[%s]']
    assert reg.dim == 8
    assert reg.dim_increment == '0x20'
    assert reg.dim_index == ['0', '1', '2', '3', '4', '5', '6', '7'], \
        f"范围语法展开错误: {reg.dim_index}"
    print("✅ test_dimindex_range_syntax passed")


def test_dimindex_comma_syntax():
    """dimIndex 逗号语法（自定义顺序，如 0,1,3,4,5,2）。"""
    svd = '''<?xml version="1.0" encoding="UTF-8"?>
<device schemaVersion="1.3">
  <name>TEST</name>
  <peripherals>
    <peripheral>
      <name>UART</name>
      <baseAddress>0x40013800</baseAddress>
      <addressBlock><offset>0x0</offset><size>0x100</size><usage>registers</usage></addressBlock>
      <registers>
        <register>
          <name>CFG[%s]</name>
          <dim>6</dim>
          <dimIncrement>0x400</dimIncrement>
          <dimIndex>0,1,3,4,5,2</dimIndex>
          <addressOffset>0x00</addressOffset>
          <resetValue>0x00000000</resetValue>
        </register>
      </registers>
    </peripheral>
  </peripherals>
</device>'''
    device = SVDParser().parse_string(svd)
    reg = device.peripherals['UART'].registers['CFG[%s]']
    assert reg.dim == 6
    assert reg.dim_index == ['0', '1', '3', '4', '5', '2'], \
        f"逗号语法应保留顺序: {reg.dim_index}"
    print("✅ test_dimindex_comma_syntax passed")


def test_backward_compat_no_dim():
    """不带 dim 的 SVD 文件不受影响（向后兼容）。"""
    svd = '''<?xml version="1.0" encoding="UTF-8"?>
<device schemaVersion="1.3">
  <name>OLD</name>
  <peripherals>
    <peripheral>
      <name>GPIO</name>
      <baseAddress>0x40010000</baseAddress>
      <addressBlock><offset>0x0</offset><size>0x40</size><usage>registers</usage></addressBlock>
      <registers>
        <register>
          <name>MODER</name>
          <addressOffset>0x00</addressOffset>
          <resetValue>0x00000000</resetValue>
        </register>
      </registers>
    </peripheral>
  </peripherals>
</device>'''
    device = SVDParser().parse_string(svd)
    reg = device.peripherals['GPIO'].registers['MODER']
    assert reg.dim is None
    assert reg.dim_index == []
    # 再生成，不应出现 dim 标签
    xml_out = SVDGenerator(device).generate()
    assert '<dim>' not in xml_out, "无 dim 寄存器不应生成 dim 标签"
    print("✅ test_backward_compat_no_dim passed")


if __name__ == "__main__":
    test_data_model_dim_fields()
    test_round_trip_generate_parse()
    test_dimindex_range_syntax()
    test_dimindex_comma_syntax()
    test_backward_compat_no_dim()
    print("\n🎉 寄存器级 dim 全部测试通过")
