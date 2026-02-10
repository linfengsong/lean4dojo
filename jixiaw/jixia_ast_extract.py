import json
import os
import sys
import re
from pathlib import Path

# 提升遞迴限制
sys.setrecursionlimit(1000000)

def get_full_range(node):
    positions = []
    def walk(item):
        if isinstance(item, dict):
            for k in ['pos', 'endPos', 'bytePos', 'byteEndPos']:
                v = item.get(k)
                if isinstance(v, (int, float)): positions.append(int(v))
            info = item.get('info', {})
            if isinstance(info, dict):
                orig = info.get('original', {})
                if isinstance(orig, dict) and 'pos' in orig:
                    positions.append(int(orig['pos']))
                    if 'endPos' in orig: positions.append(int(orig['endPos']))
            for v in item.values():
                if isinstance(v, (dict, list)): walk(v)
        elif isinstance(item, list):
            for i in item: walk(i)
    walk(node)
    return (min(positions), max(positions)) if positions else None

def clean_proof(text):
    if not text: return ""
    
    text = re.sub(r'^[ \t\n:=]+', '', text).strip()
    text = re.sub(r'--.*', '', text)
    text = re.sub(r'/-[\s\S]*?-/', '', text)
    
    stop_keywords = ["theorem", "lemma", "instance", "variable", "section", "namespace", "def", "abbrev", "@[", "#"]
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        if any(line.strip().startswith(kw) for kw in stop_keywords): break
        cleaned.append(line)
    
    return "\n".join(cleaned).strip()

def find_name_refined(inner_node):
    """提取標識符名稱"""
    if not isinstance(inner_node, dict): return "Unknown"
    KEYWORDS = {'theorem', 'lemma', 'def', 'instance', 'namespace', 'section', 'protected', 'private', 'open', 'variable'}
    found = []
    def collect(n):
        if not isinstance(n, dict) or len(found) > 0: return
        val = n.get('rawVal')
        if not val and 'atom' in n: val = n['atom'].get('val')
        if not val and 'ident' in n: val = n['ident'].get('rawVal')
        if val and val not in KEYWORDS and not val.startswith('@'):
            found.append(val)
            return
        for arg in n.get('args', []): collect(arg)
        if len(found) == 0:
            for k, v in n.items():
                if k != 'args' and k != 'info' and isinstance(v, dict): collect(v)
    collect(inner_node)
    # 這裡確保回傳的是字串
    return str(found[0]) if found else "Unknown"

def find_correct_lean_source(toolchain_root, project_root, ast_filename):
    base = ast_filename.replace('.ast.json', '')
    parts = base.split('.')
    potential_roots = [
        os.path.join(project_root, ".lake", "packages", "mathlib"),
        project_root,
        os.path.join(toolchain_root, "src", "lean")
    ]
    for p_root in potential_roots:
        rel_path = os.path.join(p_root, *parts) + ".lean"
        if os.path.exists(rel_path): return rel_path
    return None

def process_ast(fd, ast_name, project_root, toolchain_root):
    ast_path = os.path.join(project_root, ".jixia", ast_name)
    module_name = Path(ast_name).with_suffix("").with_suffix("").as_posix()

    with open(ast_path, 'r', encoding='utf-8') as f:
        try:
            ast_data = json.load(f)
        except: return [], []

    lean_file = find_correct_lean_source(toolchain_root, project_root, os.path.basename(ast_path))
    if not lean_file: return [], []
    with open(lean_file, 'rb') as f:
        src_bytes = f.read()

    results = []
    seen_ranges = set()
    
    # 核心修復：使用全局狀態追蹤 Namespace
    global_ns_stack = []

    def scan(obj):
        nonlocal global_ns_stack
        if isinstance(obj, list):
            for item in obj: scan(item)
            return

        if isinstance(obj, dict):
            inner = obj.get('node', obj)
            if not isinstance(inner, dict): return
            
            kind_obj = inner.get('kind', '')
            kind_str = str(kind_obj.get('name', kind_obj) if isinstance(kind_obj, dict) else kind_obj).lower()
            
            # 1. 處理 Namespace 進入
            if 'namespace' in kind_str:
                ns_name = find_name_refined(inner)
                if ns_name != "Unknown":
                    global_ns_stack.append(ns_name)
                    print(f"  [NS] Entered: {'.'.join(global_ns_stack)}")

            # 2. 處理 End (退出 Namespace)
            if 'command.end' in kind_str:
                if global_ns_stack:
                    global_ns_stack.pop()

            # 3. 處理 定理
            is_target = any(k in kind_str for k in ['theorem', 'lemma', 'def', 'instance', 'declaration'])
            if is_target:
                res = get_full_range(obj)
                if res and res not in seen_ranges:
                    t_name = find_name_refined(inner)
                    if t_name != "Unknown" and (not global_ns_stack or t_name != global_ns_stack[-1]):
                        seen_ranges.add(res)

                        # --- 修正名稱處理邏輯 ---
                        # 1. 組合原始名稱
                        full_name_parts = global_ns_stack + [t_name]
                        # 2. 過濾掉包含 "_root_" 的部分（Jixia 有時會抓到這個作為節點）
                        filtered_parts = [p for p in full_name_parts if p != "_root_"]
                        # 3. 合併後再次處理字串中可能殘留的 ._root_. 或開頭的 _root_.
                        full_name = ".".join(filtered_parts).replace("._root_.", ".").replace("_root_.", "")


                        start, end = res
                        text = src_bytes[start:end].decode('utf-8', errors='ignore')
                        match = re.search(r'\b(by|:=|where)\b', text)
                        if match:
                            proof = clean_proof(text[match.start():])
                            if proof:
                                data = {
                                    "module": module_name,
                                    "full_name": full_name, # 使用修正後的名稱 
                                    "tactic_proof": proof
                                }
                                fd.write(json.dumps(data, ensure_ascii=False) + '\n')

            # 遞迴子節點 (不主動彈出 NS)
            for k, v in inner.items():
                if k != 'info' and isinstance(v, (dict, list)):
                    scan(v)

    scan(ast_data)

# --- 配置 ---
TOOLCHAIN_ROOT = "/home/linfe/.elan/toolchains/leanprover--lean4---v4.24.0"
PROJECT_ROOT = "/home/linfe/math/jixiaw/lean_test"

if __name__ == "__main__":
    #AST_NAME = "Mathlib.Algebra.Homology.Refinements.ast.json"
    #extract_proof_from_ast(AST_NAME, PROJECT_ROOT, TOOLCHAIN_ROOT)
    jixia_path = Path(PROJECT_ROOT) / Path(".jixia")
    with open(PROJECT_ROOT + "/ast.jsonl", 'w', encoding='utf-8') as fd:
        for path in jixia_path.glob("Mathlib.NumberTheory.NumberField.*.json"):
        #for path in jixia_path.glob("*.ast.json"):
            ast_name = path.name
            process_ast(fd, ast_name, PROJECT_ROOT, TOOLCHAIN_ROOT)
























