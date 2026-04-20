# 图标指南 | Icon Guide

## 文件要求 | File Requirements

| Platform 平台 | Format 格式 |
|---|---|
| Windows | `.ico` (required / 必须) |
| Linux | `.png` or `.xpm` |
| macOS | `.icns` |

推荐尺寸 / Recommended sizes: 16x16, 32x32, 48x48, 256x256

颜色深度 / Color depth: 32-bit (with Alpha) or 24-bit

## 制作方法 | How to Create

### 在线工具 | Online Tools
Upload PNG/SVG → convert to ICO → rename to `icon.ico` → place in project root.
上传 PNG/SVG → 转为 ICO → 命名为 `icon.ico` → 放到项目根目录。

- https://convertio.co/zh/ico-converter/
- https://icoconvert.com/

### Python 生成 | Python Script
```python
from PIL import Image
sizes = [(16,16), (32,32), (48,48), (256,256)]
images = [Image.new('RGBA', s, (70, 130, 180, 255)) for s in sizes]
images[0].save('icon.ico', format='ICO', sizes=[(img.width, img.height) for img in images])
```

### 专业软件 | Professional Tools
GIMP (free), Inkscape (free), IcoFX (Windows)

## 放置位置 | Placement

```
project_root/
├── icon.ico    ← here / 这里
├── run.py
└── ...
```

## 构建时包含 | Build with Icon

构建脚本自动检测 / Build script auto-detects:
```bash
python build_windows.py
```

手动指定 / Manual:
```bash
python -m PyInstaller --icon=icon.ico --windowed --name SVDEditor run.py
```

## 故障排除 | Troubleshooting

| Problem 问题 | Solution 解决方案 |
|---|---|
| Icon not showing 图标不显示 | Check path and `.ico` format 检查路径和格式 |
| Icon looks blurry 图标模糊 | Include all sizes 包含所有尺寸 |
| Build error 构建报错 | Verify icon not corrupted 验证图标文件完整性 |
