"""Read-only (M2.3 Stage C0 closure): dependency audit of every asset under /Game/CyberWarden/Anims. For each asset: its hard and soft
package dependencies (split into inside / outside the folder, engine and script packages omitted) and the packages that reference it
(project-wide). Flags assets nothing else in the folder needs. Loads nothing, saves nothing; only writes Saved/C0_AuditDependencies.txt.

  powershell -File Tools\\RunHeadless.ps1 -Script Tools\\C0_AuditDependencies.py
"""
import unreal

ROOT = "/Game/CyberWarden/Anims"
out = []


def p(m):
    out.append(str(m))
    unreal.log("[C0] " + str(m))


ar = unreal.AssetRegistryHelpers.get_asset_registry()
ar.scan_paths_synchronous(["/Game"], True)
opts = unreal.AssetRegistryDependencyOptions(include_soft_package_references=True, include_hard_package_references=True,
                                            include_searchable_names=False, include_soft_management_references=False,
                                            include_hard_management_references=False)
pkgs = sorted(str(a.package_name) for a in ar.get_assets_by_path(ROOT, recursive=True))
p("assets under %s: %d" % (ROOT, len(pkgs)))
used_by_folder = {k: set() for k in pkgs}
for pkg in pkgs:
    deps = [str(d) for d in ar.get_dependencies(pkg, opts)]
    game = [d for d in deps if d.startswith("/Game")]
    inside = [d for d in game if d.startswith(ROOT)]
    outside = [d for d in game if not d.startswith(ROOT)]
    for d in inside:
        if d in used_by_folder:
            used_by_folder[d].add(pkg)
    p("%s" % pkg)
    p("   inside : %s" % [d.replace(ROOT + "/", "") for d in inside])
    p("   outside: %s" % outside)
for pkg in pkgs:
    refs = sorted(str(r) for r in ar.get_referencers(pkg, opts))
    refs_game = [r for r in refs if r.startswith("/Game")]
    outside = [r for r in refs_game if not r.startswith(ROOT)]
    p("REFERENCED %s by inside=%s outside=%s" % (pkg.replace(ROOT + "/", ""), sorted(x.replace(ROOT + "/", "") for x in used_by_folder[pkg]), outside))
p("assets nothing in the folder references: %s" % [k.replace(ROOT + "/", "") for k, v in used_by_folder.items() if not v])

with open(unreal.Paths.project_saved_dir() + "C0_AuditDependencies.txt", "w") as fh:
    fh.write("\n".join(out))
unreal.SystemLibrary.quit_editor()
