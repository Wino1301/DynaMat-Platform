"""
DynaMat Platform - TTL Validation Tool
Validate TTL files against SHACL shapes for data quality assurance.

This tool validates RDF/Turtle files against SHACL (Shapes Constraint Language)
validation shapes, providing detailed feedback on violations, warnings, and
informational issues.

Usage:
    python tools/validate_ttl.py specimen.ttl --class dyn:Specimen
    python tools/validate_ttl.py test.ttl --shape shapes/specimen_shapes.ttl
    python tools/validate_ttl.py specimen.ttl --class dyn:Specimen --verbose
"""

import sys
import argparse
import json
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Import dynamat modules directly now that it's an installable package
from dynamat.gui.core.form_validator import SHACLValidator, ValidationResult, ValidationSeverity
from dynamat.ontology import OntologyManager
from rdflib import Graph

NAMESPACES = {
    'dyn': 'https://dynamat.utep.edu/ontology#',
    'gui': 'https://dynamat.utep.edu/ontology/gui#',
}


def expand_uri(short_uri: str) -> str:
    """Expand short-form URI to full URI."""
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
    symbol = "[+]" if passed else "[!]"
    print(f"{symbol} {status}: {message}")


def print_info(label: str, value):
    """Print an info line."""
    print(f"  {label}: {value}")


def validate_ttl_file(
    ttl_file: Path,
    class_uri: Optional[str] = None,
    shape_file: Optional[Path] = None,
    verbose: bool = False,
    json_output: bool = False
) -> bool:
    """
    Validate a TTL file against SHACL shapes.

    Args:
        ttl_file: Path to TTL file to validate
        class_uri: Optional class URI to validate against (e.g., 'dyn:Specimen')
        shape_file: Optional path to specific SHACL shape file
        verbose: Show detailed validation results
        json_output: Output as JSON

    Returns:
        True if validation passed (conforms)
    """
    if not ttl_file.exists():
        if json_output:
            print(json.dumps({"error": f"File not found: {ttl_file}"}, indent=2))
        else:
            print(f"\nERROR: File not found: {ttl_file}")
        return False

    try:
        # Load the TTL file into a graph
        data_graph = Graph()
        data_graph.parse(str(ttl_file), format='turtle')

        if not json_output:
            print_section(f"TTL Validation - {ttl_file.name}")
            print_info("File", str(ttl_file))
            print_info("Triples loaded", len(data_graph))

        # Initialize validator
        om = OntologyManager()
        validator = SHACLValidator(om)

        # Determine validation scope
        if class_uri and not json_output:
            print_info("Target class", class_uri)

        if shape_file:
            if not shape_file.exists():
                error_msg = f"Shape file not found: {shape_file}"
                if json_output:
                    print(json.dumps({"error": error_msg}, indent=2))
                else:
                    print(f"\nERROR: {error_msg}")
                return False

            if not json_output:
                print_info("Shape file", str(shape_file))
        else:
            if not json_output:
                shapes_dir = PROJECT_ROOT / "src" / "dynamat" / "ontology" / "shapes"
                print_info("Using shapes from", str(shapes_dir))

        # Perform validation
        if not json_output:
            print("\nPerforming SHACL validation...")

        validation_result = validator.validate(data_graph)

        # Output results
        if json_output:
            result_data = {
                "file": str(ttl_file),
                "conforms": validation_result.conforms,
                "has_blocking_issues": validation_result.has_blocking_issues(),
                "has_any_issues": validation_result.has_any_issues(),
                "summary": {
                    "violations": len(validation_result.violations),
                    "warnings": len(validation_result.warnings),
                    "infos": len(validation_result.infos)
                },
                "issues": []
            }

            # Add all issues
            for issue in validation_result.violations:
                result_data["issues"].append({
                    "severity": "violation",
                    "message": issue.message,
                    "focus_node": issue.focus_node,
                    "result_path": issue.result_path,
                    "value": issue.value,
                    "source_shape": issue.source_shape if verbose else None
                })

            for issue in validation_result.warnings:
                result_data["issues"].append({
                    "severity": "warning",
                    "message": issue.message,
                    "focus_node": issue.focus_node,
                    "result_path": issue.result_path,
                    "value": issue.value,
                    "source_shape": issue.source_shape if verbose else None
                })

            for issue in validation_result.infos:
                result_data["issues"].append({
                    "severity": "info",
                    "message": issue.message,
                    "focus_node": issue.focus_node,
                    "result_path": issue.result_path,
                    "value": issue.value,
                    "source_shape": issue.source_shape if verbose else None
                })

            # Remove None values if not verbose
            if not verbose:
                for issue in result_data["issues"]:
                    issue.pop("source_shape", None)

            print(json.dumps(result_data, indent=2))

        else:
            # Human-readable output
            print_section("Validation Results")

            # Overall result
            if validation_result.conforms:
                print_result(True, "Validation PASSED - No issues found")
            elif validation_result.has_blocking_issues():
                print_result(False, "Validation FAILED - Blocking violations found")
            else:
                print_result(True, "Validation PASSED - No blocking issues (warnings/infos present)")

            # Summary
            print("\nSummary:")
            print_info("Violations (blocking)", len(validation_result.violations))
            print_info("Warnings (non-blocking)", len(validation_result.warnings))
            print_info("Infos (suggestions)", len(validation_result.infos))

            # Detailed results
            if validation_result.violations:
                print_subsection("VIOLATIONS (Blocking Issues)")
                for i, issue in enumerate(validation_result.violations, 1):
                    print(f"\n{i}. [!] {issue.message}")
                    if issue.focus_node:
                        print(f"   Focus: {issue.focus_node}")
                    if issue.result_path:
                        print(f"   Path: {issue.result_path}")
                    if issue.value:
                        print(f"   Value: {issue.value}")
                    if verbose and issue.source_shape:
                        print(f"   Shape: {issue.source_shape}")

            if validation_result.warnings:
                print_subsection("WARNINGS (Context-Specific Issues)")
                for i, issue in enumerate(validation_result.warnings, 1):
                    print(f"\n{i}. [*] {issue.message}")
                    if issue.focus_node:
                        print(f"   Focus: {issue.focus_node}")
                    if issue.result_path:
                        print(f"   Path: {issue.result_path}")
                    if issue.value:
                        print(f"   Value: {issue.value}")
                    if verbose and issue.source_shape:
                        print(f"   Shape: {issue.source_shape}")

            if validation_result.infos:
                print_subsection("INFOS (Suggestions)")
                for i, issue in enumerate(validation_result.infos, 1):
                    print(f"\n{i}. [i] {issue.message}")
                    if issue.focus_node:
                        print(f"   Focus: {issue.focus_node}")
                    if issue.result_path:
                        print(f"   Path: {issue.result_path}")
                    if issue.value:
                        print(f"   Value: {issue.value}")
                    if verbose and issue.source_shape:
                        print(f"   Shape: {issue.source_shape}")

            # Interpretation guide
            if validation_result.has_any_issues():
                print_subsection("Interpretation")
                if validation_result.has_blocking_issues():
                    print("  Violations MUST be fixed before saving this data.")
                    print("  These represent critical data integrity or format issues.")
                if validation_result.warnings:
                    print("  Warnings indicate context-specific issues that may be intentional.")
                    print("  Review each warning to determine if it needs correction.")
                if validation_result.infos:
                    print("  Infos are suggestions for best practices or optional improvements.")

        return not validation_result.has_blocking_issues()

    except Exception as e:
        if json_output:
            print(json.dumps({"error": str(e), "conforms": False}, indent=2))
        else:
            print(f"\nERROR: Validation failed: {e}")
            if verbose:
                import traceback
                traceback.print_exc()
        return False


def main():
    """Main entry point for the TTL validation tool."""
    parser = argparse.ArgumentParser(
        description='Validate DynaMat TTL files against SHACL shapes',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate a specimen file against its class shapes
  python tools/validate_ttl.py specimens/DYNML-AL6061-001/specimen.ttl --class dyn:Specimen

  # Validate against a specific shape file
  python tools/validate_ttl.py test.ttl --shape dynamat/ontology/shapes/specimen_shapes.ttl

  # Validate with detailed output showing constraint sources
  python tools/validate_ttl.py specimen.ttl --class dyn:Specimen --verbose

  # JSON output for CI/CD integration
  python tools/validate_ttl.py specimen.ttl --class dyn:Specimen --json

  # Validate without specifying class (uses all loaded shapes)
  python tools/validate_ttl.py data.ttl

Severity Levels:
  VIOLATION - Critical errors that block save (e.g., invalid format, required fields)
  WARNING   - Context-specific issues (e.g., shape mismatch, method parameters)
  INFO      - Best practice suggestions (e.g., optional metadata)

Exit Codes:
  0 - Validation passed (no violations)
  1 - Validation failed (violations present) or error occurred
        """
    )

    # Required arguments
    parser.add_argument('ttl_file', type=Path,
                       help='Path to TTL file to validate')

    # Optional arguments
    parser.add_argument('--class', '-c', dest='class_uri',
                       help='Class URI to validate against (e.g., dyn:Specimen, dyn:MechanicalTest)')

    parser.add_argument('--shape', '-s', dest='shape_file', type=Path,
                       help='Path to specific SHACL shape file to use for validation')

    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Show detailed validation results including constraint sources')

    parser.add_argument('--json', action='store_true',
                       help='Output results as JSON for scripting/automation')

    args = parser.parse_args()

    # Run validation
    passed = validate_ttl_file(
        ttl_file=args.ttl_file,
        class_uri=args.class_uri,
        shape_file=args.shape_file,
        verbose=args.verbose,
        json_output=args.json
    )

    # Exit with appropriate code (0 for pass, 1 for fail)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
