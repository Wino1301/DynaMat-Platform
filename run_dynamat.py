#!/usr/bin/env python3
"""
DynaMat Platform Application Entry Point

File location: run_dynamat.py (place in root directory of project)

This script serves as the main entry point for the DynaMat Platform GUI application.
It handles the Python path setup and launches the main application window.

Usage:
    python run_dynamat.py

Make sure you're in the project root directory when running this script.
"""

import sys
import os
from pathlib import Path

def setup_python_path():
    """Setup Python path to include the project directory"""
    # Get the directory containing this script (should be project root)
    project_root = Path(__file__).parent.absolute()
    
    # Add project root to Python path if not already there
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    
    # Verify that the dynamat package can be found
    dynamat_path = project_root / "dynamat"
    if not dynamat_path.exists():
        print(f"Error: dynamat package not found at {dynamat_path}")
        print("Make sure you're running this script from the project root directory.")
        sys.exit(1)
    
    return project_root

def check_dependencies():
    """Check if required dependencies are available"""
    missing_deps = []
    
    try:
        import PyQt6
    except ImportError:
        missing_deps.append("PyQt6")
    
    try:
        import rdflib
    except ImportError:
        missing_deps.append("rdflib")
    
    if missing_deps:
        print("Error: Missing required dependencies:")
        for dep in missing_deps:
            print(f"  - {dep}")
        print("\nPlease install missing dependencies:")
        print("pip install PyQt6 rdflib")
        sys.exit(1)

def main():
    """Main entry point for the DynaMat Platform application"""
    print("Starting DynaMat Platform...")
    
    # Setup Python path
    project_root = setup_python_path()
    print(f"Project root: {project_root}")
    
    # Check dependencies
    check_dependencies()
    
    try:
        # Import and run the application
        from dynamat.gui.app import main as run_app
        print("Launching DynaMat Platform GUI...")
        run_app()
        
    except ImportError as e:
        print(f"Import Error: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure you're in the project root directory")
        print("2. Check that the dynamat package structure exists")
        print("3. Verify that all required files are present")
        sys.exit(1)
        
    except Exception as e:
        print(f"Error starting application: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()