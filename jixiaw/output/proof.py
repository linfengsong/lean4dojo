import json
import os
import re
import copy
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Self
from jixia import LeanProject
from jixia.structs import Declaration, DeclarationRoot, StringRange, InfoTree, InfoTreeRoot,LineModel, LineModelRoot, RootModel,Plugin

@dataclass(frozen=True, order=True)
class FilePos:
    line: int
    column: int

@dataclass(frozen=True, order=True)
class FileRange:
    start: FilePos
    stop: FilePos

    @classmethod
    def fromStringRange(cls, lines: list[LineModel], stringRange: StringRange):
        start = FilePos(1, 1)
        stop = FilePos(len(lines) + 1, 1)
        if stringRange is not None:
            if stringRange.start is not None:
                start = cls.createFilePos(lines, int(stringRange.start))
            if stringRange.stop is not None:
                stop  = cls.createFilePos(lines, int(stringRange.stop))
        return FileRange(start, stop)
    
    @classmethod
    def createFilePos(cls, lines: list[LineModel], charPos: int):
        start = 0
        lineNum = 1
        for index, line in enumerate(lines):
            if line.start > charPos:
                break
            start = line.start
            lineNum = index + 1
        column = charPos - start + 1
        return FilePos(lineNum, column)
    
    def inRange(self, fileRange):
        return self.start <= fileRange.start and fileRange.stop <= self.stop
    
@dataclass(frozen=True, eq=False)
class Term:
    fileRange: FileRange
    ident: str
    type: str  


@dataclass(frozen=True, eq=False)
class TacticBase:
    fileRange: FileRange
    pp: str   
    before: list[str]
    after: list[str]

@dataclass(frozen=True, eq=False)
class Tactic(TacticBase):
    pass

@dataclass(frozen=True, eq=False)
class RootTactic(TacticBase):
    fileRange: FileRange
    pp: str   
    before: list[str]
    after: list[str]
    children: list[Tactic]

    def __str__(self):
        children_len = None
        if self.children is not None:
            children_len = len(self.children)
        return f"tactic={self.fileRange}, {self.pp}, children={children_len}"

@dataclass(frozen=True, eq=False)
class Theorem:
    fileRange: FileRange
    name: str
    
    signature: str
    signatureFileRange: FileRange

    proofOperator: str

    proof: str
    proofFileRange: FileRange
    
    proofTactic: RootTactic
    tactics: list[RootTactic]

    tactic_before: list
    tactic_after: list

    def __str__(self):
        return f"range={self.fileRange}, name={self.name}, type={self.type}, tactics: {len(self.tactics)}"

def createTactic(ref, tactic, lines, skipMultiples = False, previousFileRange = None):
    s: str = ref.pp
    if skipMultiples and ("\n" in ref.pp or ";" in ref.pp):
        return None
    currentFileRange = FileRange.fromStringRange(lines, ref.range)
    if previousFileRange is not None:
        if previousFileRange.inRange(currentFileRange):
            return None
    if ref.pp == "by":
        return None
    beforeGoals = []
    for goal in tactic.before:
        beforeGoals.append(goal.pp)
    afterGoals = []
    for goal in tactic.after:
        afterGoals.append(goal.pp)
    return Tactic(currentFileRange, ref.pp, beforeGoals, afterGoals)


def collect_sub_tactics(nodes: list, lines, previousFileRange = None):
    sub_tactics = []
    for node in nodes:
        if node.info and node.info.tactic:
            tacticInfo = node.info.tactic
            tactic = createTactic(node.ref, tacticInfo, lines, True, previousFileRange)
            if tactic is not None:
                sub_tactics.append(tactic)
                previousFileRange = tactic.fileRange
        # 2. 不論當前節點有沒有，都繼續往 children 找
        if node.children:
            sub_tactics.extend(collect_sub_tactics(node.children, lines, previousFileRange))
            
    return sub_tactics

def print_inforTree(fileRange: FileRange, lines: list, infoTrees: list, maxLevel: int = 8, level: int = 0):
    for infoTree in infoTrees:
        infoTreeFileRange = FileRange.fromStringRange(lines, infoTree.ref.range)
        if fileRange.inRange(infoTreeFileRange):
            print(f"ooo infoTree: {level} {infoTree.ref} {len(infoTree.children)} {infoTree.info}")
            if level < maxLevel and infoTree.info.simple:
                print_inforTree(infoTreeFileRange, lines, infoTree.children, maxLevel, level + 1)
    
def collect_all_macros(nodes: list, lines: list, module_name):
    macros = []
    #kind = ['Lean', 'Parser', 'Term', 'app']
    for node in nodes:
        if node.info and node.info.macro and node.info.macro.expanded and node.info.macro.expanded.range: #and node.info.macro.expanded.kind == kind:
            fileRange = FileRange.fromStringRange(lines, node.info.macro.expanded.range)
            macro = {
                "fileRange": fileRange,
                "macro": node.info.macro
            }
            macros.append(macro)
        if node.children:
            macros.extend(collect_all_macros(node.children, lines, module_name))
    return macros

def find_macros(fileRange: FileRange, macros: list):
    ms = []
    for macro in macros:
        if fileRange.inRange(macro["fileRange"]):
            ms.append(macro)
    return ms

def print_macro(fileRange: FileRange, macros: list):
    for macro in macros:
        if fileRange.inRange(macro["fileRange"]):
            print(f"macro: {macro}")



def collect_all_terms(nodes: list, lines: list, module_name):
    terms = []
    for node in nodes:
        if node.info and node.info.term and node.ref.kind == ["ident"] and node.info.term.expected_type is None:
            fileRange = FileRange.fromStringRange(lines, node.ref.range)
            term = Term(fileRange, node.info.term.value, node.info.term.type)
            terms.append(term)
        elif node.children:
            terms.extend(collect_all_terms(node.children, lines, module_name))
    return terms

def find_term(fileRange: FileRange, ident: str, terms: list[Term]):
    for term in terms:
        if fileRange.inRange(term.fileRange) and term.ident == ident:
            return term
    return None

def print_term(fileRange: FileRange, terms: list[Term]):
    for term in terms:
        if fileRange.inRange(term.fileRange):
            print(f"{fileRange} term: {term}")

def find_all_terms(nodes: list, pp: str):
    founds = []
    for node in nodes:
        #if node.ref and node.ref.pp == pp:
        if node.ref and pp in node.ref.pp:
            #print(f"xxxx   {node.ref.pp}")
            item = {
                "node": node, 
                "children": []
            }
            founds.append(item)
        if node.children:
            sub_founds = find_all_terms(node.children, pp)
            if len(sub_founds) > 0:
                item = {
                    "node": node, 
                    "children": sub_founds
                }
                #print(len(sub_founds))
                founds.append(item)
    return founds

def print_terms(terms: list, level = 1):
    for term in terms:
        node = term['node']
        children = term['children']
        print(f"{level} {node.info} {node.ref}")
        #print(f"{level} {term}")
        print_terms(children, level + 1)

def getLeanSourceFile(project, module_name: list[str]):
    if module_name[0].startswith("Mathlib"):
        root_path = str(project.root) + "/.lake/packages/mathlib"
    elif module_name[0].startswith("Init"):
        root_path = "/home/linfe/.elan/toolchains/leanprover--lean4---v4.24.0/src/lean"
    else:
        root_path = str(project.root)
    return root_path + "/" + "/".join(module_name).replace(".", "/") + ".lean"

def extractLine(line: str, start: int, stop: int = -1):
    buf = bytes(line, encoding='utf-8')
    if stop == -1:
        stop = len(buf)
    buf = buf[start : stop]
    return buf.decode('utf-8') 

def getLeanSourceCode(project, module_name: list[str], fileRange: FileRange):
    file_path = getLeanSourceFile(project, module_name)
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        target_lines = lines[fileRange.start.line - 1 : fileRange.stop.line]
        if not target_lines:
            return ""
        if len(target_lines) == 1:
            return extractLine(target_lines[0], fileRange.start.column -1, fileRange.stop.column)
        else:
            target_lines[0] = extractLine(target_lines[0], fileRange.start.column - 1)
            target_lines[-1] = extractLine(target_lines[-1], 0, fileRange.stop.column)
            return "".join(target_lines)

def simplify_tree(data: Any):
    if not isinstance(data, dict):
        return data

    # 先遞迴處理所有的子節點
    if "children" in data and isinstance(data["children"], list):
        data["children"] = [simplify_tree(c) for c in data["children"]]
        
        # 壓縮邏輯：如果只有一個小孩，且小孩的內容是我們想要的
        # 範例：如果 children[0] 也有 children，直接跳過中間這層
        while len(data["children"]) == 1:
            child = data["children"][0]
            if isinstance(child, dict) and "children" in child:
                # 將孫子提拔為兒子
                data["children"] = child["children"]
                # 可選擇性合併 pp 或 range 資訊
                data["pp"] = data.get("pp") or child.get("pp")
            else:
                break
                
    return data

def collect_all_tactics(nodes: list, lines: list):
    """
    遞迴遍歷整個 InfoTree 列表，將所有隱藏在深處的 tactic 抽出來。
    """
    tactics = []
    for node in nodes:
        if node.info and node.info.tactic:
            tactic = createTactic(node.ref, node.info.tactic, lines)
            sub_tactics = collect_sub_tactics(node.children, lines)
            #if "f', hf'⟩ := f.exists_leftInverse_of_injective (ker_eq_bot.mpr hf)" in tactic.pp:
            #    print(f"   xxxxx {tactic.pp}")
            rootTactic = RootTactic(tactic.fileRange, tactic.pp, tactic.before, tactic.after, sub_tactics)
            tactics.append(rootTactic)
            return tactics
        if node.children:
            tactics.extend(collect_all_tactics(node.children, lines))
    return sorted(tactics, key=lambda x: x.fileRange, reverse=False)

def find_root_tactrics(fileRange: FileRange, rootTactics: list[RootTactic]):
    tactics = []
    for rootTactic in rootTactics:
        if fileRange.inRange(rootTactic.fileRange):
            tactics.append(rootTactic)
    return tactics

def getToken(line: str, index: int):
    tokens = line.strip().replace("\n", " ").replace("\r", " ").replace("\t", " ").split()
    if index < 0:
        index = len(tokens) + index
    if index >= len(tokens):
        return None
    return tokens[index]

# =============================
# Extract Theorems
# =============================
def extract_theorem_signature_proof(project, module_name, lines, signature_start, theorem_stop):
    # does not allow define Theorem in Theorem's signature. It is kind of save to find by ":=""
    fileRange = FileRange.fromStringRange(lines, StringRange(signature_start, theorem_stop))
    text = getLeanSourceCode(project, module_name, fileRange)
    text = text.replace("\t", " ").replace("\n", " ").replace("\r", " ")
    buf = bytes(text, encoding='utf-8')
    match = re.search(bytes(" := ", encoding='utf-8'), buf)
    if match is None:
        return None, None
    match_start = signature_start + match.start()
    signature_range = StringRange(signature_start, match_start)
    proof_range = StringRange(match_start + 1, theorem_stop)
    signature_fileRange = FileRange.fromStringRange(lines, signature_range)
    proof_fileRange = FileRange.fromStringRange(lines, proof_range)
    return signature_fileRange, proof_fileRange

def extract_theorems(project, module_name):
    if not project.has_info(module_name, DeclarationRoot) or not project.has_info(module_name, InfoTreeRoot):
        return []
    declarations = project.load_info(module_name, DeclarationRoot) #\Declaration)
    infoTrees = project.load_info(module_name, InfoTreeRoot)
    if project.has_info(module_name, LineModelRoot):
        lines = project.load_info(module_name, LineModelRoot)
    else:
        lines = []
    rootTactics = collect_all_tactics(infoTrees, lines)
    macros = collect_all_macros(infoTrees, lines, module_name)
    terms = collect_all_terms(infoTrees, lines, module_name)
    #search_pp ="have ⟨f', hf'⟩ := f.exists_leftInverse_of_injective (ker_eq_bot.mpr hf)\n  ⟨φ.comp f', ext fun x ↦ congr(φ <| $hf"
    #search_pp = "⟨φ.comp f', ext fun x ↦ congr(φ <| $hf"
    #search_pp = "Function.Surjective f.dualMap := fun φ "
    #search_result = find_all_terms(infoTrees, search_pp)
    #print_terms(search_result)
    #with open("search_result.json", "w") as json_file:
    #    json.dump(search_result, json_file, indent=2)
    theorems = []
    for _, decl in enumerate(declarations):
        if decl.kind == "theorem":
            #### need handle theorem is private
            if len(decl.name) == 0 or decl.name[0] == '_private':
                continue;
            theorem = extract_theorem(project, module_name, decl, lines, rootTactics, macros, terms, infoTrees)
            if theorem is not None:
                theorems.append(theorem)
    return theorems

def extract_theorem(project, module_name, decl, lines, rootTactics, macros, terms, infoTrees):
    theorem_name = ".".join(decl.name)
    theorem_range = FileRange.fromStringRange(lines, decl.ref.range)
    tactics = find_root_tactrics(theorem_range, rootTactics)

    signature = decl.signature.pp
    signatureRange = FileRange.fromStringRange(lines, decl.signature.range)
            
    statement = decl.value.pp
    theorem_proofRange = FileRange.fromStringRange(lines, decl.value.range)

    if statement is None:
        statement = getLeanSourceCode(project, module_name, theorem_proofRange)

    proofOperator = getToken(statement, 0)

    if proofOperator != ":=" and proofOperator != "|":
        #print(f"module_name: {module_name}, theorem_name: {theorem_name}, proofOperator: {proofOperator} {theorem_range}")
        #print(f"proofOperator: {proofOperator}")
        #print(f"xxxx signatureRange: {signatureRange}, {decl.signature.pp}")
        #print(f"xxxx theorem_proofRange: {theorem_proofRange}, {decl.value.pp}")
        #print_inforTree(theorem_range, lines, infoTrees)
        #print_macro(theorem_range, macros)
        #print_term(theorem_range, terms)
        # Get proof from tactic:
        sigRange, proofRange = extract_theorem_signature_proof(project, module_name, lines, decl.signature.range.start, decl.ref.range.stop)
        if sigRange is not None and proofRange is not None:
            signatureRange = sigRange
            signature = getLeanSourceCode(project, module_name, signatureRange)
            theorem_proofRange = proofRange
            statement = getLeanSourceCode(project, module_name, theorem_proofRange)
            proofOperator = getToken(statement, 0)
        # else:
        #    fileRange = FileRange.fromStringRange(lines, StringRange(decl.signature.range.start, decl.ref.range.stop))
        #    print(f"xxxxx fail to find := in proof at: {module_name}, {theorem_name}, {fileRange}")
        #print(f"yyyy theorem_proofRange: {proofOperator} {theorem_proofRange}, {statement}")
        #print(f"yyyy theorem_proofRange: {proofOperator} {signatureRange}, {signature}")

    #else:
    #    print(f"module_name: {module_name}, theorem_name: {theorem_name}, proofOperator: {proofOperator}")
    #    print(f"yyyy signatureRange: {signatureRange}, {decl.signature.pp}")
    #    print(f"yyyy theorem_proofRange: {theorem_proofRange}, {decl.value.pp}")

    if statement is None:
        print(f"xxxxx no proof, remove: {theorem_name} {module_name}")
        return None
    if proofOperator is None:
        print(f"xxxxx no proofOperator, remove: {theorem_name} {module_name}")
        return None
    
    statement = statement.rstrip()[len(proofOperator):].rstrip()
    startBy = True
    byToken = getToken(statement, 0)
    if byToken is None or byToken != "by":
        startBy = False

    theorem_proof = statement[len(proofOperator):].lstrip()
    tactic_before = None
    tactic_after = None
    proofTactic = None
    if startBy:
        if len(tactics) > 0:
            proofTactic = tactics.pop(0)
            tactic_before = proofTactic.before
            tactic_after = proofTactic.after

    if proofTactic is None:
        name_array = copy.deepcopy(decl.name)
        term = None
        while term is None and len(name_array) > 0:
            search_name = ".".join(name_array)
            term = find_term(theorem_range, search_name, terms)
            if term is None and not search_name.startswith("@"):
                search_name = "@" + search_name
                term = find_term(theorem_range, search_name, terms)
            name_array.pop(0)
        if term is None:
            search_name = "_root_." + ".".join(decl.name)
            term = find_term(theorem_range, search_name, terms)
            if term is None:
                search_name = "@" + search_name
                term = find_term(theorem_range, search_name, terms)
        if term is None:
            search_name = "«" + decl.name[len(decl.name) - 1] + "»"
            term = find_term(theorem_range, search_name, terms)
            if term is None:
                search_name = "@" + search_name
                term = find_term(theorem_range, search_name, terms)

        if term is not None:
            #print(f"decl.name: {decl.name}")
            #print_term(signatureRange, terms)
            #print(f"result term: {term}")
            tactic_before = term.type
        else:
            print(f"xxxxx tactic_before is none, remove: {theorem_name} {module_name}")
            #print_term(theorem_range, terms)
            return None

        #if term is None:
            #print_term(theorem_range, terms)
            #macros = find_macros(theorem_range, macros)
            #for macro in macros:
            #    print(f"MMMM {macro}")
                
    return Theorem(theorem_range, theorem_name, signature, signatureRange, proofOperator, theorem_proof, theorem_proofRange, proofTactic, tactics, tactic_before, tactic_after)

def get_pos_dict(pos):
    return {"line": pos.line, "column": pos.column}

def create_tacitic_data(tactic):
    state_before = "\n\n".join(tactic.before)
    tactic_str = tactic.pp
    if len(tactic.after) == 0:
        state_after = "no goals"
    else:
        state_after = "\n\n".join(tactic.after)
    tactic_start = tactic.fileRange.start
    tactic_end = tactic.fileRange.stop

    tactic_data = {
        "tactic": tactic_str,
        "tactic_before": state_before,
        "tactic_after": state_after,
        "tactic_start": get_pos_dict(tactic_start),
        "tactic_stop": get_pos_dict(tactic_end)
    }
    return tactic_data

def create_rootTacitic_data(rootTactic):
    children = []
    for tactic in rootTactic.children:
        tactic_data = create_tacitic_data(tactic)
        children.append(tactic_data)
    root_tactic_data = create_tacitic_data(rootTactic)
    root_tactic_data["tactics"] = children
    return root_tactic_data

def process_module(fd, project, module_name, operatorSet):
    theorems = extract_theorems(project,module_name)
    name = ".".join(module_name)
    for theorem in theorems:
        theorem_name = theorem.name
        theorem_signature = theorem.signature
        theorem_operator = theorem.proofOperator
        theorem_proof = theorem.proof
        theorem_proofFileRange = theorem.proofFileRange
        tactic_before = theorem.tactic_before
        tactic_after = theorem.tactic_after
        start = theorem_proofFileRange.start
        end = theorem_proofFileRange.stop

        rootTactic_list = []
        for rootTactic in theorem.tactics:
            rootTactic_data = create_rootTacitic_data(rootTactic)
            rootTactic_list.append(rootTactic_data)

        if tactic_after is None or len(tactic_after) == 0:
            tactic_after = "no goals"

        #print(f"tactic_before: {tactic_before}, tactic_after: {tactic_after}")

        data = {
            "module": name,
            "theorem": theorem_name,
            "teorem_signature:": theorem_signature,
            "theorem_operator": theorem_operator,
            "theorem_proof": theorem_proof,
            "tactic_before:": tactic_before,
            "tactic_after": tactic_after,
            "start": get_pos_dict(start),
            "stop": get_pos_dict(end)
        }

        if theorem.proofTactic is not None:
            data["tactics"] = create_rootTacitic_data(theorem.proofTactic)
        if len(rootTactic_list) > 0:
            data["ref_tactics"] = rootTactic_list

        # 寫入 JSONL
        fd.write(json.dumps(data, ensure_ascii=False) + '\n')

        if theorem_operator in operatorSet:
            count =  operatorSet[theorem_operator] + 1
        else:
            count = 1
        operatorSet[theorem_operator] = count

def process_dir(fd, project, root_dir, operatorSet, prefix: str = None):

    root_path = Path(root_dir)

    
    for lean_path in root_path.rglob("*.lean"):
        name = lean_path.relative_to(root_path).with_suffix("").as_posix().replace("/", ".")
        if not prefix is None and not name.startswith(str(prefix)):
            continue
        #try:
        module_name = name.split(",")
        process_module(fd, project, module_name, operatorSet)
        #except Exception as e:
        #    print(f"xxxxxx An error occurred to get traced file from: lean path: {lean_path}, {e}")

    

if __name__ == "__main__":
    TOOLCHAIN_ROOT = "/home/linfe/.elan/toolchains/leanprover--lean4---v4.24.0"
    WORKING_DIR = "/home/linfe/math/lean_test"
    OUTPUT_DIR = WORKING_DIR + "/.jixiaw"

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    project = LeanProject(WORKING_DIR)
    operatorSet = {":=": 0}
    with open(OUTPUT_DIR + "/ast.jsonl", 'w', encoding='utf-8') as fd:
        process_dir(fd, project, WORKING_DIR, operatorSet, "LeanTest")
        process_dir(fd, project, WORKING_DIR + "/.lake/packages/mathlib", operatorSet)#, "Mathlib.MeasureTheory.PiSystem" )
        #process_dir(fd, project, WORKING_DIR + "/.lake/packages/mathlib", operatorSet, "Mathlib.Analysis.Calculus.ContDiff.FTaylorSeries" ) ## 292 set_option maxHeartbeats 0
        #process_dir(fd, project, WORKING_DIR + "/.lake/packages/mathlib", operatorSet, "Mathlib.MeasureTheory.Measure.Support")
        #process_dir(fd, project, WORKING_DIR + "/.lake/packages/mathlib", operatorSet, "Mathlib.RingTheory.Kaehler.Polynomial")
        #process_dir(fd, project, WORKING_DIR + "/.lake/packages/mathlib", operatorSet, "Mathlib.Algebra.Category.CommAlgCat.Monoidal")
        #process_dir(fd, project, WORKING_DIR + "/.lake/packages/mathlib", operatorSet, "Mathlib.MeasureTheory.Constructions.BorelSpace.Order")
        #process_dir(fd, project, WORKING_DIR + "/.lake/packages/mathlib", operatorSet, "Mathlib.Tactic.CC.Addition")
        #process_dir(fd, project, WORKING_DIR + "/.lake/packages/mathlib", operatorSet, "Mathlib.LinearAlgebra.Dual.Lemmas")
        process_dir(fd, project, TOOLCHAIN_ROOT + "/src/lean", operatorSet, "Init")

    print(f"Theorem Operator Set: {operatorSet}")

    #module_name = ("LeanTest","Basic")
    
    #module = project.load_module_info(fd, module_name)
    #process_module(project, module_name)


