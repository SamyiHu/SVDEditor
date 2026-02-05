# 图标指南

## 图标文件要求

### 文件格式
- **Windows**: `.ico` 格式（必须）
- **Linux**: `.png` 或 `.xpm` 格式
- **macOS**: `.icns` 格式

### 推荐尺寸
包含多种尺寸以获得最佳效果：
- 16x16 像素（任务栏、小图标）
- 32x32 像素（中等图标）
- 48x48 像素（大图标）
- 256x256 像素（高分辨率）

### 颜色深度
- 32位色深（带Alpha通道）
- 或 24位色深（不带Alpha通道）

## 获取图标的方法

### 方法1：使用在线工具
1. 访问在线ICO转换工具，如：
   - https://convertio.co/zh/ico-converter/
   - https://icoconvert.com/
2. 上传PNG或SVG文件
3. 下载生成的ICO文件
4. 重命名为 `icon.ico` 并放在项目根目录

### 方法2：使用Python生成（简单示例）
```python
from PIL import Image, ImageDraw
import os

# 创建简单的图标
def create_simple_icon():
    sizes = [(16, 16), (32, 32), (48, 48), (256, 256)]
    images = []
    
    for size in sizes:
        img = Image.new('RGBA', size, (70, 130, 180, 255))  # 钢蓝色背景
        draw = ImageDraw.Draw(img)
        
        # 绘制简单的"SVD"文字
        # 这里可以添加更复杂的图形
        
        images.append(img)
    
    # 保存为ICO
    images[0].save('icon.ico', format='ICO', sizes=[(img.width, img.height) for img in images])
    print("已创建 icon.ico")

if __name__ == '__main__':
    create_simple_icon()
```

### 方法3：使用专业软件
- Adobe Illustrator
- GIMP（免费）
- Inkscape（免费）
- IcoFX（Windows专用）

## 图标放置位置

将图标文件放在项目根目录：
```
SVDEditor/
├── icon.ico    <-- 放在这里
├── run.py
├── config.py
└── ...
```

## 构建时包含图标

### 使用构建脚本
```bash
# 如果有 icon.ico 文件，构建脚本会自动包含
python build_professional.py
```

### 手动构建
```bash
# 指定图标文件
python -m PyInstaller --icon=icon.ico --onefile --windowed --name SVDEditor run.py
```

## 验证图标

构建后，通过以下方式验证图标：

1. **Windows资源管理器**：查看EXE文件的图标
2. **文件属性**：右键 -> 属性 -> 详细信息
3. **任务栏**：运行程序时在任务栏显示的图标
4. **应用程序窗口**：窗口左上角的图标

## 故障排除

### 图标未显示
1. 检查图标文件路径是否正确
2. 确认图标格式为 `.ico`
3. 尝试重新构建
4. 清除Windows图标缓存
   ```bash
   ie4uinit.exe -show
   ```

### 图标质量差
1. 确保包含多种尺寸
2. 使用高分辨率源图像
3. 避免过度压缩

### 构建错误
1. 确保安装了PIL/Pillow（如果使用Python生成）
2. 检查图标文件是否损坏
3. 尝试使用不同的图标文件

## 推荐图标设计

### 颜色方案
- 主色：蓝色系（代表技术、专业）
- 辅助色：灰色、白色
- 避免使用太多颜色

### 图形元素
- SVD相关元素（芯片、寄存器、二进制）
- 简洁的几何图形
- 清晰的字母"SVD"

### 示例设计思路
1. 芯片轮廓 + "SVD"文字
2. 二进制代码背景 + 编辑工具图标
3. 寄存器表格图形 + 放大镜

## 注意事项

1. **版权**：确保拥有图标的使用权
2. **一致性**：保持与应用程序风格一致
3. **可识别性**：图标应易于识别
4. **测试**：在不同背景下测试图标可见性

## 快速开始

如果没有图标文件，可以：
1. 使用上面的Python代码生成简单图标
2. 从免费图标网站下载
3. 暂时不使用图标（应用程序将使用默认图标）

建议至少提供一个简单的图标，以提升应用程序的专业性。