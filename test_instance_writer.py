"""
Test script for InstanceWriter
Demonstrates how to use the instance writer with example specimen data
"""

from pathlib import Path

# Import using proper package structure
from dynamat.ontology.core.namespace_manager import NamespaceManager
from dynamat.gui.parsers.instance_writer import InstanceWriter

def test_specimen_instance():
    """Test creating a specimen TTL file"""

    # Initialize namespace manager
    ns_manager = NamespaceManager()

    # Initialize instance writer
    writer = InstanceWriter(ns_manager)

    # Example form data (simulating what FormDataHandler.extract_form_data() returns)
    specimen_form_data = {
        # Ontology properties (will be included)
        "https://dynamat.utep.edu/ontology#hasSpecimenID": "SPN-AL6061-001",
        "https://dynamat.utep.edu/ontology#hasMaterial": "https://dynamat.utep.edu/ontology#Al6061_T6",
        "https://dynamat.utep.edu/ontology#hasOriginalDiameter": {
            'value': 6.35,
            'unit': 'http://qudt.org/vocab/unit/MilliM',
            'unit_symbol': 'mm'
        },
        "https://dynamat.utep.edu/ontology#hasOriginalLength": {
            'value': 10.0,
            'unit': 'http://qudt.org/vocab/unit/MilliM',
            'unit_symbol': 'mm'
        },
        "https://dynamat.utep.edu/ontology#hasOriginalMass": {
            'value': 0.851,
            'unit': 'http://qudt.org/vocab/unit/GRAM',
            'unit_symbol': 'g'
        },
        "https://dynamat.utep.edu/ontology#hasCreationDate": "2025-01-15",
        "https://dynamat.utep.edu/ontology#hasManufacturingMethod": "Machining",
        "https://dynamat.utep.edu/ontology#hasSurfaceFinish": "Polished",

        # GUI properties (should be filtered out - using gui: namespace)
        "https://dynamat.utep.edu/ontology/gui#hasDisplayName": "Original Diameter (mm)",
        "https://dynamat.utep.edu/ontology/gui#hasFormGroup": "GeometryDimensions",
    }

    # Write instance
    print("Creating specimen instance...")
    try:
        output_path = writer.write_instance(
            class_uri="https://dynamat.utep.edu/ontology#Specimen",
            instance_id="SPN-AL6061-001",
            form_data=specimen_form_data,
            notes="Test specimen created via InstanceWriter"
        )

        print(f"✓ Successfully created: {output_path}")

        # Read and display the file
        if output_path:
            with open(output_path, 'r') as f:
                print("\n" + "="*60)
                print("Generated TTL file:")
                print("="*60)
                print(f.read())
                print("="*60)

        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Testing InstanceWriter...")
    print()
    success = test_specimen_instance()
    print()
    if success:
        print("✓ Test completed successfully!")
    else:
        print("✗ Test failed!")
