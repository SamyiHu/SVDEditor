# svd_tool/ui/form_builder.py
"""
表单构建器 - 用于动态创建表单
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QComboBox, QSpinBox,
    QCheckBox, QTextEdit, QGroupBox, QPushButton
)
from PyQt6.QtCore import Qt


class FormBuilder:
    """表单构建器"""
    
    @staticmethod
    def create_labeled_edit(label_text: str, placeholder: str = "", 
                           default_value: str = "") -> tuple:
        """创建带标签的编辑框"""
        layout = QHBoxLayout()
        label = QLabel(label_text)
        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        if default_value:
            edit.setText(default_value)
        layout.addWidget(label)
        layout.addWidget(edit)
        return layout, edit
    
    @staticmethod
    def create_labeled_combo(label_text: str, items: list) -> tuple:
        """创建带标签的下拉框"""
        layout = QHBoxLayout()
        label = QLabel(label_text)
        combo = QComboBox()
        combo.addItems(items)
        layout.addWidget(label)
        layout.addWidget(combo)
        return layout, combo
    
    @staticmethod
    def create_labeled_spinbox(label_text: str, min_val: int = 0, 
                              max_val: int = 100, default_val: int = 0) -> tuple:
        """创建带标签的微调框"""
        layout = QHBoxLayout()
        label = QLabel(label_text)
        spinbox = QSpinBox()
        spinbox.setRange(min_val, max_val)
        spinbox.setValue(default_val)
        layout.addWidget(label)
        layout.addWidget(spinbox)
        return layout, spinbox
    
    @staticmethod
    def create_form_group(title: str, widgets: list) -> QGroupBox:
        """创建表单组"""
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        
        for widget in widgets:
            if isinstance(widget, tuple):
                layout.addLayout(widget[0])
            else:
                layout.addWidget(widget)
        
        return group
    
    @staticmethod
    def create_button(text: str, callback=None, style: str = "") -> QPushButton:
        """创建按钮"""
        button = QPushButton(text)
        if callback:
            button.clicked.connect(callback)
        if style:
            button.setStyleSheet(style)
        return button
    
    @staticmethod
    def create_grid_form(labels_edits: list) -> tuple:
        """创建网格表单"""
        layout = QGridLayout()
        edits = []
        
        for i, (label_text, placeholder, default_value) in enumerate(labels_edits):
            label = QLabel(label_text)
            edit = QLineEdit()
            edit.setPlaceholderText(placeholder)
            if default_value:
                edit.setText(default_value)
            
            layout.addWidget(label, i, 0)
            layout.addWidget(edit, i, 1)
            edits.append(edit)
        
        return layout, edits
    
    @staticmethod
    def create_two_column_form(left_items: list, right_items: list) -> tuple:
        """创建两列表单"""
        main_layout = QHBoxLayout()
        left_layout = QVBoxLayout()
        right_layout = QVBoxLayout()
        
        left_edits = []
        right_edits = []
        
        # 左侧项目
        for item in left_items:
            if isinstance(item, tuple) and len(item) == 3:
                layout, edit = FormBuilder.create_labeled_edit(*item)
                left_layout.addLayout(layout)
                left_edits.append(edit)
            elif isinstance(item, QWidget):
                left_layout.addWidget(item)
        
        # 右侧项目
        for item in right_items:
            if isinstance(item, tuple) and len(item) == 3:
                layout, edit = FormBuilder.create_labeled_edit(*item)
                right_layout.addLayout(layout)
                right_edits.append(edit)
            elif isinstance(item, QWidget):
                right_layout.addWidget(item)
        
        main_layout.addLayout(left_layout)
        main_layout.addLayout(right_layout)
        
        return main_layout, left_edits + right_edits