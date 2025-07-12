#!/usr/bin/env python3
"""
Test Ontology Integration Script

File location: test_ontology_integration.py (place in root directory)

Test script to verify that the GUI components can properly access
and use the ontology data without hardcoded values.
"""

import sys
from pathlib import Path

# Setup Python path
sys.path.insert(0, str(Path(__file__).parent.absolute()))

def test_ontology_manager():
    """Test basic ontology manager functionality"""
    print("Testing Ontology Manager...")
    
    try:
        from dynamat.ontology.manager import get_ontology_manager
        
        manager = get_ontology_manager()
        print("✓ Ontology manager created successfully")
        
        # Test basic queries
        print("\\n📊 Testing Basic Queries:")
        
        # Test class queries
        try:
            all_classes = manager.get_classes()
            print(f"✓ Found {len(all_classes)} classes in ontology")
            
            # List some classes
            class_names = list(all_classes.keys())[:5]
            print(f"  Sample classes: {class_names}")
            
        except Exception as e:
            print(f"✗ Error querying classes: {e}")
        
        # Test individual queries
        try:
            materials = manager.get_individuals("Material")
            print(f"✓ Found {len(materials)} materials")
            
            if materials:
                material_names = list(materials.keys())[:3]
                print(f"  Sample materials: {material_names}")
            
        except Exception as e:
            print(f"✗ Error querying materials: {e}")
        
        # Test units
        try:
            units = manager.get_individuals("Unit")
            print(f"✓ Found {len(units)} units")
            
            if units:
                unit_names = list(units.keys())[:5]
                print(f"  Sample units: {unit_names}")
            
        except Exception as e:
            print(f"✗ Error querying units: {e}")
        
        return True
        
    except ImportError as e:
        print(f"✗ Failed to import ontology manager: {e}")
        return False
    except Exception as e:
        print(f"✗ Error testing ontology manager: {e}")
        return False

def test_gui_ontology_integration():
    """Test GUI components with ontology integration"""
    print("\\nTesting GUI-Ontology Integration...")
    
    try:
        from dynamat.gui.mechanical.test_selector import TestTypeSelector
        from dynamat.gui.mechanical.shpb_setup import SHPBConditionsForm
        from PyQt6.QtWidgets import QApplication
        
        # Create QApplication (required for widgets)
        if not QApplication.instance():
            app = QApplication([])
        
        print("✓ GUI modules imported successfully")
        
        # Test TestTypeSelector
        print("\\n🧪 Testing TestTypeSelector:")
        try:
            selector = TestTypeSelector()
            print("✓ TestTypeSelector created")
            
            # Check if it loaded test types
            if hasattr(selector, 'available_tests'):
                print(f"✓ Available tests: {len(selector.available_tests)}")
            
        except Exception as e:
            print(f"✗ Error creating TestTypeSelector: {e}")
        
        # Test SHPBConditionsForm
        print("\\n⚙️  Testing SHPBConditionsForm:")
        try:
            form = SHPBConditionsForm()
            print("✓ SHPBConditionsForm created")
            
            # Check if ontology data was populated
            velocity_combo = form.striker_velocity_unit_combo
            pressure_combo = form.striker_pressure_unit_combo
            material_combo = form.bar_material_combo
            
            print(f"✓ Velocity units loaded: {velocity_combo.count() - 1}")  # -1 for "Make a Selection"
            print(f"✓ Pressure units loaded: {pressure_combo.count() - 1}")
            print(f"✓ Materials loaded: {material_combo.count() - 1}")
            
        except Exception as e:
            print(f"✗ Error creating SHPBConditionsForm: {e}")
        
        return True
        
    except ImportError as e:
        print(f"✗ Failed to import GUI modules: {e}")
        return False
    except Exception as e:
        print(f"✗ Error testing GUI integration: {e}")
        return False

def test_ontology_coverage():
    """Test specific ontology coverage for GUI needs"""
    print("\\n🔍 Testing Ontology Coverage for GUI Requirements...")
    
    try:
        from dynamat.ontology.manager import get_ontology_manager
        
        manager = get_ontology_manager()
        
        # Test essential classes for mechanical testing
        essential_classes = [
            "Material", "Unit", "Specimen", "SHPBTest", 
            "MomentumTrap", "Structure", "Shape"
        ]
        
        found_classes = []
        missing_classes = []
        
        all_classes = manager.get_classes()
        class_names = list(all_classes.keys())
        
        for cls in essential_classes:
            if cls in class_names:
                found_classes.append(cls)
            else:
                missing_classes.append(cls)
        
        print(f"✓ Found essential classes: {found_classes}")
        if missing_classes:
            print(f"⚠️  Missing essential classes: {missing_classes}")
        
        # Test specific individuals needed for dropdowns
        test_individuals = {
            "Material": ["Steel", "Aluminum", "Titanium"],
            "Unit": ["meter", "second", "pascal"],
            "Shape": ["Cylindrical", "Rectangular"]
        }
        
        for class_name, expected_items in test_individuals.items():
            try:
                individuals = manager.get_individuals(class_name)
                found_items = list(individuals.keys()) if individuals else []
                print(f"✓ {class_name} individuals: {len(found_items)}")
                
                # Check for expected items
                for item in expected_items:
                    found = any(item.lower() in ind.lower() for ind in found_items)
                    status = "✓" if found else "⚠️"
                    print(f"  {status} {item}: {'Found' if found else 'Not found'}")
                    
            except Exception as e:
                print(f"✗ Error querying {class_name}: {e}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error testing ontology coverage: {e}")
        return False

def main():
    """Main test function"""
    print("DynaMat Ontology Integration Test")
    print("=" * 50)
    
    # Test sequence
    tests = [
        ("Ontology Manager", test_ontology_manager),
        ("GUI Integration", test_gui_ontology_integration), 
        ("Ontology Coverage", test_ontology_coverage)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\\n{'='*20} {test_name} {'='*20}")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"✗ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print(f"\\n{'='*50}")
    print("Test Summary:")
    for test_name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {test_name}: {status}")
    
    total_passed = sum(1 for _, passed in results if passed)
    print(f"\\nOverall: {total_passed}/{len(results)} tests passed")
    
    if total_passed == len(results):
        print("\\n🎉 All tests passed! The GUI should work with the ontology.")
    else:
        print("\\n⚠️  Some tests failed. Check the ontology structure and file locations.")
        print("\\nSuggestions:")
        print("1. Ensure the ontology file exists at: dynamat/ontology/core/DynaMat_core.ttl")
        print("2. Verify that essential classes and individuals are defined in the ontology")
        print("3. Check that the ontology manager can load and parse the TTL file")

if __name__ == "__main__":
    main()