"""Run with:  python test_pipeline.py
Expected cycle counts were worked out by hand on paper."""
from cpu import CPU
from pipeline import Pipeline


def run(src, **kw):
    p = Pipeline(CPU(src), **kw)
    return p, p.run()


def test_independent_instructions():
    # 4 independent instructions: n + 4 = 8 cycles, no stalls
    p, s = run("MOV R0,#1\nMOV R1,#2\nMOV R2,#3\nMOV R3,#4")
    assert s["cycles"] == 8
    assert s["data_stalls"] == 0
    assert s["non_pipelined_cycles"] == 20


def test_dependent_chain_with_forwarding():
    p, s = run("MOV R0,#1\nADD R1,R0,#1\nADD R2,R1,#1")
    assert s["cycles"] == 7           # forwarding removes all stalls
    assert s["data_stalls"] == 0


def test_dependent_chain_without_forwarding():
    p, s = run("MOV R0,#1\nADD R1,R0,#1\nADD R2,R1,#1", forwarding=False)
    assert s["cycles"] == 11          # 2 stall cycles per dependency
    assert s["data_stalls"] == 4


def test_load_use_hazard():
    # Even with forwarding, a load followed by its user needs 1 stall
    p, s = run("MOV R3,#100\nLDR R4,[R3]\nADD R5,R4,#1")
    assert s["cycles"] == 8           # 3 + 4 + 1 stall
    assert s["data_stalls"] == 1


def test_taken_branch_penalty():
    p, s = run("""
        MOV R1, #3
    loop:
        SUBS R1, R1, #1
        BNE loop
    """)
    assert s["instructions"] == 7
    assert s["flush_cycles"] == 4     # 2 taken branches x 2 lost cycles
    assert s["cycles"] == 15


def test_slow_memory_blocks_pipeline():
    fast, s1 = run("MOV R3,#100\nLDR R4,[R3]\nMOV R5,#1")
    slow, s2 = run("MOV R3,#100\nLDR R4,[R3]\nMOV R5,#1",
                   mem_latency=lambda m: 5)       # pretend a cache miss
    assert s1["cycles"] == 7
    assert s2["cycles"] == 11


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("PASS", t.__name__)
    print(f"{len(tests)} tests passed\n")

    print("Pipeline diagram (load-use example, forwarding ON):")
    p, s = run("MOV R3,#100\nLDR R4,[R3]\nADD R5,R4,#1")
    print(p.diagram())
    print(s)
