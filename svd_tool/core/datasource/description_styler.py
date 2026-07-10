"""
描述风格修正器 — 让 TRM 生成的 SVD 符合参考 SVD 的风格规范。

参考 SVD（SC32L14T_M8_M7.svd）的风格规则（已对比提炼）：
1. **语言**：全英文（TRM 是中文，需 AI 翻译）
2. **外设描述**：英文短句，如 "Analog to Digital Converter"
3. **寄存器描述**："<首字母小写> register"，如 "ADC control register"、"Control register"
4. **位域描述**：英文精简短语，如 "ADC enable"、"End Of Conversion / ADC Interrupt Flag"
5. **displayName**：寄存器必须有 displayName，值=name
6. **resetValue**：8 位完整格式 0x00000000（不裁短成 0x0）
7. **groupName**：实例外设共享 groupName（GPIOA/B/C→GPIO、UART0~5→UART）

翻译策略：批量调用 AI（一次翻译多条描述，降低 API 成本）。
AI 不可用时回退到术语词典规则转换。
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

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

    # 每批翻译的描述数量（控制单次 AI 请求大小）
    BATCH_SIZE = 40

    def style(self, device, ai_config=None, progress_cb=None) -> dict:
        """执行风格修正（就地修改 device）。

        Args:
            device: DeviceInfo（描述会被修改）
            ai_config: AIConfig，提供则用 AI 翻译；None 则用词典回退
            progress_cb: 可选回调 fn(done, total, msg)

        Returns:
            {"translated": n, "fallback": bool, "errors": [...]}
        """
        # 1. 收集所有待翻译的中文描述
        items = self._collect_descriptions(device)
        total = len(items)
        if total == 0:
            return {"translated": 0, "fallback": False, "errors": []}

        # 2. 翻译（AI 或词典回退）
        translations: dict[int, str] = {}  # id(item) → 英文
        used_fallback = False
        if ai_config is not None:
            translations, errors = self._translate_with_ai(items, ai_config, progress_cb)
            if not translations:
                logger.warning("AI 翻译无结果，回退到词典转换")
                used_fallback = True
                translations = self._translate_with_dict(items)
                errors = []
        else:
            used_fallback = True
            translations = self._translate_with_dict(items)
            errors = []

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

        return {"translated": applied, "fallback": used_fallback,
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

    # ---------- AI 批量翻译 ----------

    def _translate_with_ai(self, items: list, ai_config, progress_cb=None) -> tuple[dict, list]:
        """用 AI 批量翻译描述。返回 ({id(item): 英文}, errors)。"""
        from ...ai_assistant.backend import create_backend
        try:
            backend = create_backend(ai_config.api_type)
        except Exception as e:
            logger.warning(f"AI backend 创建失败: {e}")
            return {}, [str(e)]

        translations: dict[int, str] = {}
        errors: list[str] = []
        # 分批
        batches = [items[i:i + self.BATCH_SIZE] for i in range(0, len(items), self.BATCH_SIZE)]
        for bi, batch in enumerate(batches):
            if progress_cb:
                done = bi * self.BATCH_SIZE
                progress_cb(done, len(items), f"AI 翻译批次 {bi+1}/{len(batches)}")
            try:
                result = self._translate_batch(backend, batch, ai_config)
                translations.update(result)
            except Exception as e:
                msg = f"批次 {bi+1} 翻译失败: {e}"
                logger.warning(msg)
                errors.append(msg)
        return translations, errors

    def _translate_batch(self, backend, batch: list, ai_config) -> dict[int, str]:
        """翻译一批描述。用 JSON 数组让 AI 返回结构化结果。"""
        # 构造输入：编号→中文
        input_map = {}
        for i, item in enumerate(batch):
            input_map[str(i)] = item[2][:500]  # 限制长度，超长的截断
        prompt = (
            "You are translating embedded MCU register descriptions from Chinese to English.\n"
            "Style rules (match CMSIS-SVD convention, be VERY concise):\n"
            "- Field description: a SHORT noun phrase only. 3-6 words typically.\n"
            "  Examples: 'ADC enable', 'VREFS select', 'Receive interrupt flag', 'DMA enable', 'Port mode bits'.\n"
            "- Register description: '<function> register'. Examples: 'ADC control register', 'Status register'.\n"
            "- Peripheral description: short English name. Examples: 'Analog to Digital Converter', 'Watchdog'.\n"
            "- CRITICAL: Drop ALL enumerated values and detailed explanations.\n"
            "  '参考电压选择控制位 00：选择VDD 01：...' -> 'Reference voltage selection' (NOT '00: VDD').\n"
            "  '使能位 0：关闭 1：开启' -> 'Enable'.\n"
            "  Keep only the core functional meaning; no value tables, no bit-by-bit explanations.\n"
            "- Keep register/field NAMES and hex values (0x...) unchanged.\n"
            "- Average description length: under 30 characters. Never exceed 60.\n"
            "Return ONLY a JSON object mapping input number to English translation. No markdown.\n\n"
            f"Input:\n{json.dumps(input_map, ensure_ascii=False)}"
        )
        messages = [{"role": "user", "content": prompt}]
        resp = backend.chat(messages, ai_config)
        content = resp.get("content", "").strip()
        # 去除可能的 markdown 代码块标记
        if content.startswith("```"):
            content = re.sub(r'^```(?:json)?\s*', '', content)
            content = re.sub(r'\s*```$', '', content)
        try:
            result_map = json.loads(content)
        except json.JSONDecodeError:
            # 尝试提取 JSON 对象
            m = re.search(r'\{[\s\S]*\}', content)
            if m:
                try:
                    result_map = json.loads(m.group(0))
                except json.JSONDecodeError:
                    return {}
            else:
                return {}
        # 映射回 id(item)
        out: dict[int, str] = {}
        for i, item in enumerate(batch):
            eng = result_map.get(str(i)) or result_map.get(i)
            if eng and isinstance(eng, str):
                out[id(item)] = eng.strip()
        return out

    # ---------- 词典回退翻译 ----------

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
