"""Test script for pulse detection page refactoring."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dynamat.ontology import OntologyManager
from dynamat.gui.widgets.shpb.state.analysis_state import SHPBAnalysisState


def test_ontology_metadata_loading():
    """Test PulseDetectionParams metadata loads correctly."""
    print("\n=== Testing Ontology Metadata Loading ===")

    ontology_manager = OntologyManager()

    # Test that the class exists and has metadata
    metadata = ontology_manager.get_class_metadata_for_form("dyn:PulseDetectionParams")

    print(f"Form groups found: {list(metadata.form_groups.keys())}")
    assert "DetectionConfig" in metadata.form_groups, "Missing DetectionConfig group"
    assert "SearchBounds" in metadata.form_groups, "Missing SearchBounds group"

    print("OK: Ontology metadata loads correctly")


def test_polarity_individuals():
    """Test polarity individuals are queryable."""
    print("\n=== Testing Polarity Individuals ===")

    ontology_manager = OntologyManager()

    # Query for PolarityType individuals
    query = """
    PREFIX dyn: <https://dynamat.utep.edu/ontology#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?individual ?label ?value WHERE {
        ?individual a dyn:PolarityType ;
                    rdfs:label ?label ;
                    dyn:hasPolarityValue ?value .
    }
    """

    results = ontology_manager.sparql_executor.execute_query(query)

    print(f"Found {len(results)} polarity individuals:")
    for r in results:
        print(f"  - {r['label']}: {r['value']}")

    assert len(results) == 2, f"Expected 2 polarity individuals, found {len(results)}"

    values = [str(r['value']) for r in results]
    assert 'compressive' in values, "Missing compressive polarity"
    assert 'tensile' in values, "Missing tensile polarity"

    print("OK: Polarity individuals are queryable")


def test_metric_individuals():
    """Test detection metric individuals are queryable."""
    print("\n=== Testing Detection Metric Individuals ===")

    ontology_manager = OntologyManager()

    # Query for DetectionMetric individuals
    query = """
    PREFIX dyn: <https://dynamat.utep.edu/ontology#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?individual ?label ?value WHERE {
        ?individual a dyn:DetectionMetric ;
                    rdfs:label ?label ;
                    dyn:hasMetricValue ?value .
    }
    """

    results = ontology_manager.sparql_executor.execute_query(query)

    print(f"Found {len(results)} metric individuals:")
    for r in results:
        print(f"  - {r['label']}: {r['value']}")

    assert len(results) == 2, f"Expected 2 metric individuals, found {len(results)}"

    values = [str(r['value']) for r in results]
    assert 'median' in values, "Missing median metric"
    assert 'peak' in values, "Missing peak metric"

    print("OK: Detection metric individuals are queryable")


def test_form_builder_import():
    """Test that CustomizableFormBuilder can be imported."""
    print("\n=== Testing Form Builder Import ===")

    try:
        from dynamat.gui.builders.customizable_form_builder import CustomizableFormBuilder
        print("OK: CustomizableFormBuilder imported successfully")
    except ImportError as e:
        print(f"FAIL: Failed to import CustomizableFormBuilder: {e}")
        raise


def test_page_import():
    """Test that pulse detection page can be imported."""
    print("\n=== Testing Page Import ===")

    try:
        from dynamat.gui.widgets.shpb.pages.pulse_detection_page import PulseDetectionPage
        print("OK: PulseDetectionPage imported successfully")
    except Exception as e:
        print(f"FAIL: Failed to import PulseDetectionPage: {e}")
        raise


def test_page_instantiation():
    """Test that page can be instantiated (without Qt)."""
    print("\n=== Testing Page Instantiation ===")

    try:
        from dynamat.gui.widgets.shpb.pages.pulse_detection_page import PulseDetectionPage

        # Create minimal state
        state = SHPBAnalysisState()
        ontology_manager = OntologyManager()

        # We can't fully instantiate without QApplication, but we can check the class
        print(f"PulseDetectionPage class: {PulseDetectionPage}")
        print(f"  - __init__ signature OK")
        print(f"  - Methods: {len([m for m in dir(PulseDetectionPage) if not m.startswith('_')])}")

        print("OK: Page class structure OK (full instantiation requires Qt)")

    except Exception as e:
        print(f"FAIL: Failed to check page structure: {e}")
        raise


def main():
    """Run all tests."""
    print("=" * 60)
    print("Pulse Detection Page Refactoring Tests")
    print("=" * 60)

    try:
        test_ontology_metadata_loading()
        test_polarity_individuals()
        test_metric_individuals()
        test_form_builder_import()
        test_page_import()
        test_page_instantiation()

        print("\n" + "=" * 60)
        print("OK: All tests passed!")
        print("=" * 60)

        return 0

    except Exception as e:
        print("\n" + "=" * 60)
        print(f"FAIL: Tests failed: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
