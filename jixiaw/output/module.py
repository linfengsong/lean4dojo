
import json
import os
from pathlib import Path
from jixia import LeanProject

#from .util import collect_match_modules

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

def collect_match_modules(project, search):
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
        module_names.append(module_name)
    return module_names

def process_module(project, module_name, output_dir):
    module = project.load_module_info(module_name)
    if module is None:
        return
    module_str = ".".join(module_name)
    docstring = module.docstring
    content = project.path_of_module(module, project.root_dir).read_bytes()
    with open(os.path.join(output_dir, module_str + ".txt"), 'w', encoding='utf-8') as fd:
        fd.write(docstring)

    with open(os.path.join(output_dir, module_str + ".lean"), 'w', encoding='utf-8') as fd:
        fd.write(content.decode('utf-8'))

def process_searches(working_dir: str, search_list: list[str]):
    output_dir = working_dir + "/.jixiaw_test"
    os.makedirs(output_dir, exist_ok=True)
    project = LeanProject(working_dir)
    modules = []
    for search in search_list:
        modules.extend(collect_match_modules(project, search))

    for module_name in modules:
        process_module(project, module_name, output_dir)

if __name__ == "__main__":
    search_list = [
        #"Init",
        #"Mathlib",
        "LeanTest",
    ]

    process_searches("/home/linfe/math/lean_test", search_list)