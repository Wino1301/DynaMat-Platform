#!/usr/bin/env python3
"""
DynaMat Ontology Diagnostic Tool

File location: diagnose_ontology.py (place in root directory)

This script analyzes your ontology and tells you exactly what needs to be
added in Protégé to make the forms work properly.

Usage:
    python diagnose_ontology.py
"""

import sys
from pathlib import Path

# Setup Python path
sys.path.insert(0, str(Path(__file__).parent.absolute()))

try:
    from dynamat.ontology.manager import get_ontology_manager
except ImportError:
    print("Error: Could not import ontology manager. Make sure you're in the project root directory.")
    sys.exit(1)

def main():
    print("DynaMat Ontology Diagnostic Tool")
    print("=" * 50)
    
    try:
        # Get ontology manager
        manager = get_ontology_manager()
        print("✓ Ontology loaded successfully")
        
        # Run diagnosis
        diagnosis = manager.diagnose_ontology()
        
        print(f"\n📊 Ontology Overview:")
        print(f"   Total triples: {diagnosis['total_triples']}")
        print(f"   Total classes: {diagnosis['classes'].get('total', 0)}")
        print(f"   Total properties: {diagnosis['properties'].get('total', 0)}")
        
        # Check essential classes
        print(f"\n🏷️  Essential Classes Status:")
        essential_classes = ['Specimen', 'SHPBTest', 'Material', 'Structure', 'Shape', 'SpecimenRole']
        for class_name in essential_classes:
            status = "✓" if diagnosis['classes'].get(class_name, False) else "✗"
            print(f"   {status} {class_name}")
        
        # Check essential properties
        print(f"\n🔗 Essential Properties Status:")
        essential_properties = ['hasMaterial', 'hasStructure', 'hasDimension', 'hasShape', 'hasSpecimenRole']
        for prop_name in essential_properties:
            status = "✓" if diagnosis['properties'].get(prop_name, False) else "✗"
            print(f"   {status} {prop_name}")
        
        # Test specimen schema generation
        print(f"\n🧪 Testing Form Schema Generation:")
        try:
            specimen_schema = manager.get_class_schema("Specimen")
            print(f"   ✓ Specimen schema generated")
            print(f"     - Object properties: {len(specimen_schema['object_properties'])}")
            print(f"     - Measurement properties: {len(specimen_schema['measurement_properties'])}")
            print(f"     - Data properties: {len(specimen_schema['data_properties'])}")
            
            if specimen_schema['object_properties']:
                print(f"   📝 Found object properties:")
                for prop in specimen_schema['object_properties']:
                    available_count = len(prop['available_values'])
                    print(f"     - {prop['name']}: {available_count} options")
            
            if specimen_schema['measurement_properties']:
                print(f"   📏 Found measurement properties:")
                for prop in specimen_schema['measurement_properties']:
                    units_count = len(prop['available_units'])
                    print(f"     - {prop['name']}: {units_count} units")
            
        except Exception as e:
            print(f"   ✗ Specimen schema generation failed: {e}")
        
        # Test SHPB schema generation
        try:
            shpb_schema = manager.get_class_schema("SHPBTest")
            print(f"   ✓ SHPBTest schema generated")
            print(f"     - Object properties: {len(shpb_schema['object_properties'])}")
            print(f"     - Measurement properties: {len(shpb_schema['measurement_properties'])}")
            print(f"     - Data properties: {len(shpb_schema['data_properties'])}")
        except Exception as e:
            print(f"   ✗ SHPBTest schema generation failed: {e}")
        
        # Check for individuals
        print(f"\n👥 Individual Instances:")
        try:
            materials = manager.get_materials()
            print(f"   Materials: {len(materials)} found")
            if materials:
                for name in list(materials.keys())[:5]:  # Show first 5
                    print(f"     - {name}")
                if len(materials) > 5:
                    print(f"     ... and {len(materials) - 5} more")
        except Exception as e:
            print(f"   ✗ Could not retrieve materials: {e}")
        
        # Show missing essentials
        if diagnosis['missing_essentials']:
            print(f"\n❌ Missing Essential Elements:")
            for missing in diagnosis['missing_essentials']:
                print(f"   - {missing}")
        
        # Provide recommendations
        print(f"\n💡 Recommendations for Protégé:")
        print_protege_recommendations(diagnosis)
        
        # Test the fixed methods
        print(f"\n🧪 Testing Fixed Methods:")
        test_fixed_methods(manager)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

def print_protege_recommendations(diagnosis):
    """Print specific recommendations for what to add in Protégé"""
    
    print("\n  📌 Essential Classes to Add/Verify:")
    essential_classes = {
        'Specimen': 'Main specimen class for test samples',
        'SHPBTest': 'Split Hopkinson Pressure Bar test class',
        'Material': 'Material types (Al6061, SS316, etc.)',
        'Structure': 'Structure types (Solid, Cellular, Lattice)',
        'Shape': 'Specimen shapes (Cylindrical, Rectangular)',
        'SpecimenRole': 'Specimen roles (Test, Calibration)',
        'Unit': 'Measurement units',
        'Geometry': 'Geometric measurements',
        'TestingConditions': 'Test setup conditions'
    }
    
    for class_name, description in essential_classes.items():
        status = "✓" if diagnosis['classes'].get(class_name, False) else "➕"
        print(f"     {status} {class_name}: {description}")
    
    print("\n  📌 Essential Properties to Add/Verify:")
    essential_properties = {
        'hasMaterial': 'Specimen → Material (Object Property)',
        'hasStructure': 'Specimen → Structure (Object Property)', 
        'hasShape': 'Specimen → Shape (Object Property)',
        'hasSpecimenRole': 'Specimen → SpecimenRole (Object Property)',
        'hasDimension': 'Specimen → Geometry (Object Property)',
        'hasValue': 'Geometry → float (Data Property)',
        'hasUnits': 'Geometry → Unit (Object Property)',
        'performedOn': 'SHPBTest → Specimen (Object Property)',
        'hasTestingConditions': 'SHPBTest → TestingConditions (Object Property)'
    }
    
    for prop_name, description in essential_properties.items():
        status = "✓" if diagnosis['properties'].get(prop_name, False) else "➕"
        print(f"     {status} {prop_name}: {description}")
    
    print("\n  📌 Individual Instances to Add:")
    instances_to_add = {
        'Materials': ['Al6061', 'Al7075', 'SS316', 'Ti6Al4V'],
        'Structures': ['Solid', 'Cellular', 'Lattice'],
        'Shapes': ['Cylindrical', 'Rectangular', 'Square'],
        'SpecimenRoles': ['TestSpecimen', 'CalibrationSpecimen'],
        'Units_Length': ['mm', 'inch', 'm', 'cm'],
        'Units_Pressure': ['MPa', 'GPa', 'Pa', 'psi'],
        'Units_Temperature': ['DegreesCelsius', 'DegreesFahrenheit', 'Kelvin']
    }
    
    for category, instances in instances_to_add.items():
        print(f"     ➕ {category}: {', '.join(instances)}")

def test_fixed_methods(manager):
    """Test the fixed measurement path methods"""
    
    try:
        print("   📏 Testing measurement paths for Specimen...")
        measurements = manager.get_measurement_paths("Specimen")
        if measurements:
            print(f"     ✓ Found {len(measurements)} measurement properties:")
            for name, info in measurements.items():
                units_str = ', '.join(info['units'][:3])  # Show first 3 units
                if len(info['units']) > 3:
                    units_str += f" (+{len(info['units'])-3} more)"
                print(f"       - {name}: [{units_str}]")
        else:
            print("     ⚠️  No measurement properties found")
    
    except Exception as e:
        print(f"     ✗ Measurement path test failed: {e}")
    
    try:
        print("   🧪 Testing specific class detection...")
        specimen_test = manager.test_measurement_detection("Specimen")
        print(f"     ✓ Specimen class exists: {specimen_test['class_exists']}")
        print(f"     ✓ Properties found: {len(specimen_test['properties_found'])}")
        if specimen_test['properties_found']:
            for prop in specimen_test['properties_found'][:5]:  # Show first 5
                print(f"       - {prop}")
        
        print(f"     ✓ Measurements detected: {len(specimen_test['measurements_detected'])}")
        
        print(f"     ✓ Individual classes with instances:")
        for class_name, individuals in specimen_test['individuals_found'].items():
            if individuals:
                print(f"       - {class_name}: {len(individuals)} instances")
        
    except Exception as e:
        print(f"     ✗ Class detection test failed: {e}")
    
    try:
        print("   🔬 Testing SHPB class...")
        shpb_test = manager.test_measurement_detection("SHPBTest")
        print(f"     ✓ SHPBTest class exists: {shpb_test['class_exists']}")
        print(f"     ✓ Properties found: {len(shpb_test['properties_found'])}")
        print(f"     ✓ Measurements detected: {len(shpb_test['measurements_detected'])}")
        
    except Exception as e:
        print(f"     ✗ SHPB test failed: {e}")

if __name__ == "__main__":
    main()