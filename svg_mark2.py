import json
import sqlite3
from envelope_builder_mark2 import build_envelope, WallSegment

OUTER_WALL_STROKE = 0.6
INNER_WALL_STROKE = 0.3

SVG_SIZE = 600
VIEWBOX_SIZE = 50

ROOM_STROKE = 0.25
CORRIDOR_STROKE = 0.2
DOOR_RADIUS = 0.4


def load_layout_from_db(project_id: str, db_path="projectsData.db") -> dict:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute(
        "SELECT Layout6 FROM projects WHERE project_id = ?",
        (project_id,)
    )
    row = cur.fetchone()
    conn.close()

    if not row or not row[0]:
        raise ValueError("No layout found for project")

    return json.loads(row[0])


def generate_svg(layout: dict) -> str:
    svg = [
        f'<svg width="{SVG_SIZE}" height="{SVG_SIZE}" '
        f'viewBox="0 0 {VIEWBOX_SIZE} {VIEWBOX_SIZE}" '
        f'xmlns="http://www.w3.org/2000/svg">'
    ]

    # BUILD ENVELOPE 
    walls = build_envelope(layout)

    # outer walls first 
    for w in walls:
        if w.kind != "outer":
            continue
        svg.append(
            f'<line x1="{w.x1}" y1="{w.y1}" '
            f'x2="{w.x2}" y2="{w.y2}" '
            f'stroke="black" stroke-width="{OUTER_WALL_STROKE}" '
            f'stroke-linecap="butt" stroke-linejoin="miter"/>'
        )

    # inner walls on top 
    for w in walls:
        if w.kind != "inner":
            continue
        svg.append(
            f'<line x1="{w.x1}" y1="{w.y1}" '
            f'x2="{w.x2}" y2="{w.y2}" '
            f'stroke="#333" opacity="0.5" stroke-width="{INNER_WALL_STROKE}" '
            f'stroke-linecap="butt" stroke-linejoin="miter"/>'
        )

    # OPTIONAL: draw room labels only
    for r in layout["rooms"]:
        if r["purpose"] == "circulation":
            continue
        cx = r["x"] + r["width"] / 2
        cy = r["y"] + r["height"] / 2

        svg.append(
            f'<text x="{cx}" y="{cy}" '
            f'font-size="1.1" '
            f'text-anchor="middle" '
            f'dominant-baseline="middle" '
            f'fill="#333">'
            f'{r["name"]}</text>'
        )
    print(
    "OUTER:",
    sum(1 for w in walls if w.kind == "outer"),
    "INNER:",
    sum(1 for w in walls if w.kind == "inner")
)


    svg.append("</svg>")
    return "\n".join(svg)     


def save_svg(svg: str, output_path="output_Layout11_testing layout6_mark2_output.svg"):
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(svg)

#newly add for testing mark1(ui update)
def layout_to_svg(layout: dict) -> str:
    return generate_svg(layout)

if __name__ == "__main__":
    PROJECT_ID = "PROJ_20260125_090051" 

    layout = load_layout_from_db(PROJECT_ID)
    svg = generate_svg(layout)
    save_svg(svg)

    print("SVG generated: output_layout1.svg")
