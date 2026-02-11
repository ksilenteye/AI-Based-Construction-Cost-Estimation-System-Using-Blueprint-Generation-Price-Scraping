from dataclasses import dataclass
from typing import List, Dict, Tuple
from collections import defaultdict

EPS = 0.01
MIN_CORRIDOR_AREA = 6.0
OUTER_WALL_THICKNESS = 0.6
INNER_WALL_CLEARANCE = OUTER_WALL_THICKNESS / 2


@dataclass
class WallSegment:
    x1: float
    y1: float
    x2: float
    y2: float
    kind: str   # "outer" | "inner"


@dataclass
class Cell:
    room_id: str
    purpose: str
    x: float
    y: float
    w: float
    h: float

    @property
    def area(self):
        return self.w * self.h

    def edges(self):
        return [
            ((self.x, self.y), (self.x + self.w, self.y)),             # top
            ((self.x + self.w, self.y), (self.x + self.w, self.y + self.h)),  # right
            ((self.x + self.w, self.y + self.h), (self.x, self.y + self.h)),  # bottom
            ((self.x, self.y + self.h), (self.x, self.y))              # left
        ]
def rooms_to_cells(layout: dict) -> List[Cell]:
    cells = []
    for r in layout["rooms"]:
        cells.append(
            Cell(
                room_id=r["room_id"],
                purpose=r["purpose"],
                x=r["x"],
                y=r["y"],
                w=r["width"],
                h=r["height"]
            )
        )
    return cells
def filter_noise_cells(cells: List[Cell]) -> List[Cell]:
    clean = []
    for c in cells:
        if c.purpose == "circulation" and c.area < MIN_CORRIDOR_AREA:
            continue
        clean.append(c)
    return clean

def compute_union_silhouette(cells, grid=0.5):
    """
    Returns a SINGLE outer silhouette wrapping all cells.
    Output: List[WallSegment(kind="outer")]
    """

    # ---------------------------------------------
    # 1. Rasterize occupied space
    # ---------------------------------------------
    occupied = set()

    def snap(v):
        return round(v / grid) * grid

    for c in cells:
        x0 = snap(c.x)
        y0 = snap(c.y)
        x1 = snap(c.x + c.w)
        y1 = snap(c.y + c.h)

        x = x0
        while x < x1 - 1e-6:
            y = y0
            while y < y1 - 1e-6:
                occupied.add((x, y))
                y += grid
            x += grid

    # ---------------------------------------------
    # 2. Detect boundary edges
    # ---------------------------------------------
    edges = []

    for (x, y) in occupied:
        neighbors = {
            "left":   (x - grid, y),
            "right":  (x + grid, y),
            "top":    (x, y - grid),
            "bottom": (x, y + grid),
        }

        # left boundary
        if neighbors["left"] not in occupied:
            edges.append(((x, y), (x, y + grid)))

        # right boundary
        if neighbors["right"] not in occupied:
            edges.append(((x + grid, y), (x + grid, y + grid)))

        # top boundary
        if neighbors["top"] not in occupied:
            edges.append(((x, y), (x + grid, y)))

        # bottom boundary
        if neighbors["bottom"] not in occupied:
            edges.append(((x, y + grid), (x + grid, y + grid)))

    # ---------------------------------------------
    # 3. Merge collinear edges
    # ---------------------------------------------
    segments = []
    for (p1, p2) in edges:
        segments.append(
            WallSegment(
                x1=p1[0], y1=p1[1],
                x2=p2[0], y2=p2[1],
                kind="outer"
            )
        )

    return merge_walls(segments)


def merge_walls(walls: List[WallSegment]) -> List[WallSegment]:
    merged = []

    for w in walls:
        merged_into_existing = False

        for m in merged:
            if w.kind != m.kind:
                continue

            # vertical merge
            if abs(w.x1 - w.x2) < EPS and abs(m.x1 - m.x2) < EPS:
                if abs(w.x1 - m.x1) < EPS and (abs(w.y2 - m.y1) < EPS or abs(w.y1 - m.y2) < EPS):
                    m.y1 = min(m.y1, w.y1, w.y2)
                    m.y2 = max(m.y2, w.y1, w.y2)
                    merged_into_existing = True
                    break

            # horizontal merge
            if abs(w.y1 - w.y2) < EPS and abs(m.y1 - m.y2) < EPS:
                if abs(w.y1 - m.y1) < EPS and (abs(w.x2 - m.x1) < EPS or abs(w.x1 - m.x2) < EPS):
                    m.x1 = min(m.x1, w.x1, w.x2)
                    m.x2 = max(m.x2, w.x1, w.x2)
                    merged_into_existing = True
                    break

        if not merged_into_existing:
            merged.append(w)

    return merged


def _norm_edge(p1, p2):
    return tuple(sorted((p1, p2)))

def compute_outer_hull(cells):
    edge_map = build_edge_map(cells)
    outer = []

    for (p1, p2), owners in edge_map.items():
        if len(owners) == 1 and owners[0].purpose != "circulation":
            outer.append(WallSegment(
                p1[0], p1[1],
                p2[0], p2[1],
                "outer"
            ))

    return merge_walls(outer)




def compute_inner_walls(cells, tol=0.05):
    inner = []

    for i, a in enumerate(cells):
        for b in cells[i+1:]:
            # skip same room
            if a.room_id == b.room_id:
                continue

            # ---------- vertical adjacency ----------
            # a right touches b left
            if abs((a.x + a.w) - b.x) < tol or abs((b.x + b.w) - a.x) < tol:
                y1 = max(a.y, b.y)
                y2 = min(a.y + a.h, b.y + b.h)

                if y2 - y1 > tol:
                    x = a.x + a.w if abs((a.x + a.w) - b.x) < tol else b.x + b.w
                    inner.append(WallSegment(x, y1, x, y2, "inner"))

            # ---------- horizontal adjacency ----------
            # a bottom touches b top
            if abs((a.y + a.h) - b.y) < tol or abs((b.y + b.h) - a.y) < tol:
                x1 = max(a.x, b.x)
                x2 = min(a.x + a.w, b.x + b.w)

                if x2 - x1 > tol:
                    y = a.y + a.h if abs((a.y + a.h) - b.y) < tol else b.y + b.h
                    inner.append(WallSegment(x1, y, x2, y, "inner"))

    return merge_walls(inner)




def build_edge_map(cells: List[Cell]):
    edge_map = defaultdict(list)
    for c in cells:
        for p1, p2 in c.edges():
            edge_map[_norm_edge(p1, p2)].append(c)
    return edge_map

def wall_key(w: WallSegment):
    return tuple(sorted(((w.x1, w.y1), (w.x2, w.y2))))


def offset_outer_walls(walls: List[WallSegment], cells: List[Cell], thickness=0.6):
    """
    Offsets outer walls OUTWARD by half thickness.
    Inner walls are untouched.
    """
    offset = thickness / 2
    cell_boxes = [
        (c.x, c.y, c.x + c.w, c.y + c.h)
        for c in cells if c.purpose != "circulation"
    ]

    def intersects_cells(x1, y1, x2, y2):
        for cx1, cy1, cx2, cy2 in cell_boxes:
            if not (x2 <= cx1 or x1 >= cx2 or y2 <= cy1 or y1 >= cy2):
                return True
        return False

    shifted = []

    for w in walls:
        if w.kind != "outer":
            shifted.append(w)
            continue

        # vertical wall
        if abs(w.x1 - w.x2) < EPS:
            # test left
            test_left = (
                w.x1 - offset, w.y1,
                w.x2 - offset, w.y2
            )
            if intersects_cells(*test_left):
                dx = offset   # inside → shift right
            else:
                dx = -offset  # outside → shift left

            shifted.append(WallSegment(
                w.x1 + dx, w.y1,
                w.x2 + dx, w.y2,
                "outer"
            ))

        # horizontal wall
        elif abs(w.y1 - w.y2) < EPS:
            # test up
            test_up = (
                w.x1, w.y1 - offset,
                w.x2, w.y2 - offset
            )
            if intersects_cells(*test_up):
                dy = offset   # inside → shift down
            else:
                dy = -offset  # outside → shift up

            shifted.append(WallSegment(
                w.x1, w.y1 + dy,
                w.x2, w.y2 + dy,
                "outer"
            ))

        else:
            # fallback (should never happen)
            shifted.append(w)

    return shifted


def merge_inner_partitions(walls, tol=0.01):
    vertical = {}
    horizontal = {}
    result = []

    for w in walls:
        if abs(w.x1 - w.x2) < tol:
            x = round(w.x1, 2)
            vertical.setdefault(x, []).append((w.y1, w.y2))
        elif abs(w.y1 - w.y2) < tol:
            y = round(w.y1, 2)
            horizontal.setdefault(y, []).append((w.x1, w.x2))

    # merge vertical
    for x, spans in vertical.items():
        spans.sort()
        s, e = spans[0]
        for ns, ne in spans[1:]:
            if ns <= e + tol:
                e = max(e, ne)
            else:
                result.append(WallSegment(x, s, x, e, "inner"))
                s, e = ns, ne
        result.append(WallSegment(x, s, x, e, "inner"))

    # merge horizontal
    for y, spans in horizontal.items():
        spans.sort()
        s, e = spans[0]
        for ns, ne in spans[1:]:
            if ns <= e + tol:
                e = max(e, ne)
            else:
                result.append(WallSegment(s, y, e, y, "inner"))
                s, e = ns, ne
        result.append(WallSegment(s, y, e, y, "inner"))

    return result


def compute_room_partition_walls(cells):
    walls = []

    for c in cells:
        # 🚫 corridor does NOT own walls
        if c.purpose == "circulation":
            continue

        # left
        walls.append(WallSegment(c.x, c.y, c.x, c.y + c.h, "inner"))
        # right
        walls.append(WallSegment(c.x + c.w, c.y, c.x + c.w, c.y + c.h, "inner"))
        # top
        walls.append(WallSegment(c.x, c.y, c.x + c.w, c.y, "inner"))
        # bottom
        walls.append(WallSegment(c.x, c.y + c.h, c.x + c.w, c.y + c.h, "inner"))

    return walls

def subtract_outer_from_inner(inner, outer, tol=0.01):
    outer_keys = {
        (round(w.x1,2), round(w.y1,2), round(w.x2,2), round(w.y2,2))
        for w in outer
    }

    result = []
    for w in inner:
        key = (round(w.x1,2), round(w.y1,2), round(w.x2,2), round(w.y2,2))
        if key not in outer_keys:
            result.append(w)

    return result


def build_envelope(layout):
    cells = filter_noise_cells(rooms_to_cells(layout))

    outer = compute_union_silhouette(cells)

    inner_raw = compute_room_partition_walls(cells)
    inner_clean = subtract_outer_from_inner(inner_raw, outer)
    inner = merge_walls(inner_clean)

    return outer + inner







# donot use it me it the fucking issue
def trim_inner_wall(w, outer_keys, clearance=0.1):
    x1, y1, x2, y2 = w.x1, w.y1, w.x2, w.y2

    if abs(x1 - x2) < EPS:      # vertical
        y1 += clearance
        y2 -= clearance
    elif abs(y1 - y2) < EPS:    # horizontal
        x1 += clearance
        x2 -= clearance

    if abs(x2 - x1) < EPS or abs(y2 - y1) < EPS:
        return None

    return WallSegment(x1, y1, x2, y2, "inner")