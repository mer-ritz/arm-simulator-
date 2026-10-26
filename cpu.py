"""Simple (non-pipelined) ARM-like CPU core with memory-mapped phone I/O.

Each call to step() executes ONE instruction and returns an 'event' dict
describing what happened. The interface only displays events; it never computes.

Memory map
    0x0000 - 0xEFFF   RAM
    0xFF00  SCREEN    write: show a value (brightness / number)      read: last value
    0xFF04  TOUCH     read : next touch event from the input queue (0 when empty)
    0xFF08  TIMER     read : current tick count (instructions executed so far)
    0xFF0C  SENSOR    read : next sensor reading from the input queue (0 when empty)
"""
from assembler import ALU_OPS, assemble

MASK = 0xFFFFFFFF

IO_SCREEN, IO_TOUCH, IO_TIMER, IO_SENSOR = 0xFF00, 0xFF04, 0xFF08, 0xFF0C
IO_BASE, IO_END = 0xFF00, 0xFF10
IO_NAMES = {IO_SCREEN: "SCREEN", IO_TOUCH: "TOUCH", IO_TIMER: "TIMER", IO_SENSOR: "SENSOR"}
STACK_TOP = 0xF000


class CPUError(Exception):
    pass


class CPU:
    def __init__(self, source: str, mem_size: int = 0x10000, inputs=None):
        self.program, self.labels = assemble(source)
        self.mem_size = mem_size
        self.inputs = inputs or {}
        self.reset()

    # ---------- state ----------
    def reset(self):
        self.regs = [0] * 16
        self.regs[13] = STACK_TOP              # SP
        self.memory = bytearray(self.mem_size)
        self.pc = 0                            # instruction INDEX (R15 shows pc*4)
        self.flags = {"N": 0, "Z": 0, "C": 0, "V": 0}
        self.cycle = 0
        self.halted = False
        self._next_pc = 0
        self.queues = {"touch": list(self.inputs.get("touch", [])),
                       "sensor": list(self.inputs.get("sensor", []))}
        self.qpos = {"touch": 0, "sensor": 0}
        self.screen = 0
        self.screen_log = []                   # (instruction number, value)

    # ---------- memory ----------
    def read_word(self, addr: int) -> int:
        self._check_addr(addr)
        return int.from_bytes(self.memory[addr:addr + 4], "little")

    def write_word(self, addr: int, value: int):
        self._check_addr(addr)
        self.memory[addr:addr + 4] = (value & MASK).to_bytes(4, "little")

    def _check_addr(self, addr: int):
        if addr % 4 != 0:
            raise CPUError(f"unaligned access at {addr:#x}")
        if not 0 <= addr <= self.mem_size - 4:
            raise CPUError(f"address {addr:#x} out of range")

    # ---------- phone I/O ----------
    def _io_read(self, addr: int) -> int:
        if addr in (IO_TOUCH, IO_SENSOR):
            key = "touch" if addr == IO_TOUCH else "sensor"
            q, p = self.queues[key], self.qpos[key]
            if p < len(q):
                self.qpos[key] += 1
                return q[p] & MASK
            return 0
        if addr == IO_TIMER:
            return self.cycle & MASK
        if addr == IO_SCREEN:
            return self.screen
        raise CPUError(f"no device at address {addr:#x}")

    def _io_write(self, addr: int, value: int):
        if addr == IO_SCREEN:
            self.screen = value & MASK
            self.screen_log.append((self.cycle + 1, self.screen))
            return
        name = IO_NAMES.get(addr, f"{addr:#x}")
        raise CPUError(f"{name} is read-only (or no such device)")

    # ---------- flags ----------
    def _flags_logic(self, res):
        self.flags["N"], self.flags["Z"] = res >> 31, int(res == 0)

    def _flags_add(self, a, b):
        full = a + b
        res = full & MASK
        self._flags_logic(res)
        self.flags["C"] = int(full > MASK)
        self.flags["V"] = (~(a ^ b) & (a ^ res)) >> 31 & 1
        return res

    def _flags_sub(self, a, b):
        res = (a - b) & MASK
        self._flags_logic(res)
        self.flags["C"] = int(a >= b)          # C = "no borrow"
        self.flags["V"] = ((a ^ b) & (a ^ res)) >> 31 & 1
        return res

    def _cond(self, op: str) -> bool:
        f = self.flags
        return {
            "B": True, "BL": True,
            "BEQ": f["Z"] == 1, "BNE": f["Z"] == 0,
            "BGT": f["Z"] == 0 and f["N"] == f["V"],
            "BLT": f["N"] != f["V"],
            "BGE": f["N"] == f["V"],
            "BLE": f["Z"] == 1 or f["N"] != f["V"],
        }[op]

    # ---------- helpers ----------
    def _val(self, operand):
        kind, v = operand
        return (v & MASK) if kind == "imm" else self.regs[v]

    def _write_reg(self, ev, n, value):
        value &= MASK
        self.regs[n] = value
        ev["writes"][f"R{n}"] = value
        if n == 15:                            # e.g. MOV PC, LR  (return)
            self._next_pc = value >> 2
            ev["branch_taken"] = True

    # ---------- execute ----------
    def step(self):
        if self.halted:
            return None
        if not 0 <= self.pc < len(self.program):
            self.halted = True
            return None

        ins = self.program[self.pc]
        ev = {"cycle": self.cycle + 1, "pc": self.pc * 4, "text": ins.text,
              "writes": {}, "mem": None, "io": None, "branch_taken": False, "alu": None}
        self._next_pc = self.pc + 1
        op = ins.op

        if op == "MOV":
            res = self._val(ins.op2)
            self._write_reg(ev, ins.rd, res)
            if ins.set_flags:
                self._flags_logic(res)

        elif op in ALU_OPS:
            a, b = self.regs[ins.rn], self._val(ins.op2)
            if op == "ADD":
                res = self._flags_add(a, b) if ins.set_flags else (a + b) & MASK
            elif op == "SUB":
                res = self._flags_sub(a, b) if ins.set_flags else (a - b) & MASK
            else:
                res = {"AND": a & b, "ORR": a | b, "EOR": a ^ b,
                       "LSL": ((a << b) & MASK) if b < 32 else 0,
                       "LSR": (a >> b) if b < 32 else 0,
                       "MUL": (a * b) & MASK}[op]
                if ins.set_flags:
                    self._flags_logic(res)
            ev["alu"] = f"{a} {op} {b} = {res}"
            self._write_reg(ev, ins.rd, res)

        elif op == "CMP":
            a, b = self.regs[ins.rn], self._val(ins.op2)
            self._flags_sub(a, b)
            ev["alu"] = f"CMP {a}, {b}"

        elif op in ("LDR", "STR"):
            m = ins.mem
            base = self.regs[m["base"]]
            off = 0
            if m["offset"]:
                kind, v = m["offset"]
                off = v if kind == "imm" else self.regs[v]   # immediates may be negative
            addr = (base if m["mode"] == "post" else base + off) & MASK
            is_io = IO_BASE <= addr < IO_END
            if op == "LDR":
                if is_io:
                    data = self._io_read(addr)
                    ev["io"] = {"type": "read", "device": IO_NAMES.get(addr, "?"),
                                "addr": addr, "data": data}
                else:
                    data = self.read_word(addr)
                    ev["mem"] = {"type": "read", "addr": addr, "data": data}
                self._write_reg(ev, ins.rd, data)
            else:
                data = self.regs[ins.rd]
                if is_io:
                    self._io_write(addr, data)
                    ev["io"] = {"type": "write", "device": IO_NAMES.get(addr, "?"),
                                "addr": addr, "data": data}
                else:
                    self.write_word(addr, data)
                    ev["mem"] = {"type": "write", "addr": addr, "data": data}
            if m["mode"] == "pre":
                self._write_reg(ev, m["base"], addr)
            elif m["mode"] == "post":
                self._write_reg(ev, m["base"], base + off)

        elif op in ("B", "BEQ", "BNE", "BGT", "BLT", "BGE", "BLE", "BL"):
            if self._cond(op):
                if op == "BL":
                    self._write_reg(ev, 14, (self.pc + 1) * 4)
                self._next_pc = ins.target_idx
                ev["branch_taken"] = True

        elif op == "HLT":
            self.halted = True

        self.pc = self._next_pc
        self.regs[15] = self.pc * 4
        self.cycle += 1
        return ev

    def run(self, max_steps: int = 100000):
        events = []
        while not self.halted:
            if len(events) >= max_steps:
                raise CPUError("max steps exceeded (infinite loop?)")
            ev = self.step()
            if ev is None:
                break
            events.append(ev)
        return events
