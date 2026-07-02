"""
命令执行器
将 AI 返回的操作指令翻译为对 DeviceInfo 的直接操作
所有修改操作通过 CommandHistory 支持撤销
"""
import logging
import re
import threading
from typing import Dict, Any, Optional, Callable

from ..i18n.i18n import t

logger = logging.getLogger("svd_tool.ai_assistant.CommandExecutor")


class _GuiBridge:
    """跨线程 GUI 派发桥。

    CommandExecutor 在 AgentLoop 工作线程中被调用，但写操作（增删改）和涉及
    选中/刷新的操作会修改主线程持有的共享状态（device_info、当前选中项、视图）。
    若工作线程与主线程的手动操作交错，会产生竞态：表现为"出现两个外设"、
    "显示还是旧的"、选中错乱甚至闪退。

    本桥用 QObject 信号把可调用对象派发到主线程执行：
    - call_blocking(fn): 工作线程用 threading.Event 阻塞等待，直到 fn 在主线程
      执行完毕，返回其返回值或重新抛出其异常。注意：不使用 BlockingQueuedConnection
      （它会在"主线程执行期间又需要工作线程响应"时触发 Qt 死锁检测，
      报 "Dead lock detected while activating a BlockingQueuedConnection"），
      改用 QueuedConnection + Event 等待，规避该陷阱。
    - post(fn): 不等待，用于通知类操作（如刷新）。
    """

    def __init__(self):
        from PyQt6.QtCore import QObject, pyqtSignal, Qt

        class _Carrier(QObject):
            # 单一通道：携带 (callable, 结果盒)。连接类型在 emit 时按线程决定。
            run = pyqtSignal(object, object)

        self._carrier = _Carrier()
        # 用 QueuedConnection（跨线程时排队到主线程事件循环，不阻塞 emit 方）
        self._carrier.run.connect(
            self._on_run, Qt.ConnectionType.QueuedConnection)

    def _on_run(self, fn, result_box):
        """在主线程执行（由信号触发）。"""
        try:
            value = fn()
            if result_box is not None:
                result_box['value'] = value
                result_box['error'] = None
        except Exception as e:
            if result_box is not None:
                result_box['error'] = e
        finally:
            if result_box is not None and result_box.get('event') is not None:
                result_box['event'].set()

    def call_blocking(self, fn: Callable) -> Any:
        """把 fn 派发到主线程执行，阻塞等待结果（或重新抛出其异常）。

        工作线程用 threading.Event 等待主线程执行完毕（而非 BlockingQueuedConnection，
        后者在嵌套场景会触发 Qt 死锁检测）。

        关键：若当前已在主线程（如 execute() 已把操作派发到主线程，操作内部又
        调 call_blocking，如保存时的 _confirm_overwrite），则直接同步执行 fn。
        否则 QueuedConnection 会把 fn 排到主线程事件队列，但主线程此刻正执行
        外层 fn（事件循环没跑），fn 永远得不到执行 → Event 永不 set → 死锁。
        """
        if threading.current_thread() is threading.main_thread():
            return fn()

        result_box = {'value': None, 'error': None, 'event': threading.Event()}
        self._carrier.run.emit(fn, result_box)
        # QueuedConnection 下 emit 立即返回；用 Event 阻塞等待主线程执行完。
        # 关键：等待时长必须足够覆盖用户交互（如保存前的覆盖确认弹窗），
        # 用户犹豫时间不应让任务失败。用较长上限 + 显式超时检测，绝不能
        # 静默返回初始值 None（会导致 emit(name, None) 报参数类型错）。
        done = result_box['event'].wait(timeout=300)
        if result_box['error'] is not None:
            raise result_box['error']
        if not done:
            # 主线程长时间无响应（卡死/事件循环阻塞），明确报错而非返回 None
            raise TimeoutError("主线程响应超时，GUI 操作未能完成（可能主线程卡死）")
        return result_box['value']

    def post(self, fn: Callable) -> None:
        """把 fn 派发到主线程执行，不等待（用于刷新等通知）。"""
        if threading.current_thread() is threading.main_thread():
            fn()
            return
        self._carrier.run.emit(fn, None)


class CommandExecutor:
    """AI 操作执行器"""

    # 这些操作只读不改共享状态，可在工作线程直接跑（省一次线程切换）。
    # 其余操作（写操作、改选中、刷新）一律派发到主线程，与手动操作串行化。
    _READONLY_OPS = frozenset({
        "validate", "info", "search", "conflicts",
        "get_peripheral", "get_register", "get_field", "list_interrupts",
        "list_directory", "find_duplicate_svds", "diff_peripheral",
    })

    def __init__(self, coordinator, main_window=None):
        """
        Args:
            coordinator: 中央协调器，用于访问 StateManager 等
            main_window: 主窗口引用，用于访问 DocumentManager 等
        """
        self.coordinator = coordinator
        self.main_window = main_window
        # 跨线程 GUI 桥（在主线程构造，affinity 正确）
        self._gui = _GuiBridge()
        # 静默模式：开启后写操作只改数据模型、立即放行工作线程，
        # UI 刷新推迟到 flush_pending_updates() 统一执行。
        self._silent = False
        self._dirty = False  # 静默期间是否有待刷新的 UI 变更
        self._operation_map = {
            "validate": self._op_validate,
            "info": self._op_info,
            "search": self._op_search,
            "conflicts": self._op_conflicts,
            # 文件系统只读工具（批量任务用，不依赖当前 device_info）
            "list_directory": self._op_list_directory,
            "find_duplicate_svds": self._op_find_duplicate_svds,
            "diff": self._op_diff,
            "diff_peripheral": self._op_diff_peripheral,
            "jump": self._op_jump,
            # 片段查询工具（function-calling 专用，按需取 SVD 片段）
            "get_peripheral": self._op_get_peripheral,
            "get_register": self._op_get_register,
            "get_field": self._op_get_field,
            "list_interrupts": self._op_list_interrupts,
            "update_device": self._op_update_device,
            "add_peripheral": self._op_add_peripheral,
            "update_peripheral": self._op_update_peripheral,
            "remove_peripheral": self._op_remove_peripheral,
            "add_register": self._op_add_register,
            "update_register": self._op_update_register,
            "remove_register": self._op_remove_register,
            "add_field": self._op_add_field,
            "update_field": self._op_update_field,
            "remove_field": self._op_remove_field,
            # 中断操作（增删改复用 state_manager，保证外设 interrupts 列表双向同步 + 撤销）
            "add_interrupt": self._op_add_interrupt,
            "update_interrupt": self._op_update_interrupt,
            "remove_interrupt": self._op_remove_interrupt,
            # 多文档操作
            "open_document": self._op_open_document,
            "switch_document": self._op_switch_document,
            "save_document": self._op_save_document,
            "batch_save": self._op_batch_save,
        }

    def execute(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """执行一个操作

        Args:
            action: {"operation": "操作名", "params": {...}}

        Returns:
            {"success": bool, "message": str, "data": any}

        线程安全：只读操作（见 _READONLY_OPS）直接在当前线程执行；其余操作
        若从工作线程调用，整体派发到主线程执行（BlockingQueuedConnection 阻塞等待），
        与用户的手动操作串行化，避免竞态（"出现两个外设"/选中错乱/闪退）。
        """
        operation = action.get("operation", "")
        params = action.get("params", {})

        handler = self._operation_map.get(operation)
        if not handler:
            return {
                "success": False,
                "message": t("ai.unknown_op", op=operation),
                "data": None
            }

        def _run() -> Dict[str, Any]:
            try:
                return handler(params)
            except Exception as e:
                logger.error(f"执行操作 {operation} 失败: {e}", exc_info=True)
                return {
                    "success": False,
                    "message": t("ai.op_failed", error=str(e)),
                    "data": None,
                }

        # 只读操作直接跑；若已在主线程（非 AgentLoop 调用），也直接跑避免阻塞自身
        if operation in self._READONLY_OPS or threading.current_thread() is threading.main_thread():
            return _run()

        # 写/GUI 操作：派发到主线程，阻塞等待结果（与手动操作串行化）
        try:
            return self._gui.call_blocking(_run)
        except Exception as e:
            # call_blocking 内部异常（如主线程无响应）兜底
            logger.error(f"派发操作 {operation} 到主线程失败: {e}", exc_info=True)
            return {
                "success": False,
                "message": t("ai.op_failed", error=str(e)),
                "data": None,
            }

    def _get_device_info(self):
        """获取当前 DeviceInfo"""
        state_manager = self.coordinator.get_component("state_manager")
        if state_manager:
            return state_manager.device_info
        return None

    def _execute_undoable(self, description: str, execute_fn, undo_fn):
        """执行可撤销的操作

        Args:
            description: 操作描述
            execute_fn: 执行函数
            undo_fn: 撤销函数
        """
        from svd_tool.core.command_history import Command

        state_manager = self.coordinator.get_component("state_manager")
        if state_manager and state_manager.command_history:
            cmd = Command(execute=execute_fn, undo=undo_fn, description=description)
            state_manager.command_history.execute(cmd)
        else:
            execute_fn()

        # 关键：标记当前文档已修改。DocumentManager 的多文档隔离依赖 modified 标志
        # 决定切换时是否深拷贝（_save_current_document_state）。若不标记，AI 改过的
        # 文档会被当作"未修改"走浅引用，导致切换后多个文档共享同一 device_info
        # 引用，表现为"后开的文档覆盖先开的"。
        self._mark_modified()

    def _notify_refresh(self, peripheral_name: Optional[str] = None):
        """通知 UI 刷新。

        CommandExecutor 的写操作现在已在主线程执行（见 execute()），故本方法
        实际也在主线程被调用。但保留通过 _gui 派发的兜底，确保即使将来从其它
        线程调用也能安全地切到主线程操作 GUI（state_manager 的 QTimer、树视图等）。
        旧实现用 QTimer.singleShot 在工作线程不可靠（无事件循环），已弃用。

        静默模式下：不立即刷新，只标记 _dirty，由 flush_pending_updates() 统一刷。
        这样工作线程在 call_blocking 中等到的"主线程写操作"不含重刷新，立即放行。
        """
        # 静默模式：仅标记待刷新，不执行（写操作本身已在主线程完成数据修改）
        if getattr(self, "_silent", False):
            self._dirty = True
            return

        def _do_refresh():
            try:
                state_manager = self.coordinator.get_component("state_manager")
                if state_manager:
                    state_manager._notify_state_change()

                if peripheral_name:
                    self.coordinator.notify_peripheral_updated(peripheral_name)

                # 刷新基本信息页面
                layout_manager = self.coordinator.get_component("layout_manager")
                if layout_manager and hasattr(layout_manager, 'update_basic_info') and state_manager:
                    try:
                        layout_manager.update_basic_info(state_manager.device_info)
                    except Exception:
                        pass
            except Exception:
                logger.debug("UI 刷新失败（可忽略）", exc_info=True)

        if threading.current_thread() is threading.main_thread():
            _do_refresh()
        else:
            self._gui.post(_do_refresh)

    def _notify_interrupt_updated(self) -> None:
        """通知中断列表已变更，触发中断表自动重建。
        通过 coordinator.interrupt_updated 信号派发（main_window 订阅后重建表格）。
        工作线程派发到主线程发信号，避免跨线程 emit 的隐患。

        静默模式下推迟到 flush。
        """
        if getattr(self, "_silent", False):
            self._dirty = True
            return

        def _do_notify():
            try:
                self.coordinator.notify_interrupt_updated()
            except Exception:
                logger.debug("中断变更通知失败（可忽略）", exc_info=True)

        if threading.current_thread() is threading.main_thread():
            _do_notify()
        else:
            self._gui.post(_do_notify)

    def set_silent_mode(self, enabled: bool) -> None:
        """开启/关闭静默模式。由 controller 在启动每个 agent loop 前根据配置设置。"""
        self._silent = bool(enabled)
        # 切换模式时复位待刷新标记（新一轮任务从干净状态开始）
        self._dirty = False

    def flush_pending_updates(self) -> None:
        """静默模式任务结束时调用：把积累的待刷新 UI 变更一次性刷出。

        用 _gui.post（非阻塞）派发，主线程异步执行完整刷新，工作线程/调用方不等。
        若 _dirty 为 False 则什么都不做。
        """
        if not getattr(self, "_silent", False) and not self._dirty:
            return
        if not self._dirty:
            return

        self._dirty = False  # 已安排刷新，清标记

        def _do_flush():
            try:
                state_manager = self.coordinator.get_component("state_manager")
                if state_manager:
                    state_manager._notify_state_change()
                # 中断表重建
                try:
                    self.coordinator.notify_interrupt_updated()
                except Exception:
                    pass
                # 基本信息页
                layout_manager = self.coordinator.get_component("layout_manager")
                if layout_manager and hasattr(layout_manager, 'update_basic_info') and state_manager:
                    try:
                        layout_manager.update_basic_info(state_manager.device_info)
                    except Exception:
                        pass
            except Exception:
                logger.debug("flush 刷新失败（可忽略）", exc_info=True)

        if threading.current_thread() is threading.main_thread():
            _do_flush()
        else:
            self._gui.post(_do_flush)

    def _mark_modified(self) -> None:
        """标记当前文档已修改（见 _execute_undoable 的说明，用于多文档隔离）。"""
        dm = self.main_window.document_manager if self.main_window else None
        if dm:
            dm.mark_modified()

    def begin_batch(self) -> None:
        """开始批量操作：暂停状态变更通知，避免中间状态触发级联刷新
        （全树重建 / 地址冲突全量扫描 / 预览重生成 ×N 次）。

        必须与 end_batch() 配对使用。批量结束后由 end_batch() 恢复通知并触发
        一次合并刷新。在工作线程调用时通过 _gui 派发到主线程（pause/resume
        操作 state_manager 的 QTimer，必须在主线程）。
        """
        def _do():
            state_manager = self.coordinator.get_component("state_manager")
            if state_manager and hasattr(state_manager, "pause_notifications"):
                state_manager.pause_notifications()
        if threading.current_thread() is threading.main_thread():
            _do()
        else:
            self._gui.call_blocking(_do)

    def end_batch(self) -> None:
        """结束批量操作：恢复状态变更通知，触发一次合并刷新。

        resume_notifications 内部会立即通知一次（不带防抖），确保批量修改后的
        树/预览/冲突检测基于最终状态刷新，而非中间状态。
        """
        def _do():
            state_manager = self.coordinator.get_component("state_manager")
            if state_manager and hasattr(state_manager, "resume_notifications"):
                state_manager.resume_notifications()
        if threading.current_thread() is threading.main_thread():
            _do()
        else:
            self._gui.call_blocking(_do)

    # ==================== 只读操作 ====================

    def _op_validate(self, params: Dict) -> Dict[str, Any]:
        """验证 SVD 数据"""
        device = self._get_device_info()
        if not device or not device.name:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        try:
            from svd_tool.core.svd_schema_validator import SVDSchemaValidator
            validator = SVDSchemaValidator()
            results = validator.validate_all(device)
            summary = validator.get_summary()

            msg = t("ai.validate_done", errors=summary.get('errors', 0), warnings=summary.get('warnings', 0))
            return {"success": not summary.get("has_errors", True), "message": msg, "data": summary}
        except Exception as e:
            return {"success": False, "message": t("ai.validate_fail", error=str(e)), "data": None}

    def _op_info(self, params: Dict) -> Dict[str, Any]:
        """获取设备信息统计"""
        device = self._get_device_info()
        if not device or not device.name:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        info = {
            "device": device.name,
            "version": device.version,
            "vendor": device.vendor or t("ai.info_vendor"),
            "cpu": device.cpu.name,
            "size": device.size,
            "statistics": {
                "peripherals": len(device.peripherals),
                "registers": sum(len(p.registers) for p in device.peripherals.values()),
                "fields": sum(
                    len(r.fields)
                    for p in device.peripherals.values()
                    for r in p.registers.values()
                ),
                "interrupts": len(device.interrupts),
            },
            "peripheral_names": [
                f"{name} (derivedFrom={p.derived_from})" if p.derived_from else name
                for name, p in device.peripherals.items()
            ],
        }
        msg = t("ai.info_msg",
                name=device.name,
                periphs=info['statistics']['peripherals'],
                regs=info['statistics']['registers'],
                fields=info['statistics']['fields'],
                irqs=info['statistics']['interrupts'])
        return {"success": True, "message": msg, "data": info}

    def _op_search(self, params: Dict) -> Dict[str, Any]:
        """搜索外设/寄存器/位域（支持分页，避免大文件返回上千条）"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        keyword = params.get("keyword", "").lower()
        search_type = params.get("type", "all")
        if not keyword:
            return {"success": False, "message": t("ai.search_keyword_empty"), "data": None}

        # 分页参数：默认上限 50 条，防止巨型 SVD 单次返回过多
        try:
            limit = int(params.get("limit", 50))
        except (TypeError, ValueError):
            limit = 50
        try:
            offset = int(params.get("offset", 0))
        except (TypeError, ValueError):
            offset = 0
        limit = max(1, min(limit, 200))
        offset = max(0, offset)

        all_results = []

        if search_type in ("all", "peripheral"):
            for name, periph in device.peripherals.items():
                if keyword in name.lower():
                    entry = {"type": "peripheral", "name": name}
                    if periph.derived_from:
                        entry["derived_from"] = periph.derived_from
                    all_results.append(entry)

        if search_type in ("all", "register"):
            for pname, periph in device.peripherals.items():
                for rname in periph.registers:
                    if keyword in rname.lower():
                        all_results.append({"type": "register", "name": rname, "peripheral": pname})

        if search_type in ("all", "field"):
            for pname, periph in device.peripherals.items():
                for rname, reg in periph.registers.items():
                    for fname in reg.fields:
                        if keyword in fname.lower():
                            all_results.append({"type": "field", "name": fname, "peripheral": pname, "register": rname})

        total = len(all_results)
        page = all_results[offset:offset + limit]
        msg = t("ai.search_result", keyword=keyword, count=total)
        return {
            "success": True,
            "message": msg,
            "data": {
                "results": page,
                "total": total,
                "offset": offset,
                "limit": limit,
                "has_more": offset + limit < total,
            },
        }

    def _op_conflicts(self, params: Dict) -> Dict[str, Any]:
        """检测地址冲突"""
        device = self._get_device_info()
        if not device or not device.name:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        try:
            from svd_tool.core.address_conflict_detector import AddressConflictDetector
            detector = AddressConflictDetector()
            conflicts = detector.detect_all(device)

            if not conflicts:
                return {"success": True, "message": t("ai.conflicts_none"), "data": {"conflicts": [], "total": 0}}

            conflict_list = []
            for c in conflicts[:20]:
                conflict_list.append({
                    "type": str(c.conflict_type) if hasattr(c, 'conflict_type') else "unknown",
                    "severity": str(c.severity) if hasattr(c, 'severity') else "unknown",
                    "message": c.message if hasattr(c, 'message') else str(c),
                })

            msg = t("ai.conflicts_found", count=len(conflicts))
            return {
                "success": True,
                "message": msg,
                "data": {"conflicts": conflict_list, "total": len(conflicts), "shown": len(conflict_list)},
            }
        except Exception as e:
            return {"success": False, "message": t("ai.conflicts_fail", error=str(e)), "data": None}

    def _parse_external_device(self, file_path: str):
        """解析外部 SVD 文件为 DeviceInfo，带 (path, mtime) 缓存。

        静默/批量任务中 AI 可能反复对同一文件做对比，重复解析浪费；缓存按文件
        mtime 失效（文件改动则重新解析）。仅缓存纯数据 DeviceInfo，不缓存 Qt 对象。
        """
        import os
        if not hasattr(self, "_ext_parse_cache"):
            self._ext_parse_cache = {}  # {file_path: (mtime, device_info)}
        try:
            mtime = os.path.getmtime(file_path)
        except OSError:
            mtime = None
        cached = self._ext_parse_cache.get(file_path)
        if cached and cached[0] == mtime:
            return cached[1]
        from svd_tool.core.svd_parser import SVDParser
        device_info = SVDParser().parse_file(file_path)
        self._ext_parse_cache[file_path] = (mtime, device_info)
        # 限制缓存大小，避免长时间运行无限增长
        if len(self._ext_parse_cache) > 16:
            # 丢掉最旧的一半（dict 保持插入顺序）
            keep = list(self._ext_parse_cache.items())[-8:]
            self._ext_parse_cache = dict(keep)
        return device_info

    def _op_diff(self, params: Dict) -> Dict[str, Any]:
        """比较当前 SVD 与另一个文件或已打开的文档"""
        device = self._get_device_info()
        if not device or not device.name:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        other_device = None
        other_name = ""

        # 优先尝试从已打开的文档中获取
        compare_with = params.get("compare_with", "").strip()
        if compare_with or (not params.get("file_path") and not params.get("file")):
            other_device, other_name = self._resolve_other_device(compare_with)
            if other_device is None:
                # 返回错误，附带可用文档列表
                open_docs = self._get_open_documents_info()
                if not open_docs:
                    return {"success": False, "message": t("ai.diff_only_one"), "data": None}
                return {
                    "success": False,
                    "message": t("ai.diff_not_found", docs=', '.join(open_docs)),
                    "data": {"open_documents": open_docs}
                }

        # 如果未从打开的文档获取到，则尝试文件路径
        if other_device is None:
            file_path = params.get("file_path", "") or params.get("file", "")
            if isinstance(file_path, str):
                file_path = file_path.strip()
            if not file_path:
                # 没有提供路径，也没有其他打开的文档
                return {"success": False, "message": t("ai.diff_no_path"), "data": None}

            import os
            if not os.path.isfile(file_path):
                return {"success": False, "message": t("ai.diff_file_not_found", path=file_path), "data": None}

            try:
                other_device = self._parse_external_device(file_path)
                other_name = os.path.basename(file_path)
            except Exception as e:
                return {"success": False, "message": t("ai.diff_parse_fail", error=str(e)), "data": None}

        try:
            from svd_tool.core.svd_differ import SVDDiffer

            differ = SVDDiffer()
            diffs = differ.diff(device, other_device)

            if not diffs:
                return {"success": True, "message": t("ai.diff_identical", a=device.name, b=other_name), "data": []}

            summary = differ.generate_summary(diffs)
            diff_list = []
            total_changes = 0
            for d in diffs:
                count = d.count_changes
                total_changes += count
                diff_list.append({
                    "path": d.path,
                    "type": d.diff_type.name,
                    "changes": count,
                })

            result = {
                "success": True,
                "message": t("ai.diff_result", a=device.name, b=other_name, changes=total_changes, periphs=len(diffs)),
                "data": {
                    "source": device.name,
                    "target": other_name,
                    "total_changes": total_changes,
                    "peripheral_diffs": diff_list[:20],
                    "summary": summary[:2000] if summary else "",
                }
            }

            # 弹出可视化 diff 对话框让用户查看。
            # 静默模式下不弹框（AI 场景只需文本结果，减少打断）；用户仍可手动 Ctrl+D 弹框。
            if self.main_window and not getattr(self, "_silent", False):
                from PyQt6.QtCore import QTimer
                dm = self.main_window.document_manager if hasattr(self.main_window, 'document_manager') else None
                QTimer.singleShot(100, lambda: self._show_diff_dialog(device, other_device, dm))

            return result
        except Exception as e:
            return {"success": False, "message": t("ai.diff_fail", error=str(e)), "data": None}

    def _op_diff_peripheral(self, params: Dict) -> Dict[str, Any]:
        """比较单个外设在当前 SVD 与另一个文件/文档之间的差异。

        细分需求：不必整文件对比，只关注某个外设（寄存器/位域增删改）。
        不弹可视化对话框（AI 场景只需文本结果）。
        """
        device = self._get_device_info()
        if not device or not device.name:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        peripheral = params.get("peripheral", "").strip()
        if not peripheral:
            return {"success": False,
                    "message": t("ai.diff_periph_no_name", default="未指定要对比的外设名"), "data": None}

        # 解析另一侧（复用 _op_diff 的文档/文件解析逻辑）
        other_device = None
        other_name = ""
        compare_with = params.get("compare_with", "").strip()
        if compare_with or (not params.get("file_path") and not params.get("file")):
            other_device, other_name = self._resolve_other_device(compare_with)
            if other_device is None:
                open_docs = self._get_open_documents_info()
                if not open_docs:
                    return {"success": False, "message": t("ai.diff_only_one"), "data": None}
                return {"success": False, "message": t("ai.diff_not_found", docs=', '.join(open_docs)),
                        "data": {"open_documents": open_docs}}

        if other_device is None:
            file_path = params.get("file_path", "") or params.get("file", "")
            if isinstance(file_path, str):
                file_path = file_path.strip()
            if not file_path:
                return {"success": False, "message": t("ai.diff_no_path"), "data": None}
            import os
            if not os.path.isfile(file_path):
                return {"success": False, "message": t("ai.diff_file_not_found", path=file_path), "data": None}
            try:
                other_device = self._parse_external_device(file_path)
                other_name = os.path.basename(file_path)
            except Exception as e:
                return {"success": False, "message": t("ai.diff_parse_fail", error=str(e)), "data": None}

        try:
            from svd_tool.core.svd_differ import SVDDiffer
            differ = SVDDiffer()
            diffs = differ.diff_peripheral(device, other_device, peripheral)

            if not diffs:
                return {"success": True,
                        "message": t("ai.diff_periph_identical", name=peripheral, a=device.name, b=other_name,
                                     default="外设 '{name}' 在 {a} 与 {b} 中完全一致"),
                        "data": {"peripheral": peripheral, "total_changes": 0, "diffs": []}}

            summary = differ.generate_summary(diffs)
            diff_list = []
            total_changes = 0
            for d in diffs:
                count = d.count_changes
                total_changes += count
                diff_list.append({"path": d.path, "type": d.diff_type.name, "changes": count})

            return {"success": True,
                    "message": t("ai.diff_periph_result", name=peripheral, a=device.name, b=other_name,
                                 changes=total_changes,
                                 default="外设 '{name}' 对比 {a} vs {b}: {changes} 处差异"),
                    "data": {"peripheral": peripheral, "source": device.name, "target": other_name,
                             "total_changes": total_changes, "diffs": diff_list,
                             "summary": summary[:2000] if summary else ""}}
        except Exception as e:
            return {"success": False, "message": t("ai.diff_fail", error=str(e)), "data": None}

    def _show_diff_dialog(self, current_device, other_device, document_manager):
        """弹出 SVD 差异比较对话框让用户可视化查看差异"""
        try:
            from svd_tool.ui.dialogs.svd_diff_dialog import SVDDiffDialog
            from PyQt6.QtCore import Qt

            dialog = SVDDiffDialog(
                self.main_window, current_device,
                document_manager=document_manager
            )
            dialog.set_other_device(other_device)
            dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowType.WindowMinMaxButtonsHint)
            dialog.show()
            # 自动触发比较
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(200, dialog._do_compare)
        except Exception as e:
            logger.warning(f"弹出 diff 对话框失败: {e}")

    def _get_open_documents_info(self) -> list:
        """获取所有已打开文档的显示名称列表"""
        if not self.main_window or not hasattr(self.main_window, 'document_manager'):
            return []
        dm = self.main_window.document_manager
        return [doc.display_name for doc in dm.get_all_documents().values()]

    def _resolve_other_device(self, name_hint: str = ""):
        """从已打开的文档中找到另一个设备

        Args:
            name_hint: 可选的文档名称提示（支持模糊匹配）

        Returns:
            (device_info, display_name) 或 (None, "")
        """
        if not self.main_window or not hasattr(self.main_window, 'document_manager'):
            return None, ""

        dm = self.main_window.document_manager
        active_id = dm.active_doc_id
        all_docs = dm.get_all_documents()

        other_docs = {did: doc for did, doc in all_docs.items() if did != active_id}

        if not other_docs:
            return None, ""

        if not name_hint:
            # 没有指定名称，取第一个其他文档
            doc = list(other_docs.values())[0]
            return doc.device_info, doc.display_name

        # 模糊匹配名称
        name_lower = name_hint.lower()
        for doc in other_docs.values():
            if name_lower in doc.display_name.lower() or name_lower in (doc.device_info.name or "").lower():
                return doc.device_info, doc.display_name

        return None, ""

    def _op_jump(self, params: Dict) -> Dict[str, Any]:
        """跳转到指定外设/寄存器/位域"""
        peripheral = params.get("peripheral", "").strip()
        register = params.get("register", "").strip()
        field = params.get("field", "").strip()

        if not peripheral:
            return {"success": False, "message": t("ai.jump_hint"), "data": None}

        device = self._get_device_info()
        if not device:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        if peripheral not in device.peripherals:
            return {"success": False, "message": t("ai.periph_not_found", name=peripheral), "data": None}

        # 切换到外设标签页
        layout_manager = self.coordinator.get_component("layout_manager")
        if layout_manager:
            tab_widget = layout_manager.widget_manager.get_widget("tab_widget")
            if tab_widget:
                # 外设标签页固定在 index=1
                if tab_widget.count() > 1:
                    tab_widget.setCurrentIndex(1)

        # 使用 PeripheralManager 的选择方法
        periph_manager = self.coordinator.get_component("peripheral_manager")
        if not periph_manager:
            return {"success": False, "message": t("ai.periph_mgr_unavailable"), "data": None}

        target_desc = peripheral
        try:
            if field and register:
                periph_manager.select_field(peripheral, register, field)
                target_desc = f"{peripheral} > {register} > {field}"
            elif register:
                periph_manager.select_register(peripheral, register)
                target_desc = f"{peripheral} > {register}"
            else:
                periph_manager.select_peripheral(peripheral)
                target_desc = peripheral
        except Exception as e:
            return {"success": False, "message": t("ai.jump_fail", error=str(e)), "data": None}

        # 验证选中是否真正生效（树模型可能因数据脱节而静默失败）
        try:
            cur_sel = self.coordinator.get_component("state_manager")
            if cur_sel and hasattr(cur_sel, "current_selection"):
                sel = cur_sel.current_selection or {}
                actual_p = sel.get("peripheral", "")
                if actual_p and actual_p != peripheral:
                    return {"success": False,
                            "message": t("ai.jump_mismatch", target=peripheral, actual=actual_p,
                                         default="跳转未生效：目标 {target}，实际选中 {actual}"),
                            "data": None}
        except Exception:
            pass

        return {"success": True, "message": t("ai.jump_done", target=target_desc), "data": {
            "peripheral": peripheral,
            "register": register or None,
            "field": field or None,
        }}

    # ==================== 片段查询工具（function-calling 专用） ====================
    # 以下工具用于让 AI 按需取 SVD 片段，替代旧的"全文塞 system prompt"。
    # 设计原则：分层下发——get_peripheral 不含位域、get_register 不含 enumerated_values，
    # get_field 才返回完整位域（含枚举值）。避免单次返回过大。

    def _op_get_peripheral(self, params: Dict) -> Dict[str, Any]:
        """获取指定外设的元信息及寄存器列表（不含位域细节）。

        合并 clusters 内的寄存器（用 all_registers），并在每条标注 cluster 来源。
        """
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        name = params.get("name", "").strip()
        if name not in device.peripherals:
            return {"success": False, "message": t("ai.periph_not_found", name=name), "data": None}

        periph = device.peripherals[name]
        # all_registers 合并 clusters；同时记录每个寄存器是否来自 cluster
        reg_list = []
        for rname, reg in periph.registers.items():
            reg_list.append({
                "name": rname,
                "offset": reg.offset,
                "size": reg.size,
                "access": reg.access or "",
                "reset_value": reg.reset_value,
                "description": reg.description,
                "from_cluster": "",
            })
        for cname, cluster in periph.clusters.items():
            for rname, reg in cluster.all_registers().items():
                reg_list.append({
                    "name": rname,
                    "offset": reg.offset,
                    "size": reg.size,
                    "access": reg.access or "",
                    "reset_value": reg.reset_value,
                    "description": reg.description,
                    "from_cluster": cname,
                })

        data = {
            "name": periph.name,
            "base_address": periph.base_address,
            "description": periph.description,
            "group_name": periph.group_name,
            "derived_from": periph.derived_from or "",
            "register_count": len(reg_list),
            "registers": reg_list,
        }
        return {"success": True, "message": t("ai.get_periph_done", name=name, count=len(reg_list)), "data": data}

    def _op_get_register(self, params: Dict) -> Dict[str, Any]:
        """获取指定寄存器的元信息及位域列表（不含 enumerated_values）。"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        periph_name = params.get("peripheral", "").strip()
        reg_name = params.get("register", "").strip() or params.get("name", "").strip()
        if periph_name not in device.peripherals:
            return {"success": False, "message": t("ai.periph_not_found", name=periph_name), "data": None}

        periph = device.peripherals[periph_name]
        # 优先顶层 registers，找不到再查 clusters
        reg = periph.registers.get(reg_name)
        cluster_source = ""
        if reg is None:
            for cname, cluster in periph.clusters.items():
                regs = cluster.all_registers()
                if reg_name in regs:
                    reg = regs[reg_name]
                    cluster_source = cname
                    break
        if reg is None:
            return {"success": False, "message": t("ai.reg_not_found", name=reg_name), "data": None}

        field_list = []
        for fname, fld in reg.fields.items():
            field_list.append({
                "name": fname,
                "bit_offset": fld.bit_offset,
                "bit_width": fld.bit_width,
                "access": fld.access or "",
                "reset_value": fld.reset_value,
                "description": fld.description,
            })

        data = {
            "peripheral": periph_name,
            "name": reg.name,
            "offset": reg.offset,
            "size": reg.size,
            "access": reg.access or "",
            "reset_value": reg.reset_value,
            "reset_mask": getattr(reg, "reset_mask", ""),
            "description": reg.description,
            "derived_from": getattr(reg, "derived_from", "") or "",
            "from_cluster": cluster_source,
            "field_count": len(field_list),
            "fields": field_list,
        }
        return {"success": True, "message": t("ai.get_reg_done", periph=periph_name, name=reg_name, count=len(field_list)), "data": data}

    def _op_get_field(self, params: Dict) -> Dict[str, Any]:
        """获取单个位域的完整信息（含 enumerated_values）。"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        periph_name = params.get("peripheral", "").strip()
        reg_name = params.get("register", "").strip()
        field_name = params.get("field", "").strip() or params.get("name", "").strip()
        if periph_name not in device.peripherals:
            return {"success": False, "message": t("ai.periph_not_found", name=periph_name), "data": None}

        periph = device.peripherals[periph_name]
        reg = periph.registers.get(reg_name)
        if reg is None:
            for cluster in periph.clusters.values():
                regs = cluster.all_registers()
                if reg_name in regs:
                    reg = regs[reg_name]
                    break
        if reg is None:
            return {"success": False, "message": t("ai.reg_not_found", name=reg_name), "data": None}
        if field_name not in reg.fields:
            return {"success": False, "message": t("ai.field_not_found", name=field_name), "data": None}

        fld = reg.fields[field_name]
        data = {
            "peripheral": periph_name,
            "register": reg_name,
            "name": fld.name,
            "bit_offset": fld.bit_offset,
            "bit_width": fld.bit_width,
            "access": fld.access or "",
            "reset_value": fld.reset_value,
            "description": fld.description,
            "display_name": getattr(fld, "display_name", ""),
            "enumerated_values": getattr(fld, "enumerated_values", []),
        }
        return {"success": True, "message": t("ai.get_field_done", name=field_name), "data": data}

    def _op_list_interrupts(self, params: Dict) -> Dict[str, Any]:
        """列出设备的中断（名称/值/描述/关联外设）。"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        irq_list = []
        for name, irq in device.interrupts.items():
            irq_list.append({
                "name": name,
                "value": irq.value,
                "description": irq.description,
                "peripheral": irq.peripheral,
                "peripherals": irq.peripherals,
            })
        data = {"total": len(irq_list), "interrupts": irq_list}
        return {"success": True, "message": t("ai.list_irq_done", count=len(irq_list)), "data": data}

    # ==================== 文件系统只读工具（批量任务用） ====================
    # 以下工具让 AI 能扫描文件夹、对比文件，用于批量生成后的查重。
    # 不依赖当前 device_info，可安全在工作线程执行（已在 _READONLY_OPS 中）。
    # 安全边界：只读，不写不删；路径不存在或无权限时返回友好错误而非抛异常。

    def _op_list_directory(self, params: Dict) -> Dict[str, Any]:
        """列出文件夹下的 SVD 文件（.svd/.xml）"""
        import os
        path = str(params.get("path", "")).strip()
        if not path:
            return {"success": False, "message": t("ai.fs_no_path", default="未指定文件夹路径"), "data": None}
        if not os.path.isdir(path):
            return {"success": False,
                    "message": t("ai.fs_not_dir", path=path, default="路径不存在或不是文件夹: {path}"),
                    "data": None}
        recursive = bool(params.get("recursive", False))
        exts = (".svd", ".xml")

        files = []
        try:
            if recursive:
                for root, _dirs, names in os.walk(path):
                    for nm in names:
                        if nm.lower().endswith(exts):
                            fp = os.path.join(root, nm)
                            files.append(self._file_meta(fp))
            else:
                for nm in os.listdir(path):
                    if nm.lower().endswith(exts):
                        fp = os.path.join(path, nm)
                        if os.path.isfile(fp):
                            files.append(self._file_meta(fp))
        except PermissionError:
            return {"success": False, "message": t("ai.fs_no_perm", path=path, default="无权限访问: {path}"), "data": None}
        except Exception as e:
            return {"success": False, "message": t("ai.fs_err", error=str(e), default="读取目录失败: {error}"), "data": None}

        msg = t("ai.fs_list_done", count=len(files), path=os.path.basename(path),
                default="在 {path} 找到 {count} 个 SVD/XML 文件")
        return {"success": True, "message": msg,
                "data": {"path": path, "count": len(files), "files": files}}

    @staticmethod
    def _file_meta(fp: str) -> Dict[str, Any]:
        import os
        try:
            st = os.stat(fp)
            return {"name": os.path.basename(fp), "path": fp,
                    "size": st.st_size, "modified": int(st.st_mtime)}
        except OSError:
            return {"name": os.path.basename(fp), "path": fp, "size": -1, "modified": 0}

    def _op_find_duplicate_svds(self, params: Dict) -> Dict[str, Any]:
        """扫描文件夹，找出外设名集合重复或内容完全相同的 SVD 文件对。

        查重策略（两层）：
        1. 完全相同：文件字节内容一致（md5）→ 一定是重复
        2. 外设重叠：两个文件的外设名集合高度重合（Jaccard>=0.8）→ 疑似重复
        """
        import os
        path = str(params.get("path", "")).strip()
        if not path or not os.path.isdir(path):
            return {"success": False, "message": t("ai.fs_no_path", default="未指定有效文件夹路径"), "data": None}
        recursive = bool(params.get("recursive", False))
        exts = (".svd", ".xml")

        # 收集文件
        file_paths = []
        try:
            if recursive:
                for root, _dirs, names in os.walk(path):
                    for nm in names:
                        if nm.lower().endswith(exts):
                            file_paths.append(os.path.join(root, nm))
            else:
                for nm in os.listdir(path):
                    fp = os.path.join(path, nm)
                    if os.path.isfile(fp) and nm.lower().endswith(exts):
                        file_paths.append(fp)
        except Exception as e:
            return {"success": False, "message": t("ai.fs_err", error=str(e), default="读取目录失败: {error}"), "data": None}

        if len(file_paths) < 2:
            return {"success": True,
                    "message": t("ai.dup_too_few", default="文件不足 2 个，无需查重"),
                    "data": {"path": path, "exact": [], "overlapping": [], "scanned": len(file_paths)}}

        # 逐文件解析外设名集合 + 算 md5
        from svd_tool.core.svd_parser import SVDParser
        import hashlib
        parser = SVDParser()
        info = []  # [{path, periphs:set, md5}]
        failures = []
        for fp in file_paths:
            try:
                with open(fp, "rb") as f:
                    md5 = hashlib.md5(f.read()).hexdigest()
                dev = parser.parse_file(fp)
                periphs = set(dev.peripherals.keys())
                info.append({"path": fp, "name": os.path.basename(fp), "periphs": periphs, "md5": md5})
            except Exception as e:
                failures.append({"path": fp, "error": str(e)})

        # 1. 完全相同（同 md5）
        by_md5: Dict[str, list] = {}
        for it in info:
            by_md5.setdefault(it["md5"], []).append(it["path"])
        exact = [{"md5": k, "files": v} for k, v in by_md5.items() if len(v) > 1]

        # 2. 外设重叠（Jaccard >= 0.8）
        overlapping = []
        n = len(info)
        for i in range(n):
            for j in range(i + 1, n):
                a, b = info[i], info[j]
                if a["md5"] == b["md5"]:
                    continue  # 已在 exact 里
                pa, pb = a["periphs"], b["periphs"]
                if not pa or not pb:
                    continue
                inter = len(pa & pb)
                union = len(pa | pb)
                if union == 0:
                    continue
                jaccard = inter / union
                if jaccard >= 0.8:
                    overlapping.append({
                        "file_a": a["path"], "file_b": b["path"],
                        "jaccard": round(jaccard, 3),
                        "common_periphs": sorted(pa & pb)[:20],
                        "common_count": inter,
                    })

        total_dup = len(exact) + len(overlapping)
        msg = t("ai.dup_result", scanned=len(info), dups=total_dup,
                default="扫描 {scanned} 个文件，发现 {dups} 组疑似重复")
        return {"success": True, "message": msg,
                "data": {"path": path, "scanned": len(info),
                         "exact": exact, "overlapping": overlapping,
                         "parse_failures": failures}}

    # ==================== 中断操作（增删改，复用 state_manager） ====================
    # 中断比寄存器/位域多一层复杂性：device.interrupts 与各 peripheral.interrupts
    # 列表需双向同步。state_manager 已完整实现该同步逻辑（含撤销），这里直接复用，
    # 避免与手动编辑的中断逻辑产生差异。

    def _op_add_interrupt(self, params: Dict) -> Dict[str, Any]:
        """添加中断"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        from svd_tool.core.data_model import Interrupt

        name = str(params.get("name", "")).strip()
        if not name:
            return {"success": False, "message": t("ai.irq_name_empty", default="中断名称不能为空"), "data": None}
        if name in device.interrupts:
            return {"success": False, "message": t("ai.irq_exists", name=name, default="中断 '{name}' 已存在"), "data": None}

        try:
            value = int(params.get("value", 0))
        except (TypeError, ValueError):
            value = 0

        peripherals = params.get("peripherals", [])
        if isinstance(peripherals, str):
            peripherals = [peripherals]
        # 兼容 peripheral（单数）字段
        single = params.get("peripheral", "").strip()
        if single and single not in peripherals:
            peripherals.insert(0, single)

        irq = Interrupt(
            name=name,
            value=value,
            description=str(params.get("description", "")),
            peripheral=peripherals[0] if peripherals else "",
            peripherals=list(peripherals),
        )

        state_manager = self.coordinator.get_component("state_manager")
        if state_manager and hasattr(state_manager, "add_interrupt"):
            state_manager.add_interrupt(irq)
        else:
            device.interrupts[name] = irq
        self._notify_refresh()
        # 中断表靠 interrupt_updated 信号自动重建（_notify_refresh 的通用刷新
        # 通道不含中断表）。显式触发，确保 AI 改完中断立刻刷新，无需切标签页。
        self._notify_interrupt_updated()
        self._mark_modified()

        return {"success": True,
                "message": t("ai.add_irq_done", name=name, value=value,
                             default="已添加中断 '{name}' (IRQ {value})"),
                "data": {"name": name, "value": value}}

    def _op_update_interrupt(self, params: Dict) -> Dict[str, Any]:
        """更新中断（支持改名、改 value/description/peripherals）"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        name = str(params.get("name", "")).strip()
        if name not in device.interrupts:
            return {"success": False, "message": t("ai.irq_not_found", name=name, default="中断 '{name}' 不存在"), "data": None}

        updates = params.get("updates", {})
        if not updates:
            return {"success": False, "message": t("ai.no_updates"), "data": None}

        old_irq = device.interrupts[name]
        new_name = str(updates.get("name", name)).strip()
        if new_name != name and new_name in device.interrupts:
            return {"success": False, "message": t("ai.irq_exists", name=new_name, default="中断 '{name}' 已存在"), "data": None}

        try:
            new_value = int(updates.get("value", old_irq.value))
        except (TypeError, ValueError):
            new_value = old_irq.value

        if "peripherals" in updates:
            peripherals = updates["peripherals"]
            if isinstance(peripherals, str):
                peripherals = [peripherals]
            peripherals = list(peripherals)
        else:
            peripherals = list(old_irq.peripherals)

        from svd_tool.core.data_model import Interrupt
        updated = Interrupt(
            name=new_name,
            value=new_value,
            description=str(updates.get("description", old_irq.description)),
            peripheral=peripherals[0] if peripherals else "",
            peripherals=peripherals,
        )

        state_manager = self.coordinator.get_component("state_manager")
        if state_manager and hasattr(state_manager, "update_interrupt"):
            state_manager.update_interrupt(name, updated)
        else:
            # 兜底：直接替换（无外设同步、无撤销）
            if new_name != name:
                del device.interrupts[name]
            device.interrupts[new_name] = updated
        self._notify_refresh()
        self._mark_modified()
        self._notify_interrupt_updated()

        return {"success": True,
                "message": t("ai.update_irq_done", name=new_name, default="已更新中断 '{name}'"),
                "data": {"name": new_name, "renamed": new_name != name}}

    def _op_remove_interrupt(self, params: Dict) -> Dict[str, Any]:
        """删除中断"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        name = str(params.get("name", "")).strip()
        if name not in device.interrupts:
            return {"success": False, "message": t("ai.irq_not_found", name=name, default="中断 '{name}' 不存在"), "data": None}

        state_manager = self.coordinator.get_component("state_manager")
        if state_manager and hasattr(state_manager, "delete_interrupt"):
            state_manager.delete_interrupt(name)
        else:
            del device.interrupts[name]
        self._notify_refresh()
        self._mark_modified()
        self._notify_interrupt_updated()

        return {"success": True,
                "message": t("ai.remove_irq_done", name=name, default="已删除中断 '{name}'"),
                "data": {"name": name}}

    # ==================== 修改操作 ====================

    def _op_update_device(self, params: Dict) -> Dict[str, Any]:
        """更新设备级属性（名称、版本、厂商、描述、作者等）"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        # 合并 "updates" 字典和直接传入的字段
        direct_fields = {"name", "version", "vendor", "description", "author",
                         "license", "copyright", "svd_version"}
        updates = dict(params.get("updates", {}) or {})
        for key in direct_fields:
            if key in params:
                updates[key] = params[key]

        if not updates:
            return {"success": False, "message": t("ai.no_updates"), "data": None}

        old_values = {}
        updatable_fields = ["name", "version", "vendor", "description", "author",
                            "license", "copyright", "svd_version"]

        for key in updatable_fields:
            if key in updates:
                old_values[key] = getattr(device, key, "")
                setattr(device, key, updates[key])

        def undo():
            for key, val in old_values.items():
                setattr(device, key, val)

        self._execute_undoable("AI: 更新设备信息", lambda: None, undo)
        self._notify_refresh()

        updated = list(updates.keys())
        return {"success": True, "message": t("ai.update_device_done", fields=', '.join(updated)), "data": {"updates": updated}}

    def _op_add_peripheral(self, params: Dict) -> Dict[str, Any]:
        """添加外设"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        from svd_tool.core.data_model import Peripheral

        name = params.get("name", "").strip()
        if not name:
            return {"success": False, "message": t("ai.periph_name_empty"), "data": None}
        if name in device.peripherals:
            return {"success": False, "message": t("ai.periph_exists", name=name), "data": None}

        base_address = params.get("base_address", "0x40000000")
        periph = Peripheral(
            name=name,
            base_address=base_address,
            description=params.get("description", ""),
            group_name=params.get("group_name", ""),
        )

        def execute():
            device.peripherals[name] = periph

        def undo():
            del device.peripherals[name]

        self._execute_undoable(f"AI: 添加外设 '{name}'", execute, undo)
        self._notify_refresh(name)

        return {"success": True, "message": t("ai.add_periph_done", name=name, addr=base_address), "data": {"name": name}}

    def _op_update_peripheral(self, params: Dict) -> Dict[str, Any]:
        """更新外设属性"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        name = params.get("name", "").strip()
        if name not in device.peripherals:
            return {"success": False, "message": t("ai.periph_not_found", name=name), "data": None}

        updates = params.get("updates", {})
        if not updates:
            return {"success": False, "message": t("ai.no_updates"), "data": None}

        periph = device.peripherals[name]
        new_name = str(updates.get("name", "")).strip()

        # 改名：复用 state_manager.rename_peripheral（已处理 dict-key 迁移、顺序保持、撤销）
        rename_done = False
        if new_name and new_name != name:
            state_manager = self.coordinator.get_component("state_manager")
            if state_manager and hasattr(state_manager, "rename_peripheral"):
                try:
                    state_manager.rename_peripheral(name, new_name)
                    rename_done = True
                except ValueError as e:
                    return {"success": False, "message": str(e), "data": None}
            else:
                # 兜底：state_manager 不可用时直接迁移（无撤销）
                if new_name in device.peripherals:
                    return {"success": False,
                            "message": t("ai.periph_exists", name=new_name), "data": None}
                order = list(device.peripherals.keys())
                old_periph = device.peripherals.pop(name)
                old_periph.name = new_name
                new_periphs = {}
                for k in order:
                    new_periphs[new_name if k == name else k] = device.peripherals.get(k, old_periph if k == name else None)
                device.peripherals.clear()
                device.peripherals.update({k: v for k, v in new_periphs.items() if v is not None})
                rename_done = True

        # 改名后，periph 引用仍有效（对象未变，仅 key 变了）；用新 name 定位
        effective_name = new_name if rename_done else name
        periph = device.peripherals[effective_name]

        # 其它可改属性（改名已单独处理，这里不动 name）
        old_values = {}
        updatable_fields = ["description", "base_address", "group_name", "display_name", "derived_from"]

        # derivedFrom 校验：派生目标必须是已存在的外设，且不能形成自引用
        if "derived_from" in updates:
            df = str(updates["derived_from"]).strip()
            if df == effective_name:
                return {"success": False,
                        "message": t("ai.derived_self", name=effective_name,
                                     default="外设不能继承自己"),
                        "data": None}
            if df and df not in device.peripherals:
                return {"success": False,
                        "message": t("ai.periph_not_found", name=df), "data": None}
            updates = dict(updates)  # 避免改到调用方
            updates["derived_from"] = df

        for key in updatable_fields:
            if key in updates:
                old_values[key] = getattr(periph, key, "")
                setattr(periph, key, updates[key])

        def undo():
            for key, val in old_values.items():
                setattr(periph, key, val)

        self._execute_undoable(f"AI: 更新外设 '{effective_name}'", lambda: None, undo)
        self._notify_refresh(effective_name)

        return {"success": True, "message": t("ai.update_periph_done", name=effective_name),
                "data": {"name": effective_name, "updates": list(updates.keys()), "renamed": rename_done}}

    def _op_remove_peripheral(self, params: Dict) -> Dict[str, Any]:
        """删除外设"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        name = params.get("name", "").strip()
        if name not in device.peripherals:
            return {"success": False, "message": t("ai.periph_not_found", name=name), "data": None}

        import copy
        removed = device.peripherals[name]
        removed_copy = copy.deepcopy(removed)

        def execute():
            if name in device.peripherals:
                del device.peripherals[name]

        def undo():
            device.peripherals[name] = removed_copy

        self._execute_undoable(f"AI: 删除外设 '{name}'", execute, undo)
        self._notify_refresh(name)

        return {"success": True, "message": t("ai.remove_periph_done", name=name), "data": {"name": name}}

    def _op_add_register(self, params: Dict) -> Dict[str, Any]:
        """添加寄存器"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        from svd_tool.core.data_model import Register

        periph_name = params.get("peripheral", "").strip()
        if periph_name not in device.peripherals:
            return {"success": False, "message": t("ai.periph_not_found", name=periph_name), "data": None}

        reg_name = params.get("name", "").strip()
        if not reg_name:
            return {"success": False, "message": t("ai.reg_name_empty"), "data": None}

        periph = device.peripherals[periph_name]
        if reg_name in periph.registers:
            return {"success": False, "message": t("ai.reg_exists", name=reg_name, periph=periph_name), "data": None}

        reg = Register(
            name=reg_name,
            offset=params.get("offset", "0x00"),
            description=params.get("description", ""),
            size=params.get("size", "0x20"),
            access=params.get("access"),
            reset_value=params.get("reset_value", "0x00000000"),
        )

        def execute():
            periph.registers[reg_name] = reg

        def undo():
            if reg_name in periph.registers:
                del periph.registers[reg_name]

        self._execute_undoable(f"AI: 添加寄存器 '{reg_name}' 到 '{periph_name}'", execute, undo)
        self._notify_refresh(periph_name)

        return {"success": True, "message": t("ai.add_reg_done", name=reg_name, periph=periph_name, offset=reg.offset), "data": {"name": reg_name}}

    def _op_update_register(self, params: Dict) -> Dict[str, Any]:
        """更新寄存器属性"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        periph_name = params.get("peripheral", "").strip()
        reg_name = params.get("name", "").strip()
        updates = params.get("updates", {})

        if periph_name not in device.peripherals:
            return {"success": False, "message": t("ai.periph_not_found", name=periph_name), "data": None}

        periph = device.peripherals[periph_name]
        if reg_name not in periph.registers:
            return {"success": False, "message": t("ai.reg_not_found", name=reg_name), "data": None}

        if not updates:
            return {"success": False, "message": t("ai.no_updates"), "data": None}

        reg = periph.registers[reg_name]
        new_name = str(updates.get("name", "")).strip()

        # 改名：需要同步迁移 dict key（registers 以 name 为 key），保持顺序并支持撤销。
        # 单纯 setattr(reg, "name", ...) 会导致 dict key 与对象 name 不一致，查找错乱。
        rename_done = False
        if new_name and new_name != reg_name:
            if new_name in periph.registers:
                return {"success": False,
                        "message": t("ai.reg_exists", name=new_name, periph=periph_name), "data": None}

            # 保存旧顺序，构造 execute/undo
            reg_order = list(periph.registers.keys())

            def _rename_execute():
                old_reg = periph.registers.pop(reg_name)
                old_reg.name = new_name
                # 重建 dict 保持顺序
                new_regs = {}
                for k in reg_order:
                    if k == reg_name:
                        new_regs[new_name] = old_reg
                    else:
                        new_regs[k] = periph.registers[k]
                # 清掉剩余（已 pop 的）再覆盖
                periph.registers.clear()
                periph.registers.update(new_regs)

            def _rename_undo():
                cur = periph.registers.pop(new_name)
                cur.name = reg_name
                restored = {}
                for k in reg_order:
                    if k == reg_name:
                        restored[reg_name] = cur
                    else:
                        restored[k] = periph.registers[k]
                periph.registers.clear()
                periph.registers.update(restored)

            self._execute_undoable(f"AI: 重命名寄存器 '{reg_name}' -> '{new_name}'",
                                   _rename_execute, _rename_undo)
            rename_done = True

        # 其它可改属性（改名已单独处理，这里不动 name）
        old_values = {}
        updatable_fields = ["description", "offset", "size", "access", "reset_value", "display_name", "derived_from"]

        # derivedFrom 校验：派生目标必须是同外设下已存在的寄存器，且不能自引用
        if "derived_from" in updates:
            df = str(updates["derived_from"]).strip()
            cur_name = new_name if rename_done else reg_name
            if df == cur_name:
                return {"success": False,
                        "message": t("ai.derived_self", name=cur_name,
                                     default="寄存器不能继承自己"),
                        "data": None}
            if df and df not in periph.registers:
                return {"success": False, "message": t("ai.reg_not_found", name=df), "data": None}
            updates = dict(updates)
            updates["derived_from"] = df

        for key in updatable_fields:
            if key in updates:
                old_values[key] = getattr(reg, key, "")
                setattr(reg, key, updates[key])

        def undo():
            for key, val in old_values.items():
                setattr(reg, key, val)

        self._execute_undoable(f"AI: 更新寄存器 '{reg_name}'", lambda: None, undo)
        self._notify_refresh(periph_name)

        result_name = new_name if rename_done else reg_name
        return {"success": True, "message": t("ai.update_reg_done", name=result_name),
                "data": {"name": result_name, "renamed": rename_done}}

    def _op_remove_register(self, params: Dict) -> Dict[str, Any]:
        """删除寄存器"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        periph_name = params.get("peripheral", "").strip()
        reg_name = params.get("name", "").strip()

        if periph_name not in device.peripherals:
            return {"success": False, "message": t("ai.periph_not_found", name=periph_name), "data": None}

        periph = device.peripherals[periph_name]
        if reg_name not in periph.registers:
            return {"success": False, "message": t("ai.reg_not_found", name=reg_name), "data": None}

        import copy
        removed_copy = copy.deepcopy(periph.registers[reg_name])

        def execute():
            if reg_name in periph.registers:
                del periph.registers[reg_name]

        def undo():
            periph.registers[reg_name] = removed_copy

        self._execute_undoable(f"AI: 删除寄存器 '{reg_name}'", execute, undo)
        self._notify_refresh(periph_name)

        return {"success": True, "message": t("ai.remove_reg_done", name=reg_name, periph=periph_name), "data": {"name": reg_name}}

    def _op_add_field(self, params: Dict) -> Dict[str, Any]:
        """添加位域"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        from svd_tool.core.data_model import Field

        periph_name = params.get("peripheral", "").strip()
        reg_name = params.get("register", "").strip()
        field_name = params.get("name", "").strip()

        if periph_name not in device.peripherals:
            return {"success": False, "message": t("ai.periph_not_found", name=periph_name), "data": None}

        periph = device.peripherals[periph_name]
        if reg_name not in periph.registers:
            return {"success": False, "message": t("ai.reg_not_found", name=reg_name), "data": None}

        reg = periph.registers[reg_name]
        if field_name in reg.fields:
            return {"success": False, "message": t("ai.field_exists", name=field_name), "data": None}

        bit_offset = int(params.get("bit_offset", 0))
        bit_width = int(params.get("bit_width", 1))

        fld = Field(
            name=field_name,
            bit_offset=bit_offset,
            bit_width=bit_width,
            description=params.get("description", ""),
            access=params.get("access"),
            reset_value=params.get("reset_value", "0x0"),
        )

        def execute():
            reg.fields[field_name] = fld

        def undo():
            if field_name in reg.fields:
                del reg.fields[field_name]

        self._execute_undoable(f"AI: 添加位域 '{field_name}' 到 '{reg_name}'", execute, undo)
        self._notify_refresh(periph_name)

        return {"success": True, "message": t("ai.add_field_done", name=field_name, start=bit_offset, end=bit_offset + bit_width - 1, reg=reg_name), "data": {"name": field_name}}

    def _op_update_field(self, params: Dict) -> Dict[str, Any]:
        """更新位域属性"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        periph_name = params.get("peripheral", "").strip()
        reg_name = params.get("register", "").strip()
        field_name = params.get("name", "").strip()
        updates = params.get("updates", {})

        if periph_name not in device.peripherals:
            return {"success": False, "message": t("ai.periph_not_found", name=periph_name), "data": None}

        periph = device.peripherals[periph_name]
        if reg_name not in periph.registers:
            return {"success": False, "message": t("ai.reg_not_found", name=reg_name), "data": None}

        reg = periph.registers[reg_name]
        if field_name not in reg.fields:
            return {"success": False, "message": t("ai.field_not_found", name=field_name), "data": None}

        if not updates:
            return {"success": False, "message": t("ai.no_updates"), "data": None}

        fld = reg.fields[field_name]
        new_name = str(updates.get("name", "")).strip()

        # 改名：同步迁移 dict key（fields 以 name 为 key），保持顺序并支持撤销。
        rename_done = False
        if new_name and new_name != field_name:
            if new_name in reg.fields:
                return {"success": False,
                        "message": t("ai.field_exists", name=new_name), "data": None}

            field_order = list(reg.fields.keys())

            def _rename_execute():
                old_fld = reg.fields.pop(field_name)
                old_fld.name = new_name
                new_fields = {}
                for k in field_order:
                    if k == field_name:
                        new_fields[new_name] = old_fld
                    else:
                        new_fields[k] = reg.fields[k]
                reg.fields.clear()
                reg.fields.update(new_fields)

            def _rename_undo():
                cur = reg.fields.pop(new_name)
                cur.name = field_name
                restored = {}
                for k in field_order:
                    if k == field_name:
                        restored[field_name] = cur
                    else:
                        restored[k] = reg.fields[k]
                reg.fields.clear()
                reg.fields.update(restored)

            self._execute_undoable(f"AI: 重命名位域 '{field_name}' -> '{new_name}'",
                                   _rename_execute, _rename_undo)
            rename_done = True

        # 其它可改属性（改名已单独处理，这里不动 name）
        old_values = {}
        updatable_fields = ["description", "bit_offset", "bit_width", "access", "reset_value", "display_name", "derived_from"]

        # derivedFrom 校验：派生目标必须是同寄存器下已存在的位域，且不能自引用
        if "derived_from" in updates:
            df = str(updates["derived_from"]).strip()
            cur_name = new_name if rename_done else field_name
            if df == cur_name:
                return {"success": False,
                        "message": t("ai.derived_self", name=cur_name,
                                     default="位域不能继承自己"),
                        "data": None}
            if df and df not in reg.fields:
                return {"success": False, "message": t("ai.field_not_found", name=df), "data": None}
            updates = dict(updates)
            updates["derived_from"] = df

        for key in updatable_fields:
            if key in updates:
                old_values[key] = getattr(fld, key, "")
                new_val = updates[key]
                if key in ("bit_offset", "bit_width"):
                    new_val = int(new_val)
                setattr(fld, key, new_val)

        def undo():
            for key, val in old_values.items():
                setattr(fld, key, val)

        self._execute_undoable(f"AI: 更新位域 '{field_name}'", lambda: None, undo)
        self._notify_refresh(periph_name)

        result_name = new_name if rename_done else field_name
        return {"success": True, "message": t("ai.update_field_done", name=result_name),
                "data": {"name": result_name, "renamed": rename_done}}

    def _op_remove_field(self, params: Dict) -> Dict[str, Any]:
        """删除位域"""
        device = self._get_device_info()
        if not device:
            return {"success": False, "message": t("ai.no_file_open"), "data": None}

        periph_name = params.get("peripheral", "").strip()
        reg_name = params.get("register", "").strip()
        field_name = params.get("name", "").strip()

        if periph_name not in device.peripherals:
            return {"success": False, "message": t("ai.periph_not_found", name=periph_name), "data": None}

        periph = device.peripherals[periph_name]
        if reg_name not in periph.registers:
            return {"success": False, "message": t("ai.reg_not_found", name=reg_name), "data": None}

        reg = periph.registers[reg_name]
        if field_name not in reg.fields:
            return {"success": False, "message": t("ai.field_not_found", name=field_name), "data": None}

        import copy
        removed_copy = copy.deepcopy(reg.fields[field_name])

        def execute():
            if field_name in reg.fields:
                del reg.fields[field_name]

        def undo():
            reg.fields[field_name] = removed_copy

        self._execute_undoable(f"AI: 删除位域 '{field_name}'", execute, undo)
        self._notify_refresh(periph_name)

        return {"success": True, "message": t("ai.remove_field_done", name=field_name, reg=reg_name), "data": {"name": field_name}}

    # ==================== 多文档操作 ====================

    def _op_open_document(self, params: Dict) -> Dict[str, Any]:
        """打开一个 SVD 文件载入编辑器为新文档。

        静默模式下：工作线程内解析（纯数据构造，线程安全），再 call_blocking 到
        主线程做"最小装配"（state_manager.device_info + 树重建 + 注册文档），
        跳过中断表/预览/基础信息等重刷新（推迟到 flush）。
        非静默：整体 call_blocking 调 main_window._load_svd_from_path 复用完整流程。
        """
        file_path = params.get("file_path", "") or params.get("file", "")
        if isinstance(file_path, str):
            file_path = file_path.strip()
        if not file_path:
            return {"success": False, "message": t("ai.open_doc_no_path"), "data": None}

        import os
        if not os.path.isfile(file_path):
            return {"success": False, "message": t("ai.diff_file_not_found", path=file_path), "data": None}

        if not self.main_window:
            return {"success": False, "message": t("ai.doc_mgr_unavailable"), "data": None}

        # 静默模式：工作线程解析 + 主线程最小装配
        if getattr(self, "_silent", False):
            try:
                from svd_tool.core.svd_parser import SVDParser
                parser = SVDParser()
                device_info = parser.parse_file(file_path)
            except Exception as e:
                return {"success": False, "message": t("ai.diff_parse_fail", error=str(e)), "data": None}

            doc_id_box = {"doc_id": None, "name": None}

            def _assemble():
                try:
                    mw = self.main_window
                    # 去重：已打开则切回，不重新解析覆盖（保留未保存编辑）
                    existing = mw.document_manager.find_by_file_path(file_path) \
                        if hasattr(mw.document_manager, "find_by_file_path") else None
                    if existing:
                        mw._save_current_document_state()
                        mw.document_manager.switch_to(existing)
                        ex = mw.document_manager.get_document(existing)
                        if ex:
                            mw._restore_document_state(ex)
                        doc_id_box["doc_id"] = existing
                        doc_id_box["name"] = ex.display_name if ex else os.path.basename(file_path)
                        return

                    mw._save_current_document_state()
                    mw.state_manager.pause_notifications()
                    try:
                        mw.state_manager.device_info = device_info
                        mw.state_manager.clear_selection()
                        mw.state_manager.command_history.clear()
                        mw.peripheral_manager.update_peripheral_tree(preserve_expanded=False)
                    finally:
                        mw.state_manager.resume_notifications()
                    new_doc_id = mw.document_manager.open_document(device_info, file_path=file_path)
                    mw.document_manager.switch_to(new_doc_id)
                    if hasattr(mw.layout_manager, "show_editor"):
                        mw.layout_manager.show_editor()
                    doc_id_box["doc_id"] = new_doc_id
                    doc_id_box["name"] = device_info.name or os.path.basename(file_path)
                except Exception as e:
                    logger.error(f"open_document 静默装配失败: {e}", exc_info=True)
                    raise

            try:
                self._gui.call_blocking(_assemble)
            except Exception as e:
                return {"success": False, "message": t("ai.op_failed", error=str(e)), "data": None}

            self._dirty = True
            return {
                "success": True,
                "message": t("ai.open_doc_done", name=doc_id_box["name"]),
                "data": {"doc_id": doc_id_box["doc_id"], "name": doc_id_box["name"]},
            }

        # 非静默：复用完整流程（含警告弹窗、中断表/预览/基础信息刷新）
        def _open_full():
            try:
                self.main_window._load_svd_from_path(file_path)
                if hasattr(self.main_window.layout_manager, "show_editor"):
                    self.main_window.layout_manager.show_editor()
                return os.path.basename(file_path)
            except Exception as e:
                logger.error(f"open_document 打开失败: {e}", exc_info=True)
                raise

        try:
            name = self._gui.call_blocking(_open_full)
        except Exception as e:
            return {"success": False, "message": t("ai.diff_parse_fail", error=str(e)), "data": None}

        return {
            "success": True,
            "message": t("ai.open_doc_done", name=name),
            "data": {"name": name},
        }

    def _op_switch_document(self, params: Dict) -> Dict[str, Any]:
        """切换到指定文档"""
        if not self.main_window or not hasattr(self.main_window, 'document_manager'):
            return {"success": False, "message": t("ai.doc_mgr_unavailable"), "data": None}

        dm = self.main_window.document_manager
        target = params.get("doc_id", "").strip()
        name_hint = params.get("name", "").strip()

        if not target and not name_hint:
            return {"success": False, "message": t("ai.doc_no_param"), "data": None}

        # 按 doc_id 查找
        if target and target in dm.get_all_documents():
            # 先保存当前文档状态
            if hasattr(self.main_window, '_save_current_document_state'):
                self.main_window._save_current_document_state()
            dm.switch_to(target)
            if hasattr(self.main_window, '_restore_document_state'):
                doc = dm.get_document(target)
                if doc:
                    self.main_window._restore_document_state(doc)
            doc = dm.get_document(target)
            return {"success": True, "message": t("ai.doc_switch_done", name=doc.display_name), "data": {"doc_id": target}}

        # 按名称模糊查找
        if name_hint:
            name_lower = name_hint.lower()
            for doc_id, doc in dm.get_all_documents().items():
                if name_lower in doc.display_name.lower() or name_lower in (doc.device_info.name or "").lower():
                    if hasattr(self.main_window, '_save_current_document_state'):
                        self.main_window._save_current_document_state()
                    dm.switch_to(doc_id)
                    if hasattr(self.main_window, '_restore_document_state'):
                        self.main_window._restore_document_state(doc)
                    return {"success": True, "message": t("ai.doc_switch_done", name=doc.display_name), "data": {"doc_id": doc_id}}

        return {"success": False, "message": t("ai.doc_not_found", hint=target or name_hint), "data": None}

    def _confirm_overwrite(self, save_path: str, doc_name: str) -> bool:
        """保存到已存在的文件前弹确认框（主线程），返回是否允许覆盖。

        通过 _gui.call_blocking 派发到主线程弹 QMessageBox，工作线程阻塞等待。
        用户拒绝则返回 False，调用方应取消保存。
        """
        import os
        if not os.path.isfile(save_path):
            return True  # 文件不存在，无需确认

        def _ask() -> bool:
            from PyQt6.QtWidgets import QMessageBox
            parent = self.main_window if self.main_window else None
            ret = QMessageBox.warning(
                parent,
                t("ai.save_overwrite_title", default="确认覆盖文件"),
                t("ai.save_overwrite_text", path=save_path, doc=doc_name,
                  default="AI 即将把文档 '{doc}' 保存到已存在的文件：\n{path}\n\n确认覆盖？"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            return ret == QMessageBox.StandardButton.Yes

        return self._gui.call_blocking(_ask)

    def _op_save_document(self, params: Dict) -> Dict[str, Any]:
        """保存指定文档（默认保存当前文档）"""
        if not self.main_window or not hasattr(self.main_window, 'document_manager'):
            return {"success": False, "message": t("ai.doc_mgr_unavailable"), "data": None}

        dm = self.main_window.document_manager
        target_id = params.get("doc_id", "").strip() or dm.active_doc_id

        if not target_id:
            return {"success": False, "message": t("ai.doc_no_save"), "data": None}

        doc = dm.get_document(target_id)
        if not doc:
            return {"success": False, "message": t("ai.doc_not_exist", id=target_id), "data": None}

        # 关键：生成 XML 前必须把 state_manager 当前编辑的数据同步回目标 doc。
        # 否则 doc.device_info 可能还停留在切换前的状态（甚至因浅引用指向其它文档），
        # 导致保存时写入错误数据（"保存doc1却写入doc2"的恶性 bug）。
        # 手动保存（save_all_documents）也做了同样的 _save_current_document_state。
        if hasattr(self.main_window, '_save_current_document_state'):
            self.main_window._save_current_document_state()

        try:
            from svd_tool.core.svd_generator import SVDGenerator
            generator = SVDGenerator(doc.device_info, skip_derived_registers=getattr(self.main_window, 'skip_derived_registers', True))
            svd_xml = generator.generate()

            save_path = params.get("file_path", "").strip() or doc.file_path
            if not save_path:
                return {"success": False, "message": t("ai.doc_no_path", name=doc.display_name), "data": None}

            # 覆盖已存在文件前确认（防误覆盖，#用户反馈）
            if not self._confirm_overwrite(save_path, doc.display_name):
                return {"success": False,
                        "message": t("ai.save_cancelled", default="用户取消了保存（拒绝覆盖）"),
                        "data": {"doc_id": target_id, "path": save_path, "cancelled": True}}

            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(svd_xml)

            dm.save_document(target_id, file_path=save_path if params.get("file_path") else None)
            return {"success": True, "message": t("ai.doc_save_done", name=doc.display_name, path=save_path), "data": {"doc_id": target_id, "path": save_path}}
        except Exception as e:
            return {"success": False, "message": t("ai.doc_save_fail", error=str(e)), "data": None}

    def _op_batch_save(self, params: Dict) -> Dict[str, Any]:
        """批量保存文档

        params:
            paths: {doc_id: new_file_path} — 每个文档指定新路径（可选，指定后原文件不动）
            doc_ids: [doc_id, ...] — 指定要保存的文档
            all: true — 保存所有文档
        """
        if not self.main_window or not hasattr(self.main_window, 'document_manager'):
            return {"success": False, "message": t("ai.doc_mgr_unavailable"), "data": None}

        dm = self.main_window.document_manager
        paths = params.get("paths", {})
        target_ids = params.get("doc_ids", None)
        save_all = params.get("all", False)

        if save_all:
            docs_to_save = list(dm.get_all_documents().keys())
        elif target_ids:
            docs_to_save = target_ids
        else:
            docs_to_save = dm.get_modified_documents()

        if not docs_to_save:
            return {"success": True, "message": t("ai.doc_no_save"), "data": {"saved": [], "failed": []}}

        # 同步当前文档的编辑状态到对应 doc（同 _op_save_document，避免写入串扰数据）
        if hasattr(self.main_window, '_save_current_document_state'):
            self.main_window._save_current_document_state()

        from svd_tool.core.svd_generator import SVDGenerator
        saved = []
        failed = []

        for doc_id in docs_to_save:
            doc = dm.get_document(doc_id)
            if not doc:
                failed.append({"doc_id": doc_id, "error": t("ai.doc_not_exist", id=doc_id)})
                continue
            new_path = paths.get(doc_id, "").strip() if paths else ""
            save_path = new_path or doc.file_path
            if not save_path:
                failed.append({"doc_id": doc_id, "name": doc.display_name, "error": t("ai.doc_no_path_batch")})
                continue
            try:
                # 覆盖已存在文件前确认（每个文档单独确认，拒绝则跳过该文档）
                if not self._confirm_overwrite(save_path, doc.display_name):
                    failed.append({"doc_id": doc_id, "name": doc.display_name,
                                   "error": t("ai.save_cancelled", default="用户取消了保存")})
                    continue
                generator = SVDGenerator(doc.device_info, skip_derived_registers=getattr(self.main_window, 'skip_derived_registers', True))
                svd_xml = generator.generate()
                with open(save_path, 'w', encoding='utf-8') as f:
                    f.write(svd_xml)
                # 有新路径时更新文档记录，否则只标记已保存
                dm.save_document(doc_id, file_path=new_path or None)
                saved.append({"doc_id": doc_id, "name": doc.display_name, "path": save_path})
            except Exception as e:
                failed.append({"doc_id": doc_id, "name": doc.display_name, "error": str(e)})

        msg = t("ai.doc_batch_done", saved=len(saved), failed=len(failed))
        return {"success": len(failed) == 0, "message": msg, "data": {"saved": saved, "failed": failed}}
