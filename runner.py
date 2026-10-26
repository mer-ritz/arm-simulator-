"""Glue code used by the interface. Contains NO Streamlit, so it can be tested alone.

simulate()     -> step-by-step snapshots + pipeline timing for ONE configuration
compare_all()  -> results table: pipeline on/off, forwarding on/off, cache on/off
"""
from cache import Cache
from cpu import CPU, CPUError
from pipeline import Pipeline

MAX_STEPS = 50000
DEFAULT_CACHE = {"size": 256, "block": 16, "ways": 1}

SAMPLES = {
    "Phone: auto-brightness": {
        "touch": "", "sensor": "40, 120, 230, 90",
        "code": """\
    MOV R4, #0xFF00     ; SCREEN register
    MOV R5, #0xFF0C     ; SENSOR register (ambient light)
    MOV R7, #4          ; number of readings
loop:
    LDR R2, [R5]        ; read ambient light
    CMP R2, #200
    BLE ok
    MOV R2, #200        ; clamp: never brighter than 200
ok:
    STR R2, [R4]        ; set screen brightness
    SUBS R7, R7, #1
    BNE loop
    HLT
""",
    },
    "Phone: touch counter": {
        "touch": "1, 0, 1, 1, 0, 1, 0, 0", "sensor": "",
        "code": """\
    MOV R4, #0xFF00     ; SCREEN register
    MOV R5, #0xFF04     ; TOUCH register
    MOV R0, #0          ; tap count
    MOV R7, #8          ; samples to poll
poll:
    LDR R2, [R5]        ; 1 = finger down, 0 = nothing
    CMP R2, #0
    BEQ skip
    ADD R0, R0, #1
    STR R0, [R4]        ; show the new count
skip:
    SUBS R7, R7, #1
    BNE poll
    HLT
""",
    },
    "Phone: battery monitor (uses cache)": {
        "touch": "", "sensor": "92, 88, 85, 80, 76, 72, 70, 66",
        "code": """\
    MOV R1, #0x200      ; log base address in RAM
    MOV R5, #0xFF0C     ; SENSOR register (battery %)
    MOV R7, #8          ; 8 samples
read:
    LDR R2, [R5]        ; read battery level
    STR R2, [R1], #4    ; log it in RAM, R1 += 4
    SUBS R7, R7, #1
    BNE read
    MOV R1, #0x200      ; second pass: add up the log
    MOV R7, #8
    MOV R0, #0
sum:
    LDR R2, [R1], #4    ; log is re-read: the cache helps here
    ADD R0, R0, R2
    SUBS R7, R7, #1
    BNE sum
    LSR R0, R0, #3      ; average = sum / 8
    MOV R4, #0xFF00
    STR R0, [R4]        ; show the average on screen
    HLT
""",
    },
    "Phone: timer read": {
        "touch": "", "sensor": "",
        "code": """\
    MOV R4, #0xFF00     ; SCREEN
    MOV R5, #0xFF08     ; TIMER
    LDR R1, [R5]        ; start time
    MOV R7, #10
wait:
    SUBS R7, R7, #1
    BNE wait
    LDR R2, [R5]        ; end time
    SUB R3, R2, R1
    STR R3, [R4]        ; show elapsed ticks
    HLT
""",
    },
    "Basic: add, store, load": {
        "touch": "", "sensor": "",
        "code": """\
    MOV R0, #10
    MOV R1, #20
    ADD R2, R0, R1
    MOV R3, #100
    STR R2, [R3]
    LDR R4, [R3]
    ADD R5, R4, #1
    HLT
""",
    },
    "Basic: loop sum 5+4+3+2+1": {
        "touch": "", "sensor": "",
        "code": """\
    MOV R0, #0
    MOV R1, #5
loop:
    ADD R0, R0, R1
    SUBS R1, R1, #1
    BNE loop
    HLT
""",
    },
    "Basic: array fill then sum (post-indexed)": {
        "touch": "", "sensor": "",
        "code": """\
    MOV R1, #200        ; array base address
    MOV R2, #1          ; value to store
    MOV R3, #5          ; element count
fill:
    STR R2, [R1], #4    ; store, then R1 += 4
    ADD R2, R2, #1
    SUBS R3, R3, #1
    BNE fill
    MOV R1, #200
    MOV R3, #5
    MOV R0, #0
sum:
    LDR R4, [R1], #4    ; load, then R1 += 4
    ADD R0, R0, R4
    SUBS R3, R3, #1
    BNE sum
    HLT
""",
    },
}


def make_latency(cache, mem_latency):
    """Cycles a RAM access occupies the MEM stage. Without a cache every access is slow."""
    if cache is None:
        return lambda m: mem_latency

    def hook(m):
        hit = cache.access(m["addr"], m["type"] == "write")
        return cache.hit_time if hit else mem_latency
    return hook


def simulate(source, forwarding=True, cache_cfg=None, mem_latency=10, inputs=None, io_latency=2):
    """Return dict: snaps (per-instruction snapshots), pipe, summary, cache (or None)."""
    inputs = inputs or {}
    cpu = CPU(source, inputs=inputs)
    view_cache = Cache(**cache_cfg) if cache_cfg else None
    mem = {}

    def snap(ev):
        return {"regs": list(cpu.regs), "flags": dict(cpu.flags), "event": ev,
                "mem": dict(mem), "screen": cpu.screen, "screen_log": list(cpu.screen_log),
                "cache": view_cache.snapshot() if view_cache else None}

    snaps = [snap(None)]
    steps = 0
    while not cpu.halted:
        ev = cpu.step()
        if ev is None:
            break
        steps += 1
        if steps > MAX_STEPS:
            raise CPUError("Program ran too long (infinite loop?)")
        if ev["mem"]:
            if ev["mem"]["type"] == "write":
                mem[ev["mem"]["addr"]] = ev["mem"]["data"]
            if view_cache:
                view_cache.access(ev["mem"]["addr"], ev["mem"]["type"] == "write", ref=steps)
        snaps.append(snap(ev))

    # The pipeline gets its own, identical cache (same accesses -> same hits/misses)
    pcache = Cache(**cache_cfg) if cache_cfg else None
    pipe = Pipeline(CPU(source, inputs=inputs), forwarding,
                    make_latency(pcache, mem_latency), io_latency)
    summary = pipe.run(MAX_STEPS)
    return {"snaps": snaps, "pipe": pipe, "summary": summary, "cache": view_cache,
            "mem_latency": mem_latency, "inputs": inputs}


def _one(source, inputs, forwarding, cache_cfg, mem_latency):
    pcache = Cache(**cache_cfg) if cache_cfg else None
    pipe = Pipeline(CPU(source, inputs=inputs), forwarding, make_latency(pcache, mem_latency))
    return pipe.run(MAX_STEPS), pcache


def compare_all(source, inputs=None, cache_cfg=None, mem_latency=10):
    """Results table: 3 CPU styles x (no cache / cache). Row 1 is the baseline."""
    inputs = inputs or {}
    cfg = cache_cfg or DEFAULT_CACHE
    rows = []
    for use_cache in (False, True):
        c = cfg if use_cache else None
        s_nofwd, _ = _one(source, inputs, False, c, mem_latency)
        s_fwd, pc = _one(source, inputs, True, c, mem_latency)
        n = s_fwd["instructions"]
        if n == 0:
            return []
        tail = "with cache" if use_cache else "no cache"
        hit = f"{pc.hit_rate * 100:.0f}%" if pc and pc.accesses else "-"
        for name, cycles in (("No pipeline", s_fwd["non_pipelined_cycles"]),
                             ("Pipeline, no forwarding", s_nofwd["cycles"]),
                             ("Pipeline + forwarding", s_fwd["cycles"])):
            rows.append({"Configuration": f"{name}, {tail}", "Cycles": cycles,
                         "CPI": round(cycles / n, 2), "Cache hit rate": hit})
    base = rows[0]["Cycles"]
    for r in rows:
        r["Speedup"] = round(base / r["Cycles"], 2) if r["Cycles"] else 0
    return rows
