"""
DynaMat Platform - Constraint Validation Tool
Validates constraint loading and provides debugging information.

Usage:
    python tools/validate_constraints.py                                    # General overview
    python tools/validate_constraints.py --class-uri dyn:Specimen           # Test class
    python tools/validate_constraints.py --constraint-uri gui:specimen_c003 # Test constraint
    python tools/validate_constraints.py --verbose                          # Detailed output
    python tools/validate_constraints.py --json                             # JSON output
"""

import sys
import argparse
import json
from pathlib import Path

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dynamat.gui.dependencies import ConstraintManager


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
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def print_result(passed: bool, message: str):
    """Print a test result."""
    status = "PASS" if passed else "FAIL"
    print(f"{status}: {message}")


def test_all_constraints(verbose: bool = False) -> bool:
    """
    Test constraint loading across the entire system.

    Args:
        verbose: Show detailed output

    Returns:
        True if constraints loaded successfully
    """
    print_section("Constraint Validation - System Overview")

    try:
        cm = ConstraintManager()
        stats = cm.get_statistics()

        # Access via new unified structure
        config = stats.get('configuration', {})
        content = stats.get('content', {})

        total = config.get('total_constraints', 0)
        classes = config.get('classes_with_constraints', 0)

        print_result(total > 0, f"Total constraints loaded: {total}")
        print_result(classes > 0, f"Classes with constraints: {classes}")

        print("\nOperation breakdown:")
        operations = content.get('operations', {})
        for op_type, count in operations.items():
            print(f"  - {op_type}: {count}")

        if verbose:
            print(f"\nConstraint directory: {config.get('constraint_directory', 'N/A')}")

        return total > 0

    except Exception as e:
        print_result(False, f"Failed to load constraints: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return False


def test_class_constraints(class_uri: str, verbose: bool = False) -> bool:
    """
    Test constraints for a specific class.

    Args:
        class_uri: URI of the class (short or full form)
        verbose: Show detailed output

    Returns:
        True if class has constraints
    """
    full_uri = expand_uri(class_uri)
    print_section(f"Class Constraints - {class_uri}")

    try:
        cm = ConstraintManager()
        constraints = cm.get_constraints_for_class(full_uri)

        print_result(len(constraints) > 0, f"Total constraints: {len(constraints)}")

        if len(constraints) == 0:
            return False

        # Count by operation type
        ops = {
            'visibility': 0,
            'calculation': 0,
            'generation': 0,
            'filtering': 0,
            'population': 0
        }

        for c in constraints:
            if c.has_visibility_ops():
                ops['visibility'] += 1
            if c.has_calculation_op():
                ops['calculation'] += 1
            if c.has_generation_op():
                ops['generation'] += 1
            if c.has_filter_op():
                ops['filtering'] += 1
            if c.has_population_op():
                ops['population'] += 1

        print("\nOperation breakdown:")
        for op_type, count in ops.items():
            print(f"  - {op_type}: {count}")

        if verbose:
            print("\nDetailed constraint list:")
            for i, c in enumerate(constraints, 1):
                print(f"\n  [{i}] {c.label}")
                print(f"      URI: {c.uri}")
                print(f"      Triggers: {c.triggers}")
                print(f"      Priority: {c.priority}")

                operations = []
                if c.has_visibility_ops():
                    operations.append("visibility")
                if c.has_calculation_op():
                    operations.append("calculation")
                if c.has_generation_op():
                    operations.append("generation")
                if c.has_filter_op():
                    operations.append("filtering")

                print(f"      Operations: {', '.join(operations)}")

        return True

    except Exception as e:
        print_result(False, f"Failed to test class constraints: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return False


def test_specific_constraint(constraint_uri: str, verbose: bool = False) -> bool:
    """
    Test a specific constraint in detail.

    Args:
        constraint_uri: URI of the constraint (short or full form)
        verbose: Show detailed output

    Returns:
        True if constraint loaded and validated successfully
    """
    full_uri = expand_uri(constraint_uri)
    print_section(f"Specific Constraint - {constraint_uri}")

    try:
        cm = ConstraintManager()
        constraint = cm.get_constraint(full_uri)

        if not constraint:
            print_result(False, "Constraint not found!")
            return False

        print_result(True, f"Constraint loaded: {constraint.label}")

        print("\nConstraint Details:")
        print(f"  URI: {constraint.uri}")
        print(f"  Label: {constraint.label}")
        print(f"  For class: {constraint.for_class}")
        print(f"  Priority: {constraint.priority}")

        print(f"\n  Triggers: {constraint.triggers}")
        print(f"  Trigger logic: {constraint.trigger_logic}")
        print(f"  When values: {constraint.when_values}")

        # Show operations
        operations = []

        if constraint.has_visibility_ops():
            operations.append("visibility")
            if verbose:
                if constraint.show_fields:
                    print(f"\n  Show fields: {constraint.show_fields}")
                if constraint.hide_fields:
                    print(f"  Hide fields: {constraint.hide_fields}")

        if constraint.has_calculation_op():
            operations.append("calculation")
            if verbose:
                print(f"\n  Calculation function: {constraint.calculation_function}")
                print(f"  Calculation target: {constraint.calculation_target}")
                print(f"  Calculation inputs: {constraint.calculation_inputs}")

        if constraint.has_generation_op():
            operations.append("generation")
            if verbose:
                print(f"\n  Generation template: {constraint.generation_template}")
                print(f"  Generation target: {constraint.generation_target}")
                print(f"  Generation inputs: {constraint.generation_inputs}")

        if constraint.has_filter_op():
            operations.append("filtering")
            print(f"\n  Exclude classes: {constraint.exclude_classes}")
            print(f"  Filter by classes: {constraint.filter_by_classes}")
            print(f"  Apply to fields: {constraint.apply_to_fields}")

        if constraint.has_population_op():
            operations.append("population")
            if verbose:
                print(f"\n  Populate fields: {constraint.populate_fields}")
                print(f"  Make read-only: {constraint.make_read_only}")

        print(f"\n  Operations: {', '.join(operations)}")

        if constraint.comment and verbose:
            print(f"\n  Comment: {constraint.comment}")

        # Validation checks
        print("\nValidation Checks:")
        checks_passed = True

        # Check that constraint has at least one operation
        if not operations:
            print_result(False, "No operations defined")
            checks_passed = False
        else:
            print_result(True, f"{len(operations)} operation(s) defined")

        # Check triggers exist
        if not constraint.triggers:
            print_result(False, "No triggers defined")
            checks_passed = False
        else:
            print_result(True, f"{len(constraint.triggers)} trigger(s) defined")

        # Specific checks for filter operations
        if constraint.has_filter_op():
            if not constraint.apply_to_fields:
                print_result(False, "Filter operation but no target fields")
                checks_passed = False
            else:
                print_result(True, f"Filter applies to {len(constraint.apply_to_fields)} field(s)")

            if not constraint.exclude_classes and not constraint.filter_by_classes:
                print_result(False, "Filter operation but no filter criteria")
                checks_passed = False
            else:
                print_result(True, "Filter criteria defined")

        return checks_passed

    except Exception as e:
        print_result(False, f"Failed to test constraint: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return False


def main():
    """Main entry point for constraint validation."""
    parser = argparse.ArgumentParser(
        description='Validate DynaMat constraint loading and configuration',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/validate_constraints.py
  python tools/validate_constraints.py --class-uri dyn:Specimen
  python tools/validate_constraints.py --constraint-uri gui:specimen_c003
  python tools/validate_constraints.py --class-uri dyn:Specimen --verbose
        """
    )

    parser.add_argument(
        '--class-uri', '-c',
        help='Test constraints for a specific class (e.g., dyn:Specimen)'
    )

    parser.add_argument(
        '--constraint-uri', '-u',
        help='Test a specific constraint (e.g., gui:specimen_c003)'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed output for debugging'
    )

    parser.add_argument(
        '--json',
        action='store_true',
        help='Output constraint statistics in JSON format'
    )

    args = parser.parse_args()

    # Handle JSON output mode
    if args.json:
        try:
            cm = ConstraintManager()
            stats = cm.get_statistics()
            print(json.dumps(stats, indent=2))
            sys.exit(0)
        except Exception as e:
            error_output = {"error": str(e)}
            print(json.dumps(error_output, indent=2))
            sys.exit(1)

    # Track results
    results = []

    # If no specific tests requested, run general overview
    if not args.class_uri and not args.constraint_uri:
        results.append(("System Overview", test_all_constraints(args.verbose)))
    else:
        # Run requested tests
        if args.class_uri:
            results.append(
                (f"Class: {args.class_uri}",
                 test_class_constraints(args.class_uri, args.verbose))
            )

        if args.constraint_uri:
            results.append(
                (f"Constraint: {args.constraint_uri}",
                 test_specific_constraint(args.constraint_uri, args.verbose))
            )

    # Print summary
    print_section("Test Summary")

    for test_name, passed in results:
        print_result(passed, test_name)

    all_passed = all(result[1] for result in results)

    if all_passed:
        print("\nAll tests passed!")
        sys.exit(0)
    else:
        print("\nSome tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
