# -*- coding: utf-8 -*-
"""验证bug修复结果"""
import sys
import os

# 设置输出编码为UTF-8
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

from svd_tool.core.svd_parser import SVDParser
from svd_tool.ui.widgets.bit_field_widget import BitFieldWidget
from PyQt6.QtWidgets import QApplication

# 创建QApplication实例
app = QApplication(sys.argv)

# 解析SVD文件
parser = SVDParser()
device_info = parser.parse_file("E:/work/MCU库/SVD生成器/build版本/SVDEditor/test_data/test_inheritance.svd")

# 创建BitFieldWidget实例
bit_field_widget = BitFieldWidget()

# 测试1：非继承外设不应该显示继承信息
print("=== Test 1: Non-inherited peripheral should not show inheritance info ===")
gpioa = device_info.peripherals['GPIOA']
print(f"GPIOA derived_from: '{gpioa.derived_from}' (truth value: {bool(gpioa.derived_from)})")

# 模拟调用set_register，传递空字符串作为source_peripheral_name
bit_field_widget.set_register(None, "")
print(f"BitFieldWidget.source_peripheral_name: {bit_field_widget.source_peripheral_name}")
if bit_field_widget.source_peripheral_name is None:
    print("[PASS] Bug1 fixed: Empty string does not update source_peripheral_name")
else:
    print(f"[FAIL] Bug1 not fixed: source_peripheral_name is {bit_field_widget.source_peripheral_name}")

# 测试2：继承外设应该显示继承信息
print("\n=== Test 2: Inherited peripheral should show inheritance info ===")
gpiob = device_info.peripherals['GPIOB']
print(f"GPIOB derived_from: '{gpiob.derived_from}' (truth value: {bool(gpiob.derived_from)})")

# 模拟调用set_register，传递非空字符串作为source_peripheral_name
bit_field_widget.set_register(None, "GPIOA")
print(f"BitFieldWidget.source_peripheral_name: '{bit_field_widget.source_peripheral_name}'")
if bit_field_widget.source_peripheral_name == "GPIOA":
    print("[PASS] Inherited peripheral correctly shows inheritance info")
else:
    print("[FAIL] Inherited peripheral does not correctly show inheritance info")

# 测试3：验证derived_from属性
print("\n=== Test 3: Verify derived_from attribute ===")
for periph_name, periph in device_info.peripherals.items():
    derived_from = periph.derived_from
    print(f"Peripheral: {periph_name}, derived_from: '{derived_from}' (type: {type(derived_from)}, truth value: {bool(derived_from)})")

print("\n=== Tests completed ===")
