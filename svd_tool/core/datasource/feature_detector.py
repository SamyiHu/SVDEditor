"""
外设功能差异检测器 — 从 Datasheet 文本提取各外设实例的功能差异。

Datasheet 里有明确的差异声明：
  "UART0和UART1支持DMA请求，UART2~5不支持DMA请求"
  "TIM1、TIM2、TIM6的定时器溢出及捕获事件可触发DMA请求"
  "UART2为完整的LIN接口"

提取这些规则，建立功能矩阵，供 SVD 生成时裁剪不存在的功能位域。
"""
from __future__ import annotations

import re
from typing import Any, Optional


# 实例号集合表示：如 "0,1"、"2~5"、"0/1"、"0~5"
_RANGE_RE = re.compile(r'(\d+)\s*[~～\-]\s*(\d+)')
_INST_RE = re.compile(r'\b(\d)\b')


class FeatureDetector:
    """从 Datasheet 文本和 TRM 位域描述提取外设功能差异。"""

    # 已知的外设前缀映射（Datasheet 里的简称 → SVD 外设名）
    PERIPH_PREFIXES = {
        'UART': 'UART', 'TIM': 'TIM', 'SPI': 'SPI', 'TWI': 'TWI',
        'PWM': 'PWM', 'DMA': 'DMA',
    }

    def detect(self, datasheet_path: str) -> dict:
        """从 Datasheet 提取功能矩阵。

        Returns:
            {periph_prefix: {instance_num: {feature: bool}}}
            如 {"UART": {0: {"DMA": True}, 3: {"DMA": False}, 2: {"LIN": True}}}
        """
        from docx import Document
        doc = Document(datasheet_path)
        features: dict[str, dict[int, dict[str, bool]]] = {}

        for p in doc.paragraphs:
            txt = p.text.strip()
            if not txt or len(txt) > 300:
                continue
            self._parse_feature_line(txt, features)

        return features

    def _parse_feature_line(self, txt: str, features: dict[str, dict[int, dict[str, bool]]]):
        """解析一行特征声明。"""
        # 模式："UART0和UART1支持DMA请求" / "UART2~5不支持DMA请求"
        # "TIM1、TIM2、TIM6可触发DMA请求"
        for prefix in self.PERIPH_PREFIXES:
            if prefix not in txt:
                continue
            # 找实例号
            insts = self._extract_instances(txt, prefix)
            if not insts:
                continue
            for feature in ('DMA', 'LIN'):
                if feature in txt:
                    has = not any(w in txt for w in ('不', '不能', '无法', '无'))
                    for inst in insts:
                        features.setdefault(prefix, {}).setdefault(inst, {})[feature] = has

    def _extract_instances(self, txt: str, prefix: str) -> list[int]:
        """从文本中提取外设实例号列表。
        "UART0和UART1" → [0,1]; "UART2~5" → [2,3,4,5]; "SPI0/1" → [0,1]
        """
        # 范围：2~5
        m = re.search(rf'{prefix}\s*(\d+)\s*[~～\-]\s*(\d+)', txt)
        if m:
            return list(range(int(m.group(1)), int(m.group(2)) + 1))
        # 列表：0、1、6 / 0/1 / 0和1
        # 先取所有跟在 prefix 后的单个数字
        nums = set()
        for m in re.finditer(rf'{re.escape(prefix)}\s*(\d+)', txt):
            nums.add(int(m.group(1)))
        # 也匹配 "UART0和1" 中的 "和1"（中文语境）
        for m in re.finditer(r'[和、,]\s*(\d+)', txt):
            nums.add(int(m.group(1)))
        return sorted(nums) if nums else []

    def get_feature(self, features: dict, prefix: str, instance: int,
                    feature: str) -> Optional[bool]:
        """查询某实例是否拥有某功能。None = 未声明。"""
        return features.get(prefix, {}).get(instance, {}).get(feature)

    def missing_features(self, features: dict, prefix: str,
                         instance: int) -> set[str]:
        """返回该实例缺失的功能（同系列中别的实例有、但本实例没有的）。"""
        fam = features.get(prefix, {})
        all_features: set[str] = set()
        for inst_feats in fam.values():
            all_features.update(inst_feats.keys())
        missing = set()
        for f in all_features:
            has = fam.get(instance, {}).get(f, True)  # 未声明默认有
            if not has:
                missing.add(f)
        return missing
