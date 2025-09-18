"""
DynaMat Platform - Widget Factory
Centralized widget creation from ontology property metadata
"""

import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QTextEdit, QComboBox, 
    QSpinBox, QDoubleSpinBox, QDateEdit, QCheckBox, 
    QHBoxLayout, QFrame
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont

from ...ontology import OntologyManager, PropertyMetadata, UnitInfo

logger = logging.getLogger(__name__)


class WidgetFactory:
    """
    Centralized factory for creating GUI widgets from ontology property metadata.
    
    Handles all widget creation logic including:
    - Basic input widgets (text, numeric, date)
    - Complex widgets (combo boxes, unit-value widgets)
    - Widget configuration and validation setup
    """
    
    def __init__(self, ontology_manager: OntologyManager):
        """
        Initialize widget factory.
        
        Args:
            ontology_manager: Ontology manager for data queries
        """
        self.ontology_manager = ontology_manager
        self.logger = logging.getLogger(__name__)
        
        # Widget type mapping
        self.widget_creators = {
            'line_edit': self._create_line_edit,
            'text_area': self._create_text_area,
            'combo': self._create_combo_box,
            'object_combo': self._create_object_combo_box,
            'checkbox': self._create_checkbox,
            'spinbox': self._create_spinbox,
            'double_spinbox': self._create_double_spinbox,
            'date': self._create_date_edit,
            'unit_value': self._create_unit_value_widget
        }
    
    def create_widget(self, property_metadata: PropertyMetadata) -> QWidget:
        """
        Create appropriate widget for a property.
        
        Args:
            property_metadata: Property metadata from ontology
            
        Returns:
            QWidget appropriate for the property type
        """
        try:
            self.logger.debug(f"Creating widget for property: {property_metadata.uri}")
            
            # Determine widget type
            widget_type = self._determine_widget_type(property_metadata)
            self.logger.debug(f"Determined widget type: {widget_type}")
            
            # Create widget using appropriate creator
            if widget_type in self.widget_creators:
                widget = self.widget_creators[widget_type](property_metadata)
            else:
                self.logger.warning(f"Unknown widget type: {widget_type}, using line edit")
                widget = self._create_line_edit(property_metadata)
            
            # Apply common configuration
            self._configure_widget(widget, property_metadata)
            
            return widget
            
        except Exception as e:
            self.logger.error(f"Failed to create widget for {property_metadata.uri}: {e}")
            # Return fallback widget
            fallback = QLabel(f"Error: {str(e)}")
            fallback.setStyleSheet("color: red; font-style: italic;")
            return fallback
    
    def create_widgets_for_properties(self, properties: List[PropertyMetadata]) -> Dict[str, QWidget]:
        """
        Create widgets for a list of properties.
        
        Args:
            properties: List of property metadata
            
        Returns:
            Dictionary mapping property URI to widget
        """
        widgets = {}
        
        for prop in properties:
            try:
                widget = self.create_widget(prop)
                widgets[prop.uri] = widget
                self.logger.debug(f"Created widget for {prop.uri}")
            except Exception as e:
                self.logger.error(f"Failed to create widget for {prop.uri}: {e}")
                # Add error placeholder
                error_widget = QLabel(f"Error creating widget: {e}")
                error_widget.setStyleSheet("color: red; font-style: italic;")
                widgets[prop.uri] = error_widget
        
        self.logger.info(f"Created {len(widgets)} widgets from {len(properties)} properties")
        return widgets
    
    # ============================================================================
    # WIDGET TYPE DETERMINATION
    # ============================================================================
    
    def _determine_widget_type(self, prop: PropertyMetadata) -> str:
        """Determine the best widget type for a property."""
        
        # Check if property has explicit widget type
        if hasattr(prop, 'widget_type') and prop.widget_type:
            return prop.widget_type
        
        # Check for unit-based properties (measurements)
        if self._has_units(prop):
            return 'unit_value'
        
        # Check for valid values (enumeration)
        if hasattr(prop, 'valid_values') and prop.valid_values:
            return 'combo'
        
        # Check for object properties
        if hasattr(prop, 'data_type') and prop.data_type == 'object':
            return 'object_combo'
        
        # Check data type
        if hasattr(prop, 'data_type'):
            if prop.data_type == 'boolean':
                return 'checkbox'
            elif prop.data_type == 'date':
                return 'date'
            elif prop.data_type == 'integer':
                return 'spinbox'
            elif prop.data_type in ['double', 'float']:
                return 'double_spinbox'
        
        # Check description for hints
        if hasattr(prop, 'description') and prop.description:
            desc_lower = prop.description.lower()
            if any(word in desc_lower for word in ['note', 'comment', 'description', 'remarks']):
                return 'text_area'
        
        # Default to line edit
        return 'line_edit'
    
    def _has_units(self, prop: PropertyMetadata) -> bool:
        """Check if property has unit information."""
        return (hasattr(prop, 'compatible_units') and 
                prop.compatible_units and 
                len(prop.compatible_units) > 0)
    
    # ============================================================================
    # WIDGET CREATORS
    # ============================================================================
    
    def _create_line_edit(self, prop: PropertyMetadata) -> QLineEdit:
        """Create a line edit widget."""
        widget = QLineEdit()
        
        # Set placeholder text
        if hasattr(prop, 'description') and prop.description:
            widget.setPlaceholderText(prop.description[:50] + "..." if len(prop.description) > 50 else prop.description)
        
        return widget
    
    def _create_text_area(self, prop: PropertyMetadata) -> QTextEdit:
        """Create a text area widget."""
        widget = QTextEdit()
        widget.setMaximumHeight(100)  # Reasonable default height
        
        if hasattr(prop, 'description') and prop.description:
            widget.setPlaceholderText(prop.description)
        
        return widget
    
    def _create_combo_box(self, prop: PropertyMetadata) -> QComboBox:
        """Create a combo box for enumerated values."""
        widget = QComboBox()
        widget.setEditable(True)  # Allow custom values
        
        # Add empty option
        widget.addItem("", "")
        
        # Add valid values if available
        if hasattr(prop, 'valid_values') and prop.valid_values:
            for value in prop.valid_values:
                widget.addItem(str(value), str(value))
        
        return widget
    
    def _create_object_combo_box(self, prop: PropertyMetadata) -> QComboBox:
        """Create a combo box for object properties."""
        widget = QComboBox()
        
        # Add empty option
        widget.addItem("Select...", "")
        
        try:
            # Query ontology for available objects of this type
            if hasattr(prop, 'range_class') and prop.range_class:
                objects = self._get_available_objects(prop.range_class)
                for obj in objects:
                    display_name = obj.get('label', obj.get('name', obj['uri']))
                    widget.addItem(display_name, obj['uri'])
        except Exception as e:
            self.logger.warning(f"Could not load objects for {prop.uri}: {e}")
            widget.addItem("Error loading options", "")
        
        return widget
    
    def _create_checkbox(self, prop: PropertyMetadata) -> QCheckBox:
        """Create a checkbox widget."""
        widget = QCheckBox()
        
        # Set description as tooltip if available
        if hasattr(prop, 'description') and prop.description:
            widget.setToolTip(prop.description)
        
        return widget
    
    def _create_spinbox(self, prop: PropertyMetadata) -> QSpinBox:
        """Create an integer spinbox."""
        widget = QSpinBox()
        
        # Set reasonable defaults
        widget.setMinimum(-1000000)
        widget.setMaximum(1000000)
        
        # Apply constraints if available
        if hasattr(prop, 'min_value') and prop.min_value is not None:
            widget.setMinimum(int(prop.min_value))
        if hasattr(prop, 'max_value') and prop.max_value is not None:
            widget.setMaximum(int(prop.max_value))
        
        return widget
    
    def _create_double_spinbox(self, prop: PropertyMetadata) -> QDoubleSpinBox:
        """Create a double spinbox."""
        widget = QDoubleSpinBox()
        
        # Set reasonable defaults
        widget.setMinimum(-1e10)
        widget.setMaximum(1e10)
        widget.setDecimals(6)
        widget.setSingleStep(0.1)
        
        # Apply constraints if available
        if hasattr(prop, 'min_value') and prop.min_value is not None:
            widget.setMinimum(float(prop.min_value))
        if hasattr(prop, 'max_value') and prop.max_value is not None:
            widget.setMaximum(float(prop.max_value))
        
        return widget
    
    def _create_date_edit(self, prop: PropertyMetadata) -> QDateEdit:
        """Create a date edit widget."""
        widget = QDateEdit()
        widget.setCalendarPopup(True)
        widget.setDate(QDate.currentDate())
        
        return widget
    
    def _create_unit_value_widget(self, prop: PropertyMetadata) -> QWidget:
        """Create a unit-value widget for measurement properties."""
        try:
            # Import here to avoid circular imports
            from ..widgets.base.unit_value_widget import UnitValueWidget
            
            # Get unit information
            compatible_units = getattr(prop, 'compatible_units', [])
            default_unit = getattr(prop, 'default_unit', None)
            
            if not compatible_units:
                self.logger.warning(f"No compatible units for {prop.uri}, falling back to double spinbox")
                return self._create_double_spinbox(prop)
            
            # Create unit value widget
            widget = UnitValueWidget(
                default_unit=default_unit,
                available_units=compatible_units,
                property_uri=prop.uri
            )
            
            # Apply constraints
            if hasattr(prop, 'min_value') and prop.min_value is not None:
                widget.setMinimum(prop.min_value)
            if hasattr(prop, 'max_value') and prop.max_value is not None:
                widget.setMaximum(prop.max_value)
            
            return widget
            
        except ImportError as e:
            self.logger.error(f"Could not import UnitValueWidget: {e}")
            return self._create_double_spinbox(prop)
        except Exception as e:
            self.logger.error(f"Error creating unit value widget: {e}")
            return self._create_double_spinbox(prop)
    
    # ============================================================================
    # WIDGET CONFIGURATION
    # ============================================================================
    
    def _configure_widget(self, widget: QWidget, prop: PropertyMetadata):
        """Apply common configuration to widgets."""
        
        # Set object name for easy identification
        widget.setObjectName(f"widget_{prop.name}")
        
        # Set tooltip from description
        if hasattr(prop, 'description') and prop.description:
            widget.setToolTip(prop.description)
        
        # Set required styling
        if hasattr(prop, 'is_required') and prop.is_required:
            widget.setProperty("required", True)
            # Apply required styling via CSS
            current_style = widget.styleSheet()
            required_style = "border-left: 3px solid orange;"
            widget.setStyleSheet(f"{current_style} {required_style}")
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    def _get_available_objects(self, class_uri: str) -> List[Dict[str, Any]]:
        """Get available objects of a specific class."""
        try:
            # Use domain queries to get instances
            return self.ontology_manager.domain_queries.get_instances_of_class(class_uri)
        except Exception as e:
            self.logger.error(f"Error getting objects for class {class_uri}: {e}")
            return []