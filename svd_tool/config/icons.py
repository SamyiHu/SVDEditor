"""
图标配置文件 - Material Design 风格
使用 Google Material Design SVG 图标路径，无需外部文件依赖
所有图标基于 Material Icons (https://fonts.google.com/icons)
"""
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QPainterPath, QPen
from PyQt6.QtCore import Qt, QRect, QSize


# ==================== Material Design SVG Path Data ====================

# 每个图标使用 24x24 viewport 的 SVG path data
# 来源: Google Material Design Icons (Apache 2.0 License)

ICON_PATHS = {
    # ---- 文件操作 ----
    "file_new": "M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6zm4 18H6V4h7v5h5v11z",
    "file_open": "M20 6h-8l-2-2H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2zm0 12H4V8h16v10z",
    "file_save": "M17 3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V7l-4-4zm-5 16c-1.66 0-3-1.34-3-3s1.34-3 3-3 3 1.34 3 3-1.34 3-3 3zm3-10H5V5h10v4z",
    "file_save_as": "M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z",
    "file_close": "M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z",

    # ---- 编辑操作 ----
    "undo": "M12.5 8c-2.65 0-5.05.99-6.9 2.6L2 7v9h9l-3.62-3.62c1.39-1.16 3.16-1.88 5.12-1.88 3.54 0 6.55 2.31 7.6 5.5l2.37-.78C21.08 11.03 17.15 8 12.5 8z",
    "redo": "M18.4 10.6C16.55 8.99 14.15 8 11.5 8c-4.65 0-8.58 3.03-9.96 7.22L3.9 16c1.05-3.19 4.05-5.5 7.6-5.5 1.95 0 3.73.72 5.12 1.88L13 16h9V7l-3.6 3.6z",
    "cut": "M9.64 7.64c.23-.5.36-1.05.36-1.64 0-2.21-1.79-4-4-4S2 3.79 2 6s1.79 4 4 4c.59 0 1.14-.13 1.64-.36L10 12l-2.36 2.36C7.14 14.13 6.59 14 6 14c-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4c0-.59-.13-1.14-.36-1.64L12 14l7 7h3v-1L9.64 7.64zM6 8c-1.1 0-2-.89-2-2s.9-2 2-2 2 .89 2 2-.9 2-2 2zm0 12c-1.1 0-2-.89-2-2s.9-2 2-2 2 .89 2 2-.9 2-2 2zm6-7.5c-.28 0-.5-.22-.5-.5s.22-.5.5-.5.5.22.5.5-.22.5-.5.5zM19 3l-6 6 2 2 7-7V3z",
    "copy": "M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z",
    "paste": "M19 2h-4.18C14.4.84 13.3 0 12 0c-1.3 0-2.4.84-2.82 2H5c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-7 0c.55 0 1 .45 1 1s-.45 1-1 1-1-.45-1-1 .45-1 1-1zm7 18H5V4h2v3h10V4h2v16z",
    "delete": "M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z",
    "edit": "M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z",

    # ---- 视图操作 ----
    "expand": "M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6 1.41-1.41z",
    "collapse": "M7.41 15.41L12 10.83l4.59 4.58L18 14l-6-6-6 6z",
    "expand_all": "M12 16.41l-4.59-4.58L6 13l6 6 6-6-1.41-1.41zM12 7.59L7.41 12.17 6 11l6-6 6 6-1.41 1.41z",
    "collapse_all": "M7.41 18.59L12 14.01l4.59 4.58L18 17l-6-6-6 6zM7.41 5.41L12 9.99l4.59-4.58L18 7l-6 6-6-6z",
    "search": "M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z",
    "visible_on": "M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z",
    "visible_off": "M12 7c2.76 0 5 2.24 5 5 0 .65-.13 1.26-.36 1.83l2.92 2.92c1.51-1.26 2.7-2.89 3.43-4.75-1.73-4.39-6-7.5-11-7.5-1.4 0-2.74.25-3.98.7l2.16 2.16C10.74 7.13 11.35 7 12 7zM2 4.27l2.28 2.28.46.46C3.08 8.3 1.78 10.02 1 12c1.73 4.39 6 7.5 11 7.5 1.55 0 3.03-.3 4.38-.84l.42.42L19.73 22 21 20.73 3.27 3 2 4.27zM7.53 9.8l1.55 1.55c-.05.21-.08.43-.08.65 0 1.66 1.34 3 3 3 .22 0 .44-.03.65-.08l1.55 1.55c-.67.33-1.41.53-2.2.53-2.76 0-5-2.24-5-5 0-.79.2-1.53.53-2.2zm4.31-.78l3.15 3.15.02-.16c0-1.66-1.34-3-3-3l-.17.01z",
    "toggle_panel": "M11 21h2V3h-2v18zM3 21h2v-6H3v6zM7 21h2v-4H7v4zM15 21h2v-8h-2v8zM19 3v18h2V3h-2z",

    # ---- 工具操作 ----
    "validate": "M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z",
    "generate": "M9.4 16.6L4.8 12l4.6-4.6L8 6l-6 6 6 6 1.4-1.4zm5.2 0l4.6-4.6-4.6-4.6L16 6l6 6-6 6-1.4-1.4z",
    "export_file": "M19 12v7H5v-7H3v7c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2v-7h-2zm-6 .67l2.59-2.58L17 11.5l-5 5-5-5 1.41-1.41L11 12.67V3h2v9.67z",
    "diff": "M10 6H5v2h3.1L3 13.1 4.4 14.5 9.5 9.4V12h2V6zm8.6 2H14v2h2.1L11 15.1l1.4 1.4L17.5 11.4V14h2V8h-1.4z",
    "chain": "M3.9 12c0-1.71 1.39-3.1 3.1-3.1h4V7H7c-2.76 0-5 2.24-5 5s2.24 5 5 5h4v-1.9H7c-1.71 0-3.1-1.39-3.1-3.1zM8 13h8v-2H8v2zm9-6h-4v1.9h4c1.71 0 3.1 1.39 3.1 3.1s-1.39 3.1-3.1 3.1h-4V17h4c2.76 0 5-2.24 5-5s-2.24-5-5-5z",

    # ---- 树形视图层级图标 ----
    "peripheral": "M6 4h12v1H6zm0 15h12v1H6zm3-3h6v2H9zm0-5h6v3H9zm0-5h6v3H9z",
    "register": "M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.07.62-.07.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z",
    "field": "M17 7h-4v1.9h4c1.71 0 3.1 1.39 3.1 3.1 0 1.71-1.39 3.1-3.1 3.1h-4V17h4c2.76 0 5-2.24 5-5s-2.24-5-5-5zM7 17h4v-1.9H7c-1.71 0-3.1-1.39-3.1-3.1 0-1.71 1.39-3.1 3.1-3.1h4V7H7c-2.76 0-5 2.24-5 5s2.24 5 5 5zm-3-4h8v-2H4v2z",
    "interrupt": "M7 2v11h3v9l7-12h-4l4-8z",

    # ---- 导航 ----
    "arrow_up": "M4 12l1.41 1.41L11 7.83V20h2V7.83l5.58 5.59L20 12l-8-8-8 8z",
    "arrow_down": "M20 12l-1.41-1.41L13 16.17V4h-2v12.17l-5.58-5.59L4 12l8 8 8-8z",
    "arrow_prev": "M15.41 7.41L14 6l-6 6 6 6 1.41-1.41L10.83 12z",
    "arrow_next": "M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z",

    # ---- 状态 ----
    "status_ok": "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z",
    "status_error": "M12 2C6.47 2 2 6.47 2 12s4.47 10 10 10 10-4.47 10-10S17.53 2 12 2zm5 13.59L15.59 17 12 13.41 8.41 17 7 15.59 10.59 12 7 8.41 8.41 7 12 10.59 15.59 7 17 8.41 13.41 12 17 15.59z",
    "status_warning": "M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z",
    "status_info": "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z",

    # ---- 主题 ----
    "dark_mode": "M12 3c-4.97 0-9 4.03-9 9s4.03 9 9 9 9-4.03 9-9c0-.46-.04-.92-.1-1.36-.98 1.37-2.58 2.26-4.4 2.26-2.98 0-5.4-2.42-5.4-5.4 0-1.81.89-3.42 2.26-4.4-.44-.06-.9-.1-1.36-.1z",
    "light_mode": "M6.76 4.84l-1.8-1.79-1.41 1.41 1.79 1.79 1.42-1.41zM4 10.5H1v2h3v-2zm9-9.95h-2V3.5h2V.55zm7.45 3.91l-1.41-1.41-1.79 1.79 1.41 1.41 1.79-1.79zm-3.21 13.7l1.79 1.8 1.41-1.41-1.8-1.79-1.4 1.4zM20 10.5v2h3v-2h-3zm-8-5c-3.31 0-6 2.69-6 6s2.69 6 6 6 6-2.69 6-6-2.69-6-6-6zm-1 16.95h2V19.5h-2v2.95zm-7.45-3.91l1.41 1.41 1.79-1.8-1.41-1.41-1.79 1.8z",

    # ---- 其他 ----
    "add": "M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z",
    "sort": "M3 18h6v-2H3v2zM3 6v2h18V6H3zm0 7h12v-2H3v2z",
    "language": "M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zm6.93 6h-2.95c-.32-1.25-.78-2.45-1.38-3.56 1.84.63 3.37 1.91 4.33 3.56zM12 4.04c.83 1.2 1.48 2.53 1.91 3.96h-3.82c.43-1.43 1.08-2.76 1.91-3.96zM4.26 14C4.1 13.36 4 12.69 4 12s.1-1.36.26-2h3.38c-.08.66-.14 1.32-.14 2 0 .68.06 1.34.14 2H4.26zm.82 2h2.95c.32 1.25.78 2.45 1.38 3.56-1.84-.63-3.37-1.9-4.33-3.56zm2.95-8H5.08c.96-1.66 2.49-2.93 4.33-3.56C8.81 5.55 8.35 6.75 8.03 8zM12 19.96c-.83-1.2-1.48-2.53-1.91-3.96h3.82c-.43 1.43-1.08 2.76-1.91 3.96zM14.34 14H9.66c-.09-.66-.16-1.32-.16-2 0-.68.07-1.35.16-2h4.68c.09.65.16 1.32.16 2 0 .68-.07 1.34-.16 2zm.25 5.56c.6-1.11 1.06-2.31 1.38-3.56h2.95c-.96 1.65-2.49 2.93-4.33 3.56zM16.36 14c.08-.66.14-1.32.14-2 0-.68-.06-1.34-.14-2h3.38c.16.64.26 1.31.26 2s-.1 1.36-.26 2h-3.38z",
    "settings": "M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.07.62-.07.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z",
    "log": "M20 2H4c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zM8 20H4v-4h4v4zm0-6H4v-4h4v4zm0-6H4V4h4v4zm6 12h-4v-4h4v4zm0-6h-4v-4h4v4zm0-6h-4V4h4v4zm6 12h-4v-4h4v4zm0-6h-4v-4h4v4zm0-6h-4V4h4v4z",
    "wizard": "M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z",
    "about": "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z",

    # ---- 导出格式 ----
    "export_csv": "M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6zm-1 7V3.5L18.5 9H13zM7 17v-1h2v1H7zm0-2v-1h3v1H7zm0-2v-1h4v1H7z",
    "export_markdown": "M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6zm-1 7V3.5L18.5 9H13zM6 20V4h5v7h7v9H6zm2-6h8v1.5H8V14zm0 3h8v1.5H8V17z",
    "export_html": "M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6zm-1 7V3.5L18.5 9H13zM9 13l1.5 3-1.5 3h1.5l.75-1.5.75 1.5H15l-1.5-3 1.5-3h-1.5l-.75 1.5-.75-1.5H9z",
    "export_header": "M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6zm-1 7V3.5L18.5 9H13zM6.5 13l1 1.5-1 1.5h1l.5-.75.5.75h1l-1-1.5 1-1.5h-1l-.5.75-.5-.75h-1z",
}

# ==================== 图标颜色配置 (Material Design 色板) ====================

ICON_COLORS = {
    # 主色
    "primary": "#1976D2",       # Blue 700
    "primary_light": "#42A5F5", # Blue 400
    # 功能色
    "file": "#546E7A",          # Blue Grey 600
    "edit": "#78909C",          # Blue Grey 400
    "success": "#43A047",       # Green 600
    "warning": "#FB8C00",       # Orange 600
    "error": "#E53935",         # Red 600
    "info": "#1E88E5",          # Blue 600
    # 树节点色
    "peripheral": "#1565C0",    # Blue 800
    "register": "#2E7D32",      # Green 800
    "field": "#6A1B9A",         # Purple 800
    "interrupt": "#E65100",     # Orange 900
    # 中性色
    "grey": "#616161",          # Grey 700
    "grey_light": "#9E9E9E",    # Grey 500
    # 主题色
    "dark_theme": "#5C6BC0",    # Indigo 400
    "light_theme": "#FFA000",   # Amber 700
}


class MaterialIconProvider:
    """Material Design 风格图标提供器"""

    _instance = None

    def __init__(self):
        self._icon_cache = {}

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _render_svg_path(self, path_data: str, color: str = "#616161",
                         size: int = 24, stroke: float = 0.0) -> QIcon:
        """渲染 SVG path 数据为 QIcon"""
        key = f"{path_data[:20]}_{color}_{size}_{stroke}"
        if key in self._icon_cache:
            return self._icon_cache[key]

        # 生成多个分辨率的 pixmap
        icon = QIcon()
        for scale in [1, 2]:
            px_size = size * scale
            pixmap = QPixmap(px_size, px_size)
            pixmap.fill(Qt.GlobalColor.transparent)

            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            # 解析颜色
            qcolor = QColor(color)
            painter.setBrush(qcolor)

            if stroke > 0:
                painter.setPen(QPen(qcolor, stroke))
            else:
                painter.setPen(Qt.PenStyle.NoPen)

            # 缩放到当前 pixmap 尺寸
            painter.setViewport(0, 0, px_size, px_size)
            painter.setWindow(0, 0, 24, 24)

            # 解析并绘制 SVG path
            path = self._parse_svg_path(path_data)
            painter.drawPath(path)

            painter.end()
            icon.addPixmap(pixmap)

        self._icon_cache[key] = icon
        return icon

    def _parse_svg_path(self, d: str) -> QPainterPath:
        """解析 SVG path 的 d 属性，生成 QPainterPath"""
        path = QPainterPath()
        if not d:
            return path

        import re
        tokens = re.findall(r'[MmLlHhVvCcSsQqTtAaZz]|[-+]?[0-9]*\.?[0-9]+', d)

        i = 0
        cx, cy = 0.0, 0.0  # 当前点
        sx, sy = 0.0, 0.0  # 子路径起点

        def next_val():
            nonlocal i
            if i < len(tokens):
                v = float(tokens[i])
                i += 1
                return v
            return 0.0

        while i < len(tokens):
            cmd = tokens[i]
            i += 1

            if cmd == 'M':
                cx, cy = next_val(), next_val()
                path.moveTo(cx, cy)
                sx, sy = cx, cy
                # 后续隐含 L
                while i < len(tokens) and tokens[i] not in 'MmLlHhVvCcSsQqTtAaZz':
                    cx, cy = next_val(), next_val()
                    path.lineTo(cx, cy)
            elif cmd == 'm':
                cx, cy = cx + next_val(), cy + next_val()
                path.moveTo(cx, cy)
                sx, sy = cx, cy
                while i < len(tokens) and tokens[i] not in 'MmLlHhVvCcSsQqTtAaZz':
                    cx, cy = cx + next_val(), cy + next_val()
                    path.lineTo(cx, cy)
            elif cmd == 'L':
                cx, cy = next_val(), next_val()
                path.lineTo(cx, cy)
            elif cmd == 'l':
                cx, cy = cx + next_val(), cy + next_val()
                path.lineTo(cx, cy)
            elif cmd == 'H':
                cx = next_val()
                path.lineTo(cx, cy)
            elif cmd == 'h':
                cx += next_val()
                path.lineTo(cx, cy)
            elif cmd == 'V':
                cy = next_val()
                path.lineTo(cx, cy)
            elif cmd == 'v':
                cy += next_val()
                path.lineTo(cx, cy)
            elif cmd == 'C':
                x1, y1 = next_val(), next_val()
                x2, y2 = next_val(), next_val()
                cx, cy = next_val(), next_val()
                path.cubicTo(x1, y1, x2, y2, cx, cy)
            elif cmd == 'c':
                x1, y1 = cx + next_val(), cy + next_val()
                x2, y2 = cx + next_val(), cy + next_val()
                cx, cy = cx + next_val(), cy + next_val()
                path.cubicTo(x1, y1, x2, y2, cx, cy)
            elif cmd == 'S':
                x2, y2 = next_val(), next_val()
                cx, cy = next_val(), next_val()
                path.cubicTo(cx, cy, x2, y2, cx, cy)
            elif cmd == 's':
                x2, y2 = cx + next_val(), cy + next_val()
                cx, cy = cx + next_val(), cy + next_val()
                path.cubicTo(cx, cy, x2, y2, cx, cy)
            elif cmd == 'Q':
                x1, y1 = next_val(), next_val()
                cx, cy = next_val(), next_val()
                path.quadTo(x1, y1, cx, cy)
            elif cmd == 'q':
                x1, y1 = cx + next_val(), cy + next_val()
                cx, cy = cx + next_val(), cy + next_val()
                path.quadTo(x1, y1, cx, cy)
            elif cmd == 'T':
                cx, cy = next_val(), next_val()
                path.lineTo(cx, cy)
            elif cmd == 't':
                cx, cy = cx + next_val(), cy + next_val()
                path.lineTo(cx, cy)
            elif cmd in ('Z', 'z'):
                path.closeSubpath()
                cx, cy = sx, sy

        return path

    def _get(self, name: str, color: str = "") -> QIcon:
        """获取图标"""
        if name not in ICON_PATHS:
            return QIcon()
        c = color or ICON_COLORS.get("grey", "#616161")
        return self._render_svg_path(ICON_PATHS[name], c)

    # ==================== 菜单栏图标 ====================

    def file_new(self) -> QIcon:
        return self._get("file_new", ICON_COLORS["file"])

    def file_open(self) -> QIcon:
        return self._get("file_open", ICON_COLORS["file"])

    def file_save(self) -> QIcon:
        return self._get("file_save", ICON_COLORS["file"])

    def file_save_as(self) -> QIcon:
        return self._get("file_save_as", ICON_COLORS["file"])

    def file_exit(self) -> QIcon:
        return self._get("file_close", ICON_COLORS["grey"])

    def edit_undo(self) -> QIcon:
        return self._get("undo", ICON_COLORS["edit"])

    def edit_redo(self) -> QIcon:
        return self._get("redo", ICON_COLORS["edit"])

    def edit_cut(self) -> QIcon:
        return self._get("cut", ICON_COLORS["edit"])

    def edit_copy(self) -> QIcon:
        return self._get("copy", ICON_COLORS["edit"])

    def edit_paste(self) -> QIcon:
        return self._get("paste", ICON_COLORS["edit"])

    def view_expand(self) -> QIcon:
        return self._get("expand_all", ICON_COLORS["primary"])

    def view_collapse(self) -> QIcon:
        return self._get("collapse_all", ICON_COLORS["primary"])

    def tools_validate(self) -> QIcon:
        return self._get("status_ok", ICON_COLORS["success"])

    def tools_generate(self) -> QIcon:
        return self._get("generate", ICON_COLORS["primary"])

    def tools_export(self) -> QIcon:
        return self._get("export_file", ICON_COLORS["primary"])

    def tools_diff(self) -> QIcon:
        return self._get("diff", ICON_COLORS["info"])

    def tools_chain(self) -> QIcon:
        return self._get("chain", ICON_COLORS["primary_light"])

    def help_about(self) -> QIcon:
        return self._get("about", ICON_COLORS["info"])

    # ==================== 工具栏图标 ====================

    def toolbar_new(self) -> QIcon:
        return self.file_new()

    def toolbar_open(self) -> QIcon:
        return self.file_open()

    def toolbar_save(self) -> QIcon:
        return self.file_save()

    def toolbar_undo(self) -> QIcon:
        return self.edit_undo()

    def toolbar_redo(self) -> QIcon:
        return self.edit_redo()

    def toolbar_generate(self) -> QIcon:
        return self.tools_generate()

    def toolbar_preview(self) -> QIcon:
        return self._get("visible_on", ICON_COLORS["primary"])

    # ==================== 树形视图层级图标 ====================

    def tree_peripheral(self) -> QIcon:
        """外设图标 - Material Blue"""
        return self._get("peripheral", ICON_COLORS["peripheral"])

    def tree_register(self) -> QIcon:
        """寄存器图标 - Material Green"""
        return self._get("register", ICON_COLORS["register"])

    def tree_field(self) -> QIcon:
        """位域图标 - Material Purple"""
        return self._get("field", ICON_COLORS["field"])

    def tree_interrupt(self) -> QIcon:
        """中断图标 - Material Orange"""
        return self._get("interrupt", ICON_COLORS["interrupt"])

    # ==================== 状态栏图标 ====================

    def status_ready(self) -> QIcon:
        return self._get("status_ok", ICON_COLORS["success"])

    def status_error(self) -> QIcon:
        return self._get("status_error", ICON_COLORS["error"])

    def status_warning(self) -> QIcon:
        return self._get("status_warning", ICON_COLORS["warning"])

    # ==================== 通用图标 ====================

    def search(self) -> QIcon:
        return self._get("search", ICON_COLORS["grey"])

    def search_prev(self) -> QIcon:
        return self._get("arrow_prev", ICON_COLORS["grey"])

    def search_next(self) -> QIcon:
        return self._get("arrow_next", ICON_COLORS["grey"])

    def add(self) -> QIcon:
        return self._get("add", ICON_COLORS["success"])

    def delete(self) -> QIcon:
        return self._get("delete", ICON_COLORS["error"])

    def edit(self) -> QIcon:
        return self._get("edit", ICON_COLORS["primary"])

    def move_up(self) -> QIcon:
        return self._get("arrow_up", ICON_COLORS["grey"])

    def move_down(self) -> QIcon:
        return self._get("arrow_down", ICON_COLORS["grey"])

    def sort(self) -> QIcon:
        return self._get("sort", ICON_COLORS["grey"])

    def language(self) -> QIcon:
        return self._get("language", ICON_COLORS["primary"])

    def log(self) -> QIcon:
        return self._get("log", ICON_COLORS["grey"])

    def settings(self) -> QIcon:
        return self._get("settings", ICON_COLORS["grey"])

    def dark_mode(self) -> QIcon:
        return self._get("dark_mode", ICON_COLORS["dark_theme"])

    def light_mode(self) -> QIcon:
        return self._get("light_mode", ICON_COLORS["light_theme"])

    def export_csv(self) -> QIcon:
        return self._get("export_csv", ICON_COLORS["primary"])

    def export_markdown(self) -> QIcon:
        return self._get("export_markdown", ICON_COLORS["primary"])

    def export_html(self) -> QIcon:
        return self._get("export_html", ICON_COLORS["primary"])

    def export_header(self) -> QIcon:
        return self._get("export_header", ICON_COLORS["primary"])

    def wizard(self) -> QIcon:
        return self._get("wizard", ICON_COLORS["primary"])

    def visible_on(self) -> QIcon:
        return self._get("visible_on", ICON_COLORS["primary"])

    def visible_off(self) -> QIcon:
        return self._get("visible_off", ICON_COLORS["grey_light"])

    def toggle_panel(self) -> QIcon:
        return self._get("toggle_panel", ICON_COLORS["grey"])


# ==================== 兼容旧接口 ====================

# 保留旧名称作为别名
IconProvider = MaterialIconProvider


def get_icon(icon_name: str) -> QIcon:
    """获取图标的全局便捷函数

    Args:
        icon_name: 图标名称，对应 IconProvider 的方法名

    Returns:
        QIcon 实例
    """
    provider = MaterialIconProvider.instance()
    method = getattr(provider, icon_name, None)
    if method:
        return method()
    return QIcon()