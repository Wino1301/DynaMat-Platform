"""
DynaMat Platform - Individual Manager Widget
Generic widget for creating/editing class individuals (User, Material, Equipment, etc.)
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QMessageBox, QFrame, QComboBox, QToolBar
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction

from ....ontology import OntologyManager
from ...builders.ontology_form_builder import OntologyFormBuilder
from ...parsers.individual_writer import IndividualWriter
from ....config import config

logger = logging.getLogger(__name__)


class IndividualManagerWidget(QWidget):
    """
    Generic individual creator for any ontology class.

    Features:
    - Class selector dropdown (auto-populated from ontology)
    - Dynamic form generation based on selected class
    - Create new individuals or load/edit existing ones
    - Saves to appropriate user_data/individuals/ file
    - Triggers ontology reload for GUI refresh
    """

    # Signals
    individual_saved = pyqtSignal(str, str)  # (class_uri, individual_uri)
    individual_loaded = pyqtSignal(str, dict)  # (class_uri, data)
    ontology_reloaded = pyqtSignal()

    def __init__(self, ontology_manager: OntologyManager, main_window=None, parent=None):
        super().__init__(parent)

        self.ontology_manager = ontology_manager
        self.main_window = main_window
        self.logger = logging.getLogger(__name__)

        # Initialize form builder
        self.form_builder = OntologyFormBuilder(ontology_manager)

        # Initialize individual writer
        self.individual_writer = IndividualWriter(ontology_manager)

        # State
        self.current_class_uri = None
        self.current_form_widget = None
        self.current_individual_uri = None  # Set when loading existing
        self.is_edit_mode = False

        self._setup_ui()
        self._populate_class_selector()

        self.logger.info("Individual Manager initialized")

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
        self.content_layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(self.content_frame)

        # Create status bar
        self._create_status_bar(layout)

    def _create_toolbar(self, parent_layout):
        """Create toolbar with class selector and actions"""
        toolbar = QToolBar()
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

        # Class selector label
        class_label = QLabel("  Select Class: ")
        toolbar.addWidget(class_label)

        # Class selector dropdown
        self.class_combo = QComboBox()
        self.class_combo.setMinimumWidth(200)
        self.class_combo.currentIndexChanged.connect(self.on_class_selected)
        toolbar.addWidget(self.class_combo)

        toolbar.addSeparator()

        # New action
        new_action = QAction("New", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_individual)
        toolbar.addAction(new_action)

        # Load existing action
        load_action = QAction("Load Existing", self)
        load_action.setShortcut("Ctrl+O")
        load_action.triggered.connect(self.load_existing_individual)
        toolbar.addAction(load_action)

        toolbar.addSeparator()

        # Save action
        save_action = QAction("Save", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_individual)
        toolbar.addAction(save_action)

        # Delete action (only visible in edit mode)
        self.delete_action = QAction("Delete", self)
        self.delete_action.triggered.connect(self.delete_individual)
        self.delete_action.setVisible(False)
        toolbar.addAction(self.delete_action)

        parent_layout.addWidget(toolbar)

    def _create_status_bar(self, parent_layout):
        """Create status bar"""
        self.status_bar = QFrame()
        self.status_bar.setFrameStyle(QFrame.Shape.StyledPanel)
        self.status_bar.setMaximumHeight(30)

        status_layout = QHBoxLayout(self.status_bar)
        status_layout.setContentsMargins(5, 2, 5, 2)

        # Status label
        self.status_label = QLabel("Select a class to begin")
        status_layout.addWidget(self.status_label)

        status_layout.addStretch()

        parent_layout.addWidget(self.status_bar)

    def _populate_class_selector(self):
        """Populate class selector from ontology"""
        try:
            self.class_combo.clear()
            self.class_combo.addItem("Select a class...", None)

            # Query ontology for classes with individuals
            classes = self.ontology_manager.get_classes_with_individuals()

            for class_info in classes:
                display_name = class_info['label']
                class_uri = class_info['uri']
                self.class_combo.addItem(display_name, class_uri)

            self.logger.info(f"Populated class selector with {len(classes)} classes")

        except Exception as e:
            self.logger.error(f"Failed to populate class selector: {e}", exc_info=True)
            QMessageBox.critical(
                self, "Error",
                f"Failed to load class list:\n\n{str(e)}"
            )

    def on_class_selected(self, index):
        """Handle class selection"""
        class_uri = self.class_combo.currentData()

        if not class_uri:
            self._clear_form_area()
            self.status_label.setText("Select a class to begin")
            return

        try:
            self.current_class_uri = class_uri
            self._generate_form_for_class(class_uri)

        except Exception as e:
            self.logger.error(f"Failed to handle class selection: {e}", exc_info=True)
            QMessageBox.critical(
                self, "Error",
                f"Failed to generate form:\n\n{str(e)}"
            )

    def _generate_form_for_class(self, class_uri: str):
        """Generate form for selected class"""
        try:
            self.logger.info(f"Generating form for class: {class_uri}")

            # Clear previous form
            self._clear_form_area()

            # Build form using ontology form builder
            self.current_form_widget = self.form_builder.build_form(
                class_uri,
                parent=self.content_frame
            )

            self.content_layout.addWidget(self.current_form_widget)

            # Update status
            class_name = self._get_class_name(class_uri)
            self.status_label.setText(f"Ready to create {class_name}")

            # Reset state
            self.current_individual_uri = None
            self.is_edit_mode = False
            self.delete_action.setVisible(False)

            self.logger.info(f"Form generated successfully for {class_name}")

        except Exception as e:
            self.logger.error(f"Failed to generate form: {e}", exc_info=True)
            raise

    def _clear_form_area(self):
        """Clear the form area"""
        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self.current_form_widget = None

    def _get_class_name(self, class_uri: str) -> str:
        """Extract class name from URI"""
        if "#" in class_uri:
            return class_uri.split("#")[-1]
        elif ":" in class_uri:
            return class_uri.split(":")[-1]
        else:
            return class_uri

    def new_individual(self):
        """Clear form for new individual"""
        if not self.current_form_widget:
            QMessageBox.warning(
                self, "No Form",
                "Please select a class first."
            )
            return

        try:
            self.form_builder.clear_form(self.current_form_widget)
            self.current_individual_uri = None
            self.is_edit_mode = False
            self.delete_action.setVisible(False)

            class_name = self._get_class_name(self.current_class_uri)
            self.status_label.setText(f"New {class_name}")

            self.logger.info("Form cleared for new individual")

        except Exception as e:
            self.logger.error(f"Failed to clear form: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to clear form: {str(e)}")

    def load_existing_individual(self):
        """Load existing individual for editing"""
        if not self.current_class_uri:
            QMessageBox.warning(
                self, "No Class Selected",
                "Please select a class first."
            )
            return

        QMessageBox.information(
            self, "Not Yet Implemented",
            "Loading existing individuals will be implemented in the next phase.\n\n"
            "For now, you can create new individuals."
        )

    def save_individual(self):
        """Save individual to TTL file"""
        if not self.current_class_uri or not self.current_form_widget:
            QMessageBox.warning(
                self, "No Form",
                "Please select a class first."
            )
            return

        try:
            # Validate form
            errors = self.form_builder.validate_form(self.current_form_widget)
            if errors:
                self._show_validation_errors(errors)
                return

            # Get form data
            data = self.form_builder.get_form_data(self.current_form_widget)

            if not data:
                QMessageBox.warning(
                    self, "Empty Form",
                    "Please fill in at least one field before saving."
                )
                return

            # Generate URI
            individual_uri = self._generate_individual_uri(self.current_class_uri, data)

            # Determine output path
            output_path = self._get_output_path(self.current_class_uri)

            # Save individual
            self.status_label.setText("Saving...")

            if self.is_edit_mode and self.current_individual_uri:
                # Update existing
                self.individual_writer.update_individual(
                    individual_uri=self.current_individual_uri,
                    form_data=data,
                    output_path=output_path
                )
                mode_text = "updated"
            else:
                # Create new
                self.individual_writer.write_individual(
                    class_uri=self.current_class_uri,
                    individual_uri=individual_uri,
                    form_data=data,
                    output_path=output_path
                )
                mode_text = "created"

            # Reload ontology (CRITICAL for making new individual available)
            self.logger.info("Reloading ontology to include new individual...")
            self.ontology_manager.reload_ontology()

            # Signal success
            self.individual_saved.emit(self.current_class_uri, individual_uri)
            self.ontology_reloaded.emit()

            class_name = self._get_class_name(self.current_class_uri)
            self.status_label.setText(f"{class_name} {mode_text} successfully")

            QMessageBox.information(
                self, "Success",
                f"{class_name} {mode_text} successfully!\n\n"
                f"URI: {individual_uri}\n"
                f"File: {output_path}\n\n"
                f"The new individual is now available in dropdowns."
            )

            # Update state
            self.current_individual_uri = individual_uri
            self.is_edit_mode = True
            self.delete_action.setVisible(True)

            self.logger.info(f"Individual {mode_text}: {individual_uri}")

        except ValueError as e:
            # Duplicate URI or other validation error
            self.logger.warning(f"Validation error: {e}")
            self.status_label.setText("Save failed")
            QMessageBox.warning(
                self, "Validation Error",
                str(e)
            )

        except Exception as e:
            self.logger.error(f"Failed to save individual: {e}", exc_info=True)
            self.status_label.setText("Save failed")
            QMessageBox.critical(
                self, "Save Error",
                f"Failed to save individual:\n\n{str(e)}\n\n"
                f"See log for details."
            )

    def delete_individual(self):
        """Delete current individual"""
        if not self.current_individual_uri:
            return

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete this individual?\n\n"
            f"URI: {self.current_individual_uri}\n\n"
            f"This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            output_path = self._get_output_path(self.current_class_uri)

            self.individual_writer.delete_individual(
                individual_uri=self.current_individual_uri,
                output_path=output_path
            )

            # Reload ontology
            self.ontology_manager.reload_ontology()
            self.ontology_reloaded.emit()

            class_name = self._get_class_name(self.current_class_uri)
            QMessageBox.information(
                self, "Deleted",
                f"{class_name} deleted successfully."
            )

            # Clear form
            self.new_individual()

            self.logger.info(f"Individual deleted: {self.current_individual_uri}")

        except Exception as e:
            self.logger.error(f"Failed to delete individual: {e}", exc_info=True)
            QMessageBox.critical(
                self, "Delete Error",
                f"Failed to delete individual:\n\n{str(e)}"
            )

    def _generate_individual_uri(self, class_uri: str, form_data: Dict[str, Any]) -> str:
        """Generate URI for individual based on class and data"""
        class_name = self._get_class_name(class_uri)

        # Strategy 1: Use dyn:hasName if available
        name_keys = [
            "dyn:hasName",
            "https://dynamat.utep.edu/ontology#hasName"
        ]

        for key in name_keys:
            if key in form_data and form_data[key]:
                name = str(form_data[key]).replace(" ", "_").replace("-", "_")
                return f"dyn:{class_name}_{name}"

        # Strategy 2: Class-specific patterns
        if class_name == "User":
            first = form_data.get("dyn:hasFirstName", form_data.get("https://dynamat.utep.edu/ontology#hasFirstName", ""))
            last = form_data.get("dyn:hasLastName", form_data.get("https://dynamat.utep.edu/ontology#hasLastName", ""))
            if first and last:
                return f"dyn:User_{first}{last}".replace(" ", "")

        elif class_name == "Material":
            code_keys = [
                "dyn:hasMaterialCode",
                "https://dynamat.utep.edu/ontology#hasMaterialCode"
            ]
            for key in code_keys:
                if key in form_data and form_data[key]:
                    code = str(form_data[key]).replace(" ", "_")
                    return f"dyn:{code}"

        # Strategy 3: Use rdfs:label
        label_keys = ["rdfs:label", "http://www.w3.org/2000/01/rdf-schema#label"]
        for key in label_keys:
            if key in form_data and form_data[key]:
                label = str(form_data[key]).replace(" ", "_").replace("-", "_")
                return f"dyn:{class_name}_{label}"

        # Strategy 4: Generic fallback (use first non-empty field)
        for key, value in form_data.items():
            if value and isinstance(value, str) and value.strip():
                clean_value = value.strip()[:20].replace(" ", "_").replace("-", "_")
                return f"dyn:{class_name}_{clean_value}"

        # Last resort: use timestamp
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"dyn:{class_name}_{timestamp}"

    def _get_output_path(self, class_uri: str) -> Path:
        """Determine output file path for class"""
        class_name = self._get_class_name(class_uri).lower()
        return config.USER_INDIVIDUALS_DIR / f"{class_name}_individuals.ttl"

    def _show_validation_errors(self, errors: Dict[str, list]):
        """Show validation errors to user"""
        error_msg = "Please fix the following errors:\n\n"

        for field_uri, field_errors in errors.items():
            # Extract field name from URI
            if "#" in field_uri:
                field_name = field_uri.split("#")[-1]
            elif ":" in field_uri:
                field_name = field_uri.split(":")[-1]
            else:
                field_name = field_uri

            error_msg += f"• {field_name}:\n"
            for error in field_errors:
                error_msg += f"  - {error}\n"
            error_msg += "\n"

        QMessageBox.warning(self, "Validation Errors", error_msg)
        self.status_label.setText("Validation failed")
