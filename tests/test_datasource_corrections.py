"""人工纠错 sidecar、自动重放、撤销与寄存器名归一化测试。"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from svd_tool.core.data_model import DeviceInfo, Peripheral, Register, Field
from svd_tool.core.datasource.correction_store import (
    CONFIRMED, REJECTED, CorrectionStore,
)
from svd_tool.core.datasource.parser_bridge import _stamp_multi_source_semantics
from svd_tool.core.datasource.svd_verifier import (
    SVDVerifier, VerifyKind, canonical_register_name,
)


@pytest.fixture
def tmp_path():
    # Windows sandbox 的 pytest tmpdir ACL 在此环境不可用；使用项目内固定目录，
    # 每个测试结束即清理，不污染 git status。
    root = Path(__file__).resolve().parents[1] / "test_data" / "_correction_test_tmp"
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    yield root
    shutil.rmtree(root, ignore_errors=True)


def _ref(source, table=3, row=5, raw="ADC_STS | RW | ADC status"):
    return {
        "source_file": str(source),
        "section": "ADC",
        "table_index": table,
        "row_number": row,
        "row_id": f"{table}:{row}",
        "raw_text": raw,
    }


def _chip(source, name="ADC_STS", offset="0x00", reset="0x00000000", width=1):
    reg_ref = _ref(source, 3, 5, f"{name} | {offset} | {reset}")
    field_ref = _ref(source, 4, 2, "STS | 0 | status flag")
    fld = SimpleNamespace(
        name="STS", bit_pos=0, bit_width=width, access="RW",
        description="status", source_ref=field_ref,
    )
    reg = SimpleNamespace(
        name=name, address_offset=offset, absolute_address="",
        reset_value=reset, access="RW", description="ADC status",
        fields=[fld], source_ref=reg_ref,
    )
    pblk = SimpleNamespace(
        name="ADC", base_address="0x40000000", bus="APB",
        description="ADC", registers=[reg], source_ref=_ref(source, 2, 1, "ADC base"),
    )
    return SimpleNamespace(peripherals=[pblk])


def test_custom_value_rejected_and_undo(tmp_path):
    source = tmp_path / f"SC32F10T_TRM_{uuid4().hex}.docx"
    source.write_bytes(b"source")
    chip = _chip(source)
    store = CorrectionStore(tmp_path / f"corrections_{uuid4().hex}.json", {"word": str(source)})
    records = store.sync_candidates(chip, str(source))
    offset_record = next(r for r in records if r.property_name == "address_offset")
    reset_record = next(r for r in records if r.property_name == "reset_value")

    store.apply_actions([{
        "key": offset_record.key,
        "status": CONFIRMED,
        "manual_value": "0x24",
        "note": "人工核对表 3 第 5 行",
    }])
    store.apply_to_chip_data(chip)
    assert chip.peripherals[0].registers[0].address_offset == "0x24"

    store.apply_actions([{
        "key": reset_record.key,
        "status": REJECTED,
        "manual_value": "0xDEADBEEF",
    }])
    assert reset_record.resolved_final_value() == ""
    rejected_chip = _chip(source)
    assert store.apply_to_chip_data(rejected_chip) == 1
    assert rejected_chip.peripherals[0].registers[0].reset_value == "0x00000000"

    assert store.undo_last() == 1
    assert store.records[reset_record.key].status == "machine_extracted"
    assert store.undo_last() == 1
    assert store.records[offset_record.key].manual_value == ""


def test_reparse_reapplies_custom_value_and_exports_report(tmp_path):
    source = tmp_path / f"SC32F10T_TRM_{uuid4().hex}.docx"
    source.write_bytes(b"same source")
    path = tmp_path / f"SC32F10T_TRM_{uuid4().hex}.docx.svd-corrections.json"
    first = _chip(source)
    store = CorrectionStore(path, {"word": str(source)})
    records = store.sync_candidates(first, str(source))
    key = next(r.key for r in records if r.property_name == "address_offset")
    store.apply_actions([{"key": key, "status": CONFIRMED, "manual_value": "0x34"}])
    store.apply_to_chip_data(first)

    second = _chip(source, offset="0x00")
    store.sync_candidates(second, str(source))
    assert store.apply_to_chip_data(second) == 1
    assert second.peripherals[0].registers[0].address_offset == "0x34"

    report = store.export_markdown_report(tmp_path / f"report_{uuid4().hex}.md")
    assert "0x34" in report.read_text(encoding="utf-8")
    json_report = store.export_json_report(tmp_path / f"report_{uuid4().hex}.json")
    assert "human_confirmed" in json_report.read_text(encoding="utf-8")
    assert "table_index" in json_report.read_text(encoding="utf-8")


def test_prefix_register_names_are_not_missing(tmp_path):
    source = tmp_path / f"SC32F10T_TRM_{uuid4().hex}.docx"
    source.write_bytes(b"source")
    svd = DeviceInfo(name="SC32F10T")
    svd.peripherals["ADC"] = Peripheral(
        name="ADC", base_address="0x40000000",
        registers={"STS": Register(name="STS", offset="0x00")})
    svd.peripherals["CRC"] = Peripheral(
        name="CRC", base_address="0x40001000",
        registers={"CON": Register(name="CON", offset="0x00")})

    source_peripherals = [
        SimpleNamespace(name="ADC", base_address="0x40000000", registers=[
            SimpleNamespace(name="ADC_STS", address_offset="0x00",
                            reset_value="0x0", fields=[])], source_ref={}),
        SimpleNamespace(name="CRC", base_address="0x40001000", registers=[
            SimpleNamespace(name="CRC_CON", address_offset="0x00",
                            reset_value="0x0", fields=[])], source_ref={}),
    ]
    chip = SimpleNamespace(peripherals=source_peripherals)
    items = SVDVerifier().verify(svd, chip)
    missing = [it for it in items if it.kind in (
        VerifyKind.REG_MISSING_IN_SVD.value, VerifyKind.REG_MISSING_IN_SOURCE.value)]
    assert missing == [], missing
    assert canonical_register_name("ADC_STS", "ADC0") == "STS"
    assert canonical_register_name("CRC_CON", "CRC") == "CON"


def test_source_trace_and_field_custom_value(tmp_path):
    source = tmp_path / f"SC32F10T_TRM_{uuid4().hex}.docx"
    source.write_bytes(b"source")
    chip = _chip(source, width=1)
    store = CorrectionStore(tmp_path / f"corrections_{uuid4().hex}.json", {"word": str(source)})
    records = store.sync_candidates(chip, str(source))
    width_record = next(
        r for r in records
        if r.level == "field" and r.property_name == "bit_width")
    assert width_record.source_ref["table_index"] == 4
    assert width_record.source_ref["row_number"] == 2
    assert "status flag" in width_record.source_ref["raw_text"]
    store.apply_actions([{
        "key": width_record.key,
        "status": CONFIRMED,
        "manual_value": "3",
    }])
    store.apply_to_chip_data(chip)
    assert chip.peripherals[0].registers[0].fields[0].bit_width == 3



def test_snapshot_event_ledger_resolved_model_and_manifest(tmp_path):
    source = tmp_path / f"SC32F10T_TRM_{uuid4().hex}.docx"
    source.write_bytes(b"immutable source")
    path = tmp_path / f"corrections_{uuid4().hex}.json"
    chip = _chip(source, offset="0x08")
    store = CorrectionStore(path, {"word": str(source)})
    records = store.sync_candidates(chip, str(source))

    snapshot = store.ensure_snapshot(chip, [{"path": str(source)}])
    snapshot_path = Path(snapshot["path"])
    original_snapshot = snapshot_path.read_text(encoding="utf-8")
    offset_key = next(
        r.key for r in records if r.property_name == "address_offset")
    store.apply_actions([{
        "key": offset_key,
        "status": CONFIRMED,
        "manual_value": "0x44",
        "note": "人工确认",
    }])

    same_snapshot = store.ensure_snapshot(chip, [{"path": str(source)}])
    assert same_snapshot["sha256"] == snapshot["sha256"]
    assert same_snapshot["created"] is False
    assert snapshot_path.read_text(encoding="utf-8") == original_snapshot

    assert store.event_log_path.exists()
    event_names = [event["action"] for event in store.events]
    assert "snapshot_created" in event_names
    assert "review_decision" in event_names

    resolved = store.write_resolved_model(chip)
    resolved_data = json.loads(resolved.read_text(encoding="utf-8"))
    assert resolved_data["decision_counts"]["confirmed"] == 1
    assert any(row["final_value"] == "0x44"
               for row in resolved_data["resolved_values"])

    manifest = store.export_manifest(
        tmp_path / f"manifest_{uuid4().hex}.json",
        {"snapshot": snapshot_path, "resolved_model": resolved},
        ["base_address: ADC"],
    )
    manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
    assert manifest_data["kind"] == "trm_review_manifest"
    assert manifest_data["review"]["decision_counts"]["confirmed"] == 1
    assert manifest_data["review"]["unresolved_risks"] == ["base_address: ADC"]
    assert manifest_data["artifacts"]["snapshot"]["sha256"]

    assert store.undo_last() == 1
    assert store.events[-1]["action"] == "undo"


def test_match_evidence_and_four_dimension_semantics(tmp_path):
    source = tmp_path / f"SC32F10T_TRM_{uuid4().hex}.docx"
    source.write_bytes(b"source")
    svd = DeviceInfo(name="SC32F10T")
    svd.peripherals["ADC"] = Peripheral(
        name="ADC", base_address="0x40000000",
        registers={"STS": Register(name="STS", offset="0x10")})

    reg_ref = _ref(source, 3, 5, "ADC_STS | 0x20 | 0x0")
    source_reg = SimpleNamespace(
        name="ADC_STS", address_offset="0x20", reset_value="0x0",
        fields=[], source_ref=reg_ref, object_id="obj-adc-sts",
        semantic_path="ADC/ADC_STS", aliases=["STATUS", "STS"],
        multi_source_agreement="conflict",
    )
    source_p = SimpleNamespace(
        name="ADC", base_address="0x40000000", registers=[source_reg],
        source_ref=_ref(source, 2, 1, "ADC base"),
    )
    items = SVDVerifier().verify(
        svd, SimpleNamespace(peripherals=[source_p]))

    item = next(it for it in items if it.kind == VerifyKind.OFFSET_MISMATCH.value)
    assert item.match_reason == "peripheral_prefix"
    assert item.match_score == 0.8
    assert item.multi_source_agreement == "conflict"
    assert item.object_id == "obj-adc-sts"
    assert item.semantic_path == "ADC/ADC_STS"
    assert item.aliases == ["STATUS", "STS"]
    assert item.source_authority == "authoritative_trm"
    assert item.parse_completeness == "complete"
    assert item.manual_confirmation == "pending"


def test_multi_source_agreement_is_independent_dimension():
    def make(reset):
        return SimpleNamespace(
            name="ADC", base_address="0x40000000", description="ADC",
            registers=[SimpleNamespace(
                name="ADC_STS", address_offset="0x00", reset_value=reset,
                access="RW", description="status", fields=[])],
        )

    stamped = _stamp_multi_source_semantics(
        [make("0x0")],
        {"word": [make("0x0")], "excel": [make("0x1")]},
    )
    assert stamped[0].multi_source_agreement == "consistent"
    assert stamped[0].source_values["base_address"][0]["source"] == "excel"
    assert stamped[0].registers[0].multi_source_agreement == "conflict"

    consistent = _stamp_multi_source_semantics(
        [make("0x0")],
        {"word": [make("0x0")], "excel": [make("0x0")]},
    )
    assert consistent[0].multi_source_agreement == "consistent"
