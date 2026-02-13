# 分块加载架构文档

## 概述

分块加载架构是一种优化SVD文件处理性能的方案，通过将SVD文件按层级结构分块，实现按需加载和快速导航。

## 架构设计

### 块层级结构

```
Level 0: 设备信息 (DeviceInfo) - 始终加载
  └─ Level 1: 外设 (Peripheral) - 大块
      └─ Level 2: 寄存器 (Register) - 中块
          └─ Level 3: 位域 (Field) - 小块
```

### 核心组件

#### 1. BlockManager (块管理器)

**文件位置**: `svd_tool/core/block_manager.py`

**功能**:
- 管理所有块的加载状态
- 提供按需加载接口
- 维护块之间的引用关系
- 提供块导航功能

**主要方法**:
- `load_peripheral(peripheral_name)`: 加载外设块
- `load_register(peripheral_name, register_name)`: 加载寄存器块
- `load_field(peripheral_name, register_name, field_name)`: 加载位域块
- `navigate_to(block_key)`: 导航到指定块
- `get_next_block(block_key)`: 获取下一个块
- `get_previous_block(block_key)`: 获取上一个块
- `get_statistics()`: 获取统计信息

**使用示例**:
```python
from svd_tool.core.block_manager import BlockManager

# 创建块管理器
block_manager = BlockManager(device_info)

# 加载外设
block_manager.load_peripheral("GPIOA")

# 加载寄存器
block_manager.load_register("GPIOA", "MODER")

# 加载位域
block_manager.load_field("GPIOA", "MODER", "MODER0")

# 导航到块
block = block_manager.navigate_to("register:GPIOA:MODER")

# 获取统计信息
stats = block_manager.get_statistics()
print(f"已加载块数: {stats['loaded_blocks']}")
```

#### 2. ChunkedSVDParser (分块解析器)

**文件位置**: `svd_tool/core/chunked_svd_parser.py`

**功能**:
- 解析SVD文件并记录每个块的XML位置
- 支持按需解析特定块
- 缓存已解析的块
- 返回设备信息和块管理器

**主要方法**:
- `parse_file(file_path)`: 解析SVD文件
- `parse_string(xml_string)`: 解析SVD字符串
- `get_block_position(block_key)`: 获取块的XML位置

**使用示例**:
```python
from svd_tool.core.chunked_svd_parser import ChunkedSVDParser

# 创建分块解析器
parser = ChunkedSVDParser()

# 解析SVD文件
device_info, block_manager = parser.parse_file("device.svd")

# 获取块位置
position = parser.get_block_position("peripheral:GPIOA")
print(f"GPIOA位置: {position[0]}-{position[1]}行")
```

#### 3. ChunkedSVDGenerator (分块生成器)

**文件位置**: `svd_tool/core/chunked_svd_generator.py`

**功能**:
- 支持生成单个块的XML
- 支持生成多个块的组合XML
- 支持增量更新

**主要方法**:
- `generate_device_header()`: 生成设备头部XML
- `generate_peripheral_block(peripheral_name)`: 生成外设块XML
- `generate_register_block(peripheral_name, register_name)`: 生成寄存器块XML
- `generate_field_block(peripheral_name, register_name, field_name)`: 生成位域块XML
- `generate_visible_blocks()`: 生成所有可见块的组合XML
- `generate_blocks_by_keys(block_keys)`: 根据块key列表生成组合XML

**使用示例**:
```python
from svd_tool.core.chunked_svd_generator import ChunkedSVDGenerator

# 创建分块生成器
generator = ChunkedSVDGenerator(device_info, block_manager)

# 生成设备头部
device_header = generator.generate_device_header()

# 生成外设块
peripheral_xml = generator.generate_peripheral_block("GPIOA")

# 生成寄存器块
register_xml = generator.generate_register_block("GPIOA", "MODER")

# 生成可见块
visible_xml = generator.generate_visible_blocks()
```

#### 4. ChunkedPreviewWidget (分块预览组件)

**文件位置**: `svd_tool/ui/components/chunked_preview.py`

**功能**:
- 支持按需加载和显示
- 提供三种加载模式：可见、选中、全部
- 支持块导航

**加载模式**:
- `visible`: 只加载可见的块
- `selected`: 只加载选中的块
- `all`: 加载全部块

**主要方法**:
- `set_block_manager(block_manager)`: 设置块管理器
- `navigate_to_block(block_key)`: 导航到指定块
- `navigate_previous()`: 导航到上一个块
- `navigate_next()`: 导航到下一个块

**使用示例**:
```python
from svd_tool.ui.components.chunked_preview import ChunkedPreviewWidget

# 创建分块预览组件
preview = ChunkedPreviewWidget(state_manager, coordinator)

# 设置块管理器
preview.set_block_manager(block_manager)

# 导航到块
preview.navigate_to_block("register:GPIOA:MODER")
```

#### 5. BlockNavigatorWidget (块导航器)

**文件位置**: `svd_tool/ui/components/block_navigator.py`

**功能**:
- 提供树形结构的块导航
- 支持搜索和过滤
- 支持快速跳转

**主要方法**:
- `navigate_to_block(block_key)`: 导航到指定块
- `navigate_to_peripheral(peripheral_name)`: 导航到外设
- `navigate_to_register(peripheral_name, register_name)`: 导航到寄存器
- `navigate_to_field(peripheral_name, register_name, field_name)`: 导航到位域

**使用示例**:
```python
from svd_tool.ui.components.block_navigator import BlockNavigatorWidget

# 创建块导航器
navigator = BlockNavigatorWidget(block_manager)

# 导航到外设
navigator.navigate_to_peripheral("GPIOA")

# 导航到寄存器
navigator.navigate_to_register("GPIOA", "MODER")

# 导航到位域
navigator.navigate_to_field("GPIOA", "MODER", "MODER0")
```

## 工作流程

### 1. 导入SVD文件

```
用户选择SVD文件
    ↓
ChunkedSVDParser解析文件
    ↓
创建DeviceInfo和BlockManager
    ↓
初始化块结构（所有块都创建，但只有设备块被加载）
    ↓
显示设备信息
```

### 2. 用户展开外设

```
用户点击外设
    ↓
BlockManager.load_peripheral(peripheral_name)
    ↓
标记外设块为已加载
    ↓
ChunkedSVDGenerator生成外设块XML
    ↓
更新预览显示
```

### 3. 用户展开寄存器

```
用户点击寄存器
    ↓
BlockManager.load_register(peripheral_name, register_name)
    ↓
标记寄存器块为已加载
    ↓
ChunkedSVDGenerator生成寄存器块XML
    ↓
更新预览显示
```

### 4. 用户导航

```
用户点击导航按钮
    ↓
BlockManager.get_next_block() / get_previous_block()
    ↓
获取目标块
    ↓
BlockManager.navigate_to(block_key)
    ↓
更新预览显示
```

## 性能优势

### 1. 内存优化

- 只加载当前需要显示的内容
- 对于大型SVD文件，可以显著减少内存占用

### 2. 响应速度

- 用户操作时可以快速响应
- 不需要等待整个文件加载完成

### 3. 导航优化

- 可以直接跳转到对应的块
- 支持快速查找和过滤

## 测试

测试文件位置: `tests/test_chunked_loading.py`

运行测试:
```bash
python tests/test_chunked_loading.py
```

测试内容:
- 分块解析器测试
- 块管理器测试
- 分块生成器测试
- 集成测试

## 扩展性

### 添加新的块类型

1. 在 `BlockType` 枚举中添加新类型
2. 在 `BlockManager` 中添加加载方法
3. 在 `ChunkedSVDGenerator` 中添加生成方法
4. 在 `ChunkedPreviewWidget` 中添加显示逻辑

### 自定义加载策略

可以通过继承 `BlockManager` 并重写加载方法来实现自定义的加载策略。

## 注意事项

1. **块key格式**: 
   - 设备: `device`
   - 外设: `peripheral:{name}`
   - 寄存器: `register:{peripheral}:{name}`
   - 位域: `field:{peripheral}:{register}:{name}`

2. **加载顺序**: 
   - 加载子块前必须先加载父块
   - 例如：加载寄存器前必须先加载外设

3. **可见性管理**: 
   - 只有设置为可见的块才会被显示
   - 可以通过 `set_visible()` 方法控制

## 总结

分块加载架构通过将SVD文件按层级结构分块，实现了按需加载和快速导航，显著提升了大型SVD文件的处理性能。该架构具有良好的扩展性，可以根据需要添加新的块类型或自定义加载策略。
