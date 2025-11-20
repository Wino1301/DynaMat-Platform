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
from ....ontology.qudt import QUDTManager
from ...builders.ontology_form_builder import OntologyFormBuilder
from ...builders.layout_manager import LayoutStyle
from ...parsers.instance_writer import InstanceWriter
from ...widgets.validation_results_dialog import ValidationResultsDialog
from ...core.form_validator import ValidationResult

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
    
    def __init__(self, ontology_manager: OntologyManager, main_window=None, parent=None):
        super().__init__(parent)

        self.ontology_manager = ontology_manager
        self.main_window = main_window
        self.logger = logging.getLogger(__name__)

        # Initialize QUDT manager for unit conversions
        try:
            self.qudt_manager = QUDTManager()
            self.qudt_manager.load()
            self.logger.info("QUDT manager initialized successfully")
        except Exception as e:
            self.logger.warning(f"Failed to initialize QUDT manager: {e}")
            self.qudt_manager = None

        # Initialize instance writer for TTL serialization
        self.instance_writer = InstanceWriter(ontology_manager, self.qudt_manager)

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
            
            # Debug: Check ontology manager
            if not self.ontology_manager:
                raise RuntimeError("Ontology manager is not initialized")
            
            # Debug: Check if we can get class metadata
            specimen_uri = "https://dynamat.utep.edu/ontology#Specimen"
            try:
                class_metadata = self.ontology_manager.get_class_metadata_for_form(specimen_uri)
                self.logger.info(f"Found {len(class_metadata.properties)} properties for specimen")
                self.logger.info(f"Form groups: {list(class_metadata.form_groups.keys())}")
            except Exception as e:
                self.logger.error(f"Failed to get class metadata: {e}")
                raise RuntimeError(f"Cannot load specimen metadata: {e}")
            
            # Create form using the builder
            self.form_widget = self.form_builder.build_form(specimen_uri, self.content_frame)
            
            if not self.form_widget:
                raise RuntimeError("Form builder returned None")
            
            # Clear existing content and add new form
            self._clear_content_layout()
            self.content_layout.addWidget(self.form_widget)
            
            # Enhanced debugging: Check form widget attributes
            expected_attrs = ['form_fields', 'class_uri', 'form_style', 'widgets_created']
            missing_attrs = [attr for attr in expected_attrs if not hasattr(self.form_widget, attr)]
            
            if missing_attrs:
                self.logger.warning(f"Form widget missing attributes: {missing_attrs}")
            
            # Check if form has fields
            if hasattr(self.form_widget, 'form_fields'):
                field_count = len(self.form_widget.form_fields)
                self.logger.info(f"Form created successfully with {field_count} fields")
                
                # Log field details for debugging
                for field_uri, field in self.form_widget.form_fields.items():
                    self.logger.debug(f"  Field: {field.property_metadata.display_name} (Group: {field.group_name})")
                
                self.status_label.setText(f"Specimen form loaded with {field_count} fields")
            else:
                self.logger.warning("Form widget has no form_fields attribute")
                self.status_label.setText("Specimen form loaded (no fields detected)")
            
            # Store original empty data
            try:
                self.original_data = self.form_builder.get_form_data(self.form_widget)
            except Exception as e:
                self.logger.warning(f"Could not get initial form data: {e}")
                self.original_data = {}
            
            self.status_label.setText("Form created successfully")
            self.progress_bar.setVisible(False)
            
            self.logger.info("Specimen form created successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to create specimen form: {e}", exc_info=True)
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

    def _extract_specimen_id(self, form_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract specimen ID from form data, trying multiple possible key formats.

        Args:
            form_data: Dictionary of form data

        Returns:
            Specimen ID string, or None if not found
        """
        # Try different possible key formats
        possible_keys = [
            "https://dynamat.utep.edu/ontology#hasSpecimenID",
            "dyn:hasSpecimenID",
            "hasSpecimenID"
        ]

        for key in possible_keys:
            if key in form_data and form_data[key]:
                return str(form_data[key]).strip()

        # If not found with exact match, try searching for keys that contain "SpecimenID"
        for key in form_data.keys():
            if "SpecimenID" in key or "specimenid" in key.lower():
                value = form_data[key]
                if value:
                    self.logger.info(f"Found specimen ID with key: {key}")
                    return str(value).strip()

        self.logger.warning("Specimen ID not found in form data")
        return None

    def _compute_specimen_output_path(self, form_data: Dict[str, Any]) -> Optional[Path]:
        """
        Compute output file path for specimen TTL file (without creating directories).

        NOTE: This method does NOT create any directories. Folders are created only
        after validation passes to avoid leaving empty directories when validation fails.

        Path structure: specimens/SPN-{MaterialID}-{XXX}/SPN-{MaterialID}-{XXX}_specimen.ttl

        Args:
            form_data: Dictionary of form data

        Returns:
            Path object for the output file, or None if specimen ID is missing
        """
        # Extract specimen ID from form data
        specimen_id = self._extract_specimen_id(form_data)

        if not specimen_id:
            self.logger.error("Cannot generate output path: Specimen ID is missing from form data")
            return None

        # Clean specimen ID (replace spaces and special characters)
        clean_id = specimen_id.replace(" ", "-").replace("_", "-")

        # Compute directory structure (no folder creation)
        # specimens/SPN-{MaterialID}-{XXX}/
        specimens_dir = Path("specimens")
        specimen_folder = specimens_dir / clean_id

        # Compute output file path
        # specimens/SPN-{MaterialID}-{XXX}/SPN-{MaterialID}-{XXX}_specimen.ttl
        output_file = specimen_folder / f"{clean_id}_specimen.ttl"

        self.logger.info(f"Computed output path: {output_file}")
        return output_file

    def _show_validation_results(self, validation_result: ValidationResult, allow_save: bool = True) -> int:
        """
        Show validation results dialog to user.

        Args:
            validation_result: Validation result from SHACL validation
            allow_save: Whether to show "Save Anyway" button (only if no violations)

        Returns:
            Dialog result code (QMessageBox.StandardButton.Ok if user accepted)
        """
        try:
            # Create and show validation results dialog
            dialog = ValidationResultsDialog(validation_result, parent=self)
            result = dialog.exec()

            self.logger.info(f"Validation dialog closed with result: {result}")
            return result

        except Exception as e:
            self.logger.error(f"Failed to show validation results dialog: {e}", exc_info=True)
            # Fallback to simple message box
            QMessageBox.warning(
                self, "Validation Issues",
                f"Validation issues detected:\n\n{validation_result.get_summary()}"
            )
            return QMessageBox.StandardButton.Ok

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
        """Save current specimen data to TTL file with unit conversion and SHACL validation"""
        try:
            # First validate form structure
            errors = self.form_builder.validate_form(self.form_widget)
            if errors:
                self.validate_form()  # Show errors to user
                return

            # Get form data
            data = self.form_builder.get_form_data(self.form_widget)

            # Debug: Log all form data keys to see what we're getting
            self.logger.debug("Form data keys:")
            for key in data.keys():
                self.logger.debug(f"  - {key}: {data[key]}")

            # Extract specimen ID - try multiple possible key formats
            specimen_id = self._extract_specimen_id(data)
            if not specimen_id:
                QMessageBox.critical(
                    self, "Save Error",
                    "Cannot save specimen: Specimen ID is required.\n\n"
                    "Please fill in the Specimen ID field before saving."
                )
                return

            self.logger.info(f"Extracted specimen ID: {specimen_id}")

            # Compute output path (does not create folders yet)
            output_path = self._compute_specimen_output_path(data)
            if not output_path:
                QMessageBox.critical(
                    self, "Save Error",
                    "Failed to generate output file path.\n\n"
                    "Please check the specimen ID format."
                )
                return

            self.logger.info(f"Computed output path: {output_path}")

            # === ADD METADATA TRACKING ===
            # Add metadata for creation/modification tracking
            from datetime import datetime
            from dynamat.config import config

            # Get current user from main window
            current_user = None
            if self.main_window and hasattr(self.main_window, 'get_current_user'):
                current_user = self.main_window.get_current_user()

            # Detect if this is a new file or editing existing
            is_new_file = not output_path.exists()

            # Add metadata fields
            if current_user:
                if is_new_file:
                    # New file: add creation metadata
                    data['dyn:hasCreatedBy'] = current_user
                    data['dyn:hasCreatedDate'] = datetime.now().isoformat()
                    data['dyn:hasAppVersion'] = config.VERSION
                    self.logger.info(f"Added creation metadata for new specimen (user: {current_user})")
                else:
                    # Editing existing file: add modification metadata
                    # Keep existing creation metadata, add modification metadata
                    data['dyn:hasModifiedBy'] = current_user
                    data['dyn:hasModifiedDate'] = datetime.now().isoformat()
                    data['dyn:hasAppVersion'] = config.VERSION
                    self.logger.info(f"Added modification metadata for existing specimen (user: {current_user})")
            else:
                self.logger.warning("No user selected - metadata tracking will be incomplete")

            # Update status
            self.status_label.setText("Saving specimen with unit conversion and validation...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)  # Indeterminate

            # Write instance with automatic unit conversion and SHACL validation
            # Use the specimen_id directly (already cleaned by _extract_specimen_id)
            saved_path, validation_result = self.instance_writer.write_instance(
                form_data=data,
                class_uri="https://dynamat.utep.edu/ontology#Specimen",
                instance_id=specimen_id,  # Use the extracted specimen ID
                output_path=output_path
            )

            self.progress_bar.setVisible(False)

            # Handle validation results
            if saved_path is None:
                # Save was blocked by validation violations
                self._show_validation_results(validation_result, allow_save=False)
                self.status_label.setText("Save blocked by validation errors")
                return

            # Validation passed - now safe to create specimen subdirectories
            # (main folder already created by instance_writer)
            specimen_folder = Path(saved_path).parent
            try:
                (specimen_folder / "raw").mkdir(exist_ok=True)
                (specimen_folder / "processed").mkdir(exist_ok=True)
                self.logger.info(f"Created subdirectories in {specimen_folder}")
            except Exception as e:
                self.logger.warning(f"Failed to create subdirectories: {e}")
                # Non-critical error, continue with save

            # Check if there are warnings or infos (non-blocking issues)
            if validation_result.has_any_issues():
                # Show dialog, user can choose to continue or cancel
                user_choice = self._show_validation_results(validation_result, allow_save=True)
                if user_choice != QMessageBox.StandardButton.Ok:
                    # User canceled, but file was already saved
                    self.status_label.setText("Specimen saved (with warnings)")
                else:
                    self.status_label.setText("Specimen saved successfully")
            else:
                # No issues, save was completely successful
                self.status_label.setText("Specimen saved successfully")
                QMessageBox.information(
                    self, "Save Successful",
                    f"Specimen saved successfully!\n\nFile: {saved_path}\n\n"
                    f"- Unit conversions applied\n"
                    f"- SHACL validation passed"
                )

            # Update form state
            self.specimen_saved.emit(data)
            self.is_modified = False
            self.original_data = data.copy()
            self.current_specimen_uri = f"https://dynamat.utep.edu/ontology#{specimen_id}"

            self.logger.info(f"Specimen {specimen_id} saved successfully to {saved_path}")

        except Exception as e:
            self.logger.error(f"Failed to save specimen: {e}", exc_info=True)
            self.progress_bar.setVisible(False)
            self.status_label.setText("Save failed")
            QMessageBox.critical(
                self, "Save Error",
                f"Failed to save specimen:\n\n{str(e)}\n\n"
                f"See log for details."
            )
    
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