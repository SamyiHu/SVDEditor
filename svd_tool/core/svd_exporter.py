# svd_tool/core/svd_exporter.py
"""
SVD 文档导出器
支持将 SVD 数据导出为 CSV、Markdown、HTML 格式
用于生成寄存器描述文档（Datasheet / Reference Manual 用）
"""
import csv
import io
import logging
import os
from typing import Optional

from .data_model import DeviceInfo, Peripheral, Register, Field

logger = logging.getLogger("SVDExporter")


class SVDExporter:
    """SVD 文档导出器"""

    def __init__(self, device_info: DeviceInfo):
        self.device = device_info

    # ==================== CSV 导出 ====================

    def export_csv(self, file_path: str, peripheral_name: str = None) -> bool:
        """
        导出为 CSV 格式

        Args:
            file_path: 输出文件路径
            peripheral_name: 指定外设名称，None 则导出全部

        Returns:
            是否成功
        """
        try:
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                # 表头
                writer.writerow([
                    "外设名称", "外设描述", "外设基地址",
                    "寄存器名称", "寄存器描述", "偏移地址",
                    "复位值", "访问权限", "大小(位)",
                    "位域名称", "位域描述", "位偏移", "位宽",
                    "位域复位值", "位域访问权限"
                ])

                peripherals = self._get_peripherals(peripheral_name)
                for periph in peripherals:
                    for reg in periph.registers.values():
                        if not reg.fields:
                            # 无位域的寄存器也输出一行
                            writer.writerow([
                                periph.name, periph.description, periph.base_address,
                                reg.name, reg.description, reg.offset,
                                reg.reset_value, reg.access or "", reg.size,
                                "", "", "", "", "", ""
                            ])
                        else:
                            for fld in reg.fields.values():
                                writer.writerow([
                                    periph.name, periph.description, periph.base_address,
                                    reg.name, reg.description, reg.offset,
                                    reg.reset_value, reg.access or "", reg.size,
                                    fld.name, fld.description,
                                    fld.bit_offset, fld.bit_width,
                                    fld.reset_value, fld.access or ""
                                ])

            logger.info(f"CSV 导出成功: {file_path}")
            return True
        except Exception as e:
            logger.error(f"CSV 导出失败: {e}")
            return False

    def export_register_summary_csv(self, file_path: str) -> bool:
        """
        导出寄存器汇总 CSV（每个寄存器一行，无位域详情）
        适合快速概览所有寄存器
        """
        try:
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "外设名称", "外设基地址",
                    "寄存器名称", "偏移地址", "绝对地址",
                    "描述", "大小(位)", "访问权限", "复位值",
                    "位域数量"
                ])

                for periph in self.device.peripherals.values():
                    base = self._parse_hex(periph.base_address)
                    for reg in periph.registers.values():
                        offset = self._parse_hex(reg.offset)
                        abs_addr = (base + offset) if (base is not None and offset is not None) else ""
                        writer.writerow([
                            periph.name, periph.base_address,
                            reg.name, reg.offset,
                            f"0x{abs_addr:08X}" if isinstance(abs_addr, int) else "",
                            reg.description, reg.size,
                            reg.access or "", reg.reset_value,
                            len(reg.fields)
                        ])

            logger.info(f"寄存器汇总 CSV 导出成功: {file_path}")
            return True
        except Exception as e:
            logger.error(f"寄存器汇总导出失败: {e}")
            return False

    # ==================== Markdown 导出 ====================

    def export_markdown(self, file_path: str, peripheral_name: str = None) -> bool:
        """
        导出为 Markdown 格式（适合写入 Reference Manual）
        """
        try:
            lines = []
            device = self.device

            # 文档标题
            lines.append(f"# {device.name or 'Device'} 寄存器描述")
            lines.append("")
            lines.append(f"- **芯片型号**: {device.name}")
            lines.append(f"- **版本**: {device.version}")
            if device.vendor:
                lines.append(f"- **厂商**: {device.vendor}")
            if device.description:
                lines.append(f"- **描述**: {device.description}")
            lines.append(f"- **CPU**: {device.cpu.name}")
            lines.append(f"- **SVD版本**: {device.svd_version}")
            lines.append("")

            # 目录
            peripherals = self._get_peripherals(peripheral_name)
            lines.append("## 目录")
            lines.append("")
            for i, p in enumerate(peripherals, 1):
                anchor = p.name.lower().replace(' ', '-')
                lines.append(f"{i}. [{p.name}](#{anchor}) — 基地址: `{p.base_address}`")
            lines.append("")

            # 中断表
            if device.interrupts and not peripheral_name:
                lines.append("## 中断向量表")
                lines.append("")
                lines.append("| 中断号 | 名称 | 描述 | 关联外设 |")
                lines.append("|--------|------|------|----------|")
                sorted_irqs = sorted(device.interrupts.values(), key=lambda x: x.value)
                for irq in sorted_irqs:
                    periphs = ", ".join(irq.peripherals) if irq.peripherals else (irq.peripheral or "")
                    desc = (irq.description or "").replace("|", "\\|").replace("\n", " ")
                    lines.append(f"| {irq.value} | {irq.name} | {desc} | {periphs} |")
                lines.append("")

            # 各外设详情
            for periph in peripherals:
                lines.append(f"## {periph.name}")
                lines.append("")
                if periph.description:
                    lines.append(f"**描述**: {periph.description}")
                lines.append(f"**基地址**: `{periph.base_address}`")
                if periph.derived_from:
                    lines.append(f"**继承自**: `{periph.derived_from}`")
                lines.append("")

                # 寄存器汇总表
                lines.append("### 寄存器汇总")
                lines.append("")
                lines.append("| 名称 | 偏移 | 绝对地址 | 复位值 | 描述 |")
                lines.append("|------|------|----------|--------|------|")
                base = self._parse_hex(periph.base_address)
                for reg in periph.registers.values():
                    offset = self._parse_hex(reg.offset)
                    abs_addr = f"0x{(base + offset):08X}" if (base is not None and offset is not None) else ""
                    desc = (reg.description or "").replace("|", "\\|").replace("\n", " ")
                    lines.append(f"| {reg.name} | {reg.offset} | `{abs_addr}` | `{reg.reset_value}` | {desc} |")
                lines.append("")

                # 各寄存器位域详情
                for reg in periph.registers.values():
                    lines.append(f"### {periph.name}_{reg.name}")
                    lines.append("")
                    if reg.description:
                        lines.append(f"**描述**: {reg.description}")
                    lines.append(f"- **偏移地址**: `{reg.offset}`")
                    lines.append(f"- **大小**: {reg.size} 位")
                    if reg.access:
                        lines.append(f"- **访问权限**: {reg.access}")
                    lines.append(f"- **复位值**: `{reg.reset_value}`")
                    lines.append("")

                    if reg.fields:
                        lines.append("| 位 | 名称 | 宽度 | 访问 | 复位值 | 描述 |")
                        lines.append("|----|------|------|------|--------|------|")
                        sorted_fields = sorted(reg.fields.values(), key=lambda f: f.bit_offset, reverse=True)
                        for fld in sorted_fields:
                            end_bit = fld.bit_offset + fld.bit_width - 1
                            if fld.bit_width == 1:
                                bit_range = str(fld.bit_offset)
                            else:
                                bit_range = f"{end_bit}:{fld.bit_offset}"
                            desc = (fld.description or "").replace("|", "\\|").replace("\n", " ")
                            lines.append(
                                f"| {bit_range} | {fld.name} | {fld.bit_width} "
                                f"| {fld.access or reg.access or '-'} "
                                f"| `{fld.reset_value}` | {desc} |"
                            )
                        lines.append("")

            content = "\n".join(lines)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            logger.info(f"Markdown 导出成功: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Markdown 导出失败: {e}")
            return False

    # ==================== HTML 导出 ====================

    def export_html(self, file_path: str, peripheral_name: str = None) -> bool:
        """
        导出为 HTML 格式（带样式，可直接在浏览器查看）
        """
        try:
            device = self.device
            peripherals = self._get_peripherals(peripheral_name)

            html = []
            html.append("<!DOCTYPE html>")
            html.append("<html lang='zh-CN'>")
            html.append("<head>")
            html.append("<meta charset='UTF-8'>")
            html.append(f"<title>{device.name or 'Device'} 寄存器描述</title>")
            html.append("<style>")
            html.append(self._get_html_css())
            html.append("</style>")
            html.append("</head><body>")

            # 标题
            html.append(f"<h1>{device.name or 'Device'} 寄存器描述</h1>")
            html.append("<div class='meta'>")
            html.append(f"<span>芯片: <b>{device.name}</b></span>")
            html.append(f"<span>版本: {device.version}</span>")
            if device.vendor:
                html.append(f"<span>厂商: {device.vendor}</span>")
            html.append(f"<span>CPU: {device.cpu.name}</span>")
            html.append("</div>")

            # 目录
            html.append("<h2 id='toc'>目录</h2>")
            html.append("<ul class='toc'>")
            for p in peripherals:
                anchor = p.name.lower().replace(' ', '-')
                html.append(f"<li><a href='#{anchor}'>{p.name}</a> — 基地址: <code>{p.base_address}</code></li>")
            html.append("</ul>")

            # 中断表
            if device.interrupts and not peripheral_name:
                html.append("<h2>中断向量表</h2>")
                html.append("<table><thead><tr><th>中断号</th><th>名称</th><th>描述</th><th>关联外设</th></tr></thead><tbody>")
                sorted_irqs = sorted(device.interrupts.values(), key=lambda x: x.value)
                for irq in sorted_irqs:
                    periphs = ", ".join(irq.peripherals) if irq.peripherals else (irq.peripheral or "")
                    html.append(f"<tr><td>{irq.value}</td><td>{irq.name}</td><td>{irq.description or ''}</td><td>{periphs}</td></tr>")
                html.append("</tbody></table>")

            # 各外设
            for periph in peripherals:
                anchor = periph.name.lower().replace(' ', '-')
                html.append(f"<h2 id='{anchor}'>{periph.name}</h2>")
                if periph.description:
                    html.append(f"<p><em>{periph.description}</em></p>")
                html.append(f"<p>基地址: <code>{periph.base_address}</code>")
                if periph.derived_from:
                    html.append(f" | 继承自: <code>{periph.derived_from}</code>")
                html.append("</p>")

                # 寄存器汇总
                html.append(f"<h3>寄存器汇总 ({len(periph.registers)} 个)</h3>")
                html.append("<table><thead><tr><th>名称</th><th>偏移</th><th>绝对地址</th><th>复位值</th><th>描述</th></tr></thead><tbody>")
                base = self._parse_hex(periph.base_address)
                for reg in periph.registers.values():
                    offset = self._parse_hex(reg.offset)
                    abs_addr = f"0x{(base + offset):08X}" if (base is not None and offset is not None) else ""
                    html.append(f"<tr><td>{reg.name}</td><td><code>{reg.offset}</code></td><td><code>{abs_addr}</code></td><td><code>{reg.reset_value}</code></td><td>{reg.description or ''}</td></tr>")
                html.append("</tbody></table>")

                # 位域详情
                for reg in periph.registers.values():
                    if not reg.fields:
                        continue
                    html.append(f"<h4>{periph.name}_{reg.name}</h4>")
                    html.append(f"<p>{reg.description or ''} | 大小: {reg.size}位 | 复位值: <code>{reg.reset_value}</code></p>")
                    html.append("<table><thead><tr><th>位</th><th>名称</th><th>宽度</th><th>访问</th><th>复位值</th><th>描述</th></tr></thead><tbody>")
                    sorted_fields = sorted(reg.fields.values(), key=lambda f: f.bit_offset, reverse=True)
                    for fld in sorted_fields:
                        end_bit = fld.bit_offset + fld.bit_width - 1
                        bit_range = str(fld.bit_offset) if fld.bit_width == 1 else f"{end_bit}:{fld.bit_offset}"
                        html.append(f"<tr><td>{bit_range}</td><td>{fld.name}</td><td>{fld.bit_width}</td><td>{fld.access or reg.access or '-'}</td><td><code>{fld.reset_value}</code></td><td>{fld.description or ''}</td></tr>")
                    html.append("</tbody></table>")

            html.append("</body></html>")

            content = "\n".join(html)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            logger.info(f"HTML 导出成功: {file_path}")
            return True
        except Exception as e:
            logger.error(f"HTML 导出失败: {e}")
            return False

    # ==================== 辅助方法 ====================

    def _get_peripherals(self, peripheral_name: str = None) -> list:
        """获取要导出的外设列表"""
        if peripheral_name:
            if peripheral_name in self.device.peripherals:
                return [self.device.peripherals[peripheral_name]]
            return []
        return list(self.device.peripherals.values())

    @staticmethod
    def _parse_hex(value) -> Optional[int]:
        """解析十六进制或十进制数值"""
        if value is None:
            return None
        try:
            s = str(value).strip()
            if not s:
                return None
            if s.lower().startswith("0x"):
                return int(s, 16)
            return int(s)
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def _get_html_css() -> str:
        """返回 HTML 导出的 CSS 样式"""
        return """
        body { font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif; margin: 20px 40px; color: #333; background: #fff; }
        h1 { color: #1a5276; border-bottom: 3px solid #2980b9; padding-bottom: 10px; }
        h2 { color: #2c3e50; border-bottom: 1px solid #bdc3c7; padding-bottom: 5px; margin-top: 40px; }
        h3 { color: #34495e; margin-top: 25px; }
        h4 { color: #555; margin-top: 20px; background: #f8f9fa; padding: 5px 10px; border-left: 3px solid #2980b9; }
        .meta { display: flex; gap: 20px; flex-wrap: wrap; margin: 10px 0 20px; padding: 10px; background: #f0f3f5; border-radius: 4px; }
        .meta span { font-size: 14px; }
        table { border-collapse: collapse; width: 100%; margin: 10px 0 20px; font-size: 13px; }
        th { background: #2c3e50; color: white; padding: 8px 12px; text-align: left; }
        td { padding: 6px 12px; border-bottom: 1px solid #ddd; }
        tr:nth-child(even) { background: #f8f9fa; }
        tr:hover { background: #eaf2f8; }
        code { background: #ecf0f1; padding: 2px 6px; border-radius: 3px; font-size: 12px; }
        .toc { columns: 2; }
        .toc li { margin: 4px 0; }
        a { color: #2980b9; text-decoration: none; }
        a:hover { text-decoration: underline; }
        @media print { body { margin: 0; } h2 { page-break-before: auto; } table { page-break-inside: avoid; } }
        """
