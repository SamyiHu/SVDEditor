#!/usr/bin/env python3
"""
专业构建脚本 - 修复编码问题版本
解决报毒和目录结构问题
"""

import os
import sys
import subprocess
import platform
import shutil
import tempfile
from pathlib import Path

class ProfessionalBuilder:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.build_dir = self.project_root / "_build"
        self.dist_dir = self.project_root / "_dist"
        # 发布目录改为项目根目录的release/文件夹
        self.release_dir = self.project_root.parent / "release"
        
        # 创建目录
        self.build_dir.mkdir(exist_ok=True)
        self.dist_dir.mkdir(exist_ok=True)
        self.release_dir.mkdir(exist_ok=True)
        
        # 获取系统信息
        self.arch = platform.architecture()[0]  # 32bit or 64bit
        self.machine = platform.machine().lower()
        
    def clean_previous_builds(self):
        """清理之前的构建文件"""
        print("清理之前的构建文件...")
        
        # 删除默认的PyInstaller目录
        for dir_name in ['build', 'dist']:
            dir_path = self.project_root / dir_name
            if dir_path.exists():
                shutil.rmtree(dir_path)
                print(f"  已删除: {dir_path}")
        
        # 删除spec文件
        for spec_file in self.project_root.glob("*.spec"):
            try:
                spec_file.unlink()
                print(f"  已删除: {spec_file}")
            except:
                pass
    
    def create_optimized_spec(self, arch, console=False, onefile=True):
        """创建优化的spec文件，减少误报"""
        
        # 确定输出目录 - 直接输出到项目根目录的release/文件夹
        release_dir = str(self.project_root.parent / "release")
        if onefile:
            # 单文件模式：release/64bit/SVDEditor_64bit.exe
            output_dir = str(Path(release_dir) / arch)
        else:
            # 目录模式：release/64bit/SVDEditor_64bit/
            output_dir = str(Path(release_dir) / arch / f"SVDEditor_{arch}")
        
        # 项目根目录（父目录，因为run.py在build_tools的上一级）
        project_root_parent = str(self.project_root.parent)
        
        # run.py的绝对路径
        run_py_path = str(self.project_root.parent / 'run.py')
        
        spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
import sys
import os

# 设置递归深度限制
sys.setrecursionlimit(5000)

# 项目根目录（父目录）
project_root = r'{project_root_parent}'

# 输出目录设置 - 直接输出到release文件夹
if '{onefile}' == 'True':
    dist_dir = r'{output_dir}'
else:
    dist_dir = r'{output_dir}'

block_cipher = None

# 分析配置 - 使用run.py的绝对路径
a = Analysis(
    [r'{run_py_path}'],
    pathex=[project_root],
    binaries=[],
    datas=[
        # 配置文件 - 使用绝对路径
        (r'{project_root_parent}/config.py', '.'),
        (r'{project_root_parent}/README.md', '.'),
        (r'{project_root_parent}/README_zh.md', '.'),
        (r'{project_root_parent}/LICENSE', '.'),
    ],
    hiddenimports=[
        # PyQt6模块
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.sip',
        
        # 标准库模块
        'xml.etree',
        'xml.etree.ElementTree',
        'xml.dom',
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
        'inspect',
        'json',
        'warnings',
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    
    # 排除不必要的模块以减少文件大小和误报
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PyQt5',
        'PySide2',
        'PySide6',
        'test',
        'tests',
        'unittest',
        'pydoc',
        'pdb',
        'idlelib',
        'curses',
        'ensurepip',
        'venv',
        'distutils',
    ],
    
    # 减少误报的设置
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# 减少误报的额外设置
a.binaries = a.binaries  # 保持原样
a.datas = a.datas  # 保持原样

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# 可执行文件配置
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    
    # 减少误报的关键设置
    name='SVDEditor_{arch}',
    debug=False,           # 禁用调试信息
    bootloader_ignore_signals=False,
    strip=False,           # 不剥离符号（某些杀毒软件会检测剥离操作）
    upx=True,              # 使用UPX压缩
    upx_exclude=[],        # 不排除任何文件
    runtime_tmpdir=None,
    console={console},     # 控制台设置
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    
    # 图标设置（如果有）
    icon=os.path.join(project_root, 'icon.ico') if os.path.exists(os.path.join(project_root, 'icon.ico')) else None,
    
    # 版本信息（减少误报）
    version=os.path.join(project_root, 'version_info.txt') if os.path.exists(os.path.join(project_root, 'version_info.txt')) else None,
)

# 收集文件（用于目录模式）
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
        
        # 保存spec文件到构建目录
        spec_file = self.build_dir / f'svd_editor_{arch}.spec'
        with open(spec_file, 'w', encoding='utf-8') as f:
            f.write(spec_content)
        
        return spec_file
    
    def create_version_info(self):
        """创建版本信息文件，减少误报"""
        version_info = '''# UTF-8
#
# For more details about fixed file info 'ffi' see:
# http://msdn.microsoft.com/en-us/library/ms646997.aspx
VSVersionInfo(
  ffi=FixedFileInfo(
    # filevers and prodvers should be always a tuple with four items: (1, 2, 3, 4)
    # Set not needed items to zero 0.
    filevers=(2, 1, 0, 0),
    prodvers=(2, 1, 0, 0),
    # Contains a bitmask that specifies the valid bits 'flags'r
    mask=0x3f,
    # Contains a bitmask that specifies the Boolean attributes of the file.
    flags=0x0,
    # The operating system for which this file was designed.
    # 0x4 - NT and there is no need to change it.
    OS=0x40004,
    # The general type of file.
    # 0x1 - the file is an application.
    fileType=0x1,
    # The function of the file.
    # 0x0 - the function is not defined for this fileType
    subtype=0x0,
    # Creation date and time stamp.
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          u'040904B0',
          [StringStruct(u'CompanyName', u'SVD Tool Team'),
           StringStruct(u'FileDescription', u'SVD Editor - CMSIS SVD File Editor'),
           StringStruct(u'FileVersion', u'2.1.0.0'),
           StringStruct(u'InternalName', u'SVDEditor'),
           StringStruct(u'LegalCopyright', u'Copyright © 2026 SVD Tool Team. MIT License'),
           StringStruct(u'OriginalFilename', u'SVDEditor.exe'),
           StringStruct(u'ProductName', u'SVD Editor'),
           StringStruct(u'ProductVersion', u'2.1.0.0')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [0x409, 1200])])
  ]
)
'''
        
        version_file = self.project_root / 'version_info.txt'
        with open(version_file, 'w', encoding='utf-8') as f:
            f.write(version_info)
        
        return version_file
    
    def build(self, arch=None, console=False, onefile=True, clean=True):
        """执行构建"""
        if arch is None:
            arch = self.arch
        
        print(f"\n{'='*60}")
        print(f"构建 {arch} 版本")
        print(f"模式: {'单文件' if onefile else '目录'}")
        print(f"控制台: {'显示' if console else '隐藏'}")
        print(f"{'='*60}")
        
        # 清理之前的构建
        if clean:
            self.clean_previous_builds()
        
        # 创建版本信息文件
        version_file = self.create_version_info()
        print(f"创建版本信息文件: {version_file}")
        
        # 创建优化的spec文件
        spec_file = self.create_optimized_spec(arch, console, onefile)
        print(f"创建spec文件: {spec_file}")
        
        # 构建命令 - 当提供.spec文件时，不能使用--specpath
        # 注意：spec文件中已经设置了输出目录，但为了保险，我们也在这里设置
        release_output_dir = str(self.project_root.parent / "release" / arch)
        cmd = [
            sys.executable, '-m', 'PyInstaller',
            '--clean',
            '--distpath', release_output_dir,
            '--workpath', str(self.build_dir),
            str(spec_file)
        ]
        
        print(f"\n执行命令: {' '.join(cmd)}")
        
        try:
            # 执行构建
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                cwd=self.project_root,
                encoding='utf-8',
                errors='replace'
            )
            
            print("\n构建输出摘要:")
            for line in result.stdout.split('\n'):
                if any(keyword in line for keyword in ['INFO:', 'WARNING:', 'ERROR:']):
                    print(f"  {line}")
            
            # 检查构建结果 - 现在在release/arch目录中
            release_arch_dir = Path(release_output_dir)
            if onefile:
                exe_name = f'SVDEditor_{arch}.exe'
                exe_path = release_arch_dir / exe_name
            else:
                exe_name = f'SVDEditor_{arch}'
                exe_path = release_arch_dir / exe_name / f'SVDEditor_{arch}.exe'
            
            if exe_path.exists():
                print(f"\n[成功] 构建成功!")
                print(f"   可执行文件: {exe_path}")
                print(f"   文件大小: {exe_path.stat().st_size / 1024 / 1024:.2f} MB")
                
                # 由于已经直接输出到release目录，不需要再复制
                # 但可以创建ZIP包等
                self.create_release_package(arch, onefile, exe_path)
                
                return True
            else:
                print(f"\n[失败] 构建失败: 可执行文件未找到")
                print(f"   预期路径: {exe_path}")
                return False
                
        except subprocess.CalledProcessError as e:
            print(f"\n[失败] 构建失败，退出码: {e.returncode}")
            # 安全地处理编码问题
            try:
                print(f"错误输出:\n{e.stderr}")
            except UnicodeEncodeError:
                # 如果无法打印，则显示简化版本
                print(f"错误输出 (编码问题，显示前500字符):")
                safe_text = e.stderr.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                print(safe_text[:500])
            return False
        except Exception as e:
            print(f"\n[失败] 构建过程中发生异常: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def create_release_package(self, arch, onefile, exe_path):
        """创建发布包（ZIP和说明文件）"""
        print(f"\n创建发布包...")
        
        # arch-specific目录
        arch_dir = exe_path.parent
        
        if onefile:
            # 单文件模式 - 创建包含可执行文件和文档的ZIP包
            zip_name = f'SVDEditor_{arch}_standalone.zip'
            zip_path = self.release_dir / zip_name
            
            # 创建临时目录并复制文件
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_dir_path = Path(temp_dir)
                
                # 复制可执行文件
                shutil.copy2(exe_path, temp_dir_path / f'SVDEditor_{arch}.exe')
                
                # 复制文档文件（从项目根目录）
                project_root = self.project_root.parent
                for doc_file in ['README.md', 'README_zh.md', 'LICENSE', 'config.py']:
                    source_doc = project_root / doc_file
                    if source_doc.exists():
                        shutil.copy2(source_doc, temp_dir_path / doc_file)
                
                # 创建ZIP
                shutil.make_archive(
                    str(zip_path).replace('.zip', ''),
                    'zip',
                    temp_dir
                )
            
            print(f"   ZIP包: {zip_path}")
        else:
            # 目录模式 - 创建整个目录的ZIP包
            source_dir = arch_dir / f'SVDEditor_{arch}'
            if source_dir.exists():
                zip_name = f'SVDEditor_{arch}_portable.zip'
                zip_path = self.release_dir / zip_name
                shutil.make_archive(
                    str(zip_path).replace('.zip', ''),
                    'zip',
                    str(arch_dir),
                    f'SVDEditor_{arch}'
                )
                
                print(f"   ZIP包: {zip_path}")
        
        # 创建说明文件
        import platform
        readme_content = f'''SVD Editor {arch} 版本

构建时间: {platform.node()} @ {platform.platform()}
Python版本: {platform.python_version()}
架构: {arch}

包含文件:
1. SVDEditor_{arch}.exe - 主程序
2. config.py - 配置文件
3. README.md - 英文说明
4. README_zh.md - 中文说明
5. LICENSE - 许可证文件

使用说明:
1. 单文件版本: 直接运行 SVDEditor_{arch}.exe
2. 便携版本: 解压后运行 SVDEditor_{arch}/SVDEditor_{arch}.exe

减少误报提示:
- 已添加版本信息
- 使用标准构建配置
- 如果被杀毒软件误报，请添加到白名单
'''
        
        readme_file = arch_dir / 'README.txt'
        with open(readme_file, 'w', encoding='utf-8') as f:
            f.write(readme_content)
        
        print(f"   说明文件: {readme_file}")
    
    def print_summary(self):
        """打印构建总结"""
        print(f"\n{'='*60}")
        print("构建总结")
        print(f"{'='*60}")
        
        print(f"\n项目根目录: {self.project_root}")
        print(f"构建目录: {self.build_dir}")
        print(f"输出目录: {self.dist_dir}")
        print(f"发布目录: {self.release_dir}")
        
        print(f"\n发布文件:")
        if self.release_dir.exists():
            for item in self.release_dir.iterdir():
                if item.is_dir():
                    print(f"  [目录] {item.name}/")
                    for subitem in item.iterdir():
                        print(f"    [文件] {subitem.name}")
                elif item.is_file():
                    print(f"  [文件] {item.name}")
        
        print(f"\n减少误报措施:")
        print("  1. 添加了完整的版本信息")
        print("  2. 使用标准构建配置")
        print("  3. 排除了不必要的模块")
        print("  4. 提供了白名单说明")
        
        print(f"\n目录结构优化:")
        print("  1. 构建文件存储在 _build/ 目录")
        print("  2. 输出文件存储在 _dist/ 目录")
        print("  3. 发布文件存储在 release/ 目录")
        print("  4. 根目录保持整洁")

def main():
    """主函数"""
    print("SVD Editor 专业构建工具")
    print("="*60)
    print("解决报毒问题和目录结构不美观问题")
    
    builder = ProfessionalBuilder()
    
    # 获取当前架构
    current_arch = builder.arch
    
    # 架构选择
    print(f"\n当前系统架构: {current_arch}")
    print("\n请选择目标架构:")
    print("1. 使用当前系统架构 (自动检测)")
    print("2. 构建32位版本")
    print("3. 构建64位版本")
    
    arch_choice = input("\n请选择架构 (1-3): ").strip()
    
    target_arch = current_arch
    if arch_choice == '2':
        target_arch = '32bit'
        if current_arch != '32bit':
            print("警告: 当前Python不是32位，构建可能失败")
            confirm = input("继续构建? (y/n): ").lower()
            if confirm != 'y':
                return
    elif arch_choice == '3':
        target_arch = '64bit'
        if current_arch != '64bit':
            print("警告: 当前Python不是64位，构建可能失败")
            confirm = input("继续构建? (y/n): ").lower()
            if confirm != 'y':
                return
    elif arch_choice != '1':
        print("无效选择，使用当前系统架构")
    
    # 构建选项
    print(f"\n目标架构: {target_arch}")
    print("\n构建选项:")
    print("1. 构建单文件版本 (推荐)")
    print("2. 构建便携目录版本")
    print("3. 构建调试版本 (显示控制台)")
    print("4. 构建所有版本")
    
    choice = input("\n请选择构建模式 (1-4): ").strip()
    
    if choice == '1':
        # 单文件版本
        builder.build(arch=target_arch, console=False, onefile=True)
    elif choice == '2':
        # 便携目录版本
        builder.build(arch=target_arch, console=False, onefile=False)
    elif choice == '3':
        # 调试版本
        builder.build(arch=target_arch, console=True, onefile=True)
    elif choice == '4':
        # 所有版本
        print("\n构建所有版本...")
        builder.build(arch=target_arch, console=False, onefile=True)
        builder.build(arch=target_arch, console=False, onefile=False)
    else:
        print("无效选择")
        return
    
    # 打印总结
    builder.print_summary()

if __name__ == '__main__':
    main()