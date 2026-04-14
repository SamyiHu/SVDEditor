"""
SVD 合并引擎
将源 SVD 文件的差异部分合并到目标 SVD 中，支持用户选择合并策略
"""
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

from .data_model import (
    DeviceInfo, Peripheral, Register, Field, Cluster, CPUInfo
)


class MergeAction(Enum):
    """合并动作"""
    KEEP_TARGET = "keep_target"       # 保留目标（当前文件）
    USE_SOURCE = "use_source"         # 使用源（导入文件）
    MERGE_BOTH = "merge_both"         # 合并两者（递归到下一层）


class MergeConflictLevel(Enum):
    """冲突级别"""
    NEW_IN_SOURCE = "new_in_source"       # 源文件新增（无冲突）
    ONLY_IN_TARGET = "only_in_target"     # 仅目标有（无冲突）
    ATTR_MODIFIED = "attr_modified"       # 属性修改（低冲突）
    STRUCTURE_CHANGED = "structure_changed"  # 结构变化（高冲突）


@dataclass
class MergeItem:
    """可合并项"""
    path: str                           # 层级路径
    level: str                          # 层级: device / peripheral / register / field / cluster / interrupt
    conflict_level: MergeConflictLevel  # 冲突级别
    action: MergeAction = MergeAction.KEEP_TARGET  # 用户选择的动作
    target_obj: Any = None              # 目标对象
    source_obj: Any = None              # 源对象
    children: List['MergeItem'] = field(default_factory=list)
    parent: Optional['MergeItem'] = None

    @property
    def is_conflict(self) -> bool:
        """是否存在冲突"""
        return self.conflict_level in (
            MergeConflictLevel.ATTR_MODIFIED,
            MergeConflictLevel.STRUCTURE_CHANGED,
        )

    @property
    def display_text(self) -> str:
        """显示文本"""
        if self.conflict_level == MergeConflictLevel.NEW_IN_SOURCE:
            return f"[新增] {self.path}"
        elif self.conflict_level == MergeConflictLevel.ONLY_IN_TARGET:
            return f"[仅当前] {self.path}"
        elif self.conflict_level == MergeConflictLevel.ATTR_MODIFIED:
            return f"[属性修改] {self.path}"
        elif self.conflict_level == MergeConflictLevel.STRUCTURE_CHANGED:
            return f"[结构变化] {self.path}"
        return self.path


class SVDMerger:
    """SVD 合并引擎"""

    def __init__(self):
        self.merge_items: List[MergeItem] = []
        self._target: Optional[DeviceInfo] = None
        self._source: Optional[DeviceInfo] = None

    def analyze(self, target: DeviceInfo, source: DeviceInfo) -> List[MergeItem]:
        """
        分析两个 DeviceInfo 的差异，生成合并项列表

        Args:
            target: 当前编辑的 SVD（目标）
            source: 要导入的 SVD（源）

        Returns:
            合并项列表
        """
        self._target = target
        self._source = source
        self.merge_items = []

        # 1. 设备级属性对比
        device_items = self._analyze_device_attrs(target, source)
        self.merge_items.extend(device_items)

        # 2. 外设级对比
        periph_items = self._analyze_peripherals(target, source)
        self.merge_items.extend(periph_items)

        return self.merge_items

    def _analyze_device_attrs(self, target: DeviceInfo, source: DeviceInfo) -> List[MergeItem]:
        """分析设备级属性差异"""
        items = []
        attrs = ['name', 'version', 'description', 'vendor', 'size', 'reset_value', 'reset_mask']

        for attr in attrs:
            target_val = getattr(target, attr, None)
            source_val = getattr(source, attr, None)
            if target_val != source_val and source_val is not None and source_val != '':
                item = MergeItem(
                    path=f"Device.{attr}",
                    level="device",
                    conflict_level=MergeConflictLevel.ATTR_MODIFIED,
                    target_obj=target_val,
                    source_obj=source_val,
                )
                # 如果目标值为空/默认，默认使用源
                if not target_val or target_val == '':
                    item.action = MergeAction.USE_SOURCE
                items.append(item)

        # CPU 对比
        if target.cpu and source.cpu:
            cpu_attrs = ['name', 'revision', 'endian', 'mpu_present', 'fpu_present',
                         'nvic_prio_bits', 'vendor_systick_config']
            cpu_changed = []
            for attr in cpu_attrs:
                t_val = getattr(target.cpu, attr, None)
                s_val = getattr(source.cpu, attr, None)
                if t_val != s_val:
                    cpu_changed.append(attr)
            if cpu_changed:
                item = MergeItem(
                    path="Device.CPU",
                    level="device",
                    conflict_level=MergeConflictLevel.ATTR_MODIFIED,
                    target_obj=target.cpu,
                    source_obj=source.cpu,
                )
                items.append(item)

        return items

    def _analyze_peripherals(self, target: DeviceInfo, source: DeviceInfo) -> List[MergeItem]:
        """分析外设级差异"""
        items = []
        target_periphs = target.peripherals
        source_periphs = source.peripherals
        all_names = set(list(target_periphs.keys()) + list(source_periphs.keys()))

        for name in sorted(all_names):
            t_p = target_periphs.get(name)
            s_p = source_periphs.get(name)

            if t_p is None and s_p is not None:
                # 源文件新增外设
                item = MergeItem(
                    path=name,
                    level="peripheral",
                    conflict_level=MergeConflictLevel.NEW_IN_SOURCE,
                    action=MergeAction.USE_SOURCE,  # 新增默认使用源
                    source_obj=s_p,
                )
                item.children = self._describe_peripheral_content(s_p)
                items.append(item)

            elif t_p is not None and s_p is None:
                # 仅目标有（源中删除了）
                item = MergeItem(
                    path=name,
                    level="peripheral",
                    conflict_level=MergeConflictLevel.ONLY_IN_TARGET,
                    action=MergeAction.KEEP_TARGET,  # 默认保留
                    target_obj=t_p,
                )
                items.append(item)

            else:
                # 两者都有，深入比较
                periph_item = self._analyze_peripheral_detail(name, t_p, s_p)
                if periph_item:
                    items.append(periph_item)

        return items

    def _analyze_peripheral_detail(self, name: str, target: Peripheral, source: Peripheral) -> Optional[MergeItem]:
        """深入比较单个外设"""
        children = []
        has_structure_change = False

        # 基本属性比较
        attr_map = {
            'base_address': 'BaseAddress',
            'description': 'Description',
            'group_name': 'GroupName',
            'display_name': 'DisplayName',
        }
        for attr, label in attr_map.items():
            t_val = getattr(target, attr, None)
            s_val = getattr(source, attr, None)
            if t_val != s_val:
                child = MergeItem(
                    path=f"{name}.{label}",
                    level="peripheral_attr",
                    conflict_level=MergeConflictLevel.ATTR_MODIFIED,
                    target_obj=t_val,
                    source_obj=s_val,
                )
                children.append(child)

        # 地址块比较
        if target.address_block != source.address_block:
            child = MergeItem(
                path=f"{name}.AddressBlock",
                level="peripheral_attr",
                conflict_level=MergeConflictLevel.ATTR_MODIFIED,
                target_obj=target.address_block,
                source_obj=source.address_block,
            )
            children.append(child)

        # 寄存器比较
        reg_items, reg_structure_changed = self._analyze_registers(name, target.registers, source.registers)
        children.extend(reg_items)
        if reg_structure_changed:
            has_structure_change = True

        # 簇比较
        cl_items, cl_structure_changed = self._analyze_clusters(name, target.clusters, source.clusters)
        children.extend(cl_items)
        if cl_structure_changed:
            has_structure_change = True

        # 中断比较
        irq_items = self._analyze_interrupts(name, target.interrupts, source.interrupts)
        children.extend(irq_items)

        if children:
            conflict_level = MergeConflictLevel.STRUCTURE_CHANGED if has_structure_change else MergeConflictLevel.ATTR_MODIFIED
            item = MergeItem(
                path=name,
                level="peripheral",
                conflict_level=conflict_level,
                action=MergeAction.MERGE_BOTH,
                target_obj=target,
                source_obj=source,
            )
            # 设置父子关系
            for child in children:
                child.parent = item
            item.children = children
            return item

        return None

    def _analyze_registers(self, parent_path: str,
                           target_regs: Dict[str, Register],
                           source_regs: Dict[str, Register]) -> Tuple[List[MergeItem], bool]:
        """分析寄存器差异"""
        items = []
        structure_changed = False
        all_names = set(list(target_regs.keys()) + list(source_regs.keys()))

        for name in sorted(all_names):
            t_r = target_regs.get(name)
            s_r = source_regs.get(name)
            path = f"{parent_path}.{name}"

            if t_r is None and s_r is not None:
                structure_changed = True
                item = MergeItem(
                    path=path,
                    level="register",
                    conflict_level=MergeConflictLevel.NEW_IN_SOURCE,
                    action=MergeAction.USE_SOURCE,
                    source_obj=s_r,
                )
                items.append(item)

            elif t_r is not None and s_r is None:
                structure_changed = True
                item = MergeItem(
                    path=path,
                    level="register",
                    conflict_level=MergeConflictLevel.ONLY_IN_TARGET,
                    action=MergeAction.KEEP_TARGET,
                    target_obj=t_r,
                )
                items.append(item)

            else:
                reg_item = self._analyze_register_detail(path, t_r, s_r)
                if reg_item:
                    items.append(reg_item)

        return items, structure_changed

    def _analyze_register_detail(self, path: str, target: Register, source: Register) -> Optional[MergeItem]:
        """深入比较单个寄存器"""
        children = []
        has_structure_change = False

        attr_map = {
            'offset': 'Offset',
            'size': 'Size',
            'access': 'Access',
            'reset_value': 'ResetValue',
            'reset_mask': 'ResetMask',
            'description': 'Description',
            'display_name': 'DisplayName',
        }
        for attr, label in attr_map.items():
            t_val = getattr(target, attr, None)
            s_val = getattr(source, attr, None)
            if t_val != s_val:
                child = MergeItem(
                    path=f"{path}.{label}",
                    level="register_attr",
                    conflict_level=MergeConflictLevel.ATTR_MODIFIED,
                    target_obj=t_val,
                    source_obj=s_val,
                )
                children.append(child)

        # 位域比较
        all_field_names = set(list(target.fields.keys()) + list(source.fields.keys()))
        for fname in sorted(all_field_names):
            t_f = target.fields.get(fname)
            s_f = source.fields.get(fname)
            fpath = f"{path}.{fname}"

            if t_f is None and s_f is not None:
                has_structure_change = True
                child = MergeItem(
                    path=fpath,
                    level="field",
                    conflict_level=MergeConflictLevel.NEW_IN_SOURCE,
                    action=MergeAction.USE_SOURCE,
                    source_obj=s_f,
                )
                children.append(child)
            elif t_f is not None and s_f is None:
                has_structure_change = True
                child = MergeItem(
                    path=fpath,
                    level="field",
                    conflict_level=MergeConflictLevel.ONLY_IN_TARGET,
                    action=MergeAction.KEEP_TARGET,
                    target_obj=t_f,
                )
                children.append(child)
            else:
                # 位域属性比较
                field_children = []
                for attr, label in [('bit_offset', 'BitOffset'), ('bit_width', 'BitWidth'),
                                     ('access', 'Access'), ('description', 'Description')]:
                    t_val = getattr(t_f, attr, None)
                    s_val = getattr(s_f, attr, None)
                    if t_val != s_val:
                        field_children.append(MergeItem(
                            path=f"{fpath}.{label}",
                            level="field_attr",
                            conflict_level=MergeConflictLevel.ATTR_MODIFIED,
                            target_obj=t_val,
                            source_obj=s_val,
                        ))
                # 枚举值比较
                if t_f.enumerated_values != s_f.enumerated_values:
                    field_children.append(MergeItem(
                        path=f"{fpath}.EnumValues",
                        level="field_attr",
                        conflict_level=MergeConflictLevel.ATTR_MODIFIED,
                        target_obj=t_f.enumerated_values,
                        source_obj=s_f.enumerated_values,
                    ))
                if field_children:
                    child = MergeItem(
                        path=fpath,
                        level="field",
                        conflict_level=MergeConflictLevel.ATTR_MODIFIED,
                        action=MergeAction.MERGE_BOTH,
                        target_obj=t_f,
                        source_obj=s_f,
                    )
                    for fc in field_children:
                        fc.parent = child
                    child.children = field_children
                    children.append(child)

        if children:
            conflict = MergeConflictLevel.STRUCTURE_CHANGED if has_structure_change else MergeConflictLevel.ATTR_MODIFIED
            item = MergeItem(
                path=path,
                level="register",
                conflict_level=conflict,
                action=MergeAction.MERGE_BOTH,
                target_obj=target,
                source_obj=source,
            )
            for child in children:
                child.parent = item
            item.children = children
            return item

        return None

    def _analyze_clusters(self, parent_path: str,
                          target_clusters: Dict[str, Cluster],
                          source_clusters: Dict[str, Cluster]) -> Tuple[List[MergeItem], bool]:
        """分析簇差异"""
        items = []
        structure_changed = False
        all_names = set(list(target_clusters.keys()) + list(source_clusters.keys()))

        for name in sorted(all_names):
            t_c = target_clusters.get(name)
            s_c = source_clusters.get(name)
            path = f"{parent_path}.{name}"

            if t_c is None and s_c is not None:
                structure_changed = True
                item = MergeItem(
                    path=path,
                    level="cluster",
                    conflict_level=MergeConflictLevel.NEW_IN_SOURCE,
                    action=MergeAction.USE_SOURCE,
                    source_obj=s_c,
                )
                items.append(item)
            elif t_c is not None and s_c is None:
                structure_changed = True
                item = MergeItem(
                    path=path,
                    level="cluster",
                    conflict_level=MergeConflictLevel.ONLY_IN_TARGET,
                    action=MergeAction.KEEP_TARGET,
                    target_obj=t_c,
                )
                items.append(item)
            else:
                # 簇属性+嵌套寄存器比较
                cl_children = []
                for attr, label in [('address_offset', 'Offset'), ('size', 'Size'),
                                     ('access', 'Access'), ('dim', 'Dim')]:
                    t_val = getattr(t_c, attr, None)
                    s_val = getattr(s_c, attr, None)
                    if t_val != s_val:
                        cl_children.append(MergeItem(
                            path=f"{path}.{label}",
                            level="cluster_attr",
                            conflict_level=MergeConflictLevel.ATTR_MODIFIED,
                            target_obj=t_val,
                            source_obj=s_val,
                        ))
                # 嵌套寄存器比较
                reg_items, reg_sc = self._analyze_registers(path, t_c.registers, s_c.registers)
                cl_children.extend(reg_items)
                if reg_sc:
                    structure_changed = True

                if cl_children:
                    item = MergeItem(
                        path=path,
                        level="cluster",
                        conflict_level=MergeConflictLevel.STRUCTURE_CHANGED if reg_sc else MergeConflictLevel.ATTR_MODIFIED,
                        action=MergeAction.MERGE_BOTH,
                        target_obj=t_c,
                        source_obj=s_c,
                    )
                    for child in cl_children:
                        child.parent = item
                    item.children = cl_children
                    items.append(item)

        return items, structure_changed

    def _analyze_interrupts(self, parent_path: str,
                            target_irqs: List[dict], source_irqs: List[dict]) -> List[MergeItem]:
        """分析中断差异"""
        items = []
        t_map = {irq['name']: irq for irq in target_irqs}
        s_map = {irq['name']: irq for irq in source_irqs}
        all_names = set(list(t_map.keys()) + list(s_map.keys()))

        for name in sorted(all_names):
            t_i = t_map.get(name)
            s_i = s_map.get(name)
            path = f"{parent_path}.IRQ.{name}"

            if t_i is None and s_i is not None:
                items.append(MergeItem(
                    path=path,
                    level="interrupt",
                    conflict_level=MergeConflictLevel.NEW_IN_SOURCE,
                    action=MergeAction.USE_SOURCE,
                    source_obj=s_i,
                ))
            elif t_i is not None and s_i is None:
                items.append(MergeItem(
                    path=path,
                    level="interrupt",
                    conflict_level=MergeConflictLevel.ONLY_IN_TARGET,
                    action=MergeAction.KEEP_TARGET,
                    target_obj=t_i,
                ))
            else:
                # 比较中断属性
                irq_children = []
                for key in ['value', 'description']:
                    if t_i.get(key) != s_i.get(key):
                        irq_children.append(MergeItem(
                            path=f"{path}.{key}",
                            level="interrupt_attr",
                            conflict_level=MergeConflictLevel.ATTR_MODIFIED,
                            target_obj=t_i.get(key),
                            source_obj=s_i.get(key),
                        ))
                if irq_children:
                    item = MergeItem(
                        path=path,
                        level="interrupt",
                        conflict_level=MergeConflictLevel.ATTR_MODIFIED,
                        action=MergeAction.MERGE_BOTH,
                        target_obj=t_i,
                        source_obj=s_i,
                    )
                    for child in irq_children:
                        child.parent = item
                    item.children = irq_children
                    items.append(item)

        return items

    def _describe_peripheral_content(self, p: Peripheral) -> List[MergeItem]:
        """生成外设内容描述（新增外设的子项）"""
        items = []
        items.append(MergeItem(
            path=f"{p.name}.BaseAddress",
            level="peripheral_attr",
            conflict_level=MergeConflictLevel.NEW_IN_SOURCE,
            action=MergeAction.USE_SOURCE,
            source_obj=p.base_address,
        ))
        for reg_name in sorted(p.registers.keys()):
            reg = p.registers[reg_name]
            items.append(MergeItem(
                path=f"{p.name}.{reg_name}",
                level="register",
                conflict_level=MergeConflictLevel.NEW_IN_SOURCE,
                action=MergeAction.USE_SOURCE,
                source_obj=reg,
            ))
        for cl_name in sorted(p.clusters.keys()):
            items.append(MergeItem(
                path=f"{p.name}.{cl_name}",
                level="cluster",
                conflict_level=MergeConflictLevel.NEW_IN_SOURCE,
                action=MergeAction.USE_SOURCE,
                source_obj=p.clusters[cl_name],
            ))
        for irq in p.interrupts:
            items.append(MergeItem(
                path=f"{p.name}.IRQ.{irq['name']}",
                level="interrupt",
                conflict_level=MergeConflictLevel.NEW_IN_SOURCE,
                action=MergeAction.USE_SOURCE,
                source_obj=irq,
            ))
        return items

    def execute_merge(self, target: DeviceInfo, merge_items: List[MergeItem]) -> Tuple[DeviceInfo, Dict[str, int]]:
        """
        执行合并操作

        Args:
            target: 目标 DeviceInfo
            merge_items: 合并项列表（包含用户选择）

        Returns:
            (合并后的 DeviceInfo, 统计信息)
        """
        result = deepcopy(target)
        stats = {
            "peripherals_added": 0,
            "registers_added": 0,
            "fields_added": 0,
            "clusters_added": 0,
            "interrupts_added": 0,
            "attrs_updated": 0,
            "skipped": 0,
        }

        for item in merge_items:
            self._apply_merge_item(result, item, stats)

        return result, stats

    def _apply_merge_item(self, target: DeviceInfo, item: MergeItem, stats: Dict[str, int]):
        """应用单个合并项"""
        if item.action == MergeAction.KEEP_TARGET:
            stats["skipped"] += 1
            # 递归处理子项（用户可能在子级选择了不同策略）
            for child in item.children:
                self._apply_merge_item(target, child, stats)
            return

        if item.level == "device":
            # 设备级属性合并
            attr_name = item.path.split('.')[-1]
            if hasattr(target, attr_name) and item.action == MergeAction.USE_SOURCE:
                setattr(target, attr_name, item.source_obj)
                stats["attrs_updated"] += 1
            elif item.path == "Device.CPU" and item.action == MergeAction.USE_SOURCE:
                if isinstance(item.source_obj, CPUInfo):
                    target.cpu = deepcopy(item.source_obj)
                    stats["attrs_updated"] += 1

        elif item.level == "peripheral":
            if item.conflict_level == MergeConflictLevel.NEW_IN_SOURCE and item.action == MergeAction.USE_SOURCE:
                # 新增外设
                if isinstance(item.source_obj, Peripheral):
                    periph = deepcopy(item.source_obj)
                    periph.derived_from = ""  # 清除继承关系
                    target.peripherals[periph.name] = periph
                    stats["peripherals_added"] += 1
            elif item.conflict_level == MergeConflictLevel.ONLY_IN_TARGET:
                pass  # 仅目标有，默认保留
            elif item.action == MergeAction.USE_SOURCE:
                # 完全替换外设
                if isinstance(item.source_obj, Peripheral):
                    periph = deepcopy(item.source_obj)
                    periph.derived_from = ""
                    target.peripherals[item.path] = periph
                    stats["peripherals_added"] += 1
            elif item.action == MergeAction.MERGE_BOTH:
                # 递归处理子项
                periph_name = item.path
                if periph_name in target.peripherals:
                    for child in item.children:
                        self._apply_peripheral_child_merge(
                            target.peripherals[periph_name], child, stats)

    def _apply_peripheral_child_merge(self, periph: Peripheral, item: MergeItem, stats: Dict[str, int]):
        """应用外设内部的合并项"""
        if item.action == MergeAction.KEEP_TARGET:
            stats["skipped"] += 1
            for child in item.children:
                self._apply_peripheral_child_merge(periph, child, stats)
            return

        if item.level == "peripheral_attr":
            attr_map = {
                'BaseAddress': 'base_address',
                'Description': 'description',
                'GroupName': 'group_name',
                'DisplayName': 'display_name',
            }
            label = item.path.split('.')[-1]
            attr_name = attr_map.get(label)
            if attr_name and item.action == MergeAction.USE_SOURCE:
                setattr(periph, attr_name, item.source_obj)
                stats["attrs_updated"] += 1
            elif label == "AddressBlock" and item.action == MergeAction.USE_SOURCE:
                periph.address_block = deepcopy(item.source_obj)
                stats["attrs_updated"] += 1

        elif item.level == "register":
            if item.conflict_level == MergeConflictLevel.NEW_IN_SOURCE and item.action == MergeAction.USE_SOURCE:
                if isinstance(item.source_obj, Register):
                    periph.registers[item.source_obj.name] = deepcopy(item.source_obj)
                    stats["registers_added"] += 1
            elif item.action == MergeAction.USE_SOURCE:
                name = item.path.split('.')[-1]
                if isinstance(item.source_obj, Register):
                    periph.registers[name] = deepcopy(item.source_obj)
                    stats["registers_added"] += 1
            elif item.action == MergeAction.MERGE_BOTH:
                reg_name = item.path.split('.')[-1]
                if reg_name in periph.registers:
                    for child in item.children:
                        self._apply_register_child_merge(
                            periph.registers[reg_name], child, stats)

        elif item.level == "cluster":
            if item.conflict_level == MergeConflictLevel.NEW_IN_SOURCE and item.action == MergeAction.USE_SOURCE:
                if isinstance(item.source_obj, Cluster):
                    periph.clusters[item.source_obj.name] = deepcopy(item.source_obj)
                    stats["clusters_added"] += 1

        elif item.level == "interrupt":
            if item.action == MergeAction.USE_SOURCE:
                if isinstance(item.source_obj, dict):
                    existing_names = [irq['name'] for irq in periph.interrupts]
                    if item.source_obj['name'] not in existing_names:
                        periph.interrupts.append(deepcopy(item.source_obj))
                        stats["interrupts_added"] += 1

    def _apply_register_child_merge(self, reg: Register, item: MergeItem, stats: Dict[str, int]):
        """应用寄存器内部的合并项"""
        if item.action == MergeAction.KEEP_TARGET:
            stats["skipped"] += 1
            for child in item.children:
                self._apply_register_child_merge(reg, child, stats)
            return

        if item.level == "register_attr":
            attr_map = {
                'Offset': 'offset',
                'Size': 'size',
                'Access': 'access',
                'ResetValue': 'reset_value',
                'ResetMask': 'reset_mask',
                'Description': 'description',
                'DisplayName': 'display_name',
            }
            label = item.path.split('.')[-1]
            attr_name = attr_map.get(label)
            if attr_name and item.action == MergeAction.USE_SOURCE:
                setattr(reg, attr_name, item.source_obj)
                stats["attrs_updated"] += 1

        elif item.level == "field":
            if item.conflict_level == MergeConflictLevel.NEW_IN_SOURCE and item.action == MergeAction.USE_SOURCE:
                if isinstance(item.source_obj, Field):
                    reg.fields[item.source_obj.name] = deepcopy(item.source_obj)
                    stats["fields_added"] += 1
            elif item.action == MergeAction.USE_SOURCE:
                name = item.path.split('.')[-1]
                if isinstance(item.source_obj, Field):
                    reg.fields[name] = deepcopy(item.source_obj)
                    stats["fields_added"] += 1
            elif item.action == MergeAction.MERGE_BOTH:
                field_name = item.path.split('.')[-1]
                if field_name in reg.fields:
                    for child in item.children:
                        if child.action == MergeAction.USE_SOURCE:
                            f_attr_map = {
                                'BitOffset': 'bit_offset',
                                'BitWidth': 'bit_width',
                                'Access': 'access',
                                'Description': 'description',
                            }
                            label = child.path.split('.')[-1]
                            if label == "EnumValues":
                                reg.fields[field_name].enumerated_values = deepcopy(child.source_obj)
                                stats["attrs_updated"] += 1
                            else:
                                attr_name = f_attr_map.get(label)
                                if attr_name:
                                    setattr(reg.fields[field_name], attr_name, child.source_obj)
                                    stats["attrs_updated"] += 1

    def generate_summary(self, merge_items: List[MergeItem], stats: Dict[str, int]) -> str:
        """生成合并摘要"""
        lines = [
            "=== SVD 合并结果 ===",
            "",
            f"  新增外设:   {stats.get('peripherals_added', 0)}",
            f"  新增寄存器: {stats.get('registers_added', 0)}",
            f"  新增位域:   {stats.get('fields_added', 0)}",
            f"  新增簇:     {stats.get('clusters_added', 0)}",
            f"  新增中断:   {stats.get('interrupts_added', 0)}",
            f"  属性更新:   {stats.get('attrs_updated', 0)}",
            f"  跳过(保留): {stats.get('skipped', 0)}",
            "",
        ]
        return "\n".join(lines)

    @staticmethod
    def count_items(merge_items: List[MergeItem]) -> Dict[str, int]:
        """统计合并项"""
        counts = {
            "new_in_source": 0,
            "only_in_target": 0,
            "attr_modified": 0,
            "structure_changed": 0,
            "total": 0,
            "use_source": 0,
            "keep_target": 0,
        }

        def _count_recursive(items: List[MergeItem]):
            for item in items:
                counts["total"] += 1
                if item.conflict_level == MergeConflictLevel.NEW_IN_SOURCE:
                    counts["new_in_source"] += 1
                elif item.conflict_level == MergeConflictLevel.ONLY_IN_TARGET:
                    counts["only_in_target"] += 1
                elif item.conflict_level == MergeConflictLevel.ATTR_MODIFIED:
                    counts["attr_modified"] += 1
                elif item.conflict_level == MergeConflictLevel.STRUCTURE_CHANGED:
                    counts["structure_changed"] += 1

                if item.action == MergeAction.USE_SOURCE:
                    counts["use_source"] += 1
                elif item.action == MergeAction.KEEP_TARGET:
                    counts["keep_target"] += 1

                if item.children:
                    _count_recursive(item.children)

        _count_recursive(merge_items)
        return counts