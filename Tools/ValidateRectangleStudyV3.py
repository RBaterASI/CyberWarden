"""Standalone analytic validation of the Floor 1 rectangle study V3. NO Unreal Editor, NO project DLL.

Run with the engine's bundled Python (a separate, Epic-signed python.exe that never loads the CyberWarden module):
  "C:\\Program Files\\Epic Games\\UE_5.8\\Engine\\Binaries\\ThirdParty\\Python3\\Win64\\python.exe" -I Tools\\ValidateRectangleStudyV3.py

Writes Docs/Layout/S01_LW_F1_RectangleStudy_V3_report.txt. Exit code 1 if any check fails.
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROJECT, "Content", "Python"))
import cw_rectstudy_v3 as cw  # noqa: E402

LAYOUT = os.path.join(PROJECT, "Docs", "Layout", "S01_LW_F1_RectangleStudy_V3.json")
REPORT = os.path.join(PROJECT, "Docs", "Layout", "S01_LW_F1_RectangleStudy_V3_report.txt")

lines = []


def rep(s):
    lines.append(s)
    print(s)


t0 = time.time()
study = cw.StudyV2(cw.load(LAYOUT))
errors, warnings = cw.run_analysis(study, rep)
rep("Analytic validation only (no engine collision, no PIE). Elapsed %.1f s." % (time.time() - t0))
with open(REPORT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")
sys.exit(1 if errors else 0)
