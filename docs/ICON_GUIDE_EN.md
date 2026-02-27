# Icon Guide

## Icon File Requirements

### File Formats
- **Windows**: `.ico` format (required)
- **Linux**: `.png` or `.xpm` format
- **macOS**: `.icns` format

### Recommended Sizes
Include multiple sizes for best results:
- 16x16 pixels (taskbar, small icons)
- 32x32 pixels (medium icons)
- 48x48 pixels (large icons)
- 256x256 pixels (high resolution)

### Color Depth
- 32-bit color depth (with Alpha channel)
- Or 24-bit color depth (without Alpha channel)

## Methods to Get Icons

### Method 1: Use Online Tools
1. Visit online ICO conversion tools, such as:
   - https://convertio.co/zh/ico-converter/
   - https://icoconvert.com/
2. Upload PNG or SVG file
3. Download the generated ICO file
4. Rename to `icon.ico` and place in project root directory

### Method 2: Generate with Python (Simple Example)
```python
from PIL import Image, ImageDraw
import os

# Create a simple icon
def create_simple_icon():
    sizes = [(16, 16), (32, 32), (48, 48), (256, 256)]
    images = []
    
    for size in sizes:
        img = Image.new('RGBA', size, (70, 130, 180, 255))  # Steel blue background
        draw = ImageDraw.Draw(img)
        
        # Draw simple "SVD" text
        # You can add more complex graphics here
        
        images.append(img)
    
    # Save as ICO
    images[0].save('icon.ico', format='ICO', sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
    print("Icon created: icon.ico")

if __name__ == '__main__':
    create_simple_icon()
```

### Method 3: Use Professional Icon Editing Software
- **Windows**: GIMP, IcoFX, Axialis IconWorkshop
- **macOS**: Sketch, Figma, Icon Composer
- **Linux**: GIMP, Inkscape

## Icon Placement

Place the icon file in the project root directory:
```
SVDEditor/
├── icon.ico          # Windows icon (recommended)
├── icon.png         # Linux icon (optional)
├── icon.icns        # macOS icon (optional)
├── run.py
└── ...
```

## Build with Icon

### Using Build Script (Auto-detect)
```bash
cd build_tools
python build_professional_fixed.py
```

The build script will automatically detect and use the icon file.

### Manual Build
```bash
# Windows
python -m PyInstaller --icon=icon.ico --onefile --windowed --name SVDEditor run.py

# Linux
python -m PyInstaller --icon=icon.png --onefile --name SVDEditor run.py

# macOS
python -m PyInstaller --icon=icon.icns --onefile --windowed --name SVDEditor run.py
```

## Icon Design Tips

1. **Keep it simple**: Complex icons may not display well at small sizes
2. **Use high contrast**: Ensure visibility on different backgrounds
3. **Test at all sizes**: Verify appearance at 16x16, 32x32, 48x48, and 256x256
4. **Use vector graphics**: Start with SVG or high-resolution PNG for best quality
5. **Follow platform guidelines**: Each platform has its own icon design guidelines

## Troubleshooting

### Icon not showing
- Ensure the icon file is in the project root directory
- Check that the icon file name matches: `icon.ico` (Windows)
- Verify the icon file is not corrupted

### Icon looks blurry
- Ensure the icon file contains all required sizes
- Use high-resolution source images
- Test the icon at different display scales

### Build fails with icon error
- Verify the icon file format is correct
- Check that the icon file is not empty
- Try using a different icon creation tool
