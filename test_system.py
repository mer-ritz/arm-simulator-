"""Run with:  python test_system.py   (cache, phone I/O, new instructions, demo programs)"""
from cache import Cache
from cpu import CPU
from runner import SAMPLES, compare_all, simulate


def parse(text):
    return [int(x) for x in text.replace(",", " ").split()]


def demo(name):
    s = SAMPLES[name]
    return s["code"], {"touch": parse(s["touch"]), "sensor": parse(s["sensor"])}


def test_cache_direct_mapped():
    c = Cache(size=64, block=16, ways=1)          # 4 sets
    results = [c.access(a) for a in (0, 4, 16, 0, 64, 0)]
    # miss, hit (same block), miss, hit, miss (conflict evicts block 0), miss
    assert results == [False, True, False, True, False, False]
    assert (c.hits, c.misses) == (2, 4)


def test_cache_two_way_lru():
    c = Cache(size=64, block=16, ways=2)          # 2 sets, 2 ways
    results = [c.access(a) for a in (0, 32, 0, 64, 32, 64)]
    assert results == [False, False, True, False, False, True]
    assert (c.hits, c.misses) == (2, 4)


def test_shift_and_multiply():
    cpu = CPU("MOV R0,#40\nLSR R1,R0,#3\nLSL R2,R0,#2\nMUL R3,R0,R1\nHLT")
    cpu.run()
    assert (cpu.regs[1], cpu.regs[2], cpu.regs[3]) == (5, 160, 200)


def test_io_screen_and_sensor():
    cpu = CPU("MOV R4,#0xFF00\nMOV R5,#0xFF0C\nLDR R1,[R5]\nSTR R1,[R4]\nHLT",
              inputs={"sensor": [77]})
    cpu.run()
    assert cpu.screen == 77


def test_auto_brightness_demo():
    code, inp = demo("Phone: auto-brightness")
    cpu = CPU(code, inputs=inp)
    cpu.run()
    assert [v for _, v in cpu.screen_log] == [40, 120, 200, 90]


def test_touch_counter_demo():
    code, inp = demo("Phone: touch counter")
    cpu = CPU(code, inputs=inp)
    cpu.run()
    assert [v for _, v in cpu.screen_log] == [1, 2, 3, 4]


def test_battery_demo_and_cache():
    code, inp = demo("Phone: battery monitor (uses cache)")
    r = simulate(code, True, {"size": 256, "block": 16, "ways": 1}, 10, inp)
    assert r["snaps"][-1]["screen"] == 78         # (92+88+85+80+76+72+70+66)//8
    assert r["cache"].hits > r["cache"].misses    # the re-read pass hits


def test_timer_demo():
    code, inp = demo("Phone: timer read")
    cpu = CPU(code, inputs=inp)
    cpu.run()
    assert cpu.screen_log[-1][1] > 20             # ~10 loop iterations x 2 instructions


def test_cache_makes_it_faster():
    code, inp = demo("Phone: battery monitor (uses cache)")
    rows = compare_all(code, inp, {"size": 256, "block": 16, "ways": 1}, 10)
    cyc = {r["Configuration"]: r["Cycles"] for r in rows}
    assert len(rows) == 6
    assert cyc["Pipeline + forwarding, with cache"] < cyc["Pipeline + forwarding, no cache"]
    assert cyc["Pipeline + forwarding, with cache"] < cyc["Pipeline, no forwarding, with cache"]
    assert cyc["Pipeline + forwarding, with cache"] < cyc["No pipeline, with cache"]
    assert rows[0]["Speedup"] == 1.0


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("PASS", t.__name__)
    print(f"{len(tests)} tests passed")
