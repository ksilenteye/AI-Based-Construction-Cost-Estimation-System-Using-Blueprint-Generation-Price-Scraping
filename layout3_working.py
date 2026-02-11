from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
import json
import sqlite3
import math


@dataclass
class Room:
    room_id: str
    name: str
    purpose: str
    width: float
    height: float
    zone: str
    adjacency: List[Dict]
    x: float = 0
    y: float = 0
    locked: bool = False
    priority: int = 0
    
    def bounds(self) -> Tuple[float, float, float, float]:
        return (self.x, self.y, self.x + self.width, self.y + self.height)
    
    def center(self) -> Tuple[float, float]:
        return (self.x + self.width / 2, self.y + self.height / 2)
    
    def area(self) -> float:
        return self.width * self.height
    
    @staticmethod
    def make_corridor(room_a, room_b, width=4):
        MAX_CORRIDOR_LEN = 12
        ax, ay = room_a.center()
        bx, by = room_b.center()
        
        if abs(ax - bx) > abs(ay - by):
            length = min(abs(ax - bx), MAX_CORRIDOR_LEN)
            x = min(ax, bx)
            y = (ay + by) / 2 - width / 2
            w, h = length, width
        else:
            length = min(abs(ay - by), MAX_CORRIDOR_LEN)
            x = (ax + bx) / 2 - width / 2
            y = min(ay, by)
            w, h = width, length
        
        return Room(
            room_id=f"corridor_{room_a.room_id}_{room_b.room_id}",
            name="Corridor",
            purpose="circulation",
            width=w,
            height=h,
            zone="circulation",
            adjacency=[],
            x=x,
            y=y
        )


class ImprovedZonePlacer:
    """Strategic placement with architectural logic"""
    
    def __init__(self, plot_w, plot_h, setbacks):
        self.x0 = setbacks["left"]
        self.y0 = setbacks["front"]
        self.w = plot_w - setbacks["left"] - setbacks["right"]
        self.h = plot_h - setbacks["front"] - setbacks["rear"]
        self.bounds = (self.x0, self.y0, self.x0 + self.w, self.y0 + self.h)
    
    def place(self, rooms: List[Room]) -> List[Room]:
        # Set priorities
        for r in rooms:
            if r.purpose == "living":
                r.priority = 100
            elif r.purpose == "bedroom" and "master" in r.name.lower():
                r.priority = 90
            elif r.purpose == "bathroom" and "master" in r.name.lower():
                r.priority = 85
            elif r.purpose == "kitchen":
                r.priority = 80
            elif r.purpose == "bedroom":
                r.priority = 70
            elif r.purpose == "bathroom":
                r.priority = 65
            elif "foyer" in r.name.lower():
                r.priority = 95
            else:
                r.priority = 50
        
        # Separate rooms by type
        living_room = next((r for r in rooms if r.purpose == "living"), None)
        foyer = next((r for r in rooms if "foyer" in r.name.lower()), None)
        kitchen = next((r for r in rooms if r.purpose == "kitchen"), None)
        master_bed = next((r for r in rooms if r.purpose == "bedroom" and "master" in r.name.lower()), None)
        master_bath = next((r for r in rooms if r.purpose == "bathroom" and "master" in r.name.lower()), None)
        common_bath = next((r for r in rooms if r.purpose == "bathroom" and "common" in r.name.lower()), None)
        kids_rooms = [r for r in rooms if r.purpose == "bedroom" and "master" not in r.name.lower()]
        
        # STRATEGIC PLACEMENT
        # Top-left: Living room (main space)
        if living_room:
            living_room.x = self.x0 + 1
            living_room.y = self.y0 + 1
        
        # Top-left corner: Foyer (entrance)
        if foyer and living_room:
            foyer.x = self.x0 + 1
            foyer.y = self.y0 + 1
            # Push living room to the right
            living_room.x = foyer.x + foyer.width + 1
        
        # Kitchen: Right of foyer or below living if foyer absent
        if kitchen:
            if foyer:
                kitchen.x = foyer.x
                kitchen.y = foyer.y + foyer.height + 1
            elif living_room:
                kitchen.x = living_room.x
                kitchen.y = living_room.y + living_room.height + 1
            else:
                kitchen.x = self.x0 + 1
                kitchen.y = self.y0 + 1
        
        # Common bathroom: Attach to living room (right side)
        if common_bath and living_room:
            common_bath.x = living_room.x + living_room.width + 0.5
            common_bath.y = living_room.y + 2
        
        # Master bedroom: Bottom-left (private zone)
        if master_bed:
            if kitchen:
                master_bed.x = self.x0 + 1
                master_bed.y = kitchen.y + kitchen.height + 2
            else:
                master_bed.x = self.x0 + 1
                master_bed.y = self.y0 + self.h * 0.5
        
        # Master bathroom: DIRECTLY attach to master bedroom (right side)
        if master_bath and master_bed:
            master_bath.x = master_bed.x
            master_bath.y = master_bed.y + master_bed.height + 0.5
            master_bath.locked = True
        
        # Kids bedroom: Bottom-right
        if kids_rooms and master_bed:
            for i, kid_room in enumerate(kids_rooms):
                kid_room.x = master_bed.x + master_bed.width + 1.5
                kid_room.y = master_bed.y + (i * (kid_room.height + 1))
        
        return rooms


class StrictAdjacencyRefiner:
    """Enforces critical adjacencies"""
    GRID = 0.5
    MIN_SHARED_WALL = 2.5
    
    def refine(self, rooms: List[Room], bounds, iterations=3) -> List[Room]:
        room_map = {r.room_id: r for r in rooms}
        
        for iteration in range(iterations):
            # CRITICAL: Master bathroom MUST attach to master bedroom
            master_bed = next((r for r in rooms if r.purpose == "bedroom" and "master" in r.name.lower()), None)
            master_bath = next((r for r in rooms if r.purpose == "bathroom" and "master" in r.name.lower()), None)
            
            if master_bed and master_bath:
                # Force attachment to right side
                master_bath.x = master_bed.x + master_bed.width + 0.5
                master_bath.y = master_bed.y
                master_bath.locked = True
            
            # Process other attachments
            attachments = []
            for anchor in rooms:
                for edge in anchor.adjacency:
                    if edge["type"] != "attach":
                        continue
                    target = room_map.get(edge["to"])
                    if not target:
                        continue
                    
                    # Skip master bathroom (already handled)
                    if target.purpose == "bathroom" and "master" in target.name.lower():
                        continue
                    
                    priority = 0
                    if target.purpose == "bathroom" and anchor.purpose == "bedroom":
                        priority = 80
                    elif {anchor.purpose, target.purpose} == {"kitchen", "living"}:
                        priority = 70
                    elif target.purpose == "bathroom" and anchor.purpose == "living":
                        priority = 75
                    else:
                        priority = 50
                    
                    attachments.append((priority, anchor, target, edge))
            
            attachments.sort(key=lambda x: x[0], reverse=True)
            
            for _, anchor, target, edge in attachments:
                if anchor.purpose == "circulation" or target.purpose == "circulation":
                    continue
                
                if getattr(target, "locked", False):
                    continue
                
                best = self._best_snap(anchor, target, rooms, bounds, edge)
                if best:
                    target.x, target.y = best
        
        for r in rooms:
            self._snap_room_to_grid(r)
        
        return rooms
    
    def _best_snap(self, anchor, mover, rooms, bounds, edge):
        ax1, ay1, ax2, ay2 = anchor.bounds()
        bw, bh = mover.width, mover.height
        
        candidates = {
            "right": (ax2 + 0.5, ay1),
            "left": (ax1 - bw - 0.5, ay1),
            "top": (ax1, ay1 - bh - 0.5),
            "bottom": (ax1, ay2 + 0.5)
        }
        
        EDGE_MAP = {"front": "top", "rear": "bottom", "left": "left", "right": "right"}
        preferred = EDGE_MAP.get(edge.get("edge_preference"))
        scored = []
        
        orig_x, orig_y = mover.x, mover.y
        
        for side, (x, y) in candidates.items():
            mover.x, mover.y = x, y
            
            if not self._inside_bounds(mover, bounds):
                continue
            
            if self._overlaps_any(mover, rooms, ignore=anchor):
                continue
            
            overlap = self._wall_overlap(anchor, mover, side)
            
            if overlap < self.MIN_SHARED_WALL:
                continue
            
            dist = self._manhattan(anchor, mover)
            
            score = overlap * 100
            score -= dist * 2
            
            if preferred == side:
                score += overlap * 100
            
            scored.append((score, x, y))
        
        mover.x, mover.y = orig_x, orig_y
        
        if not scored:
            return None
        
        scored.sort(reverse=True)
        _, x, y = scored[0]
        return self._snap_to_grid(x), self._snap_to_grid(y)
    
    def _manhattan(self, a: Room, b: Room) -> float:
        ax, ay = a.center()
        bx, by = b.center()
        return abs(ax - bx) + abs(ay - by)
    
    def _inside_bounds(self, room: Room, bounds):
        x1, y1, x2, y2 = room.bounds()
        bx1, by1, bx2, by2 = bounds
        return bx1 <= x1 and by1 <= y1 and x2 <= bx2 and y2 <= by2
    
    def _snap_to_grid(self, v: float) -> float:
        return round(v / self.GRID) * self.GRID
    
    def _snap_room_to_grid(self, room: Room):
        room.x = self._snap_to_grid(room.x)
        room.y = self._snap_to_grid(room.y)
    
    def _overlaps_any(self, room, rooms, ignore):
        for r in rooms:
            if r is room or r is ignore:
                continue
            if self._overlap(room, r):
                return True
        return False
    
    def _overlap(self, a: Room, b: Room):
        ax1, ay1, ax2, ay2 = a.bounds()
        bx1, by1, bx2, by2 = b.bounds()
        return not (ax2 <= bx1 or ax1 >= bx2 or ay2 <= by1 or ay1 >= by2)
    
    def _wall_overlap(self, a, b, side):
        ax1, ay1, ax2, ay2 = a.bounds()
        bx1, by1, bx2, by2 = b.bounds()
        
        if side in ("left", "right"):
            return min(ay2, by2) - max(ay1, by1)
        if side in ("top", "bottom"):
            return min(ax2, bx2) - max(ax1, bx1)
        return 0


class StrictOverlapResolver:
    """Prevents critical room overlaps"""
    CLEARANCE = 1.0
    MAX_ITERS = 200
    
    def resolve(self, rooms):
        for iteration in range(self.MAX_ITERS):
            changed = False
            overlaps_found = 0
            
            for i in range(len(rooms)):
                for j in range(i + 1, len(rooms)):
                    a = rooms[i]
                    b = rooms[j]
                    
                    if not self._overlaps(a, b):
                        continue
                    
                    overlaps_found += 1
                    
                    if a.purpose == b.purpose == "circulation":
                        continue
                    
                    if getattr(a, "locked", False) and getattr(b, "locked", False):
                        continue
                    
                    # NEVER separate master bathroom from master bedroom
                    if self._is_master_pair(a, b):
                        continue
                    
                    resolved = self._apply_rules(a, b)
                    if resolved:
                        changed = True
                        continue
                    
                    if self._separate_by_priority(a, b):
                        changed = True
            
            if not changed and overlaps_found == 0:
                return rooms
        
        print(f"OverlapResolver: completed {self.MAX_ITERS} iterations")
        return rooms
    
    def _is_master_pair(self, a: Room, b: Room) -> bool:
        """Check if these are master bedroom and bathroom"""
        if "master" in a.name.lower() and "master" in b.name.lower():
            if {a.purpose, b.purpose} == {"bedroom", "bathroom"}:
                return True
        return False
    
    def _is_adjacent(self, a: Room, b: Room, tol=1.0) -> bool:
        """Check if two rooms are adjacent (sharing a wall)"""
        ax1, ay1, ax2, ay2 = a.bounds()
        bx1, by1, bx2, by2 = b.bounds()
        
        if abs(ax2 - bx1) < tol or abs(ax1 - bx2) < tol:
            return min(ay2, by2) - max(ay1, by1) > 1.0
        
        if abs(ay2 - by1) < tol or abs(ay1 - by2) < tol:
            return min(ax2, bx2) - max(ax1, bx1) > 1.0
        
        return False
    
    def _apply_rules(self, a: Room, b: Room) -> bool:
        # Kitchen must not be overlapped by bedroom
        if a.purpose == "kitchen" and b.purpose == "bedroom":
            b.y = a.y + a.height + self.CLEARANCE
            return True
        if b.purpose == "kitchen" and a.purpose == "bedroom":
            a.y = b.y + b.height + self.CLEARANCE
            return True
        
        # Living room priority
        if a.purpose == "living":
            if not getattr(a, "locked", False):
                self._push_away(b, a)
            return True
        if b.purpose == "living":
            if not getattr(b, "locked", False):
                self._push_away(a, b)
            return True
        
        # Kitchen priority
        if a.purpose == "kitchen":
            self._push_away(b, a)
            return True
        if b.purpose == "kitchen":
            self._push_away(a, b)
            return True
        
        # Foyer priority
        if "foyer" in a.name.lower():
            self._push_away(b, a)
            return True
        if "foyer" in b.name.lower():
            self._push_away(a, b)
            return True
        
        return False
    
    def _separate_by_priority(self, a: Room, b: Room) -> bool:
        if getattr(a, "locked", False):
            return self._push_away(b, a)
        if getattr(b, "locked", False):
            return self._push_away(a, b)
        
        if a.priority > b.priority:
            return self._push_away(b, a)
        elif b.priority > a.priority:
            return self._push_away(a, b)
        
        if a.area() <= b.area():
            return self._push_away(a, b)
        else:
            return self._push_away(b, a)
    
    def _push_away(self, mover: Room, anchor: Room) -> bool:
        ax1, ay1, ax2, ay2 = anchor.bounds()
        mx1, my1, mx2, my2 = mover.bounds()
        
        dx_left = ax2 - mx1
        dx_right = mx2 - ax1
        dy_down = ay2 - my1
        dy_up = my2 - ay1
        
        min_overlap = min(dx_left, dx_right, dy_down, dy_up)
        
        if min_overlap == dx_left:
            mover.x = ax2 + self.CLEARANCE
        elif min_overlap == dx_right:
            mover.x = ax1 - mover.width - self.CLEARANCE
        elif min_overlap == dy_down:
            mover.y = ay2 + self.CLEARANCE
        else:
            mover.y = ay1 - mover.height - self.CLEARANCE
        
        return True
    
    def _overlaps(self, a: Room, b: Room) -> bool:
        ax1, ay1, ax2, ay2 = a.bounds()
        bx1, by1, bx2, by2 = b.bounds()
        return not (ax2 <= bx1 or ax1 >= bx2 or ay2 <= by1 or ay1 >= by2)


class CorridorInserter:
    def insert(self, rooms):
        room_map = {r.room_id: r for r in rooms}
        corridors = []
        seen_pairs = set()
        
        living_room = next((r for r in rooms if r.purpose == "living"), None)
        master_bed = next((r for r in rooms if r.purpose == "bedroom" and "master" in r.name.lower()), None)
        
        if living_room and master_bed:
            corridors.append(Room.make_corridor(living_room, master_bed, width=5))
        
        for room in rooms:
            for edge in room.adjacency:
                if edge["type"] == "near":
                    continue
                
                target = room_map.get(edge["to"])
                if not target:
                    continue
                
                if self._is_adjacent(room, target):
                    continue
                
                pair = tuple(sorted([room.room_id, target.room_id]))
                if pair in seen_pairs:
                    continue
                
                seen_pairs.add(pair)
                corridors.append(Room.make_corridor(room, target))
        
        return rooms + corridors
    
    def _is_adjacent(self, a: Room, b: Room, tol=1.0) -> bool:
        ax1, ay1, ax2, ay2 = a.bounds()
        bx1, by1, bx2, by2 = b.bounds()
        
        if abs(ax2 - bx1) < tol or abs(ax1 - bx2) < tol:
            return min(ay2, by2) - max(ay1, by1) > 1.0
        
        if abs(ay2 - by1) < tol or abs(ay1 - by2) < tol:
            return min(ax2, bx2) - max(ax1, bx1) > 1.0
        
        return False


class CorridorMerger:
    def merge(self, rooms: List[Room]) -> List[Room]:
        corridors = [r for r in rooms if r.purpose == "circulation"]
        others = [r for r in rooms if r.purpose != "circulation"]
        
        merged = []
        
        while corridors:
            base = corridors.pop(0)
            bx1, by1, bx2, by2 = base.bounds()
            
            i = 0
            while i < len(corridors):
                c = corridors[i]
                if self._can_merge(base, c):
                    cx1, cy1, cx2, cy2 = c.bounds()
                    bx1 = min(bx1, cx1)
                    by1 = min(by1, cy1)
                    bx2 = max(bx2, cx2)
                    by2 = max(by2, cy2)
                    corridors.pop(i)
                else:
                    i += 1
            
            base.x = bx1
            base.y = by1
            base.width = bx2 - bx1
            base.height = by2 - by1
            base.width = max(base.width, 4)
            base.height = max(base.height, 4)
            merged.append(base)
        
        return others + merged
    
    def _can_merge(self, a: Room, b: Room, tol=0.5):
        if a.purpose != "circulation" or b.purpose != "circulation":
            return False
        
        ax1, ay1, ax2, ay2 = a.bounds()
        bx1, by1, bx2, by2 = b.bounds()
        
        if abs(ax1 - bx1) < tol and abs(ax2 - bx2) < tol:
            return not (ay2 < by1 or by2 < ay1)
        
        if abs(ay1 - by1) < tol and abs(ay2 - by2) < tol:
            return not (ax2 < bx1 or bx2 < ax1)
        
        return False


@dataclass
class Door:
    from_room: str
    to_room: str
    x: float
    y: float
    orientation: str


class DoorPlacer:
    def place(self, rooms: List[Room]) -> List[Door]:
        doors = []
        
        for i, a in enumerate(rooms):
            for b in rooms[i+1:]:
                wall = self._shared_wall(a, b)
                if not wall:
                    continue
                
                orientation, x, y = wall
                
                if a.zone == b.zone == "private":
                    if not (a.purpose == "bathroom" or b.purpose == "bathroom"):
                        continue
                
                if a.purpose == b.purpose == "circulation":
                    continue
                
                doors.append(
                    Door(
                        from_room=a.room_id,
                        to_room=b.room_id,
                        x=x,
                        y=y,
                        orientation=orientation
                    )
                )
        
        return doors
    
    def _shared_wall(self, a: Room, b: Room, tol=0.2):
        ax1, ay1, ax2, ay2 = a.bounds()
        bx1, by1, bx2, by2 = b.bounds()
        
        if abs(ax2 - bx1) < tol:
            overlap = min(ay2, by2) - max(ay1, by1)
            if overlap > 2:
                return "vertical", ax2, max(ay1, by1) + overlap / 2
        
        if abs(ax1 - bx2) < tol:
            overlap = min(ay2, by2) - max(ay1, by1)
            if overlap > 2:
                return "vertical", ax1, max(ay1, by1) + overlap / 2
        
        if abs(ay2 - by1) < tol:
            overlap = min(ax2, bx2) - max(ax1, bx1)
            if overlap > 2:
                return "horizontal", max(ax1, bx1) + overlap / 2, ay2
        
        if abs(ay1 - by2) < tol:
            overlap = min(ax2, bx2) - max(ax1, bx1)
            if overlap > 2:
                return "horizontal", max(ax1, bx1) + overlap / 2, ay1
        
        return None


def can_expand(room, rooms, bounds, dx=0, dy=0, clearance=0.5, allow_into_circulation=True):
    test = Room(
        room_id=room.room_id,
        name=room.name,
        purpose=room.purpose,
        width=room.width + dx,
        height=room.height + dy,
        zone=room.zone,
        adjacency=room.adjacency,
        x=room.x,
        y=room.y
    )
    
    bx1, by1, bx2, by2 = bounds
    x1, y1, x2, y2 = test.bounds()
    
    if x1 < bx1 or y1 < by1 or x2 > bx2 or y2 > by2:
        return False
    
    for r in rooms:
        if r is room:
            continue
        
        if allow_into_circulation and r.purpose == "circulation":
            continue
        
        rx1, ry1, rx2, ry2 = r.bounds()
        
        if not (x2 + clearance <= rx1 or 
                x1 >= rx2 + clearance or 
                y2 + clearance <= ry1 or 
                y1 >= ry2 + clearance):
            return False
    
    return True


def clamp_to_bounds(room, bounds):
    xmin, ymin, xmax, ymax = bounds
    room.x = max(xmin, min(room.x, xmax - room.width))
    room.y = max(ymin, min(room.y, ymax - room.height))

class LayoutQualityScorer:
    def score(self, rooms: List[Room], doors: List[Door]) -> int:
        score = 100

        living = next((r for r in rooms if r.purpose == "living"), None)
        corridors = [r for r in rooms if r.purpose == "circulation"]
        bedrooms = [r for r in rooms if r.purpose == "bedroom"]
        bathrooms = [r for r in rooms if r.purpose == "bathroom"]
        kitchen = next((r for r in rooms if r.purpose == "kitchen"), None)

        # 1️⃣ Living as corridor hub (BAD)
        if living:
            living_doors = [
                d for d in doors
                if d.from_room == living.room_id or d.to_room == living.room_id
            ]

            if len(living_doors) > 2:
                score -= (len(living_doors) - 2) * 10

        # 2️⃣ Bedroom–Kitchen adjacency (BAD)
        if kitchen:
            for bed in bedrooms:
                if self._shares_wall(kitchen, bed):
                    score -= 15

        # 3️⃣ Bathroom opening into living (BAD)
        if living:
            for bath in bathrooms:
                if self._shares_wall(living, bath):
                    score -= 10

        # 4️⃣ Corridor fragmentation
        if len(corridors) > 3:
            score -= (len(corridors) - 3) * 5

        # 5️⃣ Compactness bonus
        score += max(0, 10 - len(rooms))

        return max(score, 0)

    def _shares_wall(self, a: Room, b: Room, tol=0.5) -> bool:
        ax1, ay1, ax2, ay2 = a.bounds()
        bx1, by1, bx2, by2 = b.bounds()

        if abs(ax2 - bx1) < tol or abs(ax1 - bx2) < tol:
            return min(ay2, by2) - max(ay1, by1) > 2

        if abs(ay2 - by1) < tol or abs(ay1 - by2) < tol:
            return min(ax2, bx2) - max(ax1, bx1) > 2

        return False
def polish_layout(rooms: List[Room]):
    """Tiny nudges only – no major movement"""
    for r in rooms:
        # straighten corridors
        if r.purpose == "circulation":
            r.x = round(r.x)
            r.y = round(r.y)

        # align bathrooms vertically (plumbing logic)
        if r.purpose == "bathroom":
            r.x = round(r.x / 2) * 2

def generate_layout(plan_json: dict):
    """Enhanced layout generation pipeline"""
    
    rooms = [
        Room(
            room_id=r["room_id"],
            name=r["name"],
            purpose=r["purpose"],
            width=r["dimensions_ft"][0],
            height=r["dimensions_ft"][1],
            zone=r["placement_intent"]["zone"],
            adjacency=r.get("adjacency_edges", [])
        )
        for r in plan_json["rooms"]
    ]
    
    placer = ImprovedZonePlacer(
        plot_w=40,
        plot_h=40,
        setbacks={"front": 5, "rear": 5, "left": 5, "right": 5}
    )
    
    bounds = (5, 5, 35, 35)
    
    print("Phase 1: Strategic placement")
    rooms = placer.place(rooms)
    
    print("Phase 2: Enforce adjacencies")
    rooms = StrictAdjacencyRefiner().refine(rooms, bounds, iterations=3)
    
    print("Phase 3: Resolve overlaps")
    rooms = StrictOverlapResolver().resolve(rooms)
    
    print("Phase 4: Re-enforce critical adjacencies")
    rooms = StrictAdjacencyRefiner().refine(rooms, bounds, iterations=2)
    
    living_room = next((r for r in rooms if r.purpose == "living"), None)
    kitchen = next((r for r in rooms if r.purpose == "kitchen"), None)
    foyer = next((r for r in rooms if "foyer" in r.name.lower()), None)
    
    if living_room:
        living_room.locked = True
    if kitchen:
        kitchen.locked = True
    if foyer:
        foyer.locked = True
    
    print("Phase 5: Corridor insertion")
    rooms = CorridorInserter().insert(rooms)
    rooms = StrictOverlapResolver().resolve(rooms)
    rooms = CorridorMerger().merge(rooms)
    
    for r in rooms:
        if r.purpose == "circulation":
            r.locked = True
    
    print("Phase 6: Final adjacency pass")
    rooms = StrictAdjacencyRefiner().refine(rooms, bounds, iterations=1)
    
    print("Phase 7: Door placement")
    doors = DoorPlacer().place(rooms)
    
    print("Phase 8: Intelligent room expansion with circulation preservation")
    RESIZE_STEP = 0.5
    
    for r in sorted(rooms, key=lambda x: x.priority, reverse=True):
        if r.purpose in ("bathroom", "circulation"):
            continue
        
        if r.purpose == "living":
            max_steps = 30
        elif r.purpose == "kitchen":
            max_steps = 18
        elif r.purpose == "bedroom" and "master" in r.name.lower():
            max_steps = 20
        elif r.purpose == "bedroom":
            max_steps = 15
        else:
            max_steps = 10
        
        for _ in range(max_steps):
            if can_expand(r, rooms, bounds, dx=RESIZE_STEP, allow_into_circulation=False):
                r.width += RESIZE_STEP
            else:
                break
        
        for _ in range(max_steps):
            if can_expand(r, rooms, bounds, dy=RESIZE_STEP, allow_into_circulation=False):
                r.height += RESIZE_STEP
            else:
                break
    
    for r in rooms:
        clamp_to_bounds(r, bounds)
    
    print("Layout generation complete!")
    
    scorer = LayoutQualityScorer()
    polish_layout(rooms)
    quality_score = scorer.score(rooms, doors)

    

    return {
        "bounds": {
            "xmin": bounds[0],
            "ymin": bounds[1],
            "xmax": bounds[2],
            "ymax": bounds[3]
        },
        "quality_score": quality_score,
        "rooms": [
            {
                "room_id": r.room_id,
                "name": r.name,
                "purpose": r.purpose,
                "zone": r.zone,
                "x": r.x,
                "y": r.y,
                "width": r.width,
                "height": r.height
            }
            for r in rooms
        ],
        "doors": [
            {
                "from": d.from_room,
                "to": d.to_room,
                "x": d.x,
                "y": d.y,
                "orientation": d.orientation
            }
            for d in doors
        ]
    }



def save_layout_to_db(project_id: str, layout: dict):
    conn = sqlite3.connect("projectsData.db")
    cur = conn.cursor()
    cur.execute(
        "UPDATE projects SET Layout6 = ? WHERE project_id = ?",
        (json.dumps(layout, indent=2), project_id)
    )
    conn.commit()
    conn.close()
    print(f"Layout saved to Layout6 for project {project_id}")


if __name__ == "__main__":
    import sqlite3
    
    PROJECT_ID = "PROJ_20260125_090051"
    
    conn = sqlite3.connect("projectsData.db")
    cur = conn.cursor()
    cur.execute(
        "SELECT Planned FROM projects WHERE project_id = ?",
        (PROJECT_ID,)
    )
    row = cur.fetchone()
    conn.close()
    
    if not row:
        raise ValueError("Project not found or no Planned data")
    
    planned_output = json.loads(row[0])
    
    plan_json = None
    for p in planned_output["plans"]:
        if p["plan_id"] == "plan_1":
            plan_json = p
            break
    
    if not plan_json:
        raise ValueError("plan_1 not found")
    
    layout = generate_layout(plan_json)
    
    save_layout_to_db(PROJECT_ID, layout)
    
    print("\nLayout generated and saved to database.")
    print(f"Total rooms: {len(layout['rooms'])}")
    print(f"Total doors: {len(layout['doors'])}")