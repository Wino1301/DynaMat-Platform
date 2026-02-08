"""
DynaMat Platform - Statistics Workflow Integration Test
Tests statistics tracking by performing actual operations.

Usage:
    python tools/test_statistics_workflow.py
    python tools/test_statistics_workflow.py --class dyn:Specimen --property dyn:hasOriginalDiameter
    python tools/test_statistics_workflow.py --class dyn:MechanicalTest --property dyn:hasTestDate
    python tools/test_statistics_workflow.py --verbose
"""

import sys
import argparse
from pathlib import Path
from typing import Dict, Any, Tuple



from dynamat.ontology import OntologyManager
from dynamat.gui.core import WidgetFactory
from dynamat.gui.builders import OntologyFormBuilder
from dynamat.ontology.schema.gui_schema_builder import GUISchemaBuilder
from dynamat.config import Config

from PyQt6.QtWidgets import QApplication

from tools.validators import (
    validate_statistics_structure,
    compare_statistics,
    print_statistics_summary
)


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
    status = "[PASS]" if passed else "[FAIL]"
    print(f"{status} {message}")


def print_info(label: str, value: Any):
    """Print an info line."""
    print(f"  {label}: {value}")


def test_statistics_workflow(
    class_uri: str = "dyn:Specimen",
    property_uri: str = "dyn:hasOriginalDiameter",
    verbose: bool = False
) -> bool:
    """
    Test statistics tracking through a complete workflow.

    Args:
        class_uri: URI of the class to test (e.g., 'dyn:Specimen')
        property_uri: URI of a property to test (e.g., 'dyn:hasOriginalDiameter')
        verbose: Show detailed output

    Returns:
        True if all tests passed
    """
    full_class_uri = expand_uri(class_uri)
    full_property_uri = expand_uri(property_uri)

    print_section("Statistics Workflow Integration Test")
    print_info("Class URI", class_uri)
    print_info("Property URI", property_uri)

    all_passed = True

    # Disable caching to force statistics tracking
    original_cache_setting = Config.USE_SCHEMA_CACHE
    Config.USE_SCHEMA_CACHE = False
    print_info("Schema caching", "DISABLED (forcing fresh builds)")

    try:
        # Need QApplication for widget creation
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        # ================================================================
        # STEP 1: Initialize OntologyManager
        # ================================================================
        print_subsection("Step 1: Initialize OntologyManager")

        om = OntologyManager()

        # Clear any existing caches to ensure clean test
        if hasattr(om.gui_schema_builder, 'cache'):
            om.gui_schema_builder.cache.clear_all_caches()
            print_info("Cache cleared", "Fresh test environment")
        om_stats_initial = om.get_statistics()

        if verbose:
            print_statistics_summary(om_stats_initial, "OntologyManager (Initial)")

        # Validate structure - OntologyManager now follows standard pattern
        if not isinstance(om_stats_initial, dict):
            print_result(False, "OntologyManager statistics is not a dict")
            all_passed = False
        else:
            # Check for expected keys
            required_keys = {'configuration', 'execution', 'health'}
            missing = required_keys - set(om_stats_initial.keys())
            if missing:
                print_result(False, f"OntologyManager missing keys: {missing}")
                all_passed = False
            else:
                print_result(True, "OntologyManager statistics structure valid")

        # Check that ontology loaded successfully - access via components
        loader_stats = om_stats_initial.get('components', {}).get('loader', {})
        files_loaded = loader_stats.get('execution', {}).get('files_loaded', 0)
        print_info("Ontology files loaded", files_loaded)

        if files_loaded > 0:
            print_result(True, f"OntologyLoader loaded {files_loaded} files")
        else:
            print_result(False, "OntologyLoader did not load any files")
            all_passed = False

        # ================================================================
        # STEP 2: Build Class Metadata (GUISchemaBuilder)
        # ================================================================
        print_subsection("Step 2: Build Class Metadata")

        # Get GUISchemaBuilder from OntologyManager
        gsb = om.gui_schema_builder
        gsb_stats_before = gsb.get_statistics()

        if verbose:
            print_statistics_summary(gsb_stats_before, "GUISchemaBuilder (Before)")

        # Get class metadata (this should increment statistics)
        class_metadata = om.get_class_metadata_for_form(full_class_uri)

        gsb_stats_after = gsb.get_statistics()

        if verbose:
            print_statistics_summary(gsb_stats_after, "GUISchemaBuilder (After)")

        # Get nested metadata builds counter
        metadata_builds = gsb_stats_after['execution'].get('metadata_builds', {})
        total_builds = metadata_builds.get('total_builds', 0)
        print_info("Total metadata builds", total_builds)

        if total_builds > 0:
            print_result(True, f"GUISchemaBuilder tracked {total_builds} metadata build(s)")
        else:
            print_result(False, "GUISchemaBuilder did not track metadata builds")
            all_passed = False

        # ================================================================
        # STEP 3: Create Widget (WidgetFactory)
        # ================================================================
        print_subsection("Step 3: Create Widget")

        wf = WidgetFactory(om)
        wf_stats_before = wf.get_statistics()

        if verbose:
            print_statistics_summary(wf_stats_before, "WidgetFactory (Before)")

        # Find the property in class metadata
        property_metadata = None
        for prop in class_metadata.properties:
            if prop.uri == full_property_uri:
                property_metadata = prop
                break

        if not property_metadata:
            print_result(False, f"Property {property_uri} not found in class metadata")
            print_info("Available properties", [p.name for p in class_metadata.properties])
            all_passed = False
        else:
            print_result(True, f"Property metadata found: {property_metadata.display_name}")

            # Create widget
            widget = wf.create_widget(property_metadata)

            if widget is None:
                print_result(False, "Widget creation returned None")
                all_passed = False
            else:
                widget_type = type(widget).__name__
                print_result(True, f"Widget created: {widget_type}")

                # Get statistics after
                wf_stats_after = wf.get_statistics()

                if verbose:
                    print_statistics_summary(wf_stats_after, "WidgetFactory (After)")

                # Validate statistics changed
                total_widgets_before = wf_stats_before['execution'].get('total_widgets', 0)
                total_widgets_after = wf_stats_after['execution'].get('total_widgets', 0)

                widgets_created = total_widgets_after - total_widgets_before

                print_info("Widgets created this session", widgets_created)

                if widgets_created == 1:
                    print_result(True, "WidgetFactory correctly tracked widget creation")
                else:
                    print_result(False, f"Expected 1 widget created, got {widgets_created}")
                    all_passed = False

                # Check widget type tracking
                widget_counts_after = wf_stats_after['execution'].get('widget_creation_counts', {})
                if verbose:
                    print_info("Widget type counts", widget_counts_after)

        # ================================================================
        # STEP 4: Build Form (OntologyFormBuilder)
        # ================================================================
        print_subsection("Step 4: Build Form")

        ofb = OntologyFormBuilder(om)
        ofb_stats_before = ofb.get_statistics()

        if verbose:
            print_statistics_summary(ofb_stats_before, "OntologyFormBuilder (Before)")

        # Build form
        form = ofb.build_form(full_class_uri)

        if form is None:
            print_result(False, "Form creation returned None")
            all_passed = False
        else:
            print_result(True, "Form created successfully")

            # Get statistics after
            ofb_stats_after = ofb.get_statistics()

            if verbose:
                print_statistics_summary(ofb_stats_after, "OntologyFormBuilder (After)")

            # Validate statistics changed
            total_forms_before = ofb_stats_before['execution'].get('total_forms_created', 0)
            total_forms_after = ofb_stats_after['execution'].get('total_forms_created', 0)

            forms_created = total_forms_after - total_forms_before

            print_info("Forms created this session", forms_created)

            if forms_created == 1:
                print_result(True, "OntologyFormBuilder correctly tracked form creation")
            else:
                print_result(False, f"Expected 1 form created, got {forms_created}")
                all_passed = False

        # ================================================================
        # STEP 5: Cross-Manager Consistency
        # ================================================================
        print_subsection("Step 5: Cross-Manager Consistency")

        # Check that all managers report healthy state
        managers_healthy = True

        # OntologyManager health - it has 'components' instead of 'health'
        om_components = om_stats_initial.get('components', {})
        if verbose:
            print_info("OntologyManager components", om_components)

        # WidgetFactory health - check 'errors' category
        wf_final_stats = wf.get_statistics()
        wf_errors_cat = wf_final_stats.get('errors', {})
        wf_errors = wf_errors_cat.get('total_errors', 0)

        print_info("WidgetFactory creation errors", wf_errors)

        if wf_errors == 0:
            print_result(True, "No widget creation errors")
        else:
            print_result(False, f"WidgetFactory reported {wf_errors} creation errors")
            managers_healthy = False
            all_passed = False

        # OntologyFormBuilder health
        ofb_final_stats = ofb.get_statistics()
        ofb_health = ofb_final_stats.get('health', {})
        ofb_errors = ofb_health.get('total_form_errors', 0)

        print_info("OntologyFormBuilder form errors", ofb_errors)

        if ofb_errors == 0:
            print_result(True, "No form creation errors")
        else:
            print_result(False, f"OntologyFormBuilder reported {ofb_errors} form errors")
            managers_healthy = False
            all_passed = False

        if managers_healthy:
            print_result(True, "All managers report healthy state")

        # ================================================================
        # Final Summary
        # ================================================================
        print_subsection("Workflow Summary")

        print_info("OntologyLoader files loaded", files_loaded)
        print_info("GUISchemaBuilder metadata builds", total_builds)
        print_info("WidgetFactory widgets created", total_widgets_after)
        print_info("OntologyFormBuilder forms created", total_forms_after)

        return all_passed

    except Exception as e:
        print_result(False, f"Workflow test failed with error: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return False
    finally:
        # Restore original cache setting
        Config.USE_SCHEMA_CACHE = original_cache_setting


def main():
    """Main entry point for workflow testing."""
    parser = argparse.ArgumentParser(
        description='Test DynaMat statistics tracking through complete workflow',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/test_statistics_workflow.py
  python tools/test_statistics_workflow.py --class dyn:Specimen --property dyn:hasOriginalDiameter
  python tools/test_statistics_workflow.py --class dyn:MechanicalTest --property dyn:hasTestDate
  python tools/test_statistics_workflow.py --verbose
        """
    )

    parser.add_argument(
        '--class', '-c',
        dest='class_uri',
        default='dyn:Specimen',
        help='Class URI to test (e.g., dyn:Specimen)'
    )

    parser.add_argument(
        '--property', '-p',
        dest='property_uri',
        default='dyn:hasOriginalDiameter',
        help='Property URI to test (e.g., dyn:hasOriginalDiameter)'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed output'
    )

    args = parser.parse_args()

    # Run workflow test
    passed = test_statistics_workflow(
        class_uri=args.class_uri,
        property_uri=args.property_uri,
        verbose=args.verbose
    )

    # Print final result
    print_section("Final Result")

    if passed:
        print("[PASS] All workflow tests passed")
        print("\nStatistics tracking is working correctly across all managers.")
        sys.exit(0)
    else:
        print("[FAIL] Some workflow tests failed")
        print("\nReview the output above to identify which statistics are not tracking correctly.")
        sys.exit(1)


if __name__ == "__main__":
    main()
