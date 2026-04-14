"""
VSCode风格欢迎页面
启动时显示，导入/新建SVD后切换到编辑器视图
"""
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QGridLayout, QApplication, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QIcon, QCursor, QPainter, QPen, QLinearGradient


class WelcomePage(QWidget):
    """VSCode风格欢迎页面"""
    
    # 信号
    new_file_requested = pyqtSignal()
    open_file_requested = pyqtSignal()
    open_recent_requested = pyqtSignal(str)  # 文件路径
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._recent_files = []
        self._setup_ui()
    
    def _setup_ui(self):
        """构建欢迎页UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 顶部渐变装饰条
        top_bar = QFrame()
        top_bar.setFixedHeight(3)
        top_bar.setObjectName("welcomeTopBar")
        main_layout.addWidget(top_bar)
        
        # 内容区域（居中）
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(60, 40, 60, 40)
        
        # 左侧：品牌区域
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 40, 0)
        
        # 应用名称
        title = QLabel("SVD Editor")
        title_font = QFont()
        title_font.setPointSize(28)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setObjectName("welcomeTitle")
        left_layout.addWidget(title)
        
        # 版本信息
        version = QLabel("Professional v2.1")
        version_font = QFont()
        version_font.setPointSize(11)
        version.setFont(version_font)
        version.setObjectName("welcomeSubtitle")
        left_layout.addWidget(version)
        
        # 描述
        desc = QLabel("专业的SVD文件可视化编辑工具\n支持 CMSIS-SVD 标准格式")
        desc_font = QFont()
        desc_font.setPointSize(10)
        desc.setFont(desc_font)
        desc.setObjectName("welcomeDesc")
        desc.setWordWrap(True)
        left_layout.addWidget(desc)
        
        left_layout.addSpacing(20)
        
        # 操作按钮
        self._create_action_button(left_layout, "📂  打开 SVD 文件", 
            "选择一个现有的 .svd 文件进行编辑", self.open_file_requested)
        self._create_action_button(left_layout, "📄  新建 SVD 文件", 
            "通过向导创建一个新的SVD文件", self.new_file_requested)
        
        left_layout.addStretch()
        
        # 右侧：最近文件和帮助
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(40, 0, 0, 0)
        
        # 最近文件
        recent_title = QLabel("最近打开")
        recent_title_font = QFont()
        recent_title_font.setPointSize(13)
        recent_title_font.setBold(True)
        recent_title.setFont(recent_title_font)
        recent_title.setObjectName("welcomeSectionTitle")
        right_layout.addWidget(recent_title)
        
        # 最近文件容器
        self._recent_container = QVBoxLayout()
        self._recent_container.setSpacing(4)
        right_layout.addLayout(self._recent_container)
        
        # 无最近文件提示
        self._no_recent_label = QLabel("暂无最近打开的文件")
        self._no_recent_label.setObjectName("welcomeNoRecent")
        no_recent_font = QFont()
        no_recent_font.setPointSize(10)
        self._no_recent_label.setFont(no_recent_font)
        self._recent_container.addWidget(self._no_recent_label)
        
        right_layout.addSpacing(30)
        
        # 帮助/快捷操作
        help_title = QLabel("快捷操作")
        help_title_font = QFont()
        help_title_font.setPointSize(13)
        help_title_font.setBold(True)
        help_title.setFont(help_title_font)
        help_title.setObjectName("welcomeSectionTitle")
        right_layout.addWidget(help_title)
        
        shortcuts = [
            ("Ctrl+N", "新建文件"),
            ("Ctrl+O", "打开文件"),
            ("Ctrl+S", "保存文件"),
            ("Ctrl+Z", "撤销操作"),
            ("Ctrl+Y", "重做操作"),
            ("Ctrl+F", "搜索"),
            ("F9", "切换左侧面板"),
        ]
        
        for key, desc_text in shortcuts:
            shortcut_row = QHBoxLayout()
            key_label = QLabel(key)
            key_label.setObjectName("welcomeShortcutKey")
            key_label.setFixedWidth(70)
            key_font = QFont()
            key_font.setFamily("Consolas")
            key_font.setPointSize(9)
            key_label.setFont(key_font)
            key_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            shortcut_row.addWidget(key_label)
            
            desc_label = QLabel(desc_text)
            desc_label.setObjectName("welcomeShortcutDesc")
            desc_font = QFont()
            desc_font.setPointSize(10)
            desc_label.setFont(desc_font)
            shortcut_row.addWidget(desc_label)
            shortcut_row.addStretch()
            right_layout.addLayout(shortcut_row)
        
        right_layout.addStretch()
        
        content_layout.addWidget(left_panel, 1)
        content_layout.addWidget(right_panel, 1)
        
        main_layout.addWidget(content, 1)
        
        # 底部信息
        footer = QLabel("© 2025 SVD Editor  |  Powered by PyQt6")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setObjectName("welcomeFooter")
        footer_font = QFont()
        footer_font.setPointSize(9)
        footer.setFont(footer_font)
        footer.setFixedHeight(30)
        main_layout.addWidget(footer)
    
    def _create_action_button(self, parent_layout, text, description, signal):
        """创建操作按钮"""
        btn_frame = QFrame()
        btn_frame.setObjectName("welcomeActionBtn")
        btn_frame.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_frame.setFixedHeight(56)
        btn_layout = QVBoxLayout(btn_frame)
        btn_layout.setContentsMargins(16, 6, 16, 6)
        
        btn_text = QLabel(text)
        btn_text_font = QFont()
        btn_text_font.setPointSize(12)
        btn_text_font.setBold(True)
        btn_text.setFont(btn_text_font)
        btn_text.setObjectName("welcomeActionBtnText")
        btn_layout.addWidget(btn_text)
        
        btn_desc = QLabel(description)
        btn_desc_font = QFont()
        btn_desc_font.setPointSize(9)
        btn_desc.setFont(btn_desc_font)
        btn_desc.setObjectName("welcomeActionBtnDesc")
        btn_layout.addWidget(btn_desc)
        
        btn_frame.mousePressEvent = lambda e: signal.emit()
        parent_layout.addWidget(btn_frame)
    
    def set_recent_files(self, files: list):
        """设置最近打开的文件列表"""
        # 清除现有项
        while self._recent_container.count():
            item = self._recent_container.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        
        if not files:
            no_label = QLabel("暂无最近打开的文件")
            no_label.setObjectName("welcomeNoRecent")
            font = QFont()
            font.setPointSize(10)
            no_label.setFont(font)
            self._recent_container.addWidget(no_label)
            return
        
        for file_path in files[:5]:  # 最多显示5个
            name = os.path.basename(file_path)
            dir_path = os.path.dirname(file_path)
            
            row = QFrame()
            row.setObjectName("welcomeRecentItem")
            row.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(10, 6, 10, 6)
            row_layout.setSpacing(2)
            
            name_label = QLabel(name)
            name_font = QFont()
            name_font.setPointSize(10)
            name_font.setBold(True)
            name_label.setFont(name_font)
            name_label.setObjectName("welcomeRecentName")
            row_layout.addWidget(name_label)
            
            display_path = dir_path if len(dir_path) < 50 else "..." + dir_path[-47:]
            path_label = QLabel(display_path)
            path_font = QFont()
            path_font.setPointSize(8)
            path_label.setFont(path_font)
            path_label.setObjectName("welcomeRecentPath")
            row_layout.addWidget(path_label)
            
            row.mousePressEvent = lambda e, p=file_path: self.open_recent_requested.emit(p)
            self._recent_container.addWidget(row)
    
    def paintEvent(self, event):
        """绘制背景"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        from ...config.styles import is_dark_mode, get_style_scheme
        if is_dark_mode():
            bg_color = QColor(get_style_scheme().colors.welcome_bg_dark)
            painter.fillRect(self.rect(), bg_color)
        else:
            bg_color = QColor(get_style_scheme().colors.welcome_bg_light)
            painter.fillRect(self.rect(), bg_color)
        
        painter.end()