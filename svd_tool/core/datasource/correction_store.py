"""人工纠错 sidecar 与审计模型。

设计目标：
- 同一来源重新解析后，按稳定 key 自动重放人工修正；
- 同时保留解析原值、人工值、最终值、来源定位和完整审计轨迹；
- 不依赖 Qt / 外部 Parser，可在无 GUI 环境直接测试。
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field as dc_field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional
from uuid import uuid4


SCHEMA_VERSION = 2
MACHINE = "machine_extracted"
CONFIRMED = "human_confirmed"
REJECTED = "human_rejected"
IGNORED = "ignored"

_PROPERTY_ALIASES = {
    "base_address": "base_address",
    "address_offset": "address_offset",
    "offset": "address_offset",
    "reset_value": "reset_value",
    "access": "access",
    "bit_offset": "bit_offset",
    "bit_pos": "bit_offset",
    "bit_width": "bit_width",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def file_fingerprint(path: str | os.PathLike[str]) -> dict:
    p = Path(path)
    digest = hashlib.sha256()
    try:
        with p.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(chunk)
        st = p.stat()
        return {
            "path": str(p.resolve()),
            "name": p.name,
            "sha256": digest.hexdigest(),
            "size": st.st_size,
            "mtime": st.st_mtime,
        }
    except OSError:
        return {"path": str(p), "name": p.name, "sha256": "", "size": 0, "mtime": 0}


def default_sidecar_path(source_path: str | os.PathLike[str]) -> Path:
    p = Path(source_path)
    return p.with_name(p.name + ".svd-corrections.json")


def _json_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _display_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _property_name(name: str) -> str:
    return _PROPERTY_ALIASES.get(name, name)


def source_authority_label(source_file: str, explicit: str = "") -> str:
    if explicit:
        return explicit
    lower = source_file.lower()
    if lower.endswith((".docx", ".doc")) and ("trm" in lower or "technical_reference" in lower):
        return "authoritative_trm"
    if lower.endswith((".xlsx", ".xls", ".csv")):
        return "structured_support"
    if lower.endswith(".pdf"):
        return "document_support"
    return "machine_extracted"


def parse_completeness(entity: Any, level: str) -> str:
    """解析完整度只表示字段齐全程度，不代表准确率。"""
    if level == "peripheral":
        required = ("name", "base_address")
    elif level == "interrupt":
        required = ("name", "irq_number", "description")
    elif level == "register":
        required = ("name", "address_offset", "reset_value")
    else:
        required = ("name", "bit_pos", "bit_width")
    present = sum(
        1 for name in required
        if _display_value(getattr(entity, name, "")) not in ("", "None")
    )
    ratio = present / max(len(required), 1)
    if ratio >= 1:
        return "complete"
    if ratio >= 0.66:
        return "partial"
    return "incomplete"


@dataclass
class CorrectionRecord:
    key: str
    level: str
    peripheral: str
    property_name: str
    extracted_value: str
    manual_value: str = ""
    final_value: str = ""
    status: str = MACHINE
    modified_at: str = ""
    note: str = ""
    source_file: str = ""
    source_fingerprint: str = ""
    source_ref: dict = dc_field(default_factory=dict)
    register: str = ""
    field: str = ""
    original_extracted_value: str = ""
    source_authority: str = ""
    parse_completeness: str = "unknown"
    object_id: str = ""
    semantic_path: str = ""
    source_anchor: dict = dc_field(default_factory=dict)
    match_reason: str = "source_anchor"
    match_score: float = 1.0
    multi_source_agreement: str = "single_source"
    aliases: list[str] = dc_field(default_factory=list)
    source_values: dict[str, list[Any]] = dc_field(default_factory=dict)

    @property
    def manual_confirmation(self) -> str:
        return {
            MACHINE: "pending",
            CONFIRMED: "confirmed",
            REJECTED: "rejected",
            IGNORED: "ignored",
        }.get(self.status, self.status)

    def resolved_final_value(self) -> str:
        if self.status in (REJECTED, IGNORED):
            return ""
        if self.status == CONFIRMED and self.manual_value != "":
            return self.manual_value
        return self.extracted_value

    def to_dict(self) -> dict:
        data = asdict(self)
        data["manual_confirmation"] = self.manual_confirmation
        data["final_value"] = self.resolved_final_value()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "CorrectionRecord":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        payload = {k: v for k, v in data.items() if k in known}
        payload.setdefault("source_ref", {})
        record = cls(**payload)
        if not record.original_extracted_value:
            record.original_extracted_value = record.extracted_value
        if not record.final_value:
            record.final_value = record.resolved_final_value()
        return record


def entity_path(level: str, peripheral: str, register: str = "", field: str = "") -> str:
    return "/".join(x for x in (peripheral, register, field) if x)


def _canonical_identity(
    fingerprint: str,
    level: str,
    semantic_path: str,
    property_name: str,
    source_ref: Optional[dict],
) -> str:
    ref = source_ref or {}
    anchor = ref.get("row_id") or ref.get("row_number") or ""
    table = ref.get("table_index") or ""
    return "|".join((
        fingerprint[:24], level, semantic_path, _property_name(property_name),
        str(table), str(anchor),
    ))


def stable_key(
    source_file: str,
    source_fingerprint: str,
    level: str,
    peripheral: str,
    register: str,
    field: str,
    property_name: str,
    source_ref: Optional[dict] = None,
) -> str:
    ref = source_ref or {}
    path = entity_path(level, peripheral, register, field)
    if level == "peripheral":
        # 外设可能来自 REGMAP 的基址行，解析器补齐章节/表格元数据后
        # 不应改变既有人工修正 key。
        row_anchor = ""
        table_anchor = ""
    else:
        row_anchor = ref.get("row_id") or ref.get("row_number") or ""
        table_anchor = ref.get("table_index") or ref.get("table_id") or ""
    material = "|".join((
        Path(source_file).name,
        (source_fingerprint or "")[:16],
        str(table_anchor),
        str(row_anchor),
        level,
        path,
        _property_name(property_name),
    ))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]


def iter_correction_candidates(chip_data: Any, source_file: str = "") -> Iterator[CorrectionRecord]:
    """展开 ChipData，生成可供人工审阅的字段级记录。"""
    fingerprint = file_fingerprint(source_file).get("sha256", "") if source_file else ""
    authority = source_authority_label(source_file)

    def make(entity: Any, level: str, pname: str, rname: str = "", fname: str = "",
             prop: str = "", value: Any = "") -> CorrectionRecord:
        prop = _property_name(prop)
        src_ref = dict(getattr(entity, "source_ref", {}) or {})
        if not src_ref and level == "field":
            parent = getattr(entity, "_parent_source_ref", None)
            if parent:
                src_ref = dict(parent)
        src_ref.setdefault("source_file", source_file)
        semantic_path = entity_path(level, pname, rname, fname)
        key = stable_key(source_file, fingerprint, level, pname, rname, fname, prop, src_ref)
        anchor_material = _canonical_identity(
            fingerprint, level, semantic_path, prop, src_ref)
        object_id = hashlib.sha256(anchor_material.encode("utf-8")).hexdigest()[:20]
        raw = _display_value(value)
        return CorrectionRecord(
            key=key,
            level=level,
            peripheral=pname,
            register=rname,
            field=fname,
            property_name=prop,
            extracted_value=raw,
            original_extracted_value=raw,
            final_value=raw,
            source_file=source_file,
            source_fingerprint=fingerprint,
            source_ref=src_ref,
            source_authority=authority,
            parse_completeness=parse_completeness(entity, level),
            object_id=object_id,
            semantic_path=semantic_path,
            source_anchor=dict(src_ref),
            match_reason="source_anchor",
            match_score=1.0,
            multi_source_agreement=getattr(
                entity, "multi_source_agreement", "single_source"),
            aliases=list(getattr(entity, "aliases", []) or []),
            source_values=dict(getattr(entity, "source_values", {}) or {}),
        )

    for irq in getattr(chip_data, "interrupts", []) or []:
        iname = _display_value(getattr(irq, "name", ""))
        for prop in (
            "name", "irq_number", "description", "vector_number",
            "vector_address", "priority", "nvic_enable", "mask_bit",
            "sub_enable_bits", "flag_bits", "wake_from_stop",
        ):
            yield make(irq, "interrupt", iname, prop=prop,
                       value=getattr(irq, prop, ""))

    for pblk in getattr(chip_data, "peripherals", []) or []:
        pname = _display_value(getattr(pblk, "name", ""))
        for prop in ("name", "base_address", "description"):
            yield make(pblk, "peripheral", pname, prop=prop,
                       value=getattr(pblk, prop, ""))
        for reg in getattr(pblk, "registers", []) or []:
            rname = _display_value(getattr(reg, "name", ""))
            for prop in ("name", "address_offset", "reset_value", "access", "description"):
                yield make(reg, "register", pname, rname, prop=prop,
                           value=getattr(reg, prop, ""))
            for fld in getattr(reg, "fields", []) or []:
                fname = _display_value(getattr(fld, "name", ""))
                values = {
                    "name": getattr(fld, "name", ""),
                    "bit_offset": getattr(fld, "bit_pos", 0),
                    "bit_width": getattr(fld, "bit_width", 1),
                    "access": getattr(fld, "access", ""),
                    "description": getattr(fld, "description", ""),
                }
                for prop, value in values.items():
                    yield make(fld, "field", pname, rname, fname, prop, value)


class CorrectionStore:
    """字段级人工纠错 sidecar。"""

    def __init__(self, path: str | os.PathLike[str], sources: Optional[dict[str, str]] = None):
        self.path = Path(path)
        self.sources = dict(sources or {})
        self.records: dict[str, CorrectionRecord] = {}
        self.audit_log: list[dict] = []
        self.events: list[dict] = []
        self.undo_stack: list[dict] = []
        self.snapshot_paths: list[dict] = []
        self.resolved_model_path = ""
        self.loaded = False
        self.load_error = ""
        self.load()

    @classmethod
    def for_sources(
        cls,
        sources: dict[str, str],
        explicit_path: str | os.PathLike[str] | None = None,
    ) -> "CorrectionStore":
        if explicit_path:
            path = Path(explicit_path)
        else:
            candidates = [sources.get("word"), sources.get("pdf"), sources.get("excel")]
            source = next((p for p in candidates if p), next(iter(sources.values()), "."))
            path = default_sidecar_path(source)
        return cls(path, sources)

    def load(self) -> None:
        self.loaded = True
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.records = {
                item["key"]: CorrectionRecord.from_dict(item)
                for item in data.get("records", [])
                if item.get("key")
            }
            self.audit_log = list(data.get("audit_log", []))
            self.events = list(data.get("events", []))
            self.undo_stack = list(data.get("undo_stack", []))
            self.snapshot_paths = list(data.get("snapshot_paths", []))
            self.resolved_model_path = str(data.get("resolved_model_path", ""))
            self._load_event_log()
        except Exception as exc:
            # sidecar 损坏时不能阻断解析；拒绝覆盖原文件，由上层显示警告。
            self.loaded = False
            self.load_error = str(exc)

    def save(self) -> None:
        if self.load_error:
            raise RuntimeError(f"纠错 sidecar 无法读取，拒绝覆盖: {self.load_error}")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": utc_now(),
            "sources": {
                src: file_fingerprint(path) for src, path in self.sources.items()
            },
            "records": [record.to_dict() for record in self.records.values()],
            "audit_log": self.audit_log[-1000:],
            "events": self.events[-5000:],
            "undo_stack": self.undo_stack[-100:],
            "snapshot_paths": self.snapshot_paths[-100:],
            "resolved_model_path": self.resolved_model_path,
        }
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp, self.path)

    def sync_candidates(self, chip_data: Any, source_file: str = "") -> list[CorrectionRecord]:
        """把本次解析值合并进 sidecar；已有修正保持原 key 与人工决策。"""
        source_file = source_file or self._primary_source()
        merged: list[CorrectionRecord] = []
        changed = False
        for candidate in iter_correction_candidates(chip_data, source_file):
            existing = self.records.get(candidate.key)
            if existing is None:
                self.records[candidate.key] = candidate
                merged.append(candidate)
                changed = True
                continue
            if candidate.source_ref:
                existing.source_ref = candidate.source_ref
            if candidate.source_authority:
                existing.source_authority = candidate.source_authority
            if candidate.parse_completeness:
                existing.parse_completeness = candidate.parse_completeness
            if existing.extracted_value != candidate.extracted_value:
                self.audit_log.append({
                    "at": utc_now(), "action": "reparse_value_changed",
                    "key": candidate.key,
                    "old_extracted": existing.extracted_value,
                    "new_extracted": candidate.extracted_value,
                })
                existing.extracted_value = candidate.extracted_value
                existing.final_value = existing.resolved_final_value()
                changed = True
            merged.append(existing)
        current_keys = {record.key for record in merged}
        stale_machine = [
            key for key, record in self.records.items()
            if key not in current_keys and record.status == MACHINE
        ]
        for key in stale_machine:
            self.records.pop(key, None)
            self.audit_log.append({
                "at": utc_now(), "action": "stale_machine_record_removed", "key": key,
            })
        if changed or stale_machine:
            self.save()
        unique = {}
        for record in merged:
            unique.setdefault(record.key, record)
        return list(unique.values())

    def apply_to_chip_data(self, chip_data: Any, records: Optional[Iterable[CorrectionRecord]] = None) -> int:
        """重新解析后自动重放人工确认值。拒绝/忽略只保留审计状态，不覆盖机器提取结果。"""
        source_file = self._primary_source()
        candidates = list(records or iter_correction_candidates(chip_data, source_file))
        applied = 0
        for record in candidates:
            stored = self.records.get(record.key)
            if stored is None or stored.status != CONFIRMED:
                continue
            entity = self._entity_for_record(chip_data, record)
            if entity is None:
                continue
            prop = _PROPERTY_ALIASES.get(record.property_name, record.property_name)
            value = stored.manual_value if stored.manual_value != "" else stored.extracted_value
            try:
                if prop == "bit_offset":
                    setattr(entity, "bit_pos", int(value, 0))
                elif prop == "bit_width":
                    setattr(entity, "bit_width", int(value, 0))
                else:
                    setattr(entity, prop, value)
                stored.final_value = stored.resolved_final_value()
                applied += 1
            except (TypeError, ValueError):
                self.audit_log.append({
                    "at": utc_now(), "action": "apply_failed", "key": stored.key,
                    "value": value,
                })
        if applied:
            self.save()
        return applied

    @property
    def event_log_path(self) -> Path:
        return self.path.with_name(self.path.name + ".events.jsonl")

    def _load_event_log(self) -> None:
        if not self.event_log_path.exists():
            return
        seen = {event.get("event_id") for event in self.events}
        try:
            for line in self.event_log_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                event = json.loads(line)
                if event.get("event_id") not in seen:
                    self.events.append(event)
                    seen.add(event.get("event_id"))
        except Exception as exc:
            self.audit_log.append({
                "at": utc_now(), "action": "event_log_read_error",
                "detail": str(exc),
            })

    def _append_event(self, event: dict) -> None:
        self.events.append(event)
        try:
            self.event_log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.event_log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception as exc:
            self.audit_log.append({
                "at": utc_now(), "action": "event_log_write_error",
                "event_id": event.get("event_id", ""), "detail": str(exc),
            })

    def ensure_snapshot(self, chip_data: Any, source_files: Iterable[dict]) -> dict:
        from .review_workflow import write_extracted_snapshot
        snapshot = write_extracted_snapshot(
            chip_data, source_files, self.path)
        if not any(item.get("sha256") == snapshot.get("sha256")
                   for item in self.snapshot_paths):
            self.snapshot_paths.append(snapshot)
            event = {
                "event_id": str(uuid4()),
                "transaction_id": str(uuid4()),
                "action": "snapshot_created",
                "key": "",
                "at": utc_now(),
                "extracted_value": "",
                "manual_value": "",
                "before_status": "",
                "after_status": "",
                "note": "immutable extracted snapshot",
                "object_id": "",
                "semantic_path": "",
                "source_anchor": snapshot,
                "actor": "system",
            }
            self._append_event(event)
            self.audit_log.append(event)
            self.save()
        return snapshot

    def write_resolved_model(self, chip_data: Any) -> Path:
        from .review_workflow import write_resolved_model
        self.resolved_model_path = str(write_resolved_model(
            chip_data, self.records.values(), self.path))
        self.save()
        return Path(self.resolved_model_path)

    def export_manifest(
        self,
        path: str | os.PathLike[str],
        artifacts: Optional[dict] = None,
        unresolved_risks: Optional[list[str]] = None,
        extra: Optional[dict] = None,
    ) -> Path:
        from .review_workflow import write_manifest
        return write_manifest(
            path,
            self.sources.values() if isinstance(self.sources, dict) else self.sources,
            artifacts or {
                "sidecar": self.path,
                "event_log": self.event_log_path,
                "resolved_model": self.resolved_model_path,
            },
            self.summary().get("manual_confirmation", {}),
            unresolved_risks,
            extra,
        )

    def upsert(
        self,
        record: CorrectionRecord,
        status: str,
        manual_value: Optional[str] = None,
        note: str = "",
    ) -> CorrectionRecord:
        return self.apply_actions([{
            "key": record.key,
            "status": status,
            "manual_value": record.manual_value if manual_value is None else manual_value,
            "note": note or record.note,
        }])[0]

    def apply_actions(self, actions: list[dict]) -> list[CorrectionRecord]:
        """批量写入一个可撤销事务。"""
        transaction_id = str(uuid4())
        changes: list[dict] = []
        touched: list[CorrectionRecord] = []
        for action in actions:
            key = action["key"]
            before = self.records[key].to_dict() if key in self.records else None
            record = self.records.get(key)
            if record is None:
                continue
            old_status = record.status
            old_manual = record.manual_value
            old_note = record.note
            record.status = action.get("status", record.status)
            if action.get("manual_value") is not None:
                record.manual_value = _display_value(action["manual_value"])
            if action.get("note") is not None:
                record.note = _display_value(action["note"])
            record.modified_at = utc_now()
            record.final_value = record.resolved_final_value()
            changes.append({"key": key, "before": before, "after": record.to_dict()})
            self._append_event({
                "event_id": str(uuid4()),
                "transaction_id": transaction_id,
                "action": "review_decision",
                "key": key,
                "at": record.modified_at,
                "extracted_value": record.extracted_value,
                "manual_value": record.manual_value,
                "before_status": old_status,
                "after_status": record.status,
                "note": record.note,
                "object_id": record.object_id,
                "semantic_path": record.semantic_path,
                "source_anchor": record.source_ref,
                "actor": "human_operator",
            })
            self.audit_log.append({
                "at": record.modified_at,
                "action": "manual_review",
                "key": key,
                "old_status": old_status,
                "new_status": record.status,
                "old_manual_value": old_manual,
                "new_manual_value": record.manual_value,
                "note": record.note,
            })
            touched.append(record)
        if changes:
            self.undo_stack.append({"at": utc_now(), "changes": changes})
            self.save()
        return touched

    def undo_last(self) -> int:
        if not self.undo_stack:
            return 0
        transaction = self.undo_stack.pop()
        count = 0
        for change in reversed(transaction.get("changes", [])):
            key = change["key"]
            before = change.get("before")
            if before is None:
                self.records.pop(key, None)
            else:
                self.records[key] = CorrectionRecord.from_dict(before)
            count += 1
        undo_event = {
            "event_id": str(uuid4()),
            "transaction_id": str(uuid4()),
            "action": "undo",
            "key": "",
            "at": utc_now(),
            "count": count,
            "transaction_at": transaction.get("at", ""),
            "actor": "human_operator",
        }
        self._append_event(undo_event)
        self.audit_log.append(undo_event)
        self.save()
        return count

    def summary(self) -> dict:
        counts = {MACHINE: 0, CONFIRMED: 0, REJECTED: 0, IGNORED: 0}
        for record in self.records.values():
            counts[record.status] = counts.get(record.status, 0) + 1
        return {
            "total": len(self.records),
            "machine_extracted": counts[MACHINE],
            "human_confirmed": counts[CONFIRMED],
            "human_rejected": counts[REJECTED],
            "ignored": counts[IGNORED],
            "source_authority": sorted({r.source_authority for r in self.records.values()}),
            "parse_completeness": sorted({r.parse_completeness for r in self.records.values()}),
            "multi_source_agreement": sorted({
                r.multi_source_agreement for r in self.records.values()
            }),
            "manual_confirmation": {
                "pending": counts[MACHINE],
                "confirmed": counts[CONFIRMED],
                "rejected": counts[REJECTED],
                "ignored": counts[IGNORED],
            },
            "event_count": len(self.events),
            "snapshot_count": len(self.snapshot_paths),
        }

    def report_rows(self) -> list[dict]:
        rows = []
        for record in self.records.values():
            row = record.to_dict()
            row["original_extracted_value"] = record.original_extracted_value or record.extracted_value
            rows.append(row)
        rows.sort(key=lambda r: (
            r.get("peripheral", ""), r.get("register", ""), r.get("field", ""),
            r.get("property_name", ""),
        ))
        return rows

    def export_json_report(self, path: str | os.PathLike[str]) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "schema_version": SCHEMA_VERSION,
            "generated_at": utc_now(),
            "summary": self.summary(),
            "rows": self.report_rows(),
            "audit_log": self.audit_log,
            "events": self.events,
            "snapshots": self.snapshot_paths,
            "resolved_model_path": self.resolved_model_path,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        return out

    def export_markdown_report(self, path: str | os.PathLike[str]) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        summary = self.summary()
        lines = [
            "# TRM 人工纠错报告",
            "",
            f"- 生成时间：{utc_now()}",
            f"- sidecar：`{self.path}`",
            f"- 记录：{summary['total']}；人工确认：{summary['human_confirmed']}；"
            f"拒绝：{summary['human_rejected']}；忽略：{summary['ignored']}",
            "",
            "## 语义说明",
            "",
            "- 来源权威度表示资料来源类型，不是准确率。",
            "- 解析完整度表示字段齐全程度，不是准确率。",
            "- 多源一致度表示来源之间是否一致，不是准确率。",
            "- 人工确认状态只表示人工处置状态。",
            "",
            "## 字段级记录",
            "",
            "| 外设 | 寄存器 | 位域 | 属性 | 解析值 | 人工值 | 最终值 | 人工状态 | 来源权威度 | 解析完整度 | 多源一致度 | 匹配理由 | 对象ID | 章节 | 表格 | 行 | 原文 | 备注 |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---:|---:|---|---|",
        ]
        for row in self.report_rows():
            ref = row.get("source_ref") or {}
            raw = str(ref.get("raw_text", "")).replace("|", "\\|").replace("\n", " ")
            note = str(row.get("note", "")).replace("|", "\\|").replace("\n", " ")
            lines.append("| " + " | ".join(str(x).replace("|", "\\|").replace("\n", " ") for x in (
                row.get("peripheral", ""), row.get("register", ""), row.get("field", ""),
                row.get("property_name", ""), row.get("original_extracted_value", ""),
                row.get("manual_value", ""), row.get("final_value", ""),
                row.get("manual_confirmation", ""), row.get("source_authority", ""),
                row.get("parse_completeness", ""), row.get("multi_source_agreement", ""),
                row.get("match_reason", ""), row.get("object_id", ""),
                ref.get("section", ""), ref.get("table_index", ""),
                ref.get("row_number", ""), raw, note,
            )) + " |")
        lines.extend(["", "## 审计轨迹", ""])
        for item in self.audit_log:
            lines.append(f"- `{item.get('at', '')}` {item.get('action', '')}: "
                         f"`{item.get('key', '')}` {item.get('new_status', '')} "
                         f"{item.get('note', '')}")
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return out

    def _primary_source(self) -> str:
        return self.sources.get("word") or self.sources.get("pdf") or self.sources.get("excel") or next(iter(self.sources.values()), "")

    @staticmethod
    def _entity_for_record(chip_data: Any, record: CorrectionRecord) -> Any:
        wanted_ref = record.source_ref or {}
        wanted_anchor = wanted_ref.get("row_id") or wanted_ref.get("row_number")

        def same_source(entity: Any) -> bool:
            ref = getattr(entity, "source_ref", {}) or {}
            anchor = ref.get("row_id") or ref.get("row_number")
            if wanted_anchor and anchor == wanted_anchor:
                return True
            wanted_table = wanted_ref.get("table_index")
            return bool(wanted_table) and ref.get("table_index") == wanted_table

        for irq in getattr(chip_data, "interrupts", []) or []:
            if record.level == "interrupt" and (
                same_source(irq) or getattr(irq, "name", "") == record.peripheral
            ):
                return irq

        for pblk in getattr(chip_data, "peripherals", []) or []:
            if record.level == "peripheral" and (
                same_source(pblk) or getattr(pblk, "name", "") == record.peripheral
            ):
                return pblk
            if record.level == "peripheral":
                continue
            for reg in getattr(pblk, "registers", []) or []:
                if record.level == "register" and (
                    same_source(reg) or getattr(reg, "name", "") == record.register
                ):
                    return reg
                if record.level == "register":
                    continue
                for fld in getattr(reg, "fields", []) or []:
                    if same_source(fld) or getattr(fld, "name", "") == record.field:
                        return fld
        return None

