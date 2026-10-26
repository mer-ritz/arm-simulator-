"""5-stage pipeline model: IF -> ID -> EX -> MEM -> WB.

How it works
    1. The CPU runs the program normally and records every executed instruction
       (the "trace"). This keeps the CPU simple and always correct.
    2. This module then works out, instruction by instruction, WHICH CYCLE each
       one enters each stage, applying the pipeline rules below.

Rules modelled
    * One instruction per stage, strictly in order.
    * Register file: written in the first half of a cycle, read in the second
      half, so an instruction can read in ID during the producer's WB cycle.
    * Data hazards (RAW):
        - forwarding OFF: consumer waits until the producer has written back
        - forwarding ON : ALU results are forwarded after EX (no stall);
                          a LOAD result is only available after MEM (1 stall)
    * Control hazards: branches resolve in EX, predict-not-taken. A taken branch
      flushes the 2 instructions fetched after it (2 lost cycles).
    * Memory latency: LDR/STR can occupy MEM for several cycles (cache miss).
      Pass mem_latency=function(mem_event) -> cycles. The cache (next step)
      plugs in here.
    * Flags (N,Z,C,V) are treated as one extra register called "FLAGS".
"""
from dataclasses import dataclass, field

from assembler import ALU_OPS

STAGES = 5


def reg_usage(ins):
    """Return (reads, writes) for an Instruction.
    reads  : set of register names ("R3", "FLAGS")
    writes : list of (name, kind) where kind is "alu" or "load"
    """
    reads, writes = set(), []

    def rd_op(operand):
        if operand and operand[0] == "reg":
            reads.add(f"R{operand[1]}")

    op = ins.op
    if op == "MOV":
        rd_op(ins.op2)
        writes.append((f"R{ins.rd}", "alu"))
    elif op in ALU_OPS:
        reads.add(f"R{ins.rn}")
        rd_op(ins.op2)
        writes.append((f"R{ins.rd}", "alu"))
    elif op == "CMP":
        reads.add(f"R{ins.rn}")
        rd_op(ins.op2)
    elif op in ("LDR", "STR"):
        m = ins.mem
        reads.add(f"R{m['base']}")
        rd_op(m["offset"])
        if op == "LDR":
            writes.append((f"R{ins.rd}", "load"))
        else:
            reads.add(f"R{ins.rd}")            # the data being stored
        if m["mode"] in ("pre", "post"):
            writes.append((f"R{m['base']}", "alu"))
    elif op == "BL":
        writes.append(("R14", "alu"))
    elif op in ("BEQ", "BNE", "BGT", "BLT", "BGE", "BLE"):
        reads.add("FLAGS")

    if ins.set_flags:
        writes.append(("FLAGS", "alu"))
    return reads, writes


@dataclass
class Row:
    index: int
    pc: int
    text: str
    F: int = 0   # cycle the instruction enters each stage
    D: int = 0
    X: int = 0
    M: int = 0
    W: int = 0
    mem_cycles: int = 1
    data_stall: int = 0
    mem_stall: int = 0
    flush: int = 0                    # bubbles inserted AFTER this (taken) branch
    cells: dict = field(default_factory=dict)   # cycle -> label, for display


class Pipeline:
    def __init__(self, cpu, forwarding=True, mem_latency=None, io_latency=2):
        self.cpu = cpu
        self.forwarding = forwarding
        self.mem_latency = mem_latency
        self.io_latency = io_latency      # phone devices are slower than 1 cycle

    def run(self, max_steps=100000):
        cpu = self.cpu
        events = cpu.run(max_steps)
        rows, last_writer = [], {}
        prev = None
        f_next = 1

        for i, ev in enumerate(events):
            ins = cpu.program[ev["pc"] // 4]
            reads, writes = reg_usage(ins)
            lat = 1
            if ev["mem"] and self.mem_latency:
                lat = max(1, self.mem_latency(ev["mem"]))
            elif ev.get("io"):
                lat = self.io_latency

            row = Row(index=i, pc=ev["pc"], text=ev["text"], mem_cycles=lat)
            row.F = f_next
            row.D = row.F + 1 if prev is None else max(row.F + 1, prev.X)

            # earliest EX cycle allowed by data dependences
            ready = 0
            for r in reads:
                if r in last_writer:
                    p, kind = last_writer[r]
                    if self.forwarding:
                        ready = max(ready, p.M if kind == "alu" else p.W)
                    else:
                        ready = max(ready, p.W + 1)

            prev_m = prev.M if prev else 0
            prev_w = prev.W if prev else 0
            base_x = max(row.D + 1, prev_m)
            row.X = max(base_x, ready)
            row.data_stall = max(0, ready - base_x)
            row.mem_stall = max(0, base_x - (row.D + 1))
            row.M = max(row.X + 1, prev_w)
            row.W = row.M + lat

            # fetch time of the next instruction
            if ev["branch_taken"]:
                f_next = max(row.D, row.X + 1)
                row.flush = f_next - row.D
            else:
                f_next = row.D

            for name, kind in writes:
                last_writer[name] = (row, kind)

            self._fill_cells(row)
            rows.append(row)
            prev = row

        self.rows = rows
        return self.summary()

    @staticmethod
    def _fill_cells(row):
        spans = [("IF", row.F, row.D), ("ID", row.D, row.X),
                 ("EX", row.X, row.M), ("MEM", row.M, row.W), ("WB", row.W, row.W + 1)]
        for name, start, end in spans:
            for c in range(start, end):
                row.cells[c] = name if c == start else name + "*"

    def summary(self):
        rows = self.rows
        n = len(rows)
        cycles = rows[-1].W if rows else 0
        base = sum(STAGES + r.mem_cycles - 1 for r in rows)   # no pipelining
        return {
            "instructions": n,
            "cycles": cycles,
            "cpi": cycles / n if n else 0,
            "data_stalls": sum(r.data_stall for r in rows),
            "mem_stalls": sum(r.mem_stall + (r.mem_cycles - 1) for r in rows),
            "flush_cycles": sum(r.flush for r in rows),
            "non_pipelined_cycles": base,
            "speedup": base / cycles if cycles else 0,
        }

    def diagram(self):
        """Text pipeline diagram. A '*' means the instruction is stalled in that stage."""
        if not self.rows:
            return "(no instructions)"
        total = self.rows[-1].W
        w = max(len(r.text) for r in self.rows) + 2
        head = "".ljust(w) + "".join(f"{c:>5}" for c in range(1, total + 1))
        lines = [head]
        for r in self.rows:
            line = r.text.ljust(w) + "".join(f"{r.cells.get(c, '.'):>5}" for c in range(1, total + 1))
            lines.append(line)
        return "\n".join(lines)
