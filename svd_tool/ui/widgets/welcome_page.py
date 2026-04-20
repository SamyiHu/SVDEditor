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

from ...i18n.i18n import t


class WelcomePage(QWidget):
    """VSCode风格欢迎页面"""
    
    # 信号
    new_file_requested = pyqtSignal()
    open_file_requested = pyqtSignal()
    open_recent_requested = pyqtSignal(str)  # 文件路径
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._recent_files = []
        self._content = None
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
        self._content = QWidget()
        content_layout = QHBoxLayout(self._content)
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
        version = QLabel(t("welcome.version"))
        version_font = QFont()
        version_font.setPointSize(11)
        version.setFont(version_font)
        version.setObjectName("welcomeSubtitle")
        left_layout.addWidget(version)
        
        # 描述
        desc = QLabel(t("welcome.description"))
        desc_font = QFont()
        desc_font.setPointSize(10)
        desc.setFont(desc_font)
        desc.setObjectName("welcomeDesc")
        desc.setWordWrap(True)
        left_layout.addWidget(desc)
        
        left_layout.addSpacing(20)
        
        # 操作按钮
        self._create_action_button(left_layout, "📂  " + t("welcome.open_file"),
            t("welcome.open_file_desc"), self.open_file_requested)
        self._create_action_button(left_layout, "📄  " + t("welcome.new_file"),
            t("welcome.new_file_desc"), self.new_file_requested)
        
        left_layout.addStretch()
        
        # 右侧：最近文件和帮助
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(40, 0, 0, 0)
        
        # 最近文件
        recent_title = QLabel(t("welcome.recent"))
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
        self._no_recent_label = QLabel(t("welcome.no_recent"))
        self._no_recent_label.setObjectName("welcomeNoRecent")
        no_recent_font = QFont()
        no_recent_font.setPointSize(10)
        self._no_recent_label.setFont(no_recent_font)
        self._recent_container.addWidget(self._no_recent_label)
        
        right_layout.addSpacing(30)
        
        # 帮助/快捷操作
        help_title = QLabel(t("welcome.shortcuts"))
        help_title_font = QFont()
        help_title_font.setPointSize(13)
        help_title_font.setBold(True)
        help_title.setFont(help_title_font)
        help_title.setObjectName("welcomeSectionTitle")
        right_layout.addWidget(help_title)
        
        shortcuts = [
            ("Ctrl+N", t("welcome.shortcut.new")),
            ("Ctrl+O", t("welcome.shortcut.open")),
            ("Ctrl+S", t("welcome.shortcut.save")),
            ("Ctrl+Z", t("welcome.shortcut.undo")),
            ("Ctrl+Y", t("welcome.shortcut.redo")),
            ("Ctrl+F", t("welcome.shortcut.search")),
            ("F9", t("welcome.shortcut.toggle_panel")),
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

        main_layout.addWidget(self._content, 1)
        
        # 底部信息
        footer = QLabel(t("welcome.footer"))
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
    
    def refresh_ui(self):
        """刷新欢迎页文本（切换语言后调用）"""
        if self._content is None:
            return
        # 按 objectName 更新静态文本
        for label in self._content.findChildren(QLabel):
            name = label.objectName()
            if name == "welcomeSubtitle":
                label.setText(t("welcome.version"))
            elif name == "welcomeDesc":
                label.setText(t("welcome.description"))
            elif name == "welcomeNoRecent":
                label.setText(t("welcome.no_recent"))
            elif name == "welcomeSectionTitle":
                # 区分"最近打开"和"快捷操作"靠位置判断
                parent = label.parentWidget()
                if parent and parent.objectName() == "":
                    # 更简洁的方式：两个 section title 交替出现
                    pass
            elif name == "welcomeActionBtnText":
                text = label.text()
                if "📂" in text or "打开" in text or "Open" in text:
                    label.setText("📂  " + t("welcome.open_file"))
                elif "📄" in text or "新建" in text or "New" in text:
                    label.setText("📄  " + t("welcome.new_file"))
            elif name == "welcomeActionBtnDesc":
                parent = label.parentWidget()
                if parent:
                    btn_texts = [lbl.text() for lbl in parent.findChildren(QLabel) if lbl.objectName() == "welcomeActionBtnText"]
                    if btn_texts:
                        txt = btn_texts[0]
                        if "📂" in txt or "打开" in txt or "Open" in txt:
                            label.setText(t("welcome.open_file_desc"))
                        else:
                            label.setText(t("welcome.new_file_desc"))
            elif name == "welcomeShortcutDesc":
                key_label = None
                row = label.parentWidget()
                if row:
                    for child in row.findChildren(QLabel):
                        if child.objectName() == "welcomeShortcutKey":
                            key_label = child
                            break
                if key_label:
                    key = key_label.text()
                    shortcut_map = {
                        "Ctrl+N": "welcome.shortcut.new",
                        "Ctrl+O": "welcome.shortcut.open",
                        "Ctrl+S": "welcome.shortcut.save",
                        "Ctrl+Z": "welcome.shortcut.undo",
                        "Ctrl+Y": "welcome.shortcut.redo",
                        "Ctrl+F": "welcome.shortcut.search",
                        "F9": "welcome.shortcut.toggle_panel",
                    }
                    if key in shortcut_map:
                        label.setText(t(shortcut_map[key]))
            elif name == "welcomeFooter":
                label.setText(t("welcome.footer"))
        # 更新 section titles (两个，按出现顺序)
        section_titles = [lbl for lbl in self._content.findChildren(QLabel) if lbl.objectName() == "welcomeSectionTitle"]
        if len(section_titles) >= 1:
            section_titles[0].setText(t("welcome.recent"))
        if len(section_titles) >= 2:
            section_titles[1].setText(t("welcome.shortcuts"))
        # 刷新最近文件列表（重新应用翻译）
        self.set_recent_files(self._recent_files)

    def set_recent_files(self, files: list):
        """设置最近打开的文件列表"""
        self._recent_files = files
        # 清除现有项
        while self._recent_container.count():
            item = self._recent_container.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        
        if not files:
            no_label = QLabel(t("welcome.no_recent"))
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