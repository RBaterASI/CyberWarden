"""Standalone analytic validation of the Floor 1 rectangle study. NO Unreal Editor, NO project DLL.

Run with the engine's bundled Python (a separate, Epic-signed python.exe that never loads the CyberWarden module):
  "C:\\Program Files\\Epic Games\\UE_5.8\\Engine\\Binaries\\ThirdParty\\Python3\\Win64\\python.exe" -I Tools\\ValidateRectangleStudy.py

Writes Docs/Layout/S01_LW_F1_RectangleStudy_report.txt (geometry summary, capsule walk simulation, reachability,
unprotected edges, sightlines, guard-route cover, CCTV coverage, camera clearance estimate). Exit code 1 if any check fails.
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROJECT, "Content", "Python"))
import cw_rectstudy  # noqa: E402

LAYOUT = os.path.join(PROJECT, "Docs", "Layout", "S01_LW_F1_RectangleStudy.json")
REPORT = os.path.join(PROJECT, "Docs", "Layout", "S01_LW_F1_RectangleStudy_report.txt")

lines = []


def rep(s):
    lines.append(s)
    print(s)


t0 = time.time()
study = cw_rectstudy.Study(cw_rectstudy.load(LAYOUT))
errors, warnings = cw_rectstudy.run_analysis(study, rep)
rep("Analytic validation only (no engine collision, no PIE). Elapsed %.1f s." % (time.time() - t0))
with open(REPORT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")
sys.exit(1 if errors else 0)
