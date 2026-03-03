from pathlib import Path

from jixia.structs_debug import Declaration, InfoTree, Symbol



declarations = Declaration.from_json_file(
    Path(__file__).parent / "Example.decl.json"
)
symbols = Symbol.from_json_file(Path(__file__).parent / "Example.sym.json")
infotree = InfoTree.from_json_file(Path(__file__).parent / "Example.elab.json")
print(declarations)
print(symbols)
print(infotree)
