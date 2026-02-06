# SVD Editor Build Guide

## Overview

This document describes how to create executable files for the SVD Editor project, supporting Windows platforms (32-bit and 64-bit).

## Dependencies

### Development Environment
- Python 3.10 or higher
- PyQt6 6.5.0+
- PyInstaller 6.0+

### Install Dependencies
```bash
pip install PyQt6 pyinstaller
```

## Packaging Methods

### Method 1: Using Build Scripts (Recommended)

The project includes build scripts that support interactive building:

```bash
python build_windows.py
```

Options:
1. Build for current architecture (auto-detected)
2. Build 32-bit version (requires 32-bit Python)
3. Build 64-bit version (requires 64-bit Python)
4. Build all available versions
5. Build debug version (with console)

### Method 2: Using PyInstaller Directly

#### Single-file mode (all content packaged into one EXE)
```bash
python -m PyInstaller --onefile --windowed --name SVDEditor run.py
```

#### Directory mode (recommended for debugging and updates)
```bash
python -m PyInstaller --windowed --name SVDEditor run.py
```

#### Include data files
```bash
python -m PyInstaller --windowed --name SVDEditor --add-data "config.py;." --add-data "README.md;." --add-data "README_zh.md;." --add-data "LICENSE;." run.py
```

### Method 3: Using spec files

1. Generate spec file:
   ```bash
   python -m PyInstaller --onefile --windowed --name SVDEditor run.py
   ```

2. Edit the generated `SVDEditor.spec` file to add data files:
   ```python
   # Add in Analysis section
   datas=[
       ('config.py', '.'),
       ('README.md', '.'),
       ('README_zh.md', '.'),
       ('LICENSE', '.'),
   ],
   ```

3. Build using spec file:
   ```bash
   python -m PyInstaller SVDEditor.spec
   ```

## Platform-Specific Instructions

### Windows 64-bit
- Use 64-bit Python environment
- Generated executable runs on 64-bit Windows
- File size: approximately 35-40MB

### Windows 32-bit
- Use 32-bit Python environment
- Generated executable runs on both 32-bit and 64-bit Windows
- File size: approximately 30-35MB

### Important Notes
1. **Qt plugins**: PyInstaller automatically includes necessary Qt plugins
2. **Icon**: Use `--icon=icon.ico` parameter to add an icon
3. **Console**: Use `--windowed` for GUI applications, `--console` for debug versions
4. **UPX compression**: Enabled by default to reduce file size

## Testing the Build

### Quick Test
1. Navigate to `dist` directory
2. Run the generated executable:
   ```bash
   cd dist
   SVDEditor.exe
   ```

### Function Verification
- Launch the application
- Open SVD file
- Edit peripherals, registers, bitfields
- Generate SVD file
- Verify all visualization functions

## Common Issues

### 1. Application fails to start
- Ensure all dependencies are correctly packaged
- Check for missing DLL files
- Try running from command line to see error messages

### 2. File size too large
- Use UPX compression (enabled by default)
- Exclude unnecessary modules
- Use `--exclude-module` parameter

### 3. Missing data files
- Ensure data files are correctly added in spec file
- Check file paths are correct

### 4. Cross-platform building
- Windows to Linux: Need to build on Linux system
- Consider using Docker for cross-platform building

## Release Preparation

### Version Information
Edit version number in `svd_tool/__init__.py`:
```python
__version__ = "2.1.0"
```

### Included Files
Release should include:
1. Executable file (or installer package)
2. README documentation (English and Chinese)
3. LICENSE file
4. Configuration file examples

### Creating Installer Packages
You can use the following tools to create installers:
- Inno Setup (Windows)
- NSIS (Windows)
- Simple ZIP archive

## Automated Build

The project includes the following build configuration files:
1. `requirements.txt` - Dependency list
2. `setup.py` - Python package configuration
3. `build.spec` - PyInstaller configuration example
4. `build_windows.py` - Automated build script

## Support & Maintenance

If you encounter build issues, please check:
1. PyInstaller version compatibility
2. Python and PyQt6 versions
3. Operating system architecture matching
4. Error logs (in `build` directory)

## Changelog

### v2.1.0
- First complete packaging solution
- Support for Windows 32/64-bit
- Includes all necessary data files
- Provides build scripts and documentation