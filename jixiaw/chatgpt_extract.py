import json


# =============================
# Load JSON
# =============================

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# =============================
# Generic Tree Walker
# =============================

def walk_tree(node):
    yield node
    for c in node.get("children", []):
        yield from walk_tree(c)


# =============================
# Extract All Tactics (ELAB)
# =============================

def extract_all_tactics(elab):

    tactics = []

    for root in elab:
        for node in walk_tree(root):

            info = node.get("info", {})
            ref = node.get("ref", {})

            if "tactic" not in info:
                continue

            tactic_info = info.get("tactic", {})

            tactics.append({
                "tactic_text": ref.get("pp"),
                "range": ref.get("range") or [0, 0],
                "semantic_before": tactic_info.get("before"),
                "semantic_after": tactic_info.get("after"),
                "references": tactic_info.get("references")
            })

    # Sort by source order
    tactics.sort(key=lambda x: x["range"][0])

    return tactics


# =============================
# Extract Theorems (DECL)
# =============================

def extract_theorems(decl):

    theorems = []

    for d in decl:

        name = d.get("name")
        typ = d.get("type")
        rng = d.get("range") or [0, 10**12]

        if name and typ:
            theorems.append({
                "name": name,
                "type": typ,
                "range": rng
            })

    # sort by start position
    theorems.sort(key=lambda x: x["range"][0])

    return theorems


# =============================
# Lines Pretty State
# =============================

def build_line_index(lines):
    idx = {}
    for e in lines:
        start = e.get("start")
        if start is not None:
            idx[start] = e.get("state")
    return idx


def find_pretty_state(line_idx, pos):

    if pos in line_idx:
        return line_idx[pos]

    # nearest earlier
    keys = sorted(line_idx.keys())
    best = None

    for k in keys:
        if k <= pos:
            best = k
        else:
            break

    if best is None:
        return None

    return line_idx[best]


# =============================
# Assign Tactics To Theorem
# =============================

def group_tactics_by_theorem(theorems, tactics):

    results = []

    for thm in theorems:

        start = thm["range"][0]
        end = thm["range"][1]

        thm_tactics = [
            t for t in tactics
            if start <= t["range"][0] <= end
        ]

        results.append({
            "theorem_name": thm["name"],
            "theorem_type": thm["type"],
            "tactics": thm_tactics
        })

    return results


# =============================
# Attach Pretty State
# =============================

def attach_pretty_states(dataset, line_idx):

    for thm in dataset:
        for t in thm["tactics"]:
            pos = t["range"][0]
            t["pretty_state"] = find_pretty_state(line_idx, pos)

    return dataset


# =============================
# Main Pipeline
# =============================

def build_dataset(decl, elab, lines):

    theorems = extract_theorems(decl)
    tactics = extract_all_tactics(elab)
    line_idx = build_line_index(lines)

    dataset = group_tactics_by_theorem(theorems, tactics)
    dataset = attach_pretty_states(dataset, line_idx)

    return dataset


# =============================
# Main
# =============================

def main():

    decl = load_json("../lean_test/Test/LeanTest.Basic.decl.json")
    elab = load_json("../lean_test/Test/LeanTest.Basic.elab.json")
    lines = load_json("../lean_test/Test/LeanTest.Basic.line.json")

    dataset = build_dataset(decl, elab, lines)

    with open("full_training_dataset.json", "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)

    print("Dataset size (theorems):", len(dataset))


if __name__ == "__main__":
    main()
