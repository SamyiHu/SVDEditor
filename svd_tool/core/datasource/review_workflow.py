"""不可变解析快照、人工决策事件账本与交付 Manifest。"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional
from uuid import uuid4

from .correction_store import CorrectionRecord, file_fingerprint, utc_now


REVIEW_SCHEMA_VERSION = 2


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return _jsonable(model_dump())
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return _jsonable(to_dict())
    if hasattr(value, "__dict__"):
        return {
            k: _jsonable(v) for k, v in vars(value).items()
            if not k.startswith("_")
        }
    return str(value)


def _canonical_json(payload: Any) -> str:
    return json.dumps(
        _jsonable(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _artifact(path: str | os.PathLike[str]) -> dict:
    p = Path(path)
    fingerprint = file_fingerprint(p)
    return {
        "path": str(p.resolve()) if p.exists() else str(p),
        "name": p.name,
        "sha256": fingerprint.get("sha256", ""),
        "bytes": fingerprint.get("size", 0),
    }


@dataclass
class ReviewEvent:
    """一次人工审核操作。事件只追加，不原地修改。"""
    event_id: str
    transaction_id: str
    action: str
    key: str
    at: str
    extracted_value: str = ""
    manual_value: str = ""
    before_status: str = ""
    after_status: str = ""
    note: str = ""
    object_id: str = ""
    semantic_path: str = ""
    source_anchor: dict = field(default_factory=dict)
    actor: str = "human_operator"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_record(
        cls,
        record: CorrectionRecord,
        action: str,
        transaction_id: str,
        before_status: str = "",
        manual_value: Optional[str] = None,
        note: str = "",
    ) -> "ReviewEvent":
        return cls(
            event_id=str(uuid4()),
            transaction_id=transaction_id,
            action=action,
            key=record.key,
            at=utc_now(),
            extracted_value=record.extracted_value,
            manual_value=record.manual_value if manual_value is None else str(manual_value),
            before_status=before_status,
            after_status=record.status,
            note=note or record.note,
            object_id=record.object_id,
            semantic_path=record.semantic_path,
            source_anchor=dict(record.source_ref),
        )


def write_extracted_snapshot(
    chip_data: Any,
    source_files: Iterable[dict],
    sidecar_path: str | os.PathLike[str],
) -> dict:
    """写入按内容哈希命名的不可变解析快照；同内容不覆盖。"""
    sidecar = Path(sidecar_path)
    payload = {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "kind": "extracted_snapshot",
        "generated_at": utc_now(),
        "sources": [_jsonable(item) for item in source_files],
        "chip_data": _jsonable(chip_data),
    }
    canonical = _canonical_json({
        "sources": payload["sources"],
        "chip_data": payload["chip_data"],
    })
    digest = _sha256_text(canonical)
    out = sidecar.with_name(f"{sidecar.stem}.snapshot-{digest[:16]}.json")
    created = not out.exists()
    if created:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return {
        "path": str(out.resolve()),
        "sha256": digest,
        "immutable": True,
        "created": created,
    }


def resolve_review_model(
    chip_data: Any,
    records: Iterable[CorrectionRecord],
) -> dict:
    """从机器快照语义和人工 Overlay 得到最终值表，不修改 chip_data。"""
    resolved = copy.deepcopy(_jsonable(chip_data))
    values = []
    for record in records:
        values.append({
            "object_id": record.object_id,
            "semantic_path": record.semantic_path,
            "level": record.level,
            "peripheral": record.peripheral,
            "register": record.register,
            "field": record.field,
            "property": record.property_name,
            "extracted_value": record.original_extracted_value or record.extracted_value,
            "manual_value": record.manual_value,
            "final_value": record.resolved_final_value(),
            "decision": record.manual_confirmation,
            "source_anchor": record.source_ref,
        })
    return {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "kind": "resolved_review_model",
        "generated_at": utc_now(),
        "model": resolved,
        "resolved_values": values,
        "decision_counts": _decision_counts(records),
    }


def _decision_counts(records: Iterable[CorrectionRecord]) -> dict:
    counts = {
        "pending": 0,
        "confirmed": 0,
        "rejected": 0,
        "ignored": 0,
    }
    for record in records:
        key = record.manual_confirmation
        counts[key] = counts.get(key, 0) + 1
    return counts


def write_resolved_model(
    chip_data: Any,
    records: Iterable[CorrectionRecord],
    sidecar_path: str | os.PathLike[str],
) -> Path:
    sidecar = Path(sidecar_path)
    out = sidecar.with_name(f"{sidecar.stem}.resolved-model.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(resolve_review_model(chip_data, records), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out


def build_header_manifest_extra(result: Any, svd_device: Any = None) -> dict:
    """从 ParseResult 组装 Manifest 的 header 区块。

    header_path 模式未启用时返回空 dict；svd_device 给出时附加完整
    H↔SVD 覆盖率（peripherals_in_svd / matched / coverage 等）。
    """
    header_model = getattr(result, "header_model", None)
    if header_model is None:
        return {}
    fusion_coverage = dict(getattr(result, "header_coverage", {}) or {})
    coverage: Any = fusion_coverage
    if svd_device is not None:
        from .header_coverage import build_header_svd_coverage
        coverage = build_header_svd_coverage(
            header_model, svd_device,
            trm_supplement_percent=fusion_coverage.get("trm_supplement_percent"),
        )
    svd_peripherals = 0
    if svd_device is not None:
        svd_peripherals = len(getattr(svd_device, "peripherals", {}) or {})
    return {
        "header_path": getattr(header_model, "path", ""),
        "header_sha256": getattr(header_model, "fingerprint", ""),
        "header_peripherals": len(getattr(header_model, "peripherals", []) or []),
        "svd_peripherals": svd_peripherals,
        "coverage": coverage,
        "unresolved_header_items": len(getattr(header_model, "unresolved", []) or []),
    }


def write_manifest(
    path: str | os.PathLike[str],
    sources: Iterable[dict],
    artifacts: dict[str, str | os.PathLike[str]],
    decision_counts: dict,
    unresolved_risks: Optional[list[str]] = None,
    extra: Optional[dict] = None,
) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "kind": "trm_review_manifest",
        "generated_at": utc_now(),
        "sources": [
            _artifact(item.get("path", "") if isinstance(item, dict) else item)
            for item in sources
        ],
        "artifacts": {
            name: _artifact(value) for name, value in artifacts.items() if value
        },
        "review": {
            "decision_counts": decision_counts,
            "unresolved_risks": unresolved_risks or [],
        },
        "tool": {
            "name": "SVDEditor TRM Review Workflow",
            "version": "2.0",
        },
    }
    if extra:
        payload["extra"] = _jsonable(extra)
        header_block = extra.get("header") if isinstance(extra, dict) else None
        if header_block:
            # H 链路元数据提升为顶层区块：header_path / header_sha256 /
            # header_peripherals / svd_peripherals / coverage /
            # unresolved_header_items
            payload["header"] = _jsonable(header_block)
    out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out
