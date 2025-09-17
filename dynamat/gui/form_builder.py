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
            
            # Get class metadata
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
            
            # Build form groups
            form_fields = {}
            groups_created = 0
            
            # Sort form groups by minimum display order
            sorted_groups = sorted(class_metadata.form_groups.items(), 
                                 key=lambda x: min(p.display_order for p in x[1]) if x[1] else 999)
            
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
        
        # Remove duplicates based on property URI
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
            Appropriate Qt widget or None if unsupported
        """
        try:
            if prop.data_type == "object":
                # Object property - create dropdown with valid individuals
                return self._create_object_dropdown(prop)
            
            elif prop.data_type == "data":
                # Data property - determine widget based on range
                return self._create_data_widget(prop)
            
            else:
                self.logger.warning(f"Unknown property type: {prop.data_type}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error creating widget for {prop.uri}: {e}")
            return None
    
    def _create_object_dropdown(self, prop: PropertyMetadata) -> QComboBox:
        """Create dropdown for object properties"""
        combo = QComboBox()
        combo.setEditable(False)
        
        # Add empty option for optional properties
        if not prop.is_required:
            combo.addItem("(None)", "")
        
        # Get valid values
        valid_values = []
        if prop.valid_values:
            # Use predefined valid values
            valid_values = prop.valid_values
        elif prop.range_class:
            # Get individuals of the range class
            try:
                individuals = self.ontology_manager.get_all_individuals(prop.range_class)
                valid_values = individuals
            except Exception as e:
                self.logger.warning(f"Failed to get individuals for {prop.range_class}: {e}")
                valid_values = []
        
        # Add options to combo box
        for value in valid_values:
            if value and value.strip():  # Skip empty values
                if value.startswith("http"):
                    # Extract display name from URI
                    display_name = self._extract_display_name_from_ontology(value)
                    if display_name and not display_name.startswith("n"):  # Skip blank nodes
                        combo.addItem(display_name, value)
                else:
                    combo.addItem(value, value)
        
        # If no valid options were added, add a placeholder
        if combo.count() <= (1 if not prop.is_required else 0):
            combo.addItem("(No options available)", "")
        
        return combo
    
    def _extract_display_name_from_ontology(self, uri: str) -> str:
        """Extract display name from ontology using proper SPARQL query"""
        if not uri or not uri.startswith("http"):
            return uri
        
        try:
            # First try to get rdfs:label
            query = """
            SELECT ?label WHERE {
                ?individual rdfs:label ?label .
            }
            """
            result = self.ontology_manager._execute_query(query, {"individual": URIRef(uri)})
            if result:
                label = str(result[0].label)
                if label and not label.startswith("n"):  # Avoid blank node IDs
                    return label
            
            # Try dyn:hasName if available
            query = """
            SELECT ?name WHERE {
                ?individual dyn:hasName ?name .
            }
            """
            result = self.ontology_manager._execute_query(query, {"individual": URIRef(uri)})
            if result:
                name = str(result[0].name)
                if name and not name.startswith("n"):
                    return name
            
            # Fall back to extracting from URI
            return self._extract_display_name(uri)
            
        except Exception as e:
            self.logger.warning(f"Failed to extract display name for {uri}: {e}")
            return self._extract_display_name(uri)
    
    def _create_data_widget(self, prop: PropertyMetadata) -> QWidget:
        """Create widget for data properties based on their range"""
        if not prop.range_class:
            # Default to string if no range specified
            return self._create_string_widget(prop)
        
        range_type = prop.range_class.lower()
        
        if "string" in range_type:
            return self._create_string_widget(prop)
        elif "int" in range_type or "integer" in range_type:
            return self._create_integer_widget(prop)
        elif "float" in range_type or "double" in range_type or "decimal" in range_type:
            return self._create_float_widget(prop)
        elif "date" in range_type:
            return self._create_date_widget(prop)
        elif "boolean" in range_type:
            return self._create_boolean_widget(prop)
        else:
            # Default to string for unknown types
            return self._create_string_widget(prop)
    
    def _create_string_widget(self, prop: PropertyMetadata) -> QWidget:
        """Create string input widget"""
        if prop.valid_values:
            # Create dropdown for string with valid values
            combo = QComboBox()
            combo.setEditable(True)  # Allow custom values
            if not prop.is_required:
                combo.addItem("", "")
            for value in prop.valid_values:
                combo.addItem(value, value)
            return combo
        else:
            # Create line edit for free text
            line_edit = QLineEdit()
            line_edit.setMaxLength(255)  # Reasonable default
            return line_edit
    
    def _create_integer_widget(self, prop: PropertyMetadata) -> QSpinBox:
        """Create integer input widget"""
        spin_box = QSpinBox()
        spin_box.setMinimum(-2147483648)  # int32 min
        spin_box.setMaximum(2147483647)   # int32 max
        return spin_box
    
    def _create_float_widget(self, prop: PropertyMetadata) -> QDoubleSpinBox:
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
    
    def _extract_display_name(self, uri: str) -> str:
        """Extract display name from URI with better formatting"""
        if not uri:
            return "Unknown"
        
        try:
            # Extract the local name from URI
            if "#" in uri:
                name = uri.split("#")[-1]
            elif "/" in uri:
                name = uri.split("/")[-1]
            else:
                name = uri
            
            # Skip blank node identifiers
            if name.startswith("n") and len(name) > 10 and name[1:].replace("-", "").isalnum():
                return "Unknown"
            
            # Convert camelCase and PascalCase to Title Case
            result = ""
            for i, char in enumerate(name):
                if char.isupper() and i > 0 and name[i-1].islower():
                    result += " "
                elif char.isupper() and i > 0 and i < len(name) - 1 and name[i+1].islower():
                    result += " "
                result += char
            
            return result.replace("_", " ").title()
            
        except Exception as e:
            self.logger.warning(f"Failed to extract display name from {uri}: {e}")
            return "Unknown"
    
    def _extract_unit_symbol(self, unit_uri: str) -> str:
        """Extract unit symbol from QUDT URI"""
        # This would need to query the QUDT ontology for proper unit symbols
        # For now, return simplified version
        if "METER" in unit_uri.upper():
            return "m"
        elif "GRAM" in unit_uri.upper():
            return "g"
        elif "SECOND" in unit_uri.upper():
            return "s"
        elif "PASCAL" in unit_uri.upper():
            return "Pa"
        else:
            return "unit"
    
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
            if hasattr(widget, 'layout'):
                layout = widget.layout()
                if layout and layout.count() > 0:
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
                    self._set_widget_value(field.widget, value)
                except Exception as e:
                    self.logger.warning(f"Failed to set value for {prop_uri}: {e}")
    
    def _set_widget_value(self, widget: QWidget, value: Any):
        """Set value in a widget"""
        if isinstance(widget, QLineEdit):
            widget.setText(str(value))
        elif isinstance(widget, QComboBox):
            # Try to find by data first, then by text
            index = widget.findData(value)
            if index >= 0:
                widget.setCurrentIndex(index)
            else:
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
