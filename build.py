#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SVD Editor Build Script / SVD Editor 构建脚本
Python version with UTF-8 support / Python版本，支持UTF-8编码
"""

import os
import sys
import subprocess
from pathlib import Path

# Set UTF-8 encoding for Windows console / 为Windows控制台设置UTF-8编码
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

def print_bilingual(zh_text, en_text):
    """Print bilingual text / 打印双语文本"""
    print(f"{zh_text} / {en_text}")

def run_build_script(script_name, args=None):
    """Run build script / 运行构建脚本"""
    script_path = Path(__file__).parent / "build_tools" / script_name
    if not script_path.exists():
        print_bilingual(f"错误: 找不到构建脚本 {script_name}", f"Error: Build script not found {script_name}")
        return False
    
    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)
    
    try:
        result = subprocess.run(
            cmd,
            cwd=Path(__file__).parent / "build_tools",
            check=True
        )
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print_bilingual(f"构建失败，退出码: {e.returncode}", f"Build failed, exit code: {e.returncode}")
        return False
    except Exception as e:
        print_bilingual(f"构建过程中发生异常: {e}", f"Exception during build: {e}")
        return False

def main():
    """Main function / 主函数"""
    print_bilingual("SVD Editor 构建工具", "SVD Editor Build Tool")
    print("="*60)
    print_bilingual("解决报毒问题和目录结构不美观问题", "Solves false positive virus detection and directory structure issues")
    print()

    print_bilingual("请选择构建脚本:", "Please select build script:")
    print()
    print("1. Professional build (recommended) / 专业构建（推荐）")
    print_bilingual("   - 支持32位和64位架构选择", "   - Supports 32-bit and 64-bit architecture selection")
    print_bilingual("   - 更好的杀毒软件兼容性", "   - Better antivirus software compatibility")
    print_bilingual("   - 整洁的目录结构", "   - Clean directory structure")
    print()
    print("2. Basic Windows build / 基础Windows构建")
    print_bilingual("   - 简单的32位/64位选择", "   - Simple 32-bit/64-bit selection")
    print_bilingual("   - 传统PyInstaller方式", "   - Traditional PyInstaller method")
    print()
    print("="*60)
    print()

    script_choice = input("您想运行哪个构建脚本？(1 或 2) / Which build script would you like to run? (1 or 2): ").strip()

    if script_choice == '1':
        print_bilingual("\n运行专业构建脚本...", "\nRunning professional build script...")
        print()
        success = run_build_script("build_professional_fixed.py")
    elif script_choice == '2':
        print_bilingual("\n运行基础Windows构建脚本...", "\nRunning basic Windows build script...")
        print()
        success = run_build_script("build_windows.py")
    else:
        print_bilingual("\n无效选择。请手动运行:", "\nInvalid choice. Please run manually:")
        print("  cd build_tools")
        print("  python build_professional_fixed.py")
        print_bilingual("  或", "  or")
        print("  cd build_tools")
        print("  python build_windows.py")
        input("\n按回车键退出... / Press Enter to exit...")
        return

    if success:
        print_bilingual("\n构建完成！", "\nBuild completed!")
    else:
        print_bilingual("\n构建失败，请检查错误信息", "\nBuild failed, please check error messages")

    input("\n按回车键退出... / Press Enter to exit...")

if __name__ == '__main__':
    main()
