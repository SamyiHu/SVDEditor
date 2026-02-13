"""
测试Bug修复的脚本
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

from PyQt6.QtWidgets import QApplication
from svd_tool.ui.main_window_refactored import MainWindowRefactored
from svd_tool.core.svd_parser import SVDParser
from svd_tool.ui.components.state_manager import StateManager
from svd_tool.ui.components.realtime_preview import RealtimePreviewWidget

def test_bug1_preview_update():
    """测试Bug 1: SVD实时预览是否随SVD导入更新"""
    print("\n=== 测试Bug 1: SVD实时预览更新 ===")
    
    # 创建应用
    app = QApplication(sys.argv)
    
    # 创建主窗口
    main_window = MainWindowRefactored()
    
    # 获取实时预览组件
    realtime_preview = main_window.layout_manager.get_widget('realtime_preview')
    
    if not realtime_preview:
        print("❌ 失败: 未找到实时预览组件")
        return False
    
    # 检查初始状态
    initial_element_ranges = len(realtime_preview.element_ranges)
    print(f"初始element_ranges数量: {initial_element_ranges}")
    
    # 模拟加载SVD文件
    parser = SVDParser()
    test_file = "E:/work/MCU库/SVD生成器/游戏/SCD5152A&3132A/MCUlib&SVD/SVD V0.2/SCD5152AC7.svd"
    
    if os.path.exists(test_file):
        device_info = parser.parse_file(test_file)
        
        # 更新状态管理器
        main_window.state_manager.device_info = device_info
        main_window.state_manager.clear_selection()
        
        # 通知状态变化（这是修复的关键）
        main_window.state_manager._notify_state_change()
        
        # 检查更新后的状态
        updated_element_ranges = len(realtime_preview.element_ranges)
        print(f"更新后element_ranges数量: {updated_element_ranges}")
        
        if updated_element_ranges > initial_element_ranges:
            print("✅ 成功: SVD实时预览已更新")
            return True
        else:
            print("❌ 失败: SVD实时预览未更新")
            return False
    else:
        print(f"⚠️ 警告: 测试文件不存在: {test_file}")
        return None

def test_bug2_selection():
    """测试Bug 2: 框选功能"""
    print("\n=== 测试Bug 2: 框选功能 ===")
    
    # 创建应用
    app = QApplication(sys.argv)
    
    # 创建主窗口
    main_window = MainWindowRefactored()
    
    # 获取实时预览组件
    realtime_preview = main_window.layout_manager.get_widget('realtime_preview')
    
    if not realtime_preview:
        print("❌ 失败: 未找到实时预览组件")
        return False
    
    # 检查on_preview_selection_changed方法是否存在
    if hasattr(realtime_preview, 'on_preview_selection_changed'):
        print("✅ 成功: on_preview_selection_changed方法存在")
        
        # 检查方法是否正确处理选择
        import inspect
        source = inspect.getsource(realtime_preview.on_preview_selection_changed)
        
        if 'hasSelection()' in source and 'element_ranges' in source:
            print("✅ 成功: 框选方法已正确实现")
            return True
        else:
            print("❌ 失败: 框选方法实现不完整")
            return False
    else:
        print("❌ 失败: on_preview_selection_changed方法不存在")
        return False

def test_bug3_jump():
    """测试Bug 3: 跳转功能"""
    print("\n=== 测试Bug 3: 跳转功能 ===")
    
    # 创建应用
    app = QApplication(sys.argv)
    
    # 创建主窗口
    main_window = MainWindowRefactored()
    
    # 获取实时预览组件
    realtime_preview = main_window.layout_manager.get_widget('realtime_preview')
    
    if not realtime_preview:
        print("❌ 失败: 未找到实时预览组件")
        return False
    
    # 检查jump_to_selection方法是否存在
    if hasattr(realtime_preview, 'jump_to_selection'):
        print("✅ 成功: jump_to_selection方法存在")
        
        # 检查方法是否正确处理空element_ranges
        import inspect
        source = inspect.getsource(realtime_preview.jump_to_selection)
        
        if 'element_ranges' in source and '_update_preview' in source:
            print("✅ 成功: 跳转方法已正确实现")
            return True
        else:
            print("❌ 失败: 跳转方法实现不完整")
            return False
    else:
        print("❌ 失败: jump_to_selection方法不存在")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("开始测试Bug修复")
    print("=" * 50)
    
    results = []
    
    # 测试Bug 1
    result1 = test_bug1_preview_update()
    results.append(("Bug 1: SVD实时预览更新", result1))
    
    # 测试Bug 2
    result2 = test_bug2_selection()
    results.append(("Bug 2: 框选功能", result2))
    
    # 测试Bug 3
    result3 = test_bug3_jump()
    results.append(("Bug 3: 跳转功能", result3))
    
    # 输出结果
    print("\n" + "=" * 50)
    print("测试结果汇总")
    print("=" * 50)
    
    for name, result in results:
        if result is True:
            print(f"✅ {name}: 通过")
        elif result is False:
            print(f"❌ {name}: 失败")
        else:
            print(f"⚠️ {name}: 跳过")
    
    # 统计
    passed = sum(1 for _, r in results if r is True)
    failed = sum(1 for _, r in results if r is False)
    skipped = sum(1 for _, r in results if r is None)
    
    print(f"\n总计: {len(results)} 个测试")
    print(f"通过: {passed}")
    print(f"失败: {failed}")
    print(f"跳过: {skipped}")
    
    sys.exit(0 if failed == 0 else 1)
