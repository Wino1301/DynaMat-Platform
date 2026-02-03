"""
Simple validation script for group builder architecture.

This script validates that the new group builder architecture works correctly
without requiring pytest.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication, QGroupBox

from dynamat.ontology import OntologyManager, PropertyMetadata
from dynamat.gui.builders import (
    DefaultGroupBuilder, CustomizableFormBuilder
)
from dynamat.gui.core import WidgetFactory


def test_default_group_builder():
    """Test DefaultGroupBuilder creates QGroupBox."""
    print("Testing DefaultGroupBuilder...")

    ontology_manager = OntologyManager()
    widget_factory = WidgetFactory(ontology_manager)
    builder = DefaultGroupBuilder(widget_factory)

    # Create sample properties
    properties = [
        PropertyMetadata(
            uri="http://example.org#prop1",
            name="property1",
            display_name="Property 1",
            form_group="TestGroup",
            display_order=1,
            data_type="http://www.w3.org/2001/XMLSchema#string",
            is_functional=True,
            is_required=True,
            valid_values=[],
            default_unit=None,
            range_class=None,
            domain_class=None,
            description="Test property",
            group_order=1
        ),
    ]

    # Build group
    group_widget, form_fields = builder.build_group("TestGroup", properties)

    # Validate
    assert isinstance(group_widget, QGroupBox), "Group widget should be QGroupBox"
    assert group_widget.title() == "Test Group", f"Expected 'Test Group', got '{group_widget.title()}'"
    assert len(form_fields) == 1, f"Expected 1 form field, got {len(form_fields)}"

    print("  + Creates QGroupBox with correct title")
    print("  + Creates form fields for properties")
    print("  + Formats group names correctly")


def test_customizable_form_builder():
    """Test CustomizableFormBuilder initialization and registration."""
    print("\nTesting CustomizableFormBuilder...")

    ontology_manager = OntologyManager()
    builder = CustomizableFormBuilder(ontology_manager)

    # Validate initialization
    assert builder.ontology_manager is not None, "OntologyManager should be set"
    assert builder.form_manager is not None, "FormManager should be set"
    assert builder.widget_factory is not None, "WidgetFactory should be set"

    print("  + Initializes correctly with OntologyManager")
    print("  + Creates FormManager and WidgetFactory")

    # Test registration
    custom_builder = DefaultGroupBuilder(builder.widget_factory)
    builder.register_group_builder("CustomGroup", custom_builder)
    assert "CustomGroup" in builder._group_builders, "Custom builder should be registered"

    print("  + Registers custom group builders")

    # Test unregistration
    builder.unregister_group_builder("CustomGroup")
    assert "CustomGroup" not in builder._group_builders, "Custom builder should be unregistered"

    print("  + Unregisters custom group builders")


def test_equipment_page_nested_builder():
    """Test that equipment page has nested builder class."""
    print("\nTesting EquipmentPage nested builder...")

    try:
        from dynamat.gui.widgets.shpb.pages.equipment_page import EquipmentPage
        print("  + EquipmentPage imports successfully")

        # Verify nested builder exists
        assert hasattr(EquipmentPage, '_EquipmentPropertiesBuilder')
        print("  + EquipmentPage has _EquipmentPropertiesBuilder nested class")

        # Test builder instantiation
        ontology_manager = OntologyManager()
        widget_factory = WidgetFactory(ontology_manager)
        equipment_builder = EquipmentPage._EquipmentPropertiesBuilder(widget_factory)

        assert equipment_builder.widget_factory is not None
        print("  + Nested builder instantiates correctly")

    except Exception as e:
        print(f"  X Failed: {e}")
        raise


def main():
    """Run all validation tests."""
    print("=" * 60)
    print("Group Builder Architecture Validation")
    print("=" * 60)

    # Create QApplication
    app = QApplication(sys.argv)

    try:
        test_default_group_builder()
        test_customizable_form_builder()
        test_equipment_page_nested_builder()

        print("\n" + "=" * 60)
        print("All validation tests passed!")
        print("=" * 60)

    except Exception as e:
        print("\n" + "=" * 60)
        print(f"X Validation failed: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
