#!/bin/bash

echo "========================================"
echo "SVD Editor Build Script"
echo "========================================"
echo ""
echo "Build scripts have been moved to the 'build_tools/' directory."
echo ""
echo "Please use one of the following commands:"
echo ""
echo "1. For professional build (recommended):"
echo "   cd build_tools"
echo "   python build_professional_fixed.py"
echo ""
echo "2. For basic Windows build:"
echo "   cd build_tools"
echo "   python build_windows.py"
echo ""
echo "========================================"
echo ""
read -p "Would you like to run the professional build script now? (y/n): " choice

if [[ $choice =~ ^[Yy]$ ]]; then
    cd build_tools
    python build_professional_fixed.py
else
    echo ""
    echo "Please navigate to the build_tools directory manually."
fi