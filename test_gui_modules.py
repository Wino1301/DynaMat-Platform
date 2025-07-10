#!/usr/bin/env python3
"""
DynaMat Platform GUI Module Test Script

File location: test_gui_modules.py (place in root directory of project)

This script tests the individual GUI modules to verify they work correctly
and helps debug import issues.

Usage:
    python test_gui_modules.py
"""

import sys
import os
from pathlib import Path

def setup_python_path():
    """Setup Python path to include the project directory"""
    project_root = Path(__file__).parent.absolute()
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    return project_root

def test_imports():
    """Test importing all GUI modules"""
    print("Testing module imports...")
    
    try:
        print("  - Testing widgets module...")
        from dynamat.gui.widgets import (
            OntologyWidget, MeasurementWidget, OntologySelector,
            TextWidget, NumberWidget, DateWidget, BooleanWidget
        )
        print("    ✓ Widgets module imported successfully")
        
    except ImportError as e:
        print(f"    ✗ Failed to import widgets module: {e}")
        return False
    
    try:
        print("  - Testing forms module...")
        from dynamat.gui.forms import (
            OntologyFormGenerator, OntologyForm, FormData, FormTemplate
        )
        print("    ✓ Forms module imported successfully")
        
    except ImportError as e:
        print(f"    ✗ Failed to import forms module: {e}")
        return False
    
    try:
        print("  - Testing app module...")
        from dynamat.gui.app import DynaMatApp
        print("    ✓ App module imported successfully")
        
    except ImportError as e:
        print(f"    ✗ Failed to import app module: {e}")
        return False
    
    return True

def test_widget_creation():
    """Test creating individual widgets"""
    print("\nTesting widget creation...")
    
    try:
        from PyQt6.QtWidgets import QApplication
        from dynamat.gui.widgets import MeasurementWidget, OntologySelector, TextWidget
        
        # Create QApplication (required for widgets)
        if not QApplication.instance():
            app = QApplication([])
        
        print("  - Creating MeasurementWidget...")
        measurement = MeasurementWidget("test_measurement", ["mm", "inch", "m"])
        print("    ✓ MeasurementWidget created successfully")
        
        print("  - Creating OntologySelector...")
        selector = OntologySelector("test_selector", options=["Option1", "Option2"])
        print("    ✓ OntologySelector created successfully")
        
        print("  - Creating TextWidget...")
        text = TextWidget("test_text", "Test Label")
        print("    ✓ TextWidget created successfully")
        
        return True
        
    except Exception as e:
        print(f"    ✗ Failed to create widgets: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_form_generation():
    """Test form generation (requires ontology manager)"""
    print("\nTesting form generation...")
    
    try:
        from dynamat.gui.forms import OntologyFormGenerator
        
        print("  - Creating OntologyFormGenerator...")
        generator = OntologyFormGenerator()
        print("    ✓ OntologyFormGenerator created successfully")
        
        # Note: Actual form creation would require a working ontology manager
        print("    (Skipping actual form creation - requires ontology manager)")
        
        return True
        
    except Exception as e:
        print(f"    ✗ Failed to create form generator: {e}")
        return False

def main():
    """Main test function"""
    print("DynaMat Platform GUI Module Test")
    print("=" * 40)
    
    # Setup path
    project_root = setup_python_path()
    print(f"Project root: {project_root}")
    
    # Check if dynamat package exists
    dynamat_path = project_root / "dynamat"
    if not dynamat_path.exists():
        print(f"\n✗ Error: dynamat package not found at {dynamat_path}")
        print("Make sure you're running this script from the project root directory.")
        return False
    
    # Check if gui package exists
    gui_path = dynamat_path / "gui"
    if not gui_path.exists():
        print(f"\n✗ Error: GUI package not found at {gui_path}")
        print("Make sure the dynamat/gui directory exists.")
        return False
    
    print(f"GUI package found at: {gui_path}")
    
    # Run tests
    all_passed = True
    
    all_passed &= test_imports()
    all_passed &= test_widget_creation()
    all_passed &= test_form_generation()
    
    print("\n" + "=" * 40)
    if all_passed:
        print("✓ All tests passed! GUI modules are working correctly.")
        print("\nYou can now run the full application with:")
        print("python run_dynamat.py")
    else:
        print("✗ Some tests failed. Check the error messages above.")
        print("\nTroubleshooting:")
        print("1. Make sure you're in the project root directory")
        print("2. Check that all GUI module files exist in dynamat/gui/")
        print("3. Verify PyQt6 is installed: pip install PyQt6")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)