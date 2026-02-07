"""
DynaMat Platform - Main Entry Point
Desktop application for dynamic materials testing data management

This is the main entry point that should be placed in the root dynamat/ directory.
It launches the GUI application and handles command-line arguments.

Usage:
    python main.py                    # Launch GUI
    python main.py --help            # Show help
    python main.py --validate        # Validate ontology only
    python main.py --debug           # Enable debug logging
"""

import sys
import argparse
import logging
from pathlib import Path

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import after path setup
from dynamat.gui.app import DynaMatApp, main as gui_main
from dynamat.ontology.manager import OntologyManager
from dynamat.config import Config, config


def setup_logging(debug: bool = False):
    """Setup application logging"""
    level = logging.DEBUG if debug else logging.INFO
    
    # Create logs directory if it doesn't exist
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    
    # Setup logging configuration
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / "dynamat.log"),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Reduce verbosity of external libraries
    logging.getLogger('rdflib').setLevel(logging.WARNING)
    logging.getLogger('PyQt6').setLevel(logging.WARNING)


def validate_ontology():
    """Validate ontology and exit"""
    print("Validating DynaMat ontology...")
    
    try:
        manager = OntologyManager()
        print(f"Ontology loaded successfully with {len(manager.graph)} triples")
        
        # Basic validation checks
        specimen_uri = "https://dynamat.utep.edu/ontology#Specimen"
        class_metadata = manager.get_class_metadata_for_form(specimen_uri)
        print(f"✓ Specimen class found with {len(class_metadata.properties)} properties")
        
        # Check form groups
        form_groups = manager.get_form_groups_for_class(specimen_uri)
        print(f"✓ Form groups found: {', '.join(form_groups)}")
        
        print("\n Ontology validation passed!")
        return True
        
    except Exception as e:
        print(f"✗ Ontology validation failed: {e}")
        return False


def show_system_info():
    """Show system information for debugging"""
    import platform
    from PyQt6.QtCore import QT_VERSION_STR
    from PyQt6.QtWidgets import QApplication
    
    print(f"DynaMat Platform - System Information")
    print(f"=====================================")
    print(f"Python version: {sys.version}")
    print(f"Platform: {platform.platform()}")
    print(f"PyQt6 version: {QT_VERSION_STR}")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Ontology directory: {config.ONTOLOGY_DIR}")
    print(f"Data directory: {config.DATA_DIR}")
    
    # Check if running in virtual environment
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print(f"Virtual environment: {sys.prefix}")
    else:
        print("Virtual environment: Not detected")
    
    print()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="DynaMat Platform - Dynamic Materials Testing Data Management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python main.py                   # Launch GUI application
    python main.py --debug           # Launch with debug logging
    python main.py --validate        # Validate ontology only
    python main.py --info            # Show system information
        """
    )
    
    parser.add_argument(
        '--debug', 
        action='store_true',
        help='Enable debug logging'
    )
    
    parser.add_argument(
        '--validate',
        action='store_true', 
        help='Validate ontology and exit'
    )
    
    parser.add_argument(
        '--info',
        action='store_true',
        help='Show system information and exit'
    )
    
    parser.add_argument(
        '--nogui',
        action='store_true',
        help='Run without GUI (command-line mode)'
    )
    
    args = parser.parse_args()

    # Ensure all necessary directories exist
    Config.ensure_directories()
    
    # Setup logging
    setup_logging(args.debug)
    logger = logging.getLogger(__name__)
    
    try:
        # Show system info if requested
        if args.info:
            show_system_info()
            return 0
        
        # Validate ontology if requested
        if args.validate:
            success = validate_ontology()
            return 0 if success else 1
        
        # Check if GUI is available
        if not args.nogui:
            try:
                from PyQt6.QtWidgets import QApplication
                # Test if display is available
                test_app = QApplication([])
                test_app.quit()
                gui_available = True
            except Exception as e:
                logger.warning(f"GUI not available: {e}")
                gui_available = False
                args.nogui = True
        else:
            gui_available = False
        
        # Launch appropriate interface
        if args.nogui or not gui_available:
            logger.info("Running in command-line mode")
            print("DynaMat Platform - Command Line Mode")
            print("GUI mode not available or disabled.")
            print("Use --help for available options.")
            return 0
        else:
            logger.info("Launching GUI application")
            return gui_main()
    
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        return 0
    
    except Exception as e:
        logger.error(f"Application failed to start: {e}", exc_info=True)
        print(f"\nError: {e}")
        print("Use --debug for more detailed error information.")
        return 1


if __name__ == "__main__":
    sys.exit(main())