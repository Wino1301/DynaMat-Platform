"""
DynaMat Platform - Widget Factory
Centralized widget creation from ontology metadata
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QTextEdit, QComboBox, 
    QSpinBox, QDoubleSpinBox, QDateEdit, QCheckBox, 
    QHBoxLayout, QFrame
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont

from ...ontology import PropertyMetadata, OntologyManager

logger = logging.getLogger(__name__)


class WidgetFactory:
    """
    Centralized factory for creating form widgets from ontology metadata.
    
    Handles all widget creation logic, including specialized widgets like
    unit-value combinations and ontology-based combo boxes.
    """
    
    def __init__(self, ontology_manager: OntologyManager):
        """
        Initialize the widget factory.
        
        Args:
            ontology_manager: The ontology manager instance
        """
        self.ontology_manager = ontology_manager
        self.logger = logging.getLogger(__name__)
        
        # Widget type mapping
        self.widget_creators = {
            'line_edit': self._create_line_edit_widget,
            'text_area': self._create_text_area_widget,
            'combo': self._create_combo_widget,
            'object_combo': self._create_object_combo_widget,
            'spinbox': self._create_spinbox_widget,
            'double_spinbox': self._create_double_spinbox_widget,
            'checkbox': self._create_checkbox_widget,
            'date': self._create_date_widget,
            'unit_value': self._create_unit_value_widget
        }
    
    def create_widget(self, property_metadata: PropertyMetadata) -> QWidget:
        """
        Create appropriate widget for a property based on its metadata.
        """
        try:
            # Determine widget type using systematic approach
            widget_type = self._determine_widget_type(property_metadata)

            self.logger.debug(
                f"Creating widget for {property_metadata.name}: "
                f"type={widget_type}, data_type={property_metadata.data_type}"
            )

            # Get widget creator function
            creator_func = self.widget_creators.get(widget_type, self._create_line_edit_widget)

            # Create widget
            widget = creator_func(property_metadata)

            # Apply common styling and constraints
            self._apply_common_properties(widget, property_metadata)

            return widget

        except Exception as e:
            self.logger.error(f"Failed to create widget for {property_metadata.name}: {e}")
            return self._create_error_widget(f"Error: {str(e)}")

    def _determine_widget_type(self, prop: PropertyMetadata) -> str:
        """
        Determine the appropriate widget type for a property.

        Priority order:
        1. Measurement properties (has compatible_units) -> unit_value
        2. Object properties (data_type=object, references to individuals) -> object_combo
        3. Suggested widget type from metadata
        4. Fallback based on data_type

        Args:
            prop: Property metadata

        Returns:
            Widget type string
        """
        # Priority 1: Measurement properties with units (e.g., length, mass, temperature)
        if hasattr(prop, 'compatible_units') and prop.compatible_units:
            self.logger.debug(f"{prop.name}: Measurement property -> unit_value widget")
            return 'unit_value'

        # Priority 2: Object properties (references to ontology individuals)
        if prop.data_type == "object":
            # Check if it has a range_class (specific object type like Material, SpecimenRole)
            if hasattr(prop, 'range_class') and prop.range_class:
                self.logger.debug(f"{prop.name}: Object property (range: {prop.range_class}) -> object_combo widget")
                return 'object_combo'
            else:
                self.logger.debug(f"{prop.name}: Object property (no range) -> combo widget")
                return 'combo'

        # Priority 3: Use suggested widget type from metadata
        if prop.suggested_widget_type:
            self.logger.debug(f"{prop.name}: Using suggested type -> {prop.suggested_widget_type}")
            return prop.suggested_widget_type

        # Priority 4: Fallback mapping based on data_type
        type_mapping = {
            'string': 'line_edit',
            'integer': 'spinbox',
            'double': 'double_spinbox',
            'boolean': 'checkbox',
            'date': 'date'
        }

        fallback_type = type_mapping.get(prop.data_type, 'line_edit')
        self.logger.debug(f"{prop.name}: Fallback based on data_type={prop.data_type} -> {fallback_type}")
        return fallback_type
    
    def create_widgets_for_properties(self, properties: List[PropertyMetadata], 
                                     parent: Optional[QWidget] = None) -> Dict[str, QWidget]:
        """
        Create widgets for a list of properties.
        
        Args:
            properties: List of property metadata
            
        Returns:
            Dictionary mapping property URIs to widgets
        """
        widgets = {}
    
        for prop in properties:
            try:
                widget = self.create_widget(prop)
                
                # CRITICAL FIX: Set parent immediately to prevent garbage collection
                if parent:
                    widget.setParent(parent)
                
                widgets[prop.uri] = widget
                self.logger.debug(f"Created widget for {prop.name} (parent: {widget.parent() is not None})")
                
            except Exception as e:
                self.logger.error(f"Failed to create widget for {prop.name}: {e}")
                # Create error widget with parent
                error_widget = self._create_error_widget(f"Error: {prop.name}")
                if parent:
                    error_widget.setParent(parent)
                widgets[prop.uri] = error_widget
        
        self.logger.info(f"Created {len(widgets)} widgets (all with proper parents)")
        return widgets
    
    # ============================================================================
    # WIDGET CREATION METHODS
    # ============================================================================
    
    def _create_line_edit_widget(self, prop: PropertyMetadata) -> QLineEdit:
        """Create a line edit widget."""
        widget = QLineEdit()
        
        if prop.description:
            widget.setToolTip(prop.description)
        
        if hasattr(prop, 'max_length') and prop.max_length:
            widget.setMaxLength(prop.max_length)
        
        if hasattr(prop, 'placeholder') and prop.placeholder:
            widget.setPlaceholderText(prop.placeholder)
        
        return widget
    
    def _create_text_area_widget(self, prop: PropertyMetadata) -> QTextEdit:
        """Create a text area widget."""
        widget = QTextEdit()
        widget.setMaximumHeight(100)
        
        if prop.description:
            widget.setToolTip(prop.description)
        
        if hasattr(prop, 'placeholder') and prop.placeholder:
            widget.setPlaceholderText(prop.placeholder)
        
        return widget
    
    def _create_combo_widget(self, prop: PropertyMetadata) -> QComboBox:
        """Create a combo box widget with valid values."""
        widget = QComboBox()
        widget.setEditable(False)
        
        if prop.description:
            widget.setToolTip(prop.description)
        
        # Add valid values
        if hasattr(prop, 'valid_values') and prop.valid_values:
            for value in prop.valid_values:
                widget.addItem(value, value)
        
        return widget
    
    def _create_object_combo_widget(self, prop: PropertyMetadata) -> QComboBox:
        """Create a combo box for ontology objects."""
        widget = QComboBox()
        widget.setEditable(False)

        if prop.description:
            widget.setToolTip(prop.description)

        # Add empty option for non-required fields
        if not prop.is_required:
            widget.addItem("(Select...)", "")

        try:
            # Query for objects of this type from ontology
            if hasattr(prop, 'range_class') and prop.range_class:
                self.logger.info(f"Creating object combo for {prop.name}, range_class={prop.range_class}")

                # Get all individuals - should return URIs with names
                result = self.ontology_manager.domain_queries.get_instances_of_class(
                    prop.range_class,
                    include_subclasses=True
                )

                self.logger.info(f"Retrieved {len(result)} instances for {prop.range_class}")

                for instance in result:
                    # instance is a dict with 'uri' and 'name'
                    uri = instance['uri']
                    display_name = instance['name']

                    # Store URI in data, display name in text
                    widget.addItem(display_name, uri)
                    self.logger.info(f"  Added: '{display_name}' -> '{uri}'")

                self.logger.info(f"Loaded {widget.count() - 1} items for {prop.name}")

        except Exception as e:
            self.logger.error(f"Could not load objects for {prop.name} ({prop.range_class}): {e}", exc_info=True)
            widget.addItem("(Error loading data)", "")

        return widget
    
    def _create_spinbox_widget(self, prop: PropertyMetadata) -> QSpinBox:
        """Create an integer spin box widget."""
        widget = QSpinBox()
        widget.setMinimum(-2147483648)
        widget.setMaximum(2147483647)
        
        if prop.description:
            widget.setToolTip(prop.description)
        
        if hasattr(prop, 'min_value') and prop.min_value is not None:
            widget.setMinimum(int(prop.min_value))
        
        if hasattr(prop, 'max_value') and prop.max_value is not None:
            widget.setMaximum(int(prop.max_value))
        
        if hasattr(prop, 'default_value') and prop.default_value is not None:
            widget.setValue(int(prop.default_value))
        
        return widget
    
    def _create_double_spinbox_widget(self, prop: PropertyMetadata) -> QDoubleSpinBox:
        """Create a double spin box widget."""
        widget = QDoubleSpinBox()
        widget.setMinimum(-1e10)
        widget.setMaximum(1e10)
        widget.setDecimals(6)
        widget.setSingleStep(0.1)
        
        if prop.description:
            widget.setToolTip(prop.description)
        
        if hasattr(prop, 'min_value') and prop.min_value is not None:
            widget.setMinimum(float(prop.min_value))
        
        if hasattr(prop, 'max_value') and prop.max_value is not None:
            widget.setMaximum(float(prop.max_value))
        
        if hasattr(prop, 'default_value') and prop.default_value is not None:
            widget.setValue(float(prop.default_value))
        
        return widget
    
    def _create_checkbox_widget(self, prop: PropertyMetadata) -> QCheckBox:
        """Create a checkbox widget."""
        widget = QCheckBox()
        
        if prop.description:
            widget.setToolTip(prop.description)
        
        if hasattr(prop, 'default_value') and prop.default_value is not None:
            widget.setChecked(bool(prop.default_value))
        
        return widget
    
    def _create_date_widget(self, prop: PropertyMetadata) -> QDateEdit:
        """Create a date edit widget."""
        widget = QDateEdit()
        widget.setCalendarPopup(True)
        widget.setDate(QDate.currentDate())
        
        if prop.description:
            widget.setToolTip(prop.description)
        
        return widget
    
    def _create_unit_value_widget(self, prop: PropertyMetadata) -> QWidget:
        """Create a unit-value widget for measurement properties."""
        try:
            # Import here to avoid circular imports
            from ..widgets.base.unit_value_widget import UnitValueWidget
            
            # Get compatible units from the property
            compatible_units = getattr(prop, 'compatible_units', [])
            default_unit = getattr(prop, 'default_unit', None)
            
            if not compatible_units:
                self.logger.warning(f"No compatible units for {prop.name}, falling back to double spinbox")
                return self._create_double_spinbox_widget(prop)
            
            # Create unit value widget
            widget = UnitValueWidget(
                default_unit=default_unit,
                available_units=compatible_units,
                property_uri=prop.uri
            )
            
            # Set validation constraints if available
            if hasattr(prop, 'min_value') and prop.min_value is not None:
                widget.setMinimum(prop.min_value)
            if hasattr(prop, 'max_value') and prop.max_value is not None:
                widget.setMaximum(prop.max_value)
            
            return widget
            
        except Exception as e:
            self.logger.error(f"Failed to create unit value widget for {prop.name}: {e}")
            return self._create_double_spinbox_widget(prop)
    
    def _create_error_widget(self, error_message: str) -> QLabel:
        """Create an error display widget."""
        widget = QLabel(error_message)
        widget.setStyleSheet("color: red; font-style: italic;")
        return widget
    
    # ============================================================================
    # UTILITY METHODS
    # ============================================================================
    
    def _apply_common_properties(self, widget: QWidget, prop: PropertyMetadata):
        """Apply common properties to all widgets."""
        # Set minimum width for consistency
        widget.setMinimumWidth(120)
        
        # Mark required fields visually
        if prop.is_required:
            current_style = widget.styleSheet()
            widget.setStyleSheet(f"{current_style}; border-left: 3px solid orange;")
        
    def _get_objects_for_class(self, class_uri: str) -> List[Dict[str, Any]]:
        """Get instances of a class from the ontology."""
        try:
            self.logger.debug(f"Getting objects for class: {class_uri}")
            
            # Use domain_queries for ALL classes (including Material)
            if hasattr(self.ontology_manager, 'domain_queries'):
                instances = self.ontology_manager.domain_queries.get_instances_of_class(
                    class_uri, 
                    include_subclasses=True
                )
                self.logger.debug(f"  Received {len(instances)} instances")
                
                for i, inst in enumerate(instances[:3]):
                    self.logger.debug(f"    Instance {i}: {inst}")
                
                return instances
            
            # FALLBACK: Use legacy get_all_individuals (returns list of URI strings)
            elif hasattr(self.ontology_manager, 'get_all_individuals'):
                self.logger.debug("  Using legacy get_all_individuals")
                uri_list = self.ontology_manager.get_all_individuals(class_uri, include_subclasses=True)
                
                # Convert URI strings to dict format
                instances = []
                for uri in uri_list:
                    display_name = uri.split('#')[-1].replace('_', ' ')
                    instances.append({
                        'uri': uri,
                        'name': display_name,
                        'label': ''
                    })
                
                self.logger.debug(f"  Converted {len(instances)} URIs to instances")
                return instances
            else:
                self.logger.error("OntologyManager has no domain_queries or get_all_individuals")
                return []
                
        except Exception as e:
            self.logger.error(f"Failed to get objects for class {class_uri}: {e}", exc_info=True)
            return []
    
    def _extract_local_name(self, uri: str) -> str:
        """Extract local name from URI."""
        if not uri:
            return "Unknown"
        return uri.split('#')[-1].split('/')[-1].replace('_', ' ')