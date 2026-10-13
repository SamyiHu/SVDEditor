"""Headless 多文档工作区 — MCP Server 的文件级操作核心。

不依赖 PyQt，只复用 svd_tool.core：
- 编辑只进内存，save_document 才落盘（覆盖前自动生成 .bak 备份）
- 操作语义与 GUI 命令执行器（ui/managers/command_executor.py）保持一致，
  包括改名时的 dict-key 顺序保持迁移、derivedFrom 自引用校验等

返回约定与 GUI 命令执行器相同：{"success": bool, "message": str, "data": any}
"""
from __future__ import annotations

import copy
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.address_conflict_detector import AddressConflictDetector
from ..core.data_model import DeviceInfo, Field, Interrupt, Peripheral, Register
from ..core.header_generator import HeaderGenerator
from ..core.svd_differ import SVDDiffer
from ..core.svd_exporter import SVDExporter
from ..core.svd_generator import SVDGenerator
from ..core.svd_parser import SVDParser
from ..core.svd_schema_validator import SVDSchemaValidator

logger = logging.getLogger("svd_tool.mcp_server.workspace")


def _ok(message: str, data: Any = None) -> Dict[str, Any]:
    return {"success": True, "message": message, "data": data}


def _fail(message: str, data: Any = None) -> Dict[str, Any]:
    return {"success": False, "message": message, "data": data}


@dataclass
class _DocEntry:
    doc_id: str
    device: DeviceInfo
    path: Optional[Path] = None
    modified: bool = False


class HeadlessWorkspace:
    """内存多文档工作区：doc_id → DeviceInfo。

    doc_id 默认取文件名去扩展名；重名时自动加 -2/-3 后缀。
    未显式指定 doc_id 的操作都作用于"活跃文档"（最近打开/切换的）。
    """

    def __init__(self) -> None:
        self._docs: Dict[str, _DocEntry] = {}
        self._active: Optional[str] = None

    # ==================== 内部工具 ====================

    def _resolve(self, doc_id: Optional[str] = None) -> _DocEntry:
        """解析目标文档：显式 doc_id 优先，否则用活跃文档。"""
        if doc_id:
            if doc_id not in self._docs:
                raise KeyError(f"文档 '{doc_id}' 不存在。可用: {', '.join(self._docs) or '无'}")
            return self._docs[doc_id]
        if self._active is None:
            raise RuntimeError("当前没有打开的文档，请先调用 svd_open")
        return self._docs[self._active]

    def _try(self, fn) -> Dict[str, Any]:
        """统一异常包装，保证工具永不抛出。"""
        try:
            return fn()
        except (KeyError, RuntimeError, ValueError) as e:
            return _fail(str(e))
        except Exception as e:  # noqa: BLE001
            logger.exception("工作区操作失败")
            return _fail(f"操作失败: {e}")

    def _unique_doc_id(self, base: str) -> str:
        if base not in self._docs:
            return base
        n = 2
        while f"{base}-{n}" in self._docs:
            n += 1
        return f"{base}-{n}"

    # ==================== 文档管理 ====================

    def open_document(self, path: str, doc_id: Optional[str] = None) -> Dict[str, Any]:
        def _run() -> Dict[str, Any]:
            p = Path(path)
            if not p.is_absolute():
                p = Path.cwd() / p
            if not p.is_file():
                return _fail(f"文件不存在: {p}")

            parser = SVDParser()
            device = parser.parse_file(str(p))
            if device is None:
                return _fail(f"解析失败（格式不合法或不是 CMSIS-SVD 文件）: {p}")

            base_id = doc_id or p.stem
            final_id = self._unique_doc_id(base_id)
            self._docs[final_id] = _DocEntry(doc_id=final_id, device=device, path=p)
            self._active = final_id

            stats = self._stats(device)
            return _ok(
                f"已打开 {p.name} (doc_id: {final_id})："
                f"{stats['peripherals']} 外设 / {stats['registers']} 寄存器 / {stats['fields']} 位域",
                {"doc_id": final_id, "file": str(p), "device": device.name, "statistics": stats,
                 "warnings": parser.get_warnings()[:20]},
            )

        return self._try(_run)

    def list_documents(self) -> Dict[str, Any]:
        def _run() -> Dict[str, Any]:
            docs = [
                {
                    "doc_id": e.doc_id,
                    "device": e.device.name,
                    "file": str(e.path) if e.path else "(未保存)",
                    "modified": e.modified,
                    "active": e.doc_id == self._active,
                }
                for e in self._docs.values()
            ]
            return _ok(f"共 {len(docs)} 个文档", docs)

        return self._try(_run)

    def switch_document(self, doc_id: str) -> Dict[str, Any]:
        def _run() -> Dict[str, Any]:
            entry = self._resolve(doc_id)
            self._active = entry.doc_id
            return _ok(f"已切换到 '{entry.doc_id}'", {"doc_id": entry.doc_id, "device": entry.device.name})

        return self._try(_run)

    def close_document(self, doc_id: Optional[str] = None) -> Dict[str, Any]:
        def _run() -> Dict[str, Any]:
            entry = self._resolve(doc_id)
            warning = ""
            if entry.modified:
                warning = "（注意：该文档有未保存的修改，已丢弃）"
            del self._docs[entry.doc_id]
            if self._active == entry.doc_id:
                self._active = next(reversed(list(self._docs)), None)
            return _ok(f"已关闭 '{entry.doc_id}'{warning}")

        return self._try(_run)

    def save_document(self, doc_id: Optional[str] = None, path: Optional[str] = None) -> Dict[str, Any]:
        def _run() -> Dict[str, Any]:
            entry = self._resolve(doc_id)
            target = Path(path) if path else entry.path
            if target is None:
                return _fail("该文档没有关联文件，请指定 path（如 xxx.svd）")
            if not target.is_absolute():
                target = Path.cwd() / target

            backup = ""
            if target.is_file():
                bak = target.with_suffix(target.suffix + ".bak")
                copy_of = target.read_bytes()
                bak.write_bytes(copy_of)
                backup = f"，原文件已备份到 {bak.name}"

            xml = SVDGenerator(entry.device).generate(pretty_print=True)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(xml, encoding="utf-8")

            entry.path = target
            entry.modified = False
            return _ok(f"已保存到 {target}{backup}", {"doc_id": entry.doc_id, "file": str(target)})

        return self._try(_run)

    def regenerate_xml(self, doc_id: Optional[str] = None) -> Dict[str, Any]:
        def _run() -> Dict[str, Any]:
            entry = self._resolve(doc_id)
            xml = SVDGenerator(entry.device).generate(pretty_print=True)
            return _ok(f"标准化 XML 已生成（{len(xml)} 字符）", {"doc_id": entry.doc_id, "xml": xml})

        return self._try(_run)

    # ==================== 查询 ====================

    @staticmethod
    def _stats(device: DeviceInfo) -> Dict[str, int]:
        return {
            "peripherals": len(device.peripherals),
            "registers": sum(len(p.registers) for p in device.peripherals.values()),
            "fields": sum(
                len(r.fields) for p in device.peripherals.values() for r in p.registers.values()
            ),
            "interrupts": len(device.interrupts),
        }

    def device_info(self, doc_id: Optional[str] = None) -> Dict[str, Any]:
        def _run() -> Dict[str, Any]:
            entry = self._resolve(doc_id)
            d = entry.device
            data = {
                "doc_id": entry.doc_id,
                "device": {
                    "name": d.name, "version": d.version, "vendor": d.vendor,
                    "description": d.description, "cpu": d.cpu.name, "size": d.size,
                    "svd_version": d.svd_version,
                },
                "statistics": self._stats(d),
                "peripherals": [
                    {"name": n, "base_address": p.base_address,
                     "derived_from": p.derived_from or None,
                     "registers": len(p.registers)}
                    for n, p in d.peripherals.items()
                ],
            }
            return _ok(
                f"{d.name or '(未命名设备)'}：{data['statistics']['peripherals']} 外设 / "
                f"{data['statistics']['registers']} 寄存器", data)

        return self._try(_run)

    def search(self, keyword: str, search_type: str = "all",
               limit: int = 50, offset: int = 0, doc_id: Optional[str] = None) -> Dict[str, Any]:
        def _run() -> Dict[str, Any]:
            entry = self._resolve(doc_id)
            device = entry.device
            if not keyword:
                return _fail("搜索关键词不能为空")

            page_limit = max(1, min(int(limit), 200))
            page_offset = max(0, int(offset))
            kw = keyword.lower()
            results: List[Dict[str, Any]] = []

            if search_type in ("all", "peripheral"):
                for name, periph in device.peripherals.items():
                    if kw in name.lower():
                        item = {"type": "peripheral", "name": name}
                        if periph.derived_from:
                            item["derived_from"] = periph.derived_from
                        results.append(item)

            if search_type in ("all", "register"):
                for pname, periph in device.peripherals.items():
                    for rname in periph.registers:
                        if kw in rname.lower():
                            results.append({"type": "register", "name": rname, "peripheral": pname})

            if search_type in ("all", "field"):
                for pname, periph in device.peripherals.items():
                    for rname, reg in periph.registers.items():
                        for fname in reg.fields:
                            if kw in fname.lower():
                                results.append(
                                    {"type": "field", "name": fname, "peripheral": pname, "register": rname})

            total = len(results)
            return _ok(
                f"关键词 '{keyword}' 共匹配 {total} 项",
                {"results": results[page_offset:page_offset + page_limit], "total": total,
                 "offset": page_offset, "limit": page_limit,
                 "has_more": page_offset + page_limit < total},
            )

        return self._try(_run)

    def get_peripheral(self, name: str, doc_id: Optional[str] = None) -> Dict[str, Any]:
        def _run() -> Dict[str, Any]:
            device = self._resolve(doc_id).device
            pname = name.strip()
            if pname not in device.peripherals:
                return _fail(f"外设 '{pname}' 不存在")
            periph = device.peripherals[pname]

            reg_list = [
                {"name": rname, "offset": reg.offset, "size": reg.size,
                 "access": reg.access or "", "reset_value": reg.reset_value,
                 "description": reg.description, "from_cluster": ""}
                for rname, reg in periph.registers.items()
            ]
            for cname, cluster in periph.clusters.items():
                for rname, reg in cluster.all_registers().items():
                    reg_list.append(
                        {"name": rname, "offset": reg.offset, "size": reg.size,
                         "access": reg.access or "", "reset_value": reg.reset_value,
                         "description": reg.description, "from_cluster": cname})

            return _ok(
                f"外设 '{pname}' 共 {len(reg_list)} 个寄存器",
                {"name": periph.name, "base_address": periph.base_address,
                 "description": periph.description, "group_name": periph.group_name,
                 "derived_from": periph.derived_from or "",
                 "register_count": len(reg_list), "registers": reg_list},
            )

        return self._try(_run)

    def get_register(self, peripheral: str, register: str, doc_id: Optional[str] = None) -> Dict[str, Any]:
        def _run() -> Dict[str, Any]:
            device = self._resolve(doc_id).device
            periph_name = peripheral.strip()
            reg_name = (register or "").strip()
            if periph_name not in device.peripherals:
                return _fail(f"外设 '{periph_name}' 不存在")
            periph = device.peripherals[periph_name]

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
                return _fail(f"寄存器 '{reg_name}' 不存在（外设 {periph_name}）")

            field_list = [
                {"name": fname, "bit_offset": fld.bit_offset, "bit_width": fld.bit_width,
                 "access": fld.access or "", "reset_value": fld.reset_value,
                 "description": fld.description}
                for fname, fld in reg.fields.items()
            ]
            return _ok(
                f"{periph_name}.{reg_name} 共 {len(field_list)} 个位域",
                {"peripheral": periph_name, "name": reg.name, "offset": reg.offset,
                 "size": reg.size, "access": reg.access or "",
                 "reset_value": reg.reset_value, "reset_mask": getattr(reg, "reset_mask", ""),
                 "description": reg.description,
                 "derived_from": getattr(reg, "derived_from", "") or "",
                 "dim": reg.dim, "from_cluster": cluster_source,
                 "field_count": len(field_list), "fields": field_list},
            )

        return self._try(_run)

    def get_field(self, peripheral: str, register: str, field: str, doc_id: Optional[str] = None) -> Dict[str, Any]:
        def _run() -> Dict[str, Any]:
            device = self._resolve(doc_id).device
            periph_name = peripheral.strip()
            reg_name = register.strip()
            field_name = field.strip()
            if periph_name not in device.peripherals:
                return _fail(f"外设 '{periph_name}' 不存在")
            periph = device.peripherals[periph_name]
            reg = periph.registers.get(reg_name)
            if reg is None:
                for cluster in periph.clusters.values():
                    regs = cluster.all_registers()
                    if reg_name in regs:
                        reg = regs[reg_name]
                        break
            if reg is None:
                return _fail(f"寄存器 '{reg_name}' 不存在")
            if field_name not in reg.fields:
                return _fail(f"位域 '{field_name}' 不存在（{periph_name}.{reg_name}）")

            fld = reg.fields[field_name]
            return _ok(
                f"{periph_name}.{reg_name}.{field_name}",
                {"peripheral": periph_name, "register": reg_name, "name": fld.name,
                 "bit_offset": fld.bit_offset, "bit_width": fld.bit_width,
                 "access": fld.access or "", "reset_value": fld.reset_value,
                 "description": fld.description, "display_name": fld.display_name,
                 "enumerated_values": fld.enumerated_values},
            )

        return self._try(_run)

    def list_interrupts(self, doc_id: Optional[str] = None) -> Dict[str, Any]:
        def _run() -> Dict[str, Any]:
            device = self._resolve(doc_id).device
            irq_list = [
                {"name": name, "value": irq.value, "description": irq.description,
                 "peripheral": irq.peripheral, "peripherals": irq.peripherals}
                for name, irq in device.interrupts.items()
            ]
            return _ok(f"共 {len(irq_list)} 个中断", {"total": len(irq_list), "interrupts": irq_list})

        return self._try(_run)

    # ==================== 编辑：设备 ====================

    def update_device(self, updates: Dict[str, Any], doc_id: Optional[str] = None) -> Dict[str, Any]:
        def _run() -> Dict[str, Any]:
            entry = self._resolve(doc_id)
            device = entry.device
            if not updates:
                return _fail("没有要更新的字段")
            updatable = {"name", "version", "vendor", "description", "author",
                         "license", "copyright", "svd_version"}
            applied = [k for k in updates if k in updatable]
            if not applied:
                return _fail(f"无可更新字段，支持: {', '.join(sorted(updatable))}")
            for key in applied:
                setattr(device, key, updates[key])
            entry.modified = True
            return _ok(f"已更新设备属性: {', '.join(applied)}", {"updates": applied})

        return self._try(_run)

    # ==================== 编辑：外设 ====================

    def add_peripheral(self, name: str, base_address: str = "0x40000000",
                       description: str = "", group_name: str = "",
                       doc_id: Optional[str] = None) -> Dict[str, Any]:
        def _run() -> Dict[str, Any]:
            entry = self._resolve(doc_id)
            device = entry.device
            p_name = name.strip()
            if not p_name:
                return _fail("外设名不能为空")
            if p_name in device.peripherals:
                return _fail(f"外设 '{p_name}' 已存在")
            device.peripherals[p_name] = Peripheral(
                name=p_name, base_address=base_address,
                description=description, group_name=group_name)
            entry.modified = True
            return _ok(f"已添加外设 '{p_name}' (base={base_address})", {"name": p_name})

        return self._try(_run)

    def update_peripheral(self, name: str, updates: Dict[str, Any],
                          doc_id: Optional[str] = None) -> Dict[str, Any]:
        def _run() -> Dict[str, Any]:
            entry = self._resolve(doc_id)
            device = entry.device
            p_name = name.strip()
            if p_name not in device.peripherals:
                return _fail(f"外设 '{p_name}' 不存在")
            if not updates:
                return _fail("没有要更新的字段")
            periph = device.peripherals[p_name]

            # 改名：迁移 dict key 并保持顺序（与 GUI 行为一致）
            new_name = str(updates.get("name", "")).strip()
            renamed = False
            if new_name and new_name != p_name:
                if new_name in device.peripherals:
                    return _fail(f"外设 '{new_name}' 已存在")
                device.peripherals = {
                    (new_name if k == p_name else k): v for k, v in device.peripherals.items()
                }
                periph.name = new_name
                renamed = True
            effective = new_name if renamed else p_name

            # derivedFrom 校验
            if "derived_from" in updates:
                df = str(updates["derived_from"]).strip()
                if df == effective:
                    return _fail("外设不能继承自己")
                if df and df not in device.peripherals:
                    return _fail(f"派生目标外设 '{df}' 不存在")

            for key in ("description", "base_address", "group_name", "display_name", "derived_from"):
                if key in updates:
                    setattr(periph, key, updates[key])
            entry.modified = True
            return _ok(f"已更新外设 '{effective}'",
                       {"name": effective, "renamed": renamed,
                        "updates": [k for k in updates if k != "name"]})

        return self._try(_run)

    def remove_peripheral(self, name: str, doc_id: Optional[str] = None) -> Dict[str, Any]:
        def _run() -> Dict[str, Any]:
            entry = self._resolve(doc_id)
            device = entry.device
            p_name = name.strip()
            if p_name not in device.peripherals:
                return _fail(f"外设 '{p_name}' 不存在")
            del device.peripherals[p_name]
            entry.modified = True
            return _ok(f"已删除外设 '{p_name}'", {"name": p_name})

        return self._try(_run)

    # ==================== 编辑：寄存器 ====================

    def add_register(self, peripheral: str, name: str, offset: str = "0x00",
                     description: str = "", size: str = "0x20",
                     access: Optional[str] = None, reset_value: str = "0x00000000",
                     doc_id: Optional[str] = None) -> Dict[str, Any]:
        def _run() -> Dict[str, Any]:
            entry = self._resolve(doc_id)
            device = entry.device
            periph_name = peripheral.strip()
            if periph_name not in device.peripherals:
                return _fail(f"外设 '{periph_name}' 不存在")
            periph = device.peripherals[periph_name]
            reg_name = name.strip()
            if not reg_name:
                return _fail("寄存器名不能为空")
            if reg_name in periph.registers:
                return _fail(f"寄存器 '{reg_name}' 已存在（{periph_name}）")

            periph.registers[reg_name] = Register(
                name=reg_name, offset=offset, description=description,
                size=size, access=access, reset_value=reset_value)
            entry.modified = True
            return _ok(f"已添加寄存器 '{reg_name}' 到 '{periph_name}' (offset={offset})",
                       {"name": reg_name})

        return self._try(_run)

    def update_register(self, peripheral: str, name: str, updates: Dict[str, Any],
                        doc_id: Optional[str] = None) -> Dict[str, Any]:
        def _run() -> Dict[str, Any]:
            entry = self._resolve(doc_id)
            device = entry.device
            periph_name = peripheral.strip()
            reg_name = name.strip()
            if periph_name not in device.peripherals:
                return _fail(f"外设 '{periph_name}' 不存在")
            periph = device.peripherals[periph_name]
            if reg_name not in periph.registers:
                return _fail(f"寄存器 '{reg_name}' 不存在")
            if not updates:
                return _fail("没有要更新的字段")
            reg = periph.registers[reg_name]

            new_name = str(updates.get("name", "")).strip()
            renamed = False
            if new_name and new_name != reg_name:
                if new_name in periph.registers:
                    return _fail(f"寄存器 '{new_name}' 已存在（{periph_name}）")
                periph.registers = {
                    (new_name if k == reg_name else k): v for k, v in periph.registers.items()
                }
                reg.name = new_name
                renamed = True
            cur_name = new_name if renamed else reg_name

            if "derived_from" in updates:
                df = str(updates["derived_from"]).strip()
                if df == cur_name:
                    return _fail("寄存器不能继承自己")
                if df and df not in periph.registers:
                    return _fail(f"派生目标寄存器 '{df}' 不存在")

            for key in ("description", "offset", "size", "access", "reset_value",
                        "display_name", "derived_from", "reset_mask", "dim",
                        "dim_increment", "dim_index"):
                if key in updates:
                    setattr(reg, key, updates[key])
            entry.modified = True
            return _ok(f"已更新寄存器 '{cur_name}'",
                       {"name": cur_name, "renamed": renamed,
                        "updates": [k for k in updates if k != "name"]})

        return self._try(_run)

    def remove_register(self, peripheral: str, name: str, doc_id: Optional[str] = None) -> Dict[str, Any]:
        def _run() -> Dict[str, Any]:
            entry = self._resolve(doc_id)
            device = entry.device
            periph_name = peripheral.strip()
            reg_name = name.strip()
            if periph_name not in device.peripherals:
                return _fail(f"外设 '{periph_name}' 不存在")
            periph = device.peripherals[periph_name]
            if reg_name not in periph.registers:
                return _fail(f"寄存器 '{reg_name}' 不存在")
            del periph.registers[reg_name]
            entry.modified = True
            return _ok(f"已删除寄存器 '{reg_name}'（{periph_name}）", {"name": reg_name})

        return self._try(_run)

    # ==================== 编辑：位域 ====================

    def add_field(self, peripheral: str, register: str, name: str,
                  bit_offset: int = 0, bit_width: int = 1, description: str = "",
                  access: Optional[str] = None, reset_value: str = "0x0",
                  doc_id: Optional[str] = None) -> Dict[str, Any]:
        def _run() -> Dict[str, Any]:
            entry = self._resolve(doc_id)
            device = entry.device
            periph_name = peripheral.strip()
            reg_name = register.strip()
            if periph_name not in device.peripherals:
                return _fail(f"外设 '{periph_name}' 不存在")
            periph = device.peripherals[periph_name]
            if reg_name not in periph.registers:
                return _fail(f"寄存器 '{reg_name}' 不存在")
            reg = periph.registers[reg_name]
            field_name = name.strip()
            if not field_name:
                return _fail("位域名不能为空")
            if field_name in reg.fields:
                return _fail(f"位域 '{field_name}' 已存在")

            bo = int(bit_offset)
            bw = int(bit_width)
            reg.fields[field_name] = Field(
                name=field_name, bit_offset=bo, bit_width=bw,
                description=description, access=access, reset_value=reset_value)
            entry.modified = True
            return _ok(
                f"已添加位域 '{field_name}' [{bo}:{bo + bw - 1}] 到 {reg_name}",
                {"name": field_name})

        return self._try(_run)

    def update_field(self, peripheral: str, register: str, name: str,
                     updates: Dict[str, Any], doc_id: Optional[str] = None) -> Dict[str, Any]:
        def _run() -> Dict[str, Any]:
            entry = self._resolve(doc_id)
            device = entry.device
            periph_name = peripheral.strip()
            reg_name = register.strip()
            field_name = name.strip()
            if periph_name not in device.peripherals:
                return _fail(f"外设 '{periph_name}' 不存在")
            periph = device.peripherals[periph_name]
            if reg_name not in periph.registers:
                return _fail(f"寄存器 '{reg_name}' 不存在")
            reg = periph.registers[reg_name]
            if field_name not in reg.fields:
                return _fail(f"位域 '{field_name}' 不存在")
            if not updates:
                return _fail("没有要更新的字段")
            fld = reg.fields[field_name]

            new_name = str(updates.get("name", "")).strip()
            renamed = False
            if new_name and new_name != field_name:
                if new_name in reg.fields:
                    return _fail(f"位域 '{new_name}' 已存在")
                reg.fields = {
                    (new_name if k == field_name else k): v for k, v in reg.fields.items()
                }
                fld.name = new_name
                renamed = True
            cur_name = new_name if renamed else field_name

            for key in ("description", "bit_offset", "bit_width", "access",
                        "reset_value", "display_name", "enumerated_values"):
                if key in updates:
                    value = updates[key]
                    if key in ("bit_offset", "bit_width"):
                        value = int(value)
                    setattr(fld, key, value)
            entry.modified = True
            return _ok(f"已更新位域 '{cur_name}'",
                       {"name": cur_name, "renamed": renamed,
                        "updates": [k for k in updates if k != "name"]})

        return self._try(_run)

    def remove_field(self, peripheral: str, register: str, name: str,
                     doc_id: Optional[str] = None) -> Dict[str, Any]:
        def _run() -> Dict[str, Any]:
            entry = self._resolve(doc_id)
            device = entry.device
            periph_name = peripheral.strip()
            reg_name = register.strip()
            field_name = name.strip()
            if periph_name not in device.peripherals:
                return _fail(f"外设 '{periph_name}' 不存在")
            periph = device.peripherals[periph_name]
            if reg_name not in periph.registers:
                return _fail(f"寄存器 '{reg_name}' 不存在")
            reg = periph.registers[reg_name]
            if field_name not in reg.fields:
                return _fail(f"位域 '{field_name}' 不存在")
            del reg.fields[field_name]
            entry.modified = True
            return _ok(f"已删除位域 '{field_name}'（{reg_name}）", {"name": field_name})

        return self._try(_run)

    # ==================== 编辑：中断 ====================

    def add_interrupt(self, name: str, value: int, description: str = "",
                      peripherals: Optional[List[str]] = None,
                      doc_id: Optional[str] = None) -> Dict[str, Any]:
        def _run() -> Dict[str, Any]:
            entry = self._resolve(doc_id)
            device = entry.device
            irq_name = str(name).strip()
            if not irq_name:
                return _fail("中断名称不能为空")
            if irq_name in device.interrupts:
                return _fail(f"中断 '{irq_name}' 已存在")
            irq_periphs = list(peripherals or [])
            device.interrupts[irq_name] = Interrupt(
                name=irq_name, value=int(value), description=str(description),
                peripheral=irq_periphs[0] if irq_periphs else "",
                peripherals=irq_periphs)
            entry.modified = True
            return _ok(f"已添加中断 '{irq_name}' (IRQ {value})",
                       {"name": irq_name, "value": value})

        return self._try(_run)

    def update_interrupt(self, name: str, updates: Dict[str, Any],
                         doc_id: Optional[str] = None) -> Dict[str, Any]:
        def _run() -> Dict[str, Any]:
            entry = self._resolve(doc_id)
            device = entry.device
            irq_name = str(name).strip()
            if irq_name not in device.interrupts:
                return _fail(f"中断 '{irq_name}' 不存在")
            if not updates:
                return _fail("没有要更新的字段")
            old_irq = device.interrupts[irq_name]

            new_name = str(updates.get("name", irq_name)).strip()
            if new_name != irq_name and new_name in device.interrupts:
                return _fail(f"中断 '{new_name}' 已存在")

            if "peripherals" in updates:
                peripherals = updates["peripherals"]
                if isinstance(peripherals, str):
                    peripherals = [peripherals]
                peripherals = list(peripherals)
            else:
                peripherals = list(old_irq.peripherals)

            updated = Interrupt(
                name=new_name,
                value=int(updates.get("value", old_irq.value)),
                description=str(updates.get("description", old_irq.description)),
                peripheral=peripherals[0] if peripherals else "",
                peripherals=peripherals)
            if new_name != irq_name:
                del device.interrupts[irq_name]
            device.interrupts[new_name] = updated
            entry.modified = True
            return _ok(f"已更新中断 '{new_name}'", {"name": new_name, "renamed": new_name != name})

        return self._try(_run)

    def remove_interrupt(self, name: str, doc_id: Optional[str] = None) -> Dict[str, Any]:
        def _run() -> Dict[str, Any]:
            entry = self._resolve(doc_id)
            device = entry.device
            irq_name = str(name).strip()
            if irq_name not in device.interrupts:
                return _fail(f"中断 '{irq_name}' 不存在")
            del device.interrupts[irq_name]
            entry.modified = True
            return _ok(f"已删除中断 '{irq_name}'", {"name": irq_name})

        return self._try(_run)

    # ==================== 校验与对比 ====================

    def validate(self, doc_id: Optional[str] = None) -> Dict[str, Any]:
        def _run() -> Dict[str, Any]:
            entry = self._resolve(doc_id)
            validator = SVDSchemaValidator()
            validator.validate_all(entry.device)
            summary = validator.get_summary()
            text = validator.format_results_text(max_items=50)
            return _ok(
                f"校验完成：{summary.get('errors', 0)} 错误 / {summary.get('warnings', 0)} 警告",
                {"summary": summary, "details": text},
            )

        return self._try(_run)

    def conflicts(self, doc_id: Optional[str] = None) -> Dict[str, Any]:
        def _run() -> Dict[str, Any]:
            entry = self._resolve(doc_id)
            detector = AddressConflictDetector()
            found = detector.detect_all(entry.device)
            conflict_list = [
                {"type": str(getattr(c, "conflict_type", "unknown")),
                 "severity": str(getattr(c, "severity", "unknown")),
                 "message": getattr(c, "message", str(c))}
                for c in (found or [])[:50]
            ]
            return _ok(
                f"发现 {len(found or [])} 个地址冲突" if found else "未发现地址冲突",
                {"conflicts": conflict_list, "total": len(found or [])},
            )

        return self._try(_run)

    def diff(self, doc_a: str, doc_b: str, peripheral: Optional[str] = None) -> Dict[str, Any]:
        def _run() -> Dict[str, Any]:
            if doc_a not in self._docs:
                return _fail(f"文档 '{doc_a}' 未打开")
            if doc_b not in self._docs:
                return _fail(f"文档 '{doc_b}' 未打开")
            a, b = self._docs[doc_a].device, self._docs[doc_b].device
            differ = SVDDiffer()
            diffs = (differ.diff_peripheral(a, b, peripheral) if peripheral
                     else differ.diff(a, b))

            def _flatten(item, out):
                out.append({
                    "path": item.path,
                    "type": item.diff_type.name if hasattr(item, "diff_type") else str(getattr(item, "type", "")),
                    "old": item.old_value, "new": item.new_value,
                    "category": getattr(item, "category", ""),
                })
                for child in getattr(item, "children", []):
                    _flatten(child, out)

            flat: List[Dict[str, Any]] = []
            for d in diffs or []:
                _flatten(d, flat)
            summary = differ.generate_summary(diffs) if diffs else "两个文件结构完全一致"
            return _ok(f"对比完成：{len(flat)} 处差异",
                       {"summary": summary, "items": flat[:200], "total": len(flat)})

        return self._try(_run)

    # ==================== 输出 ====================

    def export(self, format: str, out_path: Optional[str] = None,
               peripheral: Optional[str] = None, doc_id: Optional[str] = None) -> Dict[str, Any]:
        def _run() -> Dict[str, Any]:
            entry = self._resolve(doc_id)
            fmt = (format or "").lower()
            if fmt not in ("csv", "markdown", "html", "md"):
                return _fail("format 仅支持 csv / markdown / html")
            if fmt == "md":
                fmt = "markdown"

            device_name = entry.device.name or entry.doc_id
            default_ext = {"csv": ".csv", "markdown": ".md", "html": ".html"}[fmt]
            target = Path(out_path) if out_path else Path(
                f"{device_name}{'_' + peripheral if peripheral else ''}{default_ext}")
            if not target.is_absolute():
                target = Path.cwd() / target

            exporter = SVDExporter(entry.device)
            if fmt == "csv":
                ok = exporter.export_csv(str(target), peripheral)
            elif fmt == "markdown":
                ok = exporter.export_markdown(str(target), peripheral)
            else:
                ok = exporter.export_html(str(target), peripheral)
            if not ok:
                return _fail(f"导出失败: {target}")
            return _ok(f"已导出 {fmt} 到 {target}", {"file": str(target)})

        return self._try(_run)

    def generate_header(self, out_path: Optional[str] = None, style: str = "upper_case",
                        prefix: str = "", cmsis: bool = False,
                        doc_id: Optional[str] = None) -> Dict[str, Any]:
        def _run() -> Dict[str, Any]:
            entry = self._resolve(doc_id)
            gen = HeaderGenerator(entry.device)
            content = gen.generate_cmsis() if cmsis else gen.generate(style=style, prefix=prefix)

            result: Dict[str, Any] = {"lines": content.count("\n") + 1}
            if out_path:
                target = Path(out_path)
                if not target.is_absolute():
                    target = Path.cwd() / target
                target.write_text(content, encoding="utf-8")
                result["file"] = str(target)
                msg = f"已生成 C 头文件 {target}（{result['lines']} 行）"
            else:
                # 不落盘时返回预览，避免超大文件整段进上下文
                preview_lines = content.splitlines()
                result["preview"] = "\n".join(preview_lines[:120])
                msg = f"已生成 C 头文件（{result['lines']} 行，预览前 120 行；提供 out_path 可保存全文件）"
            return _ok(msg, result)

        return self._try(_run)
