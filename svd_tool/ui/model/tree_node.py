# svd_tool/ui/model/tree_node.py
"""轻量内部树节点，用于 DeviceTreeModel。
不依赖任何 QWidget，只持有结构信息和懒加载状态。"""
from __future__ import annotations
from typing import Optional, List


class TreeNode:
    """DeviceTreeModel 的内部节点"""

    __slots__ = ("node_type", "name", "parent", "children", "_fetched", "_has_children_hint")

    def __init__(self, node_type: str, name: str, parent: Optional["TreeNode"] = None):
        self.node_type: str = node_type          # "peripheral" | "register" | "field"
        self.name: str = name
        self.parent: Optional["TreeNode"] = parent
        self.children: List["TreeNode"] = []
        self._fetched: bool = False              # True 表示子节点已加载
        self._has_children_hint: bool = False    # True 表示可能有子节点（用于展开箭头）

    # ---- 子节点管理 ----

    def child(self, row: int) -> Optional["TreeNode"]:
        if 0 <= row < len(self.children):
            return self.children[row]
        return None

    def child_count(self) -> int:
        return len(self.children)

    def row(self) -> int:
        """本节点在父节点 children 列表中的索引"""
        if self.parent is not None:
            try:
                return self.parent.children.index(self)
            except ValueError:
                return 0
        return 0

    def append_child(self, child: "TreeNode"):
        child.parent = self
        self.children.append(child)

    def insert_child(self, position: int, child: "TreeNode"):
        child.parent = self
        self.children.insert(position, child)

    def remove_child(self, position: int) -> "TreeNode":
        child = self.children.pop(position)
        child.parent = None
        return child

    def clear_children(self):
        for c in self.children:
            c.parent = None
        self.children.clear()

    # ---- 懒加载 ----

    @property
    def fetched(self) -> bool:
        return self._fetched

    def mark_fetched(self):
        self._fetched = True

    # ---- 路径 ----

    def path(self) -> str:
        """返回从根到本节点的路径，例如 'USART1/CR1/ENABLE'"""
        parts: List[str] = []
        node: Optional["TreeNode"] = self
        while node is not None:
            parts.append(node.name)
            node = node.parent
        return "/".join(reversed(parts))

    def __repr__(self) -> str:
        return f"TreeNode({self.node_type!r}, {self.name!r})"
