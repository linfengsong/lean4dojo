import json
import os
from pathlib import Path
from dataclasses import dataclass
from jixia import LeanProject
from jixia.structs import Declaration, StringRange, InfoTree, RootModel,Plugin
from psycopg.types.range import Range

@dataclass(frozen=True, eq=False)
class LineModel(RootModel):
    _plugin_name = "line"

    start: int

@dataclass(frozen=True, order=True)
class FilePos:
    line: int
    column: int

@dataclass(frozen=True, order=True)
class Range:
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
        return Range(start, stop)
    
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
    
    def inRange(self, range: Range):
        return self.start <= range.start and range.stop <= self.stop
    
@dataclass(frozen=True, eq=False)
class Term:
    range: Range
    ident: str
    type: str  


@dataclass(frozen=True, eq=False)
class Tactic:
    range: Range
    pp: str   
    before: list[str]
    after: list[str]

@dataclass(frozen=True, eq=False)
class RootTactic:
    tactic: Tactic
    children: list[Tactic]
    def __str__(self):
        return f"tactic={self.tactic}, children={len(self.children)}"

@dataclass(frozen=True, eq=False)
class Theorem:
    range: Range
    name: str
    
    type: str
    typeRange: Range

    signature: str
    signatureRange: Range

    proof: str
    proofRange: Range
    
    tactic_before: str
    tactics: list[RootTactic]

    def __str__(self):
        return f"range={self.range}, name={self.name}, type={self.type}, tactics: {len(self.tactics)}"

def createTactic(ref, tactic, lines, skipMultiples = False, previousRange = None):
    s: str = ref.pp
    if skipMultiples and ("\n" in ref.pp or ";" in ref.pp):
        return None
    currentRange = Range.fromStringRange(lines, ref.range)
    if previousRange is not None:
        if previousRange.inRange(currentRange):
            return None
    if ref.pp == "by":
        return None
    beforeGoals = []
    for goal in tactic.before:
        beforeGoals.append(goal.pp)
    afterGoals = []
    for goal in tactic.after:
        afterGoals.append(goal.pp)
    return Tactic(currentRange, ref.pp, beforeGoals, afterGoals)

def collect_sub_tactics(nodes: list, lines, previousRange = None):
    sub_tactics = []
    for node in nodes:
        if node.info and node.info.tactic:
            tacticInfo = node.info.tactic
            tactic = createTactic(node.ref, tacticInfo, lines, True, previousRange)
            if tactic is not None:
                sub_tactics.append(tactic)
                previousRange = tactic.range
        # 2. 不論當前節點有沒有，都繼續往 children 找
        if node.children:
            sub_tactics.extend(collect_sub_tactics(node.children, lines, previousRange))
            
    return sub_tactics

def collect_all_terms(nodes: list, lines: list):
    terms = []
    for node in nodes:
        if node.info and node.info.term and node.ref.kind == ["ident"] and node.info.term.expected_type is None:
            range = Range.fromStringRange(lines, node.ref.range)
            term = Term(range, node.info.term.value, node.info.term.type)
            terms.append(term)
        elif node.children:
            terms.extend(collect_all_terms(node.children, lines))
    return terms

def find_term(range: Range, ident: str, terms: list[Term]):
    for term in terms:
        if range.inRange(term.range) and term.ident == ident:
            return term
    return None

def collect_all_tactics(nodes: list, lines: list):
    """
    遞迴遍歷整個 InfoTree 列表，將所有隱藏在深處的 tactic 抽出來。
    """
    tactics = []
    for node in nodes:
        if node.info and node.info.tactic:
            tactic = createTactic(node.ref, node.info.tactic, lines)
            sub_tactics = collect_sub_tactics(node.children, lines)
            rootTactic = RootTactic(tactic, sub_tactics)
            tactics.append(rootTactic)
            return tactics
        if node.children:
            tactics.extend(collect_all_tactics(node.children, lines))
    return sorted(tactics, key=lambda x: x.tactic.range, reverse=False)

def find_root_tactrics(range: Range, rootTactics: list[RootTactic]):
    tactics = []
    for rootTactic in rootTactics:
        if range.inRange(rootTactic.tactic.range):
            tactics.append(rootTactic)
    return tactics

# =============================
# Extract Theorems
# =============================

def extract_theorems(project, module_name):
    if not project.has_info(module_name, Declaration) or not project.has_info(module_name, InfoTree):
        return []
    declarations = project.load_info(module_name, Declaration)
    infoTrees = project.load_info(module_name, InfoTree)
    if project.has_info(module_name, LineModel):
        lines = project.load_info(module_name, LineModel)
    else:
        lines = []
    rootTactics = collect_all_tactics(infoTrees, lines)
    terms = collect_all_terms(infoTrees, lines)
    theorems = []
    for _, decl in enumerate(declarations):
        if decl.kind == "theorem":
            #### need handle theorem is private
            if decl.name[0] == '_private':
                continue;
            theorem_name = ".".join(decl.name)
            range = Range.fromStringRange(lines, decl.ref.range)
            tactics = find_root_tactrics(range, rootTactics)

            signature = decl.signature.pp
            signatureRange = Range.fromStringRange(lines, decl.signature.range)
            
            ##if decl.value.pp is not None:
            ##pp = decl.value.pp.lstrip()
            ##proof = pp[2:].lstrip()
            proof = decl.value.pp
            proofRange = Range.fromStringRange(lines, decl.value.range)

            tactic_before = None
            term = find_term(range, theorem_name, terms)
            if term is not None:
                tactic_before = term.type
                        
            theorem = Theorem(range, theorem_name, decl.type.pp, range, signature, signatureRange, proof, proofRange, tactic_before, tactics)
            theorems.append(theorem)
    return theorems

def get_pos_dict(pos):
    return {"line": pos.line, "column": pos.column}

def process_module(fd, project, module_name):
    theorems = extract_theorems(project,module_name)
    name = ".".join(module_name)
    for theorem in theorems:
        theorem_name = theorem.name
        theorem_proof = theorem.proof
        theorem_proofRange = theorem.proofRange
        tactic_before = theorem.tactic_before
        start = theorem_proofRange.start
        end = theorem_proofRange.stop

        startBy = False
        bPrint = False
        if theorem_proof is None:
             startBy = True
             bPrint = True
        else:
            pp = theorem_proof
            if pp.startswith("by"):
                pp = pp[2:]
                if pp[0] == ' ' or pp[0] == '\t' or pp[0] == '\r' or pp[0] == '\n':
                    startBy = True

        tactic_list = []
        rootTactic_list = []
        for rootTactic in theorem.tactics:
            tactics_data = []
            for tactic in rootTactic.children:
                # 取得該步驟前的證明狀態 (State) 與執行的策略 (Tactic)
                state_before = "\n".join(tactic.before)
                tactic_str = tactic.pp
                if len(tactic.after) == 0:
                    state_after = "no goals"
                else:
                    state_after = "\n".join(tactic.after)
                tactic_start = tactic.range.start
                tactic_end = tactic.range.stop

                # 封裝成訓練格式
                tactic_data = {
                    "tactic": tactic_str,
                    "tactic_before": state_before,
                    "tactic_after": state_after,
                    "tactic_start": get_pos_dict(tactic_start),
                    "tactic_stop": get_pos_dict(tactic_end)
                }
                tactics_data.append(tactic_data)

            if startBy:
                tactic_list = tactics_data
                if theorem_proof is None:
                    theorem_proof = rootTactic.tactic.pp
            else:
                rootTactic_list.append(tactics_data)

        data = {
            "module": name,
            "theorem": theorem_name,
            "theorem_proof": theorem_proof,
            "start": get_pos_dict(start),
            "stop": get_pos_dict(end)
        }

        if len(tactic_list) == 0:
            tactic_data = {
                "tactic": theorem_proof,
                "tactic_before": tactic_before,
                "tactic_after": "no goals",
                "tactic_start": get_pos_dict(start),
                "tactic_stop": get_pos_dict(end)
            }
            tactic_list.append(tactic_data)

        if len(tactic_list) > 0:
            data["tactics"] = tactic_list
        if len(rootTactic_list) > 0:
            data["ref_tactics"] = rootTactic_list

        # 寫入 JSONL
        if data["theorem_proof"] is None:
            print(f"xxxxx proof is none: {theorem_name} {name}")
        fd.write(json.dumps(data, ensure_ascii=False) + '\n')

def process_dir(fd, project, root_dir, prefix: str = None):

    root_path = Path(root_dir)

    for lean_path in root_path.rglob("*.lean"):
        name = lean_path.relative_to(root_path).with_suffix("").as_posix().replace("/", ".")
        if not prefix is None and not name.startswith(str(prefix)):
            continue
        #try:
        module_name = name.split(",")
        process_module(fd, project, module_name)
        #except Exception as e:
        #    print(f"xxxxxx An error occurred to get traced file from: lean path: {lean_path}, {e}")

if __name__ == "__main__":
    TOOLCHAIN_ROOT = "/home/linfe/.elan/toolchains/leanprover--lean4---v4.24.0"
    WORKING_DIR = "/home/linfe/math/lean_test"
    OUTPUT_DIR = WORKING_DIR + "/.jixiaw"

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    project = LeanProject(WORKING_DIR)

    with open(OUTPUT_DIR + "/ast.jsonl", 'w', encoding='utf-8') as fd:
        process_dir(fd, project, WORKING_DIR, "LeanTest")
        process_dir(fd, project, WORKING_DIR + "/.lake/packages/mathlib")#, "Mathlib.MeasureTheory.PiSystem" )
        process_dir(fd, project, TOOLCHAIN_ROOT + "/src/lean", "Init" )


    #module_name = ("LeanTest","Basic")
    
    #module = project.load_module_info(fd, module_name)
    #process_module(project, module_name)


