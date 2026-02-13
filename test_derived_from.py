"""测试derived_from属性是否被正确设置"""
import sys
from svd_tool.core.svd_parser import SVDParser

# 解析SVD文件
parser = SVDParser()
device_info = parser.parse_file("E:/work/MCU库/SVD生成器/build版本/SVDEditor/test_data/test_inheritance.svd")

# 检查所有外设的derived_from属性
print("=== 检查所有外设的derived_from属性 ===")
for periph_name, periph in device_info.peripherals.items():
    derived_from = periph.derived_from
    print(f"外设: {periph_name}, derived_from: '{derived_from}' (类型: {type(derived_from)}, 真值: {bool(derived_from)})")
