"""
样式配置文件 - 统一现代风格
全局设计语言：扁平化、圆角、柔和阴影、统一色板
支持亮色/深色双主题
"""
from dataclasses import dataclass, field
from typing import Dict, Tuple


@dataclass
class ColorScheme:
    """颜色方案 - 统一色板"""
    # ===== 品牌主色 =====
    accent: str = "#4A90D9"             # 主色调（蓝）
    accent_hover: str = "#3A7BC8"       # 主色悬停
    accent_pressed: str = "#2E6AB5"     # 主色按下
    accent_light: str = "#E8F0FE"       # 主色浅底

    # ===== 基础颜色 =====
    white: str = "#FFFFFF"
    black: str = "#1A1A1A"
    gray: str = "#8C8C8C"
    light_gray: str = "#F7F8FA"
    dark_gray: str = "#595959"

    # ===== 背景颜色 =====
    background: str = "#F7F8FA"         # 主背景
    surface: str = "#FFFFFF"            # 卡片/面板背景
    tree_background: str = "#FFFFFF"
    table_background: str = "#FFFFFF"
    header_background: str = "#F0F2F5"
    visualization_background: str = "#F0F2F5"

    # ===== 边框颜色 =====
    border: str = "#D9D9D9"
    border_light: str = "#E8E8E8"
    border_dark: str = "#BFBFBF"

    # ===== 选中/激活 =====
    selected: str = "#E8F0FE"
    selected_border: str = "#4A90D9"
    selected_active: str = "#D0E2F7"
    hover: str = "#F0F2F5"

    # ===== 文字颜色 =====
    text_primary: str = "#1A1A1A"
    text_secondary: str = "#8C8C8C"
    text_disabled: str = "#BFBFBF"
    text_white: str = "#FFFFFF"

    # ===== 功能按钮颜色 =====
    button_primary: str = "#4A90D9"
    button_primary_hover: str = "#3A7BC8"
    button_primary_pressed: str = "#2E6AB5"

    button_success: str = "#52C41A"
    button_success_hover: str = "#45A818"
    button_success_pressed: str = "#389E0D"

    button_warning: str = "#FAAD14"
    button_warning_hover: str = "#D48806"
    button_warning_pressed: str = "#B37A00"

    button_danger: str = "#FF4D4F"
    button_danger_hover: str = "#E33E3E"
    button_danger_pressed: str = "#C72B2D"

    button_default: str = "#FFFFFF"
    button_default_hover: str = "#F0F2F5"
    button_default_pressed: str = "#E8E8E8"

    # ===== 兼容旧字段名 =====
    button_normal: str = "#FFFFFF"
    button_hover: str = "#F0F2F5"
    button_pressed: str = "#E8E8E8"

    button_add_periph: str = "#52C41A"
    button_add_periph_hover: str = "#45A818"
    button_add_periph_pressed: str = "#389E0D"

    button_add_reg: str = "#4A90D9"
    button_add_reg_hover: str = "#3A7BC8"
    button_add_reg_pressed: str = "#2E6AB5"

    button_add_field: str = "#9254DE"
    button_add_field_hover: str = "#8240CC"
    button_add_field_pressed: str = "#7030BA"

    button_delete: str = "#FF4D4F"
    button_delete_hover: str = "#E33E3E"
    button_delete_pressed: str = "#C72B2D"

    button_sort: str = "#8C8C8C"
    button_sort_hover: str = "#7A7A7A"
    button_sort_pressed: str = "#595959"

    button_move: str = "#FFFFFF"
    button_move_hover: str = "#F0F2F5"
    button_move_pressed: str = "#E8E8E8"

    button_save_preview: str = "#4A90D9"
    button_save_preview_hover: str = "#3A7BC8"
    button_save_preview_pressed: str = "#2E6AB5"

    button_add_irq: str = "#52C41A"
    button_add_irq_hover: str = "#45A818"
    button_add_irq_pressed: str = "#389E0D"

    button_generate: str = "#52C41A"
    button_generate_hover: str = "#45A818"
    button_generate_pressed: str = "#389E0D"

    # ===== 高亮颜色 =====
    highlight: str = "#FFE58F"
    highlight_light: str = "#FFFBE6"
    highlight_yellow: str = "#FFEC3D"

    # ===== 状态颜色 =====
    success: str = "#52C41A"
    warning: str = "#FAAD14"
    error: str = "#FF4D4F"
    info: str = "#4A90D9"

    # ===== 表格交替行 =====
    table_even: str = "#FAFBFC"
    table_odd: str = "#FFFFFF"

    # ===== 工具栏 =====
    toolbar_background: str = "#FFFFFF"
    toolbar_border: str = "#E8E8E8"
    toolbar_button_hover: str = "#F0F2F5"
    toolbar_button_pressed: str = "#E0E3E8"

    # ===== 标签页 =====
    tab_background: str = "#F0F2F5"
    tab_selected: str = "#FFFFFF"
    tab_text: str = "#595959"
    tab_text_selected: str = "#1A1A1A"

    # ===== 菜单 =====
    menu_background: str = "#FFFFFF"
    menu_hover: str = "#E8F0FE"
    menu_separator: str = "#E8E8E8"

    # ===== 滚动条 =====
    scrollbar_background: str = "#F0F2F5"
    scrollbar_handle: str = "#C4C4C4"
    scrollbar_handle_hover: str = "#A0A0A0"

    # ===== 文档标签栏 =====
    doc_tab_bar_background: str = "#F0F0F0"
    doc_tab_bar_border: str = "#D0D0D0"
    doc_tab_normal_background: str = "#E4E4E4"
    doc_tab_normal_border: str = "#CFCFCF"
    doc_tab_hover_background: str = "#EBEBEB"
    doc_tab_new_btn_color: str = "#666666"
    doc_tab_new_btn_hover_color: str = "#333333"
    doc_tab_new_btn_hover_background: str = "#D8D8D8"
    doc_tab_diff_text_color: str = "#0064B4"

    # ===== 汇总卡片 =====
    card_periph_background: str = "#FFF3E0"
    card_periph_count_color: str = "#E65100"
    card_periph_label_color: str = "#BF360C"
    card_reg_background: str = "#E3F2FD"
    card_reg_count_color: str = "#1565C0"
    card_reg_label_color: str = "#0D47A1"
    card_field_background: str = "#E8F5E9"
    card_field_count_color: str = "#2E7D32"
    card_field_label_color: str = "#1B5E20"
    card_irq_background: str = "#FCE4EC"
    card_irq_count_color: str = "#C62828"
    card_irq_label_color: str = "#B71C1C"

    # ===== Diff 视图 =====
    diff_label_a_title_color: str = "#1565C0"
    diff_label_a_name_color: str = "#0D47A1"
    diff_label_b_title_color: str = "#E65100"
    diff_label_b_name_color: str = "#BF360C"
    diff_header_a_gradient_start: str = "#E3F2FD"
    diff_header_a_gradient_end: str = "#BBDEFB"
    diff_header_a_border: str = "#90CAF9"
    diff_header_b_gradient_start: str = "#FFF3E0"
    diff_header_b_gradient_end: str = "#FFE0B2"
    diff_header_b_border: str = "#FFCC80"
    diff_stats_bar_background: str = "#F5F5F5"
    diff_stats_bar_border: str = "#E0E0E0"
    diff_table_gridline: str = "#E0E0E0"
    diff_table_hover: str = "#E3F2FD"
    diff_table_header_background: str = "#F5F5F5"
    diff_stats_added_color: str = "#2E7D32"
    diff_stats_removed_color: str = "#C62828"
    diff_stats_modified_color: str = "#E65100"

    # ===== XML 语法高亮 =====
    syntax_tag_color: str = "#0000FF"
    syntax_attr_color: str = "#FF00FF"
    syntax_value_color: str = "#FF0000"
    syntax_comment_color: str = "#008000"

    # ===== 可视化绘制 =====
    viz_periph_text_color: str = "#333333"
    viz_reg_text_color: str = "#333333"
    viz_field_text_color: str = "#333333"
    viz_connection_line_color: str = "#CCCCCC"
    viz_ellipsis_color: str = "#999999"
    viz_decorative_bar_color: str = "#FF9800"
    viz_separator_color: str = "#E8E8E8"
    viz_arrow_color: str = "#666666"

    # ===== 欢迎页绘制（QPainter） =====
    welcome_bg_light: str = "#F8F9FC"
    welcome_bg_dark: str = "#1A1A2E"

    # ===== 搜索结果中断颜色 =====
    search_interrupt_color: str = "#9254DE"

    # ===== AI 助手颜色 =====
    ai_user_bubble: str = "#E8F0FE"
    ai_assistant_bubble: str = "#FFFFFF"
    ai_action_success_bg: str = "#F0FFF0"
    ai_action_failed_bg: str = "#FFF0F0"
    ai_streaming_dot: str = "#4A90D9"


@dataclass
class FontScheme:
    """字体方案"""
    default_family: str = "Segoe UI"
    fallback_family: str = "Microsoft YaHei"
    monospace_family: str = "Consolas"

    default_size: int = 10
    small_size: int = 9
    large_size: int = 11
    title_size: int = 12

    normal_weight: int = 400
    bold_weight: int = 700


@dataclass
class SizeScheme:
    """尺寸方案"""
    # 通用圆角
    radius_sm: str = "4px"
    radius_md: str = "6px"
    radius_lg: str = "8px"

    # 按钮尺寸
    button_min_height: int = 28
    button_padding: str = "5px 12px"
    button_border_radius: str = "6px"

    # 输入框尺寸
    input_padding: str = "5px 8px"
    input_border_radius: str = "6px"

    # 表格/树控件尺寸
    tree_border_radius: str = "6px"
    table_border_radius: str = "6px"

    # 菜单尺寸
    menu_padding: str = "4px 12px"
    menu_border_radius: str = "6px"

    # 工具栏尺寸
    toolbar_padding: str = "2px"
    toolbar_button_padding: str = "5px 10px"

    # 可视化控件尺寸
    visualization_min_height: int = 200


@dataclass
class StyleScheme:
    """样式方案 - 统一现代风格"""
    colors: ColorScheme = field(default_factory=ColorScheme)
    fonts: FontScheme = field(default_factory=FontScheme)
    sizes: SizeScheme = field(default_factory=SizeScheme)

    def get_stylesheet(self) -> str:
        """获取完整的全局样式表 - 统一现代风格"""
        c = self.colors
        f = self.fonts
        s = self.sizes
        
        # 树形分支箭头由 TreeBranchStyle (QProxyStyle) 矢量绘制，不再需要生成 PNG
        
        return f"""
        /* ========== 全局基础 ========== */
        QMainWindow {{
            background-color: {c.background};
            font-family: "{f.default_family}", "{f.fallback_family}";
            font-size: {f.default_size}pt;
        }}

        QWidget {{
            font-family: "{f.default_family}", "{f.fallback_family}";
        }}

        /* ========== 菜单栏 ========== */
        QMenuBar {{
            background-color: {c.menu_background};
            border-bottom: 1px solid {c.toolbar_border};
            padding: 2px 4px;
            spacing: 2px;
        }}

        QMenuBar::item {{
            background-color: transparent;
            border: none;
            border-radius: {s.radius_sm};
            padding: {s.menu_padding};
            color: {c.text_primary};
        }}

        QMenuBar::item:selected,
        QMenuBar::item:pressed {{
            background-color: {c.menu_hover};
        }}

        QMenu {{
            background-color: {c.menu_background};
            border: 1px solid {c.border_light};
            border-radius: {s.radius_sm};
            padding: 4px 0px;
        }}

        QMenu::item {{
            padding: {s.menu_padding};
            border-radius: {s.radius_sm};
            color: {c.text_primary};
            margin: 1px 4px;
        }}

        QMenu::item:selected {{
            background-color: {c.menu_hover};
        }}

        QMenu::separator {{
            height: 1px;
            background-color: {c.menu_separator};
            margin: 4px 8px;
        }}

        /* ========== 工具栏 ========== */
        QToolBar {{
            background-color: {c.toolbar_background};
            border: none;
            border-bottom: 1px solid {c.toolbar_border};
            padding: 1px 4px;
            spacing: 2px;
        }}

        QToolBar QToolButton {{
            background-color: transparent;
            border: 1px solid transparent;
            border-radius: {s.radius_sm};
            padding: 3px 8px;
            color: {c.text_secondary};
            font-size: {f.small_size}pt;
            min-height: 22px;
        }}

        QToolBar QToolButton:hover {{
            background-color: {c.toolbar_button_hover};
            color: {c.text_primary};
        }}

        QToolBar QToolButton:pressed {{
            background-color: {c.toolbar_button_pressed};
        }}

        QToolBar::separator {{
            width: 1px;
            height: 16px;
            background-color: {c.border_light};
            margin: 2px 4px;
        }}

        /* 生成SVD按钮特殊样式 */
        QToolButton#generateSvdBtn {{
            background-color: {c.button_generate};
            color: {c.text_white};
            border: none;
            border-radius: {s.radius_sm};
            padding: 3px 10px;
            font-weight: bold;
            font-size: {f.small_size}pt;
            min-height: 22px;
        }}
        QToolButton#generateSvdBtn:hover {{
            background-color: {c.button_generate_hover};
        }}
        QToolButton#generateSvdBtn:pressed {{
            background-color: {c.button_generate_pressed};
        }}

        /* ========== 标签页 (Tab) ========== */
        QTabWidget::pane {{
            border: none;
            border-radius: {s.radius_md};
            background-color: {c.light_gray};
            top: -1px;
        }}

        QTabBar::tab {{
            background-color: transparent;
            color: {c.text_secondary};
            border: none;
            border-bottom: 2px solid transparent;
            border-top-left-radius: {s.radius_sm};
            border-top-right-radius: {s.radius_sm};
            padding: 5px 14px;
            margin-right: 1px;
            min-width: 50px;
            font-size: {f.small_size}pt;
        }}

        QTabBar::tab:selected {{
            background-color: {c.tab_selected};
            color: {c.accent};
            border-bottom: 2px solid {c.accent};
            font-weight: bold;
        }}

        QTabBar::tab:hover:!selected {{
            background-color: {c.hover};
            color: {c.text_primary};
        }}

        /* ========== 树形控件 ========== */
        QTreeWidget {{
            border: 1px solid {c.border_light};
            border-radius: {s.radius_md};
            background-color: {c.white};
            font-family: "{f.default_family}", "{f.fallback_family}";
            font-size: {f.default_size}pt;
            outline: 0;
            alternate-background-color: {c.table_even};
        }}

        QTreeWidget::item {{
            padding: 3px 4px;
            border-radius: {s.radius_sm};
        }}

        QTreeWidget::item:hover {{
            background-color: {c.hover};
        }}

        QTreeWidget::item:selected {{
            background-color: {c.selected};
            color: {c.text_primary};
            border: none;
        }}

        QTreeWidget::item:selected:active {{
            background-color: {c.selected_active};
        }}

        /* 折叠/展开状态的分支箭头由 TreeBranchStyle (QProxyStyle) 矢量绘制，无需 CSS image */
        QTreeWidget::branch:has-children:!has-siblings:closed,
        QTreeWidget::branch:closed:has-children:has-siblings {{
            border-image: none;
        }}

        QTreeWidget::branch:open:has-children:!has-siblings,
        QTreeWidget::branch:open:has-children:has-siblings {{
            border-image: none;
        }}

        /* 鼠标悬停 */
        QTreeWidget::branch:has-children:!has-siblings:closed:hover,
        QTreeWidget::branch:closed:has-children:has-siblings:hover {{
            background-color: {c.hover};
        }}

        QTreeWidget::branch:open:has-children:!has-siblings:hover,
        QTreeWidget::branch:open:has-children:has-siblings:hover {{
            background-color: {c.hover};
        }}

        QTreeWidget::branch:selected {{
            background-color: transparent;
        }}

        /* ========== QTreeView (periph_tree) ========== */
        QTreeView {{
            border: 1px solid {c.border_light};
            border-radius: {s.radius_md};
            background-color: {c.white};
            font-family: "{f.default_family}", "{f.fallback_family}";
            font-size: {f.default_size}pt;
            outline: 0;
            alternate-background-color: {c.table_even};
        }}

        QTreeView::item {{
            padding: 3px 4px;
            border-radius: {s.radius_sm};
        }}

        QTreeView::item:hover {{
            background-color: {c.hover};
        }}

        QTreeView::item:selected {{
            background-color: {c.selected};
            color: {c.text_primary};
            border: none;
        }}

        QTreeView::item:selected:active {{
            background-color: {c.selected_active};
        }}

        QTreeView::branch:has-children:!has-siblings:closed,
        QTreeView::branch:closed:has-children:has-siblings {{
            border-image: none;
        }}

        QTreeView::branch:open:has-children:!has-siblings,
        QTreeView::branch:open:has-children:has-siblings {{
            border-image: none;
        }}

        QTreeView::branch:has-children:!has-siblings:closed:hover,
        QTreeView::branch:closed:has-children:has-siblings:hover {{
            background-color: {c.hover};
        }}

        QTreeView::branch:open:has-children:!has-siblings:hover,
        QTreeView::branch:open:has-children:has-siblings:hover {{
            background-color: {c.hover};
        }}

        QTreeView::branch:selected {{
            background-color: transparent;
        }}

        /* ========== 表格控件 ========== */
        QTableWidget {{
            border: 1px solid {c.border_light};
            border-radius: {s.radius_md};
            background-color: {c.white};
            gridline-color: {c.border_light};
            font-family: "{f.default_family}", "{f.fallback_family}";
            font-size: {f.default_size}pt;
            outline: 0;
        }}

        QTableWidget::item {{
            padding: 4px 8px;
        }}

        QTableWidget::item:selected {{
            background-color: {c.selected};
            color: {c.text_primary};
            border: none;
        }}

        QTableWidget::item:hover {{
            background-color: {c.hover};
        }}

        QHeaderView::section {{
            background-color: {c.header_background};
            padding: 6px 8px;
            border: none;
            border-bottom: 2px solid {c.border};
            border-right: 1px solid {c.border_light};
            font-weight: bold;
            color: {c.text_primary};
        }}

        /* ========== 输入控件 ========== */
        QTextEdit {{
            border: 1px solid {c.border};
            border-radius: {s.radius_md};
            background-color: {c.white};
            selection-background-color: {c.selected};
            padding: 4px;
        }}

        QTextEdit:focus {{
            border-color: {c.accent};
        }}

        QLineEdit {{
            border: 1px solid {c.border};
            border-radius: {s.radius_md};
            padding: {s.input_padding};
            background-color: {c.white};
            selection-background-color: {c.selected};
        }}

        QLineEdit:focus {{
            border-color: {c.accent};
        }}

        QComboBox {{
            border: 1px solid {c.border};
            border-radius: {s.radius_md};
            padding: {s.input_padding};
            background-color: {c.white};
            min-height: 22px;
        }}

        QComboBox:focus {{
            border-color: {c.accent};
        }}

        QComboBox::drop-down {{
            border: none;
            width: 20px;
        }}

        QComboBox QAbstractItemView {{
            border: 1px solid {c.border_light};
            border-radius: {s.radius_md};
            background-color: {c.surface};
            selection-background-color: {c.selected};
            outline: 0;
        }}

        QComboBox#searchTypeCombo {{
            padding: 4px 10px;
            min-width: 80px;
        }}

        /* ========== 分组框 ========== */
        QGroupBox {{
            font-weight: bold;
            font-size: {f.default_size}pt;
            border: 1px solid {c.border_light};
            border-radius: {s.radius_lg};
            margin-top: 14px;
            padding: 18px 14px 14px 14px;
            background-color: {c.surface};
        }}

        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 14px;
            padding: 0 8px;
            color: {c.text_secondary};
            font-size: {f.large_size}pt;
        }}

        /* ========== 按钮 ========== */
        QPushButton {{
            border: 1px solid {c.border_light};
            border-radius: {s.radius_sm};
            padding: 4px 10px;
            background-color: {c.surface};
            color: {c.text_primary};
            min-height: 24px;
            font-size: {f.small_size}pt;
        }}

        QPushButton:hover {{
            background-color: {c.hover};
            border-color: {c.accent};
            color: {c.accent};
        }}

        QPushButton:pressed {{
            background-color: {c.button_default_pressed};
        }}

        QPushButton:disabled {{
            background-color: {c.light_gray};
            color: {c.text_disabled};
        }}

        /* 功能按钮 - 添加外设 (绿色) */
        QPushButton#btnAddPeriph {{
            background-color: {c.button_add_periph};
            color: {c.text_white};
            border: none;
            border-radius: {s.radius_sm};
            padding: 3px 10px;
            font-weight: bold;
            font-size: {f.small_size}pt;
            min-height: 22px;
        }}
        QPushButton#btnAddPeriph:hover {{
            background-color: {c.button_add_periph_hover};
        }}
        QPushButton#btnAddPeriph:pressed {{
            background-color: {c.button_add_periph_pressed};
        }}

        /* 功能按钮 - 添加寄存器 (蓝色) */
        QPushButton#btnAddReg {{
            background-color: {c.button_add_reg};
            color: {c.text_white};
            border: none;
            border-radius: {s.radius_sm};
            padding: 3px 10px;
            font-weight: bold;
            font-size: {f.small_size}pt;
            min-height: 22px;
        }}
        QPushButton#btnAddReg:hover {{
            background-color: {c.button_add_reg_hover};
        }}
        QPushButton#btnAddReg:pressed {{
            background-color: {c.button_add_reg_pressed};
        }}

        /* 功能按钮 - 添加位域 (紫色) */
        QPushButton#btnAddField {{
            background-color: {c.button_add_field};
            color: {c.text_white};
            border: none;
            border-radius: {s.radius_sm};
            padding: 3px 10px;
            font-weight: bold;
            font-size: {f.small_size}pt;
            min-height: 22px;
        }}
        QPushButton#btnAddField:hover {{
            background-color: {c.button_add_field_hover};
        }}
        QPushButton#btnAddField:pressed {{
            background-color: {c.button_add_field_pressed};
        }}

        /* 功能按钮 - 删除 (红色) */
        QPushButton#btnDelete {{
            background-color: {c.button_delete};
            color: {c.text_white};
            border: none;
            border-radius: {s.radius_sm};
            padding: 3px 10px;
            font-weight: bold;
            font-size: {f.small_size}pt;
            min-height: 22px;
        }}
        QPushButton#btnDelete:hover {{
            background-color: {c.button_delete_hover};
        }}
        QPushButton#btnDelete:pressed {{
            background-color: {c.button_delete_pressed};
        }}

        /* 排序按钮 */
        QToolButton#btnSort {{
            background-color: {c.button_sort};
            color: {c.text_white};
            border: none;
        }}
        QToolButton#btnSort:hover {{
            background-color: {c.button_sort_hover};
        }}
        QToolButton#btnSort:pressed {{
            background-color: {c.button_sort_pressed};
        }}

        /* 移动按钮 */
        QPushButton#btnMoveUp, QPushButton#btnMoveDown {{
            background-color: {c.button_move};
            color: {c.text_primary};
            border: 1px solid {c.border_light};
        }}
        QPushButton#btnMoveUp:hover, QPushButton#btnMoveDown:hover {{
            background-color: {c.button_move_hover};
            border-color: {c.accent};
        }}
        QPushButton#btnMoveUp:pressed, QPushButton#btnMoveDown:pressed {{
            background-color: {c.button_move_pressed};
        }}

        /* 保存预览 */
        QPushButton#btnSavePreview {{
            background-color: {c.button_save_preview};
            color: {c.text_white};
            border: none;
        }}
        QPushButton#btnSavePreview:hover {{
            background-color: {c.button_save_preview_hover};
        }}
        QPushButton#btnSavePreview:pressed {{
            background-color: {c.button_save_preview_pressed};
        }}

        /* 添加中断 */
        QPushButton#btnAddIrq {{
            background-color: {c.button_add_irq};
            color: {c.text_white};
            border: none;
            font-weight: bold;
        }}
        QPushButton#btnAddIrq:hover {{
            background-color: {c.button_add_irq_hover};
        }}
        QPushButton#btnAddIrq:pressed {{
            background-color: {c.button_add_irq_pressed};
        }}

        /* ========== 分割器 ========== */
        QSplitter::handle {{
            background-color: {c.border_light};
        }}

        QSplitter::handle:horizontal {{
            width: 1px;
        }}

        QSplitter::handle:vertical {{
            height: 1px;
        }}

        QSplitter::handle:hover {{
            background-color: {c.accent};
        }}

        /* ========== 状态栏 ========== */
        QStatusBar {{
            background-color: {c.light_gray};
            border-top: 1px solid {c.border_light};
            padding: 2px 8px;
            color: {c.text_secondary};
            font-size: {f.small_size}pt;
        }}

        QStatusBar QLabel {{
            color: {c.text_secondary};
        }}

        /* ========== 滚动条 ========== */
        QScrollBar:vertical {{
            background-color: {c.scrollbar_background};
            width: 8px;
            border: none;
        }}

        QScrollBar::handle:vertical {{
            background-color: {c.scrollbar_handle};
            border-radius: 4px;
            min-height: 30px;
        }}

        QScrollBar::handle:vertical:hover {{
            background-color: {c.scrollbar_handle_hover};
        }}

        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}

        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background-color: transparent;
        }}

        QScrollBar:horizontal {{
            background-color: {c.scrollbar_background};
            height: 8px;
            border: none;
        }}

        QScrollBar::handle:horizontal {{
            background-color: {c.scrollbar_handle};
            border-radius: 4px;
            min-width: 30px;
        }}

        QScrollBar::handle:horizontal:hover {{
            background-color: {c.scrollbar_handle_hover};
        }}

        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}

        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
            background-color: transparent;
        }}

        /* ========== 工具提示 ========== */
        QToolTip {{
            background-color: {c.surface};
            color: {c.text_primary};
            border: 1px solid {c.border_light};
            border-radius: {s.radius_sm};
            padding: 4px 8px;
            font-size: {f.small_size}pt;
        }}

        /* ========== SpinBox / CheckBox / RadioButton ========== */
        QSpinBox {{
            border: 1px solid {c.border};
            border-radius: {s.radius_sm};
            padding: {s.input_padding};
            background-color: {c.white};
            min-height: 28px;
        }}
        QSpinBox:focus {{
            border-color: {c.accent};
            border-width: 1.5px;
        }}
        QSpinBox:hover {{
            border-color: {c.accent};
        }}
        QSpinBox::up-button {{
            subcontrol-origin: border;
            subcontrol-position: top right;
            width: 22px;
            border-left: 1px solid {c.border_light};
            border-top-right-radius: {s.radius_sm};
            background-color: {c.white};
        }}
        QSpinBox::up-button:hover {{
            background-color: {c.accent_light};
        }}
        QSpinBox::up-button:pressed {{
            background-color: {c.accent};
        }}
        QSpinBox::up-arrow {{
            width: 8px;
            height: 8px;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-bottom: 5px solid {c.gray};
        }}
        QSpinBox::up-button:hover QSpinBox::up-arrow {{
            border-bottom-color: {c.accent};
        }}
        QSpinBox::down-button {{
            subcontrol-origin: border;
            subcontrol-position: bottom right;
            width: 22px;
            border-left: 1px solid {c.border_light};
            border-bottom-right-radius: {s.radius_sm};
            background-color: {c.white};
        }}
        QSpinBox::down-button:hover {{
            background-color: {c.accent_light};
        }}
        QSpinBox::down-button:pressed {{
            background-color: {c.accent};
        }}
        QSpinBox::down-arrow {{
            width: 8px;
            height: 8px;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid {c.gray};
        }}
        QSpinBox::down-button:hover QSpinBox::down-arrow {{
            border-top-color: {c.accent};
        }}

        QCheckBox {{
            spacing: 8px;
            color: {c.text_primary};
        }}
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border-radius: 3px;
            border: 1px solid {c.border};
        }}
        QCheckBox::indicator:checked {{
            background-color: {c.accent};
            border-color: {c.accent};
        }}

        QRadioButton {{
            spacing: 8px;
            color: {c.text_primary};
        }}

        /* ========== 欢迎页 ========== */
        QFrame#welcomeTopBar {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #4A90D9, stop:0.5 #9B59B6, stop:1 #E74C3C);
        }}

        QLabel#welcomeTitle {{
            color: {c.text_primary};
        }}

        QLabel#welcomeSubtitle {{
            color: {c.accent};
        }}

        QLabel#welcomeDesc {{
            color: {c.text_secondary};
        }}

        QLabel#welcomeSectionTitle {{
            color: {c.text_primary};
        }}

        QLabel#welcomeNoRecent {{
            color: {c.text_disabled};
        }}

        QLabel#welcomeShortcutKey {{
            color: {c.text_white};
            background-color: {c.dark_gray};
            border-radius: 4px;
            padding: 2px 6px;
        }}

        QLabel#welcomeShortcutDesc {{
            color: {c.text_secondary};
        }}

        QLabel#welcomeFooter {{
            color: {c.text_disabled};
        }}

        QFrame#welcomeActionBtn {{
            background-color: {c.surface};
            border: 1px solid {c.border_light};
            border-radius: 8px;
        }}

        QFrame#welcomeActionBtn:hover {{
            background-color: {c.accent_light};
            border-color: {c.accent};
        }}

        QLabel#welcomeActionBtnText {{
            color: {c.text_primary};
        }}

        QLabel#welcomeActionBtnDesc {{
            color: {c.text_secondary};
        }}

        QFrame#welcomeRecentItem {{
            background-color: transparent;
            border: 1px solid transparent;
            border-radius: 6px;
        }}

        QFrame#welcomeRecentItem:hover {{
            background-color: {c.hover};
            border-color: {c.border_light};
        }}

        QLabel#welcomeRecentName {{
            color: {c.accent};
        }}

        QLabel#welcomeRecentPath {{
            color: {c.text_disabled};
        }}

        /* ========== ProgressDialog ========== */
        QProgressDialog {{
            background-color: {c.surface};
        }}
        QProgressBar {{
            border: 1px solid {c.border_light};
            border-radius: {s.radius_sm};
            text-align: center;
            background-color: {c.light_gray};
        }}
        QProgressBar::chunk {{
            background-color: {c.accent};
            border-radius: {s.radius_sm};
        }}
        """

    def get_tree_stylesheet(self) -> str:
        """获取树控件的样式表"""
        return self.get_stylesheet()  # 全局样式表已包含

    def get_table_stylesheet(self) -> str:
        """获取表格的样式表"""
        return self.get_stylesheet()  # 全局样式表已包含

    def get_header_stylesheet(self) -> str:
        """获取表头的样式表"""
        return self.get_stylesheet()  # 全局样式表已包含


@dataclass
class DarkColorScheme(ColorScheme):
    """深色颜色方案 - 统一深色主题"""
    # ===== 品牌主色 =====
    accent: str = "#5B9BD5"
    accent_hover: str = "#6DABE8"
    accent_pressed: str = "#4A8BC4"
    accent_light: str = "#2A3A52"

    # ===== 基础颜色 =====
    white: str = "#D4D4D4"
    black: str = "#E0E0E0"
    gray: str = "#808080"
    light_gray: str = "#2D2D2D"
    dark_gray: str = "#B0B0B0"

    # ===== 背景颜色 =====
    background: str = "#1E1E1E"
    surface: str = "#252526"
    tree_background: str = "#252526"
    table_background: str = "#252526"
    header_background: str = "#2D2D2D"
    visualization_background: str = "#1E1E1E"

    # ===== 边框颜色 =====
    border: str = "#3C3C3C"
    border_light: str = "#333333"
    border_dark: str = "#4A4A4A"

    # ===== 选中/激活 =====
    selected: str = "#264F78"
    selected_border: str = "#5B9BD5"
    selected_active: str = "#1F4E85"
    hover: str = "#2A2D2E"

    # ===== 文字颜色 =====
    text_primary: str = "#D4D4D4"
    text_secondary: str = "#808080"
    text_disabled: str = "#505050"
    text_white: str = "#FFFFFF"

    # ===== 按钮颜色 =====
    button_primary: str = "#5B9BD5"
    button_primary_hover: str = "#6DABE8"
    button_primary_pressed: str = "#4A8BC4"

    button_success: str = "#6BCB77"
    button_success_hover: str = "#7DD88A"
    button_success_pressed: str = "#52B862"

    button_warning: str = "#FFB74D"
    button_warning_hover: str = "#FFC975"
    button_warning_pressed: str = "#E6A23C"

    button_danger: str = "#EF5350"
    button_danger_hover: str = "#F77"
    button_danger_pressed: str = "#D32F2F"

    button_default: str = "#333333"
    button_default_hover: str = "#3C3C3C"
    button_default_pressed: str = "#444444"

    # 兼容旧字段
    button_normal: str = "#333333"
    button_hover: str = "#3C3C3C"
    button_pressed: str = "#444444"

    button_add_periph: str = "#6BCB77"
    button_add_periph_hover: str = "#7DD88A"
    button_add_periph_pressed: str = "#52B862"

    button_add_reg: str = "#5B9BD5"
    button_add_reg_hover: str = "#6DABE8"
    button_add_reg_pressed: str = "#4A8BC4"

    button_add_field: str = "#B07CD8"
    button_add_field_hover: str = "#C48FE8"
    button_add_field_pressed: str = "#9A69C4"

    button_delete: str = "#EF5350"
    button_delete_hover: str = "#F77"
    button_delete_pressed: str = "#D32F2F"

    button_sort: str = "#616161"
    button_sort_hover: str = "#757575"
    button_sort_pressed: str = "#424242"

    button_move: str = "#333333"
    button_move_hover: str = "#3C3C3C"
    button_move_pressed: str = "#444444"

    button_save_preview: str = "#5B9BD5"
    button_save_preview_hover: str = "#6DABE8"
    button_save_preview_pressed: str = "#4A8BC4"

    button_add_irq: str = "#6BCB77"
    button_add_irq_hover: str = "#7DD88A"
    button_add_irq_pressed: str = "#52B862"

    button_generate: str = "#6BCB77"
    button_generate_hover: str = "#7DD88A"
    button_generate_pressed: str = "#52B862"

    # 高亮
    highlight: str = "#FFD54F"
    highlight_light: str = "#3A3520"
    highlight_yellow: str = "#FFF176"

    # 状态
    success: str = "#81C784"
    warning: str = "#FFB74D"
    error: str = "#EF5350"
    info: str = "#64B5F6"

    # 表格
    table_even: str = "#2A2A2A"
    table_odd: str = "#252526"

    # 工具栏
    toolbar_background: str = "#252526"
    toolbar_border: str = "#333333"
    toolbar_button_hover: str = "#2A2D2E"
    toolbar_button_pressed: str = "#383838"

    # 标签页
    tab_background: str = "#2D2D2D"
    tab_selected: str = "#252526"
    tab_text: str = "#808080"
    tab_text_selected: str = "#D4D4D4"

    # 菜单
    menu_background: str = "#252526"
    menu_hover: str = "#2A3A52"
    menu_separator: str = "#333333"

    # 滚动条
    scrollbar_background: str = "#1E1E1E"
    scrollbar_handle: str = "#4A4A4A"
    scrollbar_handle_hover: str = "#5A5A5A"

    # ===== 文档标签栏 =====
    doc_tab_bar_background: str = "#2D2D2D"
    doc_tab_bar_border: str = "#3C3C3C"
    doc_tab_normal_background: str = "#383838"
    doc_tab_normal_border: str = "#4A4A4A"
    doc_tab_hover_background: str = "#404040"
    doc_tab_new_btn_color: str = "#AAAAAA"
    doc_tab_new_btn_hover_color: str = "#D4D4D4"
    doc_tab_new_btn_hover_background: str = "#505050"
    doc_tab_diff_text_color: str = "#6DABE8"

    # ===== 汇总卡片 =====
    card_periph_background: str = "#3D2E1A"
    card_periph_count_color: str = "#FFB74D"
    card_periph_label_color: str = "#E6A23C"
    card_reg_background: str = "#1A2A3D"
    card_reg_count_color: str = "#64B5F6"
    card_reg_label_color: str = "#5B9BD5"
    card_field_background: str = "#1A3D1A"
    card_field_count_color: str = "#81C784"
    card_field_label_color: str = "#66BB6A"
    card_irq_background: str = "#3D1A1A"
    card_irq_count_color: str = "#EF9A9A"
    card_irq_label_color: str = "#EF5350"

    # ===== Diff 视图 =====
    diff_label_a_title_color: str = "#64B5F6"
    diff_label_a_name_color: str = "#5B9BD5"
    diff_label_b_title_color: str = "#FFB74D"
    diff_label_b_name_color: str = "#E6A23C"
    diff_header_a_gradient_start: str = "#1A2A3D"
    diff_header_a_gradient_end: str = "#1A3048"
    diff_header_a_border: str = "#2A4A6A"
    diff_header_b_gradient_start: str = "#3D2E1A"
    diff_header_b_gradient_end: str = "#483818"
    diff_header_b_border: str = "#6A5030"
    diff_stats_bar_background: str = "#2D2D2D"
    diff_stats_bar_border: str = "#3C3C3C"
    diff_table_gridline: str = "#3C3C3C"
    diff_table_hover: str = "#264F78"
    diff_table_header_background: str = "#2D2D2D"
    diff_stats_added_color: str = "#81C784"
    diff_stats_removed_color: str = "#EF5350"
    diff_stats_modified_color: str = "#FFB74D"

    # ===== XML 语法高亮 =====
    syntax_tag_color: str = "#569CD6"
    syntax_attr_color: str = "#9CDCFE"
    syntax_value_color: str = "#CE9178"
    syntax_comment_color: str = "#6A9955"

    # ===== 可视化绘制 =====
    viz_periph_text_color: str = "#D4D4D4"
    viz_reg_text_color: str = "#D4D4D4"
    viz_field_text_color: str = "#D4D4D4"
    viz_connection_line_color: str = "#555555"
    viz_ellipsis_color: str = "#777777"
    viz_decorative_bar_color: str = "#FF9800"
    viz_separator_color: str = "#3C3C3C"
    viz_arrow_color: str = "#999999"

    # ===== 欢迎页绘制 =====
    welcome_bg_light: str = "#1E1E1E"
    welcome_bg_dark: str = "#1A1A2E"

    # ===== 搜索结果中断颜色 =====
    search_interrupt_color: str = "#B07CD8"

    # ===== AI 助手颜色 =====
    ai_user_bubble: str = "#2A3A52"
    ai_assistant_bubble: str = "#252526"
    ai_action_success_bg: str = "#1A3D1A"
    ai_action_failed_bg: str = "#3D1A1A"
    ai_streaming_dot: str = "#5B9BD5"


def create_dark_style_scheme() -> StyleScheme:
    """创建深色样式方案"""
    return StyleScheme(colors=DarkColorScheme())


# 当前是否为深色模式
_is_dark_mode = False


def is_dark_mode() -> bool:
    """是否为深色模式"""
    return _is_dark_mode


def set_dark_mode(enabled: bool):
    """设置深色模式"""
    global _is_dark_mode, style_scheme
    _is_dark_mode = enabled
    if enabled:
        style_scheme = create_dark_style_scheme()
    else:
        style_scheme = StyleScheme()


def get_style_scheme() -> StyleScheme:
    """获取当前样式方案（函数式访问，避免引用失效）"""
    return style_scheme


def get_current_stylesheet() -> str:
    """获取当前全局样式表字符串"""
    return style_scheme.get_stylesheet()


def toggle_dark_mode() -> bool:
    """切换深色模式，返回切换后的状态"""
    set_dark_mode(not _is_dark_mode)
    return _is_dark_mode


# 全局样式方案实例
style_scheme = StyleScheme()
