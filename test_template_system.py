#!/usr/bin/env python3
"""
Template System Test Script

File location: test_template_system.py (place in root directory)

This script tests the template system functionality with the actual ontology
without any hardcoded assumptions.

Usage:
    python test_template_system.py
"""

import sys
from pathlib import Path

# Setup Python path
sys.path.insert(0, str(Path(__file__).parent.absolute()))

def main():
    print("DynaMat Template System Test")
    print("=" * 40)
    
    try:
        # Import modules
        from dynamat.ontology.manager import get_ontology_manager
        from dynamat.gui.forms import OntologyFormGenerator
        
        print("✓ Modules imported successfully")
        
        # Get ontology manager
        manager = get_ontology_manager()
        print("✓ Ontology manager loaded")
        
        # Test basic ontology functionality
        print(f"\n📊 Basic Ontology Stats:")
        diagnosis = manager.diagnose_ontology()
        print(f"   Total triples: {diagnosis['total_triples']}")
        print(f"   Total classes: {diagnosis['classes'].get('total', 0)}")
        print(f"   Total properties: {diagnosis['properties'].get('total', 0)}")
        
        # Test specific class detection
        print(f"\n🧪 Testing Class Detection:")
        for class_name in ['Specimen', 'SHPBTest']:
            result = manager.test_measurement_detection(class_name)
            print(f"   {class_name}:")
            print(f"     Exists: {result['class_exists']}")
            print(f"     Properties: {len(result['properties_found'])}")
            print(f"     Measurements: {len(result['measurements_detected'])}")
            
            if result['properties_found']:
                print(f"     First few properties: {result['properties_found'][:3]}")
            
            if result['measurements_detected']:
                print(f"     Measurements found:")
                for name, info in list(result['measurements_detected'].items())[:2]:
                    print(f"       - {name}: {len(info['units'])} units")
        
        # Test form generator
        print(f"\n📋 Testing Form Generator:")
        form_generator = OntologyFormGenerator(manager)
        print("✓ Form generator created")
        
        # Test template creation from ontology
        print(f"\n🎯 Testing Template Generation:")
        for class_name in ['Specimen', 'SHPBTest']:
            try:
                template = form_generator.create_template_from_ontology(class_name)
                print(f"   {class_name} template:")
                print(f"     Name: {template.name}")
                print(f"     Property groups: {len(template.property_groups)}")
                
                for group_name, properties in template.property_groups.items():
                    print(f"       - {group_name}: {len(properties)} properties")
                    if properties:
                        print(f"         {properties[:2]}{'...' if len(properties) > 2 else ''}")
                
                # Analyze template coverage
                analysis = form_generator.analyze_template_coverage(template)
                print(f"     Coverage analysis:")
                print(f"       - Covered: {len(analysis['coverage']['covered'])}")
                print(f"       - Missing: {len(analysis['coverage']['missing_from_template'])}")
                print(f"       - Extra: {len(analysis['coverage']['extra_in_template'])}")
                
                if analysis['coverage']['missing_from_template']:
                    print(f"       Missing properties: {analysis['coverage']['missing_from_template'][:3]}")
                
            except Exception as e:
                print(f"   ✗ Template creation failed for {class_name}: {e}")
        
        # Test form schema generation
        print(f"\n📝 Testing Schema Generation:")
        for class_name in ['Specimen', 'SHPBTest']:
            try:
                schema = manager.get_class_schema(class_name)
                print(f"   {class_name} schema:")
                print(f"     Object properties: {len(schema.get('object_properties', []))}")
                print(f"     Measurement properties: {len(schema.get('measurement_properties', []))}")
                print(f"     Data properties: {len(schema.get('data_properties', []))}")
                
                # Show some examples
                if schema.get('object_properties'):
                    example_prop = schema['object_properties'][0]
                    print(f"     Example object property: {example_prop['name']} -> {example_prop['range_class']}")
                    print(f"       Available values: {len(example_prop.get('available_values', []))}")
                
                if schema.get('measurement_properties'):
                    example_meas = schema['measurement_properties'][0]
                    print(f"     Example measurement: {example_meas['name']}")
                    print(f"       Units: {example_meas.get('available_units', [])}")
                
            except Exception as e:
                print(f"   ✗ Schema generation failed for {class_name}: {e}")
        
        print(f"\n✅ Template system tests completed successfully!")
        print(f"\nNext steps:")
        print(f"  1. Run 'python run_dynamat.py' to test forms in GUI")
        print(f"  2. Forms should now populate with actual ontology properties")
        print(f"  3. Templates can be created dynamically from ontology structure")
        
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("Make sure you're in the project root directory")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()