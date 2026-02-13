"""
分块加载功能测试
测试块管理器、分块解析器和分块生成器的功能
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from svd_tool.core.chunked_svd_parser import ChunkedSVDParser
from svd_tool.core.chunked_svd_generator import ChunkedSVDGenerator
from svd_tool.core.block_manager import BlockManager, BlockType
from svd_tool.core.data_model import DeviceInfo, Peripheral, Register, Field


def create_test_svd():
    """创建测试用的SVD XML"""
    svd_xml = """<?xml version="1.0" encoding="utf-8"?>
<device schemaVersion="1.3" xmlns:xs="http://www.w3.org/2001/XMLSchema-instance" xs:noNamespaceSchemaLocation="CMSIS-SVD_Schema_1_3.xsd">
  <name>TestDevice</name>
  <version>1.0</version>
  <description>Test Device for Chunked Loading</description>
  <cpu>
    <name>CM0+</name>
    <revision>r0p1</revision>
    <endian>little</endian>
    <mpuPresent>true</mpuPresent>
    <fpuPresent>false</fpuPresent>
    <nvicPrioBits>4</nvicPrioBits>
    <vendorSystickConfig>false</vendorSystickConfig>
  </cpu>
  <addressUnitBits>8</addressUnitBits>
  <width>32</width>
  <size>32</size>
  <resetValue>0x00000000</resetValue>
  <resetMask>0xFFFFFFFF</resetMask>
  <peripherals>
    <peripheral>
      <name>GPIOA</name>
      <baseAddress>0x40000000</baseAddress>
      <description>General Purpose I/O A</description>
      <groupName>GPIO</groupName>
      <addressBlock>
        <offset>0x0</offset>
        <size>0x400</size>
        <usage>registers</usage>
      </addressBlock>
      <registers>
        <register>
          <name>MODER</name>
          <addressOffset>0x00</addressOffset>
          <description>Mode register</description>
          <size>32</size>
          <access>read-write</access>
          <resetValue>0x00000000</resetValue>
          <resetMask>0xFFFFFFFF</resetMask>
          <fields>
            <field>
              <name>MODER0</name>
              <description>Port x configuration bits</description>
              <bitOffset>0</bitOffset>
              <bitWidth>2</bitWidth>
              <access>read-write</access>
              <resetValue>0x0</resetValue>
            </field>
            <field>
              <name>MODER1</name>
              <description>Port x configuration bits</description>
              <bitOffset>2</bitOffset>
              <bitWidth>2</bitWidth>
              <access>read-write</access>
              <resetValue>0x0</resetValue>
            </field>
          </fields>
        </register>
        <register>
          <name>ODR</name>
          <addressOffset>0x14</addressOffset>
          <description>Output data register</description>
          <size>32</size>
          <access>read-write</access>
          <resetValue>0x00000000</resetValue>
          <resetMask>0xFFFFFFFF</resetMask>
          <fields>
            <field>
              <name>ODR0</name>
              <description>Port output data</description>
              <bitOffset>0</bitOffset>
              <bitWidth>1</bitWidth>
              <access>read-write</access>
              <resetValue>0x0</resetValue>
            </field>
          </fields>
        </register>
      </registers>
    </peripheral>
    <peripheral>
      <name>GPIOB</name>
      <baseAddress>0x40000400</baseAddress>
      <description>General Purpose I/O B</description>
      <groupName>GPIO</groupName>
      <addressBlock>
        <offset>0x0</offset>
        <size>0x400</size>
        <usage>registers</usage>
      </addressBlock>
      <registers>
        <register>
          <name>MODER</name>
          <addressOffset>0x00</addressOffset>
          <description>Mode register</description>
          <size>32</size>
          <access>read-write</access>
          <resetValue>0x00000000</resetValue>
          <resetMask>0xFFFFFFFF</resetMask>
          <fields>
            <field>
              <name>MODER0</name>
              <description>Port x configuration bits</description>
              <bitOffset>0</bitOffset>
              <bitWidth>2</bitWidth>
              <access>read-write</access>
              <resetValue>0x0</resetValue>
            </field>
          </fields>
        </register>
      </registers>
    </peripheral>
  </peripherals>
</device>
"""
    return svd_xml


def test_chunked_parser():
    """测试分块解析器"""
    print("=" * 60)
    print("测试分块解析器")
    print("=" * 60)
    
    # 创建测试SVD
    svd_xml = create_test_svd()
    
    # 创建分块解析器
    parser = ChunkedSVDParser()
    
    # 解析SVD
    device_info, block_manager = parser.parse_string(svd_xml)
    
    # 验证解析结果
    print(f"设备名称: {device_info.name}")
    print(f"设备版本: {device_info.version}")
    print(f"外设数量: {len(device_info.peripherals)}")
    
    # 验证块管理器
    stats = block_manager.get_statistics()
    print(f"\n块统计:")
    print(f"  总块数: {stats['total_blocks']}")
    print(f"  已加载块数: {stats['loaded_blocks']}")
    print(f"  可见块数: {stats['visible_blocks']}")
    print(f"  已加载外设: {stats['loaded_peripherals']}")
    print(f"  已加载寄存器: {stats['loaded_registers']}")
    print(f"  已加载位域: {stats['loaded_fields']}")
    
    # 验证块结构
    print(f"\n块结构:")
    for block_key, block in block_manager.blocks.items():
        print(f"  {block_key}: {block.display_name} ({block.block_type.value})")
    
    print("\n[OK] 分块解析器测试通过")
    return device_info, block_manager


def test_block_manager(device_info: DeviceInfo):
    """测试块管理器"""
    print("\n" + "=" * 60)
    print("测试块管理器")
    print("=" * 60)
    
    # 创建块管理器
    block_manager = BlockManager(device_info)
    
    # 测试加载外设
    print("\n测试加载外设:")
    block_manager.load_peripheral("GPIOA")
    stats = block_manager.get_statistics()
    print(f"  加载GPIOA后: 已加载外设={stats['loaded_peripherals']}, 已加载寄存器={stats['loaded_registers']}")
    
    # 测试加载寄存器
    print("\n测试加载寄存器:")
    block_manager.load_register("GPIOA", "MODER")
    stats = block_manager.get_statistics()
    print(f"  加载MODER后: 已加载寄存器={stats['loaded_registers']}, 已加载位域={stats['loaded_fields']}")
    
    # 测试加载位域
    print("\n测试加载位域:")
    block_manager.load_field("GPIOA", "MODER", "MODER0")
    stats = block_manager.get_statistics()
    print(f"  加载MODER0后: 已加载位域={stats['loaded_fields']}")
    
    # 测试导航
    print("\n测试导航:")
    block = block_manager.navigate_to("peripheral:GPIOA")
    print(f"  导航到GPIOA: {block.display_name}")
    
    block = block_manager.navigate_to("register:GPIOA:MODER")
    print(f"  导航到MODER: {block.display_name}")
    
    block = block_manager.navigate_to("field:GPIOA:MODER:MODER0")
    print(f"  导航到MODER0: {block.display_name}")
    
    # 测试获取相邻块
    print("\n测试获取相邻块:")
    current_block = block_manager.get_block("register:GPIOA:MODER")
    next_block = block_manager.get_next_block("register:GPIOA:MODER")
    prev_block = block_manager.get_previous_block("register:GPIOA:MODER")
    print(f"  当前块: {current_block.display_name}")
    print(f"  下一个块: {next_block.display_name if next_block else 'None'}")
    print(f"  上一个块: {prev_block.display_name if prev_block else 'None'}")
    
    print("\n[OK] 块管理器测试通过")
    return block_manager


def test_chunked_generator(device_info: DeviceInfo, block_manager: BlockManager):
    """测试分块生成器"""
    print("\n" + "=" * 60)
    print("测试分块生成器")
    print("=" * 60)
    
    # 创建分块生成器
    generator = ChunkedSVDGenerator(device_info, block_manager)
    
    # 测试生成设备头部
    print("\n测试生成设备头部:")
    device_header = generator.generate_device_header()
    print(f"  设备头部长度: {len(device_header)} 字符")
    print(f"  前100字符: {device_header[:100]}...")
    
    # 测试生成外设块
    print("\n测试生成外设块:")
    peripheral_xml = generator.generate_peripheral_block("GPIOA")
    print(f"  GPIOA块长度: {len(peripheral_xml)} 字符")
    print(f"  包含MODER: {'<name>MODER</name>' in peripheral_xml}")
    
    # 测试生成寄存器块
    print("\n测试生成寄存器块:")
    register_xml = generator.generate_register_block("GPIOA", "MODER")
    print(f"  MODER块长度: {len(register_xml)} 字符")
    print(f"  包含MODER0: {'<name>MODER0</name>' in register_xml}")
    
    # 测试生成位域块
    print("\n测试生成位域块:")
    field_xml = generator.generate_field_block("GPIOA", "MODER", "MODER0")
    print(f"  MODER0块长度: {len(field_xml)} 字符")
    print(f"  包含bitOffset: {'<bitOffset>0</bitOffset>' in field_xml}")
    
    # 测试生成可见块
    print("\n测试生成可见块:")
    block_manager.set_visible("peripheral:GPIOA", True)
    block_manager.set_visible("register:GPIOA:MODER", True)
    visible_xml = generator.generate_visible_blocks()
    print(f"  可见块XML长度: {len(visible_xml)} 字符")
    print(f"  包含GPIOA: {'<name>GPIOA</name>' in visible_xml}")
    print(f"  包含MODER: {'<name>MODER</name>' in visible_xml}")
    
    # 测试按key生成
    print("\n测试按key生成:")
    block_keys = ["peripheral:GPIOA", "register:GPIOA:MODER"]
    keys_xml = generator.generate_blocks_by_keys(block_keys)
    print(f"  按key生成XML长度: {len(keys_xml)} 字符")
    print(f"  包含GPIOA: {'<name>GPIOA</name>' in keys_xml}")
    print(f"  包含MODER: {'<name>MODER</name>' in keys_xml}")
    
    print("\n[OK] 分块生成器测试通过")


def test_integration():
    """集成测试"""
    print("\n" + "=" * 60)
    print("集成测试")
    print("=" * 60)
    
    # 创建测试SVD
    svd_xml = create_test_svd()
    
    # 解析SVD
    parser = ChunkedSVDParser()
    device_info, block_manager = parser.parse_string(svd_xml)
    
    # 创建生成器
    generator = ChunkedSVDGenerator(device_info, block_manager)
    
    # 模拟用户操作流程
    print("\n模拟用户操作流程:")
    
    # 1. 用户打开文件，只显示设备信息
    print("\n1. 用户打开文件，只显示设备信息")
    device_header = generator.generate_device_header()
    print(f"   生成长度: {len(device_header)} 字符")
    
    # 2. 用户展开GPIOA外设
    print("\n2. 用户展开GPIOA外设")
    block_manager.load_peripheral("GPIOA")
    block_manager.set_visible("peripheral:GPIOA", True)
    visible_xml = generator.generate_visible_blocks()
    print(f"   生成长度: {len(visible_xml)} 字符")
    print(f"   包含GPIOA: {'<name>GPIOA</name>' in visible_xml}")
    
    # 3. 用户展开MODER寄存器
    print("\n3. 用户展开MODER寄存器")
    block_manager.load_register("GPIOA", "MODER")
    block_manager.set_visible("register:GPIOA:MODER", True)
    visible_xml = generator.generate_visible_blocks()
    print(f"   生成长度: {len(visible_xml)} 字符")
    print(f"   包含MODER: {'<name>MODER</name>' in visible_xml}")
    
    # 4. 用户点击MODER0位域
    print("\n4. 用户点击MODER0位域")
    block_manager.load_field("GPIOA", "MODER", "MODER0")
    block_manager.set_visible("field:GPIOA:MODER:MODER0", True)
    visible_xml = generator.generate_visible_blocks()
    print(f"   生成长度: {len(visible_xml)} 字符")
    print(f"   包含MODER0: {'<name>MODER0</name>' in visible_xml}")
    
    # 5. 用户导航到下一个块
    print("\n5. 用户导航到下一个块")
    next_block = block_manager.get_next_block("field:GPIOA:MODER:MODER0")
    if next_block:
        print(f"   下一个块: {next_block.display_name}")
    
    # 6. 用户导航到上一个块
    print("\n6. 用户导航到上一个块")
    prev_block = block_manager.get_previous_block("field:GPIOA:MODER:MODER0")
    if prev_block:
        print(f"   上一个块: {prev_block.display_name}")
    
    print("\n[OK] 集成测试通过")


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("分块加载功能测试")
    print("=" * 60)
    
    try:
        # 测试分块解析器
        device_info, block_manager = test_chunked_parser()
        
        # 测试块管理器
        block_manager = test_block_manager(device_info)
        
        # 测试分块生成器
        test_chunked_generator(device_info, block_manager)
        
        # 集成测试
        test_integration()
        
        print("\n" + "=" * 60)
        print("所有测试通过！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[FAIL] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
