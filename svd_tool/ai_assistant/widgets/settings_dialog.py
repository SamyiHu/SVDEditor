"""
AI 助手配置对话框
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QFormLayout, QLineEdit, QComboBox,
    QCheckBox, QPushButton, QLabel, QPlainTextEdit,
    QDialogButtonBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDoubleValidator, QIntValidator

from ...config.styles import get_style_scheme
from ..config import AIConfig
from ...i18n.i18n import t


class AISettingsDialog(QDialog):
    """AI 助手设置对话框"""

    def __init__(self, config: AIConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._setup_ui()
        self._load_config()
        self._apply_styles()

    def _setup_ui(self):
        """构建 UI"""
        self.setWindowTitle(t("ai.settings.title", default="AI 助手设置"))
        self.setMinimumWidth(480)
        self.setMinimumHeight(520)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # API 配置组
        layout.addWidget(self._create_api_group())

        # 模型设置组
        layout.addWidget(self._create_model_group())

        # 高级设置组
        layout.addWidget(self._create_advanced_group())

        # 按钮
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)

        # 设置按钮文本
        ok_btn = btn_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setText(t("button.save", default="保存"))
        cancel_btn = btn_box.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setText(t("button.cancel", default="取消"))

        layout.addWidget(btn_box)

    def _create_api_group(self) -> QGroupBox:
        """创建 API 配置组"""
        group = QGroupBox(t("ai.settings.api_group", default="API 配置"))
        form = QFormLayout(group)
        form.setSpacing(8)

        # API 类型
        self._api_type_combo = QComboBox()
        self._api_type_combo.addItem("OpenAI 兼容", "openai")
        self._api_type_combo.addItem("Anthropic Claude", "anthropic")
        self._api_type_combo.currentIndexChanged.connect(self._on_api_type_changed)
        form.addRow("API 类型:", self._api_type_combo)

        # Endpoint URL
        self._api_url_edit = QLineEdit()
        self._api_url_edit.setPlaceholderText("https://api.openai.com/v1")
        form.addRow("Endpoint URL:", self._api_url_edit)

        # API Key
        key_layout = QHBoxLayout()
        key_layout.setSpacing(6)
        self._api_key_edit = QLineEdit()
        self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_edit.setPlaceholderText("sk-...")
        key_layout.addWidget(self._api_key_edit, 1)

        self._toggle_key_btn = QPushButton(t("ai.settings.show_key", default="显示"))
        self._toggle_key_btn.setCheckable(True)
        self._toggle_key_btn.setFixedWidth(50)
        self._toggle_key_btn.clicked.connect(self._toggle_key_visibility)
        key_layout.addWidget(self._toggle_key_btn)

        form.addRow("API Key:", key_layout)

        # 测试连接按钮
        test_layout = QHBoxLayout()
        test_layout.addStretch()
        self._test_btn = QPushButton(t("ai.settings.test_connection", default="测试连接"))
        self._test_btn.clicked.connect(self._test_connection)
        test_layout.addWidget(self._test_btn)

        self._test_result_label = QLabel("")
        test_layout.addWidget(self._test_result_label)

        form.addRow("", test_layout)

        return group

    def _create_model_group(self) -> QGroupBox:
        """创建模型设置组"""
        group = QGroupBox(t("ai.settings.model_group", default="模型设置"))
        form = QFormLayout(group)
        form.setSpacing(8)

        # 模型名称
        self._model_combo = QComboBox()
        self._model_combo.setEditable(True)
        self._model_combo.addItems([
            "gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo",
            "claude-sonnet-4-20250514", "claude-haiku-4-20250414", "claude-opus-4-20250514",
            "deepseek-chat", "deepseek-coder",
        ])
        form.addRow("模型:", self._model_combo)

        # Temperature — 用 QLineEdit 替代 QDoubleSpinBox
        self._temp_edit = QLineEdit("0.3")
        self._temp_edit.setValidator(QDoubleValidator(0.0, 2.0, 1))
        self._temp_edit.setPlaceholderText("0.0 ~ 2.0")
        form.addRow("Temperature:", self._temp_edit)

        # Max Tokens — 用 QLineEdit 替代 QSpinBox
        self._max_tokens_edit = QLineEdit("2048")
        self._max_tokens_edit.setValidator(QIntValidator(256, 32768))
        self._max_tokens_edit.setPlaceholderText("256 ~ 32768")
        form.addRow("Max Tokens:", self._max_tokens_edit)

        # 流式
        self._streaming_check = QCheckBox(t("ai.settings.streaming", default="启用流式响应"))
        form.addRow("", self._streaming_check)

        return group

    def _create_advanced_group(self) -> QGroupBox:
        """创建高级设置组"""
        group = QGroupBox(t("ai.settings.advanced", default="高级设置"))
        form = QFormLayout(group)
        form.setSpacing(8)

        # 超时时间 — QLineEdit + 后缀
        timeout_layout = QHBoxLayout()
        timeout_layout.setSpacing(4)
        self._timeout_edit = QLineEdit("60")
        self._timeout_edit.setValidator(QIntValidator(10, 600))
        self._timeout_edit.setPlaceholderText("10 ~ 600")
        timeout_layout.addWidget(self._timeout_edit, 1)
        timeout_suffix = QLabel("s")
        timeout_layout.addWidget(timeout_suffix)
        form.addRow(t("ai.settings.timeout", default="超时时间:"), timeout_layout)

        # 历史消息数量 — QLineEdit
        self._history_edit = QLineEdit("50")
        self._history_edit.setValidator(QIntValidator(10, 200))
        self._history_edit.setPlaceholderText("10 ~ 200")
        form.addRow(t("ai.settings.max_history", default="历史消息数:"), self._history_edit)

        # 自定义系统提示词
        self._system_prompt_edit = QPlainTextEdit()
        self._system_prompt_edit.setMaximumHeight(80)
        self._system_prompt_edit.setPlaceholderText(t(
            "ai.settings.system_prompt_hint",
            default="可选：添加自定义指令补充到系统提示词中"
        ))
        form.addRow(t("ai.settings.extra_prompt", default="额外提示词:"), self._system_prompt_edit)

        return group

    def _load_config(self):
        """从配置加载到 UI"""
        # API 类型
        idx = self._api_type_combo.findData(self.config.api_type)
        if idx >= 0:
            self._api_type_combo.setCurrentIndex(idx)

        self._api_url_edit.setText(self.config.api_base_url)
        self._api_key_edit.setText(self.config.api_key)

        # 模型
        idx = self._model_combo.findText(self.config.model)
        if idx >= 0:
            self._model_combo.setCurrentIndex(idx)
        else:
            self._model_combo.setEditText(self.config.model)

        self._temp_edit.setText(str(self.config.temperature))
        self._max_tokens_edit.setText(str(self.config.max_tokens))
        self._streaming_check.setChecked(self.config.enable_streaming)

        # 高级
        self._timeout_edit.setText(str(self.config.request_timeout))
        self._history_edit.setText(str(self.config.max_history_messages))
        self._system_prompt_edit.setPlainText(self.config.system_prompt_extra)

    def _safe_float(self, text: str, default: float, lo: float, hi: float) -> float:
        """安全解析浮点数"""
        try:
            v = float(text)
            return max(lo, min(hi, v))
        except (ValueError, TypeError):
            return default

    def _safe_int(self, text: str, default: int, lo: int, hi: int) -> int:
        """安全解析整数"""
        try:
            v = int(text)
            return max(lo, min(hi, v))
        except (ValueError, TypeError):
            return default

    def get_config(self) -> AIConfig:
        """从 UI 获取配置"""
        return AIConfig(
            api_key=self._api_key_edit.text().strip(),
            api_base_url=self._api_url_edit.text().strip() or "https://api.openai.com/v1",
            api_type=self._api_type_combo.currentData() or "openai",
            model=self._model_combo.currentText().strip() or "gpt-4o-mini",
            temperature=self._safe_float(self._temp_edit.text(), 0.3, 0.0, 2.0),
            max_tokens=self._safe_int(self._max_tokens_edit.text(), 2048, 256, 32768),
            enable_streaming=self._streaming_check.isChecked(),
            max_history_messages=self._safe_int(self._history_edit.text(), 50, 10, 200),
            request_timeout=self._safe_int(self._timeout_edit.text(), 60, 10, 600),
            system_prompt_extra=self._system_prompt_edit.toPlainText().strip(),
        )

    def _on_api_type_changed(self, index: int):
        """API 类型切换时更新默认 URL"""
        api_type = self._api_type_combo.currentData()
        if api_type == "anthropic":
            if self._api_url_edit.text() in ("", "https://api.openai.com/v1"):
                self._api_url_edit.setText("https://api.anthropic.com")
        else:
            if self._api_url_edit.text() in ("", "https://api.anthropic.com"):
                self._api_url_edit.setText("https://api.openai.com/v1")

    def _toggle_key_visibility(self, checked: bool):
        """切换 API Key 显示/隐藏"""
        if checked:
            self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self._toggle_key_btn.setText(t("ai.settings.hide_key", default="隐藏"))
        else:
            self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self._toggle_key_btn.setText(t("ai.settings.show_key", default="显示"))

    def _test_connection(self):
        """测试 API 连接"""
        config = self.get_config()
        if not config.api_key:
            self._test_result_label.setText("请输入 API Key")
            self._test_result_label.setStyleSheet("color: red;")
            return

        self._test_btn.setEnabled(False)
        self._test_result_label.setText("测试中...")
        self._test_result_label.setStyleSheet("color: gray;")

        try:
            from ..backend import create_backend
            backend = create_backend(config.api_type)

            # 发送最小请求
            messages = [
                {"role": "user", "content": "Hi"}
            ]
            response = backend.chat(messages, config)

            if response:
                self._test_result_label.setText(
                    t("ai.settings.test_success", default="连接成功")
                )
                scheme = get_style_scheme()
                self._test_result_label.setStyleSheet(f"color: {scheme.colors.success};")
            else:
                self._test_result_label.setText(
                    t("ai.settings.test_fail", default="连接失败：空响应")
                )
                self._test_result_label.setStyleSheet("color: red;")
        except ImportError as e:
            self._test_result_label.setText(f"缺少依赖: {e}")
            self._test_result_label.setStyleSheet("color: red;")
        except Exception as e:
            self._test_result_label.setText(f"失败: {str(e)[:80]}")
            self._test_result_label.setStyleSheet("color: red;")
        finally:
            self._test_btn.setEnabled(True)

    def _apply_styles(self):
        """应用对话框样式"""
        scheme = get_style_scheme()
        c = scheme.colors
        s = scheme.sizes

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {c.background};
            }}
            QGroupBox {{
                font-weight: bold;
                font-size: 10pt;
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
                color: {c.text_primary};
            }}
            QLineEdit, QComboBox {{
                border: 1px solid {c.border};
                border-radius: {s.radius_sm};
                padding: 4px 8px;
                background-color: {c.white};
                min-height: 24px;
            }}
            QLineEdit:focus, QComboBox:focus {{
                border-color: {c.accent};
            }}
            QPushButton {{
                border: 1px solid {c.border_light};
                border-radius: {s.radius_sm};
                padding: 4px 12px;
                background-color: {c.surface};
                color: {c.text_primary};
                min-height: 26px;
            }}
            QPushButton:hover {{
                background-color: {c.hover};
                border-color: {c.accent};
            }}
            QPushButton:checked {{
                background-color: {c.accent_light};
                border-color: {c.accent};
                color: {c.accent};
            }}
            QPlainTextEdit {{
                border: 1px solid {c.border};
                border-radius: {s.radius_sm};
                padding: 4px;
                background-color: {c.white};
            }}
            QLabel {{
                color: {c.text_primary};
            }}
            QCheckBox {{
                color: {c.text_primary};
            }}
        """)
