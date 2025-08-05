"""
DynaMat Platform - Main Application
Main QApplication class and application entry point
"""

import sys
import logging
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import QApplication, QStyleFactory
from PyQt6.QtCore import Qt, QDir
from PyQt6.QtGui import QIcon, QPalette, QColor

from .main_window import MainWindow
from ..config import config
from ..ontology.manager import OntologyManager

logger = logging.getLogger(__name__)


class DynaMatApp(QApplication):
    """
    Main DynaMat Platform application class.
    
    Handles application-wide settings, styling, and initialization.
    """
    
    def __init__(self, argv):
        super().__init__(argv)
        
        # Application metadata
        self.setApplicationName("DynaMat Platform")
        self.setApplicationVersion("1.0.0")
        self.setOrganizationName("UTEP Dynamic Materials Laboratory")
        self.setOrganizationDomain("dynamat.utep.edu")
        
        # Initialize ontology manager
        self.ontology_manager = None
        self._init_ontology_manager()
        
        # Setup application style
        self._setup_style()
        
        # Initialize main window
        self.main_window = None
        
        logger.info("DynaMat application initialized")
    
    def _init_ontology_manager(self):
        """Initialize the ontology manager"""
        try:
            self.ontology_manager = OntologyManager()
            logger.info("Ontology manager loaded successfully")
        except Exception as e:
            logger.error(f"Failed to initialize ontology manager: {e}")
            # Could show error dialog here
    
    def _setup_style(self):
        """Setup application-wide styling"""
        # Set application style
        self.setStyle(QStyleFactory.create('Fusion'))
        
        # Setup dark theme palette
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(0, 0, 0))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
        palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))
        
        self.setPalette(palette)
        
        # Load custom stylesheet
        self._load_stylesheet()
    
    def _load_stylesheet(self):
        """Load custom CSS stylesheet"""
        style_file = Path(__file__).parent / "resources" / "styles.qss"
        if style_file.exists():
            with open(style_file, 'r') as f:
                self.setStyleSheet(f.read())
    
    def create_main_window(self) -> MainWindow:
        """Create and show the main window"""
        if self.main_window is None:
            self.main_window = MainWindow(self.ontology_manager)
        
        self.main_window.show()
        return self.main_window
    
    def run(self):
        """Run the application"""
        self.create_main_window()
        return self.exec()


def main():
    """Application entry point"""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create and run application
    app = DynaMatApp(sys.argv)
    return app.run()


if __name__ == "__main__":
    sys.exit(main())