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
    
    # 首先选择版本类型
    print_bilingual("请选择版本类型:", "Please select version type:")
    print()
    print("1. 单文件版本 / Single-file version")
    print_bilingual("   - 单个.exe文件，所有依赖打包在一起", "   - Single .exe file with all dependencies packaged together")
    print_bilingual("   - 适合分发和便携使用", "   - Suitable for distribution and portable use")
    print()
    print("2. 目录版本 / Directory version")
    print_bilingual("   - 包含.exe和依赖文件的文件夹", "   - Folder containing .exe and dependency files")
    print_bilingual("   - 适合调试和查看", "   - Suitable for debugging and viewing")
    print()
    print("3. 所有版本 / All versions")
    print_bilingual("   - 同时构建单文件和目录版本", "   - Build both single-file and directory versions")
    print()
    print("="*60)
    print()
    
    version_choice = input("请选择版本类型 (1-3) / Please select version type (1-3): ").strip()
    
    # 确定构建参数
    build_args = []
    if version_choice == '1':
        build_args = ['--onefile']
        print_bilingual("\n已选择: 单文件版本", "\nSelected: Single-file version")
    elif version_choice == '2':
        build_args = ['--onedir']
        print_bilingual("\n已选择: 目录版本", "\nSelected: Directory version")
    elif version_choice == '3':
        build_args = ['--all']
        print_bilingual("\n已选择: 所有版本", "\nSelected: All versions")
    else:
        print_bilingual("\n无效选择，默认使用单文件版本", "\nInvalid choice, defaulting to single-file version")
        build_args = ['--onefile']
    
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
        print_bilingual("注意: 此脚本将询问架构选择 (32位/64位)", "Note: This script will ask for architecture selection (32-bit/64-bit)")
        print()
        success = run_build_script("build_professional_fixed.py", build_args)
    elif script_choice == '2':
        print_bilingual("\n运行基础Windows构建脚本...", "\nRunning basic Windows build script...")
        print_bilingual("注意: 此脚本将询问架构选择 (32位/64位)", "Note: This script will ask for architecture selection (32-bit/64-bit)")
        print()
        success = run_build_script("build_windows.py", build_args)
    else:
        print_bilingual("\n无效选择。请手动运行:", "\nInvalid choice. Please run manually:")
        print("  cd build_tools")
        print("  python build_professional_fixed.py")
        print_bilingual("  或", "  or")
        print("  cd build_tools")
        print("  python build_windows.py")
        return
    
    if success:
        print_bilingual("\n构建完成！", "\nBuild completed!")
    else:
        print_bilingual("\n构建失败，请检查错误信息", "\nBuild failed, please check error messages")

if __name__ == '__main__':
    main()
