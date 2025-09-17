"""
DynaMat Platform - Specimen Form Widget
Form widget for specimen data entry and management
"""

import logging
from typing import Dict, Any, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QMessageBox, QFrame, QProgressBar
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
        
        self._setup_ui()
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
        
        # Form container
        self.form_container = QWidget()
        layout.addWidget(self.form_container)
        
        # Status section
        status_frame = QFrame()
        status_frame.setFrameStyle(QFrame.Shape.Box)
        status_layout = QVBoxLayout(status_frame)
        
        self.status_label = QLabel("Ready")
        status_layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        status_layout.addWidget(self.progress_bar)
        
        layout.addWidget(status_frame)
    
    def _create_specimen_form(self):
        """Create the specimen form from ontology"""
        try:
            specimen_uri = "https://dynamat.utep.edu/ontology#Specimen"
            logger.info(f"Creating specimen form for {specimen_uri}")
            
            # Clear existing form
            if self.form_widget:
                self.form_container.layout().removeWidget(self.form_widget)
                self.form_widget.deleteLater()
                self.form_widget = None
            
            # Test ontology manager
            if not self.ontology_manager:
                raise Exception("Ontology manager not available")
            
            # Test if we can get class metadata
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
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        # Clear form
        if self.form_widget:
            self.form_builder.populate_form(self.form_widget, {})
        
        self.current_specimen_uri = None
        self.is_modified = False
        self.status_label.setText("New specimen created")
        
        logger.info("Created new specimen")
    
    def load_specimen(self):
        """Load an existing specimen"""
        # This would show a specimen selection dialog
        # For now, just show a placeholder message
        QMessageBox.information(
            self, "Load Specimen",
            "Specimen loading functionality will be implemented with the database interface."
        )
    
    def save_specimen(self):
        """Save the current specimen"""
        try:
            if not self.form_widget:
                QMessageBox.warning(self, "Error", "No form available to save")
                return
            
            # Extract form data
            form_data = self.form_builder.get_form_data(self.form_widget)
            
            if not form_data:
                QMessageBox.warning(self, "Error", "No data to save")
                return
            
            # Validate required fields
            validation_errors = self.validate_form_data(form_data)
            if validation_errors:
                QMessageBox.warning(
                    self, "Validation Error",
                    f"Please fix the following errors:\n\n{validation_errors}"
                )
                return
            
            # Show progress
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)  # Indeterminate progress
            self.status_label.setText("Saving specimen...")
            
            # Here would be the actual save logic
            # For now, just simulate saving
            self._simulate_save_operation(form_data)
            
        except Exception as e:
            logger.error(f"Failed to save specimen: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save specimen:\n{str(e)}")
            self.status_label.setText("Save failed")
        finally:
            self.progress_bar.setVisible(False)
    
    def _simulate_save_operation(self, form_data: Dict[str, Any]):
        """Simulate save operation (placeholder)"""
        import time
        time.sleep(1)  # Simulate processing time
        
        self.is_modified = False
        self.status_label.setText("Specimen saved successfully")
        self.specimen_saved.emit(form_data)
        
        logger.info(f"Specimen saved with data: {form_data}")
    
    def validate_specimen(self):
        """Validate the current specimen data"""
        try:
            if not self.form_widget:
                QMessageBox.warning(self, "Error", "No form available to validate")
                return
            
            form_data = self.form_builder.get_form_data(self.form_widget)
            validation_errors = self.validate_form_data(form_data)
            
            if validation_errors:
                QMessageBox.warning(
                    self, "Validation Errors",
                    f"Found the following validation errors:\n\n{validation_errors}"
                )
                self.validation_error.emit(validation_errors)
            else:
                QMessageBox.information(
                    self, "Validation Success",
                    "All specimen data is valid!"
                )
                self.status_label.setText("Validation successful")
                
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            QMessageBox.critical(self, "Error", f"Validation failed:\n{str(e)}")
    
    def validate_form_data(self, form_data: Dict[str, Any]) -> str:
        """
        Validate form data and return error messages.
        
        Args:
            form_data: Dictionary of form data
            
        Returns:
            String containing error messages, empty if valid
        """
        errors = []
        
        if not self.form_widget or not hasattr(self.form_widget, 'form_fields'):
            return ""
        
        # Check required fields
        for prop_uri, field in self.form_widget.form_fields.items():
            if field.required:
                if prop_uri not in form_data or not form_data[prop_uri]:
                    errors.append(f"• {field.property_metadata.display_name} is required")
        
        # Additional validation rules could be added here
        # - Format validation
        # - Range validation
        # - Cross-field validation
        
        return "\n".join(errors)
    
    def apply_template(self, template_data: Dict[str, Any]):
        """Apply template data to the form"""
        if self.form_widget and template_data:
            self.form_builder.populate_form(self.form_widget, template_data)
            self.is_modified = True
            self.status_label.setText(f"Template applied: {template_data.get('name', 'Unknown')}")
    
    def create_new_instance(self, class_uri: str):
        """Create new instance of the given class"""
        if class_uri == "https://dynamat.utep.edu/ontology#Specimen":
            self.create_new_specimen()
        else:
            logger.warning(f"Cannot create instance of {class_uri} in specimen form")
    
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
            except Exception as e:
                logger.error(f"Failed to get shape individuals: {e}")
                
            logger.info("=== END ONTOLOGY DEBUG ===")
            
        except Exception as e:
            logger.error(f"Debug failed: {e}")
    
    def __init__(self, ontology_manager: OntologyManager, parent=None):
        super().__init__(parent)
        
        self.ontology_manager = ontology_manager
        self.form_builder = OntologyFormBuilder(ontology_manager)
        self.current_specimen_uri = None
        self.form_widget = None
        self.is_modified = False
        
        # Debug ontology status
        self.debug_ontology_status()
        
        self._setup_ui()
        self._create_specimen_form()
        self._connect_signals()
        
        logger.info("Specimen form widget initialized")