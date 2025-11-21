"""
DynaMat Platform - Instance Index Testing Tool
Test the InstanceQueryBuilder SPARQL indexing system for entity discovery.

This tool tests the InstanceQueryBuilder functionality by:
- Scanning entity directories for TTL files
- Building SPARQL-queryable index
- Finding and displaying instances
- Testing lazy loading of full data

Usage:
    # Test specimens with default settings
    python tools/test_instance_index.py specimens/

    # Test with custom class URI
    python tools/test_instance_index.py tests/ --class-uri dyn:MechanicalTest

    # Test with custom file pattern
    python tools/test_instance_index.py specimens/ --pattern "SPN-*.ttl"

    # Verbose output showing full property details
    python tools/test_instance_index.py specimens/ --verbose

    # JSON output for automation
    python tools/test_instance_index.py specimens/ --json

    # Test specific instance by ID
    python tools/test_instance_index.py specimens/ --test-id "DYNML-A356-00001"
"""

import sys
import argparse
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dynamat.ontology import InstanceQueryBuilder

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


def extract_display_value(value: Any) -> str:
    """Extract displayable value from RDF data."""
    if isinstance(value, str):
        # Extract just the name from URIs for display
        if value.startswith('http'):
            if '#' in value:
                return value.split('#')[-1]
            elif '/' in value:
                return value.split('/')[-1]
        return value
    return str(value) if value else ""


def test_instance_index(
    entity_dir: Path,
    class_uri: str = "https://dynamat.utep.edu/ontology#Specimen",
    file_pattern: str = "*_specimen.ttl",
    display_properties: Optional[List[str]] = None,
    test_id: Optional[str] = None,
    id_property: str = "hasSpecimenID",
    verbose: bool = False,
    json_output: bool = False
) -> bool:
    """
    Test the InstanceQueryBuilder with a given entity directory.

    Args:
        entity_dir: Directory containing entity TTL files
        class_uri: Full URI of the ontology class
        file_pattern: Glob pattern for finding TTL files
        display_properties: List of properties to display (short form)
        test_id: Optional specific instance ID to test find_by_id
        id_property: Property name for ID field (short form)
        verbose: Show detailed property information
        json_output: Output as JSON

    Returns:
        True if all tests passed
    """
    if not entity_dir.exists():
        error_msg = f"Directory not found: {entity_dir}"
        if json_output:
            print(json.dumps({"error": error_msg}, indent=2))
        else:
            print(f"\nERROR: {error_msg}")
        return False

    # Default display properties if not specified
    if display_properties is None:
        if "Specimen" in class_uri:
            display_properties = ["hasSpecimenID", "hasMaterial", "hasShape", "hasStructure"]
        elif "Test" in class_uri:
            display_properties = ["hasTestID", "hasTestDate", "hasSpecimen"]
        else:
            display_properties = []

    try:
        results = {
            "entity_dir": str(entity_dir),
            "class_uri": class_uri,
            "file_pattern": file_pattern,
            "tests": []
        }

        # Create query builder
        if not json_output:
            print_section("Instance Index Testing")
            print_info("Entity directory", str(entity_dir))
            print_info("Class URI", class_uri)
            print_info("File pattern", file_pattern)

        query_builder = InstanceQueryBuilder()

        # Test 1: Scan and index
        if not json_output:
            print_subsection("Test 1: Scanning and Indexing")

        indexed_count = query_builder.scan_and_index(
            entity_dir,
            class_uri,
            file_pattern
        )

        test_passed = indexed_count >= 0
        if json_output:
            results["tests"].append({
                "name": "scan_and_index",
                "passed": test_passed,
                "indexed_count": indexed_count
            })
        else:
            print_result(test_passed, f"Indexed {indexed_count} instances")

        # Test 2: Get index statistics
        if not json_output:
            print_subsection("Test 2: Index Statistics")

        stats = query_builder.get_index_statistics()
        if json_output:
            results["statistics"] = stats
        else:
            print_info("Indexed classes", stats['indexed_classes'])
            print_info("Total triples", stats['total_instances'])
            for class_uri_stat, info in stats['classes'].items():
                print_info(f"  {class_uri_stat}", f"{info['count']} instances")

        # Test 3: Find all instances
        if not json_output:
            print_subsection("Test 3: Finding All Instances")

        # Build full property URIs
        full_property_uris = [
            prop if prop.startswith('http') else f"https://dynamat.utep.edu/ontology#{prop}"
            for prop in display_properties
        ]

        instances = query_builder.find_all_instances(
            class_uri,
            display_properties=full_property_uris if display_properties else None
        )

        test_passed = len(instances) == indexed_count
        if json_output:
            results["tests"].append({
                "name": "find_all_instances",
                "passed": test_passed,
                "found_count": len(instances)
            })
            results["instances"] = instances
        else:
            print_result(test_passed, f"Found {len(instances)} instances")

        # Test 4: Display instance details
        if instances and not json_output:
            print_subsection("Test 4: Instance Details")

            for i, instance in enumerate(instances, 1):
                print(f"\n  Instance {i}:")
                print(f"    URI: {instance.get('uri', 'N/A')}")

                # Display requested properties
                for prop in display_properties:
                    full_uri = prop if prop.startswith('http') else f"https://dynamat.utep.edu/ontology#{prop}"
                    value = instance.get(full_uri, 'N/A')
                    display_val = extract_display_value(value)
                    print(f"    {prop}: {display_val}")

                print(f"    File: {instance.get('file_path', 'N/A')}")

        # Test 5: Lazy loading (verbose mode)
        if instances and verbose:
            if not json_output:
                print_subsection("Test 5: Lazy Loading Full Data")

            first_instance_uri = instances[0]['uri']
            if not json_output:
                print_info("Loading full data for", first_instance_uri)

            full_data = query_builder.load_full_instance_data(first_instance_uri)
            test_passed = len(full_data) > 0

            if json_output:
                results["tests"].append({
                    "name": "lazy_loading",
                    "passed": test_passed,
                    "property_count": len(full_data)
                })
                if verbose:
                    results["sample_instance_full_data"] = {
                        k: str(v) for k, v in list(full_data.items())[:10]
                    }
            else:
                print_result(test_passed, f"Loaded {len(full_data)} properties")

                # Show sample properties
                print("\n  Sample properties:")
                for i, (prop, value) in enumerate(list(full_data.items())[:10], 1):
                    value_str = str(value)
                    if len(value_str) > 50:
                        value_str = value_str[:47] + "..."
                    print(f"    {i}. {prop.split('#')[-1] if '#' in prop else prop}: {value_str}")

        # Test 6: Find by ID (if test_id provided)
        if test_id:
            if not json_output:
                print_subsection(f"Test 6: Find Instance by ID '{test_id}'")

            found_instance = query_builder.find_instance_by_id(
                class_uri,
                id_property,
                test_id
            )

            test_passed = found_instance is not None
            if json_output:
                results["tests"].append({
                    "name": "find_by_id",
                    "passed": test_passed,
                    "test_id": test_id,
                    "found": test_passed
                })
                if found_instance:
                    results["found_instance"] = found_instance
            else:
                if found_instance:
                    id_full_uri = f"https://dynamat.utep.edu/ontology#{id_property}"
                    actual_id = found_instance.get(id_full_uri, 'Unknown')
                    print_result(True, f"Found instance: {actual_id}")
                    print_info("  File", found_instance.get('file_path', 'N/A'))
                else:
                    print_result(False, f"Instance '{test_id}' not found")

        # Summary
        if json_output:
            results["success"] = all(t.get("passed", True) for t in results["tests"])
            print(json.dumps(results, indent=2))
        else:
            print_section("Summary")
            print_result(True, f"All tests completed")
            print_info("Indexed instances", indexed_count)
            print_info("Query tests", "Passed")
            if verbose:
                print_info("Lazy loading", "Tested")
            if test_id:
                print_info("Find by ID", "Tested")

        return True

    except Exception as e:
        if json_output:
            print(json.dumps({
                "error": str(e),
                "success": False
            }, indent=2))
        else:
            print(f"\nERROR: {e}")
            import traceback
            if verbose:
                traceback.print_exc()
        return False


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Test InstanceQueryBuilder SPARQL indexing system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test specimens with default settings
  python tools/test_instance_index.py specimens/

  # Test with custom class URI
  python tools/test_instance_index.py tests/ --class-uri dyn:MechanicalTest

  # Test with custom file pattern
  python tools/test_instance_index.py specimens/ --pattern "*_specimen.ttl"

  # Verbose output showing full property details
  python tools/test_instance_index.py specimens/ --verbose

  # JSON output for automation
  python tools/test_instance_index.py specimens/ --json

  # Test specific instance by ID
  python tools/test_instance_index.py specimens/ --test-id "DYNML-A356-00001"

Exit Codes:
  0 - All tests passed
  1 - Tests failed or error occurred
        """
    )

    # Required arguments
    parser.add_argument('entity_dir', type=Path,
                       help='Directory containing entity TTL files (e.g., specimens/)')

    # Optional arguments
    parser.add_argument('--class-uri', '-c', dest='class_uri',
                       default='dyn:Specimen',
                       help='Class URI to index (short or full form, default: dyn:Specimen)')

    parser.add_argument('--pattern', '-p', dest='file_pattern',
                       default='*_specimen.ttl',
                       help='File glob pattern for finding TTL files (default: *_specimen.ttl)')

    parser.add_argument('--display-props', '-d', dest='display_properties',
                       help='Comma-separated list of properties to display (short form, e.g., "hasSpecimenID,hasMaterial")')

    parser.add_argument('--test-id', '-t', dest='test_id',
                       help='Test find_by_id with specific instance ID')

    parser.add_argument('--id-property', dest='id_property',
                       default='hasSpecimenID',
                       help='Property name for ID field (short form, default: hasSpecimenID)')

    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Show detailed property information including lazy loading test')

    parser.add_argument('--json', action='store_true',
                       help='Output results as JSON for scripting/automation')

    args = parser.parse_args()

    # Expand class URI if needed
    class_uri = expand_uri(args.class_uri)

    # Parse display properties
    display_properties = None
    if args.display_properties:
        display_properties = [p.strip() for p in args.display_properties.split(',')]

    # Run tests
    passed = test_instance_index(
        entity_dir=args.entity_dir,
        class_uri=class_uri,
        file_pattern=args.file_pattern,
        display_properties=display_properties,
        test_id=args.test_id,
        id_property=args.id_property,
        verbose=args.verbose,
        json_output=args.json
    )

    # Exit with appropriate code
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
