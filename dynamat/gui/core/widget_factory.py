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
        
        Args:
            property_metadata: Property metadata from ontology
            
        Returns:
            Configured widget for the property
        """
        try:
            widget_type = property_metadata.suggested_widget_type
            self.logger.debug(f"Creating {widget_type} widget for {property_metadata.name}")
            
            # Check if property has units (measurement property)
            if hasattr(property_metadata, 'compatible_units') and property_metadata.compatible_units:
                widget_type = 'unit_value'
            
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
    
    def create_widgets_for_properties(self, properties: List[PropertyMetadata]) -> Dict[str, QWidget]:
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
                widgets[prop.uri] = widget
                self.logger.debug(f"Created widget for {prop.name}")
            except Exception as e:
                self.logger.error(f"Failed to create widget for {prop.name}: {e}")
                widgets[prop.uri] = self._create_error_widget(f"Error: {prop.name}")
        
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
        
        try:
            # Query for objects of this type from ontology
            if hasattr(prop, 'range_class') and prop.range_class:
                objects = self._get_objects_for_class(prop.range_class)
                
                for obj in objects:
                    display_name = obj.get('name', obj.get('uri', 'Unknown'))
                    widget.addItem(display_name, obj.get('uri'))
        
        except Exception as e:
            self.logger.warning(f"Could not load objects for {prop.name}: {e}")
            widget.addItem("(No data available)", "")
        
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
            # Use ontology manager to query for instances
            # This is a placeholder - implement based on your ontology structure
            if hasattr(self.ontology_manager, 'domain_queries'):
                return self.ontology_manager.domain_queries.get_instances_of_class(class_uri)
            else:
                return []
        except Exception as e:
            self.logger.error(f"Failed to get objects for class {class_uri}: {e}")
            return []