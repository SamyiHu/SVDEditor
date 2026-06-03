from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView
from ...i18n.i18n import t
from ...core.address_conflict_detector import ConflictType, ConflictSeverity
from ..managers.batch_operations_manager import BatchOperationsManager


class ToolActionsMixin:

    def show_advanced_search(self):
        """显示高级搜索对话框"""
        self.search_manager.show_advanced_search_dialog(self)

    def show_goto_address(self):
        """显示跳转到地址对话框"""
        self.search_manager.show_goto_address_dialog(self)

    def show_batch_modify(self):
        """显示批量修改属性对话框"""
        mgr = BatchOperationsManager(self.state_manager, self.coordinator)
        mgr.operation_completed.connect(lambda desc, n: self._on_batch_completed(desc, n))
        mgr.show_batch_modify_dialog(self)

    def show_batch_generate(self):
        """显示批量生成寄存器对话框"""
        mgr = BatchOperationsManager(self.state_manager, self.coordinator)
        mgr.operation_completed.connect(lambda desc, n: self._on_batch_completed(desc, n))
        mgr.show_batch_generate_dialog(self)

    def show_batch_clone(self):
        """显示批量克隆寄存器对话框"""
        mgr = BatchOperationsManager(self.state_manager, self.coordinator)
        mgr.operation_completed.connect(lambda desc, n: self._on_batch_completed(desc, n))
        mgr.show_batch_clone_dialog(self)

    def _on_batch_completed(self, desc: str, count: int):
        """批量操作完成后的 UI 刷新"""
        self.peripheral_manager.update_peripheral_tree()
        self.update_data_stats()
        self.layout_manager.update_status(desc)
        self.logger.info(desc)

    def show_svd_diff(self):
        """显示 SVD 差异比较对话框（纯对比，非模态）"""
        self._show_diff_dialog(initial_mode="compare")

    def show_svd_diff_merge(self):
        """显示 SVD 比较与合并对话框（非模态）"""
        self._show_diff_dialog(initial_mode="merge")

    def _show_diff_dialog(self, initial_mode="compare"):
        """统一对话框入口"""
        from ..dialogs.svd_diff_dialog import SVDDiffDialog
        if not self.state_manager.device_info:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, t("message.info"), t("msg.open_or_create_first"))
            return

        self._diff_dialog = SVDDiffDialog(
            self, self.state_manager.device_info,
            document_manager=self.document_manager,
            initial_mode=initial_mode
        )
        self._diff_dialog.merge_completed.connect(self._on_merge_completed)
        self._diff_dialog.setWindowFlags(
            self._diff_dialog.windowFlags() | Qt.WindowType.WindowMinMaxButtonsHint
        )
        self._diff_dialog.show()

    def _cleanup_diff_merge_dialog(self):
        """清理比较合并对话框引用"""
        if hasattr(self, '_diff_merge_dialog'):
            self._diff_merge_dialog = None

    def _on_merge_completed(self, merged_device):
        """合并完成后的回调"""
        from PyQt6.QtWidgets import QApplication

        # 更新状态管理器
        self.state_manager.device_info = merged_device
        self.state_manager.clear_selection()

        # 通知状态变更
        self.state_manager._notify_state_change()

        # 发射事件
        if hasattr(self, 'coordinator') and self.coordinator:
            self.coordinator.emit_event("device_info_updated", merged_device)

        # 刷新 UI
        self.peripheral_manager.update_peripheral_tree()
        self.update_data_stats()
        self._update_interrupt_table()

        # 更新预览
        if self.preview_manager:
            self.preview_manager.refresh_preview(immediate=True)

        # 更新基础信息
        if hasattr(self.layout_manager, 'update_basic_info'):
            self.layout_manager.update_basic_info(merged_device)

        self.layout_manager.update_status(t("status.merge_complete"))
        self.logger.info("SVD 导入合并完成")

    def show_address_conflicts(self):
        """显示地址冲突检测面板"""
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
            QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox)

        # 运行检测
        self.conflict_detector.detect_all(self.state_manager.device_info)
        conflicts = self.conflict_detector.conflicts

        dialog = QDialog(self)
        dialog.setWindowTitle("地址冲突检测")
        dialog.setMinimumSize(800, 500)
        layout = QVBoxLayout(dialog)

        # 摘要
        summary = self.conflict_detector.get_summary()
        summary_label = QLabel(
            f"检测完成：共 {summary['total']} 个冲突 "
            f"({summary['errors']} 错误, {summary['warnings']} 警告)"
        )
        if summary['errors'] > 0:
            summary_label.setStyleSheet("color: red; font-weight: bold; font-size: 14px;")
        else:
            summary_label.setStyleSheet("color: green; font-weight: bold; font-size: 14px;")
        layout.addWidget(summary_label)

        # 冲突表格
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["严重程度", "类型", "位置", "消息", "详情"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setRowCount(len(conflicts))

        for row, c in enumerate(conflicts):
            severity_item = QTableWidgetItem("🔴 错误" if c.severity == ConflictSeverity.ERROR else "🟡 警告")
            type_map = {
                ConflictType.PERIPHERAL_ADDRESS_OVERLAP: "外设地址重叠",
                ConflictType.PERIPHERAL_BASE_DUPLICATE: "外设基地址重复",
                ConflictType.REGISTER_OFFSET_DUPLICATE: "寄存器偏移重复",
                ConflictType.FIELD_BIT_OVERLAP: "位域位重叠",
                ConflictType.INTERRUPT_VALUE_DUPLICATE: "中断号重复",
            }
            table.setItem(row, 0, severity_item)
            table.setItem(row, 1, QTableWidgetItem(type_map.get(c.conflict_type, str(c.conflict_type))))
            table.setItem(row, 2, QTableWidgetItem(c.location))
            table.setItem(row, 3, QTableWidgetItem(c.message))
            table.setItem(row, 4, QTableWidgetItem(c.detail))

        layout.addWidget(table)

        # 按钮
        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton("刷新检测")
        refresh_btn.clicked.connect(lambda: (
            self.conflict_detector.detect_all(self.state_manager.device_info),
            dialog.accept(),
            self.show_address_conflicts()
        ))
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(refresh_btn)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        dialog.exec()

    def _on_data_changed_detect_conflicts(self):
        """数据变更时执行冲突检测"""
        if hasattr(self, 'conflict_detector') and hasattr(self, 'state_manager'):
            try:
                self.conflict_detector.detect_all(self.state_manager.device_info)
            except Exception as e:
                self.logger.error(f"冲突检测失败: {e}")

    def _on_conflicts_updated(self, conflicts):
        """冲突列表更新时的回调"""
        try:
            summary = self.conflict_detector.get_summary()
            error_count = summary.get('errors', 0)

            # 更新状态栏
            if error_count > 0:
                self.layout_manager.update_status(
                    f"⚠ 检测到 {error_count} 个地址冲突"
                )
            elif hasattr(self, 'layout_manager'):
                pass  # 不覆盖其他状态消息

        except Exception as e:
            self.logger.error(f"冲突回调处理失败: {e}")
