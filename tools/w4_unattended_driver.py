#!/usr/bin/env python3
"""W4 restructure driver — APPROVED PLAN, reconciled.

Place at: tools/w4_unattended_driver.py  (run from repo root: python tools/w4_unattended_driver.py ...)

Supervised, batch-by-batch package restructure of the flat root. Runtime code
moves into packages; documented human-facing commands keep working via REAL CLI
wrappers (runpy entrypoints, not sys.modules shims). Worst-case state at any
instant is "last green commit."

Corrections folded in from review rounds:
  * commit() HALTS on a failed git commit — never returns a stale "success" SHA.
  * CLI wrappers are real: runpy.run_module(pkg.mod, run_name="__main__").
  * Wave 5 is wrapper-aware: allowlisted root commands become wrappers, not deleted.
  * Step 0 GENERATES the grandfather baseline + wrapper candidates from the live
    repo (no hand-guessed lists).
  * Do NOT git stash across the run — pre-flight requires a clean, committed tree.

WAVES
  0 preflight (clean+committed tree, branch, baseline gate, generate Step-0 files)
  1 tests/smokes/replays/evals -> tests/            (no wrapper)
  2 non-smoke leaves           -> package           (identity shim)
  3 clustered modules          -> package           (identity shim)
  4 hubs + uncategorized       -> package           (identity shim, FULL gate/batch)
  5 de-shim: rewrite imports; delete shims; allowlisted files -> CLI wrapper (FULL gate/batch)
  6 .app/import verification    (no auto-rollback)

USAGE
  python tools/w4_unattended_driver.py --step0          # generate baselines only
  python tools/w4_unattended_driver.py --plan-only
  python tools/w4_unattended_driver.py --dry-run --waves 1,2,3,4,5
  python tools/w4_unattended_driver.py --waves 1 --gate full-per-wave --auto-rollback
"""
from __future__ import annotations

import argparse
import ast
import collections
import datetime as dt
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(".").resolve()
BRANCH = "w4/restructure"
LOG_DIR = ROOT / "logs" / "w4"
GATE_CMD_FULL = [sys.executable, "local_ci.py"]
GRANDFATHER_FILE = LOG_DIR / "grandfather_baseline.txt"
WRAPPER_CANDIDATES_FILE = LOG_DIR / "cli_wrapper_candidates.txt"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SMOKE_SUFFIXES = ("_smoke", "_500", "_700", "_10000", "_eval", "_live", "_probe")
SMOKE_DEST = {"_smoke": "tests/smokes", "_500": "tests/replays", "_10000": "tests/replays",
              "_700": "tests/replays", "_eval": "tests/evals", "_live": "tests/smokes", "_probe": "tests/smokes"}
FIXTURE_EXCLUDE = ("_smoke", "_fakes", "_replay_", "phase22_")  # + startswith("live_")

# Never move (gate/build infra + the .app entrypoint with dynamic imports).
KEEP_AT_ROOT = {"code_health", "local_ci", "scored_eval_suite", "main", "conftest",
                "kampung_ai_app", "build_kampung_ai_app"}

# Implementation moves into a package, but a REAL CLI wrapper stays at root.
# Verified to exist with a __main__ block; regenerated/validated in Step 0.
WRAPPER_ALLOWLIST = {"browser_extension_bridge", "service_install", "doctor",
                     "run_demo", "demo_evidence", "live_browser_reliability_run",
                     "live_agentic_reliability_run", "may1_rehearsal",
                     "self_heal_memory", "weekly_memory", "memory_watchdog",
                     "browser_benchmark", "browser_field_tests", "dependency_manifest",
                     "hardware_live_proof", "imac_june8_regression",
                     "memory_recall_eval_compare"}

HUBS = {"storage", "skill_store", "harness_store", "lesson_store", "routine_store",
        "permission_policy", "assistant", "session_memory_store", "route_tracker",
        "harness_artifact_store", "cost_tracker", "workspace_paths", "context_layers",
        "utils", "office_modern_files", "maya_runtime_config"}

CLUSTER_PKG = {
    "browser": "maya_browser", "xai": "maya_voice", "voice": "maya_voice",
    "telegram": "maya_telegram", "document": "maya_documents",
    "office": "maya_documents", "word": "maya_documents", "pptx": "maya_documents",
    "deck": "maya_documents", "excel": "maya_documents", "artifact": "maya_documents",
    "harness": "maya_harness", "travel": "maya_travel", "flight": "maya_travel",
    "stay": "maya_travel", "booking": "maya_travel",
    "canonical": "maya_memory", "memory": "maya_memory",
    "live": "maya_harness",
}
FALLBACK_PKG = "maya_core"
SHIM_MARK = "# W4 compatibility shim"
WRAPPER_MARK = "# W4 CLI wrapper"


def log(msg: str) -> None:
    line = f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_DIR / "driver.log", "a") as fh:
        fh.write(line + "\n")


def sh(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=check)


# --- git -------------------------------------------------------------------
def tree_clean() -> bool:
    return sh("git", "status", "--porcelain").stdout.strip() == ""


def current_branch() -> str:
    return sh("git", "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()


def head_sha() -> str:
    return sh("git", "rev-parse", "HEAD").stdout.strip()


def commit(message: str) -> str:
    """Commit; HALT if git reports failure OR HEAD did not advance (no fake SHA)."""
    before = head_sha()
    sh("git", "add", "-A")
    for path in (GRANDFATHER_FILE, WRAPPER_CANDIDATES_FILE, LOG_DIR / "baseline_ci.txt"):
        if path.exists():
            sh("git", "add", "-f", str(path.relative_to(ROOT)), check=False)
    r = sh("git", "commit", "-m", message, check=False)
    after = head_sha()
    if r.returncode != 0 or after == before:
        raise RuntimeError(f"git commit failed (rc={r.returncode}): {r.stdout}\n{r.stderr}")
    return after[:9]


def hard_rollback() -> None:
    sh("git", "reset", "--hard", "HEAD", check=False)
    sh("git", "clean", "-fd", check=False)


# --- graph -----------------------------------------------------------------
def root_modules() -> dict[str, str]:
    return {p.stem: p.name for p in ROOT.glob("*.py")}


def all_py_files() -> list[Path]:
    skip = {"venv", ".venv", "__pycache__", ".git", ".claude", "backups"}
    return [p for p in ROOT.rglob("*.py") if not any(s in p.parts for s in skip)]


def build_importers(mods: dict[str, str]):
    names = set(mods)
    importers = collections.defaultdict(set)
    for stem, fname in mods.items():
        try:
            tree = ast.parse(Path(fname).read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            continue
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for a in n.names:
                    t = a.name.split(".")[0]
                    if t in names and t != stem:
                        importers[t].add(stem)
            elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
                t = n.module.split(".")[0]
                if t in names and t != stem:
                    importers[t].add(stem)
    return importers


def is_smoke(stem: str) -> bool:
    return any(stem.endswith(s) for s in SMOKE_SUFFIXES)


def smoke_dest(stem: str) -> str:
    for suf, dest in SMOKE_DEST.items():
        if stem.endswith(suf):
            return dest
    return "tests/smokes"


def dest_pkg(stem: str) -> str:
    return CLUSTER_PKG.get(stem.split("_")[0], FALLBACK_PKG)


def is_shim(stem: str) -> bool:
    p = ROOT / f"{stem}.py"
    return p.exists() and SHIM_MARK in p.read_text(errors="ignore")


def is_cli_wrapper(stem: str) -> bool:
    p = ROOT / f"{stem}.py"
    return p.exists() and WRAPPER_MARK in p.read_text(errors="ignore")


# --- Step 0 generators -----------------------------------------------------
def gen_wrapper_candidates() -> list[str]:
    """Root files with __main__ that are referenced as `python X.py` in docs/runbooks."""
    main_files = {p.stem for p in ROOT.glob("*.py")
                  if re.search(r'__name__ == .__main__.', p.read_text(errors="ignore"))}
    documented = set()
    docs = [
        p for p in ROOT.rglob("*.md")
        if not any(part in {".git", "venv", ".venv", "__pycache__", ".claude"} for part in p.parts)
    ]
    for f in all_py_files() + docs:
        try:
            text = f.read_text(errors="ignore")
            for m in re.findall(r'(?:python3?|(?:\./)?venv/bin/python|(?:\./)?\.venv/bin/python|(?:\./)?venv/bin/python3|(?:\./)?\.venv/bin/python3|/[^ \n]+/venv/bin/python)\s+([A-Za-z0-9_./-]+\.py)', text):
                documented.add(Path(m).name[:-3])
        except Exception:
            continue
    cand = sorted(main_files & documented)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    WRAPPER_CANDIDATES_FILE.write_text("\n".join(cand) + "\n")
    log(f"Step0: {len(cand)} CLI wrapper candidates -> {WRAPPER_CANDIDATES_FILE}")
    # surface drift vs the hard allowlist for human review
    extra = sorted(set(cand) - WRAPPER_ALLOWLIST - KEEP_AT_ROOT)
    missing = sorted(WRAPPER_ALLOWLIST - set(cand))
    if extra:
        log(f"Step0 REVIEW: documented commands NOT in allowlist: {extra}")
    if missing:
        log(f"Step0 REVIEW: allowlist entries not found as documented commands: {missing}")
    return cand


def _baseline_package_dirs() -> list[Path]:
    exact = {
        "telegram_helpers",
        "office_drafter_helpers",
        "office_pptx_helpers",
        "pptx_helpers",
        "word_helpers",
        "harness_helpers",
    }
    return [
        d for d in ROOT.iterdir()
        if d.is_dir()
        and (d / "__init__.py").exists()
        and d.name not in {"tests", "venv", ".venv"}
        and (d.name.startswith("maya_") or d.name in exact)
    ]


def gen_grandfather_baseline(*, force: bool = False) -> list[str]:
    """Capture every CURRENT package file >300 logical lines (package-aware code_health)."""
    if GRANDFATHER_FILE.exists() and not force:
        existing = [
            line.strip()
            for line in GRANDFATHER_FILE.read_text(errors="ignore").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        log(f"Step0: reusing {len(existing)} grandfathered package violations -> {GRANDFATHER_FILE}")
        return existing
    import code_health
    excl = FIXTURE_EXCLUDE
    over = []
    for d in _baseline_package_dirs():
        for f in d.rglob("*.py"):
            nm = f.name
            if "__pycache__" in f.parts or nm.startswith("live_") or any(s in nm for s in excl):
                continue
            try:
                if code_health._count_file(f).lines > 300:
                    over.append(str(f.relative_to(ROOT)))
            except Exception:
                continue
    over = sorted(over)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    GRANDFATHER_FILE.write_text("\n".join(over) + "\n")
    log(f"Step0: {len(over)} grandfathered package violations -> {GRANDFATHER_FILE}")
    for v in over:
        log(f"   grandfather: {v}")
    return over


# --- mechanics -------------------------------------------------------------
def ensure_pkg(pkg: str) -> None:
    p = ROOT / pkg
    p.mkdir(parents=True, exist_ok=True)
    if not pkg.startswith("tests"):
        (p / "__init__.py").touch(exist_ok=True)


def write_shim(stem: str, pkg: str) -> None:
    Path(f"{stem}.py").write_text(
        f"{SHIM_MARK} — re-exports the relocated module (removed/converted in Wave 5).\n"
        f"from {pkg} import {stem} as _m\nimport sys as _sys\n_sys.modules[__name__] = _m\n")


def write_cli_wrapper(stem: str, pkg: str, *, also_importable: bool) -> None:
    """Real CLI wrapper: runs the package module as __main__. Optionally importable."""
    body = [f"{WRAPPER_MARK} — runs {pkg}.{stem} as a CLI; safe to delete only if the",
            "# command is migrated to `python -m`. NOT a compatibility shim.",
            "from __future__ import annotations", "import runpy", f'_TARGET = "{pkg}.{stem}"']
    if also_importable:
        body += ["import importlib", "import sys"]
    body += ['if __name__ == "__main__":',
             '    runpy.run_module(_TARGET, run_name="__main__")']
    if also_importable:
        body += ["else:", "    _module = importlib.import_module(_TARGET)", "    sys.modules[__name__] = _module"]
    Path(f"{stem}.py").write_text("\n".join(body) + "\n")


def update_ci_refs(stem: str, dest_dir: str) -> None:
    for path in all_py_files():
        if path.parts[0] in {"tests", "venv", ".venv"}:
            continue
        t = path.read_text(errors="ignore")
        n = t.replace(f'"{stem}.py"', f'"{dest_dir}/{stem}.py"').replace(f"'{stem}.py'", f"'{dest_dir}/{stem}.py'")
        if n != t:
            path.write_text(n)


def existing_target_wrapper(stem: str, dest: str) -> bool:
    """True when root `stem.py` is already a wrapper for `dest/stem.py`."""
    source = ROOT / f"{stem}.py"
    target = ROOT / dest / f"{stem}.py"
    if not source.exists() or not target.exists():
        return False
    text = source.read_text(errors="ignore")
    module_path = f"{dest.replace('/', '.')}.{stem}"
    return module_path in text or f"{dest}/{stem}.py" in text


def add_test_root_bootstrap(path: Path) -> None:
    """Make moved test scripts runnable as `python tests/.../name.py`."""
    text = path.read_text(errors="ignore")
    lines = text.splitlines()
    if "W4_TEST_ROOT_BOOTSTRAP" in text:
        cleaned: list[str] = []
        index = 0
        while index < len(lines):
            if lines[index].strip() == "# W4_TEST_ROOT_BOOTSTRAP":
                index += 1
                while index < len(lines):
                    current = lines[index].strip()
                    index += 1
                    if current == "del _w4_Path, _w4_root, _w4_sys":
                        if index < len(lines) and not lines[index].strip():
                            index += 1
                        break
                continue
            cleaned.append(lines[index])
            index += 1
        lines = cleaned
        text = "\n".join(lines) + "\n"
    insert_at = 0
    try:
        tree = ast.parse(text)
        if (
            tree.body
            and isinstance(tree.body[0], ast.Expr)
            and isinstance(getattr(tree.body[0], "value", None), ast.Constant)
            and isinstance(tree.body[0].value.value, str)
        ):
            insert_at = getattr(tree.body[0], "end_lineno", 0)
    except SyntaxError:
        insert_at = 0
    for index, line in enumerate(lines[:80]):
        if line.startswith("from __future__ import "):
            insert_at = max(insert_at, index + 1)
    bootstrap = [
        "# W4_TEST_ROOT_BOOTSTRAP",
        "import sys as _w4_sys",
        "from pathlib import Path as _w4_Path",
        "_w4_root = _w4_Path(__file__).resolve().parents[2]",
        "if str(_w4_root) not in _w4_sys.path:",
        "    _w4_sys.path.insert(0, str(_w4_root))",
        "del _w4_Path, _w4_root, _w4_sys",
        "",
    ]
    lines[insert_at:insert_at] = bootstrap
    path.write_text("\n".join(lines) + "\n")


def shim_target(stem: str) -> str | None:
    m = re.search(r"from\s+([\w.]+)\s+import\s+" + re.escape(stem) + r"\s+as\s+_m",
                  (ROOT / f"{stem}.py").read_text(errors="ignore"))
    return m.group(1) if m else None


def rewrite_imports(stem: str, pkg: str) -> int:
    changed = 0
    new_path = f"{pkg}.{stem}"
    pat_from = re.compile(rf"^(\s*from\s+){re.escape(stem)}(\s+import\s)", re.M)
    pat_imp = re.compile(rf"^(\s*import\s+){re.escape(stem)}(\s+as\s+\w+)?(\s*(#.*)?)$", re.M)
    for f in all_py_files():
        if f.name == f"{stem}.py" or f.parts[-2:] == (pkg, f"{stem}.py"):
            continue
        text = f.read_text(errors="ignore")
        if stem not in text:
            continue
        new = pat_from.sub(rf"\1{new_path}\2", text)
        new = pat_imp.sub(lambda m: f"{m.group(1)}{new_path}{m.group(2) or f' as {stem}'}{m.group(3) or ''}", new)
        if new != text:
            f.write_text(new)
            changed += 1
    return changed


# --- gates -----------------------------------------------------------------
def fast_gate(moved: list[str], *, import_old_names: bool = True) -> tuple[bool, str]:
    excluded = {".git", ".venv", "venv", "__pycache__", ".claude", "backups"}
    files = [
        str(path.relative_to(ROOT))
        for path in all_py_files()
        if not any(part in excluded for part in path.parts)
    ]
    r = sh(sys.executable, "-m", "py_compile", *files, check=False)
    if r.returncode != 0:
        return False, "compileall failed:\n" + r.stdout + r.stderr
    if import_old_names:
        for stem in moved:
            c = sh(sys.executable, "-c", f"import {stem}", check=False)
            if c.returncode != 0:
                return False, f"import {stem} failed:\n" + c.stderr
    h = sh(sys.executable, "-c",
           "from code_health import collect_code_health as c;import sys;sys.exit(0 if c('.').ok else 1)",
           check=False)
    if h.returncode != 0:
        return False, "code_health regressed:\n" + h.stdout + h.stderr
    return True, "fast gate ok"


def full_gate() -> tuple[bool, str]:
    r = sh(*GATE_CMD_FULL, check=False)
    return r.returncode == 0, (r.stdout + r.stderr)[-4000:]


# --- batches ---------------------------------------------------------------
def plan_batches(wave: int, bs: int = 15) -> list[dict]:
    names = set(root_modules())
    importers = build_importers(root_modules())

    def chunks(items, size, **extra):
        items = sorted(items)
        for i in range(0, len(items), size):
            yield {"wave": wave, **extra, "items": items[i:i + size]}

    out = []
    if wave == 1:
        runtime_imported = {
            dep
            for dep, mods in importers.items()
            if any(not is_smoke(mod) for mod in mods)
        }
        files = [
            s for s in names
            if is_smoke(s) and s not in KEEP_AT_ROOT and s not in runtime_imported
        ]
        out += [{**b, "kind": "move", "wrap": "none",
                 "moves": [(s, smoke_dest(s)) for s in b["items"]]} for b in chunks(files, bs)]
    elif wave == 2:
        imp_ns = {d for d, ms in importers.items() if any(not is_smoke(m) for m in ms)}
        leaves = [s for s in names if not is_smoke(s) and s not in KEEP_AT_ROOT and not is_cli_wrapper(s)
                  and s not in HUBS and s not in imp_ns]
        out += [{**b, "kind": "move", "wrap": "shim",
                 "moves": [(s, dest_pkg(s)) for s in b["items"]]} for b in chunks(leaves, bs)]
    elif wave == 3:
        mov = [s for s in names if not is_smoke(s) and s not in KEEP_AT_ROOT and not is_cli_wrapper(s)
               and s not in HUBS and not is_shim(s)]
        out += [{**b, "kind": "move", "wrap": "shim",
                 "moves": [(s, dest_pkg(s)) for s in b["items"]]} for b in chunks(mov, bs)]
    elif wave == 4:
        mov = [s for s in names if not is_smoke(s) and s not in KEEP_AT_ROOT and not is_cli_wrapper(s) and not is_shim(s)]
        out += [{**b, "kind": "move", "wrap": "shim", "full_gate_each": True,
                 "moves": [(s, dest_pkg(s)) for s in b["items"]]} for b in chunks(mov, max(3, min(6, bs)))]
    elif wave == 5:
        shims = [s for s in names if is_shim(s)]
        out += [{**b, "kind": "deshim", "full_gate_each": True} for b in chunks(shims, 10)]
    elif wave == 6:
        out += [{"wave": 6, "kind": "app_verify", "items": ["kampung_ai_app"]}]
    return out


def _gate_and_commit(b, moved, message, auto_rollback, label) -> bool:
    use_full = b.get("full_gate_each")
    import_old_names = b.get("wrap") != "none"
    ok, detail = full_gate() if use_full else fast_gate(moved, import_old_names=import_old_names)
    if not ok:
        log(f"  {'FULL' if use_full else 'FAST'} GATE RED: {detail[:1200]}")
        if auto_rollback:
            hard_rollback(); log(f"ROLLBACK: {label} gate-red")
        return False
    try:
        sha = commit(message)
    except RuntimeError as e:
        log(f"  COMMIT FAILED — HALT: {e}")
        if auto_rollback:
            hard_rollback()
        return False
    log(f"  COMMIT {sha} ok ({len(moved)} items, {'full' if use_full else 'fast'} gate)")
    return True


def run_move_batch(b, *, dry, auto_rollback) -> bool:
    moved, label = [], f"w{b['wave']} move [{', '.join(s for s,_ in b['moves'])}]"
    log(f"BATCH START {label}")
    if dry:
        for s, d in b["moves"]:
            log(f"  would move {s}.py -> {d}/" + ("  (+shim)" if b['wrap'] == 'shim' else ""))
        return True
    try:
        for stem, dest in b["moves"]:
            ensure_pkg(dest)
            if existing_target_wrapper(stem, dest):
                sh("git", "rm", "-q", f"{stem}.py")
                update_ci_refs(stem, dest)
                add_test_root_bootstrap(ROOT / dest / f"{stem}.py")
                moved.append(stem)
                continue
            sh("git", "mv", f"{stem}.py", f"{dest}/{stem}.py")
            if b["wrap"] == "none":
                add_test_root_bootstrap(ROOT / dest / f"{stem}.py")
            if b["wrap"] == "shim":
                if stem in WRAPPER_ALLOWLIST:
                    write_cli_wrapper(stem, dest.replace("/", "."), also_importable=True)
                else:
                    write_shim(stem, dest.replace("/", "."))
            else:
                update_ci_refs(stem, dest)
            moved.append(stem)
    except subprocess.CalledProcessError as e:
        log(f"  MOVE ERROR: {e.stderr.strip()}")
        if auto_rollback:
            hard_rollback()
        return False
    return _gate_and_commit(b, moved, f"w4: move {len(moved)} -> {b['moves'][0][1].split('/')[0]}",
                            auto_rollback, label)


def run_deshim_batch(b, *, dry, auto_rollback) -> bool:
    label = f"w5 deshim [{', '.join(b['items'])}]"
    log(f"BATCH START {label}")
    touched = []
    if dry:
        for s in b["items"]:
            kind = "CLI-wrapper" if s in WRAPPER_ALLOWLIST else "delete"
            log(f"  would rewrite imports of {s} -> {shim_target(s)}.{s}; then {kind}")
        return True
    try:
        for stem in b["items"]:
            pkg = shim_target(stem)
            if not pkg:
                log(f"  SKIP {stem}: not a recognizable shim")
                continue
            n = rewrite_imports(stem, pkg)
            if stem in WRAPPER_ALLOWLIST:
                write_cli_wrapper(stem, pkg, also_importable=True)
                log(f"  rewrote {n} files for {stem}; root file -> CLI wrapper")
            else:
                sh("git", "rm", "-q", f"{stem}.py", check=False)
                log(f"  rewrote {n} files for {stem}; removed shim")
            touched.append(stem)
    except subprocess.CalledProcessError as e:
        log(f"  DESHIM ERROR: {e.stderr.strip()}")
        if auto_rollback:
            hard_rollback()
        return False
    return _gate_and_commit(b, touched, f"w4: de-shim {len(touched)} modules", auto_rollback, label)


def run_app_verify(b, *, dry, auto_rollback) -> bool:
    log("BATCH START w6 app-bundle verification")
    if dry:
        log("  would: import kampung_ai_app, dynamic-import review, optional .app build")
        return True
    c = sh(sys.executable, "-c", "import kampung_ai_app", check=False)
    if c.returncode != 0:
        log("  ALERT app_verify: kampung_ai_app import FAILED — hand-fix dynamic imports.\n" + c.stderr[-1500:])
        return False
    dyn = sh("grep", "-nE", r"(import_module|__import__|run_path|run_module)\(", "kampung_ai_app.py", check=False)
    if dyn.stdout.strip():
        log("  REVIEW dynamic imports in kampung_ai_app.py:\n" + dyn.stdout)
    if os.getenv("W4_BUILD_APP") == "1":
        log("  building .app via build_kampung_ai_app.py ...")
        bld = sh(sys.executable, "build_kampung_ai_app.py", check=False)
        if bld.returncode != 0:
            log("  ALERT app_verify: .app build FAILED.\n" + (bld.stdout + bld.stderr)[-2000:])
            return False
    log("  app_verify PASS")
    return True


def ratchet_limit() -> None:
    count = len(list(ROOT.glob("*.py")))
    ch = ROOT / "code_health.py"
    t = ch.read_text()
    n = re.sub(r"ROOT_PY_FILE_LIMIT\s*=\s*\d+", f"ROOT_PY_FILE_LIMIT = {count}", t)
    if n != t:
        ch.write_text(n)
        try:
            log(f"RATCHET ROOT_PY_FILE_LIMIT={count} commit {commit(f'w4: ratchet ROOT_PY_FILE_LIMIT -> {count}')}")
        except RuntimeError as e:
            log(f"  ratchet commit failed: {e}")


# --- preflight + main ------------------------------------------------------
def preflight() -> bool:
    if not tree_clean():
        log("ABORT: tree dirty. COMMIT a checkpoint (do NOT stash) or discard, then retry.")
        return False
    if current_branch() != BRANCH:
        log(f"ABORT: not on {BRANCH} (on {current_branch()}). `git checkout -b {BRANCH}`.")
        return False
    log("preflight: generating Step-0 baselines ...")
    gen_wrapper_candidates()
    gen_grandfather_baseline()
    log("preflight: baseline full gate ...")
    ok, detail = full_gate()
    if not ok:
        log("ABORT: baseline gate RED.\n" + detail[-1500:])
        return False
    log("preflight OK.")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--waves", default="1,2,3,4,5,6")
    ap.add_argument("--gate", choices=["fast-only", "full-per-wave"], default="full-per-wave")
    ap.add_argument("--auto-rollback", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--plan-only", action="store_true")
    ap.add_argument("--step0", action="store_true", help="generate Step-0 baselines and exit")
    ap.add_argument("--batch-size", type=int, default=15)
    a = ap.parse_args()

    if a.step0:
        gen_wrapper_candidates(); gen_grandfather_baseline(force=True); return 0
    if a.plan_only:
        for w in [int(x) for x in a.waves.split(",") if x.strip().isdigit()]:
            bs = plan_batches(w, a.batch_size)
            print(f"Wave {w}: {len(bs)} batches, "
                  f"{sum(len(b.get('moves', b.get('items', []))) for b in bs)} files "
                  f"(reflects CURRENT tree state, not post-move waves)")
        return 0
    if not a.dry_run and not preflight():
        return 2

    for w in [int(x) for x in a.waves.split(",") if x.strip().isdigit()]:
        batches = plan_batches(w, a.batch_size)
        log(f"=== WAVE {w}: {len(batches)} batches ===")
        for b in batches:
            runner = {"deshim": run_deshim_batch, "app_verify": run_app_verify}.get(b["kind"], run_move_batch)
            if not runner(b, dry=a.dry_run, auto_rollback=a.auto_rollback):
                log(f"HALT in wave {w}. Repo at last green commit.")
                return 1
        if not a.dry_run and w != 6:
            if a.gate == "full-per-wave":
                ok, detail = full_gate()
                if not ok:
                    log(f"WAVE {w} FULL GATE RED — halting.\n" + detail[-1500:])
                    if a.auto_rollback:
                        hard_rollback()
                    return 1
                log(f"WAVE {w} FULL GATE GREEN")
            ratchet_limit()

    log("ALL WAVES GREEN — restructure complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
