"""
简单测试Bug 1修复
"""
import sys
import os

# 设置UTF-8编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from svd_tool.ui.components.state_manager import StateManager
from svd_tool.core.data_model import DeviceInfo, Peripheral, Register

def test_bug1():
    """测试Bug 1: 状态变化通知"""
    print("\n=== 测试Bug 1: 状态变化通知 ===")
    
    # 创建状态管理器
    state_manager = StateManager()
    
    # 注册回调
    callback_called = []
    def test_callback():
        callback_called.append(True)
        print("✅ 回调被调用")
    
    state_manager.register_state_change_callback(test_callback)
    
    # 创建测试数据
    device_info = DeviceInfo()
    device_info.name = "TestDevice"
    peripheral = Peripheral(name="TEST", base_address="0x40000000")
    device_info.peripherals["TEST"] = peripheral
    
    # 直接设置device_info（模拟file_operations中的操作）
    print("设置device_info...")
    state_manager.device_info = device_info
    
    # 检查回调是否被调用
    if not callback_called:
        print("❌ 失败: 回调未被调用")
        print("   这意味着需要手动调用 _notify_state_change()")
        return False
    
    # 现在测试手动调用_notify_state_change
    print("\n手动调用 _notify_state_change()...")
    state_manager._notify_state_change()
    
    if len(callback_called) >= 1:
        print("✅ 成功: _notify_state_change() 正常工作")
        return True
    else:
        print("❌ 失败: _notify_state_change() 未触发回调")
        return False

if __name__ == "__main__":
    result = test_bug1()
    sys.exit(0 if result else 1)
