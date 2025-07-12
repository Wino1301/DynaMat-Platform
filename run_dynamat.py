#!/usr/bin/env python3
"""
DynaMat Platform Launcher - Fixed Version

File location: run_dynamat.py (place in root directory)

Fixed launcher script that handles imports gracefully and provides
helpful error messages for troubleshooting.
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

def check_project_structure(project_root):
    """Check if the project structure exists"""
    required_paths = [
        project_root / "dynamat",
        project_root / "dynamat" / "gui",
        project_root / "dynamat" / "ontology",
        project_root / "dynamat" / "gui" / "__init__.py",
        project_root / "dynamat" / "ontology" / "__init__.py",
    ]
    
    missing_paths = []
    for path in required_paths:
        if not path.exists():
            missing_paths.append(str(path))
    
    return missing_paths

def check_gui_files(project_root):
    """Check if GUI files exist"""
    gui_files = [
        project_root / "dynamat" / "gui" / "ribbon.py",
        project_root / "dynamat" / "gui" / "app.py",
        project_root / "dynamat" / "gui" / "mechanical" / "__init__.py",
    ]
    
    existing_files = []
    missing_files = []
    
    for file_path in gui_files:
        if file_path.exists():
            existing_files.append(str(file_path))
        else:
            missing_files.append(str(file_path))
    
    return existing_files, missing_files

def test_imports():
    """Test importing required modules step by step"""
    print("Testing imports step by step...")
    
    # Test PyQt6
    try:
        from PyQt6.QtWidgets import QApplication
        print("✓ PyQt6 is available")
    except ImportError as e:
        print(f"✗ PyQt6 import failed: {e}")
        print("  Please install PyQt6: pip install PyQt6")
        return False
    
    # Test basic ontology import
    try:
        from dynamat.ontology.manager import get_ontology_manager
        print("✓ Ontology manager import successful")
    except ImportError as e:
        print(f"⚠ Ontology manager import failed: {e}")
        print("  This may be expected if ontology files are missing")
    
    # Test GUI __init__
    try:
        import dynamat.gui
        print("✓ GUI package import successful")
    except ImportError as e:
        print(f"⚠ GUI package import failed: {e}")
    
    # Test individual GUI components
    try:
        from dynamat.gui.ribbon import RibbonMenu
        print("✓ Ribbon menu import successful")
    except ImportError as e:
        print(f"⚠ Ribbon menu import failed: {e}")
    
    try:
        from dynamat.gui.app import DynaMatApp
        print("✓ Main app import successful")
        return True
    except ImportError as e:
        print(f"⚠ Main app import failed: {e}")
        return False

def run_test_mode():
    """Run in test mode to verify components"""
    print("\\n" + "="*50)
    print("RUNNING IN TEST MODE")
    print("="*50)
    
    try:
        # Test ontology integration
        print("\\n1. Testing Ontology Integration...")
        exec(open("test_ontology_integration.py").read())
        
    except FileNotFoundError:
        print("test_ontology_integration.py not found - skipping ontology test")
    except Exception as e:
        print(f"Ontology test failed: {e}")
    
    # Test GUI components individually
    print("\\n2. Testing Individual GUI Components...")
    
    try:
        from PyQt6.QtWidgets import QApplication
        from dynamat.gui.ribbon import RibbonMenu
        
        if not QApplication.instance():
            app = QApplication([])
        
        # Test ribbon menu
        ribbon = RibbonMenu()
        print("✓ Ribbon menu created successfully")
        
        # Test mechanical components
        from dynamat.gui.mechanical.test_selector import TestTypeSelector
        selector = TestTypeSelector()
        print("✓ Test selector created successfully")
        
        from dynamat.gui.mechanical.shpb_setup import SHPBConditionsForm
        shpb_form = SHPBConditionsForm()
        print("✓ SHPB form created successfully")
        
        print("\\n✓ All GUI components working!")
        return True
        
    except Exception as e:
        print(f"✗ GUI component test failed: {e}")
        return False

def main():
    """Main launcher function"""
    print("Starting DynaMat Platform...")
    
    # Setup Python path
    project_root = setup_python_path()
    print(f"Project root: {project_root}")
    
    # Check project structure
    missing_paths = check_project_structure(project_root)
    if missing_paths:
        print("\\nError: Missing required directories:")
        for path in missing_paths:
            print(f"  - {path}")
        print("\\nPlease ensure the basic project structure exists.")
        return 1
    
    # Check GUI files
    existing_files, missing_files = check_gui_files(project_root)
    print(f"\\nGUI Files Status:")
    print(f"  Existing: {len(existing_files)} files")
    print(f"  Missing: {len(missing_files)} files")
    
    if missing_files:
        print("\\nMissing GUI files:")
        for file_path in missing_files:
            print(f"  - {file_path}")
    
    # Test imports
    print("\\n" + "="*40)
    import_success = test_imports()
    
    if not import_success:
        print("\\n" + "="*40)
        print("IMPORT ERRORS DETECTED")
        print("="*40)
        print("\\nWould you like to run in test mode to verify what's working? (y/n)")
        response = input().lower().strip()
        
        if response == 'y':
            return run_test_mode()
        else:
            print("\\nTroubleshooting steps:")
            print("1. Ensure all required files are in correct locations")
            print("2. Check that PyQt6 is installed: pip install PyQt6")
            print("3. Verify the ontology file exists: dynamat/ontology/core/DynaMat_core.ttl")
            print("4. Make sure all __init__.py files exist in the package directories")
            return 1
    
    try:
        # Import main application
        from dynamat.gui.app import DynaMatApp
        from PyQt6.QtWidgets import QApplication
        
        print("\\n" + "="*40)
        print("STARTING GUI APPLICATION")
        print("="*40)
        
        # Create and run application
        app = QApplication(sys.argv)
        
        # Set application properties
        app.setApplicationName("DynaMat Platform")
        app.setApplicationVersion("1.0")
        app.setOrganizationName("UTEP Dynamic Materials Laboratory")
        
        # Create main window
        main_window = DynaMatApp()
        main_window.show()
        
        print("✓ DynaMat Platform started successfully")
        print("\\nThe application window should now be visible.")
        print("If you don't see the window, check your desktop for the DynaMat application.")
        
        # Start event loop
        return app.exec()
        
    except ImportError as e:
        print(f"\\nFinal Import Error: {e}")
        print("\\nDespite earlier tests passing, the main application could not start.")
        print("This suggests there may be circular imports or missing dependencies.")
        print("\\nTrying test mode instead...")
        return run_test_mode()
        
    except Exception as e:
        print(f"\\nUnexpected Error: {e}")
        print("The application encountered an error during startup.")
        print("\\nTrying test mode to isolate the issue...")
        return run_test_mode()

if __name__ == "__main__":
    sys.exit(main())