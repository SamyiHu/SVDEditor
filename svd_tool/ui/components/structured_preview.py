"""
结构化SVD预览组件 - 层级卡片式视图
以XML风格卡片展示外设/寄存器/位域层次结构，懒加载，现代简洁
"""
import logging
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame, QSizePolicy, QToolButton
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from ...i18n.i18n import t
from ...config.styles import get_style_scheme

# 类型对应的颜色
TYPE_COLORS = {
    'peripheral': '#4A90D9',
    'register': '#1890FF',
    'field': '#52C41A',
}

# 访问权限颜色
ACCESS_COLORS = {
    "read-write": "#1890FF",
    "read-only": "#52C41A",
    "write-only": "#FA8C16",
    "write-once": "#FF4D4F",
}


class HierarchicalCardWidget(QFrame):
    """层级卡片组件 - XML风格，懒加载子节点"""

    clicked = pyqtSignal(str, str, str, str)  # (type, peripheral, register, field)

    def __init__(self, card_type: str, data: dict, color: str,
                 state_manager=None, parent=None):
        super().__init__(parent)
        self._card_type = card_type
        self._data = data
        self._color = color
        self._state_manager = state_manager
        self._expanded = False
        self._children_loaded = False
        self._setup_ui()

    def _setup_ui(self):
        scheme = get_style_scheme()
        c = scheme.colors

        self.setFrameShape(QFrame.Shape.StyledPanel)
        bg_map = {
            'peripheral': c.card_periph_background,
            'register': c.card_reg_background,
            'field': c.card_field_background,
        }
        bg = bg_map.get(self._card_type, c.surface)
        self.setStyleSheet(f"""
            HierarchicalCardWidget {{
                background-color: {bg};
                border: 1px solid {c.border_light};
                border-left: 3px solid {self._color};
                border-radius: 4px;
                margin: 1px 2px;
            }}
            HierarchicalCardWidget:hover {{
                border-color: {self._color};
            }}
        """)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)

        # --- Header 行 ---
        header = QHBoxLayout()
        header.setSpacing(4)

        # 展开/折叠箭头（只有外设和寄存器有子节点）
        if self._card_type in ('peripheral', 'register'):
            self._toggle_btn = QToolButton()
            self._toggle_btn.setArrowType(Qt.ArrowType.RightArrow)
            self._toggle_btn.setFixedSize(14, 14)
            self._toggle_btn.setStyleSheet("border: none; background: transparent;")
            self._toggle_btn.clicked.connect(self._toggle)
            header.addWidget(self._toggle_btn)

        # XML风格标签
        tag_text = self._build_tag_text()
        self._tag_label = QLabel(tag_text)
        self._tag_label.setFont(QFont("Consolas", 9))
        self._tag_label.setStyleSheet(f"color: {self._color}; border: none;")
        header.addWidget(self._tag_label)

        header.addStretch()
        layout.addLayout(header)

        # --- 描述行 ---
        desc = self._data.get('description', '')
        if desc:
            desc_text = desc[:100] + ('...' if len(desc) > 100 else '')
            desc_label = QLabel(desc_text)
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet(
                f"color: {c.text_secondary}; font-size: 8pt; border: none; margin-left: 18px;")
            layout.addWidget(desc_label)

        # --- 折叠摘要行（如 "5 registers..."） ---
        summary_text = self._build_summary_text()
        if summary_text:
            self._summary_label = QLabel(summary_text)
            self._summary_label.setStyleSheet(
                f"color: {c.text_secondary}; font-size: 8pt; border: none; margin-left: 18px;")
            layout.addWidget(self._summary_label)
        else:
            self._summary_label = None

        # --- 子节点容器（初始隐藏） ---
        self._children_widget = QWidget()
        self._children_widget.setStyleSheet("background: transparent; border: none;")
        self._children_layout = QVBoxLayout(self._children_widget)
        self._children_layout.setContentsMargins(16, 4, 0, 0)
        self._children_layout.setSpacing(2)
        self._children_widget.setVisible(False)
        layout.addWidget(self._children_widget)

    def _build_tag_text(self) -> str:
        d = self._data
        if self._card_type == 'peripheral':
            addr = d.get('base_address', '0x0')
            try:
                addr_str = f"0x{int(addr, 16):08X}" if isinstance(addr, str) and addr.startswith('0x') else str(addr)
            except (ValueError, TypeError):
                addr_str = str(addr)
            return f'<peripheral name="{d["name"]}" base_address="{addr_str}">'
        elif self._card_type == 'register':
            offset = d.get('offset', '')
            try:
                offset_str = f"0x{int(offset, 16):04X}" if offset else ""
            except (ValueError, TypeError):
                offset_str = str(offset)
            access = d.get('access', '')
            size = d.get('size', '')
            parts = [f'name="{d["name"]}"']
            if offset_str:
                parts.append(f'offset="{offset_str}"')
            if size:
                parts.append(f'size="{size}"')
            if access:
                parts.append(f'access="{access}"')
            return f'<register {" ".join(parts)}>'
        elif self._card_type == 'field':
            name = d.get('name', '')
            bit_range = d.get('bit_range', '')
            access = d.get('access', '')
            reset = d.get('reset_value', '')
            parts = [f'name="{name}"']
            if bit_range:
                parts.append(f'bits="{bit_range}"')
            if access:
                parts.append(f'access="{access}"')
            if reset:
                parts.append(f'reset="{reset}"')
            return f'<field {" ".join(parts)}>'
        return ''

    def _build_summary_text(self) -> str:
        d = self._data
        if self._card_type == 'peripheral':
            count = d.get('register_count', 0)
            if count > 0:
                return f"{count} registers"
            return "(no registers)"
        elif self._card_type == 'register':
            count = d.get('field_count', 0)
            if count > 0:
                return f"{count} fields"
            return "(no fields)"
        return ""

    def _toggle(self):
        self._expanded = not self._expanded
        self._children_widget.setVisible(self._expanded)
        if hasattr(self, '_toggle_btn'):
            self._toggle_btn.setArrowType(
                Qt.ArrowType.DownArrow if self._expanded else Qt.ArrowType.RightArrow
            )
        if self._summary_label:
            self._summary_label.setVisible(not self._expanded)

        if self._expanded and not self._children_loaded:
            self._load_children()
            self._children_loaded = True

    def _load_children(self):
        """懒加载子卡片"""
        if not self._state_manager:
            return

        device = self._state_manager.device_info
        if not device:
            return

        if self._card_type == 'peripheral':
            periph_name = self._data['name']
            periph = device.peripherals.get(periph_name)
            if not periph:
                return
            for rname, reg in sorted(periph.registers.items(),
                    key=lambda x: self._safe_offset(x[1].offset)):
                field_count = len(reg.fields) if reg.fields else 0
                child = HierarchicalCardWidget(
                    card_type='register',
                    data={
                        'name': rname,
                        'offset': reg.offset,
                        'size': reg.size,
                        'access': reg.access or '',
                        'description': reg.description,
                        'field_count': field_count,
                        'reset_value': reg.reset_value,
                        '_periph_name': periph_name,
                    },
                    color=TYPE_COLORS['register'],
                    state_manager=self._state_manager,
                    parent=self
                )
                self._children_layout.addWidget(child)

        elif self._card_type == 'register':
            periph_name = self._data.get('_periph_name', '')
            reg_name = self._data['name']
            periph = device.peripherals.get(periph_name)
            if not periph:
                return
            reg = periph.registers.get(reg_name)
            if not reg:
                return
            for fname, fld in sorted(reg.fields.items(),
                    key=lambda x: int(x[1].bit_offset) if x[1].bit_offset is not None else 0):
                bit_range = ''
                if fld.bit_offset is not None and fld.bit_width is not None:
                    end = int(fld.bit_offset) + int(fld.bit_width) - 1
                    bit_range = f"{end}:{fld.bit_offset}"
                child = HierarchicalCardWidget(
                    card_type='field',
                    data={
                        'name': fname,
                        'bit_range': bit_range,
                        'access': fld.access if hasattr(fld, 'access') and fld.access else '',
                        'description': fld.description,
                        'reset_value': fld.reset_value,
                    },
                    color=TYPE_COLORS['field'],
                    state_manager=self._state_manager,
                    parent=self
                )
                self._children_layout.addWidget(child)

    @staticmethod
    def _safe_offset(offset) -> int:
        try:
            return int(offset, 16) if isinstance(offset, str) else int(offset)
        except (ValueError, TypeError):
            return 0


class StructuredPreviewWidget(QWidget):
    """结构化SVD预览 - 层级卡片式视图（懒加载）"""

    element_selected = pyqtSignal(str, str, str)  # (type, peripheral, name)

    def __init__(self, state_manager=None, coordinator=None, parent=None):
        super().__init__(parent)
        self.state_manager = state_manager
        self.coordinator = coordinator
        self.logger = logging.getLogger("StructuredPreviewWidget")
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 顶部信息栏
        self._info_label = QLabel(t("preview.no_data"))
        self._info_label.setStyleSheet(
            "color: #8C8C8C; font-size: 9pt; padding: 6px 8px; "
            "background: #FAFBFC; border-bottom: 1px solid #E8E8E8;")
        layout.addWidget(self._info_label)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: #F7F8FA; border: none; }")

        self._container = QWidget()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(4, 4, 4, 4)
        self._container_layout.setSpacing(4)
        self._container_layout.addStretch()

        scroll.setWidget(self._container)
        layout.addWidget(scroll)

        self.setStyleSheet("background-color: #F7F8FA;")

    def refresh(self):
        """刷新预览内容 — 只创建外设级别卡片（懒加载）"""
        # 清除现有内容
        while self._container_layout.count() > 0:
            item = self._container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self.state_manager or not self.state_manager.device_info:
            self._info_label.setText(t("preview.no_data"))
            return

        device = self.state_manager.device_info
        periph_count = len(device.peripherals)
        reg_count = sum(len(p.registers) for p in device.peripherals.values())
        field_count = sum(
            sum(len(r.fields) for r in p.registers.values())
            for p in device.peripherals.values()
        )
        self._info_label.setText(
            f"{device.name or 'SVD'} | "
            f"{periph_count} {t('type.peripheral')}s, "
            f"{reg_count} {t('type.register')}s, "
            f"{field_count} {t('label.field')}s"
        )

        # 只创建外设级别卡片（O(P)），寄存器和位域按需展开加载
        for pname, periph in sorted(device.peripherals.items()):
            reg_count_p = len(periph.registers)

            card = HierarchicalCardWidget(
                card_type='peripheral',
                data={
                    'name': pname,
                    'base_address': periph.base_address or '0x0',
                    'description': periph.description,
                    'register_count': reg_count_p,
                },
                color=TYPE_COLORS['peripheral'],
                state_manager=self.state_manager,
            )
            self._container_layout.insertWidget(self._container_layout.count() - 1, card)

    def _on_selection_changed(self):
        if self.state_manager:
            selection = self.state_manager.get_selection()
            self._highlight_selection(selection)

    def _on_coordinator_selection_changed(self, selection):
        self._highlight_selection(selection)

    def _highlight_selection(self, selection):
        pass

    def cleanup(self):
        pass
