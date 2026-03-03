import json
import os
import re
from pathlib import Path
from dataclasses import dataclass
from jixia import LeanProject
from jixia.structs import Declaration, StringRange, InfoTree, LineModel, Plugin
from .util import getLeanSourceDirOrFile, collect_match_modules

@dataclass(frozen=True, order=True)
class FilePos:
    line: int
    column: int

@dataclass(frozen=True)
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
    
    def __lt__(self, other):
        return self.start < other.start or self.start == other.start and self.stop >= other.stop
    
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
    proofType: str
    
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

def collect_all_tactics(nodes: list, lines: list):
    tactics = []
    for node in nodes:
        if node.info and node.info.tactic:
            tactic = createTactic(node.ref, node.info.tactic, lines)
            sub_tactics = collect_sub_tactics(node.children, lines)
            rootTactic = RootTactic(tactic.fileRange, tactic.pp, tactic.before, tactic.after, sub_tactics)
            tactics.append(rootTactic)
            return tactics
        elif node.children:
            tactics.extend(collect_all_tactics(node.children, lines))
    return sorted(tactics, key=lambda x: x.fileRange, reverse=False)

def find_root_tactrics(fileRange: FileRange, rootTactics: list[RootTactic]):
    tactics = []
    for rootTactic in rootTactics:
        if fileRange.inRange(rootTactic.fileRange):
            tactics.append(rootTactic)
    return tactics

def find_all_terms(nodes: list, pp: str):
    founds = []
    for node in nodes:
        if node.ref and pp in node.ref.pp:
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
                founds.append(item)
    return founds

def extractLine(line: str, start: int, stop: int = -1):
    buf = bytes(line, encoding='utf-8')
    if stop == -1:
        stop = len(buf)
    buf = buf[start : stop]
    return buf.decode('utf-8') 

def getLeanSourceCode(project, module_name: list[str], fileRange: FileRange):
    file_path = getLeanSourceDirOrFile(project, module_name, True)
    if file_path is None:
        raise "Cannot find module_name: {module_name}"

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

def getToken(line: str, index: int):
    tokens = line.strip().replace("\n", " ").replace("\r", " ").replace("\t", " ").split()
    if index < 0:
        index = len(tokens) + index
    if index >= len(tokens):
        return None
    return tokens[index]

def getTheoremName(module_name: list[str], decl: Declaration):
    #first item is "_private" if it's a private declaration, we need to remove the prefix and get the real name
    # for example, if the declaration name is ["_private", "Init", "Nat", "add"], and the module name is ["Init", "Nat"], we need to remove the prefix and get the real name "add"  
    if decl.name is None or len(decl.name) == 0:
        return None
    if decl.name[0] != '_private':
        return ".".join(decl.name)
    private_name = decl.name[len(module_name) + 2:]
    return ".".join(private_name)

# =============================
# Extract Theorems
# =============================
def extract_theorem_signature_proof(project, module_name, lines, signature_start, theorem_stop):
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
    if not project.has_info(module_name, Declaration) or not project.has_info(module_name, InfoTree):
        return []
    declarations = project.load_info(module_name, Declaration)
    infoTrees = project.load_info(module_name, InfoTree)
    if project.has_info(module_name, LineModel):
        lines = project.load_info(module_name, LineModel)
    else:
        lines = []
    rootTactics = collect_all_tactics(infoTrees, lines)
    terms = collect_all_terms(infoTrees, lines, module_name)
    theorems = []
    for _, decl in enumerate(declarations):
        if decl.kind == "theorem":
            if len(decl.name) == 0:
                continue;
            theorem = extract_theorem(project, module_name, decl, lines, rootTactics, terms)
            if theorem is not None:
                theorems.append(theorem)
    return theorems

def extract_theorem(project, module_name, decl, lines, rootTactics, terms):
    theorem_name = getTheoremName(module_name, decl)
    theorem_range = FileRange.fromStringRange(lines, decl.ref.range)
    tactics = find_root_tactrics(theorem_range, rootTactics)

    signature = decl.signature.pp
    signatureRange = FileRange.fromStringRange(lines, decl.signature.range)
            
    statement = decl.value.pp
    theorem_proofRange = FileRange.fromStringRange(lines, decl.value.range)

    if statement is None:
        statement = getLeanSourceCode(project, module_name, theorem_proofRange)

    proofOperator = getToken(statement, 0)
    if proofOperator != ":=" and proofOperator != "|" and proofOperator != "where":
        print(f"xxxxx proofOperator {proofOperator}  is not valid, remove: {theorem_name} {module_name}")
        return None

    if statement is None:
        print(f"xxxxx no proof, remove: {theorem_name} {module_name}")
        return None
    if proofOperator is None:
        print(f"xxxxx no proofOperator, remove: {theorem_name} {module_name}")
        return None
    
    statement = statement.rstrip()[len(proofOperator) + 1:].lstrip()
    startBy = True
    byToken = getToken(statement, 0)
    if byToken is None or byToken != "by":
        startBy = False

    theorem_proof = statement[len(proofOperator):].lstrip()
    tactic_before = None
    tactic_after = None
    proofTactic = None
    proofType = "Term"
    if startBy:
        proofType = "Tactic"
        if len(tactics) > 0:
            proofTactic = tactics.pop(0)
            tactic_before = proofTactic.before
            tactic_after = proofTactic.after

    if proofTactic is None:
        name_array = theorem_name.split(".")
        term = None
        while term is None and len(name_array) > 0:
            search_name = ".".join(name_array)
            term = find_term(theorem_range, search_name, terms)
            if term is None and not search_name.startswith("@"):
                search_name = "@" + search_name
                term = find_term(theorem_range, search_name, terms)
            name_array.pop(0)
        if term is None:
            search_name = "_root_." + theorem_name
            term = find_term(theorem_range, search_name, terms)
            if term is None:
                search_name = "@" + search_name
                term = find_term(theorem_range, search_name, terms)
        if term is None:
            search_name = "«" + theorem_name.split('.')[-1] + "»"
            term = find_term(theorem_range, search_name, terms)
            if term is None:
                search_name = "@" + search_name
                term = find_term(theorem_range, search_name, terms)

        if term is not None:
            tactic_before = term.type
        elif startBy:
            print(f"xxxxx ERROR tactic_before is none on Tactic: {theorem_name} {module_name}")
        else:
            if decl.name[0] != '_private':
                print(f"xxxxx tactic_before is none, remove: {theorem_name} {module_name}")
            return None

    return Theorem(theorem_range, theorem_name, signature, signatureRange, proofOperator, theorem_proof, theorem_proofRange, proofType, proofTactic, tactics, tactic_before, tactic_after)

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

def process_module(project, module_name, operatorSet):
    theorems = extract_theorems(project,module_name)
    name = ".".join(module_name)
    lines = []
    for theorem in theorems:
        theorem_name = theorem.name
        theorem_signature = theorem.signature
        theorem_operator = theorem.proofOperator
        theorem_proof = theorem.proof
        theorem_proofFileRange = theorem.proofFileRange
        theorem_proofType = theorem.proofType
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

        data = {
            "module": name,
            "theorem": theorem_name,
            "teorem_signature:": theorem_signature,
            "theorem_operator": theorem_operator,
            "theorem_proof": theorem_proof,
            "theorem_proofType": theorem_proofType,
            "tactic_before:": tactic_before,
            "tactic_after": tactic_after,
            "start": get_pos_dict(start),
            "stop": get_pos_dict(end)
        }

        if theorem.proofTactic is not None:
            data["tactics"] = create_rootTacitic_data(theorem.proofTactic)
        if len(rootTactic_list) > 0:
            data["ref_tactics"] = rootTactic_list

        lines.append(json.dumps(data, ensure_ascii=False))
        if theorem_operator in operatorSet:
            count =  operatorSet[theorem_operator] + 1
        else:
            count = 1
        operatorSet[theorem_operator] = count
    return lines

def process_searches(working_dir: str, search_list: list[str]):
    output_dir = working_dir + "/.jixiaw"
    os.makedirs(output_dir, exist_ok=True)
    project = LeanProject(working_dir)
    modules = []
    for search in search_list:
        modules.extend(collect_match_modules(project, search))

    operatorSet = {":=": 0}
    #with open(output_dir + "/ast.jsonl", 'w', encoding='utf-8') as fd:
    #    for module in modules:
    #        lines = process_module(project, module, operatorSet)
    #        for line in lines:
    #            fd.write(f'{line}\n')
    for module_name in modules:
        module_str = ".".join(module_name)
        path = f"{output_dir}/{module_str}.jsonl"
        with open(path, 'w', encoding='utf-8') as fd:
            lines = process_module(project, module_name, operatorSet)
            fd.write('\n'.join(lines) + '\n')

    print(f"Theorem Operator Set: {operatorSet}")

if __name__ == "__main__":
    search_list = [
        #"Init",
        #"Mathlib",
        "LeanTest",
        #Mathlib.Analysis.CStarAlgebra.ContinuousFunctionalCalculus.Unitary"
        #"Mathlib.Topology.Algebra.Order.LiminfLimsup",
        #"Init.Grind.Ordered.Field",
        #"Mathlib.MeasureTheory.Measure.Real",
        #"Mathlib.Data.List.InsertIdx",
        #"Mathlib.Analysis.Analytic.IteratedFDeriv"
        #"Mathlib.MeasureTheory.PiSystem",
        #"Mathlib.Analysis.Calculus.ContDiff.FTaylorSeries",
        #"Mathlib.MeasureTheory.Measure.Support",
        #"Mathlib.RingTheory.Kaehler.Polynomial",
        #"Mathlib.Algebra.Category.CommAlgCat.Monoidal",
        #"Mathlib.MeasureTheory.Constructions.BorelSpace.Order",
        #"Mathlib.Tactic.CC.Addition",
        #"Mathlib.LinearAlgebra.Dual.Lemmas",
        #"Mathlib.LinearAlgebra.QuadraticForm",
        #"Mathlib.LinearAlgebra.Basis.Submodule"
        #"Mathlib.GroupTheory.GroupAction.MultipleTransitivity"
        #"Mathlib.RingTheory.TensorProduct.Basic"
    ]

    process_searches("/home/linfe/math/lean_test", search_list)

