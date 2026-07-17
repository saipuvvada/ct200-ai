import pytest
from app.schemas.parser import ParsedNode
from app.models.document import Document
from app.models.node import Node
from app.services.document_service import import_document_version
from app.services.version_matcher import align_document_versions

def test_version_alignment_scenarios(db_session):
    """
    Test version alignment matching across 5 distinct scenarios:
    1. Heading changed slightly (Battery Installation -> Installing Batteries) -> MATCHED/MODIFIED
    2. Body text changed (200 mmHg -> 220 mmHg) -> MODIFIED (retains logical ID)
    3. Moved section (Battery moves from Chapter 3 to Chapter 5) -> MATCHED/MODIFIED (score adjusted by path similarity)
    4. Duplicate subheadings (Warning under Safety vs Warning under Maintenance) -> Match correctly based on path context
    5. New section (Bluetooth Setup) -> NEW status, fresh UUID
    """
    # -------------------------------------------------------------
    # 1. SETUP VERSION 1 DOCUMENT AND HIERARCHY
    # -------------------------------------------------------------
    v1_root = ParsedNode(heading="Document Root", level=0, node_type="heading", order_index=0)
    
    # Chapter 3
    ch3 = ParsedNode(heading="3. Chapter Three", level=1, node_type="heading", order_index=1)
    v1_root.children.append(ch3)
    
    # Target 1: Slightly changed heading (v1: Battery Installation)
    battery_install_v1 = ParsedNode(
        heading="Battery Installation",
        level=2,
        node_type="heading",
        body="Install battery carefully.",
        order_index=2
    )
    ch3.children.append(battery_install_v1)
    
    # Target 2: Body text edit (v1: Pressure: 200 mmHg)
    pressure_v1 = ParsedNode(
        heading="Pressure Guidelines",
        level=2,
        node_type="heading",
        body="Set standard pressure: 200 mmHg.",
        order_index=3
    )
    ch3.children.append(pressure_v1)

    # Target 3: Moved section (v1: Battery details under Chapter 3)
    battery_details_v1 = ParsedNode(
        heading="Battery Details",
        level=2,
        node_type="heading",
        body="Technical specs of battery.",
        order_index=4
    )
    ch3.children.append(battery_details_v1)

    # Target 4: Duplicate subheadings (Warning under Safety)
    safety_v1 = ParsedNode(heading="Safety Guidelines", level=1, node_type="heading", order_index=5)
    v1_root.children.append(safety_v1)
    warning_safety_v1 = ParsedNode(
        heading="Warning",
        level=2,
        node_type="heading",
        body="Wear safety goggles.",
        order_index=6
    )
    safety_v1.children.append(warning_safety_v1)

    # Duplicate subheadings (Warning under Maintenance)
    maint_v1 = ParsedNode(heading="Maintenance Guidelines", level=1, node_type="heading", order_index=7)
    v1_root.children.append(maint_v1)
    warning_maint_v1 = ParsedNode(
        heading="Warning",
        level=2,
        node_type="heading",
        body="Disconnect power before clean.",
        order_index=8
    )
    maint_v1.children.append(warning_maint_v1)

    # Import v1 into DB
    doc_v1 = import_document_version(
        db=db_session,
        filename="manual.pdf",
        version="v1",
        parsed_root=v1_root
    )

    # Capture logical IDs from v1 to verify alignment later
    v1_nodes = db_session.query(Node).filter(Node.document_id == doc_v1.id).all()
    v1_map = {n.heading: n.logical_node_id for n in v1_nodes if n.heading}
    v1_warning_nodes = {n.body: n.logical_node_id for n in v1_nodes if n.heading == "Warning"}

    # -------------------------------------------------------------
    # 2. SETUP VERSION 2 DOCUMENT AND HIERARCHY
    # -------------------------------------------------------------
    v2_root = ParsedNode(heading="Document Root", level=0, node_type="heading", order_index=0)
    
    # Chapter 3 (heading slightly changed, level remains 1)
    ch3_v2 = ParsedNode(heading="3. Chapter Three", level=1, node_type="heading", order_index=1)
    v2_root.children.append(ch3_v2)

    # Scenario 1: Heading changed slightly (Battery Installation -> Installing Batteries)
    battery_install_v2 = ParsedNode(
        heading="Installing Batteries",
        level=2,
        node_type="heading",
        body="Install battery carefully.", # Body unchanged
        order_index=2
    )
    ch3_v2.children.append(battery_install_v2)

    # Scenario 2: Body text edit (200 mmHg -> 220 mmHg)
    pressure_v2 = ParsedNode(
        heading="Pressure Guidelines", # Heading unchanged
        level=2,
        node_type="heading",
        body="Set standard pressure: 220 mmHg.", # Edited body
        order_index=3
    )
    ch3_v2.children.append(pressure_v2)

    # Chapter 5 (added in v2)
    ch5_v2 = ParsedNode(heading="5. Chapter Five", level=1, node_type="heading", order_index=4)
    v2_root.children.append(ch5_v2)

    # Scenario 3: Moved section (Battery Details moved to Chapter 5)
    battery_details_v2 = ParsedNode(
        heading="Battery Details",
        level=2,
        node_type="heading",
        body="Technical specs of battery.",
        order_index=5
    )
    ch5_v2.children.append(battery_details_v2)

    # Scenario 4: Duplicate subheadings (Warning under Safety)
    safety_v2 = ParsedNode(heading="Safety Guidelines", level=1, node_type="heading", order_index=6)
    v2_root.children.append(safety_v2)
    warning_safety_v2 = ParsedNode(
        heading="Warning",
        level=2,
        node_type="heading",
        body="Wear safety goggles.",
        order_index=7
    )
    safety_v2.children.append(warning_safety_v2)

    # Duplicate subheadings (Warning under Maintenance)
    maint_v2 = ParsedNode(heading="Maintenance Guidelines", level=1, node_type="heading", order_index=8)
    v2_root.children.append(maint_v2)
    warning_maint_v2 = ParsedNode(
        heading="Warning",
        level=2,
        node_type="heading",
        body="Disconnect power before clean.",
        order_index=9
    )
    maint_v2.children.append(warning_maint_v2)

    # Scenario 5: Brand new section (Bluetooth Setup)
    bluetooth_v2 = ParsedNode(
        heading="Bluetooth Setup",
        level=2,
        node_type="heading",
        body="Search for devices and connect.",
        order_index=10
    )
    ch5_v2.children.append(bluetooth_v2)

    # -------------------------------------------------------------
    # 3. RUN ALIGNMENT AND TEST ASSERTIONS
    # -------------------------------------------------------------
    logical_map = align_document_versions(
        db=db_session,
        doc_id_v1=doc_v1.id,
        parsed_root_v2=v2_root
    )

    # Import v2 into DB with alignment mapping
    doc_v2 = import_document_version(
        db=db_session,
        filename="manual.pdf",
        version="v2",
        parsed_root=v2_root,
        logical_node_map=logical_map
    )

    # Query imported v2 nodes
    v2_nodes = db_session.query(Node).filter(Node.document_id == doc_v2.id).all()
    v2_by_heading = {n.heading: n for n in v2_nodes if n.heading}

    # ASSERTION 1: Heading changed slightly ("Installing Batteries")
    node_install = v2_by_heading["Installing Batteries"]
    assert node_install.logical_node_id == v1_map["Battery Installation"]
    assert node_install.matching_status == "MODIFIED" # Heading changed, so hash changed
    assert node_install.matched_score > 70.0

    # ASSERTION 2: Body text edit ("Pressure Guidelines")
    node_pressure = v2_by_heading["Pressure Guidelines"]
    assert node_pressure.logical_node_id == v1_map["Pressure Guidelines"]
    assert node_pressure.matching_status == "MODIFIED" # Body changed, so hash changed
    assert 90.0 < node_pressure.matched_score < 100.0 # Heading, path, type all match perfectly, only body has minor diff

    # ASSERTION 3: Moved section ("Battery Details" moved from Ch 3 to Ch 5)
    # The heading & body match perfectly, only the path changed. The score is still above 70%.
    node_moved = v2_by_heading["Battery Details"]
    assert node_moved.logical_node_id == v1_map["Battery Details"]
    assert node_moved.matching_status == "MATCHED" # Content hash didn't change (only path changed)
    assert node_moved.matched_score > 70.0

    # ASSERTION 4: Duplicate subheadings ("Warning" nodes)
    # They should align to their corresponding parents correctly
    v2_warning_nodes = [n for n in v2_nodes if n.heading == "Warning"]
    assert len(v2_warning_nodes) == 2
    for node in v2_warning_nodes:
        # Check that warning warning aligns to correct v1 ID using body
        original_logical_id = v1_warning_nodes[node.body]
        assert node.logical_node_id == original_logical_id
        assert node.matching_status == "MATCHED"

    # ASSERTION 5: Brand new section ("Bluetooth Setup")
    node_bluetooth = v2_by_heading["Bluetooth Setup"]
    assert node_bluetooth.logical_node_id not in v1_map.values()
    assert node_bluetooth.matching_status == "NEW"
    assert node_bluetooth.matched_score is None
