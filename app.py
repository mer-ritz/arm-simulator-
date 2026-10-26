"""ARM Lab - Streamlit interface.   Start with:   streamlit run app.py"""
import html

import pandas as pd
import streamlit as st

from assembler import AsmError
from cpu import CPUError
from runner import SAMPLES, compare_all, simulate

st.set_page_config(page_title="ARM Lab", layout="wide")
st.title("ARM Lab")
st.caption("Mobile-Phone ARM Processor Architecture Simulator: a simplified ARM-like RISC CPU "
           "with registers, addressing modes, a 5-stage pipeline, an L1 cache and phone I/O.")

REG_NAMES = [f"R{i}" for i in range(13)] + ["SP", "LR", "PC"]
STAGE_COLORS = {"IF": "#3b82f6", "ID": "#8b5cf6", "EX": "#10b981",
                "MEM": "#f59e0b", "WB": "#6b7280"}

ARCH_DOT = r"""
digraph G {
  rankdir=LR; bgcolor="#f1f5f9"; fontname="Helvetica"; nodesep=0.35; ranksep=0.5;
  node [shape=box, style="rounded,filled", fillcolor="#ffffff", color="#334155",
        fontname="Helvetica", fontcolor="#0f172a"];
  edge [color="#475569", fontname="Helvetica", fontsize=10, fontcolor="#0f172a"];
  PROG [label="Assembly\nprogram", fillcolor="#fef9c3"];
  subgraph cluster_cpu {
    label="ARM-like RISC CPU (5-stage pipeline)"; fontcolor="#0f172a"; color="#334155"; style="rounded";
    IF [label="IF\nfetch"]; ID [label="ID\ndecode +\nregister read"];
    EX [label="EX\nALU"]; MEM [label="MEM\nload / store"]; WB [label="WB\nwrite back"];
    REG [label="Register file\nR0-R12, SP, LR, PC\nflags N Z C V", fillcolor="#dbeafe"];
    IF -> ID -> EX -> MEM -> WB;
    ID -> REG [dir=both]; WB -> REG;
    EX -> ID [label="forwarding", style=dashed, constraint=false];
  }
  PROG -> IF;
  CACHE [label="L1 cache\nhit = 1 cycle", fillcolor="#dcfce7"];
  RAM [label="Main memory (RAM)\nslow: miss penalty", fillcolor="#fee2e2"];
  IO [label="Memory-mapped I/O\n0xFF00 - 0xFF0F", fillcolor="#fae8ff"];
  MEM -> CACHE [dir=both]; CACHE -> RAM [dir=both]; MEM -> IO [dir=both];
  SCREEN [label="SCREEN 0xFF00"]; TOUCH [label="TOUCH 0xFF04"];
  TIMER [label="TIMER 0xFF08"]; SENSOR [label="SENSOR 0xFF0C"];
  IO -> SCREEN; IO -> TOUCH; IO -> TIMER; IO -> SENSOR;
}
"""


# ---------------------------------------------------------------- helpers
def parse_ints(text):
    return [int(x) for x in text.replace(",", " ").split()]


def pipeline_html(rows, highlight):
    total = rows[-1].W
    h = ['<div style="overflow-x:auto"><table style="border-collapse:collapse;'
         'font-family:monospace;font-size:13px">']
    h.append('<tr><th style="text-align:left;padding:4px 10px">Instruction</th>')
    for c in range(1, total + 1):
        h.append(f'<th style="padding:4px 6px">{c}</th>')
    h.append("</tr>")
    for r in rows:
        weight = "700" if r.index == highlight else "400"
        mark = "&#9654; " if r.index == highlight else ""
        h.append(f'<tr><td style="padding:4px 10px;white-space:nowrap;font-weight:{weight}">'
                 f'{mark}{html.escape(r.text)}</td>')
        for c in range(1, total + 1):
            label = r.cells.get(c)
            if label:
                stalled = label.endswith("*")
                stage = label.rstrip("*")
                bg = "#ef4444" if stalled else STAGE_COLORS[stage]
                h.append(f'<td style="background:{bg};color:white;text-align:center;'
                         f'padding:4px 6px;border:1px solid rgba(0,0,0,0.25)">{stage}</td>')
            else:
                h.append("<td></td>")
        h.append("</tr>")
    h.append("</table></div>")
    return "".join(h)


FIRST = next(iter(SAMPLES))
if "code" not in st.session_state:
    st.session_state["code"] = SAMPLES[FIRST]["code"]
    st.session_state["touch_txt"] = SAMPLES[FIRST]["touch"]
    st.session_state["sensor_txt"] = SAMPLES[FIRST]["sensor"]


def load_sample():
    s = SAMPLES[st.session_state["sample"]]
    st.session_state["code"] = s["code"]
    st.session_state["touch_txt"] = s["touch"]
    st.session_state["sensor_txt"] = s["sensor"]
    st.session_state.pop("result", None)
    st.session_state.pop("step", None)


def reset_all():
    st.session_state.pop("result", None)
    st.session_state.pop("step", None)


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Settings")
    forwarding = st.toggle("Data forwarding", value=True,
                           help="Forward ALU results straight to the next instruction.")
    st.subheader("Cache")
    use_cache = st.toggle("Enable L1 cache", value=True)
    cache_size = st.selectbox("Cache size (bytes)", [64, 128, 256, 512, 1024], index=2)
    block = st.selectbox("Block size (bytes)", [8, 16, 32], index=1)
    ways = st.selectbox("Associativity (ways)", [1, 2, 4], index=0,
                        help="1 = direct-mapped")
    mem_lat = st.slider("Main memory latency (cycles)", 2, 30, 10)
    st.subheader("Phone inputs")
    st.text_input("Touch events", key="touch_txt", help="Comma-separated numbers read from 0xFF04")
    st.text_input("Sensor readings", key="sensor_txt", help="Comma-separated numbers read from 0xFF0C")
    st.divider()
    st.selectbox("Sample program", list(SAMPLES), key="sample")
    st.button("Load sample", on_click=load_sample)
    st.divider()
    st.markdown("**Instructions**  \n"
                "`MOV ADD SUB AND ORR EOR LSL LSR MUL CMP`  \n"
                "`LDR STR`  \n"
                "`B BEQ BNE BGT BLT BGE BLE BL`  \n"
                "`HLT`  \n"
                "Add `S` (e.g. `SUBS`) to set flags.  \n"
                "**Devices:** `0xFF00` SCREEN, `0xFF04` TOUCH, `0xFF08` TIMER, `0xFF0C` SENSOR")

cache_cfg = None
if use_cache:
    if cache_size % (block * ways) == 0:
        cache_cfg = {"size": cache_size, "block": block, "ways": ways}
    else:
        st.sidebar.error("Cache size must be a multiple of block size x ways. Cache is off.")

try:
    inputs = {"touch": parse_ints(st.session_state["touch_txt"]),
              "sensor": parse_ints(st.session_state["sensor_txt"])}
except ValueError:
    st.sidebar.error("Inputs must be whole numbers separated by commas.")
    inputs = {"touch": [], "sensor": []}

sig = (forwarding, tuple(sorted(cache_cfg.items())) if cache_cfg else None, mem_lat,
       tuple(inputs["touch"]), tuple(inputs["sensor"]))


def run_sim(src):
    """Run the simulation and store the result. Returns True on success."""
    try:
        out = simulate(src, forwarding, cache_cfg, mem_lat, inputs)
        out["compare"] = compare_all(src, inputs, cache_cfg, mem_lat)
    except (AsmError, CPUError) as e:
        st.error(f"Error: {e}")
        st.session_state.pop("result", None)
        return False
    out["src"], out["sig"] = src, sig
    st.session_state["result"] = out
    return True


# ---------------------------------------------------------------- editor
code = st.text_area("Assembly program", key="code", height=300)
b1, b2, _ = st.columns([1, 1, 6])
if b1.button("▶ Run", type="primary"):
    if run_sim(code):
        st.session_state["step"] = len(st.session_state["result"]["snaps"]) - 1
b2.button("Reset", on_click=reset_all)

res = st.session_state.get("result")
if res and res["sig"] != sig:                  # a setting changed: redo the simulation
    run_sim(res["src"])
    res = st.session_state.get("result")

if not res:
    st.info("Write or load a program, then press **Run**.")
    st.stop()

if res["src"] != code:
    st.warning("The program was edited after the last run. Press **Run** to update the results.")

snaps, pipe, summary, cache = res["snaps"], res["pipe"], res["summary"], res["cache"]
n = len(snaps) - 1
if n == 0:
    st.info("The program has no instructions.")
    st.stop()

tabs = st.tabs(["Step-through", "Pipeline", "Cache", "Phone I/O",
                "Performance", "Architecture", "Execution log"])
tab_step, tab_pipe, tab_cache, tab_phone, tab_perf, tab_arch, tab_log = tabs

# ---------------------------------------------------------------- step-through
with tab_step:
    step = st.slider("Step through the program (0 = before the first instruction)",
                     0, n, key="step")
    snap = snaps[step]
    prev = snaps[step - 1] if step > 0 else snaps[0]
    ev = snap["event"]
    if ev is None:
        st.info("Initial state: all registers are 0 except SP.")
    else:
        msg = f"**Instruction {step}:** `{ev['text']}` (address {ev['pc']:#06x})"
        if ev["alu"]:
            msg += f"  \nALU: {ev['alu']}"
        if ev["mem"]:
            kind = "reads" if ev["mem"]["type"] == "read" else "writes"
            msg += f"  \nMemory {kind} address {ev['mem']['addr']}, value {ev['mem']['data']}"
            if snap["cache"] and snap["cache"]["last"]:
                msg += f"  \nCache: **{snap['cache']['last']['Result']}**"
        if ev["io"]:
            kind = "reads from" if ev["io"]["type"] == "read" else "writes to"
            msg += f"  \nI/O {kind} {ev['io']['device']} ({ev['io']['addr']:#06x}), value {ev['io']['data']}"
        if ev["branch_taken"]:
            msg += "  \nBranch taken"
        st.info(msg)

    st.subheader("Registers")
    for row in range(4):
        cols = st.columns(4)
        for k in range(4):
            i = row * 4 + k
            val, old = snap["regs"][i], prev["regs"][i]
            cols[k].metric(REG_NAMES[i], val,
                           delta=(val - old) if val != old else None, delta_color="off")

    left, right = st.columns(2)
    with left:
        st.subheader("Flags")
        fc = st.columns(4)
        for col, f in zip(fc, "NZCV"):
            col.metric(f, snap["flags"][f])
    with right:
        st.subheader("Memory (written words)")
        if snap["mem"]:
            df = pd.DataFrame([{"Address": f"{a:#06x}", "Decimal": a, "Value": v}
                               for a, v in sorted(snap["mem"].items())])
            st.dataframe(df, hide_index=True)
        else:
            st.caption("Nothing written to memory yet.")

# ---------------------------------------------------------------- pipeline
with tab_pipe:
    st.subheader("Pipeline diagram")
    st.caption("Each row is an instruction, each column a clock cycle. "
               "Red cells mean the instruction is waiting (data hazard, or slow memory after a cache miss). "
               "The arrow marks the instruction selected in the Step-through tab.")
    st.markdown(pipeline_html(pipe.rows, highlight=step - 1), unsafe_allow_html=True)
    st.markdown(" ".join(
        f'<span style="background:{c};color:white;padding:2px 8px;border-radius:4px">{s}</span>'
        for s, c in STAGE_COLORS.items()), unsafe_allow_html=True)

# ---------------------------------------------------------------- cache
with tab_cache:
    st.subheader("L1 cache")
    if cache is None:
        st.info("The cache is switched off, so every RAM access takes the full "
                f"{mem_lat} cycles. Turn it on in the sidebar.")
    else:
        cs = snap["cache"]
        st.caption(cache.describe())
        m = st.columns(4)
        m[0].metric("Accesses", cs["accesses"])
        m[1].metric("Hits", cs["hits"])
        m[2].metric("Misses", cs["misses"])
        m[3].metric("Hit rate", f"{(cs['hits'] / cs['accesses'] * 100) if cs['accesses'] else 0:.0f}%")
        m2 = st.columns(3)
        m2[0].metric("Avg access time, with cache", f"{cache.amat(mem_lat):.2f} cycles")
        m2[1].metric("Avg access time, no cache", f"{mem_lat} cycles")
        m2[2].metric("Memory access speedup",
                     f"{mem_lat / cache.amat(mem_lat):.2f}x" if cache.accesses else "-")
        st.caption("Numbers at the top follow the Step-through slider; averages are for the whole run.")
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Contents at this step")
            if cs["lines"]:
                st.dataframe(pd.DataFrame(cs["lines"]), hide_index=True)
            else:
                st.caption("The cache is empty.")
        with c2:
            st.subheader("Access log")
            if cache.log:
                st.dataframe(pd.DataFrame(cache.log), hide_index=True)
            else:
                st.caption("This program never touched RAM.")

# ---------------------------------------------------------------- phone I/O
with tab_phone:
    st.subheader("Phone I/O")
    sv = snap["screen"]
    lvl = max(0, min(255, sv))
    fg = "#000" if lvl > 128 else "#fff"
    p1, p2 = st.columns([1, 3])
    with p1:
        st.markdown(
            f'<div style="width:150px;height:280px;border:7px solid #1f2937;border-radius:28px;'
            f'background:rgb({lvl},{lvl},{lvl});display:flex;align-items:center;'
            f'justify-content:center;font-size:40px;font-weight:700;color:{fg}">{sv}</div>',
            unsafe_allow_html=True)
        st.caption("Phone screen at this step (grey level = value, max 255)")
    with p2:
        log = snap["screen_log"]
        if log:
            st.markdown("**Values written to the screen so far**")
            st.line_chart(pd.DataFrame({"Screen value": [v for _, v in log]}))
        else:
            st.caption("Nothing written to the screen yet.")
        st.markdown("**Input queues**")
        st.write(f"Touch events: {res['inputs']['touch'] or 'none'}  \n"
                 f"Sensor readings: {res['inputs']['sensor'] or 'none'}")
    st.markdown("**Memory-mapped devices**")
    st.dataframe(pd.DataFrame([
        {"Address": "0xFF00", "Device": "SCREEN", "Access": "write / read", "Meaning": "value shown on the phone screen"},
        {"Address": "0xFF04", "Device": "TOUCH", "Access": "read", "Meaning": "next touch event (0 if none)"},
        {"Address": "0xFF08", "Device": "TIMER", "Access": "read", "Meaning": "instructions executed so far"},
        {"Address": "0xFF0C", "Device": "SENSOR", "Access": "read", "Meaning": "next sensor reading (0 if none)"},
    ]), hide_index=True)
    st.caption("I/O accesses bypass the cache and take 2 cycles in the MEM stage.")

# ---------------------------------------------------------------- performance
with tab_perf:
    st.subheader("Performance (current settings)")
    m = st.columns(6)
    m[0].metric("Instructions", summary["instructions"])
    m[1].metric("Cycles", summary["cycles"])
    m[2].metric("CPI", f"{summary['cpi']:.2f}")
    m[3].metric("Data stalls", summary["data_stalls"])
    m[4].metric("Flush cycles", summary["flush_cycles"])
    m[5].metric("Speedup", f"{summary['speedup']:.2f}x",
                help="Compared with a CPU that finishes each instruction before starting the next.")
    st.subheader("Results table: pipeline x forwarding x cache")
    if res["compare"]:
        dfc = pd.DataFrame(res["compare"])
        st.dataframe(dfc, hide_index=True)
        st.bar_chart(dfc.set_index("Configuration")[["Cycles"]])
        st.caption("Same program in six configurations. The first row is the baseline "
                   "(speedup 1.0). Cache settings come from the sidebar.")

# ---------------------------------------------------------------- architecture
with tab_arch:
    st.subheader("Architecture")
    st.graphviz_chart(ARCH_DOT)
    st.markdown(
        "- **RISC:** fixed instruction set, load/store architecture (only `LDR`/`STR` touch memory).  \n"
        "- **Registers:** R0-R12 general purpose, SP, LR, PC, plus N/Z/C/V flags.  \n"
        "- **Addressing modes:** immediate, register, register indirect, base + offset, "
        "pre-indexed `[R1, #4]!`, post-indexed `[R1], #4`.  \n"
        "- **Pipeline:** IF, ID, EX, MEM, WB with stalls, forwarding and branch flushes.  \n"
        "- **Cache and I/O:** see the Cache and Phone I/O tabs.")

# ---------------------------------------------------------------- log
with tab_log:
    st.subheader("Execution log")
    rows = []
    for i, s in enumerate(snaps[1:], start=1):
        e = s["event"]
        rows.append({
            "#": i,
            "Address": f"{e['pc']:#06x}",
            "Instruction": e["text"],
            "Register changes": ", ".join(f"{k}={v}" for k, v in e["writes"].items()),
            "Memory": (f"{e['mem']['type']} @{e['mem']['addr']} = {e['mem']['data']}"
                       if e["mem"] else ""),
            "I/O": (f"{e['io']['type']} {e['io']['device']} = {e['io']['data']}"
                    if e["io"] else ""),
            "Branch taken": "yes" if e["branch_taken"] else "",
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True)
