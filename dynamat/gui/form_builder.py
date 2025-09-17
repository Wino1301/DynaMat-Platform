"""
DynaMat Platform - Ontology Form Builder
Generates PyQt6 forms from ontology class definitions
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

from ..ontology.manager import OntologyManager, PropertyMetadata, ClassMetadata

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
    
    def __init__(self, ontology_manager: OntologyManager):
        self.ontology_manager = ontology_manager
        self.logger = logging.getLogger(__name__)
        
    def build_form(self, class_uri: str, parent: Optional[QWidget] = None) -> QWidget:
        """
        Build a complete form for the given class.
        
        Args:
            class_uri: URI of the ontology class
            parent: Parent widget
            
        Returns:
            Widget containing the complete form
        """
        try:
            self.logger.info(f"Building form for class: {class_uri}")
            
            # Get class metadata - using your existing method
            class_metadata = self.ontology_manager.get_class_metadata_for_form(class_uri)
            self.logger.info(f"Got metadata for {class_metadata.name} with {len(class_metadata.properties)} properties")
            
            if not class_metadata.properties:
                self.logger.warning("No properties found for class")
                error_widget = QLabel("No properties found for this class.")
                error_widget.setStyleSheet("color: orange; padding: 20px;")
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
            
            # Build form groups - use existing form_groups from ontology manager
            form_fields = {}
            groups_created = 0
            
            # Sort form groups by the minimum display order of properties within each group
            def get_group_min_order(group_items):
                group_name, group_properties = group_items
                if not group_properties:
                    return 999
                return min(p.display_order for p in group_properties)
            
            sorted_groups = sorted(class_metadata.form_groups.items(), key=get_group_min_order)
            
            for group_name, group_properties in sorted_groups:
                if group_properties:  # Only create groups with properties
                    self.logger.info(f"Creating group '{group_name}' with {len(group_properties)} properties")
                    
                    group_widget, group_fields = self._build_form_group(group_name, group_properties)
                    content_layout.addWidget(group_widget)
                    form_fields.update(group_fields)
                    groups_created += 1
                    
                    self.logger.info(f"Group '{group_name}' created with {len(group_fields)} fields")
            
            if groups_created == 0:
                self.logger.warning("No form groups were created")
                error_widget = QLabel("No form groups could be created.")
                error_widget.setStyleSheet("color: orange; padding: 20px;")
                return error_widget
            
            # Set content widget to scroll area
            scroll_area.setWidget(content_widget)
            main_layout.addWidget(scroll_area)
            
            # Store form fields in widget for later access
            form_widget.form_fields = form_fields
            form_widget.class_uri = class_uri
            form_widget.class_metadata = class_metadata
            
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
                self.logger.warning(f"Failed to create field for {prop.uri}: {e}")
                continue
        
        return group_box, group_fields
    
    def _format_group_name(self, group_name: str) -> str:
        """Format group name for display"""
        if not group_name or group_name == "General":
            return "General Information"
        
        # Convert camelCase or snake_case to Title Case
        formatted = group_name.replace("_", " ")
        
        # Split camelCase
        result = ""
        for i, char in enumerate(formatted):
            if char.isupper() and i > 0 and formatted[i-1].islower():
                result += " "
            result += char
        
        return result.title()
    
    def _create_field_widget(self, prop: PropertyMetadata) -> Optional[QWidget]:
        """
        Create appropriate widget for a property based on its metadata.
        
        Args:
            prop: Property metadata
            
        Returns:
            Appropriate widget for the property
        """
        # Use the actual data_type attribute from your PropertyMetadata
        data_type = prop.data_type.lower()
        
        # Handle different data types based on your ontology structure
        if data_type == "object":
            # Object properties - create combo with valid instances
            return self._create_object_combo_widget(prop)
        elif "string" in data_type or data_type == "data":
            # String/text properties
            if prop.valid_values:
                return self._create_combo_widget(prop)
            else:
                return self._create_string_widget(prop)
        elif "int" in data_type:
            return self._create_integer_widget(prop)
        elif "double" in data_type or "float" in data_type:
            return self._create_float_widget(prop)
        elif "date" in data_type:
            return self._create_date_widget(prop)
        elif "bool" in data_type:
            return self._create_boolean_widget(prop)
        else:
            # Default to string widget for unknown types
            self.logger.info(f"Unknown data type '{data_type}' for {prop.uri}, using string widget")
            return self._create_string_widget(prop)
    
    def _create_string_widget(self, prop: PropertyMetadata) -> QWidget:
        """Create string input widget"""
        if prop.description and ("note" in prop.description.lower() or "description" in prop.description.lower()):
            # Use text area for notes and descriptions
            text_edit = QTextEdit()
            text_edit.setMaximumHeight(100)
            return text_edit
        else:
            # Use line edit for regular strings
            line_edit = QLineEdit()
            line_edit.setMaxLength(255)  # Reasonable default
            return line_edit
    
    def _create_combo_widget(self, prop: PropertyMetadata) -> QComboBox:
        """Create combo box widget with valid values"""
        combo = QComboBox()
        
        # Add empty option for non-required fields
        if not prop.is_required:
            combo.addItem("", "")
        
        # Add valid values
        for value in prop.valid_values:
            if value.strip():  # Skip empty values
                combo.addItem(value.strip(), value.strip())
        
        return combo
    
    def _create_object_combo_widget(self, prop: PropertyMetadata) -> QComboBox:
        """Create combo box for object properties"""
        combo = QComboBox()
        
        # Add empty option
        combo.addItem("", "")
        
        # Try to get available instances for the range class
        if prop.range_class:
            try:
                instances = self.ontology_manager.get_all_individuals(prop.range_class)
                for instance in instances:
                    # Extract display name from URI
                    display_name = instance.split('#')[-1].replace('_', ' ')
                    combo.addItem(display_name, instance)
            except Exception as e:
                self.logger.warning(f"Could not load instances for {prop.range_class}: {e}")
        
        return combo
    
    def _create_integer_widget(self, prop: PropertyMetadata) -> QSpinBox:
        """Create integer input widget"""
        spin_box = QSpinBox()
        spin_box.setMinimum(-2147483648)  # int32 min
        spin_box.setMaximum(2147483647)   # int32 max
        return spin_box
    
    def _create_float_widget(self, prop: PropertyMetadata) -> QWidget:
        """Create float input widget"""
        spin_box = QDoubleSpinBox()
        spin_box.setMinimum(-1e10)
        spin_box.setMaximum(1e10)
        spin_box.setDecimals(6)
        
        # Add unit label if available
        if prop.default_unit:
            unit_widget = QWidget()
            layout = QHBoxLayout(unit_widget)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(spin_box)
            unit_label = QLabel(self._extract_unit_symbol(prop.default_unit))
            unit_label.setStyleSheet("font-weight: bold; color: gray;")
            layout.addWidget(unit_label)
            return unit_widget
        
        return spin_box
    
    def _create_date_widget(self, prop: PropertyMetadata) -> QDateEdit:
        """Create date input widget"""
        date_edit = QDateEdit()
        date_edit.setDate(QDate.currentDate())
        date_edit.setCalendarPopup(True)
        return date_edit
    
    def _create_boolean_widget(self, prop: PropertyMetadata) -> QCheckBox:
        """Create boolean input widget"""
        checkbox = QCheckBox()
        return checkbox
    
    def _extract_unit_symbol(self, unit_uri: str) -> str:
        """Extract unit symbol from unit URI"""
        if not unit_uri:
            return ""
        
        # Simple extraction from common unit URIs
        unit_mappings = {
            "unit:MilliM": "mm",
            "unit:MilliM2": "mm²", 
            "unit:MilliM3": "mm³",
            "unit:GRAM": "g",
            "unit:KiloGRAM": "kg",
            "unit:MegaPA": "MPa",
            "unit:PA": "Pa",
            "unit:PERCENT": "%",
            "unit:DegreeCelsius": "°C",
        }
        
        return unit_mappings.get(unit_uri, unit_uri.split(":")[-1])
    
    def get_form_data(self, form_widget: QWidget) -> Dict[str, Any]:
        """
        Extract data from form widget.
        
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
        """Extract value from a widget"""
        if isinstance(widget, QLineEdit):
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
            # Try to handle compound widgets (like float with unit)
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
        """Populate a widget with a value"""
        if isinstance(widget, QLineEdit):
            widget.setText(str(value))
        elif isinstance(widget, QComboBox):
            index = widget.findData(value)
            if index >= 0:
                widget.setCurrentIndex(index)
            else:
                # Try to find by text
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
        elif isinstance(widget, QCheckBox):
            widget.setChecked(bool(value))
        elif isinstance(widget, QTextEdit):
            widget.setPlainText(str(value))
        else:
            # Handle compound widgets
            if hasattr(widget, 'layout') and widget.layout():
                layout = widget.layout()
                if layout.count() > 0:
                    first_widget = layout.itemAt(0).widget()
                    self._populate_widget_value(first_widget, value)