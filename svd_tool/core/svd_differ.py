# -*- coding: utf-8 -*-
"""SVD差异比较引擎"""

import copy
from enum import Enum, auto
from typing import Optional, List
from .svd_merger import SVDMerger


class DiffType(Enum):
    """差异类型枚举"""
    UNCHANGED = auto()
    ADDED = auto()
    REMOVED = auto()
    MODIFIED = auto()


class DiffItem:
    """层次化的差异项"""
    def __init__(self, path: str, diff_type: DiffType,
                 old_value=None, new_value=None, category: str = 'property'):
        self.path = path
        self.diff_type = diff_type
        self.old_value = old_value
        self.new_value = new_value
        self.category = category
        self.children: List['DiffItem'] = []

    @property
    def count_changes(self) -> int:
        """递归统计变更数量"""
        count = 0
        if self.diff_type in (DiffType.ADDED, DiffType.REMOVED, DiffType.MODIFIED):
            count += 1
        for child in self.children:
            count += child.count_changes
        return count

    def __repr__(self):
        return f"DiffItem({self.diff_type.name}: {self.path})"


class SVDDiffResult:
    """单个差异项（扁平列表格式）"""
    def __init__(self, path, diff_type, old_value=None, new_value=None, category='property'):
        self.path = path
        self.type = diff_type  # 'added', 'removed', 'modified'
        self.old_value = old_value
        self.new_value = new_value
        self.category = category  # 'peripheral', 'register', 'field', 'property'
    
    def __repr__(self):
        return f"SVDDiffResult({self.category}/{self.type}: {self.path})"


class SVDDiffer:
    """SVD差异比较引擎
    
    支持两种使用方式：
    1. SVDDiffer(device_a, device_b) + compare() — 基于字典的分析模式
    2. SVDDiffer() + diff(device_a, device_b) — 基于 DeviceInfo 对象的模式
    """
    
    def __init__(self, svd_a=None, svd_b=None):
        """初始化比较器
        
        Args:
            svd_a: 第一个SVD数据（基准），可以是字典或 DeviceInfo
            svd_b: 第二个SVD数据（比较），可以是字典或 DeviceInfo
        """
        self.svd_a = svd_a
        self.svd_b = svd_b
        self._diffs = None
        
        # 合并器（用于字典模式）
        self._merger = SVDMerger(svd_a, svd_b) if svd_a and svd_b else None
        
        # 过滤选项（用于 DeviceInfo 模式）
        self.ignore_description = False
        self.ignore_display_name = False
        self.ignore_reset_value = False
    
    # ===== DeviceInfo 对象模式 =====
    
    def diff(self, device_a, device_b):
        """比较两个 DeviceInfo 对象，返回层次化的 DiffItem 列表
        
        Args:
            device_a: 基准 DeviceInfo 对象
            device_b: 比较 DeviceInfo 对象
            
        Returns:
            List[DiffItem]: 层次化的差异列表
        """
        results = []

        periphs_a = {name: p for name, p in device_a.peripherals.items()} if device_a else {}
        periphs_b = {name: p for name, p in device_b.peripherals.items()} if device_b else {}

        # 按 B 的原始顺序排列，B 中没有的 A 外设追加在末尾
        ordered_names = list(periphs_b.keys())
        for name in periphs_a:
            if name not in periphs_b:
                ordered_names.append(name)

        for periph_name in ordered_names:
            p_a = periphs_a.get(periph_name)
            p_b = periphs_b.get(periph_name)
            
            if p_a and not p_b:
                # 外设被删除
                item = DiffItem(periph_name, DiffType.REMOVED,
                                old_value=f"baseAddress={getattr(p_a, 'base_address', 'N/A')}",
                                category='peripheral')
                results.append(item)
            elif not p_a and p_b:
                # 外设被新增
                item = DiffItem(periph_name, DiffType.ADDED,
                                new_value=f"baseAddress={getattr(p_b, 'base_address', 'N/A')}",
                                category='peripheral')
                results.append(item)
            else:
                # 外设在两边都存在，比较内容
                periph_diff = self._diff_peripheral(periph_name, p_a, p_b)
                if periph_diff:
                    results.append(periph_diff)
        
        return results
    
    def _diff_peripheral(self, name, p_a, p_b):
        """比较两个外设"""
        children = []
        
        # 比较外设属性
        prop_diffs = self._diff_properties(name, p_a, p_b, 
            ['base_address', 'description', 'display_name', 'version', 'group_name'])
        children.extend(prop_diffs)
        
        # 比较寄存器（按 B 的原始顺序排列）
        regs_a = {r_name: r for r_name, r in p_a.registers.items()} if p_a.registers else {}
        regs_b = {r_name: r for r_name, r in p_b.registers.items()} if p_b.registers else {}

        ordered_reg_names = list(regs_b.keys())
        for rname in regs_a:
            if rname not in regs_b:
                ordered_reg_names.append(rname)

        for reg_name in ordered_reg_names:
            r_a = regs_a.get(reg_name)
            r_b = regs_b.get(reg_name)
            
            if r_a and not r_b:
                children.append(DiffItem(f"{name}.{reg_name}", DiffType.REMOVED,
                                         category='register'))
            elif not r_a and r_b:
                children.append(DiffItem(f"{name}.{reg_name}", DiffType.ADDED,
                                         category='register'))
            else:
                reg_diff = self._diff_register(f"{name}.{reg_name}", r_a, r_b)
                if reg_diff:
                    children.append(reg_diff)
        
        # 比较中断
        irqs_a = {i.name: i for i in (p_a.interrupts or []) if hasattr(i, 'name') and i.name} if p_a else {}
        irqs_b = {i.name: i for i in (p_b.interrupts or []) if hasattr(i, 'name') and i.name} if p_b else {}
        
        all_irq_names = set(list(irqs_a.keys()) + list(irqs_b.keys()))
        
        for irq_name in sorted(all_irq_names):
            i_a = irqs_a.get(irq_name)
            i_b = irqs_b.get(irq_name)
            
            if i_a and not i_b:
                children.append(DiffItem(f"{name}.{irq_name}", DiffType.REMOVED,
                                         category='interrupt'))
            elif not i_a and i_b:
                children.append(DiffItem(f"{name}.{irq_name}", DiffType.ADDED,
                                         category='interrupt'))
            else:
                irq_diff = self._diff_interrupt_props(f"{name}.{irq_name}", i_a, i_b)
                children.extend(irq_diff)
        
        if not children:
            return None
        
        has_changes = any(c.diff_type != DiffType.UNCHANGED for c in children)
        item = DiffItem(name, DiffType.MODIFIED if has_changes else DiffType.UNCHANGED,
                        category='peripheral')
        item.children = children
        return item
    
    def _diff_register(self, path, r_a, r_b):
        """比较两个寄存器"""
        children = []
        
        # 比较寄存器属性
        reg_prop_diffs = self._diff_properties(path, r_a, r_b,
            ['address_offset', 'size', 'access', 'reset_value', 'reset_mask',
             'description', 'display_name'])
        children.extend(reg_prop_diffs)
        
        # 比较位域
        fields_a = {f.name: f for f in (r_a.fields.values() if hasattr(r_a.fields, 'values') else (r_a.fields or []))} if r_a.fields else {}
        if not isinstance(fields_a, dict) and hasattr(r_a.fields, 'items'):
            fields_a = dict(r_a.fields)
        
        fields_b = {f.name: f for f in (r_b.fields.values() if hasattr(r_b.fields, 'values') else (r_b.fields or []))} if r_b.fields else {}
        if not isinstance(fields_b, dict) and hasattr(r_b.fields, 'items'):
            fields_b = dict(r_b.fields)
        
        all_field_names = set(list(fields_a.keys()) + list(fields_b.keys()))
        
        for field_name in sorted(all_field_names):
            f_a = fields_a.get(field_name)
            f_b = fields_b.get(field_name)
            
            if f_a and not f_b:
                children.append(DiffItem(f"{path}.{field_name}", DiffType.REMOVED,
                                         category='field'))
            elif not f_a and f_b:
                children.append(DiffItem(f"{path}.{field_name}", DiffType.ADDED,
                                         category='field'))
            else:
                field_diff = self._diff_field(f"{path}.{field_name}", f_a, f_b)
                if field_diff:
                    children.append(field_diff)
        
        if not children:
            return None
        
        has_changes = any(c.diff_type != DiffType.UNCHANGED for c in children)
        item = DiffItem(path, DiffType.MODIFIED if has_changes else DiffType.UNCHANGED,
                        category='register')
        item.children = children
        return item
    
    def _diff_field(self, path, f_a, f_b):
        """比较两个位域"""
        children = self._diff_properties(path, f_a, f_b,
            ['bit_offset', 'bit_width', 'access', 'description', 'display_name'])
        
        if not children:
            return None
        
        has_changes = any(c.diff_type != DiffType.UNCHANGED for c in children)
        item = DiffItem(path, DiffType.MODIFIED if has_changes else DiffType.UNCHANGED,
                        category='field')
        item.children = children
        return item
    
    def _diff_properties(self, path, obj_a, obj_b, props):
        """比较两个对象的指定属性"""
        diffs = []
        for prop in props:
            # 跳过被过滤的属性
            if prop == 'description' and self.ignore_description:
                continue
            if prop == 'display_name' and self.ignore_display_name:
                continue
            if prop == 'reset_value' and self.ignore_reset_value:
                continue
            
            val_a = self._get_attr(obj_a, prop)
            val_b = self._get_attr(obj_b, prop)
            
            if val_a != val_b:
                diffs.append(DiffItem(
                    f"{path}.{prop}",
                    DiffType.MODIFIED,
                    old_value=str(val_a) if val_a is not None else "",
                    new_value=str(val_b) if val_b is not None else "",
                    category='property'
                ))
        return diffs
    
    def _diff_interrupt_props(self, path, i_a, i_b):
        """比较两个中断"""
        return self._diff_properties(path, i_a, i_b, ['value', 'description'])
    
    @staticmethod
    def _get_attr(obj, name):
        """安全获取对象属性，支持多种命名风格"""
        # 尝试直接属性名
        val = getattr(obj, name, None)
        if val is not None:
            return val
        # 尝试下划线转驼峰
        parts = name.split('_')
        camel = parts[0] + ''.join(p.capitalize() for p in parts[1:])
        return getattr(obj, camel, None)
    
    def generate_summary(self, diffs: List[DiffItem]) -> str:
        """生成差异摘要文本
        
        Args:
            diffs: DiffItem 列表
            
        Returns:
            str: 格式化的差异摘要
        """
        lines = ["=" * 60, "SVD 差异比较报告", "=" * 60, ""]
        
        added = sum(d.count_changes for d in diffs if self._item_has_type(d, DiffType.ADDED))
        removed = sum(d.count_changes for d in diffs if self._item_has_type(d, DiffType.REMOVED))
        modified = sum(d.count_changes for d in diffs if self._item_has_type(d, DiffType.MODIFIED))
        
        lines.append(f"总计变更: {added + removed + modified} 项")
        lines.append(f"  新增: {added}")
        lines.append(f"  删除: {removed}")
        lines.append(f"  修改: {modified}")
        lines.append("")
        
        self._append_summary_items(lines, diffs, 0)
        
        return "\n".join(lines)
    
    def _append_summary_items(self, lines, items, indent):
        """递归生成摘要"""
        prefix = "  " * indent
        for item in items:
            type_icon = {
                DiffType.ADDED: "[+]",
                DiffType.REMOVED: "[-]",
                DiffType.MODIFIED: "[~]",
                DiffType.UNCHANGED: "   ",
            }.get(item.diff_type, "   ")
            
            if item.diff_type != DiffType.UNCHANGED:
                line = f"{prefix}{type_icon} {item.path}"
                if item.old_value is not None or item.new_value is not None:
                    old_str = str(item.old_value) if item.old_value is not None else ""
                    new_str = str(item.new_value) if item.new_value is not None else ""
                    if old_str or new_str:
                        line += f"  ({old_str} → {new_str})"
                lines.append(line)
            
            if item.children:
                self._append_summary_items(lines, item.children, indent + 1)
    
    def _item_has_type(self, item: DiffItem, diff_type: DiffType) -> bool:
        """递归检查差异类型"""
        if item.diff_type == diff_type:
            return True
        return any(self._item_has_type(c, diff_type) for c in item.children)
    
    # ===== 字典模式（基于 SVDMerger） =====
    
    def compare(self):
        """执行比较（字典模式），返回扁平差异列表
        
        统一使用SVDMerger.analyze()进行分析，
        然后将层次化结果转换为扁平的差异列表。
        """
        if self._diffs is not None:
            return self._diffs
        
        self._diffs = []
        
        if not self._merger:
            return self._diffs
        
        # 使用统一的分析引擎
        analysis = self._merger.analyze()
        
        # 将分析结果转换为扁平的差异列表
        self._convert_analysis_to_diffs(analysis)
        
        return self._diffs
    
    def _convert_analysis_to_diffs(self, analysis):
        """将SVDMerger的分析结果转换为扁平差异列表"""
        
        # 处理新增的外设
        for periph_name in analysis.get('added_peripherals', []):
            periph = self._find_peripheral(self.svd_b, periph_name)
            if periph:
                self._diffs.append(SVDDiffResult(
                    path=periph_name,
                    diff_type='added',
                    new_value=self._peripheral_summary(periph),
                    category='peripheral'
                ))
        
        # 处理删除的外设
        for periph_name in analysis.get('removed_peripherals', []):
            periph = self._find_peripheral(self.svd_a, periph_name)
            if periph:
                self._diffs.append(SVDDiffResult(
                    path=periph_name,
                    diff_type='removed',
                    old_value=self._peripheral_summary(periph),
                    category='peripheral'
                ))
        
        # 处理修改的外设
        for mod_periph in analysis.get('modified_peripherals', []):
            periph_name = mod_periph.get('name', '')
            
            # 外设属性变化
            for prop in mod_periph.get('property_changes', []):
                self._diffs.append(SVDDiffResult(
                    path=f"{periph_name}/{prop.get('property', '')}",
                    diff_type='modified',
                    old_value=prop.get('old_value'),
                    new_value=prop.get('new_value'),
                    category='property'
                ))
            
            # 新增的寄存器
            for reg_name in mod_periph.get('added_registers', []):
                periph_b = self._find_peripheral(self.svd_b, periph_name)
                reg = self._find_register(periph_b, reg_name) if periph_b else None
                self._diffs.append(SVDDiffResult(
                    path=f"{periph_name}/{reg_name}",
                    diff_type='added',
                    new_value=self._register_summary(reg) if reg else '',
                    category='register'
                ))
            
            # 删除的寄存器
            for reg_name in mod_periph.get('removed_registers', []):
                periph_a = self._find_peripheral(self.svd_a, periph_name)
                reg = self._find_register(periph_a, reg_name) if periph_a else None
                self._diffs.append(SVDDiffResult(
                    path=f"{periph_name}/{reg_name}",
                    diff_type='removed',
                    old_value=self._register_summary(reg) if reg else '',
                    category='register'
                ))
            
            # 修改的寄存器
            for mod_reg in mod_periph.get('modified_registers', []):
                reg_name = mod_reg.get('name', '')
                
                # 寄存器属性变化
                for prop in mod_reg.get('property_changes', []):
                    self._diffs.append(SVDDiffResult(
                        path=f"{periph_name}/{reg_name}/{prop.get('property', '')}",
                        diff_type='modified',
                        old_value=prop.get('old_value'),
                        new_value=prop.get('new_value'),
                        category='property'
                    ))
                
                # 新增的字段
                for field_name in mod_reg.get('added_fields', []):
                    self._diffs.append(SVDDiffResult(
                        path=f"{periph_name}/{reg_name}/{field_name}",
                        diff_type='added',
                        category='field'
                    ))
                
                # 删除的字段
                for field_name in mod_reg.get('removed_fields', []):
                    self._diffs.append(SVDDiffResult(
                        path=f"{periph_name}/{reg_name}/{field_name}",
                        diff_type='removed',
                        category='field'
                    ))
                
                # 修改的字段
                for mod_field in mod_reg.get('modified_fields', []):
                    field_name = mod_field.get('name', '')
                    for prop in mod_field.get('property_changes', []):
                        self._diffs.append(SVDDiffResult(
                            path=f"{periph_name}/{reg_name}/{field_name}/{prop.get('property', '')}",
                            diff_type='modified',
                            old_value=prop.get('old_value'),
                            new_value=prop.get('new_value'),
                            category='property'
                        ))
    
    def _find_peripheral(self, svd_data, name):
        """在SVD数据中查找外设"""
        if not svd_data:
            return None
        peripherals = svd_data.get('peripherals', {}).get('peripheral', [])
        if isinstance(peripherals, dict):
            peripherals = [peripherals]
        for p in peripherals:
            if p.get('name') == name:
                return p
        return None
    
    def _find_register(self, peripheral, name):
        """在外设中查找寄存器"""
        if not peripheral:
            return None
        registers = peripheral.get('registers', {}).get('register', [])
        if isinstance(registers, dict):
            registers = [registers]
        for r in registers:
            if r.get('name') == name:
                return r
        return None
    
    def _peripheral_summary(self, periph):
        """生成外设摘要"""
        if not periph:
            return ''
        parts = [f"name={periph.get('name', '')}"]
        if 'baseAddress' in periph:
            parts.append(f"baseAddress={periph['baseAddress']}")
        return ', '.join(parts)
    
    def _register_summary(self, reg):
        """生成寄存器摘要"""
        if not reg:
            return ''
        parts = [f"name={reg.get('name', '')}"]
        if 'addressOffset' in reg:
            parts.append(f"offset={reg['addressOffset']}")
        return ', '.join(parts)
    
    def get_summary(self):
        """获取差异摘要（字典模式）"""
        diffs = self.compare()
        added = sum(1 for d in diffs if d.type == 'added')
        removed = sum(1 for d in diffs if d.type == 'removed')
        modified = sum(1 for d in diffs if d.type == 'modified')
        return {
            'total': len(diffs),
            'added': added,
            'removed': removed,
            'modified': modified
        }
    
    def get_analysis(self):
        """获取原始分析结果（来自SVDMerger）"""
        if self._merger:
            return self._merger.analyze()
        return {}
    
    def get_device_names(self):
        """获取两个SVD的设备名称"""
        name_a = self.svd_a.get('name', 'SVD A') if self.svd_a else 'SVD A'
        name_b = self.svd_b.get('name', 'SVD B') if self.svd_b else 'SVD B'
        # 尝试从device节点获取
        if isinstance(name_a, dict):
            name_a = name_a.get('#text', str(name_a))
        if isinstance(name_b, dict):
            name_b = name_b.get('#text', str(name_b))
        return str(name_a), str(name_b)
