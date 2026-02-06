@echo off
echo ========================================
echo SVD Editor Build Script
echo ========================================
echo.
echo Build scripts have been moved to the 'build_tools/' directory.
echo.
echo Please select which build script to run:
echo.
echo 1. Professional build (recommended)
echo    - 支持32位和64位架构选择
echo    - 更好的杀毒软件兼容性
echo    - 整洁的目录结构
echo    - 提供单文件版本和目录版本选择
echo.
echo 2. Basic Windows build
echo    - 简单的32位/64位选择
echo    - 传统PyInstaller方式
echo    - 同样支持单文件和目录版本
echo.
echo ========================================
echo.
echo 版本说明:
echo - 单文件版本: 单个.exe文件，所有依赖打包在一起，适合分发
echo - 目录版本: 包含.exe和依赖文件的文件夹，适合调试和查看
echo.
echo Which build script would you like to run? (1 or 2)
set /p script_choice=
if "%script_choice%"=="1" (
    echo.
    echo Running professional build script...
    echo 注意: 此脚本将询问架构选择 (32位/64位) 和版本类型 (单文件/目录)
    echo.
    cd build_tools
    python build_professional_fixed.py
) else if "%script_choice%"=="2" (
    echo.
    echo Running basic Windows build script...
    echo 注意: 此脚本将询问架构选择 (32位/64位) 和版本类型 (单文件/目录)
    echo.
    cd build_tools
    python build_windows.py
) else (
    echo.
    echo Invalid choice. Please run manually:
    echo   cd build_tools
    echo   python build_professional_fixed.py
    echo or
    echo   cd build_tools
    echo   python build_windows.py
)