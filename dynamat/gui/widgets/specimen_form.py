"""
DynaMat Platform - Specimen Form Widget
Form widget for specimen data entry and management
"""

import logging
from typing import Dict, Any, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QMessageBox, QFrame, QProgressBar, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from ...ontology.manager import OntologyManager
from ..form_builder import OntologyFormBuilder

logger = logging.getLogger(__name__)


class SpecimenFormWidget(QWidget):
    """
    Widget for specimen data entry and management.
    
    Features:
    - Auto-generated form from ontology definitions
    - Template loading and saving
    - Data validation
    - Save/load specimen instances
    """
    
    # Signals
    specimen_saved = pyqtSignal(dict)
    specimen_loaded = pyqtSignal(dict)
    validation_error = pyqtSignal(str)
    form_changed = pyqtSignal()
    
    def __init__(self, ontology_manager: OntologyManager, parent=None):
        super().__init__(parent)
        
        self.ontology_manager = ontology_manager
        self.form_builder = OntologyFormBuilder(ontology_manager)
        self.current_specimen_uri = None
        self.form_widget = None
        self.is_modified = False
        self.form_container = None
        
        # Debug ontology status first
        self.debug_ontology_status()
        
        self._setup_ui()
        
        # Create form immediately instead of deferring
        self._create_specimen_form()
        
        self._connect_signals()
        
        logger.info("Specimen form widget initialized")
    
    def _setup_ui(self):
        """Setup the widget UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header section
        header_frame = QFrame()
        header_frame.setFrameStyle(QFrame.Shape.Box)
        header_layout = QHBoxLayout(header_frame)
        
        # Title
        title_label = QLabel("Specimen Information")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Action buttons
        self.new_btn = QPushButton("New")
        self.new_btn.setToolTip("Create new specimen")
        header_layout.addWidget(self.new_btn)
        
        self.load_btn = QPushButton("Load")
        self.load_btn.setToolTip("Load existing specimen")
        header_layout.addWidget(self.load_btn)
        
        self.save_btn = QPushButton("Save")
        self.save_btn.setToolTip("Save current specimen")
        header_layout.addWidget(self.save_btn)
        
        self.validate_btn = QPushButton("Validate")
        self.validate_btn.setToolTip("Validate specimen data")
        header_layout.addWidget(self.validate_btn)
        
        layout.addWidget(header_frame)
        
        # Status label
        self.status_label = QLabel("Loading...")
        self.status_label.setStyleSheet("color: #888; font-style: italic;")
        layout.addWidget(self.status_label)
        
        # Scroll area for form
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Form container
        self.form_container = QWidget()
        scroll_area.setWidget(self.form_container)
        layout.addWidget(scroll_area)
    
    def debug_ontology_status(self):
        """Debug method to check ontology status"""
        try:
            logger.info("=== ONTOLOGY DEBUG INFO ===")
            
            # Check ontology manager
            if not self.ontology_manager:
                logger.error("Ontology manager is None")
                return
            
            # Check graph size
            graph_size = len(self.ontology_manager.graph)
            logger.info(f"Ontology graph has {graph_size} triples")
            
            # Check specimen class
            specimen_uri = "https://dynamat.utep.edu/ontology#Specimen"
            try:
                properties = self.ontology_manager.get_class_properties(specimen_uri)
                logger.info(f"Found {len(properties)} properties for Specimen class")
                
                for prop in properties[:5]:  # Show first 5 properties
                    logger.info(f"  - {prop.display_name} ({prop.form_group}, order: {prop.display_order})")
                
                if len(properties) > 5:
                    logger.info(f"  ... and {len(properties) - 5} more properties")
                    
            except Exception as e:
                logger.error(f"Failed to get specimen properties: {e}")
            
            # Check individuals
            try:
                shapes = self.ontology_manager.get_all_individuals("https://dynamat.utep.edu/ontology#Shape")
                logger.info(f"Found {len(shapes)} shape individuals")
                for shape in shapes[:3]:
                    logger.info(f"  - Shape: {shape}")
                    
                roles = self.ontology_manager.get_all_individuals("https://dynamat.utep.edu/ontology#SpecimenRole")
                logger.info(f"Found {len(roles)} specimen role individuals")
                for role in roles[:3]:
                    logger.info(f"  - Role: {role}")
                    
            except Exception as e:
                logger.error(f"Failed to get shape individuals: {e}")
                
            logger.info("=== END ONTOLOGY DEBUG ===")
            
        except Exception as e:
            logger.error(f"Debug failed: {e}")
    
    def _create_specimen_form(self):
        """Create the specimen form from ontology"""
        try:
            logger.info("Creating specimen form for https://dynamat.utep.edu/ontology#Specimen")
            
            specimen_uri = "https://dynamat.utep.edu/ontology#Specimen"
            
            # Validate ontology manager and specimen class
            try:
                class_metadata = self.ontology_manager.get_class_metadata_for_form(specimen_uri)
                logger.info(f"Found {len(class_metadata.properties)} properties for specimen")
                logger.info(f"Form groups: {list(class_metadata.form_groups.keys())}")
            except Exception as e:
                logger.error(f"Failed to get class metadata: {e}")
                raise Exception(f"Cannot load specimen metadata: {e}")
            
            # Create new form
            self.form_widget = self.form_builder.build_form(specimen_uri, self.form_container)
            
            if not self.form_widget:
                raise Exception("Form builder returned None")
            
            # Add to container
            if not self.form_container.layout():
                container_layout = QVBoxLayout(self.form_container)
                container_layout.setContentsMargins(0, 0, 0, 0)
            
            self.form_container.layout().addWidget(self.form_widget)
            
            # Check if form has fields
            if hasattr(self.form_widget, 'form_fields'):
                field_count = len(self.form_widget.form_fields)
                logger.info(f"Form created successfully with {field_count} fields")
                self.status_label.setText(f"Specimen form loaded with {field_count} fields")
            else:
                logger.warning("Form widget has no form_fields attribute")
                self.status_label.setText("Specimen form loaded (no fields detected)")
            
        except Exception as e:
            logger.error(f"Failed to create specimen form: {e}", exc_info=True)
            self.status_label.setText(f"Error: {str(e)}")
            
            # Show detailed error message
            error_widget = QLabel(f"Failed to load specimen form:\n\n{str(e)}\n\nCheck the terminal for more details.")
            error_widget.setStyleSheet("color: red; padding: 20px; background-color: #2a1a1a; border: 1px solid red;")
            error_widget.setWordWrap(True)
            
            if not self.form_container.layout():
                container_layout = QVBoxLayout(self.form_container)
            
            self.form_container.layout().addWidget(error_widget)
            self.form_widget = error_widget
    
    def _connect_signals(self):
        """Connect widget signals"""
        self.new_btn.clicked.connect(self.create_new_specimen)
        self.load_btn.clicked.connect(self.load_specimen)
        self.save_btn.clicked.connect(self.save_specimen)
        self.validate_btn.clicked.connect(self.validate_specimen)
    
    def create_new_specimen(self):
        """Create a new specimen"""
        if self.is_modified:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Create new specimen anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
        
        # Clear form
        if self.form_widget and hasattr(self.form_widget, 'clear_form'):
            self.form_widget.clear_form()
        
        self.current_specimen_uri = None
        self.is_modified = False
        logger.info("Created new specimen")
    
    def load_specimen(self):
        """Load an existing specimen"""
        # Placeholder for load functionality
        logger.info("Load specimen requested")
        self.status_label.setText("Load specimen functionality not yet implemented")
    
    def save_specimen(self):
        """Save the current specimen"""
        # Placeholder for save functionality
        logger.info("Save specimen requested")
        self.status_label.setText("Save specimen functionality not yet implemented")
    
    def validate_specimen(self):
        """Validate the current specimen data"""
        # Placeholder for validation functionality
        logger.info("Validate specimen requested")
        self.status_label.setText("Validate specimen functionality not yet implemented")
    
    def get_form_data(self) -> Dict[str, Any]:
        """Get form data"""
        if self.form_widget and hasattr(self.form_widget, 'get_form_data'):
            return self.form_widget.get_form_data()
        return {}
    
    def populate_form(self, data: Dict[str, Any]):
        """Populate form with data"""
        if self.form_widget and hasattr(self.form_widget, 'populate_form'):
            self.form_widget.populate_form(data)
            self.is_modified = False
    
    def clear_form(self):
        """Clear all form fields"""
        if self.form_widget and hasattr(self.form_widget, 'clear_form'):
            self.form_widget.clear_form()
            self.is_modified = False
    
    def is_form_valid(self) -> bool:
        """Check if form data is valid"""
        if self.form_widget and hasattr(self.form_widget, 'is_valid'):
            return self.form_widget.is_valid()
        return True
    
    def showEvent(self, event):
        """Handle widget show event"""
        super().showEvent(event)
        logger.debug("Specimen form widget shown")
    
    def hideEvent(self, event):
        """Handle widget hide event"""
        super().hideEvent(event)
        logger.debug("Specimen form widget hidden")