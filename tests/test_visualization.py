#!/usr/bin/env python3
"""
测试可视化控件导入和实例化
"""
import sys
import traceback
sys.path.insert(0, '.')

from PyQt6.QtWidgets import QApplication

app = QApplication(sys.argv)

try:
    from svd_tool.ui.widgets.visualization_widget import VisualizationWidget
    print('导入成功')
    widget = VisualizationWidget()
    print(f'实例创建成功: {widget}')
    print(f'address_map: {widget.address_map}')
    print(f'bit_field: {widget.bit_field}')
except Exception as e:
    print(f'异常: {e}')
    traceback.print_exc()

# 测试AddressMapWidget和BitFieldWidget
try:
    from svd_tool.ui.widgets.address_map_widget import AddressMapWidget
    from svd_tool.ui.widgets.bit_field_widget import BitFieldWidget
    print('AddressMapWidget和BitFieldWidget导入成功')
    am = AddressMapWidget()
    bf = BitFieldWidget()
    print(f'AddressMapWidget实例: {am}')
    print(f'BitFieldWidget实例: {bf}')
except Exception as e:
    print(f'子部件导入异常: {e}')
    traceback.print_exc()

app.quit()