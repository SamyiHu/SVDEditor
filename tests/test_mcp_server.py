#!/usr/bin/env python3
"""MCP Server 测试 — headless 工作区全链路 + FastMCP 工具注册。

不依赖 PyQt / 图形环境。
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from svd_tool.mcp_server.headless_workspace import HeadlessWorkspace

STM32 = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "test_data", "STM32F103xx.svd")


@pytest.fixture
def ws():
    return HeadlessWorkspace()


class TestDocuments:
    def test_open_info_and_list(self, ws):
        r = ws.open_document(STM32)
        assert r["success"], r["message"]
        assert r["data"]["statistics"]["peripherals"] > 0

        info = ws.device_info()
        assert info["success"]
        assert info["data"]["device"]["name"]
        assert len(info["data"]["peripherals"]) == info["data"]["statistics"]["peripherals"]

        docs = ws.list_documents()
        assert docs["success"] and docs["data"][0]["active"] is True

    def test_open_missing_file(self, ws):
        r = ws.open_document("Z:/not/exist.svd")
        assert not r["success"]

    def test_doc_id_dedup_and_switch(self, ws):
        ws.open_document(STM32)
        r2 = ws.open_document(STM32)  # 同名文件再开一次
        assert r2["data"]["doc_id"].startswith("STM32F103xx-")

        ws.switch_document("STM32F103xx")
        info = ws.device_info()
        assert info["data"]["doc_id"] == "STM32F103xx"

    def test_no_document_open(self, ws):
        assert not ws.device_info()["success"]
        assert not ws.add_peripheral("X")["success"]


class TestQuery:
    def test_search_and_getters(self, ws):
        ws.open_document(STM32)

        s = ws.search("gpio", search_type="peripheral")
        assert s["success"] and s["data"]["total"] >= 1

        p = ws.get_peripheral("GPIOA")
        assert p["success"] and p["data"]["register_count"] > 0

        reg_name = p["data"]["registers"][0]["name"]
        r = ws.get_register("GPIOA", reg_name)
        assert r["success"] and "fields" in r["data"]

        if r["data"]["fields"]:
            f = ws.get_field("GPIOA", reg_name, r["data"]["fields"][0]["name"])
            assert f["success"]

        irq = ws.list_interrupts()
        assert irq["success"] and irq["data"]["total"] > 0

    def test_search_pagination(self, ws):
        ws.open_document(STM32)
        s1 = ws.search("I", search_type="all", limit=5)
        assert len(s1["data"]["results"]) <= 5
        if s1["data"]["has_more"]:
            s2 = ws.search("I", search_type="all", limit=5, offset=5)
            assert s2["data"]["results"]

    def test_missing_targets(self, ws):
        ws.open_document(STM32)
        assert not ws.get_peripheral("NOPE")["success"]
        assert not ws.get_register("GPIOA", "NOPE")["success"]


class TestEdit:
    def test_full_crud_roundtrip(self, ws, tmp_path):
        ws.open_document(STM32)

        # 外设
        assert ws.add_peripheral("TESTP", base_address="0x50001000")["success"]
        assert not ws.add_peripheral("TESTP")["success"]  # 重名
        assert ws.update_peripheral("TESTP", {"name": "TESTP2", "description": "test"})["success"]
        assert "TESTP2" in ws.device_info()["data"]["peripherals"][-1]["name"] or \
            any(p["name"] == "TESTP2" for p in ws.device_info()["data"]["peripherals"])

        # 寄存器
        assert ws.add_register("TESTP2", "CTRL", offset="0x04",
                               description="control")["success"]
        assert ws.update_register("TESTP2", "CTRL",
                                  {"name": "CTRL2", "size": "0x10"})["success"]

        # 位域
        assert ws.add_field("TESTP2", "CTRL2", "EN", bit_offset=0, bit_width=1)["success"]
        assert ws.update_field("TESTP2", "CTRL2", "EN",
                               {"bit_width": 2, "description": "enable"})["success"]

        # 中断
        assert ws.add_interrupt("TEST_IRQ", 55, peripherals=["TESTP2"])["success"]
        assert ws.update_interrupt("TEST_IRQ", {"value": 56})["success"]

        # 校验 + 保存 + 重开验证持久化
        v = ws.validate()
        assert v["success"]

        out = tmp_path / "roundtrip.svd"
        save = ws.save_document(path=str(out))
        assert save["success"], save["message"]
        assert out.is_file()

        ws2 = HeadlessWorkspace()
        ws2.open_document(str(out))
        reg = ws2.get_register("TESTP2", "CTRL2")
        assert reg["success"]
        assert reg["data"]["size"] == "0x10"
        fld = ws2.get_field("TESTP2", "CTRL2", "EN")
        assert fld["success"] and fld["data"]["bit_width"] == 2
        irq = ws2.list_interrupts()
        assert any(i["name"] == "TEST_IRQ" and i["value"] == 56
                   for i in irq["data"]["interrupts"])

        # 删除链
        assert ws.remove_field("TESTP2", "CTRL2", "EN")["success"]
        assert ws.remove_register("TESTP2", "CTRL2")["success"]
        assert ws.remove_peripheral("TESTP2")["success"]
        assert not ws.get_peripheral("TESTP2")["success"]

    def test_save_backup(self, ws, tmp_path):
        target = tmp_path / "bak.svd"
        ws.open_document(STM32)
        ws.save_document(path=str(target))
        ws.add_peripheral("BAKP")
        ws.save_document(path=str(target))
        bak = tmp_path / "bak.svd.bak"
        assert bak.is_file()  # 第二次覆盖前备份了第一版
        # 备份里没有 BAKP，新文件里有
        ws3 = HeadlessWorkspace()
        ws3.open_document(str(bak))
        assert not ws3.get_peripheral("BAKP")["success"]
        ws4 = HeadlessWorkspace()
        ws4.open_document(str(target))
        assert ws4.get_peripheral("BAKP")["success"]

    def test_rename_conflicts_and_derived_from(self, ws):
        ws.open_document(STM32)
        assert not ws.update_peripheral("GPIOA", {"name": "GPIOB"})["success"]  # 目标名已存在
        assert not ws.update_peripheral("GPIOA", {"derived_from": "GPIOA"})["success"]  # 自引用


class TestDiffAndExport:
    def test_diff_detects_change(self, ws, tmp_path):
        ws.open_document(STM32)          # STM32F103xx
        modified = tmp_path / "mod.svd"
        ws.add_peripheral("DIFFP", base_address="0x50002000")
        ws.save_document(path=str(modified))
        ws.open_document(str(modified))  # doc_id: mod

        r = ws.diff("STM32F103xx", "mod")
        assert r["success"]
        assert any("DIFFP" in (item.get("path") or "") for item in r["data"]["items"])

        rp = ws.diff("STM32F103xx", "mod", peripheral="DIFFP")
        assert rp["success"]

    def test_export_and_header(self, ws, tmp_path):
        ws.open_document(STM32)

        csv_path = tmp_path / "gpio.csv"
        r = ws.export("csv", out_path=str(csv_path), peripheral="GPIOA")
        assert r["success"] and csv_path.is_file()

        md_path = tmp_path / "doc.md"
        assert ws.export("markdown", out_path=str(md_path))["success"] and md_path.is_file()

        h_path = tmp_path / "dev.h"
        h = ws.generate_header(out_path=str(h_path))
        assert h["success"] and h_path.is_file() and h["data"]["lines"] > 10

        preview = ws.generate_header()
        assert preview["success"] and preview["data"]["preview"]

        assert not ws.export("xml")["success"]  # 不支持的格式


class TestFastMCPServer:
    def test_tools_registered(self):
        from svd_tool.mcp_server import mcp

        tools = asyncio.run(mcp.list_tools())
        names = [t.name for t in tools]
        assert len(names) >= 25
        assert all(n.startswith("svd_") for n in names)
        for must in ("svd_open", "svd_device_info", "svd_get_register",
                     "svd_add_field", "svd_validate", "svd_save_document",
                     "svd_export", "svd_diff"):
            assert must in names, f"missing tool: {must}"

    def test_tool_call_roundtrip(self):
        """通过 MCPServer 的 call_tool 走一遍完整链路（不经 stdio）。"""
        from svd_tool.mcp_server import mcp

        async def _run():
            import json as _json

            res = await mcp.call_tool("svd_open", {"path": STM32})
            # mcp 2.x 返回 CallToolResult；1.x 返回 tuple，兼容两者
            data = getattr(res, "structured_content", None)
            if data is None and getattr(res, "content", None):
                data = _json.loads(res.content[0].text)
            if data is None and isinstance(res, tuple):
                data = res[1]
            assert data and data.get("success"), f"svd_open failed: {data}"
            return data

        asyncio.run(_run())
