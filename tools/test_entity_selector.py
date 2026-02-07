#!/usr/bin/env python3
"""
Test script for EntitySelector module.

Tests:
1. EntitySelectorConfig validation and property normalization
2. FilterPanel creation and filter value management
3. DetailsPanel creation and value formatting
4. EntitySelectorWidget integration with query builder
5. EntitySelectorDialog static method

Run with: python tools/test_entity_selector.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from PyQt6.QtWidgets import QApplication

# Must create QApplication before importing Qt widgets
app = QApplication(sys.argv)


def test_config():
    """Test EntitySelectorConfig creation and methods."""
    print("\n=== Testing EntitySelectorConfig ===")

    from dynamat.gui.widgets.base.entity_selector import EntitySelectorConfig, SelectionMode

    # Test basic creation
    config = EntitySelectorConfig(
        class_uri="https://dynamat.utep.edu/ontology#Specimen",
        display_properties=[
            "https://dynamat.utep.edu/ontology#hasSpecimenID",
            "dyn:hasMaterial",
            "hasShape",
        ],
        property_labels={
            "https://dynamat.utep.edu/ontology#hasSpecimenID": "Specimen ID",
        },
        filter_properties=["dyn:hasMaterial"],
        show_details_panel=True,
    )

    print(f"  Class URI: {config.class_uri}")
    print(f"  Display properties: {config.display_properties}")
    print(f"  Selection mode: {config.selection_mode}")

    # Test property label extraction
    label1 = config.get_property_label("https://dynamat.utep.edu/ontology#hasSpecimenID")
    print(f"  Label for hasSpecimenID: {label1}")
    assert label1 == "Specimen ID", f"Expected 'Specimen ID', got '{label1}'"

    label2 = config.get_property_label("https://dynamat.utep.edu/ontology#hasMaterial")
    print(f"  Label for hasMaterial: {label2}")
    assert label2 == "Material", f"Expected 'Material', got '{label2}'"

    # Test property normalization
    norm1 = config.normalize_property_uri("hasSpecimenID")
    print(f"  Normalized 'hasSpecimenID': {norm1}")
    assert norm1 == "https://dynamat.utep.edu/ontology#hasSpecimenID"

    norm2 = config.normalize_property_uri("dyn:hasMaterial")
    print(f"  Normalized 'dyn:hasMaterial': {norm2}")
    assert norm2 == "https://dynamat.utep.edu/ontology#hasMaterial"

    # Test normalized properties
    normalized = config.get_normalized_display_properties()
    print(f"  Normalized display properties: {normalized}")
    assert len(normalized) == 3
    assert all(p.startswith("https://") for p in normalized)

    print("  [PASS] EntitySelectorConfig tests passed")
    return True


def test_filter_panel():
    """Test FilterPanel creation and methods."""
    print("\n=== Testing FilterPanel ===")

    from dynamat.gui.widgets.base.entity_selector import EntitySelectorConfig, FilterPanel

    config = EntitySelectorConfig(
        class_uri="https://dynamat.utep.edu/ontology#Specimen",
        display_properties=["dyn:hasSpecimenID"],
        filter_properties=["dyn:hasMaterial", "dyn:hasStructure"],
        filter_labels={
            "dyn:hasMaterial": "Material",
            "dyn:hasStructure": "Structure Type",
        },
        show_search_box=True,
        show_refresh_button=True,
    )

    panel = FilterPanel(config)
    print(f"  Created FilterPanel with {len(panel._filter_combos)} filter combos")
    assert len(panel._filter_combos) == 2, "Expected 2 filter combos"

    # Test filter value management
    filters = panel.get_filter_values()
    print(f"  Initial filter values: {filters}")
    assert filters == {}, "Expected empty filters initially"

    # Test populating options
    panel.populate_filter_options(
        "dyn:hasMaterial",
        [
            ("https://dynamat.utep.edu/ontology#SS316", "SS316"),
            ("https://dynamat.utep.edu/ontology#Al6061", "Al6061"),
        ]
    )
    print("  Populated material filter with 2 options")

    # Test search box
    assert panel._search_box is not None, "Search box should exist"
    panel.set_search_text("test search")
    assert panel.get_search_text() == "test search"
    print(f"  Search text: {panel.get_search_text()}")

    # Test clear
    panel.clear_filters()
    assert panel.get_search_text() == ""
    print("  Cleared filters")

    print("  [PASS] FilterPanel tests passed")
    return True


def test_details_panel():
    """Test DetailsPanel creation and methods."""
    print("\n=== Testing DetailsPanel ===")

    from dynamat.gui.widgets.base.entity_selector import EntitySelectorConfig, DetailsPanel

    config = EntitySelectorConfig(
        class_uri="https://dynamat.utep.edu/ontology#Specimen",
        display_properties=["dyn:hasSpecimenID"],
        details_properties=[
            "https://dynamat.utep.edu/ontology#hasSpecimenID",
            "https://dynamat.utep.edu/ontology#hasMaterial",
            "https://dynamat.utep.edu/ontology#hasOriginalHeight",
        ],
        details_labels={
            "https://dynamat.utep.edu/ontology#hasSpecimenID": "ID",
            "https://dynamat.utep.edu/ontology#hasMaterial": "Material",
            "https://dynamat.utep.edu/ontology#hasOriginalHeight": "Height",
        },
    )

    panel = DetailsPanel(config)
    print(f"  Created DetailsPanel with {len(panel._value_labels)} value labels")
    assert len(panel._value_labels) == 3, "Expected 3 value labels"

    # Test update
    panel.update_details({
        "https://dynamat.utep.edu/ontology#hasSpecimenID": "SPN-001",
        "https://dynamat.utep.edu/ontology#hasMaterial": "https://dynamat.utep.edu/ontology#SS316",
        "https://dynamat.utep.edu/ontology#hasOriginalHeight": {"value": 10.5, "unit": "unit:MilliM"},
    })
    print("  Updated details with test data")

    # Check formatted values
    id_label = panel._value_labels.get("https://dynamat.utep.edu/ontology#hasSpecimenID")
    if id_label:
        print(f"  Specimen ID displayed: {id_label.text()}")
        assert id_label.text() == "SPN-001"

    mat_label = panel._value_labels.get("https://dynamat.utep.edu/ontology#hasMaterial")
    if mat_label:
        print(f"  Material displayed: {mat_label.text()}")
        assert mat_label.text() == "SS316"  # Should extract local name from URI

    height_label = panel._value_labels.get("https://dynamat.utep.edu/ontology#hasOriginalHeight")
    if height_label:
        print(f"  Height displayed: {height_label.text()}")
        assert "10.5" in height_label.text()

    # Test clear
    panel.clear()
    if id_label:
        assert id_label.text() == "--"
    print("  Cleared panel")

    print("  [PASS] DetailsPanel tests passed")
    return True


def test_entity_selector_widget():
    """Test EntitySelectorWidget creation."""
    print("\n=== Testing EntitySelectorWidget ===")

    from dynamat.gui.widgets.base.entity_selector import EntitySelectorConfig, EntitySelectorWidget

    config = EntitySelectorConfig(
        class_uri="https://dynamat.utep.edu/ontology#Specimen",
        display_properties=[
            "https://dynamat.utep.edu/ontology#hasSpecimenID",
            "https://dynamat.utep.edu/ontology#hasMaterial",
        ],
        filter_properties=["https://dynamat.utep.edu/ontology#hasMaterial"],
        show_details_panel=True,
        show_search_box=True,
        show_refresh_button=True,
    )

    # Create widget without query builder (won't load data)
    widget = EntitySelectorWidget(config)
    print("  Created EntitySelectorWidget (no query builder)")

    assert widget._table is not None, "Table should exist"
    assert widget._filter_panel is not None, "Filter panel should exist"
    assert widget._details_panel is not None, "Details panel should exist"
    assert widget._status_label is not None, "Status label should exist"

    print(f"  Table columns: {widget._table.columnCount()}")
    assert widget._table.columnCount() == 2, "Expected 2 columns"

    # Test public methods
    selected = widget.get_selected_entity()
    assert selected is None, "No entity should be selected initially"

    filters = widget.get_filters()
    assert filters == {}, "No filters initially"

    print("  [PASS] EntitySelectorWidget tests passed")
    return True


def test_entity_selector_dialog():
    """Test EntitySelectorDialog creation."""
    print("\n=== Testing EntitySelectorDialog ===")

    from dynamat.gui.widgets.base.entity_selector import EntitySelectorConfig, EntitySelectorDialog

    config = EntitySelectorConfig(
        class_uri="https://dynamat.utep.edu/ontology#Specimen",
        display_properties=["dyn:hasSpecimenID"],
        show_details_panel=True,
    )

    # Create dialog (won't show it)
    dialog = EntitySelectorDialog(config, title="Test Dialog")
    print("  Created EntitySelectorDialog")

    assert dialog._selector is not None, "Selector widget should exist"
    assert dialog._load_button is not None, "Load button should exist"
    assert not dialog._load_button.isEnabled(), "Load button should be disabled initially"

    selector = dialog.get_selector()
    assert selector is not None, "get_selector() should return widget"

    data = dialog.get_selected_data()
    assert data is None, "No data selected initially"

    print("  [PASS] EntitySelectorDialog tests passed")
    return True


def test_integration_with_query_builder():
    """Test integration with actual query builder (if specimens exist)."""
    print("\n=== Testing Integration with Query Builder ===")

    from dynamat.ontology import OntologyManager
    from dynamat.ontology.instance_query_builder import InstanceQueryBuilder
    from dynamat.gui.widgets.base.entity_selector import EntitySelectorConfig, EntitySelectorWidget
    from dynamat.config import config

    # Initialize ontology manager
    ontology_manager = OntologyManager()
    print("  Initialized OntologyManager")

    # Initialize query builder
    query_builder = InstanceQueryBuilder(ontology_manager)
    print("  Initialized InstanceQueryBuilder")

    # Scan specimens directory if it exists
    if config.SPECIMENS_DIR.exists():
        indexed = query_builder.scan_and_index(
            config.SPECIMENS_DIR,
            "https://dynamat.utep.edu/ontology#Specimen",
            "*_specimen.ttl"
        )
        print(f"  Indexed {indexed} specimens from {config.SPECIMENS_DIR}")

        if indexed > 0:
            # Create widget with query builder
            selector_config = EntitySelectorConfig(
                class_uri="https://dynamat.utep.edu/ontology#Specimen",
                display_properties=[
                    "https://dynamat.utep.edu/ontology#hasSpecimenID",
                    "https://dynamat.utep.edu/ontology#hasMaterial",
                ],
                filter_properties=["https://dynamat.utep.edu/ontology#hasMaterial"],
                show_details_panel=True,
            )

            widget = EntitySelectorWidget(
                config=selector_config,
                query_builder=query_builder,
                ontology_manager=ontology_manager
            )

            # Check table was populated
            row_count = widget._table.rowCount()
            print(f"  EntitySelectorWidget loaded {row_count} specimens")

            if row_count > 0:
                # Verify SPARQL filtering works
                widget.set_filters({})  # Clear filters
                all_count = widget._table.rowCount()

                # Get a material from first specimen
                first_instance = widget._instances_cache[0] if widget._instances_cache else {}
                material = first_instance.get("https://dynamat.utep.edu/ontology#hasMaterial")

                if material:
                    widget.set_filters({"https://dynamat.utep.edu/ontology#hasMaterial": material})
                    filtered_count = widget._table.rowCount()
                    print(f"  Filtered by material '{material}': {filtered_count} of {all_count} specimens")
                    assert filtered_count <= all_count, "Filtered count should be <= total"

            print("  [PASS] Integration tests passed")
            return True
    else:
        print(f"  Specimens directory not found: {config.SPECIMENS_DIR}")
        print("  [SKIP] Skipping integration tests (no specimens)")
        return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("EntitySelector Module Tests")
    print("=" * 60)

    all_passed = True

    try:
        all_passed &= test_config()
        all_passed &= test_filter_panel()
        all_passed &= test_details_panel()
        all_passed &= test_entity_selector_widget()
        all_passed &= test_entity_selector_dialog()
        all_passed &= test_integration_with_query_builder()
    except Exception as e:
        print(f"\n[ERROR] Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("All tests PASSED")
    else:
        print("Some tests FAILED")
    print("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
