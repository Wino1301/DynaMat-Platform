"""
DynaMat Platform - Widget Validation Tool
Validates widget creation and configuration against ontology definitions.

Usage:
    python tools/validate_widget.py dyn:hasOriginalDiameter
    python tools/validate_widget.py dyn:hasMaterial --class dyn:Specimen
    python tools/validate_widget.py dyn:hasMatrixMaterial --verbose
    python tools/validate_widget.py dyn:hasOriginalLength --show-constraints
"""

import sys
import argparse
from pathlib import Path
from typing import Optional, Dict, Any, List

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dynamat.ontology import OntologyManager
from dynamat.gui.dependencies import ConstraintManager
from dynamat.gui.core import WidgetFactory
from dynamat.ontology.schema.gui_schema_builder import PropertyMetadata

from PyQt6.QtWidgets import QApplication, QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit, QCheckBox, QLabel, QDateEdit
from PyQt6.QtCore import QDate

# Import UnitValueWidget validator
from tools.validators import validate_unit_value_widget


# URI namespace mappings
NAMESPACES = {
    'dyn': 'https://dynamat.utep.edu/ontology#',
    'gui': 'https://dynamat.utep.edu/gui/constraints#',
}


def expand_uri(short_uri: str) -> str:
    """
    Expand short-form URI to full URI.

    Args:
        short_uri: Short URI like 'dyn:Specimen' or full URI

    Returns:
        Full URI string
    """
    if short_uri.startswith('http'):
        return short_uri

    for prefix, namespace in NAMESPACES.items():
        if short_uri.startswith(f'{prefix}:'):
            return short_uri.replace(f'{prefix}:', namespace)

    return short_uri


def print_section(title: str):
    """Print a section header."""
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def print_subsection(title: str):
    """Print a subsection header."""
    print("\n" + "-" * 70)
    print(title)
    print("-" * 70)


def print_result(passed: bool, message: str):
    """Print a test result."""
    status = "PASS" if passed else "FAIL"
    print(f"{status}: {message}")


def print_info(label: str, value: Any):
    """Print an info line."""
    print(f"  {label}: {value}")


def get_widget_initial_value(widget, widget_type: str) -> str:
    """
    Get the initial/default value of a widget.

    Args:
        widget: The PyQt6 widget instance
        widget_type: Type of widget

    Returns:
        String representation of initial value
    """
    try:
        if isinstance(widget, QComboBox):
            current_text = widget.currentText()
            current_data = widget.currentData()
            item_count = widget.count()
            return f"'{current_text}' (data: {current_data}, {item_count} items)"

        elif isinstance(widget, QSpinBox):
            return str(widget.value())

        elif isinstance(widget, QDoubleSpinBox):
            return str(widget.value())

        elif isinstance(widget, QLineEdit):
            text = widget.text()
            return f"'{text}'" if text else "(empty)"

        elif isinstance(widget, QCheckBox):
            return "checked" if widget.isChecked() else "unchecked"

        elif isinstance(widget, QLabel):
            text = widget.text()
            return f"'{text}'" if text else "(empty)"

        elif isinstance(widget, QDateEdit):
            return widget.date().toString("yyyy-MM-dd")

        else:
            return f"(unknown widget type: {type(widget).__name__})"

    except Exception as e:
        return f"(error reading value: {e})"


def validate_initial_value(widget, widget_type: str, prop: PropertyMetadata) -> tuple[bool, str]:
    """
    Validate that initial value matches expectations.

    Args:
        widget: The PyQt6 widget instance
        widget_type: Type of widget
        prop: Property metadata

    Returns:
        (passed, message) tuple
    """
    try:
        if isinstance(widget, QComboBox):
            # Check if non-required has "(Select...)" option
            if not prop.is_required:
                first_text = widget.itemText(0) if widget.count() > 0 else ""
                if first_text != "(Select...)":
                    return False, f"Non-required combo should start with '(Select...)' but has '{first_text}'"
                if widget.itemData(0) != "":
                    return False, f"First item data should be empty string, got: {widget.itemData(0)}"

            # If it's a unit combo, check for default unit
            if prop.is_measurement_property and prop.default_unit:
                # Unit combos are handled by UnitValueWidget, not directly accessible here
                return True, "Unit combo (validated by UnitValueWidget)"

            return True, "Combo initialized correctly"

        elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            initial = widget.value()
            if initial != 0:
                return False, f"Spinbox should initialize to 0, got {initial}"
            return True, "Spinbox initialized to 0"

        elif isinstance(widget, QLineEdit):
            text = widget.text()
            if text != "":
                return False, f"LineEdit should be empty, got '{text}'"
            return True, "LineEdit is empty"

        elif isinstance(widget, QCheckBox):
            if widget.isChecked():
                return False, "Checkbox should be unchecked initially"
            return True, "Checkbox is unchecked"

        elif isinstance(widget, QLabel):
            text = widget.text()
            if text != "":
                return False, f"Label should be empty, got '{text}'"
            return True, "Label is empty"

        elif isinstance(widget, QDateEdit):
            # Date widgets typically initialize to current date
            return True, f"Date initialized to {widget.date().toString('yyyy-MM-dd')}"

        else:
            return True, f"No initial value check for {type(widget).__name__}"

    except Exception as e:
        return False, f"Error validating initial value: {e}"


def validate_widget_for_property(
    property_uri: str,
    class_uri: Optional[str] = None,
    verbose: bool = False,
    show_constraints: bool = False
) -> bool:
    """
    Validate widget creation for a specific property.

    Args:
        property_uri: URI of the property to validate
        class_uri: Optional class URI (will auto-detect if not provided)
        verbose: Show detailed output
        show_constraints: Show constraint details

    Returns:
        True if validation passed
    """
    full_property_uri = expand_uri(property_uri)
    full_class_uri = expand_uri(class_uri) if class_uri else None

    print_section(f"Widget Validation - {property_uri}")

    try:
        # Initialize managers
        ontology_manager = OntologyManager()
        constraint_manager = ConstraintManager()

        # Find the class if not provided
        if not full_class_uri:
            print("\nSearching for property domain...")
            # Query ontology for domain
            result = ontology_manager.domain_queries.get_property_domain(full_property_uri)
            if result:
                full_class_uri = result
                print_info("Auto-detected class", class_uri or full_class_uri)
            else:
                print_result(False, "Could not determine property domain")
                return False
        else:
            print_info("Target class", class_uri or full_class_uri)

        # Get property metadata
        print("\nLoading property metadata...")
        class_metadata = ontology_manager.get_class_metadata_for_form(full_class_uri)

        # Find the property in class metadata
        property_metadata = None
        for prop in class_metadata.properties:
            if prop.uri == full_property_uri:
                property_metadata = prop
                break

        if not property_metadata:
            print_result(False, f"Property {property_uri} not found in class metadata")
            return False

        print_result(True, f"Property metadata loaded")

        # Display property information
        print_subsection("Property Metadata")
        print_info("URI", property_metadata.uri)
        print_info("Name", property_metadata.name)
        print_info("Display Name", property_metadata.display_name)
        print_info("Data Type", property_metadata.data_type)
        print_info("Form Group", property_metadata.form_group)
        print_info("Display Order", property_metadata.display_order)
        print_info("Is Required", property_metadata.is_required)
        print_info("Is Functional", property_metadata.is_functional)
        print_info("Is Read-only", property_metadata.is_read_only)

        if verbose:
            print_info("Description", property_metadata.description)
            if property_metadata.range_class:
                print_info("Range Class", property_metadata.range_class)
            if property_metadata.valid_values:
                print_info("Valid Values", property_metadata.valid_values)

        # Display measurement information if applicable
        if property_metadata.is_measurement_property:
            print_subsection("Measurement Configuration")
            print_info("Quantity Kind", property_metadata.quantity_kind)
            print_info("Default Unit", property_metadata.default_unit)
            if verbose and property_metadata.compatible_units:
                print(f"  Compatible Units ({len(property_metadata.compatible_units)}):")
                for unit_info in property_metadata.compatible_units[:5]:  # Show first 5
                    print(f"    - {unit_info.name} ({unit_info.symbol})")
                if len(property_metadata.compatible_units) > 5:
                    print(f"    ... and {len(property_metadata.compatible_units) - 5} more")

        # Display constraints from property metadata
        if property_metadata.min_value is not None or property_metadata.max_value is not None:
            print_subsection("Property Constraints")
            if property_metadata.min_value is not None:
                print_info("Min Value", property_metadata.min_value)
            if property_metadata.max_value is not None:
                print_info("Max Value", property_metadata.max_value)
            if property_metadata.max_length:
                print_info("Max Length", property_metadata.max_length)
            if property_metadata.pattern:
                print_info("Pattern", property_metadata.pattern)

        # Create widget using WidgetFactory
        print_subsection("Widget Creation")

        # Need QApplication for widget creation
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        widget_factory = WidgetFactory(ontology_manager)

        # Determine expected widget type
        expected_widget_type = widget_factory._determine_widget_type(property_metadata)
        print_info("Expected Widget Type", expected_widget_type)

        # Create the widget
        widget = widget_factory.create_widget(property_metadata)

        if widget is None:
            print_result(False, "Widget creation returned None")
            return False

        actual_widget_class = type(widget).__name__
        print_result(True, f"Widget created: {actual_widget_class}")

        # Validate widget type matches expectation
        widget_type_map = {
            'label': QLabel,
            'line_edit': QLineEdit,
            'combo': QComboBox,
            'object_combo': QComboBox,
            'spinbox': QSpinBox,
            'double_spinbox': QDoubleSpinBox,
            'checkbox': QCheckBox,
            'date': QDateEdit,
            'unit_value': 'UnitValueWidget',  # Custom widget
        }

        expected_class = widget_type_map.get(expected_widget_type)
        if expected_class == 'UnitValueWidget':
            # UnitValueWidget is a composite widget, check differently
            widget_matches = widget.__class__.__name__ == 'UnitValueWidget'
        else:
            widget_matches = isinstance(widget, expected_class) if expected_class else False

        if widget_matches:
            print_result(True, f"Widget type matches expectation")
        else:
            print_result(False, f"Widget type mismatch: expected {expected_class}, got {actual_widget_class}")

        # Special handling for UnitValueWidget
        if actual_widget_class == 'UnitValueWidget':
            print_subsection("UnitValueWidget Detailed Validation")

            unit_widget_passed, unit_widget_details = validate_unit_value_widget(
                widget, property_metadata, verbose
            )

            # Display summary information
            spinbox_info = unit_widget_details.get('value_spinbox_info', {})
            combobox_info = unit_widget_details.get('unit_combobox_info', {})

            print_info("Value Spinbox", f"value={spinbox_info.get('value', 'N/A')}")
            print_info("Unit Combobox",
                      f"count={combobox_info.get('count', 'N/A')}, "
                      f"current={combobox_info.get('current_text', 'N/A')}")

            # Display all validation checks
            print("\nValidation Checks:")
            for check_name, passed in unit_widget_details.get('validation_checks', {}).items():
                status = "PASS" if passed else "FAIL"
                print(f"  {status}: {check_name}")

            # Display errors
            if unit_widget_details.get('errors'):
                print("\nErrors:")
                for error in unit_widget_details['errors']:
                    print(f"  - {error}")

            # Display warnings
            if unit_widget_details.get('warnings'):
                print("\nWarnings:")
                for warning in unit_widget_details['warnings']:
                    print(f"  - {warning}")

            if not unit_widget_passed:
                print_result(False, "UnitValueWidget validation failed")
                checks_passed = False
            else:
                print_result(True, "UnitValueWidget validation passed")

        # Check initial value
        print_subsection("Initial Value Validation")
        initial_value = get_widget_initial_value(widget, expected_widget_type)
        print_info("Initial Value", initial_value)

        value_passed, value_message = validate_initial_value(widget, expected_widget_type, property_metadata)
        print_result(value_passed, value_message)

        # Check widget properties
        print_subsection("Widget Properties")
        print_info("Enabled", widget.isEnabled())
        print_info("Visible", widget.isVisible())
        print_info("Minimum Width", widget.minimumWidth())

        if property_metadata.is_read_only:
            print_info("Read-only Mode", "Expected: True")
            # Check if widget is properly disabled or styled for read-only
            # QLabel widgets are always enabled, so skip this check for labels
            if isinstance(widget, QLabel):
                print_result(True, "Label widget for read-only display")
            elif not widget.isEnabled():
                print_result(True, "Widget is disabled for read-only")
            else:
                print_result(False, "Read-only widget should be disabled")

        # Load constraints that affect this property
        print_subsection("Constraint Analysis")
        all_constraints = constraint_manager.get_constraints_for_class(full_class_uri)

        # Find constraints that trigger on this property
        triggered_by_this = [c for c in all_constraints if full_property_uri in c.triggers]
        print_info("Constraints triggered by this field", len(triggered_by_this))

        # Find constraints that show/hide this property
        visibility_constraints = [c for c in all_constraints if c.has_visibility_ops()]
        affects_visibility = []
        for c in visibility_constraints:
            if c.show_fields and full_property_uri in c.show_fields:
                affects_visibility.append((c, 'show'))
            if c.hide_fields and full_property_uri in c.hide_fields:
                affects_visibility.append((c, 'hide'))

        print_info("Constraints affecting visibility", len(affects_visibility))

        # Find constraints that calculate this property
        calculation_constraints = [c for c in all_constraints
                                   if c.has_calculation_op() and c.calculation_target == full_property_uri]
        print_info("Constraints that calculate this field", len(calculation_constraints))

        # Find constraints that generate this property
        generation_constraints = [c for c in all_constraints
                                 if c.has_generation_op() and c.generation_target == full_property_uri]
        print_info("Constraints that generate this field", len(generation_constraints))

        # Find constraints where this property is an input
        used_as_input = []
        for c in all_constraints:
            if c.calculation_inputs and full_property_uri in c.calculation_inputs:
                used_as_input.append((c, 'calculation'))
            if c.generation_inputs and full_property_uri in c.generation_inputs:
                used_as_input.append((c, 'generation'))

        print_info("Constraints using this as input", len(used_as_input))

        # Find filtering constraints that apply to this field
        filter_constraints = [c for c in all_constraints
                             if c.has_filter_op() and c.apply_to_fields and full_property_uri in c.apply_to_fields]
        print_info("Filter constraints applying to this field", len(filter_constraints))

        # Detailed constraint output
        if show_constraints or verbose:
            if triggered_by_this:
                print("\n  Constraints triggered by this field:")
                for c in triggered_by_this:
                    print(f"    - {c.label} (priority {c.priority})")
                    if verbose:
                        print(f"      URI: {c.uri}")
                        print(f"      When: {c.when_values}")
                        ops = []
                        if c.has_visibility_ops():
                            ops.append("visibility")
                        if c.has_calculation_op():
                            ops.append("calculation")
                        if c.has_generation_op():
                            ops.append("generation")
                        if c.has_filter_op():
                            ops.append("filtering")
                        print(f"      Operations: {', '.join(ops)}")

            if affects_visibility:
                print("\n  Constraints affecting visibility:")
                for c, action in affects_visibility:
                    print(f"    - {c.label} ({action}s field)")
                    if verbose:
                        print(f"      Triggers: {c.triggers}")
                        print(f"      When: {c.when_values}")

            if calculation_constraints:
                print("\n  Constraints calculating this field:")
                for c in calculation_constraints:
                    print(f"    - {c.label}")
                    if verbose:
                        print(f"      Function: {c.calculation_function}")
                        print(f"      Inputs: {c.calculation_inputs}")

            if generation_constraints:
                print("\n  Constraints generating this field:")
                for c in generation_constraints:
                    print(f"    - {c.label}")
                    if verbose:
                        print(f"      Template: {c.generation_template}")
                        print(f"      Inputs: {c.generation_inputs}")

            if used_as_input:
                print("\n  Used as input in constraints:")
                for c, op_type in used_as_input:
                    print(f"    - {c.label} ({op_type})")

            if filter_constraints:
                print("\n  Filter constraints applying to this field:")
                for c in filter_constraints:
                    print(f"    - {c.label}")
                    if verbose:
                        if c.exclude_classes:
                            print(f"      Excludes: {c.exclude_classes}")
                        if c.filter_by_classes:
                            print(f"      Filters by: {c.filter_by_classes}")

        print_subsection("Validation Summary")
        checks_passed = widget_matches and value_passed

        if checks_passed:
            print_result(True, "All validation checks passed")
        else:
            print_result(False, "Some validation checks failed")

        return checks_passed

    except Exception as e:
        print_result(False, f"Validation failed with error: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return False


def main():
    """Main entry point for widget validation."""
    parser = argparse.ArgumentParser(
        description='Validate DynaMat widget creation and configuration',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/validate_widget.py dyn:hasOriginalDiameter
  python tools/validate_widget.py dyn:hasMaterial --class dyn:Specimen
  python tools/validate_widget.py dyn:hasMatrixMaterial --verbose
  python tools/validate_widget.py dyn:hasOriginalLength --show-constraints
        """
    )

    parser.add_argument(
        'property_uri',
        help='Property URI to validate (e.g., dyn:hasOriginalDiameter)'
    )

    parser.add_argument(
        '--class', '-c',
        dest='class_uri',
        help='Class URI (e.g., dyn:Specimen) - will auto-detect if not provided'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed output for debugging'
    )

    parser.add_argument(
        '--show-constraints',
        action='store_true',
        help='Show detailed constraint information'
    )

    args = parser.parse_args()

    # Run validation
    passed = validate_widget_for_property(
        property_uri=args.property_uri,
        class_uri=args.class_uri,
        verbose=args.verbose,
        show_constraints=args.show_constraints
    )

    # Exit with appropriate code
    if passed:
        print("\n" + "=" * 70)
        print("VALIDATION PASSED")
        print("=" * 70)
        sys.exit(0)
    else:
        print("\n" + "=" * 70)
        print("VALIDATION FAILED")
        print("=" * 70)
        sys.exit(1)


if __name__ == "__main__":
    main()
