"""CMSIS/C 固件头文件解析器。

目标不是一次性生成完美 SVD，而是提取可审计的结构骨架：
- 外设实例与基地址；
- typedef 内寄存器成员、偏移、数组；
- *_Pos/_Msk 位域（按外设实例 + 寄存器成员挂载）；
- IRQn 中断映射；
- 每个字段的原始行号和原始文本，供人工纠错。

所有无法解析的条目一律进入 model.unresolved，不允许静默丢弃。
表达式求值只支持 +、- 与有限层括号（tokenizer + 递归下降），禁止 eval。
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


def normalize_identifier(value: str) -> str:
    value = (value or "").upper().strip()
    value = value.split("@", 1)[0]
    value = re.sub(r"[^A-Z0-9_]+", "", value)
    return value


def peripheral_root(name: str) -> str:
    return re.sub(r"\d+$", "", normalize_identifier(name))


def register_root(name: str, peripheral: str = "") -> str:
    raw = normalize_identifier(name)
    if not raw:
        return ""
    root = peripheral_root(peripheral)
    if root and len(raw) > len(root):
        pattern = re.compile(r"^" + re.escape(root) + r"(?:\d+)?(?:_?)(.+)$")
        match = pattern.match(raw)
        if match and match.group(1):
            raw = match.group(1)
    return raw.strip("_") or normalize_identifier(name)


def _strip_comments(line: str) -> str:
    line = re.sub(r"/\*.*?\*/", " ", line)
    line = re.sub(r"//.*$", "", line)
    return line.strip()


def _numeric_literal(expr: str) -> Optional[int]:
    match = re.fullmatch(r"(0[xX][0-9A-Fa-f]+|\d+)[UuLl]*", expr.strip())
    if not match:
        return None
    token = match.group(1)
    return int(token, 16) if token.lower().startswith("0x") else int(token)


# ════════════════════════════════════════════════════
# 受限表达式求值（+、-、有限括号；无 eval）
# ════════════════════════════════════════════════════

_NUMBER_TOKEN_RE = re.compile(r"(0[xX][0-9A-Fa-f]+|\d+)[UuLl]*")
_IDENT_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_MAX_PAREN_DEPTH = 3


def _tokenize_expression(text: str) -> Optional[list]:
    """把纯数字/运算符表达式拆成 token；出现未知符号或不支持的运算符返回 None。"""
    tokens: list = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch in "+-()":
            tokens.append(ch)
            i += 1
            continue
        match = _NUMBER_TOKEN_RE.match(text, i)
        if match:
            literal = match.group(1)
            tokens.append(("num", int(literal, 16 if literal.lower().startswith("0x") else 10)))
            i = match.end()
            continue
        if _IDENT_TOKEN_RE.match(text[i:]):
            # 词边界替换后仍有符号残留 → 无法求值
            return None
        # 其余字符（* / << 等）不支持
        return None
    return tokens


def _parse_sum(tokens: list, pos: int, depth: int) -> tuple[Optional[int], int]:
    """expr := [+|-] term (('+'|'-') term)*"""
    sign = 1
    if pos < len(tokens) and tokens[pos] in ("+", "-"):
        sign = -1 if tokens[pos] == "-" else 1
        pos += 1
    value, pos = _parse_term(tokens, pos, depth)
    if value is None:
        return None, pos
    total = sign * value
    while pos < len(tokens) and tokens[pos] in ("+", "-"):
        op = tokens[pos]
        pos += 1
        value, pos = _parse_term(tokens, pos, depth)
        if value is None:
            return None, pos
        total = total + value if op == "+" else total - value
    return total, pos


def _parse_term(tokens: list, pos: int, depth: int) -> tuple[Optional[int], int]:
    if depth > _MAX_PAREN_DEPTH:
        return None, pos
    if pos < len(tokens) and tokens[pos] == "(":
        value, nxt = _parse_sum(tokens, pos + 1, depth + 1)
        if value is None or nxt >= len(tokens) or tokens[nxt] != ")":
            return None, pos
        return value, nxt + 1
    if pos < len(tokens) and isinstance(tokens[pos], tuple) and tokens[pos][0] == "num":
        return tokens[pos][1], pos + 1
    return None, pos


def _balanced_parens(text: str) -> bool:
    depth = 0
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def _safe_sum_expression(expr: str, symbols: dict[str, int]) -> Optional[int]:
    """求值形如 SYMBOL + (0x20UL) 的地址表达式。

    支持：普通 SYMBOL/NUMBER、SYMBOL + (NUMBER)、一层嵌套括号 (A + (0x20))、
    UL/U/L 后缀。符号替换严格按词边界（AHBPERIPH_BASE 不会被 PERIPH_BASE 误替换）。
    出现未知符号、不支持的运算符或括号过深 → 返回 None（调用方记 unresolved）。
    """
    text = _strip_comments(expr)
    text = re.sub(r"\s+", "", text)
    if not text:
        return None
    # 词边界替换已知符号；长名优先，多轮直到稳定（符号值依赖链）
    for _ in range(8):
        replaced = False
        for name in sorted(symbols, key=len, reverse=True):
            pattern = re.compile(
                r"(?<![A-Za-z0-9_])" + re.escape(name) + r"(?![A-Za-z0-9_])")
            new_text = pattern.sub(str(symbols[name]), text)
            if new_text != text:
                text = new_text
                replaced = True
        if not replaced:
            break
    tokens = _tokenize_expression(text)
    if tokens is None:
        return None
    value, pos = _parse_sum(tokens, 0, 0)
    if value is None or pos != len(tokens):
        return None
    return value


# ════════════════════════════════════════════════════
# 数据模型
# ════════════════════════════════════════════════════

@dataclass
class HeaderField:
    name: str
    register: str
    peripheral: str
    bit_offset: int
    bit_width: int
    line_number: int
    raw_text: str
    mask: int = 0
    object_id: str = ""
    semantic_path: str = ""

    def __post_init__(self):
        self.object_id = hashlib.sha256(
            f"{self.peripheral}/{self.register}/{self.name}/{self.bit_offset}".encode()
        ).hexdigest()[:20]
        self.semantic_path = "/".join(x for x in (
            self.peripheral, self.register, self.name) if x)


@dataclass
class HeaderRegister:
    name: str
    peripheral: str
    offset: int
    line_number: int
    raw_text: str
    fields: list[HeaderField] = field(default_factory=list)
    array_length: int = 0            # >0 表示数组寄存器（如 PWM_DT[32]）
    description: str = ""            # 成员行注释里的描述（去 Address offset 部分）
    offset_source: str = "comment"   # comment | inferred
    object_id: str = ""
    semantic_path: str = ""

    def __post_init__(self):
        self.object_id = hashlib.sha256(
            f"{self.peripheral}/{self.name}/{self.offset}".encode()
        ).hexdigest()[:20]
        self.semantic_path = "/".join(x for x in (self.peripheral, self.name) if x)


@dataclass
class HeaderPeripheral:
    name: str
    base_address: int
    type_name: str
    registers: list[HeaderRegister] = field(default_factory=list)
    line_number: int = 0
    raw_text: str = ""
    base_symbol: str = ""
    object_id: str = ""
    semantic_path: str = ""

    def __post_init__(self):
        self.object_id = hashlib.sha256(
            f"{self.name}/{self.base_address:#X}/{self.type_name}".encode()
        ).hexdigest()[:20]
        self.semantic_path = self.name
        self._cursor = 0   # 成员偏移推断游标（含 RESERVED 推进量）


@dataclass
class HeaderIrq:
    name: str
    irq_number: int
    description: str
    line_number: int
    raw_text: str
    object_id: str = ""
    semantic_path: str = ""

    def __post_init__(self):
        self.object_id = hashlib.sha256(
            f"irq/{self.name}/{self.irq_number}".encode()
        ).hexdigest()[:20]
        self.semantic_path = f"interrupt/{self.name}"


@dataclass
class HeaderModel:
    path: str = ""
    fingerprint: str = ""
    peripherals: list[HeaderPeripheral] = field(default_factory=list)
    interrupts: list[HeaderIrq] = field(default_factory=list)
    unresolved: list[dict] = field(default_factory=list)
    base_symbols: dict[str, int] = field(default_factory=dict)

    @property
    def peripheral_names(self) -> set[str]:
        return {p.name for p in self.peripherals}

    def count_registers(self) -> int:
        return sum(len(p.registers) for p in self.peripherals)

    def count_fields(self) -> int:
        return sum(len(r.fields) for p in self.peripherals for r in p.registers)


# ════════════════════════════════════════════════════
# 解析器
# ════════════════════════════════════════════════════

_TYPE_SIZE = {"uint8_t": 1, "uint16_t": 2, "uint32_t": 4, "int": 4, "vu8": 1, "vu16": 2, "vu32": 4}


class HeaderParser:
    """最小 CMSIS 头文件结构解析器，针对常见 _Pos/_Msk 风格。"""

    _irq_re = re.compile(
        r"^\s*([A-Za-z][A-Za-z0-9_]*_IRQn)\s*=\s*(-?\d+)\s*,?\s*$"
    )
    _define_re = re.compile(r"^#define\s+([A-Za-z_][A-Za-z0-9_]*)\s+(.+)$")
    _pos_define_re = re.compile(
        r"^#define\s+([A-Za-z_][A-Za-z0-9_]*)_Pos\s+(.+?)\s*$")
    _msk_define_re = re.compile(
        r"^#define\s+([A-Za-z_][A-Za-z0-9_]*)_Msk\s+(.+?)\s*$")
    _msk_shift_re = re.compile(
        r"^\(?\s*(0[xX][0-9A-Fa-f]+|\d+)[UuLl]*\s*<<\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)?$")
    _member_re = re.compile(
        r"\b(uint8_t|uint16_t|uint32_t|vu8|vu16|vu32)\s+"
        r"([A-Za-z_][A-Za-z0-9_]*)\s*(?:\[(\d+)\])?\s*;")
    _member_loose_re = re.compile(
        r"\b([A-Za-z_][A-Za-z0-9_]*)\s*(?:\[(\d+)\])?\s*;")
    _offset_comment_re = re.compile(
        r"Address\s*offset\s*[:：]?\s*(0[xX][0-9A-Fa-f]+|\d+)", re.I)
    _block_comment_re = re.compile(r"/\*\s*<?!?(.*?)\s*\*/")

    def parse_file(self, path: str | Path) -> HeaderModel:
        p = Path(path)
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        model = HeaderModel(path=str(p.resolve()), fingerprint=self._fingerprint(p))
        self._parse_irqs(lines, model)
        symbols = self._parse_base_symbols(lines, model)
        model.base_symbols = dict(symbols)
        typedefs = self._parse_typedefs(lines)
        self._parse_instances(lines, model, symbols, typedefs)
        self._parse_bitfields(lines, model)
        return model

    def parse_text(self, text: str, path: str = "<memory>") -> HeaderModel:
        """支持内存文本解析（测试用），语义与 parse_file 一致。"""
        lines = text.splitlines()
        model = HeaderModel(path=path, fingerprint=hashlib.sha256(text.encode("utf-8")).hexdigest())
        self._parse_irqs(lines, model)
        symbols = self._parse_base_symbols(lines, model)
        model.base_symbols = dict(symbols)
        typedefs = self._parse_typedefs(lines)
        self._parse_instances(lines, model, symbols, typedefs)
        self._parse_bitfields(lines, model)
        return model

    @staticmethod
    def _fingerprint(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    # ---------- IRQ ----------

    def _parse_irqs(self, lines: list[str], model: HeaderModel) -> None:
        for no, raw_line in enumerate(lines, 1):
            clean = _strip_comments(raw_line)
            match = self._irq_re.match(clean)
            if not match:
                continue
            name, number = match.groups()
            desc_match = self._block_comment_re.search(raw_line)
            model.interrupts.append(HeaderIrq(
                name=name[:-5],
                irq_number=int(number),
                description=(desc_match.group(1).strip() if desc_match else ""),
                line_number=no,
                raw_text=raw_line.strip(),
            ))

    # ---------- 基地址符号 ----------

    def _parse_base_symbols(self, lines: list[str], model: HeaderModel) -> dict[str, int]:
        pending: dict[str, tuple[int, str]] = {}
        for no, raw_line in enumerate(lines, 1):
            clean = _strip_comments(raw_line)
            if clean.startswith("//"):
                continue
            match = self._define_re.match(clean)
            if not match or not match.group(1).endswith("_BASE"):
                continue
            pending[match.group(1)] = (no, match.group(2))
        symbols: dict[str, int] = {}
        for _ in range(8):
            progress = False
            for name, (_no, expression) in list(pending.items()):
                value = _safe_sum_expression(expression, symbols)
                if value is not None:
                    symbols[name] = value
                    pending.pop(name, None)
                    progress = True
            if not progress:
                break
        model.unresolved.extend({
            "kind": "base_address",
            "name": name,
            "line": no,
            "raw_text": expression,
        } for name, (no, expression) in sorted(pending.items()))
        return symbols

    # ---------- typedef struct ----------

    def _parse_typedefs(self, lines: list[str]) -> dict[str, list[dict]]:
        """typedef 模板：type_name → [{name, line, raw, size, count}]。"""
        typedefs: dict[str, list[dict]] = {}
        i = 0
        while i < len(lines):
            if re.match(r"^\s*typedef\s+struct\b", lines[i]):
                j = i + 1
                while j < len(lines) and "}" not in lines[j]:
                    j += 1
                if j < len(lines):
                    close_match = re.search(
                        r"}\s*([A-Za-z_][A-Za-z0-9_]*)", lines[j])
                    if close_match:
                        members = []
                        for no in range(i + 1, j):
                            raw = lines[no]
                            member = self._parse_member(raw)
                            if member:
                                member["line"] = no + 1
                                members.append(member)
                        typedefs[close_match.group(1)] = members
                i = j
            i += 1
        return typedefs

    @classmethod
    def _parse_member(cls, raw: str) -> Optional[dict]:
        clean = _strip_comments(raw)
        if not clean or clean.startswith("//"):
            return None
        match = cls._member_re.search(clean)
        if match:
            ctype, name, count = match.groups()
            return {
                "name": name, "raw": raw.strip(),
                "size": _TYPE_SIZE.get(ctype, 4),
                "count": int(count) if count else 1,
            }
        loose = cls._member_loose_re.search(clean)
        if loose:
            name, count = loose.groups()
            if name in ("struct", "union", "volatile"):
                return None
            return {
                "name": name, "raw": raw.strip(),
                "size": 4, "count": int(count) if count else 1,
            }
        return None

    # ---------- 外设实例 ----------

    def _parse_instances(
        self,
        lines: list[str],
        model: HeaderModel,
        symbols: dict[str, int],
        typedefs: dict[str, list[dict]],
    ) -> None:
        instance_re = re.compile(
            r"^#define\s+([A-Za-z_][A-Za-z0-9_]*)\s+"
            r"\(\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)_TypeDef\s*\*\s*\)\s*"
            r"([A-Za-z_][A-Za-z0-9_]*)\s*\)"
        )
        for no, raw_line in enumerate(lines, 1):
            clean = _strip_comments(raw_line)
            if not clean.startswith("#define"):
                continue
            match = instance_re.match(clean)
            if not match:
                continue
            name, type_name, base_symbol = match.groups()
            base = symbols.get(base_symbol)
            if base is None:
                model.unresolved.append({
                    "kind": "instance_base", "name": name,
                    "line": no, "raw_text": raw_line.strip(),
                    "detail": f"base symbol {base_symbol} unresolved",
                })
                continue
            periph = HeaderPeripheral(
                name=normalize_identifier(name),
                base_address=base,
                type_name=type_name,
                line_number=no,
                raw_text=raw_line.strip(),
                base_symbol=base_symbol,
            )
            for member in typedefs.get(f"{type_name}_TypeDef", []):
                self._append_register(periph, member)
            model.peripherals.append(periph)

    @staticmethod
    def _member_description(raw: str) -> str:
        match = re.search(r"/\*\s*(.*?)\s*\*/", raw)
        if not match:
            return ""
        desc = match.group(1).lstrip("<!").strip()
        desc = re.sub(r"[,，]?\s*Address\s*offset\s*[:：]?\s*0[xX][0-9A-Fa-f]+.*$", "", desc, flags=re.I)
        desc = re.sub(r"[,，]?\s*@.*$", "", desc)
        return desc.strip(" ,，")

    @classmethod
    def _append_register(cls, periph: HeaderPeripheral, member: dict) -> None:
        """按注释偏移或顺序推断放置成员；RESERVED[n] 只推进游标不产出寄存器。"""
        raw = member["raw"]
        name = member["name"]
        count = member.get("count", 1)
        size = member.get("size", 4)
        offset_match = cls._offset_comment_re.search(raw)
        if offset_match:
            offset = int(offset_match.group(1), 16 if offset_match.group(1).lower().startswith("0x") else 10)
            offset_source = "comment"
        else:
            offset = cls._cursor_end(periph)
            offset_source = "inferred"
        # 推进游标：无论是否 RESERVED
        cls._advance_cursor(periph, offset, size * count)
        if re.fullmatch(r"RESERVED\d*", normalize_identifier(name)):
            return
        periph.registers.append(HeaderRegister(
            name=normalize_identifier(name),
            peripheral=periph.name,
            offset=offset,
            line_number=member.get("line", 0),
            raw_text=raw,
            array_length=count if count > 1 else 0,
            description=cls._member_description(raw),
            offset_source=offset_source,
        ))

    @staticmethod
    def _cursor_end(periph: HeaderPeripheral) -> int:
        """结构体末尾游标：取最后一个成员（含 RESERVED）的结束位置。"""
        return getattr(periph, "_cursor", 0)

    @staticmethod
    def _advance_cursor(periph: HeaderPeripheral, start: int, byte_size: int) -> None:
        end = start + byte_size
        cursor = getattr(periph, "_cursor", None)
        periph._cursor = max(end, cursor if cursor is not None else 0)

    # ---------- 位域 ----------

    def _parse_bitfields(self, lines: list[str], model: HeaderModel) -> None:
        pos_values: dict[str, tuple[int, int, str]] = {}  # 字段全名 → (pos, line, raw)
        msk_raws: dict[str, tuple[int, str]] = {}
        pos_symbols: dict[str, int] = {}              # Pos 符号名 → 值（跨字段引用）
        for no, raw_line in enumerate(lines, 1):
            clean = _strip_comments(raw_line)
            pos_match = self._pos_define_re.match(clean)
            if pos_match:
                value = _safe_sum_expression(pos_match.group(2), {})
                if value is None:
                    model.unresolved.append({
                        "kind": "bitfield_pos_value", "name": pos_match.group(1) + "_Pos",
                        "line": no, "raw_text": raw_line.strip(),
                    })
                    continue
                pos_values[pos_match.group(1)] = (value, no, raw_line.strip())
                pos_symbols[f"{pos_match.group(1)}_Pos"] = value
                continue
            msk_match = self._msk_define_re.match(clean)
            if msk_match:
                msk_raws[msk_match.group(1)] = (no, raw_line.strip())

        for field_name, (pos, pos_line, pos_raw) in pos_values.items():
            msk_entry = msk_raws.pop(field_name, None)
            if msk_entry is None:
                model.unresolved.append({
                    "kind": "bitfield_missing_pair", "name": field_name,
                    "line": pos_line, "raw_text": pos_raw,
                    "detail": "has _Pos but no _Msk",
                })
                continue
            msk_no, msk_raw = msk_entry
            mask = self._parse_mask_value(msk_raw, pos_symbols, pos)
            if mask is None:
                model.unresolved.append({
                    "kind": "bitfield_msk_value", "name": field_name + "_Msk",
                    "line": msk_no, "raw_text": msk_raw,
                })
                continue
            shifted = mask >> pos
            width = shifted.bit_length()
            if width <= 0:
                model.unresolved.append({
                    "kind": "bitfield_msk_value", "name": field_name + "_Msk",
                    "line": msk_no, "raw_text": msk_raw,
                    "detail": f"mask {mask:#x} inconsistent with pos {pos}",
                })
                continue
            mounted = self._mount_bitfield(
                model, field_name, pos, max(width, 1), mask, msk_no, msk_raw)
            if not mounted:
                model.unresolved.append({
                    "kind": "bitfield_no_register", "name": field_name,
                    "line": msk_no, "raw_text": msk_raw,
                    "detail": "no peripheral/register anchor found",
                })
        for field_name, (no, raw_text) in msk_raws.items():
            model.unresolved.append({
                "kind": "bitfield_missing_pair", "name": field_name,
                "line": no, "raw_text": raw_text,
                "detail": "has _Msk but no _Pos",
            })

    def _parse_mask_value(
        self, raw_text: str, pos_symbols: dict[str, int], own_pos: int,
    ) -> Optional[int]:
        text = _strip_comments(raw_text)
        # 去掉行首 "#define NAME"
        define_match = self._msk_define_re.match(text)
        expr = define_match.group(2) if define_match else text
        expr = expr.strip()
        while (expr.startswith("(") and expr.endswith(")")
               and _balanced_parens(expr[1:-1])):
            expr = expr[1:-1].strip()
        shift_match = self._msk_shift_re.match(expr)
        if shift_match:
            literal, symbol = shift_match.groups()
            num = int(literal, 16 if literal.lower().startswith("0x") else 10)
            shift = pos_symbols.get(symbol, own_pos if symbol.endswith("_Pos") else None)
            if shift is None:
                return None
            return num << shift
        direct = _numeric_literal(expr)
        if direct is not None:
            return direct
        return None

    # ---------- 位域挂载 ----------

    @staticmethod
    def _register_name_variants(reg_name: str, periph_name: str) -> list[str]:
        """寄存器匹配键：前缀剥离 + INT 前缀缩写变体（INTF_IE ↔ FIE）。"""
        base = register_root(reg_name, periph_name)
        variants = [base]
        if base.startswith("INT"):
            stripped = base[3:]
            variants.append(stripped)
            compact = stripped.lstrip("_")
            if compact:
                variants.append(compact)
                squashed = compact.replace("_", "")
                if squashed:
                    variants.append(squashed)
        seen: list[str] = []
        for item in variants:
            if item and item not in seen:
                seen.append(item)
        return seen

    def _find_register(self, periph: HeaderPeripheral, reg_seg: str) -> Optional[HeaderRegister]:
        target = register_root(reg_seg, periph.name)
        for reg in periph.registers:
            if target in self._register_name_variants(reg.name, periph.name):
                return reg
        return None

    def _mount_bitfield(
        self, model: HeaderModel, field_name: str, pos: int, width: int,
        mask: int, line_no: int, raw_text: str,
    ) -> int:
        parts = normalize_identifier(field_name).split("_")
        parts = [p for p in parts if p]
        if len(parts) < 3:
            return 0
        fld = parts[-1]
        # split = 外设段数（≥1），寄存器段至少 1 段
        for split in range(1, len(parts) - 1):
            periph_seg = "_".join(parts[:split])
            reg_seg = "_".join(parts[split:-1])
            # A. 精确实例名
            instances = [p for p in model.peripherals if p.name == periph_seg]
            # B. 外设前缀去掉实例号（UART → UART0..3）
            if not instances:
                root = peripheral_root(periph_seg)
                if root:
                    instances = [
                        p for p in model.peripherals
                        if peripheral_root(p.name) == root
                    ]
            mounted = 0
            for inst in instances:
                reg = self._find_register(inst, reg_seg)
                if reg is None:
                    continue
                reg.fields.append(HeaderField(
                    name=normalize_identifier(fld),
                    register=reg.name,
                    peripheral=inst.name,
                    bit_offset=pos,
                    bit_width=width,
                    line_number=line_no,
                    raw_text=raw_text,
                    mask=mask,
                ))
                mounted += 1
            if mounted:
                return mounted
        # C. 唯一全名寄存器匹配：PLL_CFG_xxx → RCC.PLL_CFG
        full_reg = "_".join(parts[:-1])
        hits: dict[str, HeaderPeripheral] = {}
        for periph in model.peripherals:
            for reg in periph.registers:
                if reg.name == full_reg:
                    hits.setdefault(periph.name, periph)
        if len(hits) == 1:
            inst = next(iter(hits.values()))
            reg = next(r for r in inst.registers if r.name == full_reg)
            reg.fields.append(HeaderField(
                name=normalize_identifier(fld),
                register=reg.name,
                peripheral=inst.name,
                bit_offset=pos,
                bit_width=width,
                line_number=line_no,
                raw_text=raw_text,
                mask=mask,
            ))
            return 1
        return 0
