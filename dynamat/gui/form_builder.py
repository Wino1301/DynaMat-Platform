"""
DynaMat Platform - Ontology Form Builder (CORRECTED IMPORTS)
Generates PyQt6 forms from ontology class definitions
Compatible with refactored ontology module structure
"""

import logging
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QFormLayout, QGroupBox, QLabel, QLineEdit, QTextEdit,
    QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit,
    QCheckBox, QPushButton, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QDate
from PyQt6.QtGui import QFont

from rdflib import URIRef

# CORRECTED IMPORTS - Now import from ontology module level
from ..ontology import OntologyManager, PropertyMetadata, ClassMetadata, UnitInfo
from .dependency_manager import DependencyManager
from .widgets.unit_value_widget import UnitValueWidget

logger = logging.getLogger(__name__)


@dataclass
class FormField:
    """Represents a form field with its widget and metadata"""
    widget: QWidget
    property_uri: str
    property_metadata: PropertyMetadata
    group_name: str
    required: bool = False


class OntologyFormBuilder:
    """
    Builds PyQt6 forms from ontology class definitions.
    
    Automatically generates appropriate widgets based on property types,
    organizes fields into logical groups, and handles validation.
    """
    
    def __init__(self, ontology_manager: OntologyManager, dependency_config: Optional[str] = None):
        self.ontology_manager = ontology_manager
        self.logger = logging.getLogger(__name__)
        
        # Initialize dependency manager
        self.dependency_manager = None
        if dependency_config is not None:
            try:
                self.dependency_manager = DependencyManager(ontology_manager, dependency_config)
                self.logger.info("Dependency manager initialized")
            except Exception as e:
                self.logger.error(f"Failed to initialize dependency manager: {e}")
        else:
            # Try to use default config
            try:
                self.dependency_manager = DependencyManager(ontology_manager)
                self.logger.info("Dependency manager initialized with default config")
            except Exception as e:
                self.logger.warning(f"Dependency manager not available: {e}")
        
    def build_form(self, class_uri: str, parent: Optional[QWidget] = None) -> QWidget:
        """
        Build a complete form for the given class.
        
        Args:
            class_uri: URI of the ontology class
            parent: Parent widget
            
        Returns:
            Widget containing the complete form
        """
        print(f"@@@ build_form CALLED for {class_uri}")
        try:
            self.logger.info(f"Building form for class: {class_uri}")
            
            # Get class metadata - using the refactored method
            self.ontology_manager.classes_cache.clear()
            class_metadata = self.ontology_manager.get_class_metadata_for_form(class_uri)
            self.logger.info(f"Got metadata for {class_metadata.name} with {len(class_metadata.properties)} properties")
            
            if not class_metadata.properties:
                self.logger.warning("No properties found for class")
                error_widget = QLabel("No properties found for this class.")
                error_widget.setStyleSheet("color: red; padding: 20px; background-color: #2a1a1a; border: 1px solid red;")
                error_widget.setWordWrap(True)
                return error_widget
    
            # Create main form widget
            form_widget = QWidget(parent)
            main_layout = QVBoxLayout(form_widget)
            main_layout.setContentsMargins(0, 0, 0, 0)
            
            # Create scroll area for large forms
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            
            # Create content widget inside scroll area
            content_widget = QWidget()
            content_layout = QVBoxLayout(content_widget)
            
            # Build form groups using explicit group ordering
            form_fields = {}
            groups_created = 0
            
            # Sort form groups by their order
            ordered_groups = class_metadata.get_ordered_groups()
            
            for group_name in ordered_groups:
                group_properties = class_metadata.form_groups[group_name]
                
                if group_properties:  # Only create groups that have properties
                    group_widget, group_fields = self._build_form_group(group_name, group_properties)
                    
                    if group_fields:  # Only add groups that successfully created fields
                        content_layout.addWidget(group_widget)
                        form_fields.update(group_fields)
                        groups_created += 1
                        self.logger.debug(f"Created group '{group_name}' with {len(group_fields)} fields")
            
            # Handle ungrouped properties (shouldn't happen with good ontology design)
            ungrouped_props = []
            for prop in class_metadata.properties:
                if prop.uri not in form_fields:
                    ungrouped_props.append(prop)
            
            if ungrouped_props:
                self.logger.warning(f"Found {len(ungrouped_props)} ungrouped properties, adding to 'Other' group")
                group_widget, group_fields = self._build_form_group("Other", ungrouped_props)
                if group_fields:
                    content_layout.addWidget(group_widget)
                    form_fields.update(group_fields)
                    groups_created += 1
            
            if not form_fields:
                self.logger.error("No form fields were created")
                error_widget = QLabel("Failed to create form fields.\nCheck terminal for details.")
                error_widget.setStyleSheet("color: orange; padding: 20px;")
                return error_widget
            
            # Set content widget to scroll area
            scroll_area.setWidget(content_widget)
            main_layout.addWidget(scroll_area)
            
            # Store form fields in widget for later access
            form_widget.form_fields = form_fields
            form_widget.class_uri = class_uri
            form_widget.class_metadata = class_metadata
            
            # === Set up dependencies ===
            if self.dependency_manager:
                try:
                    self.logger.info("Setting up widget dependencies...")
                    self.dependency_manager.setup_dependencies(form_widget, class_uri)
                    self.logger.info("Widget dependencies configured successfully")
                except Exception as e:
                    self.logger.error(f"Failed to setup dependencies: {e}")
            else:
                self.logger.info("No dependency manager available, skipping dependency setup")
            
            self.logger.info(f"Form built successfully with {len(form_fields)} total fields in {groups_created} groups")
            return form_widget
            
        except Exception as e:
            self.logger.error(f"Failed to build form for {class_uri}: {e}", exc_info=True)
            # Return error widget
            error_widget = QLabel(f"Error building form:\n\n{str(e)}\n\nCheck terminal for details.")
            error_widget.setStyleSheet("color: red; padding: 20px; background-color: #2a1a1a; border: 1px solid red;")
            error_widget.setWordWrap(True)
            return error_widget

    def _build_form_group(self, group_name: str, properties: List[PropertyMetadata]) -> tuple:
        """
        Build a form group with its properties.
        
        Args:
            group_name: Name of the form group
            properties: List of properties in this group
            
        Returns:
            Tuple of (group_widget, field_dict)
        """
        # Format group name for display
        formatted_group_name = self._format_group_name(group_name)
        
        # Create group box
        group_box = QGroupBox(formatted_group_name)
        group_layout = QFormLayout(group_box)
        group_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        
        # Build fields
        group_fields = {}
        
        # Remove duplicates based on property URI (shouldn't happen but be safe)
        unique_properties = {}
        for prop in properties:
            if prop.uri not in unique_properties:
                unique_properties[prop.uri] = prop
            else:
                # Keep the one with more specific form group or lower display order
                existing = unique_properties[prop.uri]
                if (prop.form_group != "General" and existing.form_group == "General") or \
                   (prop.display_order < existing.display_order):
                    unique_properties[prop.uri] = prop
        
        # Sort by display order
        sorted_properties = sorted(unique_properties.values(), key=lambda p: p.display_order)
        
        for prop in sorted_properties:
            try:
                field_widget = self._create_field_widget(prop)
                if field_widget:
                    # Create label
                    label_text = prop.display_name
                    if prop.is_required:
                        label_text += " *"
                    
                    label = QLabel(label_text)
                    if prop.description:
                        label.setToolTip(prop.description)
                        field_widget.setToolTip(prop.description)
                    
                    # Add to form layout
                    group_layout.addRow(label, field_widget)
                    
                    # Store field
                    field = FormField(
                        widget=field_widget,
                        property_uri=prop.uri,
                        property_metadata=prop,
                        group_name=group_name,
                        required=prop.is_required
                    )
                    
                    group_fields[prop.uri] = field
                    
            except Exception as e:
                self.logger.error(f"Failed to create field widget for {prop.uri}: {e}")
        
        return group_box, group_fields
    
    def _format_group_name(self, group_name: str) -> str:
        """Format group name for display."""
        if not group_name or group_name == "General":
            return "General Properties"
        
        # Convert camelCase to Title Case
        formatted = ""
        for i, char in enumerate(group_name):
            if char.isupper() and i > 0:
                formatted += " "
            formatted += char
        
        return formatted.title()
    
    def _create_field_widget(self, prop: PropertyMetadata) -> Optional[QWidget]:
        """
        Create appropriate widget based on property metadata.
        
        Args:
            prop: Property metadata
            
        Returns:
            Widget for the property or None if creation failed
        """
        try:
            widget_type = prop.suggested_widget_type
            
            if widget_type == "line_edit":
                return self._create_line_edit_widget(prop)
            elif widget_type == "text_area":
                return self._create_text_area_widget(prop)
            elif widget_type == "combo":
                return self._create_combo_widget(prop)
            elif widget_type == "object_combo":
                return self._create_object_combo_widget(prop)
            elif widget_type == "checkbox":
                return self._create_checkbox_widget(prop)
            elif widget_type == "spinbox":
                return self._create_spinbox_widget(prop)
            elif widget_type == "double_spinbox":
                return self._create_double_spinbox_widget(prop)
            elif widget_type == "date":
                return self._create_date_widget(prop)
            else:
                # Default to line edit
                self.logger.debug(f"Unknown widget type '{widget_type}' for {prop.uri}, using line edit")
                return self._create_line_edit_widget(prop)
                
        except Exception as e:
            self.logger.error(f"Failed to create widget for {prop.uri}: {e}")
            return None
    
    def _create_line_edit_widget(self, prop: PropertyMetadata) -> QLineEdit:
        """Create a line edit widget."""
        widget = QLineEdit()
        if prop.max_length:
            widget.setMaxLength(prop.max_length)
        return widget
    
    def _create_text_area_widget(self, prop: PropertyMetadata) -> QTextEdit:
        """Create a text area widget."""
        widget = QTextEdit()
        widget.setMaximumHeight(100)  # Reasonable height for forms
        return widget
    
    def _create_combo_widget(self, prop: PropertyMetadata) -> QComboBox:
        """Create a combo box widget with valid values."""
        widget = QComboBox()
        if prop.valid_values:
            for value in prop.valid_values:
                widget.addItem(value, value)
        return widget
    
    def _create_object_combo_widget(self, prop: PropertyMetadata) -> QComboBox:
        """Create a combo box for object properties."""
        widget = QComboBox()
        # This would be populated with available individuals of the range class
        # For now, just add a placeholder
        widget.addItem("Select...", None)
        return widget
    
    def _create_checkbox_widget(self, prop: PropertyMetadata) -> QCheckBox:
        """Create a checkbox widget."""
        return QCheckBox()
    
    def _create_spinbox_widget(self, prop: PropertyMetadata) -> QSpinBox:
        """Create a spin box widget for integers."""
        widget = QSpinBox()
        if prop.min_value is not None:
            widget.setMinimum(int(prop.min_value))
        if prop.max_value is not None:
            widget.setMaximum(int(prop.max_value))
        return widget
    
    def _create_double_spinbox_widget(self, prop: PropertyMetadata) -> QDoubleSpinBox:
        """Create a double spin box widget for floats."""
        widget = QDoubleSpinBox()
        if prop.min_value is not None:
            widget.setMinimum(prop.min_value)
        if prop.max_value is not None:
            widget.setMaximum(prop.max_value)
        widget.setDecimals(3)  # Default to 3 decimal places
        return widget
    
    def _create_date_widget(self, prop: PropertyMetadata) -> QDateEdit:
        """Create a date widget."""
        widget = QDateEdit()
        widget.setDate(QDate.currentDate())
        widget.setCalendarPopup(True)
        return widget
    
    # ============================================================================
    # DATA EXTRACTION AND POPULATION METHODS
    # ============================================================================
    
    def get_form_data(self, form_widget: QWidget) -> Dict[str, Any]:
        """
        Extract data from form widgets.
        
        Args:
            form_widget: Widget created by build_form()
            
        Returns:
            Dictionary of property URIs to values
        """
        if not hasattr(form_widget, 'form_fields'):
            return {}
        
        data = {}
        
        for prop_uri, field in form_widget.form_fields.items():
            try:
                value = self._extract_widget_value(field.widget)
                if value is not None and value != "":
                    data[prop_uri] = value
            except Exception as e:
                self.logger.warning(f"Failed to extract value for {prop_uri}: {e}")
        
        return data
    
    def _extract_widget_value(self, widget: QWidget) -> Any:
        """Extract value from a widget - MODIFIED to handle UnitValueWidget"""
        if isinstance(widget, UnitValueWidget):
            # Return dictionary with value, unit, and unit symbol
            return widget.getData()
        elif isinstance(widget, QLineEdit):
            return widget.text()
        elif isinstance(widget, QComboBox):
            return widget.currentData() or widget.currentText()
        elif isinstance(widget, QSpinBox):
            return widget.value()
        elif isinstance(widget, QDoubleSpinBox):
            return widget.value()
        elif isinstance(widget, QDateEdit):
            return widget.date().toString(Qt.DateFormat.ISODate)
        elif isinstance(widget, QCheckBox):
            return widget.isChecked()
        elif isinstance(widget, QTextEdit):
            return widget.toPlainText()
        else:
            # Try to handle compound widgets (existing logic)
            if hasattr(widget, 'layout') and widget.layout():
                layout = widget.layout()
                if layout.count() > 0:
                    first_widget = layout.itemAt(0).widget()
                    return self._extract_widget_value(first_widget)
        
        return None
    
    def populate_form(self, form_widget: QWidget, data: Dict[str, Any]):
        """
        Populate form with data.
        
        Args:
            form_widget: Widget created by build_form()
            data: Dictionary of property URIs to values
        """
        if not hasattr(form_widget, 'form_fields'):
            return
        
        for prop_uri, value in data.items():
            if prop_uri in form_widget.form_fields:
                field = form_widget.form_fields[prop_uri]
                try:
                    self._populate_widget_value(field.widget, value)
                except Exception as e:
                    self.logger.warning(f"Failed to populate value for {prop_uri}: {e}")
    
    def _populate_widget_value(self, widget: QWidget, value: Any):
        """Populate widget with value - MODIFIED to handle UnitValueWidget"""
        if isinstance(widget, UnitValueWidget):
            if isinstance(value, dict):
                widget.setData(value)
            else:
                widget.setValue(value)
        elif isinstance(widget, QLineEdit):
            widget.setText(str(value))
        elif isinstance(widget, QComboBox):
            # Try to find and set the value
            index = widget.findData(value)
            if index >= 0:
                widget.setCurrentIndex(index)
            else:
                # Try by text
                index = widget.findText(str(value))
                if index >= 0:
                    widget.setCurrentIndex(index)
        elif isinstance(widget, QSpinBox):
            widget.setValue(int(value))
        elif isinstance(widget, QDoubleSpinBox):
            widget.setValue(float(value))
        elif isinstance(widget, QDateEdit):
            if isinstance(value, str):
                widget.setDate(QDate.fromString(value, Qt.DateFormat.ISODate))
            else:
                widget.setDate(QDate.fromString(str(value), Qt.DateFormat.ISODate))
        elif isinstance(widget, QCheckBox):
            widget.setChecked(bool(value))
        elif isinstance(widget, QTextEdit):
            widget.setPlainText(str(value))
    
    def validate_form(self, form_widget: QWidget) -> Dict[str, List[str]]:
        """
        Validate form data.
        
        Args:
            form_widget: Widget created by build_form()
            
        Returns:
            Dictionary of field URIs to list of validation errors
        """
        errors = {}
        
        if not hasattr(form_widget, 'form_fields'):
            return errors
        
        for prop_uri, field in form_widget.form_fields.items():
            field_errors = []
            
            # Check required fields
            if field.required:
                value = self._extract_widget_value(field.widget)
                if value is None or (isinstance(value, str) and value.strip() == ""):
                    field_errors.append("This field is required")
            
            # Additional validation could be added here based on property metadata
            # e.g., min/max values, patterns, etc.
            
            if field_errors:
                errors[prop_uri] = field_errors
        
        return errors