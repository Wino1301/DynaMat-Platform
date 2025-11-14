"""
DynaMat Platform - Statistics Validation Tool
Validates statistics methods across all managers.

Usage:
    python tools/validate_statistics.py                    # Test all managers
    python tools/validate_statistics.py --manager WidgetFactory
    python tools/validate_statistics.py --verbose
    python tools/validate_statistics.py --json             # JSON output
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Dict, Any, List, Tuple

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dynamat.ontology import OntologyManager
from dynamat.gui.core import WidgetFactory
from dynamat.gui.builders import OntologyFormBuilder
from dynamat.gui.dependencies import DependencyManager, ConstraintManager
from dynamat.ontology.schema.gui_schema_builder import GUISchemaBuilder
from dynamat.ontology.core.ontology_loader import OntologyLoader

from tools.validators import (
    validate_statistics_structure,
    validate_json_serializable,
    validate_counter_types,
    validate_category,
    print_statistics_summary
)


def print_section(title: str):
    """Print a section header."""
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def print_result(passed: bool, message: str):
    """Print a test result."""
    status = "[PASS]" if passed else "[FAIL]"
    print(f"{status} {message}")


def print_info(label: str, value: Any):
    """Print an info line."""
    print(f"  {label}: {value}")


def test_widget_factory(verbose: bool = False) -> Tuple[bool, Dict[str, Any]]:
    """
    Test WidgetFactory statistics.

    Args:
        verbose: Show detailed output

    Returns:
        Tuple of (passed: bool, stats: dict)
    """
    manager_name = "WidgetFactory"
    print_section(f"Testing {manager_name}")

    try:
        # Initialize
        om = OntologyManager()
        wf = WidgetFactory(om)

        # Get statistics
        stats = wf.get_statistics()

        if verbose:
            print_statistics_summary(stats, manager_name)

        # Validate structure
        expected_categories = {'configuration', 'execution', 'health'}
        struct_passed, struct_errors = validate_statistics_structure(
            stats, expected_categories, manager_name
        )

        for error in struct_errors:
            print_result(False, error)

        if struct_passed:
            print_result(True, "Statistics structure valid")

        # Validate JSON serializable
        json_passed, json_errors = validate_json_serializable(stats, manager_name)
        for error in json_errors:
            print_result(False, error)

        if json_passed:
            print_result(True, "Statistics JSON-serializable")

        # Validate counter types
        types_passed, types_errors = validate_counter_types(stats, manager_name, verbose)
        for error in types_errors:
            print_result(False, error)

        if types_passed:
            print_result(True, "Counter types valid")

        # Validate specific keys - WidgetFactory uses 'widgets_created' not 'widget_creation_counts'
        config_passed, config_errors = validate_category(
            stats, 'configuration',
            {'available_widget_types'},
            manager_name
        )
        for error in config_errors:
            print_result(False, error)

        exec_passed, exec_errors = validate_category(
            stats, 'execution',
            {'total_widgets'},  # widgets_created is optional
            manager_name
        )
        for error in exec_errors:
            print_result(False, error)

        # Print key stats
        if not verbose:
            print_info("Available widget types", stats['configuration']['available_widget_types'])
            print_info("Total widgets created", stats['execution']['total_widgets'])

        all_passed = struct_passed and json_passed and types_passed and config_passed and exec_passed
        return all_passed, stats

    except Exception as e:
        print_result(False, f"Failed to test {manager_name}: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return False, {}


def test_gui_schema_builder(verbose: bool = False) -> Tuple[bool, Dict[str, Any]]:
    """
    Test GUISchemaBuilder statistics.

    Args:
        verbose: Show detailed output

    Returns:
        Tuple of (passed: bool, stats: dict)
    """
    manager_name = "GUISchemaBuilder"
    print_section(f"Testing {manager_name}")

    try:
        # Initialize - GUISchemaBuilder is accessed through OntologyManager
        om = OntologyManager()
        gsb = om.gui_schema_builder

        # Get statistics
        stats = gsb.get_statistics()

        if verbose:
            print_statistics_summary(stats, manager_name)

        # Validate structure
        expected_categories = {'configuration', 'execution', 'health'}
        struct_passed, struct_errors = validate_statistics_structure(
            stats, expected_categories, manager_name
        )

        for error in struct_errors:
            print_result(False, error)

        if struct_passed:
            print_result(True, "Statistics structure valid")

        # Validate JSON serializable
        json_passed, json_errors = validate_json_serializable(stats, manager_name)
        for error in json_errors:
            print_result(False, error)

        if json_passed:
            print_result(True, "Statistics JSON-serializable")

        # Validate counter types
        types_passed, types_errors = validate_counter_types(stats, manager_name, verbose)
        for error in types_errors:
            print_result(False, error)

        if types_passed:
            print_result(True, "Counter types valid")

        # Print key stats
        if not verbose:
            metadata_builds = stats['execution'].get('metadata_builds', {})
            print_info("Total metadata builds", metadata_builds.get('total_builds', 0))
            property_extraction = stats['execution'].get('property_extraction', {})
            avg_props = property_extraction.get('average_properties_per_class', 0)
            print_info("Average properties per class", f"{avg_props:.1f}")

        all_passed = struct_passed and json_passed and types_passed
        return all_passed, stats

    except Exception as e:
        print_result(False, f"Failed to test {manager_name}: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return False, {}


def test_dependency_manager(verbose: bool = False) -> Tuple[bool, Dict[str, Any]]:
    """
    Test DependencyManager statistics.

    Args:
        verbose: Show detailed output

    Returns:
        Tuple of (passed: bool, stats: dict)
    """
    manager_name = "DependencyManager"
    print_section(f"Testing {manager_name}")

    try:
        # Initialize
        om = OntologyManager()
        cm = ConstraintManager()
        dm = DependencyManager(cm)

        # Get statistics
        stats = dm.get_statistics()

        if verbose:
            print_statistics_summary(stats, manager_name)

        # Validate structure - now follows standard pattern
        expected_categories = {'configuration', 'execution', 'health'}
        struct_passed, struct_errors = validate_statistics_structure(
            stats, expected_categories, manager_name
        )

        for error in struct_errors:
            print_result(False, error)

        if struct_passed:
            print_result(True, "Statistics structure valid")

        # Validate JSON serializable
        json_passed, json_errors = validate_json_serializable(stats, manager_name)
        for error in json_errors:
            print_result(False, error)

        if json_passed:
            print_result(True, "Statistics JSON-serializable")

        # Validate counter types
        types_passed, types_errors = validate_counter_types(stats, manager_name, verbose)
        for error in types_errors:
            print_result(False, error)

        if types_passed:
            print_result(True, "Counter types valid")

        # Print key stats
        if not verbose:
            exec_stats = stats.get('execution', {})
            print_info("Total constraint evaluations", exec_stats.get('total_evaluations', 0))
            op_execs = exec_stats.get('operation_executions', {}).get('by_type', {})
            total_ops = sum(op_execs.values())
            print_info("Total operations executed", total_ops)

        all_passed = struct_passed and json_passed and types_passed
        return all_passed, stats

    except Exception as e:
        print_result(False, f"Failed to test {manager_name}: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return False, {}


def test_ontology_form_builder(verbose: bool = False) -> Tuple[bool, Dict[str, Any]]:
    """
    Test OntologyFormBuilder statistics.

    Args:
        verbose: Show detailed output

    Returns:
        Tuple of (passed: bool, stats: dict)
    """
    manager_name = "OntologyFormBuilder"
    print_section(f"Testing {manager_name}")

    try:
        # Initialize
        om = OntologyManager()
        ofb = OntologyFormBuilder(om)

        # Get statistics
        stats = ofb.get_statistics()

        if verbose:
            print_statistics_summary(stats, manager_name)

        # Validate structure
        expected_categories = {'configuration', 'execution', 'health'}
        struct_passed, struct_errors = validate_statistics_structure(
            stats, expected_categories, manager_name
        )

        for error in struct_errors:
            print_result(False, error)

        if struct_passed:
            print_result(True, "Statistics structure valid")

        # Validate JSON serializable
        json_passed, json_errors = validate_json_serializable(stats, manager_name)
        for error in json_errors:
            print_result(False, error)

        if json_passed:
            print_result(True, "Statistics JSON-serializable")

        # Validate counter types
        types_passed, types_errors = validate_counter_types(stats, manager_name, verbose)
        for error in types_errors:
            print_result(False, error)

        if types_passed:
            print_result(True, "Counter types valid")

        # Print key stats
        if not verbose:
            print_info("Total forms created", stats['execution'].get('total_forms_created', 0))

        all_passed = struct_passed and json_passed and types_passed
        return all_passed, stats

    except Exception as e:
        print_result(False, f"Failed to test {manager_name}: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return False, {}


def test_ontology_loader(verbose: bool = False) -> Tuple[bool, Dict[str, Any]]:
    """
    Test OntologyLoader statistics.

    Args:
        verbose: Show detailed output

    Returns:
        Tuple of (passed: bool, stats: dict)
    """
    manager_name = "OntologyLoader"
    print_section(f"Testing {manager_name}")

    try:
        # Initialize (loader is part of OntologyManager)
        om = OntologyManager()
        loader = om.loader

        # Get statistics
        stats = loader.get_statistics()

        if verbose:
            print_statistics_summary(stats, manager_name)

        # Validate structure
        expected_categories = {'configuration', 'execution', 'health'}
        struct_passed, struct_errors = validate_statistics_structure(
            stats, expected_categories, manager_name
        )

        for error in struct_errors:
            print_result(False, error)

        if struct_passed:
            print_result(True, "Statistics structure valid")

        # Validate JSON serializable
        json_passed, json_errors = validate_json_serializable(stats, manager_name)
        for error in json_errors:
            print_result(False, error)

        if json_passed:
            print_result(True, "Statistics JSON-serializable")

        # Validate counter types
        types_passed, types_errors = validate_counter_types(stats, manager_name, verbose)
        for error in types_errors:
            print_result(False, error)

        if types_passed:
            print_result(True, "Counter types valid")

        # Print key stats
        if not verbose:
            print_info("Files loaded", stats['execution'].get('files_loaded', 0))
            print_info("Total triples", stats['execution'].get('total_triples_added', 0))

        all_passed = struct_passed and json_passed and types_passed
        return all_passed, stats

    except Exception as e:
        print_result(False, f"Failed to test {manager_name}: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return False, {}


def test_ontology_manager(verbose: bool = False) -> Tuple[bool, Dict[str, Any]]:
    """
    Test OntologyManager statistics.

    Args:
        verbose: Show detailed output

    Returns:
        Tuple of (passed: bool, stats: dict)
    """
    manager_name = "OntologyManager"
    print_section(f"Testing {manager_name}")

    try:
        # Initialize
        om = OntologyManager()

        # Get statistics
        stats = om.get_statistics()

        if verbose:
            print_statistics_summary(stats, manager_name)

        # Validate structure - now follows standard pattern
        expected_categories = {'configuration', 'execution', 'health'}
        struct_passed, struct_errors = validate_statistics_structure(
            stats, expected_categories, manager_name
        )

        for error in struct_errors:
            print_result(False, error)

        if struct_passed:
            print_result(True, "Statistics structure valid")

        # Validate JSON serializable
        json_passed, json_errors = validate_json_serializable(stats, manager_name)
        for error in json_errors:
            print_result(False, error)

        if json_passed:
            print_result(True, "Statistics JSON-serializable")

        # Validate counter types
        types_passed, types_errors = validate_counter_types(stats, manager_name, verbose)
        for error in types_errors:
            print_result(False, error)

        if types_passed:
            print_result(True, "Counter types valid")

        # Print key stats
        if not verbose:
            content = stats.get('content', {}).get('ontology_data', {})
            print_info("Total classes", content.get('total_classes', 0))
            print_info("Total individuals", content.get('total_individuals', 0))

        all_passed = struct_passed and json_passed and types_passed
        return all_passed, stats

    except Exception as e:
        print_result(False, f"Failed to test {manager_name}: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return False, {}


def test_constraint_manager(verbose: bool = False) -> Tuple[bool, Dict[str, Any]]:
    """
    Test ConstraintManager statistics.

    Args:
        verbose: Show detailed output

    Returns:
        Tuple of (passed: bool, stats: dict)
    """
    manager_name = "ConstraintManager"
    print_section(f"Testing {manager_name}")

    try:
        # Initialize
        cm = ConstraintManager()

        # Get statistics
        stats = cm.get_statistics()

        if verbose:
            print_statistics_summary(stats, manager_name)

        # Validate structure - now follows standard pattern
        expected_categories = {'configuration', 'execution', 'health'}
        struct_passed, struct_errors = validate_statistics_structure(
            stats, expected_categories, manager_name
        )

        for error in struct_errors:
            print_result(False, error)

        if struct_passed:
            print_result(True, "Statistics structure valid")

        # Validate JSON serializable
        json_passed, json_errors = validate_json_serializable(stats, manager_name)
        for error in json_errors:
            print_result(False, error)

        if json_passed:
            print_result(True, "Statistics JSON-serializable")

        # Validate counter types
        types_passed, types_errors = validate_counter_types(stats, manager_name, verbose)
        for error in types_errors:
            print_result(False, error)

        if types_passed:
            print_result(True, "Counter types valid")

        # Print key stats
        if not verbose:
            config = stats.get('configuration', {})
            print_info("Total constraints", config.get('total_constraints', 0))
            print_info("Classes with constraints", config.get('classes_with_constraints', 0))

        all_passed = struct_passed and json_passed and types_passed
        return all_passed, stats

    except Exception as e:
        print_result(False, f"Failed to test {manager_name}: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return False, {}


def main():
    """Main entry point for statistics validation."""
    parser = argparse.ArgumentParser(
        description='Validate DynaMat manager statistics methods',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/validate_statistics.py
  python tools/validate_statistics.py --manager WidgetFactory
  python tools/validate_statistics.py --verbose
  python tools/validate_statistics.py --json
        """
    )

    parser.add_argument(
        '--manager', '-m',
        choices=[
            'WidgetFactory',
            'GUISchemaBuilder',
            'DependencyManager',
            'OntologyFormBuilder',
            'OntologyLoader',
            'OntologyManager',
            'ConstraintManager'
        ],
        help='Test a specific manager'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed output'
    )

    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results as JSON'
    )

    args = parser.parse_args()

    # Manager test functions
    manager_tests = {
        'WidgetFactory': test_widget_factory,
        'GUISchemaBuilder': test_gui_schema_builder,
        'DependencyManager': test_dependency_manager,
        'OntologyFormBuilder': test_ontology_form_builder,
        'OntologyLoader': test_ontology_loader,
        'OntologyManager': test_ontology_manager,
        'ConstraintManager': test_constraint_manager
    }

    # Determine which tests to run
    if args.manager:
        tests_to_run = {args.manager: manager_tests[args.manager]}
    else:
        tests_to_run = manager_tests

    # Run tests
    results = {}
    for manager_name, test_func in tests_to_run.items():
        passed, stats = test_func(args.verbose)
        results[manager_name] = {
            'passed': passed,
            'statistics': stats
        }

    # Output results
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        # Print summary
        print_section("Test Summary")

        passed_count = sum(1 for r in results.values() if r['passed'])
        total_count = len(results)

        for manager_name, result in results.items():
            print_result(result['passed'], manager_name)

        print(f"\n{passed_count}/{total_count} managers passed")

    # Exit with appropriate code
    all_passed = all(r['passed'] for r in results.values())
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
