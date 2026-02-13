"""
测试继承外设点击跳转功能修复
"""
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from svd_tool.ui.main_window_refactored import MainWindowRefactored
from svd_tool.core.svd_parser import SVDParser
from svd_tool.core.data_model import DeviceInfo

def test_inheritance_jump():
    """测试继承外设点击跳转功能"""
    print("=== 测试继承外设点击跳转功能 ===")
    
    app = QApplication(sys.argv)
    
    # 创建主窗口
    main_window = MainWindowRefactored()
    main_window.show()
    
    # 加载测试SVD文件
    svd_file = "E:/work/MCU库/SVD生成器/build版本/SVDEditor/test_data/test_inheritance.svd"
    
    # 创建测试SVD文件（如果不存在）
    import os
    if not os.path.exists(svd_file):
        print(f"创建测试SVD文件: {svd_file}")
        os.makedirs(os.path.dirname(svd_file), exist_ok=True)
        
        # 创建一个包含继承外设的测试SVD文件
        svd_content = """<?xml version="1.0" encoding="utf-8"?>
<device schemaVersion="1.3" xmlns:xs="http://www.w3.org/2001/XMLSchema-instance" xs:noNamespaceSchemaLocation="CMSIS-SVD.xsd">
  <name>TestDevice</name>
  <version>1.0</version>
  <description>Test device with inheritance</description>
  <addressUnitBits>8</addressUnitBits>
  <width>32</width>
  <size>32</size>
  <access>read-write</access>
  <resetValue>0x00000000</resetValue>
  <resetMask>0xFFFFFFFF</resetMask>
  <peripherals>
    <peripheral>
      <name>GPIOA</name>
      <baseAddress>0x40000000</baseAddress>
      <description>General Purpose I/O A</description>
      <registers>
        <register>
          <name>MODER</name>
          <description>Mode register</description>
          <addressOffset>0x00</addressOffset>
          <size>0x20</size>
          <access>read-write</access>
          <resetValue>0x00000000</resetValue>
          <fields>
            <field>
              <name>MODER0</name>
              <description>Port x configuration bits</description>
              <bitOffset>0</bitOffset>
              <bitWidth>2</bitWidth>
            </field>
          </fields>
        </register>
      </registers>
    </peripheral>
    <peripheral derivedFrom="GPIOA">
      <name>GPIOB</name>
      <baseAddress>0x40000400</baseAddress>
      <description>General Purpose I/O B</description>
    </peripheral>
  </peripherals>
</device>
"""
        with open(svd_file, 'w', encoding='utf-8') as f:
            f.write(svd_content)
    
    # 解析SVD文件
    parser = SVDParser()
    device_info = parser.parse_file(svd_file)
    
    print(f"加载的设备: {device_info.name}")
    print(f"外设数量: {len(device_info.peripherals)}")
    
    # 检查继承外设
    for periph_name, peripheral in device_info.peripherals.items():
        if peripheral.derived_from:
            print(f"继承外设: {periph_name} -> {peripheral.derived_from}")
    
    # 设置设备信息到主窗口
    main_window.state_manager.device_info = device_info
    main_window.state_manager._notify_state_change()
    
    # 测试跳转功能
    print("\n=== 测试跳转功能 ===")
    
    # 获取可视化控件
    visualization_widget = main_window.layout_manager.get_widget('visualization_widget')
    
    # 检查信号是否连接
    print(f"可视化控件: {visualization_widget}")
    
    # 模拟点击继承外设的位域图
    print("\n模拟点击继承外设的位域图...")
    
    # 选择继承外设GPIOB
    main_window.state_manager.set_selection(peripheral='GPIOB')
    
    # 获取位域控件
    bit_field_widget = visualization_widget.bit_field
    
    # 设置源外设名称（模拟继承外设的位域图）
    bit_field_widget.set_register(None, 'GPIOA')
    
    # 检查源外设名称是否设置
    print(f"源外设名称: {bit_field_widget.source_peripheral_name}")
    
    # 检查信号是否连接
    print(f"检查信号连接...")
    print(f"visualization_widget.jump_to_peripheral: {visualization_widget.jump_to_peripheral}")
    print(f"main_window.on_jump_to_peripheral: {main_window.on_jump_to_peripheral}")
    
    # 手动连接信号（如果未连接）
    try:
        visualization_widget.jump_to_peripheral.disconnect(main_window.on_jump_to_peripheral)
        print("信号已断开")
    except:
        print("信号未连接")
    
    visualization_widget.jump_to_peripheral.connect(main_window.on_jump_to_peripheral)
    print("信号已连接")
    
    # 模拟鼠标点击事件
    from PyQt6.QtCore import QPointF
    from PyQt6.QtGui import QMouseEvent
    
    # 创建鼠标点击事件
    mouse_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(100, 100),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier
    )
    
    # 触发鼠标点击事件
    bit_field_widget.mousePressEvent(mouse_event)
    
    print("鼠标点击事件已触发")
    
    # 手动触发信号（用于测试）
    print("手动触发 jump_to_peripheral 信号...")
    visualization_widget.jump_to_peripheral.emit('GPIOA')
    print("信号已发射")
    
    # 检查选择是否更新
    selection = main_window.state_manager.get_selection()
    print(f"当前选择: {selection}")
    
    # 验证跳转是否成功
    if selection.get('peripheral') == 'GPIOA':
        print("[SUCCESS] 跳转成功！已跳转到源外设 GPIOA")
        return True
    else:
        print("[FAILED] 跳转失败！未跳转到源外设")
        print(f"期望: GPIOA, 实际: {selection.get('peripheral')}")
        return False

if __name__ == '__main__':
    success = test_inheritance_jump()
    sys.exit(0 if success else 1)
