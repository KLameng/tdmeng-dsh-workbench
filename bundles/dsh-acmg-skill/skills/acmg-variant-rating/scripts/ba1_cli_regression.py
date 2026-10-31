# -*- coding: utf-8 -*-
"""回归确认：CLI dict 修复后，所有带 dict 参数的 vcep 函数 CLI 均可用（不破坏既有）。"""
import subprocess, sys, os
ws = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def run(*args):
    r = subprocess.run([sys.executable, os.path.join(ws, "scripts", "acmg_evidence.py")] + list(args),
                       capture_output=True, text=True, encoding="utf-8")
    return (r.stdout or r.stderr).strip().splitlines()
print("BA1   :", run("ba1_vcep_band", "0.003", "CDH1", "AD", '{"cutoff":0.002,"direction":"ge"}')[0])
print("BS1   :", run("bs1_vcep_band", "0.01", "MYH7", "AD", '{"strong":0.0001}')[0])
print("PS3   :", run("ps3_vcep_band", '{"kato":"non-functional","lof_majority":true}', "TP53", '{"type":"experiment","bands":{"strong":{"kato":"non-functional","lof_majority":true}}}')[0])
print("BP4   :", run("bp4_vcep_band", '{"revel":0.1}', "GJB2", '{"type":"tool_threshold","tool":"revel","le":0.15}')[0])
print("PP3   :", run("pp3_vcep_band", '{"revel":0.80}', "ACADVL", '{"type":"tool_threshold","tool":"revel","ge":0.75}')[0])
print("PM3   :", run("pm3_vcep_band", '[{"type":"A","n":1}]', "GJB2", '{}')[0])
