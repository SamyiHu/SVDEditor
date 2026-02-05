<!-- README.md - English Version -->
<div align="center">

# 🚀 SVD Editor

[![English](https://img.shields.io/badge/English-🇺🇸-blue?style=for-the-badge)](README.md)
[![中文](https://img.shields.io/badge/中文-🇨🇳-red?style=for-the-badge)](README_zh.md)

**A CMSIS SVD parsing/editing/visualization tool based on componentized architecture, supporting peripheral addition, register editing, interrupt management, developed with Python/Qt, providing better maintainability and extensibility.**

[View in Chinese](README_zh.md) | [查看中文版](README_zh.md)

</div>

---

## 🌐 Quick Navigation
- [English Version](#english-version) 🇺🇸
- [中文版本](README_zh.md) 🇨🇳

---

## 📖 English Version

### Major Improvements
- **Componentized Architecture**: Split main window logic into independent components (StateManager, LayoutManager, PeripheralManager)
- **Better Code Organization**: Reduced coupling, improved testability
- **Enhanced State Management**: Centralized state handling, supports snapshots and recovery
- **Modern UI Components**: Implement visualization functions using dedicated widgets
- **Complete Test Suite**: Includes unit tests, integration tests, and GUI tests

### Features

#### Core Functions
- **SVD/XML File Parsing**: Import standard SVD files, parse device, peripheral, register, bitfield hierarchy
- **Visual Editing**: Tree view displays three-level structure (Peripheral → Register → Bitfield), supports CRUD operations
- **Inherited Peripheral Support**: Automatically merges register definitions from base class peripherals, visually displays inheritance relationships
- **Address Mapping Visualization**: Graphical display of peripheral address space layout and register offsets
- **Bitfield Visualization**: Graphical display of register bitfields, supports highlighting and editing
- **Interrupt Management**: Configure and manage peripheral interrupt vectors

#### User Experience
- **Undo/Redo**: Complete operation history, supports unlimited undo/redo
- **Search & Filter**: Quickly locate peripherals, registers, bitfields
- **Drag-and-Drop Sorting**: Intuitive adjustment of peripheral and register order
- **Multi-tab Interface**: Page management for different functional modules
- **Real-time Preview**: Real-time updates to visual effects during editing

#### Output & Export
- **Formatted SVD Generation**: Generate well-formatted, neatly indented SVD/XML files
- **Custom Configuration**: Supports output format customization (indentation, attribute order, etc.)
- **Batch Processing**: Supports batch import/export

## Installation & Running

### Environment Requirements
- Python 3.10 or higher
- PyQt6 6.5.0+

### Quick Start

1. **Clone Repository**
   ```bash
   git clone https://github.com/SamyiHu/SVDEditor.git
   cd SVDEditor
   ```

2. **Create Virtual Environment (Recommended)**
   ```bash
   python -m venv .venv
   # Windows
   .\.venv\Scripts\activate
   # Linux/Mac
   source .venv/bin/activate
   ```

3. **Install Dependencies**
   ```bash
   pip install PyQt6
   # Or use requirements.txt (if exists)
   pip install -r requirements.txt
   ```

4. **Run Application**
   ```bash
   python run.py
   ```

## Building & Distribution

The project includes professional build tools for creating standalone executables for Windows platforms.

### Build Tools

Build scripts are located in the `build_tools/` directory:

- **`build_professional_fixed.py`** (Recommended) - Professional build script with anti-virus false positive reduction
- **`build_windows.py`** - Basic Windows build script with 32/64-bit architecture selection

### Quick Build Instructions

1. **Install Build Dependencies**
   ```bash
   pip install -r requirements.txt
   pip install pyinstaller
   ```

2. **Use Convenience Scripts (Optional)**
   - **Windows**: Run `build.bat` from the project root
   - **Linux/Mac**: Run `./build.sh` from the project root
   
   Or manually navigate to the build tools directory:
   ```bash
   cd build_tools
   ```

3. **Run Professional Build Script**
   ```bash
   python build_professional_fixed.py
   ```

4. **Find Output Files**
   - Executable: `../_dist/SVDEditor_64bit.exe`
   - Release files: `../release/64bit/`

### Build Features

- **Anti-virus False Positive Reduction**: Includes version information and uses standard build techniques
- **Clean Directory Structure**: Build artifacts are organized in `_build/` and `_dist/` directories
- **Icon Support**: Automatically includes `icon.ico` from project root
- **Version Information**: Reads from `version_info.txt`

### Important Notes

- The build scripts must be run from the `build_tools/` directory
- If you encounter "file not found" errors, ensure you're in the correct directory
- For 32-bit builds, use `python build_windows.py` and select the 32-bit option

## User Guide

### Basic Workflow
1. **Import SVD File**: Click "File" → "Open", select SVD/XML file
2. **Browse Structure**: Left tree view displays device→peripheral→register→bitfield hierarchy
3. **Edit Items**:
   - Double-click tree nodes to edit properties
   - Right-click menu to add/delete items
   - Drag and drop to adjust order
4. **Visual View**:
   - Select peripheral to view address map
   - Select register to view bitfield distribution
   - Select bitfield to view detailed properties
5. **Save Results**: Click "Generate" button to save formatted SVD file

### Inherited Peripheral Handling
When peripherals use the `derivedFrom` attribute, the tool automatically:
- Merges register definitions from base class peripherals
- Differentiates inherited registers with different colors in address maps
- Maintains completeness of register definitions

### Shortcuts
- `Ctrl+O`: Open file
- `Ctrl+S`: Save file
- `Ctrl+Z`: Undo
- `Ctrl+Y`: Redo
- `Ctrl+F`: Search
- `F5`: Refresh view

## Project Structure (Refactored Version)

```
SVDEditor/
├── run.py                    # Application startup script
├── config.py                 # Configuration file
├── README.md                 # This document (English)
├── README_zh.md             # Chinese documentation
├── requirements.txt          # Python dependencies
├── setup.py                  # Python package configuration
├── icon.ico                  # Application icon
├── version_info.txt          # Version information for builds
├── svd_tool/                 # Main package directory
│   ├── main.py              # Application entry (using MainWindowRefactored)
│   ├── core/                # Core logic
│   │   ├── data_model.py    # Data models (Device, Peripheral, Register, Field)
│   │   ├── svd_parser.py    # SVD parser
│   │   ├── svd_generator.py # SVD generator
│   │   ├── validators.py    # Data validation
│   │   └── command_history.py # Command history (undo/redo)
│   ├── ui/                  # User interface (componentized)
│   │   ├── main_window_refactored.py   # Refactored main window (componentized architecture)
│   │   ├── dialog_factories.py # Dialog factories
│   │   ├── dialogs.py       # Various dialogs
│   │   ├── form_builder.py  # Form builder
│   │   ├── tree_manager.py  # Tree view management
│   │   ├── components/      # Component directory
│   │   │   ├── state_manager.py     # State management component
│   │   │   ├── layout_manager.py    # UI layout management component
│   │   │   ├── peripheral_manager.py # Peripheral management component
│   │   │   ├── menu_bar.py          # Menu bar component
│   │   │   └── toolbar.py           # Toolbar component
│   │   └── widgets/         # Dedicated widgets
│   │       ├── address_map_widget.py   # Address mapping widget
│   │       ├── bit_field_widget.py     # Bitfield widget
│   │       └── visualization_widget.py # Visualization widget
│   └── utils/               # Utility functions
│       ├── helpers.py       # Helper functions
│       └── logger.py        # Log configuration
├── build_tools/             # Build and packaging tools
│   ├── build_professional_fixed.py  # Professional build script (recommended)
│   ├── build_windows.py             # Basic Windows build script
│   └── README.md                    # Build tools documentation
├── docs/                    # Project documentation
│   ├── BUILD_INSTRUCTIONS.md       # Detailed build instructions
│   ├── FINAL_SOLUTION.md           # Final solution documentation
│   ├── ICON_GUIDE.md               # Icon usage guide
│   ├── MIGRATION_PROGRESS.md       # Migration progress
│   ├── PROJECT_STRUCTURE.md        # Project structure documentation
│   └── README.md                   # Documentation index
├── tests/                   # Test suite
│   ├── unit_tests/         # Unit tests
│   ├── integration_tests/  # Integration tests
│   └── gui_tests/          # GUI tests
├── _build/                  # PyInstaller build artifacts (auto-generated)
├── _dist/                   # PyInstaller output executables (auto-generated)
├── release/                 # Release files (auto-generated)
├── LICENSE                 # MIT license
└── .venv/                  # Virtual environment (optional)
```

## Development & Contribution

### Code Standards
- Follow PEP 8 Python coding standards
- Use type annotations (Type Hints)
- Modular design, separation of concerns

### Testing
The project includes multiple test scripts to verify core functionality:
- `test_all_improvements.py`: Comprehensive test of all improved features
- `test_inheritance_fix.py`: Test inherited peripheral functionality
- `test_graphics.py`: Test graphical components
- `test_rectangle_fix.py`: Test rectangle drawing
- `test_final_verification.py`: Final verification test

Run tests:
```bash
python test_all_improvements.py
```

### Submitting Contributions
1. Fork this repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -m 'Add some feature'`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Create a Pull Request

### Open Source License Information

This project uses the MIT License, a permissive open source license that allows:

- Commercial use
- Modification and distribution
- Private use
- Sublicensing
- Patent grant

The only requirement is to preserve the original copyright notice and license statement.

### Contributor Agreement

By submitting code to this project, you agree that your contributions will be released under the MIT License.

## Maintainers

- SamyiHu (@SamyiHu) - Project creator and main maintainer

## Changelog

### Latest Version (v2.1)
- **Visualization Improvements**: Added address mapping and bitfield visualization components
- **Inherited Peripheral Support**: Enhanced register merging display for derivedFrom peripherals
- **UI Optimization**: Refactored toolbar, removed redundant buttons, optimized layout
- **Test Suite**: Added multiple functional test scripts
- **Bug Fixes**: Fixed known issues with tree view selection, undo/redo, etc.

---

<div align="center">

**Enjoy using SVD Editor!** ✨

[![English](https://img.shields.io/badge/English-🇺🇸-blue?style=for-the-badge)](README.md)
[![中文](https://img.shields.io/badge/中文-🇨🇳-red?style=for-the-badge)](README_zh.md)

</div>