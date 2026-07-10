"""
数据源管理器 — 资源导入 / 自动生成 / SVD 核对 的统一调度中心。

职责：
1. 后台线程调用 Parser 解析 Excel/Word/PDF（单源或多源融合）
2. 把解析结果转为 DeviceInfo 并导入（新建文档 或 并入当前文档，均走撤销栈）
3. 用解析结果核对当前 SVD，产出结构化差异项
4. 单项/批量「接受」核对差异（undoable）

线程模型：
- 解析（重 IO/CPU）用 QThreadPool 后台跑，通过信号回报进度/完成/失败
- 写回（导入/接受差异）在主线程执行，包入 CommandHistory 保证可撤销
- AI 工具（CommandExecutor）调用 parse_sync 直跑解析（read-only，在 worker 线程）

注册到 Coordinator 为 'datasource_manager'，供 UI 与 AI 共用同一缓存。
"""
from __future__ import annotations

import logging
import traceback
from typing import Any, Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

from ...core.datasource.parser_bridge import (
    ParserBridge, ParseRequest, ParseResult, ParserUnavailableError,
)
from ...core.datasource.chip_to_svd_converter import ChipToSvdConverter
from ...core.datasource.svd_verifier import SVDVerifier, VerifyItem
from ...core.data_model import DeviceInfo, Peripheral, Register, Field
from ...core.command_history import Command

logger = logging.getLogger("svd_tool.ui.DatasourceManager")


class _ParseWorker(QObject):
    """解析工作线程对象（移到 QThread 执行）。"""
    finished = pyqtSignal(object)   # ParseResult
    failed = pyqtSignal(str)        # 错误消息
    progress = pyqtSignal(str)

    def __init__(self, request: ParseRequest):
        super().__init__()
        self._request = request

    @pyqtSlot()
    def run(self):
        try:
            self.progress.emit("正在加载数据手册解析器…")
            bridge = ParserBridge()
            result = bridge.parse_sync(self._request)
            if result.errors:
                self.failed.emit("\n".join(result.errors))
            else:
                self.finished.emit(result)
        except ParserUnavailableError as e:
            hint = ""
            if e.missing_deps:
                hint = f"\n\n请安装缺失依赖：pip install {' '.join(e.missing_deps)}"
            self.failed.emit(str(e) + hint)
        except Exception as e:
            logger.exception("解析线程异常")
            self.failed.emit(f"解析失败：{e}\n{traceback.format_exc()[-300:]}")


class DatasourceManager(QObject):
    """资源导入 / SVD 核对 管理器。

    缓存最近一次解析结果（last_chip_data），供核对面板与 AI 工具复用，
    避免重复解析同一份手册。
    """

    # ── 信号 ──
    parse_started = pyqtSignal()
    parse_progress = pyqtSignal(str)
    parse_finished = pyqtSignal(object)        # ParseResult
    parse_failed = pyqtSignal(str)
    parse_unavailable = pyqtSignal(str, list)  # (message, missing_deps)

    import_finished = pyqtSignal(str)          # doc_id 或 ""（失败）
    verify_ready = pyqtSignal(list)            # list[VerifyItem]
    verify_failed = pyqtSignal(str)
    items_accepted = pyqtSignal(int)           # 本次接受的项数

    def __init__(self, coordinator, main_window=None):
        super().__init__()
        self.coordinator = coordinator
        self.main_window = main_window
        self._bridge = ParserBridge()
        self._converter = ChipToSvdConverter()
        self._verifier = SVDVerifier()

        # 最近一次解析结果缓存（核对面板 / AI 核对工具共用）
        self.last_result: Optional[ParseResult] = None
        self.last_chip_data: Any = None

        # 解析线程句柄（持有引用避免 GC）
        self._thread: Optional[QThread] = None
        self._worker: Optional[_ParseWorker] = None

    # ════════════════════════════════════════════════════
    # 解析（异步，UI 用）
    # ════════════════════════════════════════════════════

    def run_parse(self, request: ParseRequest) -> bool:
        """启动后台解析（非阻塞）。返回是否成功启动。"""
        if self._thread is not None and self._thread.isRunning():
            self.parse_failed.emit("已有解析任务在进行中")
            return False

        self._thread = QThread()
        self._worker = _ParseWorker(request)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)

        # 结果/错误都先回到主线程，再 emit 对外信号
        self._worker.progress.connect(self.parse_progress)
        self._worker.finished.connect(self._on_parse_done)
        self._worker.failed.connect(self._on_parse_failed)
        # 线程结束后清理
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(lambda: setattr(self, "_thread", None))

        self.parse_started.emit()
        self._thread.start()
        return True

    @pyqtSlot(object)
    def _on_parse_done(self, result: ParseResult):
        """解析完成（主线程）。缓存结果并广播。"""
        self.last_result = result
        self.last_chip_data = result.chip_data if result else None
        self.parse_finished.emit(result)

    @pyqtSlot(str)
    def _on_parse_failed(self, message: str):
        self.parse_failed.emit(message)

    def parse_sync(self, request: ParseRequest) -> ParseResult:
        """同步解析（AI 工具 / 测试用，阻塞当前线程）。"""
        return self._bridge.parse_sync(request)

    # ════════════════════════════════════════════════════
    # 导入
    # ════════════════════════════════════════════════════

    def import_as_new_document(self, chip_data: Any, display_name: str = "",
                               style_english: bool = False) -> str:
        """把 ChipData 转为 DeviceInfo 并作为新文档打开。

        Args:
            style_english: True 时对描述做英文风格化（AI 翻译 + 格式修正），
                           使输出符合参考 SVD 风格。需配置 AI。
        Returns:
            doc_id 或 ""（失败）
        """
        device, report = self._converter.convert(chip_data)
        if style_english:
            self._apply_description_style(device)
        return self._open_as_document(device, display_name or device.name)

    def merge_into_current(self, chip_data: Any, style_english: bool = False) -> dict:
        """把 ChipData 并入当前活跃文档（撤销栈）。

        Args:
            style_english: True 时对描述做英文风格化。
        Returns:
            {"doc_id": str, "report": ConversionReport.to_dict()}
        """
        state_manager = self.coordinator.get_component("state_manager")
        dm = self.main_window.document_manager if self.main_window else None
        if not state_manager or not state_manager.device_info or not dm:
            self.import_finished.emit("")
            return {"doc_id": "", "report": {}}

        target = state_manager.device_info
        device, report = self._converter.convert(chip_data, target=target, merge=True)
        if style_english:
            self._apply_description_style(device)

        # 通过撤销栈整体替换 device_info 的外设/中断
        # 记录旧快照用于撤销
        old_periphs = _shallow_copy_dict(state_manager.device_info.peripherals)
        old_irqs = _shallow_copy_dict(state_manager.device_info.interrupts)
        new_periphs = device.peripherals
        new_irqs = device.interrupts

        def _execute():
            state_manager.device_info.peripherals = new_periphs
            state_manager.device_info.interrupts = new_irqs

        def _undo():
            state_manager.device_info.peripherals = old_periphs
            state_manager.device_info.interrupts = old_irqs

        self._execute_undoable("数据手册并入当前文档", _execute, _undo)
        self._notify_refresh()
        self._mark_modified()

        self.import_finished.emit(dm.active_doc_id or "")
        return {"doc_id": dm.active_doc_id or "", "report": report.to_dict()}

    def _open_as_document(self, device: DeviceInfo, display_name: str) -> str:
        """把 device 作为新文档打开并完整切换 UI 到它。

        必须复刻主窗口 _assemble_loaded_document 的关键步骤：
        1. 保存当前文档状态（保证数据隔离）
        2. 暂停通知 → 把 state_manager.device_info 换成新 device → 重建树/中断表/预览
        3. 注册文档到 DocumentManager 并切换 active
        4. 显示编辑器页面（从欢迎页切换）

        只调 new_document()+switch_to() 是不够的——那不会更新 state_manager.device_info，
        也不会重建树/切换到编辑器页，表现为「新建标签但内容是旧文档/停留在欢迎页」。
        """
        mw = self.main_window
        if mw is None:
            self.import_finished.emit("")
            return ""
        try:
            # 1. 保存当前文档状态（保证数据隔离）
            if hasattr(mw, "_save_current_document_state"):
                mw._save_current_document_state()

            # 2. 把新 device 装入 state_manager 并重建 UI（暂停通知避免多次刷新）
            sm = self.coordinator.get_component("state_manager")
            if sm is None:
                self.import_finished.emit("")
                return ""
            if hasattr(sm, "pause_notifications"):
                sm.pause_notifications()
            try:
                sm.device_info = device
                if hasattr(sm, "clear_selection"):
                    sm.clear_selection()
                if hasattr(sm, "command_history") and sm.command_history is not None:
                    sm.command_history.clear()
                # 重置预览器选中/折叠状态
                pm = getattr(mw, "preview_manager", None)
                if pm and getattr(pm, "preview_widget", None):
                    pw = pm.preview_widget
                    pw.folded_elements = set()
                    if hasattr(pw, "current_selection"):
                        pw.current_selection = {'type': None, 'peripheral': None,
                                                'register': None, 'field': None, 'interrupt': None}
                    if hasattr(pw, "preview_edit") and pw.preview_edit:
                        pw.preview_edit.clear_highlight()
                # 重建树（不保留旧文档展开状态）
                if hasattr(mw, "peripheral_manager") and mw.peripheral_manager:
                    mw.peripheral_manager.update_peripheral_tree(preserve_expanded=False)
                if hasattr(mw, "update_data_stats"):
                    mw.update_data_stats()
                if hasattr(mw, "_update_interrupt_table"):
                    mw._update_interrupt_table()
            finally:
                if hasattr(sm, "resume_notifications"):
                    sm.resume_notifications()

            # 3. 注册到文档管理器并切换 active
            dm = mw.document_manager
            doc_id = dm.open_document(device, file_path=None, display_name=display_name)
            dm.switch_to(doc_id)

            # 4. 显示编辑器页面（从欢迎页切换过来）
            if hasattr(mw, "layout_manager") and mw.layout_manager:
                if hasattr(mw.layout_manager, "show_editor"):
                    mw.layout_manager.show_editor()
                if hasattr(mw.layout_manager, "update_basic_info"):
                    mw.layout_manager.update_basic_info(device)
                if hasattr(mw.layout_manager, "update_status"):
                    mw.layout_manager.update_status(display_name)

            self.import_finished.emit(doc_id)
            return doc_id
        except Exception as e:
            logger.exception("新建文档失败")
            self.import_finished.emit("")
            return ""

    # ════════════════════════════════════════════════════
    # 描述风格化（英文翻译 + 格式修正）
    # ════════════════════════════════════════════════════

    def _apply_description_style(self, device) -> dict:
        """对 device 的描述做英文风格化（AI 翻译 + 格式对齐参考 SVD）。

        从已配置的 AI 读取 config；AI 未配置则用词典回退。
        """
        from ...core.datasource.description_styler import DescriptionStyler
        ai_config = None
        try:
            from ...ai_assistant.config import AIConfigManager
            cfg = AIConfigManager().load()
            if cfg.api_key:
                ai_config = cfg
        except Exception:
            pass
        styler = DescriptionStyler()

        def _progress(done, total, msg):
            self.parse_progress.emit(msg)

        return styler.style(device, ai_config=ai_config, progress_cb=_progress)

    # ════════════════════════════════════════════════════
    # 核对
    # ════════════════════════════════════════════════════

    def run_verify(self, chip_data: Any = None) -> list[VerifyItem]:
        """核对当前活跃文档与解析结果。

        Args:
            chip_data: 显式指定；None 则用缓存的 last_chip_data

        Returns:
            list[VerifyItem]
        """
        cd = chip_data if chip_data is not None else self.last_chip_data
        state_manager = self.coordinator.get_component("state_manager")
        if cd is None:
            msg = "没有可用的解析结果。请先从数据手册导入，再执行核对。"
            self.verify_failed.emit(msg)
            return []
        if not state_manager or not state_manager.device_info:
            self.verify_failed.emit("当前没有打开的 SVD 文档。")
            return []

        items = self._verifier.verify(state_manager.device_info, cd)
        self.verify_ready.emit(items)
        return items

    def accept_verify_item(self, item: VerifyItem) -> bool:
        """接受单个核对差异项（undoable）。返回是否成功。"""
        return self._apply_suggested([item]) == 1

    def accept_items(self, items: list[VerifyItem]) -> int:
        """批量接受差异项（单条撤销记录，silent 风格刷新）。返回成功数。"""
        if not items:
            return 0
        n = self._apply_suggested(items)
        if n > 0:
            self.items_accepted.emit(n)
        return n

    def _apply_suggested(self, items: list[VerifyItem]) -> int:
        """把差异项的 suggested 应用到当前 device_info（撤销栈 + 刷新）。"""
        state_manager = self.coordinator.get_component("state_manager")
        if not state_manager or not state_manager.device_info:
            return 0
        device = state_manager.device_info

        applied = []     # (undo_fn) 列表，整体回滚
        count = 0

        for item in items:
            if not item.suggested:
                continue
            undo = self._apply_one(device, item)
            if undo is not None:
                applied.append(undo)
                count += 1

        if count == 0:
            return 0

        # 把所有 undo 闭包合并为一条撤销记录
        def _execute():
            pass  # 修改已在上面即时应用

        def _undo():
            for fn in reversed(applied):
                fn()

        desc = f"接受 {count} 项核对建议" if count > 1 else "接受核对建议"
        self._execute_undoable(desc, _execute, _undo)
        self._notify_refresh()
        self._mark_modified()
        return count

    def _apply_one(self, device: DeviceInfo, item: VerifyItem):
        """对单个差异项应用 suggested，返回 undo 闭包（None 表示无法应用）。

        缺失项（missing_in_svd）→ 新增外设/寄存器/位域（undo=删除）
        不符项（mismatch）→ 改属性（undo=还原）
        仅在源侧缺失（missing_in_source）→ 不动（属于 SVD 独有信息）
        """
        periphs = device.peripherals
        pname = item.peripheral

        # 外设级缺失 → 新增整个外设
        if item.kind == "missing_in_svd":
            s = item.suggested
            if pname in periphs:
                return None
            new_p = Peripheral(
                name=s.get("name", pname),
                base_address=s.get("base_address", "0x40000000"),
                group_name=s.get("group_name", ""),
                description=s.get("description", ""),
            )
            def _undo():
                periphs.pop(pname, None)
            periphs[pname] = new_p
            return _undo

        periph = periphs.get(pname)
        if periph is None:
            return None

        # 外设级 base_address 不符
        if item.level == "peripheral" and item.kind == "base_address":
            old = periph.base_address
            new = item.suggested.get("base_address", old)
            if old == new:
                return None
            def _undo():
                periph.base_address = old
            periph.base_address = new
            return _undo

        reg_name = item.register
        if not reg_name:
            return None

        # 寄存器级缺失 → 新增寄存器
        if item.kind == "reg_missing_in_svd":
            if reg_name in periph.registers:
                return None
            s = item.suggested
            new_r = Register(
                name=s.get("name", reg_name),
                offset=s.get("offset", "0x0"),
                reset_value=s.get("reset_value", "0x00000000"),
                description=s.get("description", ""),
            )
            def _undo():
                periph.registers.pop(reg_name, None)
            periph.registers[reg_name] = new_r
            return _undo

        reg = periph.registers.get(reg_name)
        if reg is None:
            return None

        # 寄存器属性不符
        if item.level == "register":
            attr_map = {"offset": "offset", "reset_value": "reset_value"}
            attr = attr_map.get(item.kind)
            if attr is None:
                return None
            old = getattr(reg, attr)
            new = item.suggested.get(attr, old)
            if old == new:
                return None
            def _undo():
                setattr(reg, attr, old)
            setattr(reg, attr, new)
            return _undo

        # 位域级
        field_name = item.field
        if item.kind == "field_missing_in_svd":
            if field_name in reg.fields:
                return None
            s = item.suggested
            new_f = Field(
                name=s.get("name", field_name),
                bit_offset=int(s.get("bit_offset", 0)),
                bit_width=int(s.get("bit_width", 1)),
                description=s.get("description", ""),
            )
            def _undo():
                reg.fields.pop(field_name, None)
            reg.fields[field_name] = new_f
            return _undo

        fld = reg.fields.get(field_name) if field_name else None
        if fld is None:
            return None

        # 位域属性不符
        attr_map = {"width": "bit_width", "access": "access"}
        attr = attr_map.get(item.kind)
        if attr is None:
            return None
        old = getattr(fld, attr)
        try:
            new = int(item.suggested.get(attr, old)) if attr == "bit_width" else item.suggested.get(attr, old)
        except (TypeError, ValueError):
            return None
        if old == new:
            return None

        def _undo():
            setattr(fld, attr, old)
        setattr(fld, attr, new)
        return _undo

    # ════════════════════════════════════════════════════
    # 撤销栈 / 刷新（复用 CommandExecutor 同款机制，避免环依赖）
    # ════════════════════════════════════════════════════

    def _execute_undoable(self, description: str, execute_fn, undo_fn):
        state_manager = self.coordinator.get_component("state_manager")
        if state_manager and getattr(state_manager, "command_history", None):
            cmd = Command(execute=execute_fn, undo=undo_fn, description=description)
            state_manager.command_history.execute(cmd)
        else:
            execute_fn()

    def _notify_refresh(self):
        state_manager = self.coordinator.get_component("state_manager")
        if state_manager and hasattr(state_manager, "_notify_state_change"):
            state_manager._notify_state_change()
        if self.coordinator and hasattr(self.coordinator, "notify_peripheral_updated"):
            self.coordinator.notify_peripheral_updated(None)
        layout_manager = self.coordinator.get_component("layout_manager") if self.coordinator else None
        if layout_manager and hasattr(layout_manager, "update_basic_info") and state_manager:
            try:
                layout_manager.update_basic_info(state_manager.device_info)
            except Exception:
                logger.debug("update_basic_info 失败（可忽略）", exc_info=True)

    def _mark_modified(self):
        dm = self.main_window.document_manager if self.main_window else None
        if dm:
            dm.mark_modified()


def _shallow_copy_dict(d: dict) -> dict:
    """浅拷贝 dict（保留 value 引用，但 dict 容器独立，便于撤销时整体替换）。"""
    return dict(d)
