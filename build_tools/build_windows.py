#!/usr/bin/env python3
"""
Windows平台打包脚本
支持32位和64位Windows可执行文件生成
"""

import os
import sys
import subprocess
import platform
import shutil
from pathlib import Path

def check_pyinstaller():
    """检查PyInstaller是否安装"""
    try:
        import PyInstaller
        print(f"PyInstaller版本: {PyInstaller.__version__}")
        return True
    except ImportError:
        print("错误: PyInstaller未安装，请运行: pip install pyinstaller")
        return False

def get_architecture():
    """获取当前Python架构"""
    arch = platform.architecture()[0]
    machine = platform.machine().lower()
    
    if arch == '32bit':
        return '32bit'
    elif arch == '64bit':
        return '64bit'
    else:
        # 根据机器类型判断
        if 'x86' in machine or 'i386' in machine or 'i686' in machine:
            return '32bit'
        elif 'x64' in machine or 'amd64' in machine or 'x86_64' in machine:
            return '64bit'
        elif 'arm' in machine:
            return 'ARM'
        else:
            return 'unknown'

def create_spec_file(arch, console=False):
    """创建PyInstaller spec文件"""
    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
import sys
sys.setrecursionlimit(5000)

block_cipher = None

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config.py', '.'),
        ('README.md', '.'),
        ('README_zh.md', '.'),
        ('LICENSE', '.'),
    ],
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtGui', 
        'PyQt6.QtWidgets',
        'xml.etree.ElementTree',
        'xml.dom.minidom',
        'collections',
        'collections.abc',
        'dataclasses',
        'typing',
        'logging',
        're',
        'copy',
        'sys',
        'os',
        'pathlib',
        'datetime',
        'enum',
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas', 'scipy', 'PyQt5', 'PySide2', 'PySide6'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SVDEditor_{arch}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console={console},
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico' if os.path.exists('icon.ico') else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='SVDEditor_{arch}',
)
'''
    
    spec_filename = f'svd_editor_{arch}.spec'
    with open(spec_filename, 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    return spec_filename

def build_for_architecture(arch, console=False):
    """为特定架构构建"""
    print(f"\n{'='*60}")
    print(f"构建 {arch} 版本")
    print(f"{'='*60}")
    
    # 创建spec文件
    spec_file = create_spec_file(arch, console)
    
    # 构建命令
    cmd = ['pyinstaller', '--clean', spec_file]
    
    print(f"执行命令: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("构建输出:")
        print(result.stdout)
        if result.stderr:
            print("错误输出:")
            print(result.stderr)
        
        # 检查输出目录
        dist_dir = Path('dist') / f'SVDEditor_{arch}'
        if dist_dir.exists():
            print(f"\n构建成功！输出目录: {dist_dir}")
            
            # 创建ZIP压缩包
            zip_name = f'SVDEditor_{arch}.zip'
            shutil.make_archive(f'SVDEditor_{arch}', 'zip', 'dist', f'SVDEditor_{arch}')
            print(f"已创建压缩包: {zip_name}")
            
            return True
        else:
            print(f"\n错误: 输出目录不存在: {dist_dir}")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"\n构建失败，退出码: {e.returncode}")
        print(f"错误输出: {e.stderr}")
        return False
    except Exception as e:
        print(f"\n构建过程中发生异常: {e}")
        return False

def main():
    """主函数"""
    print("SVD Editor Windows打包工具")
    print("="*60)
    
    # 检查PyInstaller
    if not check_pyinstaller():
        sys.exit(1)
    
    # 获取当前架构
    current_arch = get_architecture()
    print(f"当前系统架构: {current_arch}")
    
    # 询问构建选项
    print("\n构建选项:")
    print("1. 构建当前架构版本 (自动检测)")
    print("2. 构建32位版本 (需要32位Python)")
    print("3. 构建64位版本 (需要64位Python)")
    print("4. 构建所有可用版本")
    print("5. 构建调试版本 (显示控制台)")
    
    choice = input("\n请选择 (1-5): ").strip()
    
    # 清理之前的构建
    if os.path.exists('build'):
        shutil.rmtree('build')
    if os.path.exists('dist'):
        shutil.rmtree('dist')
    
    success = False
    
    if choice == '1':
        # 构建当前架构
        success = build_for_architecture(current_arch)
        
    elif choice == '2':
        # 构建32位版本
        if current_arch != '32bit':
            print("警告: 当前Python不是32位，构建可能失败")
            confirm = input("继续构建? (y/n): ").lower()
            if confirm != 'y':
                return
        success = build_for_architecture('32bit')
        
    elif choice == '3':
        # 构建64位版本
        if current_arch != '64bit':
            print("警告: 当前Python不是64位，构建可能失败")
            confirm = input("继续构建? (y/n): ").lower()
            if confirm != 'y':
                return
        success = build_for_architecture('64bit')
        
    elif choice == '4':
        # 构建所有版本
        successes = []
        if current_arch == '32bit' or input("构建32位版本? (y/n): ").lower() == 'y':
            successes.append(build_for_architecture('32bit'))
        
        if current_arch == '64bit' or input("构建64位版本? (y/n): ").lower() == 'y':
            successes.append(build_for_architecture('64bit'))
        
        success = all(successes)
        
    elif choice == '5':
        # 构建调试版本
        debug_arch = input(f"构建架构 ({current_arch}): ").strip() or current_arch
        success = build_for_architecture(debug_arch, console=True)
        
    else:
        print("无效选择")
        return
    
    # 清理临时文件
    spec_files = [f for f in os.listdir('.') if f.endswith('.spec')]
    for spec_file in spec_files:
        try:
            os.remove(spec_file)
        except:
            pass
    
    if success:
        print(f"\n{'='*60}")
        print("构建完成！")
        print(f"{'='*60}")
        print("\n输出文件:")
        for item in os.listdir('.'):
            if item.endswith('.zip'):
                print(f"  - {item}")
        
        dist_dir = Path('dist')
        if dist_dir.exists():
            for item in dist_dir.iterdir():
                if item.is_dir():
                    print(f"  - dist/{item.name}/")
    else:
        print("\n构建失败，请检查错误信息")

if __name__ == '__main__':
    main()