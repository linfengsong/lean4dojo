import os
from jixia import LeanProject
from jixia.structs import Symbol,Declaration,InfoTree
from .module import ModuleData,SymbolData,DeclarationData,InfoTreeData
from .util import collect_match_modules

def to_module_id(module_name):
    return ".".join(module_name)

def write_obj_to_json(module_name, obj_type, obj, output_dir):
    module_id = to_module_id(module_name)
    with open(os.path.join(output_dir, module_id + "." + obj_type + ".json"), 'w', encoding='utf-8') as fd:
        fd.write(obj.to_json())

def write_list_to_jsonl(module_name, obj_type, list, output_dir):
    module_id = to_module_id(module_name)
    with open(os.path.join(output_dir, module_id + "." + obj_type + ".json"), 'w', encoding='utf-8') as fd:
        for obj in list:
            fd.write(obj.to_json())
            fd.write("\n")

def write_lean(project, module_name, output_dir):
    module_id = to_module_id(module_name)
    content = project.path_of_module(module_name, project.root).read_bytes()
    with open(os.path.join(output_dir, module_id + ".lean"), 'w', encoding='utf-8') as fd:
        fd.write(content.decode('utf-8'))

def process_module(project, module_name, output_dir):
    module = project.load_module_info(module_name)
    if module is None:
        return
    try:
        #write_lean(project, module_name, output_dir)
        write_obj_to_json(module_name, "module", ModuleData.create(module), output_dir)

        symbols = project.load_info(module_name, Symbol)
        write_list_to_jsonl(module_name, "symbol", [SymbolData.create(symbol) for symbol in symbols], output_dir)

        decls = project.load_info(module_name, Declaration)
        write_list_to_jsonl(module_name, "decl", [DeclarationData.create(decl) for decl in decls], output_dir)

        infoTrees = project.load_info(module_name, InfoTree)
        write_list_to_jsonl(module_name, "elab", [InfoTreeData.create(infoTree) for infoTree in infoTrees], output_dir)
    except Exception as e:
        print(f"xxxx Fail to process module: {module_name}, {e}")


def process_searches(working_dir: str, search_list: list[str], exclude_list: list[str]):
    output_dir = working_dir + "/.jixiaw_test"
    os.makedirs(output_dir, exist_ok=True)
    project = LeanProject(working_dir)
    modules = []
    for search in search_list:
        modules.extend(collect_match_modules(project, search, exclude_list))

    for module_name in modules:
        process_module(project, module_name, output_dir)

if __name__ == "__main__":
    search_list = [
        #"Init",
        #"Mathlib",
        "LeanTest",
    ]
    exclude_list = [
        "Init.WF",
        "Init.Meta.Defs",
        'Mathlib.Data.Prod.Basic'
    ]

    process_searches("/home/linfe/math/lean_test", search_list, exclude_list)