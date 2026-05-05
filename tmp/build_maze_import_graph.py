import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(".")
DEPS_PATH = ROOT / "maze_import_deps.json"
DOT_PATH = ROOT / "maze_import_graph.dot"
MERMAID_PATH = ROOT / "maze_import_graph.mmd"
SUMMARY_PATH = ROOT / "maze_import_summary.txt"

if not DEPS_PATH.exists():
    raise SystemExit("maze_import_deps.json not found")

data = json.loads(DEPS_PATH.read_text(encoding="utf-8"))

nodes = set()
edges = set()
for mod, payload in data.items():
    if not mod.startswith("maze"):
        continue
    nodes.add(mod)
    for dep in payload.get("imports", []):
        if isinstance(dep, str) and dep.startswith("maze"):
            nodes.add(dep)
            edges.add((mod, dep))

# SCC via Tarjan
index = 0
stack = []
onstack = set()
indices = {}
lowlink = {}
sccs = []
adj = defaultdict(list)
for src, dst in edges:
    adj[src].append(dst)


def strongconnect(v: str) -> None:
    global index
    indices[v] = index
    lowlink[v] = index
    index += 1
    stack.append(v)
    onstack.add(v)

    for w in adj.get(v, []):
        if w not in indices:
            strongconnect(w)
            lowlink[v] = min(lowlink[v], lowlink[w])
        elif w in onstack:
            lowlink[v] = min(lowlink[v], indices[w])

    if lowlink[v] == indices[v]:
        comp = []
        while True:
            w = stack.pop()
            onstack.remove(w)
            comp.append(w)
            if w == v:
                break
        sccs.append(sorted(comp))


for n in sorted(nodes):
    if n not in indices:
        strongconnect(n)

cyclic = [c for c in sccs if len(c) > 1]

# DOT
dot_lines = [
    "digraph maze_imports {",
    "  rankdir=LR;",
    "  node [shape=box, style=rounded, fontsize=10];",
]
for n in sorted(nodes):
    dot_lines.append(f'  "{n}";')
for s, d in sorted(edges):
    dot_lines.append(f'  "{s}" -> "{d}";')
dot_lines.append("}")
DOT_PATH.write_text("\n".join(dot_lines), encoding="utf-8")

# Mermaid
mmd_lines = ["graph LR"]
for i, n in enumerate(sorted(nodes)):
    mmd_lines.append(f"  n{i}[{n}]")
idx = {n: i for i, n in enumerate(sorted(nodes))}
for s, d in sorted(edges):
    mmd_lines.append(f"  n{idx[s]} --> n{idx[d]}")
MERMAID_PATH.write_text("\n".join(mmd_lines), encoding="utf-8")

# Summary
incoming = defaultdict(int)
outgoing = defaultdict(int)
for s, d in edges:
    outgoing[s] += 1
    incoming[d] += 1

hot_out = sorted(outgoing.items(), key=lambda x: x[1], reverse=True)[:20]
hot_in = sorted(incoming.items(), key=lambda x: x[1], reverse=True)[:20]

summary = []
summary.append(f"modules={len(nodes)}")
summary.append(f"edges={len(edges)}")
summary.append(f"cycles={len(cyclic)}")
summary.append("")
summary.append("top_outgoing:")
summary.extend([f"  {m}: {c}" for m, c in hot_out])
summary.append("")
summary.append("top_incoming:")
summary.extend([f"  {m}: {c}" for m, c in hot_in])
summary.append("")
summary.append("cycle_components:")
if cyclic:
    for comp in sorted(cyclic, key=lambda c: (-len(c), c[0])):
        summary.append("  - " + ", ".join(comp))
else:
    summary.append("  - none")

SUMMARY_PATH.write_text("\n".join(summary), encoding="utf-8")
print(f"wrote: {DOT_PATH}")
print(f"wrote: {MERMAID_PATH}")
print(f"wrote: {SUMMARY_PATH}")
print(f"modules={len(nodes)} edges={len(edges)} cycles={len(cyclic)}")
