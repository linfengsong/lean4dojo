import json


# =============================
# Load JSON
# =============================

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# =============================
# Tree Walker
# =============================

def walk_tree(node):
    yield node
    for c in node.get("children", []):
        yield from walk_tree(c)


# =============================
# Extract Tactics From ELAB
# =============================

def extract_all_tactics(elab):

    tactics = []

    for root in elab:
        for node in walk_tree(root):

            info = node.get("info", {})
            ref = node.get("ref", {})

            if "tactic" not in info:
                continue

            tactic_info = info["tactic"]

            tactics.append({
                "tactic_text": ref.get("pp"),
                "range": ref.get("range") or [0, 0],
                "semantic_before": tactic_info.get("before"),
                "semantic_after": tactic_info.get("after"),
                "references": tactic_info.get("references")
            })

    tactics.sort(key=lambda x: x["range"][0])
    return tactics


# =============================
# Extract Theorems
# =============================

def extract_theorems(decl):

    theorems = []

    for d in decl:
        name = d.get("name")
        typ = d.get("type")
        rng = d.get("range") or [0, 10**12]

        if name:
            theorems.append({
                "name": name,
                "type": typ,
                "range": rng
            })

    theorems.sort(key=lambda x: x["range"][0])
    return theorems


# =============================
# Build Line Index
# =============================

def build_line_index(lines):

    idx = {}

    for e in lines:
        start = e.get("start")
        if start is not None:
            idx[start] = e.get("state")

    return idx


# =============================
# Find Closest Line + State
# =============================

def find_line_and_state(line_idx, pos):

    keys = sorted(line_idx.keys())

    best = None
    for k in keys:
        if k <= pos:
            best = k
        else:
            break

    if best is None:
        return None, None

    return best, line_idx[best]


# =============================
# Group Tactics By Theorem
# =============================

def build_dataset(theorems, tactics, line_idx):

    dataset = []

    for thm in theorems:

        start = thm["range"][0]
        end = thm["range"][1]

        proof_steps = []

        for t in tactics:

            pos = t["range"][0]

            if not (start <= pos <= end):
                continue

            line, pretty = find_line_and_state(line_idx, pos)

            proof_steps.append({
                "line": line,
                "tactic_text": t["tactic_text"],
                "semantic_before": t["semantic_before"],
                "semantic_after": t["semantic_after"],
                "pretty_state": pretty
            })

        dataset.append({
            "theorem_name": thm["name"],
            "theorem_type": thm["type"],
            "proof": proof_steps
        })

    return dataset


# =============================
# MAIN
# =============================

def main():

    decl = load_json("../lean_test/Test/LeanTest.Basic.decl.json")
    elab = load_json("../lean_test/Test/LeanTest.Basic.elab.json")
    lines = load_json("../lean_test/Test/LeanTest.Basic.line.json")

    theorems = extract_theorems(decl)
    tactics = extract_all_tactics(elab)
    line_idx = build_line_index(lines)

    dataset = build_dataset(theorems, tactics, line_idx)

    with open("theorem_training_dataset.json", "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)

    print("Done. Theorems:", len(dataset))


if __name__ == "__main__":
    main()
