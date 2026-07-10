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

![AI Assistant](docs/screenshots/ai_assistant.png)
*Natural language interaction with SVD data*

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

### AI Assistant

The built-in AI assistant provides natural language interaction for SVD data operations. Simply describe what you want to do in plain language, and the AI will execute the corresponding operations.

**Key Capabilities:**

| Capability | Example |
|------------|---------|
| **Query & Search** | "Show me all peripherals", "Find registers with offset 0x10" |
| **CRUD Operations** | "Add a new peripheral named TIMER0", "Delete register MODER" |
| **Validation** | "Validate this SVD file", "Check for address conflicts" |
| **Batch Operations** | "Rename all GPIO peripherals", "Fix all address conflicts" |
| **Multi-document** | "Switch to STM32F4.svd", "Diff with the other open file" |
| **Navigation** | "Jump to UART1", "Show register MODER in GPIOA" |
| **Datasheet Import** | "Parse this Word manual and import as SVD", "Verify current SVD against the manual to find missing registers" |

**Supported Providers:**
- OpenAI (GPT-4o, GPT-4o-mini, etc.)
- Anthropic (Claude 3.5 Sonnet, Claude 3 Haiku, etc.)
- Any OpenAI-compatible API (Ollama, vLLM, etc.)

**Configuration:**
- API key and endpoint configuration via Settings dialog
- Streaming response support
- Custom system prompt extensions
- Conversation history management

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
| `create` | **Create new SVD from JSON data** (e.g. from AIfull_link) |
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

## AIfull_link Integration

Create SVD files directly from [AIfull_link](https://github.com/SamyiHu/AIfull_link) parsed register data:

```bash
# 1. In AIfull_link, export register data as JSON
#    (use export_svd tool in Agent Shell)

# 2. Create SVD from the exported JSON
python run.py create --data scf10t_svd_data.json -o SCF10T.svd --validate

# 3. Open in GUI for visual editing
python run.py --gui --file SCF10T.svd
```

The JSON format is compatible with `DeviceInfo.to_dict()` output. See `data_model.py` for schema details.

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

### AI Assistant Setup

```bash
# Install optional AI dependencies
pip install openai anthropic

# Configure API key (via GUI Settings or environment variable)
export OPENAI_API_KEY="your-api-key"
```

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
# Create SVD from JSON (e.g. exported from AIfull_link)
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
│   ├── ai_assistant/
│   │   ├── __init__.py             # Module entry
│   │   ├── config.py               # AI configuration
│   │   ├── backend.py              # API backend (OpenAI/Anthropic)
│   │   ├── controller.py           # AI controller
│   │   ├── prompt_builder.py       # System prompt builder
│   │   ├── command_executor.py     # Operation executor
│   │   ├── chat_history.py         # Chat history management
│   │   └── widgets/
│   │       ├── chat_panel.py       # Chat panel UI
│   │       ├── chat_bubble.py      # Chat bubble widget
│   │       └── settings_dialog.py  # AI settings dialog
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
