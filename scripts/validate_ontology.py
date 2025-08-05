"""
Standalone ontology validation script
"""

if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    # Add parent directory to path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    # Run validation
    from main import validate_ontology
    success = validate_ontology()
    sys.exit(0 if success else 1)