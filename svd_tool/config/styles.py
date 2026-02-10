"""
样式配置文件
统一管理应用程序的样式、颜色和字体
"""
from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass
class ColorScheme:
    """颜色方案"""
    # 基础颜色
    white: str = "#FFFFFF"
    black: str = "#000000"
    gray: str = "#CCCCCC"
    light_gray: str = "#F5F5F5"
    dark_gray: str = "#333333"
    
    # 背景颜色
    background: str = "#F5F5F5"
    white_background: str = "#FFFFFF"
    tree_background: str = "#FFFFFF"
    table_background: str = "#FFFFFF"
    header_background: str = "#F0F0F0"
    visualization_background: str = "#F0F0F0"
    
    # 边框颜色
    border: str = "#CCCCCC"
    border_light: str = "#E0E0E0"
    border_dark: str = "#D0D0D0"
    
    # 选中颜色
    selected: str = "#D1E9FF"
    selected_border: str = "#90C8FF"
    selected_active: str = "#B8DAFF"
    hover: str = "#F5F5F5"
    
    # 按钮颜色
    button_normal: str = "#E0E0E0"
    button_hover: str = "#CFCFCF"
    button_pressed: str = "#BFBFBF"
    
    # 功能按钮颜色
    button_add_periph: str = "#4CAF50"
    button_add_periph_hover: str = "#45A049"
    button_add_periph_pressed: str = "#3A8A40"
    
    button_add_reg: str = "#2196F3"
    button_add_reg_hover: str = "#1E88E5"
    button_add_reg_pressed: str = "#1976D2"
    
    button_add_field: str = "#9C27B0"
    button_add_field_hover: str = "#8E24AA"
    button_add_field_pressed: str = "#7B1FA2"
    
    button_delete: str = "#F44336"
    button_delete_hover: str = "#E53935"
    button_delete_pressed: str = "#D32F2F"
    
    button_sort: str = "#9E9E9E"
    button_sort_hover: str = "#8E8E8E"
    button_sort_pressed: str = "#7E7E7E"
    
    button_move: str = "#E0E0E0"
    button_move_hover: str = "#D5D5D5"
    button_move_pressed: str = "#C9C9C9"
    
    button_save_preview: str = "#2196F3"
    button_save_preview_hover: str = "#1E88E5"
    button_save_preview_pressed: str = "#1976D2"
    
    button_add_irq: str = "#4CAF50"
    button_add_irq_hover: str = "#45A049"
    button_add_irq_pressed: str = "#3A8A40"
    
    button_generate: str = "#4CAF50"
    button_generate_hover: str = "#45A049"
    button_generate_pressed: str = "#3A8A40"
    
    # 高亮颜色
    highlight: str = "#FFFF00"
    highlight_light: str = "#FFFFC8"
    highlight_yellow: str = "#FFFF99"
    
    # 文本颜色
    text_normal: str = "#333333"
    text_light: str = "#666666"
    text_white: str = "#FFFFFF"
    
    # 状态颜色
    success: str = "#4CAF50"
    warning: str = "#FF9800"
    error: str = "#F44336"
    info: str = "#2196F3"
    
    # 表格交替行颜色
    table_even: str = "#F9F9F9"
    table_odd: str = "#FFFFFF"


@dataclass
class FontScheme:
    """字体方案"""
    # 字体族
    default_family: str = "Segoe UI"
    fallback_family: str = "Microsoft YaHei"
    monospace_family: str = "Consolas"
    
    # 字体大小
    default_size: int = 10
    small_size: int = 9
    large_size: int = 11
    title_size: int = 12
    
    # 字体粗细
    normal_weight: int = 400
    bold_weight: int = 700


@dataclass
class SizeScheme:
    """尺寸方案"""
    # 按钮尺寸
    button_min_height: int = 26
    button_padding: str = "4px 8px"
    button_border_radius: str = "4px"
    
    # 输入框尺寸
    input_padding: str = "3px"
    input_border_radius: str = "3px"
    
    # 表格/树控件尺寸
    tree_border_radius: str = "3px"
    table_border_radius: str = "3px"
    
    # 菜单尺寸
    menu_padding: str = "3px 10px"
    menu_border_radius: str = "3px"
    
    # 工具栏尺寸
    toolbar_padding: str = "1px"
    
    # 可视化控件尺寸
    visualization_min_height: int = 200


@dataclass
class StyleScheme:
    """样式方案"""
    colors: ColorScheme = ColorScheme()
    fonts: FontScheme = FontScheme()
    sizes: SizeScheme = SizeScheme()
    
    def get_stylesheet(self) -> str:
        """获取完整的样式表"""
        return f"""
            QMainWindow {{
                background-color: {self.colors.background};
            }}
            
            QGroupBox {{
                font-weight: bold;
                border: 1px solid {self.colors.border};
                border-radius: 5px;
                margin-top: 10px;
                padding: 10px;
            }}
            
            QTreeWidget {{
                border: 1px solid {self.colors.border};
                border-radius: {self.sizes.tree_border_radius};
                background-color: {self.colors.tree_background};
                font-family: "{self.fonts.default_family}", "{self.fonts.fallback_family}";
                font-size: {self.fonts.default_size}pt;
                outline: 0;
            }}
            
            QTreeWidget::item:hover {{
                background-color: {self.colors.hover};
            }}
            
            QTreeWidget::item:selected {{
                background-color: {self.colors.selected};
                color: {self.colors.black};
                border: 1px solid {self.colors.selected_border};
                border-radius: 3px;
            }}
            
            QTreeWidget::item:selected:active {{
                background-color: {self.colors.selected_active};
            }}
            
            QTreeWidget::branch:selected {{
                background-color: transparent;
            }}
            
            QTableWidget {{
                border: 1px solid {self.colors.border};
                border-radius: {self.sizes.table_border_radius};
                background-color: {self.colors.table_background};
                gridline-color: {self.colors.border_light};
                font-family: "{self.fonts.default_family}", "{self.fonts.fallback_family}";
                font-size: {self.fonts.default_size}pt;
                outline: 0;
            }}
            
            QTableWidget::item:selected {{
                background-color: {self.colors.selected};
                color: {self.colors.black};
                border: 1px solid {self.colors.selected_border};
                border-radius: 3px;
            }}
            
            QTableWidget::item:hover {{
                background-color: {self.colors.hover};
            }}
            
            QTableWidget::item:nth-child(even) {{
                background-color: {self.colors.table_even};
            }}
            
            QTableWidget::item:nth-child(odd) {{
                background-color: {self.colors.table_odd};
            }}
            
            QHeaderView::section {{
                background-color: {self.colors.header_background};
                padding: 6px;
                border: 1px solid {self.colors.border_dark};
                font-weight: bold;
            }}
            
            QTextEdit {{
                border: 1px solid {self.colors.border};
                border-radius: {self.sizes.input_border_radius};
                background-color: {self.colors.white_background};
            }}
            
            QLineEdit {{
                border: 1px solid {self.colors.border};
                border-radius: {self.sizes.input_border_radius};
                padding: {self.sizes.input_padding};
                background-color: {self.colors.white_background};
            }}
            
            QMenuBar {{
                padding: {self.sizes.menu_padding};
                color: {self.colors.text_normal};
            }}
            
            QMenuBar::item:selected {{
                background-color: {self.colors.border_dark};
                border-radius: {self.sizes.menu_border_radius};
            }}
            
            QPushButton, QToolButton {{
                border: 1px solid {self.colors.border};
                border-radius: {self.sizes.button_border_radius};
                padding: {self.sizes.button_padding};
                background-color: {self.colors.button_normal};
                min-height: {self.sizes.button_min_height}px;
            }}
            
            QPushButton:hover, QToolButton:hover {{
                background-color: {self.colors.button_hover};
            }}
            
            QPushButton:pressed, QToolButton:pressed {{
                background-color: {self.colors.button_pressed};
            }}
            
            QPushButton#btnAddPeriph {{
                background-color: {self.colors.button_add_periph};
            }}
            QPushButton#btnAddPeriph:hover {{
                background-color: {self.colors.button_add_periph_hover};
            }}
            QPushButton#btnAddPeriph:pressed {{
                background-color: {self.colors.button_add_periph_pressed};
            }}
            
            QPushButton#btnAddReg {{
                background-color: {self.colors.button_add_reg};
            }}
            QPushButton#btnAddReg:hover {{
                background-color: {self.colors.button_add_reg_hover};
            }}
            QPushButton#btnAddReg:pressed {{
                background-color: {self.colors.button_add_reg_pressed};
            }}
            
            QPushButton#btnAddField {{
                background-color: {self.colors.button_add_field};
            }}
            QPushButton#btnAddField:hover {{
                background-color: {self.colors.button_add_field_hover};
            }}
            QPushButton#btnAddField:pressed {{
                background-color: {self.colors.button_add_field_pressed};
            }}
            
            QPushButton#btnDelete {{
                background-color: {self.colors.button_delete};
            }}
            QPushButton#btnDelete:hover {{
                background-color: {self.colors.button_delete_hover};
            }}
            QPushButton#btnDelete:pressed {{
                background-color: {self.colors.button_delete_pressed};
            }}
            
            QToolButton#btnSort {{
                background-color: {self.colors.button_sort};
                color: white;
            }}
            QToolButton#btnSort:hover {{
                background-color: {self.colors.button_sort_hover};
            }}
            QToolButton#btnSort:pressed {{
                background-color: {self.colors.button_sort_pressed};
            }}
            
            QPushButton#btnMoveUp, QPushButton#btnMoveDown {{
                background-color: {self.colors.button_move};
                color: {self.colors.text_normal};
            }}
            QPushButton#btnMoveUp:hover, QPushButton#btnMoveDown:hover {{
                background-color: {self.colors.button_move_hover};
            }}
            QPushButton#btnMoveUp:pressed, QPushButton#btnMoveDown:pressed {{
                background-color: {self.colors.button_move_pressed};
            }}
            
            QPushButton#btnSavePreview {{
                background-color: {self.colors.button_save_preview};
            }}
            QPushButton#btnSavePreview:hover {{
                background-color: {self.colors.button_save_preview_hover};
            }}
            QPushButton#btnSavePreview:pressed {{
                background-color: {self.colors.button_save_preview_pressed};
            }}
            
            QPushButton#btnAddIrq {{
                background-color: {self.colors.button_add_irq};
            }}
            QPushButton#btnAddIrq:hover {{
                background-color: {self.colors.button_add_irq_hover};
            }}
            QPushButton#btnAddIrq:pressed {{
                background-color: {self.colors.button_add_irq_pressed};
            }}
            
            QToolButton#generateSvdBtn {{
                background-color: {self.colors.button_generate};
                color: white;
                padding: {self.sizes.button_padding};
                border-radius: {self.sizes.button_border_radius};
                font-size: {self.fonts.small_size}px;
            }}
            QToolButton#generateSvdBtn:hover {{
                background-color: {self.colors.button_generate_hover};
            }}
            QToolButton#generateSvdBtn:pressed {{
                background-color: {self.colors.button_generate_pressed};
            }}
            
            QToolBar {{
                padding: {self.sizes.toolbar_padding};
            }}
        """
    
    def get_tree_stylesheet(self) -> str:
        """获取树控件的样式表"""
        return f"""
            QTreeWidget {{
                font-family: "{self.fonts.default_family}", "{self.fonts.fallback_family}";
                font-size: {self.fonts.default_size}pt;
                outline: 0;
            }}
            
            QTreeWidget::item:hover {{
                background-color: {self.colors.hover};
            }}
            
            QTreeWidget::item:selected {{
                background-color: {self.colors.selected};
                color: {self.colors.black};
                border: 1px solid {self.colors.selected_border};
                border-radius: 3px;
            }}
            
            QTreeWidget::item:selected:active {{
                background-color: {self.colors.selected_active};
            }}
            
            QTreeWidget::branch:selected {{
                background-color: transparent;
            }}
        """
    
    def get_table_stylesheet(self) -> str:
        """获取表格的样式表"""
        return f"""
            QTableWidget {{
                gridline-color: {self.colors.border_light};
                font-family: "{self.fonts.default_family}", "{self.fonts.fallback_family}";
                font-size: {self.fonts.default_size}pt;
                outline: 0;
            }}
            
            QTableWidget::item:selected {{
                background-color: {self.colors.selected};
                color: {self.colors.black};
                border: 1px solid {self.colors.selected_border};
                border-radius: 3px;
            }}
            
            QTableWidget::item:hover {{
                background-color: {self.colors.hover};
            }}
            
            QTableWidget::item:nth-child(even) {{
                background-color: {self.colors.table_even};
            }}
            
            QTableWidget::item:nth-child(odd) {{
                background-color: {self.colors.table_odd};
            }}
        """
    
    def get_header_stylesheet(self) -> str:
        """获取表头的样式表"""
        return f"""
            QHeaderView::section {{
                background-color: {self.colors.header_background};
                padding: 6px;
                border: 1px solid {self.colors.border_dark};
                font-weight: bold;
            }}
        """


# 全局样式方案实例
style_scheme = StyleScheme()
