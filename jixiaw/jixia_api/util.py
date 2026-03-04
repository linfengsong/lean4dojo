import os
from pathlib import Path

def getLeanSourceDirOrFile(project, module_name: list[str], forceLeanFile: bool = False):
    if module_name[0].startswith("Mathlib"):
        root_path = str(project.root) + "/.lake/packages/mathlib"
    elif module_name[0].startswith("Cache"):
        root_path = str(project.root) + "/.lake/packages/mathlib"
    elif module_name[0].startswith("Init"):
        root_path = "/home/linfe/.elan/toolchains/leanprover--lean4---v4.24.0/src/lean"
    else:
        root_path = str(project.root)
    path = root_path + "/" + "/".join(module_name).replace(".", "/")
    if not forceLeanFile and os.path.exists(path):
        return path
    path = path + ".lean"
    if os.path.exists(path):
        return path
    return None

def collect_match_modules(project, search, exclude_list):
    module_names = []
    search_module_name = search.split(".")
    lean_file = getLeanSourceDirOrFile(project, search_module_name, True)
    if lean_file is not None:
        module_names.append(search_module_name)

    lean_Dir = getLeanSourceDirOrFile(project, search_module_name)
    if lean_Dir is None:
        return module_names
    rootDir = lean_Dir[:-len(search)]
    searchPath = Path(lean_Dir)
    rootPath = Path(rootDir)
    for lean_path in searchPath.rglob("*.lean"):
        relative_path = lean_path.relative_to(rootPath)
        module_name = relative_path.with_suffix("").as_posix().split("/")
        module_id = ".".join(module_name)
        if module_id in exclude_list:
            continue
        module_names.append(module_name)
    return module_names
