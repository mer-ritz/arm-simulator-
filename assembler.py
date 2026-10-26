"""Assembler: turns ARM-like assembly text into a list of Instruction objects.

Supported instructions
    MOV  Rd, op2
    ADD / SUB / AND / ORR / EOR / LSL / LSR / MUL  Rd, Rn, op2   (add S for flags: SUBS ...)
    CMP  Rn, op2
    LDR / STR  Rd, [Rn] | [Rn, #imm] | [Rn, Rm] | [Rn, #imm]! | [Rn], #imm
    B / BEQ / BNE / BGT / BLT / BGE / BLE / BL  label
    HLT

op2 is either an immediate (#10, #0x1F) or a register (R0..R15, SP, LR, PC).
Comments start with ';', '@' or '//'. Labels end with ':'.
"""
import re
from dataclasses import dataclass
from typing import Optional

REG_ALIASES = {"SP": 13, "LR": 14, "PC": 15}
ALU_OPS = {"ADD", "SUB", "AND", "ORR", "EOR", "LSL", "LSR", "MUL"}
BRANCH_OPS = {"B", "BEQ", "BNE", "BGT", "BLT", "BGE", "BLE", "BL"}

MEM_RE = re.compile(
    r"^\[\s*(\w+)\s*(?:,\s*(#?[-\w]+))?\s*\](!)?\s*(?:,\s*(#?[-\w]+))?$"
)


class AsmError(Exception):
    pass


@dataclass
class Instruction:
    op: str
    text: str = ""
    line: int = 0
    set_flags: bool = False
    rd: Optional[int] = None
    rn: Optional[int] = None
    op2: Optional[tuple] = None      # ("imm", value) or ("reg", n)
    mem: Optional[dict] = None       # {"base": n, "offset": op2-tuple|None, "mode": "offset"|"pre"|"post"}
    target: Optional[str] = None     # label name for branches
    target_idx: Optional[int] = None


def parse_reg(tok: str, line: int) -> int:
    t = tok.strip().upper()
    if t in REG_ALIASES:
        return REG_ALIASES[t]
    m = re.fullmatch(r"R(\d+)", t)
    if m and int(m.group(1)) <= 15:
        return int(m.group(1))
    raise AsmError(f"line {line}: bad register '{tok}'")


def parse_op2(tok: str, line: int) -> tuple:
    tok = tok.strip()
    if tok.startswith("#"):
        try:
            return ("imm", int(tok[1:], 0))
        except ValueError:
            raise AsmError(f"line {line}: bad immediate '{tok}'")
    return ("reg", parse_reg(tok, line))


def parse_mem(tok: str, line: int) -> dict:
    m = MEM_RE.match(tok.strip())
    if not m:
        raise AsmError(f"line {line}: bad memory operand '{tok}'")
    base, off_in, bang, off_post = m.groups()
    base = parse_reg(base, line)
    if off_post is not None:
        return {"base": base, "offset": parse_op2(off_post, line), "mode": "post"}
    offset = parse_op2(off_in, line) if off_in is not None else None
    return {"base": base, "offset": offset, "mode": "pre" if bang else "offset"}


def _split_ops(rest: str):
    return [p.strip() for p in rest.split(",")] if rest.strip() else []


def assemble(source: str):
    """Return (instructions, labels). Raises AsmError on bad input."""
    labels = {}
    pending = []  # (line_no, mnemonic, rest, original_text)

    for line_no, raw in enumerate(source.splitlines(), start=1):
        line = re.split(r";|@|//", raw)[0].strip()
        while True:
            m = re.match(r"^([A-Za-z_]\w*)\s*:\s*", line)
            if not m:
                break
            if m.group(1) in labels:
                raise AsmError(f"line {line_no}: duplicate label '{m.group(1)}'")
            labels[m.group(1)] = len(pending)
            line = line[m.end():]
        if not line:
            continue
        parts = line.split(None, 1)
        pending.append((line_no, parts[0].upper(), parts[1] if len(parts) > 1 else "", line))

    program = []
    for line_no, mn, rest, text in pending:
        set_flags = False
        op = mn
        if mn.endswith("S") and mn[:-1] in (ALU_OPS | {"MOV"}):
            op, set_flags = mn[:-1], True
        ins = Instruction(op=op, text=text, line=line_no, set_flags=set_flags)

        if op == "MOV":
            a = _split_ops(rest)
            if len(a) != 2:
                raise AsmError(f"line {line_no}: MOV needs 2 operands")
            ins.rd, ins.op2 = parse_reg(a[0], line_no), parse_op2(a[1], line_no)
        elif op in ALU_OPS:
            a = _split_ops(rest)
            if len(a) != 3:
                raise AsmError(f"line {line_no}: {op} needs 3 operands")
            ins.rd, ins.rn = parse_reg(a[0], line_no), parse_reg(a[1], line_no)
            ins.op2 = parse_op2(a[2], line_no)
        elif op == "CMP":
            a = _split_ops(rest)
            if len(a) != 2:
                raise AsmError(f"line {line_no}: CMP needs 2 operands")
            ins.rn, ins.op2, ins.set_flags = parse_reg(a[0], line_no), parse_op2(a[1], line_no), True
        elif op in ("LDR", "STR"):
            m = re.match(r"^(\w+)\s*,\s*(\[.*)$", rest.strip())
            if not m:
                raise AsmError(f"line {line_no}: {op} needs 'Rd, [address]'")
            ins.rd = parse_reg(m.group(1), line_no)
            ins.mem = parse_mem(m.group(2), line_no)
        elif op in BRANCH_OPS:
            ins.target = rest.strip()
            if ins.target not in labels:
                raise AsmError(f"line {line_no}: unknown label '{ins.target}'")
            ins.target_idx = labels[ins.target]
        elif op == "HLT":
            pass
        else:
            raise AsmError(f"line {line_no}: unknown instruction '{mn}'")
        program.append(ins)

    return program, labels
