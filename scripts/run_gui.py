"""
Quick launcher script for the GUI application
"""

if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    # Add parent directory to path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    # Launch main application
    from main import main
    sys.exit(main())
