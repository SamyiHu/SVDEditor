"""
数据手册导入向导 — Excel/Word/PDF → SVD。

5 页流程：
1. 模式选择：单源快速导入 / 多源融合导入
2. 来源选择：文件/目录选择（单源1个槽，多源3个槽 + 策略 + 主源）
3. 解析进度：后台线程解析，进度日志
4. 预览 + 置信度：外设树（置信度色标）+ 统计 + 融合冲突计数
5. 导入选项：新建文档 / 并入当前文档 + 设备名

仿 NewSVDWizard 的 QWizard 模式，复用 get_style_scheme() 配色。
解析通过 DatasourceManager.run_parse 后台线程执行，进度/完成/失败经信号回报。
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QLabel, QLineEdit, QComboBox, QGroupBox, QTextEdit, QPlainTextEdit,
    QPushButton, QRadioButton, QButtonGroup, QFileDialog, QMessageBox,
    QTreeWidget, QTreeWidgetItem, QProgressBar, QHeaderView, QSizePolicy,
    QCheckBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from ...i18n.i18n import t
from ...config.styles import get_style_scheme
from ..managers.datasource_manager import DatasourceManager
from ...core.datasource.parser_bridge import ParseRequest, is_parser_available

# 置信度 → 显示色（与核对面板一致）
_CONF_COLORS = {
    "high": QColor("#2E7D32"),     # 绿
    "medium": QColor("#1565C0"),   # 蓝
    "low": QColor("#E65100"),      # 橙
    "missing": QColor("#C62828"),  # 红
    "unknown": QColor("#9E9E9E"),  # 灰
}
_CONF_LABELS = {
    "high": "高", "medium": "中", "low": "低",
    "missing": "缺失", "unknown": "未知",
}


class ImportWizard(QWizard):
    """数据手册导入向导。"""

    def __init__(self, parent, datasource_manager: DatasourceManager):
        super().__init__(parent)
        self.mgr = datasource_manager
        self._result_holder = {}   # 页面间共享状态（非 field）

        self.setWindowTitle(t("datasource.wizard_title", default="从数据手册导入"))
        self.setMinimumSize(720, 560)
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setOption(QWizard.WizardOption.HaveHelpButton, False)
        self.setOption(QWizard.WizardOption.IndependentPages, False)

        # Parser 不可用时仍允许打开（在解析页报错），但给提示
        self._parser_ok = is_parser_available()

        self.mode_page = ModeSelectPage(self)
        self.source_page = SourceSelectPage(self)
        self.parse_page = ParseProgressPage(self)
        self.preview_page = PreviewPage(self)
        self.import_page = ImportOptionsPage(self)

        self.addPage(self.mode_page)
        self.addPage(self.source_page)
        self.addPage(self.parse_page)
        self.addPage(self.preview_page)
        self.addPage(self.import_page)

        # 当前页切换钩子（用于触发解析、刷新预览）
        self.currentIdChanged.connect(self._on_page_changed)
        self.accepted.connect(self._do_import)

    # ---------- 跨页状态访问 ----------

    @property
    def mode(self) -> str:
        return "fusion" if self.mode_page.fusion_radio.isChecked() else "single"

    @property
    def sources(self) -> dict:
        return self.source_page.collect_sources(self.mode)

    @property
    def primary_source(self) -> str:
        return self.source_page.primary_combo.currentText().lower() if hasattr(self.source_page, "primary_combo") else ""

    @property
    def strategy(self) -> str:
        return "fusion" if self.mode == "fusion" else "single"

    @property
    def chip_name(self) -> str:
        return self.import_page.chip_name_edit.text().strip()

    @property
    def import_mode(self) -> str:
        return "merge" if self.import_page.merge_radio.isChecked() else "new_document"

    @property
    def style_english(self) -> bool:
        return self.import_page.style_english_chk.isChecked()

    # ---------- 页面切换 ----------

    def _on_page_changed(self, page_id: int):
        # 进入解析页 → 启动后台解析
        if page_id == 2:  # ParseProgressPage
            self.parse_page.start_parse(self)
        # 进入预览页 → 填充数据
        elif page_id == 3:  # PreviewPage
            self.preview_page.populate(self)
        # 进入导入选项页 → 填充设备名 + 检测并入冲突
        elif page_id == 4:  # ImportOptionsPage
            self.import_page.populate(self)

    def _do_import(self):
        """向导完成 → 执行导入。"""
        chip_data = getattr(self.mgr, "last_chip_data", None)
        if chip_data is None:
            QMessageBox.warning(self, t("message.warning"),
                                t("datasource.no_parsed_data", default="没有解析结果，无法导入"))
            return
        if self.chip_name:
            try:
                chip_data.chip_name = self.chip_name
            except Exception:
                pass
        try:
            if self.import_mode == "merge":
                res = self.mgr.merge_into_current(chip_data, style_english=self.style_english)
                report = res.get("report", {})
                QMessageBox.information(
                    self, t("datasource.import_done", default="导入完成"),
                    t("datasource.merge_done_msg",
                      added=report.get("peripherals_added", 0),
                      regs=report.get("registers_added", 0),
                      skipped=report.get("peripherals_skipped", 0),
                      default=(f"已并入当前文档：新增 {report.get('peripherals_added', 0)} 外设 / "
                               f"{report.get('registers_added', 0)} 寄存器"
                               f"（跳过 {report.get('peripherals_skipped', 0)} 个同名外设）")))
            else:
                doc_id = self.mgr.import_as_new_document(
                    chip_data, display_name=self.chip_name or "",
                    style_english=self.style_english)
                n_p = len(chip_data.peripherals or [])
                if doc_id:
                    QMessageBox.information(
                        self, t("datasource.import_done", default="导入完成"),
                        t("datasource.new_done_msg", p=n_p,
                          default=f"已作为新文档导入：{n_p} 个外设"))
                else:
                    QMessageBox.warning(
                        self, t("message.warning"),
                        t("datasource.import_failed", default="导入失败，请查看日志"))
        except Exception as e:
            QMessageBox.critical(self, t("message.error"),
                                 t("datasource.import_error", msg=str(e),
                                   default=f"导入出错：{e}"))


# ════════════════════════════════════════════════════
# 第 1 页：模式选择
# ════════════════════════════════════════════════════

class ModeSelectPage(QWizardPage):
    def __init__(self, wizard: ImportWizard):
        super().__init__(wizard)
        self.setTitle(t("datasource.step1_title", default="选择导入模式"))
        self.setSubTitle(t("datasource.step1_subtitle",
                           default="单源快速导入适合只有一个数据源；多源融合可交叉验证、提升准确度"))

        layout = QVBoxLayout(self)

        self.single_radio = QRadioButton(t(
            "datasource.mode_single", default="单源快速导入"))
        self.single_radio.setChecked(True)
        self.fusion_radio = QRadioButton(t(
            "datasource.mode_fusion", default="多源融合导入（交叉验证）"))

        single_desc = QLabel(t("datasource.mode_single_desc",
            default="从 Excel / Word / PDF 中的一种快速导入。速度快，但无法交叉验证。"))
        fusion_desc = QLabel(t("datasource.mode_fusion_desc",
            default="同时提供多种来源，按置信度加权融合。能发现各源分歧、提升一致项的可信度，适合关键芯片建档。"))
        for lbl in (single_desc, fusion_desc):
            lbl.setWordWrap(True)
            lbl.setStyleSheet("color: gray; margin-left: 24px;")

        layout.addWidget(self.single_radio)
        layout.addWidget(single_desc)
        layout.addSpacing(8)
        layout.addWidget(self.fusion_radio)
        layout.addWidget(fusion_desc)
        layout.addStretch()

        if not wizard._parser_ok:
            warn = QLabel(t("datasource.parser_missing_warn",
                default="⚠ 检测到 Parser 或其依赖（openpyxl/pdfplumber/pymupdf/python-docx）未安装。"
                        "继续将无法解析。"))
            warn.setWordWrap(True)
            warn.setStyleSheet("color: #C62828; font-weight: bold; padding: 8px;")
            layout.addWidget(warn)


# ════════════════════════════════════════════════════
# 第 2 页：来源选择
# ════════════════════════════════════════════════════

class SourceSelectPage(QWizardPage):
    def __init__(self, wizard: ImportWizard):
        super().__init__(wizard)
        self.setTitle(t("datasource.step2_title", default="选择数据来源"))
        self.setSubTitle(t("datasource.step2_subtitle",
                           default="每个来源可选「目录」或「多选文件」。一个外设一个文件时选目录"))
        self._slots = {}   # source_name → QLineEdit

        layout = QVBoxLayout(self)

        # 格式说明
        hint = QLabel(t("datasource.format_hint",
            default="💡 Excel：推荐选目录（一个外设一个 .xlsx）；也可多选文件。"
                    "Word：选 TRM 参考手册 .docx（自动走 pandoc 三段式解析）。"
                    "PDF：选技术手册 .pdf 或其所在目录。"))
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; padding: 4px; font-size: 9pt;")
        layout.addWidget(hint)

        # 三个来源槽，每个有「选目录」+「选文件(多选)」两个按钮
        self._build_slot(layout, "excel",
                         t("datasource.source_excel", default="Excel SFR 表"),
                         "Excel 文件 (*.xlsx *.xls)")
        self._build_slot(layout, "word",
                         t("datasource.source_word", default="Word 文档（TRM）"),
                         "Word 文件 (*.docx)")
        self._build_slot(layout, "pdf",
                         t("datasource.source_pdf", default="PDF 手册"),
                         "PDF 文件 (*.pdf)")

        # 主源选择（多源融合时用）
        primary_box = QGroupBox(t("datasource.primary_source_group", default="融合策略"))
        pb_layout = QFormLayout(primary_box)
        self.primary_combo = QComboBox()
        self.primary_combo.addItems(["excel", "word", "pdf"])
        pb_layout.addRow(t("datasource.primary_source", default="单源直通时的主源："), self.primary_combo)
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItem(t("datasource.strategy_fusion", default="融合（加权裁决）"), "fusion")
        self.strategy_combo.addItem(t("datasource.strategy_single", default="单源直通（取主源）"), "single")
        self.strategy_combo.setCurrentIndex(0)
        pb_layout.addRow(t("datasource.strategy_label", default="策略："), self.strategy_combo)
        layout.addWidget(primary_box)

        layout.addStretch()

    def _build_slot(self, parent_layout, name: str, label: str, file_filter: str):
        row = QHBoxLayout()
        row.addWidget(QLabel(label + ":"))
        edit = QLineEdit()
        edit.setPlaceholderText(t("datasource.path_hint",
            default="目录路径，或多个文件路径（分号分隔）"))
        row.addWidget(edit, 1)
        # 「选目录」按钮（目录优先）
        dir_btn = QPushButton(t("datasource.btn_choose_dir", default="选目录"))
        dir_btn.clicked.connect(lambda _checked, e=edit: self._choose_dir(e))
        row.addWidget(dir_btn)
        # 「选文件」按钮（支持多选）
        file_btn = QPushButton(t("datasource.btn_choose_files", default="选文件…"))
        file_btn.clicked.connect(lambda _checked, e=edit, f=file_filter, n=name:
                                 self._choose_files(e, f, n))
        row.addWidget(file_btn)
        parent_layout.addLayout(row)
        self._slots[name] = edit

    def _choose_dir(self, edit: QLineEdit):
        dir_path = QFileDialog.getExistingDirectory(self, t("datasource.btn_choose_dir", default="选目录"))
        if dir_path:
            edit.setText(dir_path)

    def _choose_files(self, edit: QLineEdit, file_filter: str, name: str):
        paths, _ = QFileDialog.getOpenFileNames(
            self, t("datasource.btn_choose_files", default="选择文件（可多选）"), "", file_filter)
        if paths:
            edit.setText(";".join(paths))

    def collect_sources(self, mode: str) -> dict:
        """根据模式收集非空来源。

        多个文件用分号分隔时：若是同一目录下的多文件，返回该目录（Excel 一个外设一文件场景更友好）；
        否则保留分号串（Parser 的 parse 接目录，TRM 解析器接文件/目录，分号串由各解析器处理）。
        单源模式只用第一个非空槽。
        """
        result = {}
        for name, edit in self._slots.items():
            text = edit.text().strip()
            if not text:
                continue
            # 多文件：若都在同一目录，归约成目录
            if ";" in text:
                parts = [p.strip() for p in text.split(";") if p.strip()]
                if parts:
                    import os
                    dirs = {os.path.dirname(p) for p in parts}
                    if len(dirs) == 1:
                        result[name] = parts[0] if len(parts) == 1 else next(iter(dirs))
                    else:
                        result[name] = text  # 跨目录：保留分号串
            else:
                result[name] = text
        if mode == "single" and result:
            # 单源：按权重取首个
            for pri in ("excel", "word", "pdf"):
                if pri in result:
                    return {pri: result[pri]}
        return result

    def validatePage(self) -> bool:
        """Next 按钮校验：至少有一个非空来源。"""
        wizard: ImportWizard = self.wizard()
        sources = self.collect_sources(wizard.mode)
        if not sources:
            QMessageBox.warning(self, t("message.warning"),
                                t("datasource.no_source_selected",
                                  default="请至少为一个来源选择文件/目录"))
            return False
        return True


# ════════════════════════════════════════════════════
# 第 3 页：解析进度
# ════════════════════════════════════════════════════

class ParseProgressPage(QWizardPage):
    def __init__(self, wizard: ImportWizard):
        super().__init__(wizard)
        self.setTitle(t("datasource.step3_title", default="解析中…"))
        self.setSubTitle(t("datasource.step3_subtitle",
                           default="后台解析数据手册，请稍候。解析大 PDF 可能需要数秒到数十秒"))
        self._done = False

        layout = QVBoxLayout(self)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # 不确定进度（busy）
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel(t("datasource.parse_preparing", default="准备解析…"))
        layout.addWidget(self.status_label)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(500)
        layout.addWidget(self.log, 1)

    def start_parse(self, wizard: ImportWizard):
        """进入本页时启动解析。"""
        self._done = False
        self.progress_bar.show()
        self.log.clear()
        self._append_log(t("datasource.parse_starting", default="开始解析…"))

        # 连接管理器信号
        mgr = wizard.mgr
        try:
            mgr.parse_progress.disconnect()
        except TypeError:
            pass
        try:
            mgr.parse_finished.disconnect()
        except TypeError:
            pass
        try:
            mgr.parse_failed.disconnect()
        except TypeError:
            pass
        mgr.parse_progress.connect(self._on_progress)
        mgr.parse_finished.connect(self._on_finished)
        mgr.parse_failed.connect(self._on_failed)

        request = ParseRequest(
            sources=wizard.sources,
            strategy=wizard.strategy,
            primary_source=wizard.primary_source,
            chip_name=wizard.chip_name,
        )
        if not mgr.run_parse(request):
            self._on_failed(t("datasource.parse_busy", default="已有解析任务进行中"))

    def _append_log(self, msg: str):
        self.log.appendPlainText(msg)

    def _on_progress(self, msg: str):
        self.status_label.setText(msg)
        self._append_log(msg)

    def _on_finished(self, result):
        self.progress_bar.hide()
        q = result.quality or {}
        self._done = True
        self._append_log(t("datasource.parse_ok",
                           p=q.get("peripherals", 0), r=q.get("registers", 0), f=q.get("fields", 0),
                           default=(f"解析完成：{q.get('peripherals', 0)} 外设 / "
                                    f"{q.get('registers', 0)} 寄存器 / {q.get('fields', 0)} 位域")))
        self.status_label.setText(t("datasource.parse_ok_status", default="解析完成，点击下一步预览"))
        self.completeChanged.emit()

    def _on_failed(self, msg: str):
        self.progress_bar.hide()
        self._done = False
        self._append_log(t("datasource.parse_fail", msg=msg, default=f"解析失败：{msg}"))
        self.status_label.setText(t("datasource.parse_fail_status", default="解析失败，请返回上一步检查来源"))

    def isComplete(self) -> bool:
        """Next 按钮在解析完成前禁用。"""
        return self._done


# ════════════════════════════════════════════════════
# 第 4 页：预览 + 置信度
# ════════════════════════════════════════════════════

class PreviewPage(QWizardPage):
    def __init__(self, wizard: ImportWizard):
        super().__init__(wizard)
        self.setTitle(t("datasource.step4_title", default="预览解析结果"))
        self.setSubTitle(t("datasource.step4_subtitle",
                           default="查看外设结构与置信度分布。绿色=高、蓝色=中、橙色=低、红色=缺失"))

        layout = QVBoxLayout(self)

        # 统计面板
        stats_box = QGroupBox(t("datasource.stats_group", default="统计"))
        stats_layout = QGridLayout(stats_box)
        self.stat_labels = {}
        for i, key in enumerate(["peripherals", "registers", "fields"]):
            stats_layout.addWidget(QLabel(t(f"datasource.stat_{key}",
                default={"peripherals": "外设", "registers": "寄存器", "fields": "位域"}[key])),
                0, i)
            lbl = QLabel("0")
            lbl.setStyleSheet("font-size: 16pt; font-weight: bold;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            stats_layout.addWidget(lbl, 1, i)
            self.stat_labels[key] = lbl
        # 置信度分布
        conf_row = QHBoxLayout()
        self.conf_labels = {}
        for conf in ("high", "medium", "low", "missing", "unknown"):
            box = QVBoxLayout()
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {_CONF_COLORS[conf].name()}; font-size: 14pt;")
            dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val = QLabel("0")
            val.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val.setStyleSheet(f"color: {_CONF_COLORS[conf].name()}; font-weight: bold;")
            cap = QLabel(_CONF_LABELS[conf])
            cap.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cap.setStyleSheet("color: gray;")
            box.addWidget(dot)
            box.addWidget(val)
            box.addWidget(cap)
            conf_row.addLayout(box)
            self.conf_labels[conf] = val
        stats_layout.addLayout(conf_row, 2, 0, 1, 3)
        layout.addWidget(stats_box)

        # 外设树
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([t("datasource.tree_name", default="名称"),
                                   t("datasource.tree_detail", default="详情"),
                                   t("datasource.tree_conf", default="置信度")])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.tree, 1)

        # 融合信息（仅多源时显示）
        self.fusion_label = QLabel("")
        self.fusion_label.setWordWrap(True)
        self.fusion_label.setStyleSheet("color: #1565C0; padding: 4px;")
        layout.addWidget(self.fusion_label)

    def populate(self, wizard: ImportWizard):
        """填充预览。"""
        result = getattr(wizard.mgr, "last_result", None)
        if result is None or result.chip_data is None:
            self.tree.clear()
            return
        cd = result.chip_data
        q = result.quality or {}
        self.stat_labels["peripherals"].setText(str(q.get("peripherals", 0)))
        self.stat_labels["registers"].setText(str(q.get("registers", 0)))
        self.stat_labels["fields"].setText(str(q.get("fields", 0)))
        fc = q.get("field_confidence", {})
        for conf, lbl in self.conf_labels.items():
            lbl.setText(str(fc.get(conf, 0)))

        # 外设树
        self.tree.clear()
        for pblk in (getattr(cd, "peripherals", []) or [])[:200]:
            p_item = QTreeWidgetItem([pblk.name,
                                      f"{t('datasource.base', default='基址')}: {getattr(pblk, 'base_address', '')}",
                                      ""])
            p_item.setForeground(2, _CONF_COLORS.get(_periph_conf(pblk), QColor("gray")))
            for reg in (pblk.registers or [])[:300]:
                r_item = QTreeWidgetItem([reg.name,
                                          f"{t('datasource.off', default='偏移')}: {getattr(reg, 'address_offset', '')}",
                                          getattr(reg, "confidence", "")])
                r_item.setForeground(2, _CONF_COLORS.get(getattr(reg, "confidence", ""), QColor("gray")))
                p_item.addChild(r_item)
                for f in (reg.fields or [])[:200]:
                    f_item = QTreeWidgetItem([f.name,
                                              f"bit[{getattr(f, 'bit_pos', 0)}:{getattr(f, 'bit_pos', 0) + max(getattr(f, 'bit_width', 1), 1) - 1}]",
                                              getattr(f, "confidence", "")])
                    f_item.setForeground(2, _CONF_COLORS.get(getattr(f, "confidence", ""), QColor("gray")))
                    r_item.addChild(f_item)
            self.tree.addTopLevelItem(p_item)

        # 融合信息
        if result.fusion_report is not None and result.strategy == "fusion":
            fr = result.fusion_report
            self.fusion_label.setText(t("datasource.fusion_info",
                conflicts=len(fr.conflicts), promotions=len(fr.promotions),
                default=(f"多源融合：{len(fr.conflicts)} 处冲突待复核，"
                         f"{len(fr.promotions)} 处一致性提升。可在「工具 → 多源融合审阅」详查")))
        else:
            self.fusion_label.setText("")


# ════════════════════════════════════════════════════
# 第 5 页：导入选项
# ════════════════════════════════════════════════════

class ImportOptionsPage(QWizardPage):
    def __init__(self, wizard: ImportWizard):
        super().__init__(wizard)
        self.setTitle(t("datasource.step5_title", default="选择导入方式"))
        self.setSubTitle(t("datasource.step5_subtitle",
                           default="作为新文档打开（推荐）或并入当前文档"))

        layout = QVBoxLayout(self)

        self.new_radio = QRadioButton(t("datasource.import_new", default="作为新文档打开（推荐）"))
        self.new_radio.setChecked(True)
        self.merge_radio = QRadioButton(t("datasource.import_merge", default="并入当前文档（同名外设跳过）"))
        layout.addWidget(self.new_radio)
        layout.addWidget(self.merge_radio)

        # 英文描述风格化开关（AI 翻译中文描述 → 英文，并对齐参考 SVD 格式）
        self.style_english_chk = QCheckBox(t("datasource.style_english",
            default="应用英文描述风格（AI 翻译 + displayName/resetValue 格式对齐）"))
        style_hint = QLabel(t("datasource.style_english_hint",
            default="💡 勾选后中文描述由 AI 翻译为英文，并补齐 displayName、补 8 位 resetValue、归一化 groupName。需配置 AI 助手"))
        style_hint.setWordWrap(True)
        style_hint.setStyleSheet("color: gray; font-size: 9pt; margin-left: 24px;")
        layout.addWidget(self.style_english_chk)
        layout.addWidget(style_hint)

        # 设备名
        form = QFormLayout()
        self.chip_name_edit = QLineEdit()
        self.chip_name_edit.setPlaceholderText(t("datasource.chip_name_hint", default="留空则用解析推断的设备名"))
        form.addRow(t("datasource.chip_name_label", default="设备名："), self.chip_name_edit)
        layout.addLayout(form)

        # 影响范围提示
        self.impact_label = QLabel("")
        self.impact_label.setWordWrap(True)
        self.impact_label.setStyleSheet("color: #E65100; padding: 8px;")
        layout.addWidget(self.impact_label)
        layout.addStretch()

    def populate(self, wizard: ImportWizard):
        result = getattr(wizard.mgr, "last_result", None)
        if result and result.chip_data:
            if not self.chip_name_edit.text():
                self.chip_name_edit.setText(getattr(result.chip_data, "chip_name", "") or "")
        # 并入模式影响提示
        if self.merge_radio.isChecked():
            state_manager = wizard.mgr.coordinator.get_component("state_manager")
            existing = set()
            if state_manager and state_manager.device_info:
                existing = set(state_manager.device_info.peripherals.keys())
            new_names = set()
            if result and result.chip_data:
                new_names = {p.name for p in result.chip_data.peripherals if p.name}
            overlap = existing & new_names
            if overlap:
                self.impact_label.setText(t("datasource.merge_overlap_warn", n=len(overlap),
                    sample=", ".join(list(overlap)[:5]),
                    default=(f"⚠ 当前文档已有 {len(overlap)} 个同名外设将被跳过（如 {', '.join(list(overlap)[:5])}…）")))
            else:
                self.impact_label.setText(t("datasource.merge_no_overlap",
                    default="✓ 无同名外设冲突，将全部新增"))
        else:
            self.impact_label.setText(t("datasource.new_doc_hint",
                default="将创建新文档并切换为当前文档，不影响已打开的文档"))


def _periph_conf(pblk) -> str:
    best = "unknown"
    order = {"unknown": 0, "missing": 1, "low": 2, "medium": 3, "high": 4}
    for r in getattr(pblk, "registers", []) or []:
        c = getattr(r, "confidence", "unknown") or "unknown"
        if order.get(c, 0) > order.get(best, 0):
            best = c
    return best
