"""Run with:  python test_cpu.py"""
from cpu import CPU


def test_add_store_load():
    cpu = CPU("""
        MOV R0, #10
        MOV R1, #20
        ADD R2, R0, R1
        MOV R3, #100
        STR R2, [R3]
        LDR R4, [R3]
        HLT
    """)
    cpu.run()
    assert cpu.regs[2] == 30
    assert cpu.read_word(100) == 30
    assert cpu.regs[4] == 30


def test_loop_sum():
    cpu = CPU("""
        MOV R0, #0
        MOV R1, #5
    loop:
        ADD R0, R0, R1
        SUBS R1, R1, #1
        BNE loop
        HLT
    """)
    cpu.run()
    assert cpu.regs[0] == 15          # 5+4+3+2+1


def test_addressing_modes():
    cpu = CPU("""
        MOV R1, #200
        MOV R0, #7
        STR R0, [R1], #4      ; post-index: store at 200, then R1 = 204
        MOV R0, #9
        STR R0, [R1, #4]!     ; pre-index: R1 = 208, store at 208
        MOV R2, #200
        LDR R3, [R2]          ; register indirect
        MOV R5, #8
        LDR R4, [R2, R5]      ; base + register offset (address 208)
        HLT
    """)
    cpu.run()
    assert cpu.read_word(200) == 7
    assert cpu.regs[1] == 208
    assert cpu.regs[3] == 7
    assert cpu.regs[4] == 9


def test_function_call():
    cpu = CPU("""
        MOV R0, #3
        BL double
        HLT
    double:
        ADD R0, R0, R0
        MOV PC, LR
    """)
    cpu.run()
    assert cpu.regs[0] == 6


def test_flags():
    cpu = CPU("""
        MOV R0, #5
        CMP R0, #5
        HLT
    """)
    cpu.run()
    assert cpu.flags["Z"] == 1


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("PASS", t.__name__)
    print(f"{len(tests)} tests passed")
