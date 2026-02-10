"""
测试国际化功能
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from svd_tool.i18n.i18n import I18nManager, get_i18n_manager, set_i18n_manager, t

def test_i18n():
    """测试国际化功能"""
    print("=== 测试国际化功能 ===")
    
    # 测试中文
    print("\n1. 测试中文:")
    i18n_zh = I18nManager("zh_CN")
    set_i18n_manager(i18n_zh)
    print(f"   menu.file: {t('menu.file')}")
    print(f"   msg.save_success: {t('msg.save_success')}")
    print(f"   msg.select_peripheral_first: {t('msg.select_peripheral_first')}")
    
    # 测试英文
    print("\n2. 测试英文:")
    i18n_en = I18nManager("en_US")
    set_i18n_manager(i18n_en)
    print(f"   menu.file: {t('menu.file')}")
    print(f"   msg.save_success: {t('msg.save_success')}")
    print(f"   msg.select_peripheral_first: {t('msg.select_peripheral_first')}")
    
    # 测试参数替换
    print("\n3. 测试参数替换:")
    set_i18n_manager(i18n_zh)
    print(f"   msg.register_not_exist: {t('msg.register_not_exist', name='TEST_REG')}")
    print(f"   msg.data_validation_failed: {t('msg.data_validation_failed', count=5)}")
    
    set_i18n_manager(i18n_en)
    print(f"   msg.register_not_exist: {t('msg.register_not_exist', name='TEST_REG')}")
    print(f"   msg.data_validation_failed: {t('msg.data_validation_failed', count=5)}")
    
    # 测试不存在的键
    print("\n4. 测试不存在的键:")
    result = t('non.existent.key')
    print(f"   non.existent.key: {result}")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_i18n()
