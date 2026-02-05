# svd_tool/core/constants.py
# 常量定义

# SVD版本支持
SVD_VERSIONS = ["1.1", "1.3", "2.0"]

# 访问权限选项
ACCESS_OPTIONS = ["无", "read-write", "read-only", "write-only", "writeOnce", "read-writeOnce"]

# 默认值
DEFAULT_VALUES = {
    "peripheral": {
        "address_block_offset": "0x0",
        "address_block_size": "0x14",
        "address_block_usage": "registers"
    },
    "register": {
        "size": "0x20",
        "reset_value": "0x00000000",
        "reset_mask": "0xFFFFFFFF"
    },
    "field": {
        "reset_value": "0x0",
        "bit_width": 1
    }
}

# 颜色定义
COLORS = {
    "highlight": "#FFFF99",
    "error": "#FF6B6B",
    "success": "#4CAF50",
    "warning": "#FFA726",
    "info": "#2196F3"
}

# 树节点类型
NODE_TYPES = {
    "PERIPHERAL": "peripheral",
    "REGISTER": "register",
    "FIELD": "field"
}