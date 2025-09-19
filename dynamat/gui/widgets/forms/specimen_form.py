"""
DynaMat Platform - Specimen Form Widget (Refactored)
Simplified form widget using new builders architecture
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QMessageBox, QFrame, QProgressBar, QScrollArea,
    QToolBar, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QAction

from ....ontology import OntologyManager
from ...builders.ontology_form_builder import OntologyFormBuilder
from ...builders.layout_manager import LayoutStyle

logger = logging.getLogger(__name__)


class SpecimenFormWidget(QWidget):
    """
    Simplified specimen form widget using the new builders architecture.
    
    Features:
    - Auto-generated form from ontology definitions
    - Template loading and saving
    - Data validation
    - Save/load specimen instances
    - Much cleaner implementation using specialized components
    """
    
    # Signals
    specimen_saved = pyqtSignal(dict)
    specimen_loaded = pyqtSignal(dict)
    validation_error = pyqtSignal(str)
    form_changed = pyqtSignal()
    template_loaded = pyqtSignal(str)
    template_saved = pyqtSignal(str)
    
    def __init__(self, ontology_manager: OntologyManager, parent=None):
        super().__init__(parent)
        
        self.ontology_manager = ontology_manager
        self.logger = logging.getLogger(__name__)
        
        # Initialize form builder with dependencies
        self.form_builder = OntologyFormBuilder(ontology_manager)
        self._enable_dependencies()
        
        # Form state
        self.current_specimen_uri = None
        self.form_widget = None
        self.is_modified = False
        self.original_data = {}
        
        self._setup_ui()
        self._create_specimen_form()
        
        self.logger.info("Specimen form widget initialized")
    
    def _setup_ui(self):
        """Setup the widget UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Create toolbar
        self._create_toolbar(layout)
        
        # Create main content area
        self.content_frame = QFrame()
        self.content_layout = QVBoxLayout(self.content_frame)
        self.content_layout.setContentsMargins(5, 5, 5, 5)
        layout.addWidget(self.content_frame)
        
        # Create status bar
        self._create_status_bar(layout)
    
    def _create_toolbar(self, parent_layout):
        """Create toolbar with common actions"""
        toolbar = QToolBar()
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        
        # New action
        new_action = QAction("New", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_specimen)
        toolbar.addAction(new_action)
        
        toolbar.addSeparator()
        
        # Load template action
        load_template_action = QAction("Load Template", self)
        load_template_action.triggered.connect(self.load_template)
        toolbar.addAction(load_template_action)
        
        # Save template action
        save_template_action = QAction("Save Template", self)
        save_template_action.triggered.connect(self.save_template)
        toolbar.addAction(save_template_action)
        
        toolbar.addSeparator()
        
        # Validate action
        validate_action = QAction("Validate", self)
        validate_action.setShortcut("Ctrl+Shift+V")
        validate_action.triggered.connect(self.validate_form)
        toolbar.addAction(validate_action)
        
        # Save action
        save_action = QAction("Save", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_specimen)
        toolbar.addAction(save_action)
        
        parent_layout.addWidget(toolbar)
    
    def _create_status_bar(self, parent_layout):
        """Create status bar"""
        self.status_bar = QFrame()
        self.status_bar.setFrameStyle(QFrame.Shape.StyledPanel)
        self.status_bar.setMaximumHeight(30)
        
        status_layout = QHBoxLayout(self.status_bar)
        status_layout.setContentsMargins(5, 2, 5, 2)
        
        # Status label
        self.status_label = QLabel("Ready")
        status_layout.addWidget(self.status_label)
        
        status_layout.addStretch()
        
        # Progress bar (initially hidden)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(200)
        status_layout.addWidget(self.progress_bar)
        
        parent_layout.addWidget(self.status_bar)
    
    def _enable_dependencies(self):
        """Enable dependency management with fallback"""
        try:
            # Try to find dependencies configuration
            config_path = Path(__file__).parent.parent.parent / "dependencies.json"
            if config_path.exists():
                self.form_builder.enable_dependencies(str(config_path))
                self.logger.info("Dependencies enabled with configuration")
            else:
                self.form_builder.enable_dependencies()
                self.logger.info("Dependencies enabled with default configuration")
        except Exception as e:
            self.logger.warning(f"Could not enable dependencies: {e}")
    
    def _create_specimen_form(self):
        """Create the specimen form using the new builder"""
        try:
            self.status_label.setText("Creating form...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)  # Indeterminate
            
            # Create form using the builder
            self.form_widget = self.form_builder.build_form("Specimen", self.content_frame)
            
            # Clear existing content and add new form
            self._clear_content_layout()
            self.content_layout.addWidget(self.form_widget)
            
            # Store original empty data
            self.original_data = self.form_builder.get_form_data(self.form_widget)
            
            self.status_label.setText("Form created successfully")
            self.progress_bar.setVisible(False)
            
            self.logger.info("Specimen form created successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to create specimen form: {e}")
            self._show_error_form(f"Failed to create form: {str(e)}")
            self.status_label.setText("Error creating form")
            self.progress_bar.setVisible(False)
    
    def _clear_content_layout(self):
        """Clear all widgets from content layout"""
        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
    
    def _show_error_form(self, error_message: str):
        """Show error message in place of form"""
        error_label = QLabel(f"Error: {error_message}")
        error_label.setStyleSheet("color: red; padding: 20px; background-color: #2a1a1a; border: 1px solid red;")
        error_label.setWordWrap(True)
        error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self._clear_content_layout()
        self.content_layout.addWidget(error_label)
    
    # ============================================================================
    # PUBLIC METHODS
    # ============================================================================
    
    def new_specimen(self):
        """Create new specimen form"""
        if self.is_modified:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Continue without saving?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        try:
            self.form_builder.clear_form(self.form_widget)
            self.current_specimen_uri = None
            self.is_modified = False
            self.original_data = self.form_builder.get_form_data(self.form_widget)
            self.status_label.setText("New specimen form")
            self.logger.info("New specimen form created")
            
        except Exception as e:
            self.logger.error(f"Failed to create new specimen: {e}")
            QMessageBox.critical(self, "Error", f"Failed to create new specimen: {str(e)}")
    
    def load_template(self):
        """Load specimen template"""
        try:
            # TODO: Implement template loading dialog
            # For now, just show a placeholder message
            QMessageBox.information(self, "Template Loading", "Template loading will be implemented with template manager")
            self.template_loaded.emit("template_name")
            
        except Exception as e:
            self.logger.error(f"Failed to load template: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load template: {str(e)}")
    
    def save_template(self):
        """Save current form as template"""
        try:
            # TODO: Implement template saving dialog
            # For now, just show a placeholder message
            QMessageBox.information(self, "Template Saving", "Template saving will be implemented with template manager")
            self.template_saved.emit("template_name")
            
        except Exception as e:
            self.logger.error(f"Failed to save template: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save template: {str(e)}")
    
    def validate_form(self):
        """Validate current form data"""
        try:
            errors = self.form_builder.validate_form(self.form_widget)
            
            if not errors:
                QMessageBox.information(self, "Validation", "Form validation passed!")
                self.status_label.setText("Validation passed")
            else:
                error_msg = "Validation errors found:\n\n"
                for field_uri, field_errors in errors.items():
                    error_msg += f"• {field_uri}: {', '.join(field_errors)}\n"
                
                QMessageBox.warning(self, "Validation Errors", error_msg)
                self.validation_error.emit(error_msg)
                self.status_label.setText("Validation failed")
            
        except Exception as e:
            self.logger.error(f"Failed to validate form: {e}")
            QMessageBox.critical(self, "Error", f"Failed to validate form: {str(e)}")
    
    def save_specimen(self):
        """Save current specimen data"""
        try:
            # First validate
            errors = self.form_builder.validate_form(self.form_widget)
            if errors:
                self.validate_form()  # Show errors to user
                return
            
            # Get form data
            data = self.form_builder.get_form_data(self.form_widget)
            
            # TODO: Implement actual saving with ontology
            # For now, just emit signal and update status
            self.specimen_saved.emit(data)
            self.is_modified = False
            self.original_data = data.copy()
            self.status_label.setText("Specimen saved")
            
            QMessageBox.information(self, "Save", "Specimen saved successfully!")
            
        except Exception as e:
            self.logger.error(f"Failed to save specimen: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save specimen: {str(e)}")
    
    def load_specimen_data(self, data: Dict[str, Any]):
        """Load specimen data into form"""
        try:
            success = self.form_builder.set_form_data(self.form_widget, data)
            if success:
                self.original_data = data.copy()
                self.is_modified = False
                self.status_label.setText("Specimen data loaded")
                self.specimen_loaded.emit(data)
            else:
                QMessageBox.warning(self, "Warning", "Some data could not be loaded")
                
        except Exception as e:
            self.logger.error(f"Failed to load specimen data: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load specimen data: {str(e)}")
    
    def get_form_data(self) -> Dict[str, Any]:
        """Get current form data"""
        try:
            return self.form_builder.get_form_data(self.form_widget)
        except Exception as e:
            self.logger.error(f"Failed to get form data: {e}")
            return {}
    
    def is_form_modified(self) -> bool:
        """Check if form has been modified"""
        try:
            return self.form_builder.is_form_modified(self.form_widget, self.original_data)
        except Exception as e:
            self.logger.error(f"Failed to check if form is modified: {e}")
            return False
    
    def get_form_complexity_analysis(self) -> Dict[str, Any]:
        """Get analysis of form complexity"""
        try:
            return self.form_builder.analyze_form_complexity("Specimen")
        except Exception as e:
            self.logger.error(f"Failed to analyze form complexity: {e}")
            return {}
    
    def change_layout_style(self, layout_style: LayoutStyle):
        """Change the form layout style"""
        try:
            self.status_label.setText("Changing layout...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)
            
            # Get current data
            current_data = self.form_builder.get_form_data(self.form_widget)
            
            # Rebuild form with new layout
            new_form = self.form_builder.build_form_with_layout("Specimen", layout_style, self.content_frame)
            
            # Replace form widget
            self._clear_content_layout()
            self.content_layout.addWidget(new_form)
            self.form_widget = new_form
            
            # Restore data
            self.form_builder.set_form_data(self.form_widget, current_data)
            
            self.status_label.setText(f"Layout changed to {layout_style.value}")
            self.progress_bar.setVisible(False)
            
        except Exception as e:
            self.logger.error(f"Failed to change layout: {e}")
            QMessageBox.critical(self, "Error", f"Failed to change layout: {str(e)}")
            self.status_label.setText("Error changing layout")
            self.progress_bar.setVisible(False)
    
    def refresh_form(self):
        """Refresh the form from ontology"""
        try:
            self.status_label.setText("Refreshing form...")
            self.form_builder.refresh_ontology()
            self._create_specimen_form()
        except Exception as e:
            self.logger.error(f"Failed to refresh form: {e}")
            QMessageBox.critical(self, "Error", f"Failed to refresh form: {str(e)}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get widget statistics"""
        try:
            form_stats = self.form_builder.get_statistics()
            return {
                'form_builder_stats': form_stats,
                'current_specimen_uri': self.current_specimen_uri,
                'is_modified': self.is_form_modified(),
                'form_created': self.form_widget is not None
            }
        except Exception as e:
            self.logger.error(f"Failed to get statistics: {e}")
            return {}