# svd_tool/ui/model/device_tree_model.py
"""QAbstractItemModel 子类，包装 DeviceInfo 为 QTreeView 提供数据。
完全控制行移动（beginMoveRows/endMoveRows），支持懒加载。"""
from __future__ import annotations

from typing import Optional, List, Any

from PyQt6.QtCore import (
    Qt, QAbstractItemModel, QModelIndex, QMimeData, QByteArray,
)
from PyQt6.QtGui import QColor

from ...core.data_model import DeviceInfo, Peripheral, Register, Field
from ...i18n.i18n import t
from .tree_node import TreeNode


class DeviceTreeModel(QAbstractItemModel):
    """SVD 设备树模型

    三层结构：Peripheral → Register → Field
    数据存储在 DeviceInfo 中，TreeNode 只是轻量包装。
    """

    # 自定义 Role
    NodeTypeRole = Qt.ItemDataRole.UserRole       # str: "peripheral" | "register" | "field"
    NodeNameRole = Qt.ItemDataRole.UserRole + 1    # str: 节点名称
    NodePathRole = Qt.ItemDataRole.UserRole + 2    # str: 完整路径 "P/R/F"

    COLUMNS = 5
    HEADER_KEYS = [
        "label.name_column",
        "label.offset_column",
        "label.description_column",
        "label.access_column",
        "label.reset_value_column",
    ]

    def __init__(self, device_info: Optional[DeviceInfo] = None, parent=None):
        super().__init__(parent)
        self._device_info: DeviceInfo = device_info or DeviceInfo(name="", version="")
        self._root_nodes: List[TreeNode] = []
        self._compact_mode: bool = False  # 紧凑模式：不显示位域
        self._rebuild_root()

    # ================================================================
    # 数据绑定
    # ================================================================

    def set_device_info(self, device_info: DeviceInfo):
        """整体重置（文档切换 / undo/redo 后）"""
        self.beginResetModel()
        self._device_info = device_info
        self._rebuild_root()
        self.endResetModel()

    def device_info(self) -> DeviceInfo:
        return self._device_info

    def refresh_data(self):
        """仅刷新显示数据，不重建树结构（保留展开/折叠/fetched 状态）。
        当外设列表的名称和顺序未变，只是数据值变化时使用。
        调用前需确保 self._device_info 已更新。
        """
        # 对所有已加载的节点发射 dataChanged
        if not self._root_nodes:
            return

        # 顶层节点（外设）
        tl = self.index(0, 0)
        br = self.index(len(self._root_nodes) - 1, self.COLUMNS - 1)
        self.dataChanged.emit(tl, br)

        for i, root in enumerate(self._root_nodes):
            if root.fetched and root.children:
                pidx = self.createIndex(i, 0, root)
                tl2 = self.index(0, 0, pidx)
                br2 = self.index(len(root.children) - 1, self.COLUMNS - 1, pidx)
                self.dataChanged.emit(tl2, br2)

                for j, child in enumerate(root.children):
                    if child.fetched and child.children:
                        cidx = self.createIndex(j, 0, child)
                        tl3 = self.index(0, 0, cidx)
                        br3 = self.index(len(child.children) - 1, self.COLUMNS - 1, cidx)
                        self.dataChanged.emit(tl3, br3)

    def get_peripheral_order(self) -> List[str]:
        """获取当前外设名称列表（顺序即 dict 顺序）"""
        return [n.name for n in self._root_nodes]

    def is_structure_stale(self) -> bool:
        """检查已加载节点的子节点列表是否与 device_info 不一致。
        用于判断是否需要完整重建（而非仅刷新数据）。
        """
        for root in self._root_nodes:
            if not root.fetched:
                continue
            periph = self._device_info.peripherals.get(root.name)
            if periph is None:
                return True  # 外设被删除
            # 检查寄存器列表是否变化
            reg_names = [c.name for c in root.children]
            actual_regs = list(periph.registers.keys())
            if reg_names != actual_regs:
                return True
            # 检查已展开的寄存器的位域列表是否变化
            for reg_node in root.children:
                if not reg_node.fetched:
                    continue
                reg = periph.registers.get(reg_node.name)
                if reg is None:
                    return True  # 寄存器被删除
                field_names = [c.name for c in reg_node.children]
                actual_fields = list(reg.fields.keys())
                if field_names != actual_fields:
                    return True
        return False

    def set_compact_mode(self, compact: bool):
        """设置紧凑模式（不显示位域）。
        如果模式改变，重置模型并返回 True。调用者负责保存/恢复展开状态。
        如果模式未变，返回 False。
        """
        if self._compact_mode == compact:
            return False
        self._compact_mode = compact
        self.beginResetModel()
        self._rebuild_root()
        self.endResetModel()
        return True

    def _rebuild_root(self):
        """从 device_info.peripherals 重建顶层节点"""
        self._root_nodes.clear()
        for periph_name in self._device_info.peripherals:
            node = TreeNode("peripheral", periph_name)
            node._has_children_hint = bool(
                self._device_info.peripherals[periph_name].registers
                or self._device_info.peripherals[periph_name].clusters
            )
            self._root_nodes.append(node)

    # ================================================================
    # 数据解析
    # ================================================================

    def _resolve_data(self, node: TreeNode):
        """根据 TreeNode 路径查找对应的数据对象 (Peripheral/Register/Field)"""
        if node.node_type == "peripheral":
            return self._device_info.peripherals.get(node.name)
        elif node.node_type == "register":
            p = node.parent
            if p is None:
                return None
            periph = self._device_info.peripherals.get(p.name)
            return periph.registers.get(node.name) if periph else None
        elif node.node_type == "field":
            reg_node = node.parent
            if reg_node is None:
                return None
            periph_node = reg_node.parent
            if periph_node is None:
                return None
            periph = self._device_info.peripherals.get(periph_node.name)
            if not periph:
                return None
            reg = periph.registers.get(reg_node.name)
            return reg.fields.get(node.name) if reg else None
        return None

    # ================================================================
    # QAbstractItemModel 必选重写
    # ================================================================

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        if row < 0 or column < 0 or column >= self.COLUMNS:
            return QModelIndex()

        if not parent.isValid():
            # 顶层
            if row >= len(self._root_nodes):
                return QModelIndex()
            return self.createIndex(row, column, self._root_nodes[row])

        parent_node: TreeNode = parent.internalPointer()
        if parent_node is None:
            return QModelIndex()
        child = parent_node.child(row)
        if child is None:
            return QModelIndex()
        return self.createIndex(row, column, child)

    def parent(self, child: QModelIndex) -> QModelIndex:
        if not child.isValid():
            return QModelIndex()
        node: TreeNode = child.internalPointer()
        if node is None or node.parent is None:
            return QModelIndex()
        grandparent = node.parent.parent
        if grandparent is None:
            row = self._root_nodes.index(node.parent)
        else:
            row = grandparent.children.index(node.parent)
        return self.createIndex(row, 0, node.parent)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if not parent.isValid():
            return len(self._root_nodes)
        if parent.column() != 0:
            return 0
        node: TreeNode = parent.internalPointer()
        if node is None:
            return 0
        return node.child_count()

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return self.COLUMNS

    def hasChildren(self, parent: QModelIndex = QModelIndex()) -> bool:
        """重写以支持懒加载：未加载但有 _has_children_hint 的节点也报告有子节点。
        Qt 文档：如果实现了 canFetchMore/fetchMore，必须同时重写 hasChildren()。
        """
        if self.rowCount(parent) > 0:
            return True
        return self.canFetchMore(parent)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        node: TreeNode = index.internalPointer()
        if node is None:
            return None
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            return self._get_display_data(node, col)
        elif role == self.NodeTypeRole:
            return node.node_type
        elif role == self.NodeNameRole:
            return node.name
        elif role == self.NodePathRole:
            return node.path()
        elif role == Qt.ItemDataRole.ForegroundRole:
            # 可扩展：高亮等
            return None
        elif role == Qt.ItemDataRole.BackgroundRole:
            return None
        return None

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if orientation != Qt.Orientation.Horizontal:
            return None
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if 0 <= section < len(self.HEADER_KEYS):
            return t(self.HEADER_KEYS[section])
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.ItemIsDropEnabled  # 允许拖到空白区域
        base = (Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable)
        node: TreeNode = index.internalPointer()
        if node is None:
            return base
        if node.node_type == "peripheral":
            base |= Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsDropEnabled
        elif node.node_type == "field":
            base |= Qt.ItemFlag.ItemIsDragEnabled
        # register: 不可拖拽，不可放置
        return base

    # ================================================================
    # 显示数据
    # ================================================================

    def _get_display_data(self, node: TreeNode, column: int) -> str:
        obj = self._resolve_data(node)
        if obj is None:
            return ""

        if node.node_type == "peripheral":
            if column == 0:
                return obj.name
            elif column == 1:
                return obj.base_address
            elif column == 2:
                return obj.description
            elif column == 3:
                return ""
            elif column == 4:
                return ""

        elif node.node_type == "register":
            if column == 0:
                return obj.name
            elif column == 1:
                return obj.offset
            elif column == 2:
                return obj.description
            elif column == 3:
                return obj.access or ""
            elif column == 4:
                return obj.reset_value

        elif node.node_type == "field":
            if column == 0:
                return obj.name
            elif column == 1:
                return f"[{obj.bit_offset}:{obj.bit_offset + obj.bit_width - 1}]"
            elif column == 2:
                return obj.description or ""
            elif column == 3:
                return obj.access or ""
            elif column == 4:
                return obj.reset_value

        return ""

    # ================================================================
    # 懒加载
    # ================================================================

    def canFetchMore(self, parent: QModelIndex) -> bool:
        if not parent.isValid():
            return False
        node: TreeNode = parent.internalPointer()
        if node is None:
            return False
        if node.node_type == "peripheral" and not node.fetched and node._has_children_hint:
            return True
        if node.node_type == "register" and not node.fetched and node._has_children_hint:
            return True
        return False

    def fetchMore(self, parent: QModelIndex):
        node: TreeNode = parent.internalPointer()
        if node is None or node.fetched:
            return
        if node.node_type == "peripheral":
            self._populate_peripheral(node, parent)
        elif node.node_type == "register":
            self._populate_register(node, parent)
        node.mark_fetched()

    def _populate_peripheral(self, node: TreeNode, parent_idx: QModelIndex):
        periph = self._device_info.peripherals.get(node.name)
        if not periph:
            return
        children: List[TreeNode] = []
        for reg_name in periph.registers:
            child = TreeNode("register", reg_name, parent=node)
            # 紧凑模式下寄存器不显示位域展开箭头
            child._has_children_hint = (not self._compact_mode) and bool(periph.registers[reg_name].fields)
            children.append(child)
        if not children:
            return
        self.beginInsertRows(parent_idx, 0, len(children) - 1)
        node.children = children
        self.endInsertRows()

    def _populate_register(self, node: TreeNode, parent_idx: QModelIndex):
        reg_node = node
        periph_node = node.parent
        if periph_node is None:
            return
        periph = self._device_info.peripherals.get(periph_node.name)
        if not periph:
            return
        register = periph.registers.get(reg_node.name)
        if not register:
            return
        children: List[TreeNode] = []
        for field_name in register.fields:
            child = TreeNode("field", field_name, parent=reg_node)
            children.append(child)
        if not children:
            return
        self.beginInsertRows(parent_idx, 0, len(children) - 1)
        reg_node.children = children
        self.endInsertRows()

    # ================================================================
    # 强制展开路径（用于选择恢复时确保节点已加载）
    # ================================================================

    def ensure_fetched(self, index: QModelIndex):
        """确保 index 对应节点的子节点已加载"""
        if not index.isValid():
            return
        if self.canFetchMore(index):
            self.fetchMore(index)

    def find_index_by_path(self, path: str, column: int = 0) -> QModelIndex:
        """根据路径查找 QModelIndex，自动确保路径上的节点已加载。
        路径格式: "USART1" 或 "USART1/CR1" 或 "USART1/CR1/ENABLE"
        """
        parts = path.split("/")
        # 找顶层
        for i, root in enumerate(self._root_nodes):
            if root.name == parts[0]:
                idx = self.createIndex(i, column, root)
                if len(parts) == 1:
                    return idx
                # 展开并加载子节点
                self.ensure_fetched(idx)
                return self._find_child_recursive(idx, parts[1:], column)
        return QModelIndex()

    def _find_child_recursive(self, parent_idx: QModelIndex, parts: List[str],
                               column: int) -> QModelIndex:
        if not parts:
            return parent_idx
        parent_node: TreeNode = parent_idx.internalPointer()
        if parent_node is None:
            return QModelIndex()
        for i, child in enumerate(parent_node.children):
            if child.name == parts[0]:
                idx = self.createIndex(i, column, child)
                if len(parts) == 1:
                    return idx
                self.ensure_fetched(idx)
                return self._find_child_recursive(idx, parts[1:], column)
        return QModelIndex()

    # ================================================================
    # 行移动 API
    # ================================================================

    def move_peripheral(self, source_row: int, target_row: int):
        """移动外设行（source → target），同时更新 device_info dict 顺序

        target_row 语义：在原始列表中的目标插入位置。
        - "above row i"  → target_row = i
        - "below row i"  → target_row = i + 1
        """
        if source_row == target_row or source_row < 0 or target_row < 0:
            return
        if source_row >= len(self._root_nodes) or target_row > len(self._root_nodes):
            return

        # 同一位置（向下移动一格的 no-op）
        if source_row < target_row and source_row == target_row - 1:
            return

        # beginMoveRows：Qt 同一父节点移动时，destChild 使用原始坐标
        # Qt 内部会自动调整：destChild > sourceLast 时 actualDest = destChild - 1
        self.beginMoveRows(QModelIndex(), source_row, source_row,
                           QModelIndex(), target_row)

        node = self._root_nodes.pop(source_row)
        # 向下移动：pop 后索引左移，需 -1
        insert_at = target_row if source_row > target_row else target_row - 1
        self._root_nodes.insert(insert_at, node)

        self.endMoveRows()

        # 同步 device_info.peripherals 的 dict 顺序
        self._sync_peripheral_order()

    def move_field(self, source_row: int, target_row: int,
                   periph_name: str, reg_name: str):
        """移动位域行（source → target），在同一寄存器内"""
        # 找到寄存器节点
        reg_node = self._find_register_node(periph_name, reg_name)
        if reg_node is None:
            return
        if source_row == target_row:
            return
        if source_row < 0 or source_row >= len(reg_node.children):
            return
        if target_row < 0 or target_row > len(reg_node.children):
            return

        # 同一位置 no-op
        if source_row < target_row and source_row == target_row - 1:
            return

        reg_idx = self._index_from_node(reg_node)

        self.beginMoveRows(reg_idx, source_row, source_row,
                           reg_idx, target_row)

        node = reg_node.children.pop(source_row)
        insert_at = target_row if source_row > target_row else target_row - 1
        reg_node.children.insert(insert_at, node)

        self.endMoveRows()

        # 同步 register.fields dict 顺序
        self._sync_field_order(periph_name, reg_name, reg_node)

    def _find_register_node(self, periph_name: str, reg_name: str) -> Optional[TreeNode]:
        for root in self._root_nodes:
            if root.name == periph_name:
                if not root.fetched:
                    return None
                for child in root.children:
                    if child.name == reg_name:
                        return child
        return None

    def _sync_peripheral_order(self):
        """将 _root_nodes 的顺序同步到 device_info.peripherals"""
        new_order = [n.name for n in self._root_nodes]
        peripherals = self._device_info.peripherals
        reordered = {name: peripherals[name] for name in new_order if name in peripherals}
        self._device_info.peripherals = reordered

    def _sync_field_order(self, periph_name: str, reg_name: str, reg_node: TreeNode):
        """将 reg_node.children 顺序同步到 register.fields"""
        new_order = [n.name for n in reg_node.children]
        periph = self._device_info.peripherals.get(periph_name)
        if not periph:
            return
        register = periph.registers.get(reg_name)
        if not register:
            return
        fields = register.fields
        register.fields = {name: fields[name] for name in new_order if name in fields}

    # ================================================================
    # 获取顺序信息（用于 undo/redo）
    # ================================================================

    def get_field_order(self, periph_name: str, reg_name: str) -> List[str]:
        reg_node = self._find_register_node(periph_name, reg_name)
        if reg_node is None:
            return []
        return [n.name for n in reg_node.children]

    # ================================================================
    # 辅助方法
    # ================================================================

    def _node_from_index(self, index: QModelIndex) -> Optional[TreeNode]:
        if not index.isValid():
            return None
        return index.internalPointer()

    def _index_from_node(self, node: TreeNode, column: int = 0) -> QModelIndex:
        if node.parent is None:
            # 顶层节点
            try:
                row = self._root_nodes.index(node)
            except ValueError:
                return QModelIndex()
            return self.createIndex(row, column, node)
        else:
            return self.createIndex(node.row(), column, node)

    def get_peripheral_name(self, index: QModelIndex) -> Optional[str]:
        """获取 index 对应外设的名称（任何层级）"""
        node = self._node_from_index(index)
        if node is None:
            return None
        if node.node_type == "peripheral":
            return node.name
        elif node.node_type == "register":
            return node.parent.name if node.parent else None
        elif node.node_type == "field":
            reg = node.parent
            return reg.parent.name if reg and reg.parent else None
        return None

    def get_register_name(self, index: QModelIndex) -> Optional[str]:
        """获取 index 对应寄存器的名称（register 或 field 层级）"""
        node = self._node_from_index(index)
        if node is None:
            return None
        if node.node_type == "register":
            return node.name
        elif node.node_type == "field":
            return node.parent.name if node.parent else None
        return None

    def get_field_name(self, index: QModelIndex) -> Optional[str]:
        """获取 index 对应位域的名称"""
        node = self._node_from_index(index)
        if node is None or node.node_type != "field":
            return None
        return node.name

    # ================================================================
    # 拖放 MIME
    # ================================================================

    def supportedDropActions(self) -> Qt.DropAction:
        return Qt.DropAction.MoveAction

    def mimeTypes(self) -> List[str]:
        return ["application/x-svd-tree-node"]

    def mimeData(self, indexes: List[QModelIndex]) -> QMimeData:
        mime = QMimeData()
        if indexes:
            node = self._node_from_index(indexes[0])
            if node:
                mime.setData("application/x-svd-tree-node",
                             node.path().encode("utf-8"))
        return mime

    def dropMimeData(self, data: QMimeData, action: Qt.DropAction,
                     row: int, column: int, parent: QModelIndex) -> bool:
        # 不使用 Qt 默认的 drop 路径，由 DeviceTreeView 直接控制
        return False

    # ================================================================
    # 展开状态辅助
    # ================================================================

    def get_expanded_paths(self, tree_view) -> List[str]:
        """获取当前所有已展开节点的路径列表"""
        expanded = []
        for i, root in enumerate(self._root_nodes):
            idx = self.createIndex(i, 0, root)
            if tree_view.isExpanded(idx):
                expanded.append(root.name)
                if root.fetched:
                    for j, child in enumerate(root.children):
                        child_idx = self.createIndex(j, 0, child)
                        if tree_view.isExpanded(child_idx):
                            expanded.append(f"{root.name}/{child.name}")
        return expanded

    def restore_expanded(self, tree_view, paths: List[str]):
        """根据路径列表恢复展开状态"""
        path_set = set(paths)
        for i, root in enumerate(self._root_nodes):
            if root.name in path_set:
                idx = self.createIndex(i, 0, root)
                self.ensure_fetched(idx)
                tree_view.setExpanded(idx, True)
                if root.fetched:
                    for j, child in enumerate(root.children):
                        child_path = f"{root.name}/{child.name}"
                        if child_path in path_set:
                            child_idx = self.createIndex(j, 0, child)
                            self.ensure_fetched(child_idx)
                            tree_view.setExpanded(child_idx, True)
