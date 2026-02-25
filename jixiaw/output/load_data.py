import os
import re
from pathlib import Path
from argparse import ArgumentParser

from jixia import LeanProject
from jixia.structs_debug import parse_name

_LEAN4_TOOLCHAINS_DIR = Path(".elan/toolchains")

_LEAN4_VERSION_REGEX = re.compile(r"leanprover/lean4:(?P<version>.+?)")

_LEAN4_SRC_LEAN_DIR = Path("src/lean")

def get_lean4_version_from_config(project_root: Path) -> str:
    with open(project_root / 'lean-toolchain', 'r') as file:
        content = file.read()
        m = _LEAN4_VERSION_REGEX.fullmatch(content.strip())
        assert m is not None, "Invalid config."
        v = m["version"]
        if not v.startswith("v") and v[0].isnumeric():
            v = "v" + v
        return v


def get_elan_toolchain_path(project_root: Path) -> Path:
    version = get_lean4_version_from_config(project_root)
    lean_version = version[1:]  #ignore "v" at beginning
    toolchain_name = f"leanprover--lean4---v{lean_version}"
    return Path.home() / _LEAN4_TOOLCHAINS_DIR / Path(toolchain_name)

def main():
    parser = ArgumentParser()
    subparser = parser.add_subparsers()
    jixia_parser = subparser.add_parser("jixia")
    jixia_parser.set_defaults(command="jixia")
    jixia_parser.add_argument("project_root", help="Project to be indexed")
    jixia_parser.add_argument(
        "prefixes",
        help="Comma-separated list of module prefixes to be included in the index; e.g., Init,Mathlib",
    )

    args = parser.parse_args()

    print(f"project_root: {args.project_root}")
    print(f"prefixes: {args.prefixes}")

    project = LeanProject(args.project_root)
    prefixes = [parse_name(p) for p in args.prefixes.split(",")]

    lean_sysroot = os.environ.get("LEAN_SYSROOT")
    if lean_sysroot is None:
        lean_sysroot = get_elan_toolchain_path(project.root)
        
    lean_src = lean_sysroot / _LEAN4_SRC_LEAN_DIR
    for d in project.root, lean_src:
        results = project.batch_run_jixia(
            base_dir=d,
            prefixes=prefixes,
            plugins=["module", "declaration", "symbol","elaboration", "ast", "line"],
        )
        print(results)

if __name__ == "__main__":
    # python load_data.py jixia /home/linfe/math/lean_test Init,Mathlib,LeanTest
    # python load_data.py jixia /home/linfe/math/lean_test Mathlib.Analysis.Calculus.ContDiff.FTaylorSeries
    main()