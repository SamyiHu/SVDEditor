<!-- README.md - English Version -->
<div align="center">

# SVD Editor

[![English](https://img.shields.io/badge/English-US-blue?style=for-the-badge)](README.md)
[![中文](https://img.shields.io/badge/中文-CN-red?style=for-the-badge)](README_zh.md)

**A professional CMSIS-SVD parsing, editing, visualization, and CLI tool. Supports peripheral management, register editing, bitfield visualization, batch operations, diff/merge, C header generation, and more.**

[View in Chinese](README_zh.md)

</div>

---

## Features

### GUI Editor
- **SVD/XML Parsing**: Import standard CMSIS-SVD files, parse device/peripheral/register/field hierarchy
- **Visual Tree Editing**: Three-level tree view (Peripheral -> Register -> Bitfield) with full CRUD
- **Inherited Peripheral Support**: Auto-merge registers from `derivedFrom` base peripherals
- **Address Map Visualization**: Graphical peripheral address space layout with register offsets
- **Bitfield Visualization**: Register bitfield diagrams with highlight and editing
- **Interrupt Management**: Configure and manage interrupt vectors
- **Undo/Redo**: Unlimited operation history with snapshot recovery
- **Advanced Search**: Unified search syntax (`type:periph name:GPIO* addr:0x4001*`) with structured and full-text modes
- **Batch Operations**: Batch modify, batch generate registers, batch clone across peripherals
- **Chain Rules**: Cascading delete/modify rules with configurable actions
- **Drag-and-Drop Sorting**: Reorder peripherals and registers via drag-and-drop
- **Multi-document Tabs**: Open and switch between multiple SVD files
- **Real-time Preview**: Live XML preview with syntax highlighting
- **Dark/Light Theme**: Built-in theme switching with modern flat UI

### CLI Commands (CI/CD Ready)

| Command | Description |
|---------|-------------|
| `validate` | Validate SVD against CMSIS-SVD schema (bitfield overlap, address conflicts, required fields) |
| `export` | Export to CSV, Markdown, or HTML documentation |
| `generate` | Regenerate/formatter SVD XML |
| `diff` | Compare two SVD files for structural differences |
| `info` | Display device info and statistics |
| `merge` | Merge two SVD files with configurable conflict strategy |
| `header` | Generate C header files from SVD |
| `conflicts` | Detect address overlaps, register offset duplicates, bitfield conflicts |
| `extract` | Extract specific peripherals into a new SVD file |

### Output & Export
- **SVD Generation**: Well-formatted, indented SVD/XML output
- **Documentation Export**: CSV, Markdown, HTML register documentation
- **C Header Generation**: `#define` macros for register addresses and bitfield masks
- **Diff Reports**: Text or JSON difference reports

## Installation & Running

### Requirements
- Python 3.10+
- PyQt6 6.5.0+

### Quick Start

```bash
git clone https://github.com/SamyiHu/SVDEditor.git
cd SVDEditor
pip install PyQt6
python run.py                # GUI mode
python run.py info file.svd  # CLI mode
```

## CLI Usage

```bash
# Validate
python run.py validate chip.svd [--json] [--strict]

# Export documentation
python run.py export chip.svd --format markdown -o registers.md
python run.py export chip.svd --format csv --peripheral GPIOA --summary-only

# Regenerate SVD
python run.py generate chip.svd -o output.svd

# Diff two versions
python run.py diff chip_v1.svd chip_v2.svd [--json] [--ignore-description]

# Device info
python run.py info chip.svd [--json]

# Merge SVD files
python run.py merge target.svd source.svd --strategy source -o merged.svd

# Generate C header
python run.py header chip.svd --style upper_case --prefix CHIP_ -o device.h

# Check address conflicts
python run.py conflicts chip.svd [--json] [--strict]

# Extract peripherals
python run.py extract chip.svd --peripherals GPIOA,GPIOB,GPIOC -o gpio.svd
```

### Keyboard Shortcuts (GUI)
| Shortcut | Action |
|----------|--------|
| `Ctrl+N` | New SVD file |
| `Ctrl+O` | Open file |
| `Ctrl+S` | Save file |
| `Ctrl+Z` | Undo |
| `Ctrl+Y` | Redo |
| `Ctrl+F` | Quick search |
| `Ctrl+H` | Advanced search |
| `Ctrl+Shift+G` | Go to address |
| `F5` | Refresh view |

## Project Structure

```
SVDEditor/
├── run.py                          # Entry point (GUI + CLI)
├── svd_tool/
│   ├── cli.py                      # CLI module (9 commands)
│   ├── main.py                     # GUI entry
│   ├── core/
│   │   ├── data_model.py           # Device, Peripheral, Register, Field
│   │   ├── svd_parser.py           # SVD parser
│   │   ├── svd_generator.py        # SVD generator
│   │   ├── svd_schema_validator.py # Schema validation
│   │   ├── svd_exporter.py         # CSV/Markdown/HTML export
│   │   ├── svd_differ.py           # Diff engine
│   │   ├── svd_merger.py           # Merge engine
│   │   ├── header_generator.py     # C header generator
│   │   ├── address_conflict_detector.py  # Conflict detection
│   │   ├── chain_rules.py          # Chain rules engine
│   │   └── command_history.py      # Undo/Redo
│   ├── ui/
│   │   ├── main_window_refactored.py     # Main window
│   │   ├── components/
│   │   │   ├── state_manager.py          # State management
│   │   │   ├── layout_manager.py         # Layout coordination
│   │   │   ├── tab_builder.py            # Tab page construction
│   │   │   ├── ui_updater.py             # UI update coordination
│   │   │   └── menu_bar.py / toolbar.py  # Menu & toolbar
│   │   ├── managers/
│   │   │   ├── search_manager.py         # Search (quick + advanced)
│   │   │   ├── batch_operations_manager.py  # Batch operations
│   │   │   ├── file_operations.py        # File I/O
│   │   │   └── register_manager.py       # Register management
│   │   ├── dialogs/
│   │   │   ├── chain_rules_dialog.py     # Chain rules editor
│   │   │   ├── new_svd_wizard.py         # New file wizard
│   │   │   └── svd_diff_dialog.py        # Diff dialog
│   │   └── widgets/
│   │       ├── bit_field_widget.py       # Bitfield visualization
│   │       ├── address_map_widget.py     # Address map
│   │       ├── toggle_switch.py          # iOS-style toggle
│   │       ├── labeled_slider.py         # Slider with input
│   │       └── welcome_page.py           # Welcome page
│   ├── config/
│   │   ├── styles.py               # Theme/style system (dark/light)
│   │   └── tree_branch_style.py    # Custom tree branches
│   └── i18n/
│       ├── zh_CN.json              # Chinese translations
│       └── en_US.json              # English translations
├── build_tools/                    # PyInstaller build scripts
├── test_data/                      # Test SVD files
└── tests/                          # Test suite
```

## Building

See [BUILD_INSTRUCTIONS_EN.md](docs/BUILD_INSTRUCTIONS_EN.md) for detailed build instructions.

```bash
pip install pyinstaller
cd build_tools
python build_professional_fixed.py
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Maintainer

- SamyiHu (@SamyiHu)

---

<div align="center">

**Enjoy using SVD Editor!**

[![English](https://img.shields.io/badge/English-US-blue?style=for-the-badge)](README.md)
[![中文](https://img.shields.io/badge/中文-CN-red?style=for-the-badge)](README_zh.md)

</div>
