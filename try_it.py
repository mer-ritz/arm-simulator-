from cpu import CPU
from pipeline import Pipeline

program = """
    MOV R3, #100
    MOV R0, #5
    STR R0, [R3]
    LDR R4, [R3]
    ADD R5, R4, #1
    HLT
"""

for fwd in (False, True):
    p = Pipeline(CPU(program), forwarding=fwd)
    summary = p.run()
    print("Forwarding:", fwd)
    print(p.diagram())
    print("cycles:", summary["cycles"], "CPI:", round(summary["cpi"], 2),
          "stalls:", summary["data_stalls"], "\n")