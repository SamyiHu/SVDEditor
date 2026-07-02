# svd_tool/ui/widgets/device_tree_view.py
"""QTreeView 子类，提供：
1. 自绘彩色拖拽指示器（带脉冲动画的插入线 + 半透明预览行）
2. 完全自行控制的拖放验证和执行
3. 与 DeviceTreeModel 配合的行移动 + undo/redo
"""
from __future__ import annotations

from math import sin, pi
from typing import Optional

from PyQt6.QtCore import Qt, QRect, QPoint, QModelIndex, QTimer, QElapsedTimer
from PyQt6.QtGui import (QPainter, QPen, QColor, QBrush, QLinearGradient,
                          QPainterPath, QFont, QPixmap)
from PyQt6.QtWidgets import (
    QTreeView, QAbstractItemView, QHeaderView, QApplication,
)

from ..model.device_tree_model import DeviceTreeModel
from ...i18n.i18n import t


class DeviceTreeView(QTreeView):
    """SVD 设备树视图 — 自定义拖拽反馈"""

    def __init__(self, parent=None):
        super().__init__(parent)

        # ---- 拖拽配置 ----
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(False)   # 不用 Qt 默认指示器，自绘
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setUniformRowHeights(True)
        self.setAlternatingRowColors(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        # ---- 列宽策略 ----
        # 注意：setSectionResizeMode 在 model 尚未绑定（section 不存在）时会静默失效，
        # 因此 __init__ 里只设不依赖 section 的属性，真正的 resize mode 在
        # _apply_column_policy()（setModel 后调用）里设。
        self.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.header().setMinimumSectionSize(60)

        # ---- 拖拽状态 ----
        self._drop_indicator_rect = QRect()
        self._drop_indicator_valid = False
        self._drop_target_row = -1
        self._drop_position: Optional[str] = None   # "above" | "below" | "onto"
        self._drag_source_type: Optional[str] = None
        self._drag_source_path: Optional[str] = None

        # ---- 动画 ----
        self._anim_color = QColor("#4A90D9")
        self._anim_color_invalid = QColor("#D94A4A")
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(16)  # ~60fps
        self._anim_timer.timeout.connect(self._anim_tick)
        self._anim_elapsed = QElapsedTimer()
        self._anim_phase = 0.0

        # ---- 源项预览 ----
        self._source_pixmap: Optional[QPixmap] = None

    # ================================================================
    # Model 访问辅助
    # ================================================================

    def _model(self) -> Optional[DeviceTreeModel]:
        m = self.model()
        if isinstance(m, DeviceTreeModel):
            return m
        return None

    def setModel(self, model):
        """重写：绑定 model 后再应用列宽策略。

        关键修复：setSectionResizeMode 在 model 尚未绑定（header 无真实 section）时
        会静默失效（读回变 Fixed/默认），导致 __init__ 里设的 ResizeToContents 根本
        没生效——表现为名称列被省略成 IA/RCC_AP。改为在 setModel 后（section 已存在）
        调用 _apply_column_policy()，确保 resize mode 真正写入。
        """
        super().setModel(model)
        if model is not None:
            self._apply_column_policy()

    def _apply_column_policy(self):
        """应用列宽策略（必须在 model 已绑定、section 真实存在后调用）。

        名称列(0)：ResizeToContents —— 依据 model 的 SizeHintRole（见
          device_tree_model._name_size_hint）按"文字宽+缩进"算列宽，深嵌套寄存器/
          位域名也能完整显示。
        offset/access/reset 列(1/3/4)：Interactive 固定宽度（数值列，可手动拖）。
        描述列(2)：Interactive + 默认省略（描述常很长，不全展开，超出 ElideRight）。
        末列 stretch 兜底：名称列 ResizeToContents 撑开后视口若有剩余，由末列吸收，
          避免右侧出现空白区。
        """
        header = self.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        header.resizeSection(1, 100)   # offset
        header.resizeSection(2, 200)   # description（默认省略，可拖宽）
        header.resizeSection(3, 80)    # access
        header.resizeSection(4, 80)    # reset value
        header.setMinimumSectionSize(60)
        header.setStretchLastSection(True)
        self.setTextElideMode(Qt.TextElideMode.ElideRight)

    # ================================================================
    # 动画
    # ================================================================

    def _anim_tick(self):
        self._anim_phase = (self._anim_elapsed.elapsed() % 2000) / 2000.0
        self.viewport().update()

    def _pulse_alpha(self) -> float:
        """脉冲因子 0.4 ~ 1.0，用于指示器呼吸效果"""
        return 0.7 + 0.3 * sin(self._anim_phase * 2 * pi)

    def _start_anim(self):
        self._anim_phase = 0.0
        self._anim_elapsed.start()
        self._anim_timer.start()

    def _stop_anim(self):
        self._anim_timer.stop()

    # ================================================================
    # 自绘拖拽指示器
    # ================================================================

    def _repaint_rows(self, *rows):
        """已弃用：纯 QSS image 方案后 chevron 由 QSS 绘制，无需 hover 重绘。
        保留空实现仅为兼容（不应再被调用）。
        """
        return

    def paintEvent(self, event):
        """先画默认内容，再叠加拖拽指示器"""
        super().paintEvent(event)

        if not self._drop_indicator_valid or self._drop_indicator_rect.isNull():
            return

        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pulse = self._pulse_alpha()
        r = self._drop_indicator_rect

        if self._drop_position in ("above", "below"):
            self._paint_insert_line(painter, r, pulse)
        elif self._drop_position == "onto":
            self._paint_onto_highlight(painter, r, pulse)

        painter.end()

    def _paint_insert_line(self, painter: QPainter, r: QRect, pulse: float):
        """绘制插入指示线：渐变色线 + 三角箭头 + 半透明预览行"""
        y = r.top() if self._drop_position == "above" else r.bottom()

        # 1) 半透明预览行（显示源项将插入的位置）
        if self._source_pixmap:
            preview_h = self._source_pixmap.height()
            preview_y = y - preview_h // 2 if self._drop_position == "above" else y - preview_h // 2
            preview_rect = QRect(r.left(), preview_y, r.width(), preview_h)

            # 裁剪到 viewport
            painter.save()
            painter.setClipRect(self.viewport().rect())

            # 绘制半透明背景
            bg = QColor(self._anim_color)
            bg.setAlpha(int(25 * pulse))
            painter.fillRect(preview_rect, bg)

            # 绘制源项缩略图
            p = QPixmap(self._source_pixmap)
            p.setDevicePixelRatio(self.devicePixelRatio())
            tmp = QPainter(p)
            tmp.setOpacity(0.35 * pulse)
            tmp.end()
            painter.setOpacity(0.35 * pulse)
            painter.drawPixmap(preview_rect, self._source_pixmap)
            painter.setOpacity(1.0)

            painter.restore()

        # 2) 渐变插入线
        grad = QLinearGradient(r.left(), y, r.right(), y)
        c = QColor(self._anim_color)
        c.setAlphaF(pulse)
        grad.setColorAt(0.0, QColor(c.red(), c.green(), c.blue(), int(40 * pulse)))
        grad.setColorAt(0.1, c)
        grad.setColorAt(0.9, c)
        grad.setColorAt(1.0, QColor(c.red(), c.green(), c.blue(), int(40 * pulse)))

        pen = QPen(QBrush(grad), 3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(r.left() + 20, y, r.right() - 10, y)

        # 3) 左侧三角箭头
        arrow_size = 8
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(c)
        if self._drop_position == "above":
            tri = QPainterPath()
            tri.moveTo(r.left(), y)
            tri.lineTo(r.left() + arrow_size, y - arrow_size // 2)
            tri.lineTo(r.left() + arrow_size, y + arrow_size // 2)
            tri.closeSubpath()
            painter.drawPath(tri)
        else:
            tri = QPainterPath()
            tri.moveTo(r.left(), y)
            tri.lineTo(r.left() + arrow_size, y - arrow_size // 2)
            tri.lineTo(r.left() + arrow_size, y + arrow_size // 2)
            tri.closeSubpath()
            painter.drawPath(tri)

        # 4) 右侧圆点
        painter.drawEllipse(QPoint(r.right() - 5, y), 3, 3)

        # 5) 目标位置文字提示
        if self._drop_target_row >= 0:
            painter.setPen(QColor(c.red(), c.green(), c.blue(), int(180 * pulse)))
            font = painter.font()
            font.setPointSize(font.pointSize() - 1)
            painter.setFont(font)
            target_text = f"#{self._drop_target_row}"
            painter.drawText(r.right() - 50, y - 6, target_text)

    def _paint_onto_highlight(self, painter: QPainter, r: QRect, pulse: float):
        """绘制 onto 高亮（半透明覆盖 + 圆角边框）"""
        fill = QColor(self._anim_color)
        fill.setAlpha(int(35 * pulse))
        painter.fillRect(r, fill)

        pen = QPen(self._anim_color, 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        alpha_color = QColor(self._anim_color)
        alpha_color.setAlpha(int(200 * pulse))
        pen.setColor(alpha_color)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(r.adjusted(2, 1, -2, -1), 4, 4)

    # ================================================================
    # 拖拽事件
    # ================================================================

    def startDrag(self, supportedActions):
        """拖拽源生成前的拦截点。
        排序是单选语义（把一个项插到某位置），多选拖拽排序语义混乱（多个项
        要插到哪、相对顺序如何均无定义）。故：选中了不止一个节点时直接不生成
        拖拽源，强制用户先单选。拖拽预览也不会出现，反馈一致。
        """
        # 按行去重计数（SelectRows 下同一行也可能返回多个列 index）
        selected = self.selectedIndexes()
        if selected:
            unique_rows = {(idx.parent(), idx.row()) for idx in selected}
            if len(unique_rows) > 1:
                return  # 多选：阻止拖拽
        super().startDrag(supportedActions)

    def dragEnterEvent(self, event):
        m = self._model()
        if m is None:
            event.ignore()
            return
        indexes = self.selectedIndexes()
        if not indexes:
            event.ignore()
            return
        node = m._node_from_index(indexes[0])
        if node is None or node.node_type not in ("peripheral", "register", "field"):
            event.ignore()
            return
        self._drag_source_type = node.node_type
        self._drag_source_path = node.path()

        # 捕获源行截图用于预览
        self._capture_source_pixmap(indexes[0])

        self._start_anim()
        event.acceptProposedAction()

    def dragMoveEvent(self, event):
        m = self._model()
        if m is None:
            event.ignore()
            self._clear_drop_indicator()
            self.viewport().update()
            return
        pos = event.position().toPoint()
        target_idx = self.indexAt(pos)

        self._clear_drop_indicator()

        if not self._is_valid_drop(target_idx, pos):
            event.ignore()
            self.viewport().update()
            return

        self._compute_drop_indicator(target_idx, pos)
        event.acceptProposedAction()
        self.viewport().update()

    def dragLeaveEvent(self, event):
        self._clear_drop_indicator()
        self._stop_anim()
        self._source_pixmap = None
        self.viewport().update()

    def dropEvent(self, event):
        m = self._model()
        if m is None:
            event.ignore()
            return

        pos = event.position().toPoint()
        target_idx = self.indexAt(pos)

        if self._drag_source_type == "peripheral":
            self._execute_peripheral_drop(m, target_idx, pos)
        elif self._drag_source_type == "register":
            self._execute_register_drop(m, target_idx, pos)
        elif self._drag_source_type == "field":
            self._execute_field_drop(m, target_idx, pos)

        self._clear_drop_indicator()
        self._stop_anim()
        self._source_pixmap = None
        event.acceptProposedAction()

    # ================================================================
    # 源项截图
    # ================================================================

    def _capture_source_pixmap(self, index: QModelIndex):
        """捕获源行的截图用于拖拽预览"""
        rect = self.visualRect(index)
        if rect.isValid():
            self._source_pixmap = self.viewport().grab(rect)
        else:
            self._source_pixmap = None

    # ================================================================
    # 拖拽验证
    # ================================================================

    def _is_valid_drop(self, target_idx: QModelIndex, pos: QPoint) -> bool:
        m = self._model()
        if m is None:
            return False
        source_type = self._drag_source_type

        if source_type == "peripheral":
            if not target_idx.isValid():
                return True  # 拖到底部空白区域
            node = m._node_from_index(target_idx)
            return node is not None and node.node_type == "peripheral"

        elif source_type == "register":
            # 寄存器只能在外设内重排
            if not target_idx.isValid():
                return False
            node = m._node_from_index(target_idx)
            if node is None:
                return False
            source_indexes = self.selectedIndexes()
            if not source_indexes:
                return False
            source_node = m._node_from_index(source_indexes[0])
            if source_node is None:
                return False
            if node.node_type == "register":
                # 必须同一外设
                return source_node.parent is node.parent
            elif node.node_type == "peripheral":
                # 拖到外设节点上（该外设就是源寄存器的外设）
                return source_node.parent is node
            return False

        elif source_type == "field":
            if not target_idx.isValid():
                return False
            node = m._node_from_index(target_idx)
            if node is None:
                return False
            if node.node_type == "field":
                # 必须同一寄存器
                source_indexes = self.selectedIndexes()
                if not source_indexes:
                    return False
                source_node = m._node_from_index(source_indexes[0])
                return source_node is not None and source_node.parent is node.parent
            elif node.node_type == "register":
                source_indexes = self.selectedIndexes()
                if not source_indexes:
                    return False
                source_node = m._node_from_index(source_indexes[0])
                return source_node is not None and source_node.parent is node
            return False

        return False

    # ================================================================
    # 指示器计算
    # ================================================================

    def _compute_drop_indicator(self, target_idx: QModelIndex, pos: QPoint):
        m = self._model()
        if m is None:
            return

        if not target_idx.isValid():
            # 拖到底部
            row_count = m.rowCount()
            if row_count > 0:
                last_rect = self.visualRect(m.index(row_count - 1, 0))
                self._drop_indicator_rect = QRect(
                    last_rect.left(), last_rect.bottom(),
                    self.viewport().width(), 0)
                self._drop_target_row = row_count
                self._drop_position = "below"
            else:
                self._drop_target_row = 0
                self._drop_position = "above"
            self._drop_indicator_valid = True
            return

        target_rect = self.visualRect(target_idx)
        threshold = target_rect.height() / 3.0
        relative_y = pos.y() - target_rect.top()

        if relative_y < threshold:
            # 上方插入
            self._drop_indicator_rect = QRect(
                target_rect.left(), target_rect.top(),
                self.viewport().width(), 0)
            self._drop_target_row = target_idx.row()
            self._drop_position = "above"
        elif relative_y > target_rect.height() - threshold:
            # 下方插入
            self._drop_indicator_rect = QRect(
                target_rect.left(), target_rect.bottom(),
                self.viewport().width(), 0)
            self._drop_target_row = target_idx.row() + 1
            self._drop_position = "below"
        else:
            # 放到项目上（高亮）
            self._drop_indicator_rect = target_rect
            self._drop_target_row = target_idx.row()
            self._drop_position = "onto"

        self._drop_indicator_valid = True

    def _clear_drop_indicator(self):
        self._drop_indicator_valid = False
        self._drop_indicator_rect = QRect()
        self._drop_target_row = -1
        self._drop_position = None

    # ================================================================
    # Drop 执行
    # ================================================================

    def _execute_peripheral_drop(self, m: DeviceTreeModel,
                                  target_idx: QModelIndex, pos: QPoint):
        source_indexes = self.selectedIndexes()
        if not source_indexes:
            return
        source_idx = source_indexes[0]
        source_node = m._node_from_index(source_idx)
        if source_node is None:
            return
        # 必须用 QModelIndex.row()，不能用 TreeNode.row()
        # TreeNode.row() 对顶层节点永远返回 0（parent is None）
        source_row = source_idx.row()

        # 计算 target_row
        if self._drop_position == "above":
            target_row = self._drop_target_row
        elif self._drop_position == "below":
            target_row = self._drop_target_row
        elif self._drop_position == "onto":
            target_row = target_idx.row() + 1
        else:
            return

        # 跳过无效移动（同一位置或相邻向下）
        if source_row == target_row:
            return
        if source_row < target_row and source_row == target_row - 1:
            return

        # 保存旧顺序（undo 用）
        old_order = m.get_peripheral_order()

        # 执行移动
        m.move_peripheral(source_row, target_row)

        # 新顺序
        new_order = m.get_peripheral_order()

        if old_order != new_order:
            self._record_peripheral_reorder(m, source_node.name, old_order, new_order)

    def _execute_field_drop(self, m: DeviceTreeModel,
                             target_idx: QModelIndex, pos: QPoint):
        source_indexes = self.selectedIndexes()
        if not source_indexes:
            return
        source_idx = source_indexes[0]
        source_node = m._node_from_index(source_idx)
        if source_node is None or source_node.parent is None:
            return
        reg_node = source_node.parent
        periph_node = reg_node.parent
        if periph_node is None:
            return

        periph_name = periph_node.name
        reg_name = reg_node.name
        # 用 QModelIndex.row() 获取正确的行号
        source_row = source_idx.row()

        # 计算 target_row
        if self._drop_position == "above":
            target_row = self._drop_target_row
        elif self._drop_position == "below":
            target_row = self._drop_target_row
        elif self._drop_position == "onto":
            target_row = target_idx.row() + 1
        else:
            return

        if source_row == target_row:
            return

        old_order = m.get_field_order(periph_name, reg_name)

        m.move_field(source_row, target_row, periph_name, reg_name)

        new_order = m.get_field_order(periph_name, reg_name)

        if old_order != new_order:
            self._record_field_reorder(m, source_node.name,
                                       periph_name, reg_name,
                                       old_order, new_order)

    def _execute_register_drop(self, m: DeviceTreeModel,
                                target_idx: QModelIndex, pos: QPoint):
        """执行寄存器拖放重排序（同一外设内）。与 _execute_field_drop 平行。"""
        source_indexes = self.selectedIndexes()
        if not source_indexes:
            return
        source_idx = source_indexes[0]
        source_node = m._node_from_index(source_idx)
        if source_node is None or source_node.parent is None:
            return
        periph_node = source_node.parent
        periph_name = periph_node.name
        # 用 QModelIndex.row() 获取正确的行号
        source_row = source_idx.row()

        # 计算 target_row
        if self._drop_position == "above":
            target_row = self._drop_target_row
        elif self._drop_position == "below":
            target_row = self._drop_target_row
        elif self._drop_position == "onto":
            # 拖到外设节点上：放到该外设末尾
            target_row = len(periph_node.children)
        else:
            return

        if source_row == target_row:
            return

        old_order = m.get_register_order(periph_name)

        m.move_register(source_row, target_row, periph_name)

        new_order = m.get_register_order(periph_name)

        if old_order != new_order:
            self._record_register_reorder(m, source_node.name,
                                          periph_name, old_order, new_order)

    # ================================================================
    # undo/redo 记录
    # ================================================================

    def _record_peripheral_reorder(self, m: DeviceTreeModel, source_name: str,
                                    old_order: list, new_order: list):
        """记录外设重排序到命令历史"""
        try:
            from ..components.state_manager import StateManager
            state_mgr = self._find_state_manager()
            if state_mgr is None:
                return

            captured_old = old_order[:]
            captured_new = new_order[:]

            def execute_reorder():
                peripherals = state_mgr.device_info.peripherals
                reordered = {name: peripherals[name]
                             for name in captured_new if name in peripherals}
                state_mgr.device_info.peripherals = reordered
                state_mgr._notify_state_change()
                return True

            def undo_reorder():
                peripherals = state_mgr.device_info.peripherals
                reordered = {name: peripherals[name]
                             for name in captured_old if name in peripherals}
                state_mgr.device_info.peripherals = reordered
                state_mgr._notify_state_change()
                return True

            from ...core.command_history import Command
            command = Command(
                execute=execute_reorder,
                undo=undo_reorder,
                description=t("status.periph_reordered", name=source_name)
                           if "status.periph_reordered" in t.__wrapped__
                           else f"拖放调整外设顺序: {source_name}",
            )
            state_mgr.command_history.history.append(command)
            state_mgr.command_history.current_index = len(state_mgr.command_history.history) - 1
            state_mgr.command_history.redo_stack.clear()
        except Exception:
            pass

    def _record_field_reorder(self, m: DeviceTreeModel, source_name: str,
                               periph_name: str, reg_name: str,
                               old_order: list, new_order: list):
        """记录位域重排序到命令历史"""
        try:
            state_mgr = self._find_state_manager()
            if state_mgr is None:
                return

            captured_old = old_order[:]
            captured_new = new_order[:]
            captured_periph = periph_name
            captured_reg = reg_name

            def execute_field_reorder():
                periph = state_mgr.device_info.peripherals.get(captured_periph)
                if periph is None:
                    return False
                reg = periph.registers.get(captured_reg)
                if reg is None:
                    return False
                old_fields = reg.fields
                reg.fields = {name: old_fields[name]
                              for name in captured_new if name in old_fields}
                state_mgr._notify_state_change()
                return True

            def undo_field_reorder():
                periph = state_mgr.device_info.peripherals.get(captured_periph)
                if periph is None:
                    return False
                reg = periph.registers.get(captured_reg)
                if reg is None:
                    return False
                old_fields = reg.fields
                reg.fields = {name: old_fields[name]
                              for name in captured_old if name in old_fields}
                state_mgr._notify_state_change()
                return True

            from ...core.command_history import Command
            command = Command(
                execute=execute_field_reorder,
                undo=undo_field_reorder,
                description=f"拖放调整位域顺序: {source_name}",
            )
            state_mgr.command_history.history.append(command)
            state_mgr.command_history.current_index = len(state_mgr.command_history.history) - 1
            state_mgr.command_history.redo_stack.clear()
        except Exception:
            pass

    def _record_register_reorder(self, m: DeviceTreeModel, source_name: str,
                                  periph_name: str,
                                  old_order: list, new_order: list):
        """记录寄存器重排序到命令历史（与 _record_field_reorder 平行）"""
        try:
            state_mgr = self._find_state_manager()
            if state_mgr is None:
                return

            captured_old = old_order[:]
            captured_new = new_order[:]
            captured_periph = periph_name

            def execute_register_reorder():
                periph = state_mgr.device_info.peripherals.get(captured_periph)
                if periph is None:
                    return False
                old_regs = periph.registers
                periph.registers = {name: old_regs[name]
                                    for name in captured_new if name in old_regs}
                state_mgr._notify_state_change()
                return True

            def undo_register_reorder():
                periph = state_mgr.device_info.peripherals.get(captured_periph)
                if periph is None:
                    return False
                old_regs = periph.registers
                periph.registers = {name: old_regs[name]
                                    for name in captured_old if name in old_regs}
                state_mgr._notify_state_change()
                return True

            from ...core.command_history import Command
            command = Command(
                execute=execute_register_reorder,
                undo=undo_register_reorder,
                description=f"拖放调整寄存器顺序: {source_name}",
            )
            state_mgr.command_history.history.append(command)
            state_mgr.command_history.current_index = len(state_mgr.command_history.history) - 1
            state_mgr.command_history.redo_stack.clear()
        except Exception:
            pass

    def _find_state_manager(self):
        """沿着 parent 链查找 StateManager 实例"""
        from ..components.state_manager import StateManager
        widget = self.parent()
        while widget is not None:
            if hasattr(widget, 'state_manager') and isinstance(widget.state_manager, StateManager):
                return widget.state_manager
            if isinstance(widget, StateManager):
                return widget
            widget = widget.parent()
        return None
