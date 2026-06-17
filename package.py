"""
Build distribution zips for the RJK Reporting Framework.

Usage:
    python package.py

Outputs (next to the project root, NOT inside it):
    ../rjk_dist/rjk_app.zip          — full app, ready to run
    ../rjk_dist/rjk_test_hello.zip   — single hello_world.py for scan testing

What is included (all paths relative to project root):
    Root files     app.py, launch.py, requirements.txt, .env.example, CLAUDE.md
    src/           all .py files under src/
    templates/     all files under templates/
    reports/       all .sql files, excluding anything under reports/_trash/
    data/mock/     all .json files (seed / mock data), if the directory exists
"""

import zipfile
from pathlib import Path

ROOT = Path(__file__).parent
OUT  = ROOT.parent / "rjk_dist"
OUT.mkdir(exist_ok=True)

# ── Explicit single-file includes ────────────────────────────────────────────
ROOT_FILES = [
    "app.py",
    "launch.py",
    "requirements.txt",
    ".env.example",
    "CLAUDE.md",
]

# ── Directory glob rules: (glob_pattern, exclusion_predicate) ─────────────
# Each entry yields Path objects relative to ROOT; exclude() returns True to skip.
GLOB_RULES = [
    # All Python source files
    ("src/**/*.py",         lambda p: "__pycache__" in p.parts),
    # HTML templates
    ("templates/**/*",      lambda p: p.is_dir()),
    # SQL reports — skip the _trash recycle bin
    ("reports/**/*.sql",    lambda p: "_trash" in p.parts),
    # Mock / seed data JSON
    ("data/mock/**/*.json", lambda _: False),
]


def _collect_files() -> list[Path]:
    """Return all files that should go into the app zip, as paths relative to ROOT."""
    seen: set[Path] = set()
    result: list[Path] = []

    def _add(rel: Path):
        if rel not in seen:
            seen.add(rel)
            result.append(rel)

    for name in ROOT_FILES:
        _add(Path(name))

    for pattern, exclude in GLOB_RULES:
        for abs_path in sorted(ROOT.glob(pattern)):
            rel = abs_path.relative_to(ROOT)
            if not exclude(abs_path):
                _add(rel)

    return result


def build_app_zip():
    files = _collect_files()
    path  = OUT / "rjk_app.zip"
    missing = 0
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in files:
            src = ROOT / rel
            if not src.exists():
                print(f"  WARNING: missing {rel}")
                missing += 1
                continue
            z.write(src, f"rjk/{rel.as_posix()}")
    included = len(files) - missing
    print(f"rjk_app.zip        {path.stat().st_size:>10,} bytes   ({included} files)   {path}")


def build_hello_zip():
    path = OUT / "rjk_test_hello.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("hello_world.py", 'print("Hello, World!")\n')
    print(f"rjk_test_hello.zip {path.stat().st_size:>10,} bytes   {path}")


if __name__ == "__main__":
    print(f"Building packages -> {OUT}\n")
    files = _collect_files()
    print(f"Collecting {len(files)} files:")
    for f in files:
        src = ROOT / f
        status = "OK" if src.exists() else "MISSING"
        print(f"  [{status}] {f.as_posix()}")
    print()
    build_app_zip()
    build_hello_zip()
    print("\nDone.")
