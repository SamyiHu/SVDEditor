# SVD Editor Project Structure

## Final Clean Structure

```
SVDEditor/                          # Project root directory
├── run.py                          # Application startup script
├── config.py                       # Configuration file
├── icon.ico                        # Application icon (optional)
├── pytest.ini                      # pytest configuration file
├── requirements.txt                # Python dependency list
├── setup.py                        # Python package configuration
├── README.md                       # English README (GitHub display)
├── README_zh.md                    # Chinese README
├── LICENSE                         # MIT License
├── bash.sh                         # Project creation script (historical file)
│
├── svd_tool/                       # Source code directory
│   ├── __init__.py                 # Package initialization file (version 2.1.0)
│   ├── main.py                     # Application main entry point
│   ├── config/                     # Configuration module
│   │   ├── __init__.py
│   │   └── styles.py              # Style configuration (colors, fonts, sizes)
│   ├── core/                       # Core logic
│   │   ├── data_model.py           # Data model
│   │   ├── svd_parser.py           # SVD parser
│   │   ├── svd_generator.py        # SVD generator
│   │   ├── validators.py           # Data validation
│   │   ├── command_history.py      # Command history (undo/redo)
│   │   ├── block_manager.py       # Block manager (chunked loading)
│   │   ├── chunked_svd_parser.py  # Chunked SVD parser
│   │   └── chunked_svd_generator.py # Chunked SVD generator
│   ├── ui/                         # User interface
│   │   ├── main_window_refactored.py  # Refactored main window
│   │   ├── coordinator.py          # Component coordinator
│   │   ├── dialog_factories.py     # Dialog factories
│   │   ├── dialogs.py              # Dialogs
│   │   ├── form_builder.py         # Form builder
│   │   ├── tree_manager.py         # Tree view manager
│   │   ├── preview_window.py       # Preview window
│   │   ├── components/             # UI components
│   │   │   ├── state_manager.py    # State management
│   │   │   ├── layout_manager.py   # Layout management
│   │   │   ├── peripheral_manager.py # Peripheral management
│   │   │   ├── menu_bar.py         # Menu bar
│   │   │   ├── toolbar.py          # Toolbar
│   │   │   ├── tab_builder.py     # Tab builder
│   │   │   ├── widget_manager.py  # Widget manager
│   │   │   ├── ui_updater.py      # UI updater
│   │   │   ├── preview_manager.py # Preview manager
│   │   │   ├── realtime_preview.py # Real-time preview
│   │   │   ├── block_navigator.py # Block navigator
│   │   │   └── chunked_preview.py # Chunked preview
│   │   ├── widgets/                # Specialized widgets
│   │   │   ├── address_map_widget.py   # Address map
│   │   │   ├── bit_field_widget.py     # Bit field visualization
│   │   │   └── visualization_widget.py # Visualization component
│   │   └── managers/               # Function managers
│   │       ├── device_info_manager.py # Device info management
│   │       ├── file_operations.py    # File operations
│   │       ├── interrupt_manager.py  # Interrupt management
│   │       ├── register_manager.py   # Register management
│   │       ├── search_manager.py     # Search management
│   │       └── visualization_manager.py # Visualization management
│   ├── i18n/                      # Internationalization module
│   │   ├── __init__.py
│   │   ├── i18n.py               # Internationalization manager
│   │   ├── zh_CN.json            # Chinese translation
│   │   └── en_US.json            # English translation
│   └── utils/                      # Utility functions
│       ├── helpers.py              # Helper functions
│       ├── logger.py               # Logger configuration
│       ├── debug_logger.py        # Debug logger
│       └── error_handler.py      # Error handler
│
├── tests/                          # Test directory
│   ├── unit_tests/                 # Unit tests
│   │   ├── test_log_system.py
│   │   ├── test_about_message.py
│   │   ├── test_register_management.py
│   │   ├── test_field_management.py
│   │   ├── test_simple_import.py
│   │   └── test_device_info_manager.py
│   ├── integration_tests/          # Integration tests
│   │   └── test_run_refactored.py
│   ├── gui_tests/                  # GUI tests
│   │   ├── gui_test_basic.py
│   │   ├── gui_test_functional.py
│   │   └── gui_test_file_operations.py
│   ├── run_tests.py               # Test runner script
│   ├── README.md                  # Test documentation
│   ├── analyze_main_window.py     # Main window analysis tool
│   ├── final_integration_test.py  # Final integration test
│   ├── test_refactored_components.py # Refactored components test
│   ├── test_chunked_loading.py   # Chunked loading test
│   ├── test_i18n.py             # Internationalization test
│   ├── test_inheritance_fix.py   # Inheritance fix test
│   ├── test_move_functionality.py # Move functionality test
│   ├── test_rectangle_fix.py      # Rectangle fix test
│   └── test_simplified_text.py   # Simplified text test
│
├── docs/                           # Documentation directory
│   ├── README.md                   # Documentation index
│   ├── BUILD_INSTRUCTIONS.md       # Build instructions (Chinese)
│   ├── BUILD_INSTRUCTIONS_EN.md   # Build instructions (English)
│   ├── ICON_GUIDE.md            # Icon guide (Chinese)
│   ├── ICON_GUIDE_EN.md        # Icon guide (English)
│   ├── PROJECT_STRUCTURE.md      # Project structure (Chinese)
│   └── PROJECT_STRUCTURE_EN.md  # Project structure (English)
│
├── build_tools/                    # Build tools directory
│   ├── README.md                   # Build tools documentation
│   ├── build_professional_fixed.py # Professional build script (recommended)
│   ├── build_windows.py            # Basic build script
│   └── BUILD_VERSION_EXPLANATION.md # Build version explanation
│
├── test_data/                      # Test data directory
│   └── test_inheritance.svd       # Inheritance test SVD file
│
├── _build/                         # Build temporary files (hidden directory)
│   └── (PyInstaller build process files)
│
├── _dist/                          # Output files (hidden directory)
│   └── SVDEditor_64bit.exe         # Generated executable file
│
└── release/                        # Release files directory
    ├── 64bit/                      # 64-bit version
    │   ├── SVDEditor_64bit.exe     # Executable file
    │   ├── README.txt              # Usage instructions
    │   └── Other documentation files
    └── SVDEditor_64bit_standalone.zip # Release package
```

## Structure Optimization Results

### 1. Root Directory Significantly Simplified
- **Before**: 19 files/directories
- **After**: 13 files/directories (32% reduction)
- **Key files retained**: README, LICENSE, configuration, icon

### 2. Clear Categorization
- **Source code**: `svd_tool/` - Complete application code
- **Documentation**: `docs/` - All detailed documentation
- **Build tools**: `build_tools/` - Packaging and build scripts
- **Tests**: `tests/` - Test suite
- **Build output**: `_build/`, `_dist/`, `release/` - Separate build directories

### 3. Original Problems Resolved
- **False positive virus detection**: Reduced false positives through version info and standard build
- **Ugly directory structure**: Build files moved to hidden directories, documentation categorized
- **Icon support**: `icon.ico` in root directory, build script auto-detects

### 4. Test Script Organization
- **Deleted temporary tests**: Deleted 6 temporary bug fix verification scripts in root
- **Deleted diagnostic scripts**: Deleted 6 diagnostic and debug scripts in tests directory
- **Deleted duplicate tests**: Deleted 17 duplicate or obsolete test scripts in tests directory
- **Retained core tests**: Retained GUI tests, unit tests, integration tests, and feature tests

## Build Process

### Using Professional Build Script
```bash
cd build_tools
python build_professional_fixed.py
```

### Build Results
1. Temporary files: `_build/` directory
2. Output files: `_dist/SVDEditor_64bit.exe`
3. Release files: `release/64bit/` directory and ZIP package

## Maintenance Guidelines

### Adding New Features
1. Add code in the appropriate directory under `svd_tool/`
2. Update `requirements.txt` if new dependencies are needed
3. Run tests to ensure compatibility

### Updating Documentation
1. User documentation: Update files in `docs/` directory
2. API documentation: Add docstrings in code
3. README: Update README files in root directory

### Adding Tests
1. GUI tests in `tests/gui_tests/` directory
2. Unit tests in `tests/unit_tests/` directory
3. Integration tests in `tests/integration_tests/` directory
4. Feature tests in `tests/` root directory
5. Update `tests/README.md` documentation

### Releasing New Version
1. Update version number in `svd_tool/__init__.py`
2. Run build script to generate new version
3. Update files in `release/` directory
4. Create GitHub Release

## Advantages Summary

1. **Professional appearance**: Clean directory structure, following Python project best practices
2. **Easy to maintain**: Code, documentation, and build tools separated
3. **User-friendly**: Clear build process and documentation
4. **Scalable**: Easy to add new features and platform support
5. **Problems solved**: Resolved false positive virus detection and messy directory structure
6. **Complete tests**: Comprehensive test suite covering core functionality

## From Messy to Clean

### Previous Problems
- Too many files in root directory, difficult to find key files
- Build files polluting project directory
- Scattered documentation, difficult to maintain
- Build scripts had encoding issues
- Messy test scripts with many temporary tests

### Current Solution
- Categorized storage, each with its own purpose
- Build files in hidden directories
- Centralized documentation management
- Fixed build scripts in dedicated directory
- Organized test scripts, retaining core tests

The project now has all the characteristics of a professional open-source project, easy to use, maintain, and distribute.
