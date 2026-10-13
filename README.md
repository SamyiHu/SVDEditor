<!-- README.md - English Version -->
<div align="center">

# SVD Editor

[![English](https://img.shields.io/badge/English-US-blue?style=for-the-badge)](README.md)
[![中文](https://img.shields.io/badge/中文-CN-red?style=for-the-badge)](README_zh.md)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![PyQt6](https://img.shields.io/badge/PyQt6-6.5+-41CD52?style=for-the-badge&logo=qt&logoColor=white)](https://www.riverbankcomputing.com/software/pyqt/)
[![License](https://img.shields.io/badge/License-GPL%20v3-blue?style=for-the-badge)](LICENSE)

**A professional CMSIS-SVD parsing, editing, visualization, and CLI tool. Supports peripheral management, register editing, bitfield visualization, batch operations, diff/merge, C header generation, and more.**

[View in Chinese](README_zh.md)

</div>

---

## Screenshots

![GUI Overview](docs/screenshots/gui_overview.png)
*Main interface: three-level tree, address map, XML live preview*

![Bitfield Editor](docs/screenshots/bitfield_editor.png)
*Bitfield visualization and register details*

---

## Features

### GUI Editor

| Feature | Description |
|---------|-------------|
| **SVD/XML Parsing** | Import standard CMSIS-SVD files, parse device/peripheral/register/field hierarchy |
| **Visual Tree Editing** | Three-level tree view (Peripheral -> Register -> Bitfield) with full CRUD |
| **Inherited Peripheral Support** | Auto-merge registers from `derivedFrom` base peripherals |
| **Address Map Visualization** | Graphical peripheral address space layout with register offsets |
| **Bitfield Visualization** | Register bitfield diagrams with highlight and editing |
| **Interrupt Management** | Configure and manage interrupt vectors |
| **Undo/Redo** | Unlimited operation history with snapshot recovery |
| **Advanced Search** | Unified search syntax (`type:periph name:GPIO* addr:0x4001*`) with structured and full-text modes |
| **Batch Operations** | Batch modify, batch generate registers, batch clone across peripherals |
| **Chain Rules** | Cascading delete/modify rules with configurable actions |
| **Drag-and-Drop Sorting** | Reorder peripherals and registers via drag-and-drop |
| **Multi-document Tabs** | Open and switch between multiple SVD files |
| **Real-time Preview** | Live XML preview with syntax highlighting |
| **Dark/Light Theme** | Built-in theme switching with modern flat UI |
| **dim Register Arrays** | Full support for register & cluster level `dim`/`dimIncrement`/`dimIndex` (configurable via edit dialog) |

### AI Integration (MCP)

The built-in AI panel has been removed in favor of a standard **MCP Server**: connect your own AI client (ZCode / Claude Desktop / Cursor / Cherry Studio / Cline, etc.) and edit SVD files in natural language. Model, API keys, and chat UI are all managed by your client — this tool just exposes 30 standard MCP tools.

**Capabilities:**

| Capability | Description |
|------------|-------------|
| **Query & Search** | Device summary, layered peripheral/register/field getters, unified search with pagination |
| **CRUD** | Full add/update/remove for peripherals, registers, bitfields, and interrupts (incl. rename, derivedFrom) |
| **Validation** | CMSIS-SVD schema validation, address conflict detection |
| **Multi-document** | Open / switch / diff multiple SVD files |
| **Export** | CSV / Markdown / HTML docs, C header generation (plain & CMSIS style) |

**Conventions:** edits stay in memory; `svd_save_document` writes to disk (auto `.bak` backup before overwriting). Addresses/offsets use hex strings.

**Client config** (works across clients):

```json
{
  "mcpServers": {
    "svd-editor": {
      "command": "python",
      "args": ["C:/path/to/SVDEditor/run.py", "--mcp"],
      "env": { "PYTHONUTF8": "1" }
    }
  }
}
```

See [docs/MCP_DESIGN.md](docs/MCP_DESIGN.md) for the full tool list, the planned GUI live-bridge mode, and branch strategy.

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
| `create` | **Create new SVD from JSON data** (`DeviceInfo.to_dict()` format) |
| `add-peripheral` | Add peripherals from JSON to existing SVD |
| `update-peripheral` | Update peripheral properties (base address, description, etc.) |
| `remove-peripheral` | Remove peripherals from SVD by name |
| `add-register` | Add registers to a peripheral (from JSON or CLI args) |
| `update-register` | Update register properties (offset, size, access, etc.) |
| `remove-register` | Remove registers from a peripheral by name |
| `add-field` | Add bitfields to a register (from JSON or CLI args) |
| `update-field` | Update bitfield properties (bit offset, bit width, access, etc.) |
| `remove-field` | Remove bitfields from a register by name |

### Output & Export

- **SVD Generation**: Well-formatted, indented SVD/XML output
- **Documentation Export**: CSV, Markdown, HTML register documentation
- **C Header Generation**: `#define` macros for register addresses and bitfield masks
- **Diff Reports**: Text or JSON difference reports

---

## Datasheet Resource Import (Excel/Word/PDF → SVD)

Integrates the [Parser](https://github.com/SamyiHu) multi-source parsing package to auto-generate SVDs from chip datasheets (TRM) and Excel SFR tables, and to verify existing SVDs against manuals.

### Workflow

```
Datasheet (Excel/Word/PDF) → parse → peripherals/registers/fields → import as SVD / verify
```

GUI entry: **Tools menu → Import from Datasheet** (`Ctrl+Shift+I`) or the green "Import" toolbar button.

### Three Capabilities

| Capability | Description |
|------------|-------------|
| **Resource Import** | Parse Excel/Word/PDF datasheets to auto-generate SVD. Supports single-source quick import and multi-source fusion (confidence-weighted cross-validation) |
| **SVD Verification** | Compare current SVD against parsed manual results, finding missing registers/fields, offset/reset/access/width mismatches. Supports one-click "accept suggestion" fixes (undoable) |
| **Package Trim Analysis** | Auto-derive peripheral differences per package (LQFP48/64/80) from the Datasheet pinout table, outputting a trim manifest (see below) |

### Multi-source Fusion

When providing Excel + Word + PDF simultaneously, results are fused with confidence weighting:
- **Cross-validation**: Properties consistent across sources get boosted confidence
- **Conflict marking**: Disputed properties are recorded in `FusionReport`, reviewable via "Tools → Multi-source Fusion Review"
- **Confidence color-coding**: Tree nodes show high/medium/low/missing quality at a glance

### Word TRM Three-Stage Parsing

A specialized parser for domestic MCU TRMs (SC32/STM32-style) register three-stage structure:
1. **Register map table**: Contains "base address" + `|REG|offset|R/W|desc|reset|`, extracting peripheral and register metadata
2. **Bitfield detail table**: `|bit#|symbol|desc|` after `####` register headings, extracting fields
3. **Normalized matching**: `PWM0_DTx` → `PWMn_DTn`, correctly attributing fields to register templates

> Far more accurate than the Parser's native Word parser (which only recognizes a single table type and frequently loses register names as UNKNOWN).

---

## Package Trim Analysis (Datasheet Pinout → Per-Variant SVD)

Different packages of the same chip family (e.g., LQFP48/64/80) trim peripherals differently (e.g., fewer ADC channels, CMP pins not bonded out). This tool can **auto-derive** per-package trim differences from the Datasheet's "Pin Resource List" table.

### Trim Rules

Identifies which peripheral functions each package actually bonds out, generating a trim manifest relative to the master (the package with the most pins):

| Trim Type | Trigger | Action |
|-----------|---------|--------|
| **Peripheral-level** | A peripheral has no pins at all in a package (e.g., CMP/OP on 48-pin) | Remove the entire peripheral |
| **Instance-level** | A peripheral instance (e.g., UART1) has no default or remapped pins | Remove that instance |
| **ADC bitfield** | AIN channel count varies by package | Narrow the `AINx` bitfield width |
| **LCD segment** | SEG count varies by package | Trim SEGR registers 1:1 |

> **Parenthesis rule**: Functions in parentheses (e.g., `(RxD2)`) = pin remapping; counted as available, not triggering removal.

### Example (SC32L14T/14G)

Auto-analyzed trim manifest from Datasheet:

```
Master package: LQFP80

LQFP48 (48-pin):
  Remove periphs:  CMP, OP
  Remove instances: UART1, UART2, TIM5
  ADC narrow:      AINx bit[0:19] → bit[0:13] (AIN0~13)
  SEGR trim:       55 → 28 registers

LQFP64 (64-pin):
  Remove instances: UART4
  ADC narrow:      AINx → bit[0:17]
  SEGR trim:       55 → 40 registers
```

### API Usage

```python
from svd_tool.core.datasource.pinout_parser import DatasheetPinoutParser

parser = DatasheetPinoutParser()
result = parser.parse_file("SC32L14T_14G_Datasheet.docx")

print(f"Master package: {result.master_package}")
for spec in result.packages:
    print(f"\n{spec.package_name} ({spec.pin_count}-pin):")
    print(f"  Remove periphs: {spec.remove_peripherals}")
    print(f"  Remove instances: {spec.remove_instances}")
    print(f"  Trim fields: {spec.trim_fields}")
    print(f"  Trim reg arrays: {spec.trim_register_arrays}")
```

> Currently provides trim manifest analysis (`PackageTrimSpec`). The variant generator that auto-generates per-package SVDs from a master SVD is planned.

---

## dim Register Array Support

Full support for the CMSIS-SVD spec `dim`/`dimIncrement`/`dimIndex` trio:

| Level | Support |
|-------|---------|
| **Register** | ✅ Data model + parsing + generation + **configurable via edit dialog** |
| **Cluster** | ✅ Full support |
| **Field** | Data model supported, UI not exposed (rarely used per spec) |

The register edit dialog's "Register Array (dim)" group lets you toggle it on, configure count/increment/index (supports both `0-7` range and `0,1,2` comma syntax), with live preview of the generated dim tags.

---

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

### Datasheet Import Setup (Optional)

The datasheet import feature depends on the external [Parser](../Parser) package and its parsing libraries (missing these does not affect the editor itself; the import wizard will prompt to install):

```bash
# Parser package (editable install recommended)
pip install -e ../Parser

# Parser dependencies
pip install openpyxl python-docx pdfplumber pymupdf pyyaml

# pandoc (recommended for Word TRM three-stage parsing, for docx→markdown conversion)
# Install from https://pandoc.org, or: winget install pandoc
```

### MCP Server Setup (AI Client Access)

```bash
# Install optional MCP dependency
pip install mcp            # or: pip install -r requirements-mcp.txt

# Start (either way)
python run.py --mcp
python -m svd_tool.mcp_server
```

See the "AI Integration (MCP)" section above for client configuration. Set `PYTHONUTF8=1` on Windows.

---

## CLI Usage

<details>
<summary><b>Basic Commands</b></summary>

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

</details>

<details>
<summary><b>Advanced Commands</b></summary>

```bash
# Create SVD from JSON (DeviceInfo.to_dict() format)
python run.py create --data device_data.json -o chip.svd [--validate] [--open]

# Add peripherals from JSON
python run.py add-peripheral chip.svd --data peripheral.json -o updated.svd

# Remove peripherals
python run.py remove-peripheral chip.svd --name GPIOC,GPIOD -o updated.svd

# Update peripheral properties
python run.py update-peripheral chip.svd -n GPIOA --base-address 0x48010000 -o updated.svd

# Add register (from CLI args)
python run.py add-register chip.svd -p GPIOA --name IDR --offset 0x10 --desc "Input data" -o updated.svd

# Add register (from JSON)
python run.py add-register chip.svd -p GPIOA --data registers.json -o updated.svd

# Update register properties
python run.py update-register chip.svd -p GPIOA -n MODER --offset 0x08 --size 0x20 -o updated.svd

# Remove registers
python run.py remove-register chip.svd -p GPIOA --names OTYPER,OSPEEDR -o updated.svd

# Add bitfield (from CLI args)
python run.py add-field chip.svd -p GPIOA -r MODER --name MODE7 --bit-offset 14 --bit-width 2 -o updated.svd

# Update bitfield properties
python run.py update-field chip.svd -p GPIOA -r MODER -n MODE0 --bit-width 1 --access read-write -o updated.svd

# Remove bitfields
python run.py remove-field chip.svd -p GPIOA -r MODER --names MODE0,MODE1 -o updated.svd
```

</details>

<details>
<summary><b>GUI Mode</b></summary>

```bash
# Open GUI with a specific file
python run.py --gui --file chip.svd
```

</details>

---

## Keyboard Shortcuts (GUI)

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

---

## Project Structure

```
SVDEditor/
├── run.py                          # Entry point (GUI + CLI)
├── svd_tool/
│   ├── cli.py                      # CLI module (19 commands)
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
│   │   ├── document_manager.py     # Multi-document manager
│   │   ├── command_history.py      # Undo/Redo
│   │   └── datasource/             # Datasheet integration core layer
│   │       ├── parser_bridge.py        # Parser package bridge (threaded)
│   │       ├── trm_parser.py           # Word TRM three-stage parser
│   │       ├── chip_to_svd_converter.py # ChipData → DeviceInfo
│   │       ├── svd_verifier.py         # SVD verification engine
│   │       └── pinout_parser.py        # Datasheet pinout → package trim manifest
│   ├── mcp_server/                 # MCP Server (AI client access, no PyQt dependency)
│   │   ├── server.py                   # 30 MCP tool definitions + stdio entry
│   │   └── headless_workspace.py       # Headless multi-doc workspace (edit → explicit save)
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
│   │   │   ├── datasource_manager.py     # Datasheet import/verify orchestration
│   │   │   ├── command_executor.py       # Structured operation executor (op layer for the MCP GUI bridge)
│   │   │   ├── file_operations.py        # File I/O
│   │   │   └── register_manager.py       # Register management
│   │   ├── dialogs/
│   │   │   ├── chain_rules_dialog.py     # Chain rules editor
│   │   │   ├── svd_diff_merge_dialog.py  # Diff & merge dialog
│   │   │   ├── new_svd_wizard.py         # New file wizard
│   │   │   ├── import_wizard.py          # Datasheet import wizard
│   │   │   ├── fusion_review_dialog.py   # Multi-source fusion review
│   │   │   └── svd_verify_dialog.py      # SVD verification panel
│   │   └── widgets/
│   │       ├── bit_field_widget.py       # Bitfield visualization
│   │       ├── address_map_widget.py     # Address map
│   │       ├── document_tab_bar.py       # Multi-document tabs
│   │       └── welcome_page.py           # Welcome page
│   ├── config/
│   │   ├── about.json              # About dialog config
│   │   └── styles.py               # Theme/style system (dark/light)
│   └── i18n/
│       ├── i18n.py                 # i18n manager
│       ├── zh_CN.json              # Chinese translations
│       └── en_US.json              # English translations
├── docs/                           # Documentation
├── build_tools/                    # PyInstaller build scripts
├── test_data/                      # Test SVD files
└── tests/                          # Test suite
```

---

## Building

See [BUILD_INSTRUCTIONS.md](docs/BUILD_INSTRUCTIONS.md) for detailed build instructions.

```bash
pip install pyinstaller
cd build_tools
python build_professional_fixed.py
```

---

## License

GNU General Public License v3.0 - see [LICENSE](LICENSE) for details.

## Maintainer

- SamyiHu ([@SamyiHu](https://github.com/SamyiHu))

---

<div align="center">

**Enjoy using SVD Editor!**

[![English](https://img.shields.io/badge/English-US-blue?style=for-the-badge)](README.md)
[![中文](https://img.shields.io/badge/中文-CN-red?style=for-the-badge)](README_zh.md)

</div>
