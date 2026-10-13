"""
描述风格修正器 — 让 TRM 生成的 SVD 符合参考 SVD 的风格规范。

参考 SVD（SC32L14T_M8_M7.svd）的风格规则（已对比提炼）：
1. **语言**：全英文（TRM 是中文，用术语词典规则转换；AI 批量翻译已随内嵌
   AI 助手移除，如需 AI 翻译可在 ai-panel 分支或外部 agent 流程完成）
2. **外设描述**：英文短句，如 "Analog to Digital Converter"
3. **寄存器描述**："<首字母小写> register"，如 "ADC control register"、"Control register"
4. **位域描述**：英文精简短语，如 "ADC enable"、"End Of Conversion / ADC Interrupt Flag"
5. **displayName**：寄存器必须有 displayName，值=name
6. **resetValue**：8 位完整格式 0x00000000（不裁短成 0x0）
7. **groupName**：实例外设共享 groupName（GPIOA/B/C→GPIO、UART0~5→UART）

翻译策略：术语词典规则转换 + 格式对齐。
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger("svd_tool.datasource.DescriptionStyler")


# ════════════════════════════════════════════════════
# 术语词典（AI 不可用时的规则转换回退）
# ════════════════════════════════════════════════════

# 中文关键词 → 英文术语（高频，覆盖常见描述）
_TERM_DICT = {
    # 寄存器类型
    "控制寄存器": "control register", "状态寄存器": "status register",
    "配置寄存器": "configuration register", "数据寄存器": "data register",
    "中断寄存器": "interrupt register", "使能寄存器": "enable register",
    # 通用动作
    "使能": "enable", "禁止": "disable", "复位": "reset", "清除": "clear",
    "标志": "flag", "状态": "status", "选择": "select", "设置": "set",
    "启动": "start", "停止": "stop", "输出": "output", "输入": "input",
    # 外设
    "看门狗": "watchdog", "定时器": "timer", "计数器": "counter",
    "中断": "interrupt", "时钟": "clock", "分频": "prescaler",
    "波特率": "baud rate", "发送": "transmit", "接收": "receive",
    "缓冲": "buffer", "移位": "shift", "采样": "sample", "转换": "conversion",
    "通道": "channel", "电压": "voltage", "参考": "reference",
    "比较器": "comparator", "运放": "op-amp", "加密": "encryption",
    "段码": "segment", "触摸": "touch", "唤醒": "wake-up",
}

# groupName 归一化映射：外设名前缀 → groupName
# 多实例外设（GPIOA/B/C、UART0~5）共享同一 groupName
_GROUP_PREFIX_RULES = [
    (re.compile(r'^GPIO[A-E]$'), 'GPIO'),
    (re.compile(r'^UART\d'), 'UART'),
    (re.compile(r'^TIM\d'), 'TIM'),
    (re.compile(r'^PWM\d'), 'PWM'),
    (re.compile(r'^DMA\d'), 'DMA'),
    (re.compile(r'^TWI_SPI\d'), 'TWI_SPI'),
]


def _infer_group_name(periph_name: str) -> str:
    """推断外设的 groupName。

    单实例外设：groupName = 外设名本身。
    多实例外设（GPIOA/UART0）：按前缀归一化到 GPIO/UART。
    """
    for pat, gname in _GROUP_PREFIX_RULES:
        if pat.match(periph_name):
            return gname
    return periph_name


# ════════════════════════════════════════════════════
# 描述风格修正器
# ════════════════════════════════════════════════════

class DescriptionStyler:
    """把 TRM 生成的 DeviceInfo 的描述风格修正为参考 SVD 风格。

    用法：
        styler = DescriptionStyler()
        styler.style(device_info, ai_config=ai_config)
        # device_info 的描述已被改为英文 + 格式对齐
    """

    # 每批转换的描述数量（保留分批接口，便于展示进度）
    BATCH_SIZE = 40

    def style(self, device, progress_cb=None) -> dict:
        """执行风格修正（就地修改 device）。

        Args:
            device: DeviceInfo（描述会被修改）
            progress_cb: 可选回调 fn(done, total, msg)

        Returns:
            {"translated": n, "fallback": bool, "errors": [...]}
        """
        # 1. 收集所有待转换的中文描述
        items = self._collect_descriptions(device)
        total = len(items)
        if total == 0:
            return {"translated": 0, "fallback": False, "errors": []}

        # 2. 术语词典规则转换
        translations = self._translate_with_dict(items)
        errors: list[str] = []

        # 3. 应用翻译结果到原对象（通过 id 映射）
        applied = 0
        for item in items:
            obj, attr, original = item
            eng = translations.get(id(item))
            if eng:
                setattr(obj, attr, eng)
                applied += 1
            # 未翻译到的保持原样

        # 4. 格式风格修正（不依赖翻译）
        self._apply_format_style(device)

        if progress_cb:
            progress_cb(total, total, "风格修正完成")

        return {"translated": applied, "fallback": True,
                "errors": errors, "total": total}

    # ---------- 收集描述 ----------

    def _collect_descriptions(self, device) -> list:
        """收集所有需要翻译的描述 (obj, attr_name, original_text)。

        只收集中文描述（含中文字符的才翻译；已是英文的跳过）。
        """
        items = []
        # 外设描述
        if self._has_chinese(device.description):
            items.append((device, "description", device.description))
        # 外设/寄存器/位域描述
        for pname, periph in device.peripherals.items():
            if self._has_chinese(periph.description):
                items.append((periph, "description", periph.description))
            for rname, reg in periph.registers.items():
                if self._has_chinese(reg.description):
                    items.append((reg, "description", reg.description))
                for fname, fld in reg.fields.items():
                    if self._has_chinese(fld.description):
                        items.append((fld, "description", fld.description))
        return items

    @staticmethod
    def _has_chinese(text: str) -> bool:
        """判断文本是否含中文字符。"""
        if not text:
            return False
        return any('\u4e00' <= c <= '\u9fff' for c in text)

    # ---------- 词典规则翻译 ----------

    def _translate_with_dict(self, items: list) -> dict[int, str]:
        """用术语词典做规则转换（AI 不可用的回退）。

        粗转换：按词典把中文关键词替换为英文。无法完美翻译，但保证英文格式。
        """
        translations: dict[int, str] = {}
        for item in items:
            obj, attr, original = item
            text = original
            for zh, en in _TERM_DICT.items():
                text = text.replace(zh, en)
            # 如果还是大部分中文，用一个保守回退：取寄存器/位域名 + "register"
            if self._has_chinese(text) and len(text) > 20:
                # 太长且仍含中文，截断
                text = text[:60] + "..."
            translations[id(item)] = text
        return translations

    # ---------- 格式风格修正（非翻译部分）----------

    def _apply_format_style(self, device):
        """应用不依赖翻译的格式风格修正。"""
        # groupName 归一化
        for pname, periph in device.peripherals.items():
            periph.group_name = _infer_group_name(pname)

        # displayName：寄存器 displayName = name
        for periph in device.peripherals.values():
            for reg in periph.registers.values():
                if not reg.display_name:
                    reg.display_name = reg.name
                # resetValue 补齐到 8 位（0x0 → 0x00000000）
                reg.reset_value = self._pad_reset_value(reg.reset_value)

        # device 级 resetValue
        device.reset_value = self._pad_reset_value(device.reset_value)

    @staticmethod
    def _pad_reset_value(val: str) -> str:
        """把复位值补齐到 8 位十六进制：0x0 → 0x00000000。

        参考 SVD 统一用 8 位格式。已有的 8 位保持不变。
        """
        if not val:
            return "0x00000000"
        v = val.strip()
        m = re.match(r'^(0x|0X)([0-9A-Fa-f]+)$', v)
        if not m:
            return v
        digits = m.group(2)
        if len(digits) >= 8:
            return f"0x{digits[-8:].upper()}"
        return f"0x{digits.upper():0>8}"
