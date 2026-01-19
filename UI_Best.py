import streamlit as st
import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, Any
import os

def init_db():
    """Initialize SQLite database"""
    conn = sqlite3.connect('projectsData.db')
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            project_id TEXT PRIMARY KEY,
            project_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            data_json TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()

def save_project(project_data: Dict[str, Any]) -> str:
    """Save project to database handling different schemas"""
    conn = sqlite3.connect('projectsData.db')
    cursor = conn.cursor()

    project_id = project_data.get('project_id', f"PROJ_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

    # 1. Detect columns in the existing table
    cursor.execute("PRAGMA table_info(projects)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    # 2. Prepare data
    insert_data = {
        'project_id': project_id,
        'project_name': project_data.get('project_name', 'Untitled'),
        'updated_at': datetime.now().isoformat(),
        'data_json': json.dumps(project_data, indent=2, default=str)
    }

    # 3. Handle Legacy Columns (city_region, num_floors) if they exist
    if 'city_region' in existing_columns:
        insert_data['city_region'] = project_data.get('city_region', 'Unknown')

    if 'num_floors' in existing_columns:
        # Convert string "Ground + 1" to integer for DB column if needed
        floors_val = project_data.get('num_floors', 1)
        if isinstance(floors_val, str):
            if "Ground" in floors_val:
                if "+" in floors_val:
                    try:
                        floors_val = 1 + int(floors_val.split("+")[1])
                    except:
                        floors_val = 2
                else:
                    floors_val = 1
            else:
                floors_val = 1
        insert_data['num_floors'] = int(floors_val)

    # 4. Construct Dynamic Query
    columns = list(insert_data.keys())
    placeholders = ",".join(["?"] * len(columns))
    col_str = ",".join(columns)
    values = [insert_data[col] for col in columns]

    query = f"INSERT OR REPLACE INTO projects ({col_str}) VALUES ({placeholders})"

    cursor.execute(query, values)
    conn.commit()
    conn.close()
    return project_id

def load_all_projects() -> list:
    """Load all projects from database"""
    conn = sqlite3.connect('projectsData.db')
    cursor = conn.cursor()

    cursor.execute("SELECT project_id, project_name, created_at FROM projects ORDER BY created_at DESC")
    projects = cursor.fetchall()
    conn.close()

    return projects

def load_project_data(project_id: str) -> Optional[Dict[str, Any]]:
    """Load specific project data"""
    conn = sqlite3.connect('projectsData.db')
    cursor = conn.cursor()

    cursor.execute("SELECT data_json FROM projects WHERE project_id = ?", (project_id,))
    result = cursor.fetchone()
    conn.close()

    if result:
        return json.loads(result[0])
    return None

st.set_page_config(
    page_title="Residential Design Planning",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

init_db()

# Initialize session state
if 'current_page' not in st.session_state:
    st.session_state.current_page = 'home'
if 'project_data' not in st.session_state:
    st.session_state.project_data = {}
if 'editing_project_id' not in st.session_state:
    st.session_state.editing_project_id = None

# HOME PAGE - PROJECT LIST & CREATE
def page_home():
    st.title("🏗️ Residential Design Planning System")

    col1, col2 = st.columns([3, 1])

    with col1:
        st.markdown("### Your Projects")

    with col2:
        if st.button("➕ New Project", use_container_width=True):
            st.session_state.current_page = 'form'
            st.session_state.project_data = {}
            st.session_state.editing_project_id = None
            st.rerun()

    # Load and display projects
    projects = load_all_projects()

    if not projects:
        st.info("📭 No projects yet. Create one to get started!")
    else:
        for project_id, project_name, created_at in projects:
            with st.container():
                col1, col2, col3 = st.columns([3, 1, 1])

                with col1:
                    st.markdown(f"**{project_name}**")
                    st.caption(f"ID: {project_id} | Created: {created_at}")

                with col2:
                    if st.button("✏️ Edit", key=f"edit_{project_id}"):
                        st.session_state.current_page = 'form'
                        st.session_state.project_data = load_project_data(project_id) or {}
                        st.session_state.editing_project_id = project_id
                        st.rerun()

                with col3:
                    if st.button("👁️ View", key=f"view_{project_id}"):
                        st.session_state.current_page = 'view'
                        st.session_state.editing_project_id = project_id
                        st.rerun()

                st.divider()

# FORM PAGE - COLLECT INPUTS
def page_form():
    st.title("📋 Enter Project Details")

    # Back button
    if st.button("← Back to Projects"):
        st.session_state.current_page = 'home'
        st.rerun()

    st.divider()

    # Initialize form data
    form_data = st.session_state.project_data.copy()

    # SCREEN 1: BASIC PROJECT INFO
    st.subheader("Screen 1: Basic Project Info")

    form_data['project_name'] = st.text_input(
        "Project Name",
        value=form_data.get('project_name', ''),
        placeholder="e.g., Dream Villa 2024"
    )

    form_data['city_region'] = st.selectbox(
        "City/Region",
        options=["Noida", "Delhi", "Bangalore", "Mumbai", "Gurgaon", "Other"],
        index=0 if form_data.get('city_region') == "Noida" else (
            1 if form_data.get('city_region') == "Delhi" else 0
        )
    )

    if form_data['city_region'] == "Other":
        form_data['city_region_custom'] = st.text_input(
            "Specify City/Region",
            value=form_data.get('city_region_custom', '')
        )
        form_data['city_region'] = form_data['city_region_custom']

    form_data['num_floors'] = st.select_slider(
        "Number of Floors",
        options=["Ground", "Ground + 1", "Ground + 2", "Ground + 3"],
        value=form_data.get('num_floors', "Ground + 1")
    )

    st.divider()

    # SCREEN 2: PLOT DETAILS
    st.subheader("Screen 2: Plot Details")

    col1, col2 = st.columns(2)

    with col1:
        form_data['plot_length_ft'] = st.number_input(
            "Plot Length (feet)",
            min_value=10.0,
            value=float(form_data.get('plot_length_ft', 50)),
            step=0.5
        )

    with col2:
        form_data['plot_breadth_ft'] = st.number_input(
            "Plot Breadth (feet)",
            min_value=10.0,
            value=float(form_data.get('plot_breadth_ft', 40)),
            step=0.5
        )

    # Auto-calculate plot area
    plot_area = form_data['plot_length_ft'] * form_data['plot_breadth_ft']
    st.info(f"📐 Plot Area: {plot_area:,.0f} sq ft")
    form_data['plot_area_sqft'] = plot_area

    form_data['plot_type'] = st.radio(
        "Plot Type",
        options=["Center", "Corner", "T-point"],
        index=0 if form_data.get('plot_type') == "Center" else (
            1 if form_data.get('plot_type') == "Corner" else 2
        ),
        horizontal=True
    )

    st.markdown("**Road Frontage (Select all that apply)**")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        form_data['road_front'] = st.checkbox("Front", value=form_data.get('road_front', True))
    with col2:
        form_data['road_left'] = st.checkbox("Left", value=form_data.get('road_left', False))
    with col3:
        form_data['road_right'] = st.checkbox("Right", value=form_data.get('road_right', False))
    with col4:
        form_data['road_back'] = st.checkbox("Back", value=form_data.get('road_back', False))

    form_data['road_sides'] = []
    if form_data['road_front']: form_data['road_sides'].append("Front")
    if form_data['road_left']: form_data['road_sides'].append("Left")
    if form_data['road_right']: form_data['road_sides'].append("Right")
    if form_data['road_back']: form_data['road_sides'].append("Back")

    st.divider()

    # SCREEN 3: ROOMS & LAYOUT (IMPROVED)
    st.subheader("Screen 3: Rooms & Configuration")

    # Ground floor parking toggle
    form_data['ground_parking_only'] = st.checkbox(
        "Ground Floor = Parking Only",
        value=form_data.get('ground_parking_only', False),
        help="Check if ground floor is for parking, residential from first floor"
    )

    # Parse floor count
    num_floors_str = form_data['num_floors']
    if num_floors_str == "Ground":
        floor_count = 1
    elif num_floors_str == "Ground + 1":
        floor_count = 2
    elif num_floors_str == "Ground + 2":
        floor_count = 3
    elif num_floors_str == "Ground + 3":
        floor_count = 4
    else:
        floor_count = 2

    if 'floors_config' not in form_data:
        form_data['floors_config'] = {}

    # Create tabs for each floor
    floor_labels = ["Ground"] + [f"Floor {i}" for i in range(1, floor_count)]
    floor_tabs = st.tabs(floor_labels)

    for floor_idx, tab in enumerate(floor_tabs):
        floor_name = f"floor_{floor_idx}"

        with tab:
            if form_data['ground_parking_only'] and floor_idx == 0:
                # PARKING ONLY FLOOR
                st.subheader("🅿️ Parking Level")

                col1, col2 = st.columns(2)
                with col1:
                    form_data[f"car_{floor_name}"] = st.number_input(
                        "Car Parking Spaces",
                        min_value=0,
                        max_value=10,
                        value=int(form_data.get(f"car_{floor_name}", 2)),
                        key=f"car_{floor_name}"
                    )
                with col2:
                    form_data[f"bike_{floor_name}"] = st.number_input(
                        "Bike Parking Spaces",
                        min_value=0,
                        max_value=20,
                        value=int(form_data.get(f"bike_{floor_name}", 4)),
                        key=f"bike_{floor_name}"
                    )

            else:
                # RESIDENTIAL FLOOR
                st.subheader("🛏️ Bedrooms")

                bed_count = st.number_input(
                    f"Number of Bedrooms",
                    min_value=0,
                    max_value=8,
                    value=int(form_data.get(f"beds_{floor_name}", 2)),
                    key=f"beds_{floor_name}"
                )

                # Initialize bedroom configs
                if f"bedroom_details_{floor_name}" not in form_data:
                    form_data[f"bedroom_details_{floor_name}"] = {}

                bedroom_details = form_data[f"bedroom_details_{floor_name}"]

                # Dynamic expanders
                for bed_num in range(int(bed_count)):
                    bed_key = f"bed_{bed_num}"

                    if bed_key not in bedroom_details:
                        bedroom_details[bed_key] = {
                            'type': 'Master' if bed_num == 0 else 'Kids',
                            'attached_toilet': bed_num == 0,
                            'dressing': bed_num == 0,
                            'balcony': False
                        }

                    with st.expander(f"Bedroom {bed_num + 1}", expanded=False):
                        bed_col1, bed_col2, bed_col3 = st.columns(3)

                        with bed_col1:
                            bedroom_details[bed_key]['type'] = st.selectbox(
                                "Type",
                                options=["Master", "Kids", "Guest"],
                                index=0 if bedroom_details[bed_key].get('type') == "Master" else (
                                    1 if bedroom_details[bed_key].get('type') == "Kids" else 2
                                ),
                                key=f"type_bed_{floor_name}_{bed_num}"
                            )

                        with bed_col2:
                            bedroom_details[bed_key]['attached_toilet'] = st.checkbox(
                                "Attached Toilet",
                                value=bedroom_details[bed_key].get('attached_toilet', False),
                                key=f"toilet_bed_{floor_name}_{bed_num}"
                            )
                            bedroom_details[bed_key]['dressing'] = st.checkbox(
                                "Dressing",
                                value=bedroom_details[bed_key].get('dressing', False),
                                key=f"dress_bed_{floor_name}_{bed_num}"
                            )

                        with bed_col3:
                            bedroom_details[bed_key]['balcony'] = st.checkbox(
                                "Balcony",
                                value=bedroom_details[bed_key].get('balcony', False),
                                key=f"balc_bed_{floor_name}_{bed_num}"
                            )

                form_data[f"bedroom_details_{floor_name}"] = bedroom_details

                st.divider()

                # LIVING & KITCHEN SECTION
                st.subheader("🏠 Living & Kitchen")

                col1, col2 = st.columns(2)
                with col1:
                    form_data[f"living_{floor_name}"] = st.checkbox(
                        "Living Room",
                        value=form_data.get(f"living_{floor_name}", True),
                        key=f"living_{floor_name}"
                    )

                with col2:
                    form_data[f"kitchen_{floor_name}"] = st.radio(
                        "Kitchen Type",
                        options=["Closed", "Open"],
                        index=0 if form_data.get(f"kitchen_{floor_name}", "Closed") == "Closed" else 1,
                        key=f"kitchen_{floor_name}",
                        horizontal=True
                    )

                st.divider()

                # BATHROOMS & UTILITIES
                st.subheader("🚿 Bathrooms & Utilities")

                col1, col2 = st.columns(2)
                with col1:
                    form_data[f"common_bath_{floor_name}"] = st.number_input(
                        "Common Bathrooms",
                        min_value=1,
                        max_value=5,
                        value=int(form_data.get(f"common_bath_{floor_name}", 1)),
                        key=f"common_bath_{floor_name}"
                    )

                with col2:
                    form_data[f"stair_pos_{floor_name}"] = st.selectbox(
                        "Stair Position",
                        options=["AI Decide", "Front", "Middle", "Side"],
                        index=0,
                        key=f"stair_pos_{floor_name}"
                    )

                # OTHER SPACES
                if floor_idx == 0:
                    st.divider()
                    st.subheader("✨ Other Spaces")

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        form_data["pooja_room"] = st.checkbox(
                            "Pooja Room",
                            value=form_data.get("pooja_room", False),
                            key="pooja_room"
                        )
                    with col2:
                        form_data["study_room"] = st.checkbox(
                            "Study/Office",
                            value=form_data.get("study_room", False),
                            key="study_room"
                        )
                    with col3:
                        form_data["store_room"] = st.checkbox(
                            "Store Room",
                            value=form_data.get("store_room", False),
                            key="store_room"
                        )

    st.divider()

    # SCREEN 4: CLIMATE & OUTDOORS
    st.subheader("Screen 4: Climate & Outdoor Features")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Sun Preferences**")
        form_data['morning_sun_bedrooms'] = st.checkbox(
            "Morning sun in bedrooms",
            value=form_data.get('morning_sun_bedrooms', True)
        )
        form_data['maximize_living_light'] = st.checkbox(
            "Maximize light in living area",
            value=form_data.get('maximize_living_light', True)
        )
        form_data['west_south_insulated'] = st.checkbox(
            "Keep west/south walls insulated",
            value=form_data.get('west_south_insulated', False)
        )

    with col2:
        st.markdown("**Vastu Preference**")
        form_data['vastu_preference'] = st.radio(
            "Vastu Orientation",
            options=["None", "Soft", "Strict"],
            index=0 if form_data.get('vastu_preference') == "None" else (
                1 if form_data.get('vastu_preference') == "Soft" else 2
            ),
            key="vastu_radio"
        )

    col1, col2 = st.columns(2)

    with col1:
        form_data['car_parking'] = st.number_input(
            "Car Parking Spots",
            min_value=0,
            max_value=10,
            value=int(form_data.get('car_parking', 1))
        )

        form_data['bike_parking'] = st.number_input(
            "Bike Parking Spots",
            min_value=0,
            max_value=20,
            value=int(form_data.get('bike_parking', 2))
        )

    with col2:
        form_data['garden_location'] = st.multiselect(
            "Garden/Yard Location",
            options=["Front", "Rear", "Side"],
            default=form_data.get('garden_location', ["Front"])
        )

        form_data['terrace_use'] = st.multiselect(
            "Terrace Usage",
            options=["Open Terrace", "Terrace Garden", "Solar Panels", "Utility"],
            default=form_data.get('terrace_use', ["Open Terrace"])
        )

    st.divider()

    # SCREEN 5: COST & MATERIALS
    st.subheader("Screen 5: Budget & Materials")

    col1, col2 = st.columns(2)

    with col1:
        form_data['budget_per_sqft'] = st.number_input(
            "Budget (₹/sq ft)",
            min_value=500,
            max_value=50000,
            value=int(form_data.get('budget_per_sqft', 2500)),
            step=100
        )

    with col2:
        form_data['quality_tier'] = st.selectbox(
            "Quality Tier",
            options=["Economy", "Standard", "Premium"],
            index=1 if form_data.get('quality_tier') == "Standard" else 0
        )

    col1, col2, col3 = st.columns(3)

    with col1:
        form_data['flooring_type'] = st.selectbox(
            "Flooring",
            options=["Vitrified Tiles", "Marble", "Wooden", "Mix"],
            index=0 if form_data.get('flooring_type') == "Vitrified Tiles" else 0
        )

    with col2:
        form_data['window_type'] = st.selectbox(
            "Windows",
            options=["UPVC", "Aluminum", "Wood"],
            index=1 if form_data.get('window_type') == "Aluminum" else 0
        )

    with col3:
        form_data['door_type'] = st.selectbox(
            "Doors",
            options=["Flush", "Solid Wood", "Mixed"],
            index=1 if form_data.get('door_type') == "Solid Wood" else 0
        )

    st.divider()

    # SCREEN 6: INTERIOR DESIGN (OPTIONAL)
    st.subheader("Screen 6: Interior Design (Optional)")

    form_data['interior_scope'] = st.radio(
        "Interior Design Scope",
        options=["Only Layout", "With Furniture", "Full Interior + Finishes"],
        index=0 if form_data.get('interior_scope') == "Only Layout" else (
            1 if form_data.get('interior_scope') == "With Furniture" else 2
        ),
        horizontal=True
    )

    form_data['interior_style'] = st.multiselect(
        "Interior Style Preference",
        options=["Modern", "Contemporary", "Traditional", "Minimal", "Luxury"],
        default=form_data.get('interior_style', ["Modern"])
    )

    st.divider()

    # SAVE BUTTON
    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        if st.button("💾 Save Project", use_container_width=True, type="primary"):
            if not form_data.get('project_name'):
                st.error("❌ Project name is required!")
            else:
                try:
                    project_id = save_project(form_data)
                    st.success(f"✅ Project saved! ID: {project_id}")
                    st.session_state.current_page = 'home'
                    st.session_state.project_data = {}
                    st.rerun()
                except Exception as e:
                    st.error(f"Save failed: {str(e)}")
                    st.info("Try deleting 'projectsData.db' if issue persists.")

    with col2:
        if st.button("↩️ Cancel", use_container_width=True):
            st.session_state.current_page = 'home'
            st.session_state.project_data = {}
            st.rerun()

    with col3:
        if st.button("📋 Preview JSON", use_container_width=True):
            st.json(form_data)

# VIEW PAGE - DISPLAY SAVED PROJECT
def page_view():
    if st.button("← Back to Projects"):
        st.session_state.current_page = 'home'
        st.rerun()

    project_data = load_project_data(st.session_state.editing_project_id)

    if not project_data:
        st.error("Project not found!")
        return

    st.title(f"📄 {project_data.get('project_name', 'Project Details')}")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("### Project Information")

        info = {
            "Location": project_data.get('city_region', 'N/A'),
            "Floors": project_data.get('num_floors', 'N/A'),
            "Plot Area": f"{project_data.get('plot_area_sqft', 0):,.0f} sq ft",
            "Plot Type": project_data.get('plot_type', 'N/A'),
            "Budget/sqft": f"₹{project_data.get('budget_per_sqft', 0):,}",
            "Quality": project_data.get('quality_tier', 'N/A'),
        }

        for key, value in info.items():
            st.markdown(f"**{key}**: {value}")

    with col2:
        st.markdown("### Quick Stats")
        plot_area = project_data.get('plot_area_sqft', 0)
        budget_per_sqft = project_data.get('budget_per_sqft', 0)
        estimated_total = plot_area * budget_per_sqft

        st.metric("Plot Area", f"{plot_area:,.0f} sq ft")
        st.metric("Est. Budget", f"₹{estimated_total:,.0f}")

    st.divider()

    st.markdown("### All Details (JSON)")
    st.json(project_data)

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        if st.button("✏️ Edit Project", use_container_width=True):
            st.session_state.current_page = 'form'
            st.session_state.project_data = project_data
            st.rerun()

    with col2:
        # Download JSON
        import json
        json_str = json.dumps(project_data, indent=2)
        st.download_button(
            label="⬇️ Download JSON",
            data=json_str,
            file_name=f"{project_data.get('project_name', 'project')}.json",
            mime="application/json",
            use_container_width=True
        )

# PAGE ROUTING
if st.session_state.current_page == 'home':
    page_home()
elif st.session_state.current_page == 'form':
    page_form()
elif st.session_state.current_page == 'view':
    page_view()