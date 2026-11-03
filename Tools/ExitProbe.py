"""Workload for the shutdown-crash A/B experiment: proves the C++ module classes are loaded, then runs ValidateSchedule.py.

Markers: [EXITPROBE] module=ok|MISSING  and (from ValidateSchedule) [SCHEDCHK] RESULT. The process exit code is judged separately.
"""
import os
import runpy

import unreal

ok = all(hasattr(unreal, n) for n in ("PrisonScheduleManager", "PrisonScheduleComponent", "PrisonScheduleData"))
unreal.log("[EXITPROBE] module=%s" % ("ok" if ok else "MISSING"))
runpy.run_path(os.path.join(unreal.Paths.project_dir(), "Tools", "ValidateSchedule.py"))
