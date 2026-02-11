import json
import sqlite3
import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

# def db_connection(project_name: str) -> dict:
#     conn = sqlite3.connect("projectsData.db")
#     cursor = conn.cursor()
#     cursor.execute(
#         "SELECT data_json FROM projects WHERE project_id = ?",
#         (project_name,)
#     )
#     row = cursor.fetchone()
#     conn.close()
    # return json.loads(row[0]) if row else None
    # if not row:
    #     raise ValueError("Project not found")

    # return json.loads(row[0])   # IMPORTANT
def db_connection(project_name: str) -> dict:
    with sqlite3.connect("projectsData.db", timeout=30) as conn:
        # conn.execute("PRAGMA journal_mode=WAL;")
        # conn.execute("PRAGMA synchronous=NORMAL;")

        cursor = conn.cursor()
        cursor.execute(
            "SELECT data_json FROM projects WHERE project_id = ?",
            (project_name,)
        )
        row = cursor.fetchone()

    if not row:
        raise ValueError("Project not found")

    return json.loads(row[0])

import time

def update_planned(project_id: str, plans: dict):
    with sqlite3.connect("projectsData.db", timeout=10) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE projects SET Planned = ? WHERE project_id = ?",
            (json.dumps(plans), project_id)
        )

        if cursor.rowcount == 0:
            raise ValueError(f"Project {project_id} not found")

        conn.commit()

    print(f"Updated Planned for {project_id}")




# CONSTRAINT LAYER
def extract_constraints(site_data: dict) -> dict:
    bedrooms = site_data.get("bedroom_details_floor_0", {})

    attached_toilets = [
        bed_id for bed_id, bed in bedrooms.items()
        if bed.get("attached_toilet") is True
    ]

    return {
        "num_bedrooms": len(bedrooms),
        "attached_toilets": attached_toilets,
        "common_baths": site_data.get("f0_common_bath", 0),
        "kitchen_type": site_data.get("f0_kitchen"),
        "num_floors": site_data.get("num_floors"),
        "morning_sun_bedrooms": site_data.get("morning_sun_bedrooms", False)
    }


# ---------------- VALIDATORS ----------------

def validate_bathrooms(plan: dict, constraints: dict) -> list[str]:
    errors = []

    rooms = {r["room_id"].lower(): r for r in plan["rooms"]}
    bathrooms = [rid for rid in rooms if "bath" in rid]

    required = len(constraints["attached_toilets"]) + constraints["common_baths"]

    if len(bathrooms) < required:
        errors.append(
            f"Bathrooms required: {required}, found: {len(bathrooms)}"
        )
        return errors

    # Check attached toilets
    for bed_id in constraints["attached_toilets"]:
        bed_key = None
        for rid in rooms:
            if bed_id.replace("_", "") in rid.replace("_", ""):
                bed_key = rid
                break

        if not bed_key:
            continue


        attached = False
        for edge in rooms[bed_key].get("adjacency_edges", []):
            if "bath" in edge["to"].lower() and edge["type"] == "attach":
                attached = True

        if not attached:
            errors.append(f"Bedroom {bed_id} missing attached toilet")

    return errors


def validate_kitchen(plan: dict, constraints: dict) -> list[str]:
    if constraints["kitchen_type"] != "Closed":
        return []

    errors = []

    for room in plan["rooms"]:
        if room["room_id"].lower() == "kitchen":
            for edge in room.get("adjacency_edges", []):
                if edge["to"].lower() == "living" and edge["type"] == "attach":
                    errors.append("Closed kitchen attached directly to living")

    return errors


def validate_entry_logic(plan: dict) -> list[str]:
    entry = plan.get("entry_logic", {})
    entry_room = entry.get("entry_room", "").lower()
    buffer_flag = entry.get("buffer_before_living")

    if buffer_flag and entry_room == "living":
        return [
            "If buffer_before_living is true, entry_room must be 'Foyer', not 'Living'"
        ]

    return []


def validate_morning_sun(plan: dict, constraints: dict) -> list[str]:
    if not constraints["morning_sun_bedrooms"]:
        return []

    warnings = []# was returning errors but morning sun is a preference  #error[]
    for room in plan["rooms"]:
        if room["room_id"].lower().startswith("bed"):
            if room.get("orientation") not in ("east", "north"):
                warnings.append(# error.append(
                    f"Bedroom {room['room_id']} violates morning sun preference"
                )
    return warnings #error

def validate_foyer(plan: dict) -> list[str]:
    entry = plan.get("entry_logic", {})
    if not entry.get("buffer_before_living"):
        return []

    rooms = [r["room_id"].lower() for r in plan["rooms"]]
    if not any("foyer" in r for r in rooms):
        return ["buffer_before_living is true but no Foyer room exists"]

    return []

def validate_plan(plan: dict, constraints: dict) -> tuple[list[str], list[str]]:
    fatal_errors = []
    warnings = []

    fatal_errors += validate_bathrooms(plan, constraints)
    fatal_errors += validate_kitchen(plan, constraints)
    fatal_errors += validate_entry_logic(plan)
    fatal_errors += validate_foyer(plan)
    warnings += validate_morning_sun(plan, constraints)

    return fatal_errors, warnings


SYSTEM_PROMPT = """
You are an architectural layout planner AI whose output is consumed directly
by an automated geometric layout engine.

Your responsibility is to convert structured site data into deterministic,
machine-readable residential layout plans.

ABSOLUTE RULES:
- Output VALID JSON ONLY (no markdown, no comments, no explanations)
- Every plan must be drawable without human interpretation
- Use only the information provided in SITE_DATA
- All geometry must fit within plot and setback constraints

YOU MUST:
- Respect plot dimensions, road sides, plot type, and setbacks
- Produce layout-engine-consumable geometry and graphs
- Explicitly encode adjacency, circulation, zoning, and placement intent
- Ensure ventilation and lighting logic is spatially feasible

YOU MUST NOT:
- Invent dimensions, floors, or plot properties
- Output SVG, HTML, ASCII diagrams, or natural language explanations
- Use vague spatial phrases without structured coordinates or intent

"""

PLANNER_INSTRUCTION = """
Generate {N_PLANS} DISTINCT residential blueprint layout plans.

Each plan MUST be structurally different and independently drawable.

========================
REQUIRED PLAN STRUCTURE
========================

Each plan must include the following TOP-LEVEL fields:

- plan_id
- planning_concept
- geometry
- entry_logic
- circulation_graph
- rooms
- ventilation_strategy
- assumptions
- validation
- layout_engine_contract

------------------------
1. geometry (MANDATORY)
------------------------
Define numeric build constraints:

- origin (south_west)
- plot_boundary_ft {width, depth}
- setbacks_ft {front, rear, left, right}
- buildable_rectangle_ft {x, y, width, depth}

------------------------
2. entry_logic (MANDATORY)
------------------------
- road_side
- entry_room
- buffer_before_living (true/false)

------------------------
3. circulation_graph (MANDATORY)
------------------------
Define circulation as a graph, NOT prose.

Fields:
- entry
- type (centralized | corridor | hybrid)
- paths (ordered room_id sequences)

------------------------
4. rooms (MANDATORY)
------------------------
Each room must include ALL of the following:

- room_id (unique, stable identifier)
- name
- purpose
- dimensions_ft [length, width]
- orientation (north | south | east | west)
- placement_intent
- adjacency_edges

placement_intent must include:
- zone (public | semi_private | private | service)
- edge_preference (front | rear | left | right | center)
- road_facing (true/false)
- light_priority (high | medium | low)

adjacency_edges must be a list of:
- to (room_id)
- type (attach | near | separate)

------------------------
5. ventilation_strategy (MANDATORY)
------------------------
Structured explanation of cross-ventilation logic
referencing room_ids and orientations.

------------------------
6. validation (MANDATORY)
------------------------
Self-check flags (true/false):

- area_within_limits
- no_direct_toilet_entry
- adjacency_rules_respected
- circulation_complete
- ventilation_feasible

------------------------
7. layout_engine_contract (MANDATORY)
------------------------
Defines how the layout engine should consume this plan:

- units ("ft")
- coordinate_system ("cartesian_2d")
- origin ("south_west")
- allow_room_rotation (true/false)
- allow_room_resize_within_ft (numeric tolerance)

========================
STRUCTURAL DIVERSITY RULES
========================

Each plan MUST differ from the others by AT LEAST ONE of:

- adjacency graph topology
- public/private zoning arrangement
- circulation type
- openness between living, dining, and kitchen

Reusing the same adjacency structure across plans is FORBIDDEN.

========================
OUTPUT FORMAT
========================

Return a single JSON object with:

{
  "plans": [ ... ]
}

No additional keys.
No prose.
No explanations.

"""

class GroqClient:
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not found")

        self.client = Groq(api_key=api_key)
        self.model = "llama-3.3-70b-versatile"
    def generate_blueprint_plans(self, site_data: dict, n_plans: int = 1) -> dict:
        constraints = extract_constraints(site_data)


        constraint_block = f"""
HARD CONSTRAINTS (NON-NEGOTIABLE):

- Bedrooms required: {constraints["num_bedrooms"]}
- Bedrooms with attached toilets: {constraints["attached_toilets"]}
- Common bathrooms required: {constraints["common_baths"]}
- Kitchen type: {constraints["kitchen_type"]}
- Floors: {constraints["num_floors"]}
- Morning sun bedrooms: {constraints["morning_sun_bedrooms"]}

Violating ANY constraint makes the plan INVALID.
"""
        repair_note = getattr(self, "extra_repair_instruction", "")

        required_rooms_block = f"""
REQUIRED ROOMS (MUST EXIST AS SEPARATE ROOM OBJECTS):

- Living room
- Kitchen
- Bedrooms: {constraints["num_bedrooms"]}
- Bathrooms (TOTAL): {len(constraints["attached_toilets"]) + constraints["common_baths"]}
- Foyer (REQUIRED if buffer_before_living is true)

ENTRY RULE (MANDATORY):

- If buffer_before_living = true:
    - entry_room MUST be "Foyer"
    - A "Foyer" room MUST exist
- If entry_room = "Living":
    - buffer_before_living MUST be false

Bathroom rules:
- One bathroom MUST be attached to each of these bedrooms: {constraints["attached_toilets"]}
- Remaining bathrooms are COMMON bathrooms
- Common bathrooms must NOT be attached to any bedroom
"""

        instruction = (
            constraint_block + 
            required_rooms_block +
            PLANNER_INSTRUCTION.replace("{N_PLANS}", str(n_plans)) +
            repair_note 
        )

        user_prompt = f"""
SITE_DATA:
{json.dumps(site_data, indent=2)}
"""

        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0.2,
            max_tokens=2000,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "assistant", "content": instruction},
                {"role": "user", "content": user_prompt}
            ]
        )

        return json.loads(response.choices[0].message.content)

def build_repair_instruction(errors: list[str]) -> str:
    bullet_errors = "\n".join(f"- {e}" for e in errors)

    return f"""
PREVIOUS PLAN WAS INVALID AND REJECTED BY A RULE ENGINE.

You MUST FIX the following violations in the next output:

{bullet_errors}

MANDATORY FIXES:
- Generate EXACTLY the required number of bathroom rooms.
- Bathrooms must be separate room objects, not implied.
- One bathroom must be attached to the master bedroom.
- One bathroom must be a common bathroom.
- Do NOT attach a closed kitchen directly to the living room.
- Do NOT repeat any listed violation.

All other constraints still apply.
"""


if __name__ == "__main__":
    project_id = "PROJ_20260125_090051"

    site_data = db_connection(project_id)
    planner = GroqClient()
    constraints = extract_constraints(site_data)

    MAX_RETRIES = 5
    last_errors = None
    repair_note = ""

    for attempt in range(1, MAX_RETRIES + 1):
        print(f"\n[Attempt {attempt}] Generating plan...")

        result = planner.generate_blueprint_plans(
            site_data=site_data,
            n_plans=1
        )

        fatal_errors = []
        warnings = []

        for plan in result["plans"]:
            fe, w = validate_plan(plan, constraints)
            fatal_errors += fe
            warnings += w

        if not fatal_errors:
            if warnings:
                print("[WARNINGS]")
                for w in warnings:
                    print(" -", w)

            update_planned(project_id, result)
            print("[SUCCESS] Valid plan saved.")
            print(json.dumps(result, indent=2))
            break

        else:
            print("[INVALID PLAN]")
            for e in fatal_errors:
                print(" -", e)

            last_errors = fatal_errors
            repair_note = build_repair_instruction(fatal_errors)

            planner.extra_repair_instruction = repair_note

    else:
        raise ValueError({
            "status": "FAILED_AFTER_RETRIES",
            "errors": last_errors
        })


    print(json.dumps(result, indent=2))

