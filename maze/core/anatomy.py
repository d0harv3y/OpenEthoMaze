from __future__ import annotations

STANDARD_NODE_NAMES: tuple[str, ...] = (
    "nose",
    "tail",
    "neck",
    "hindL",
    "foreL",
    "foreR",
    "hindR",
    "spine",
)

# Backup blob polygon (H5 tracking/blob, E6 stream B). Fixed at 8 to match len(STANDARD_NODE_NAMES).
BLOB_VERTEX_COUNT: int = len(STANDARD_NODE_NAMES)
BLOB_NODE_NAMES: tuple[str, ...] = tuple(f"blob_p{i}" for i in range(BLOB_VERTEX_COUNT))

FALLBACK_NODE_INDEX: dict[str, int] = {
    node_name: index for index, node_name in enumerate(STANDARD_NODE_NAMES)
}

SPOT_NODE_NAMES: tuple[str, ...] = ("nose", "neck", "foreL", "foreR")
SPOT_NODE_NAMES_CASEFOLDED: frozenset[str] = frozenset(
    node_name.casefold() for node_name in SPOT_NODE_NAMES
)

SKELETON_EDGES: tuple[tuple[str, str], ...] = (
    ("nose", "neck"),
    ("neck", "spine"),
    ("spine", "tail"),
    ("tail", "hindL"),
    ("tail", "hindR"),
    ("neck", "foreL"),
    ("neck", "foreR"),
)


def is_spot_node_name(node_name: str) -> bool:
    """Return True when a node contributes to the front-body spot."""
    return node_name.strip().casefold() in SPOT_NODE_NAMES_CASEFOLDED


def skeleton_edge_indices(
    node_names: tuple[str, ...] | list[str] = STANDARD_NODE_NAMES,
) -> list[tuple[int, int]]:
    """Convert named skeleton edges to index pairs for a node ordering."""
    name_to_idx = {name: i for i, name in enumerate(node_names)}
    return [
        (name_to_idx[start], name_to_idx[end])
        for start, end in SKELETON_EDGES
        if start in name_to_idx and end in name_to_idx
    ]
