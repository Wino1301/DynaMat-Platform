"""Widget factory for ontology-driven form creation.

This module provides centralized widget creation from ontology metadata.
It maps ontology property types and annotations to appropriate PyQt6 widgets.

Classes
-------
WidgetFactory
    Factory for creating form widgets from property metadata.

Widget Type Mapping
-------------------
The factory determines widget types based on property metadata:

1. Read-only string properties -> QLabel
2. Measurement properties (has compatible_units) -> UnitValueWidget
3. Object properties (data_type=object) -> QComboBox or QListWidget
4. Boolean properties -> QCheckBox
5. Integer properties -> QSpinBox
6. Double properties -> QDoubleSpinBox
7. Date properties -> QDateEdit
8. String properties -> QLineEdit (default)

Example
-------
::

    from dynamat.ontology import OntologyManager
    from dynamat.gui.core import WidgetFactory

    ontology = OntologyManager()
    factory = WidgetFactory(ontology)

    # Create single widget
    widget = factory.create_widget(property_metadata)

    # Create widgets for all properties
    widgets = factory.create_widgets_for_properties(properties)
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QTextEdit, QComboBox,
    QSpinBox, QDoubleSpinBox, QDateEdit, QCheckBox,
    QHBoxLayout, QFrame, QListWidget, QListWidgetItem, QAbstractItemView,
    QPushButton, QCalendarWidget, QDialog, QVBoxLayout, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont

from ...ontology import PropertyMetadata, OntologyManager

logger = logging.getLogger(__name__)


class WidgetFactory:
    """Centralized factory for creating form widgets from ontology metadata.

    Handles all widget creation logic, including specialized widgets like
    unit-value combinations and ontology-based combo boxes. The factory
    determines the appropriate widget type based on property metadata
    including data type, compatible units, and suggested widget hints.

    Parameters
    ----------
    ontology_manager : OntologyManager
        The ontology manager instance for querying individuals.

    Attributes
    ----------
    ontology_manager : OntologyManager
        Reference to the ontology manager.
    widget_creators : dict
        Mapping of widget type names to creator functions.

    Example
    -------
    ::

        factory = WidgetFactory(ontology_manager)
        widget = factory.create_widget(property_metadata)

        # Get creation statistics
        stats = factory.get_statistics()
    """

    def __init__(self, ontology_manager: OntologyManager):
        self.ontology_manager = ontology_manager

        # Widget type mapping
        self.widget_creators = {
            'label': self._create_label_widget,
            'line_edit': self._create_line_edit_widget,
            'text_area': self._create_text_area_widget,
            'combo': self._create_combo_widget,
            'object_combo': self._create_object_combo_widget,
            'object_multi_select': self._create_multi_select_object_widget,
            'spinbox': self._create_spinbox_widget,
            'double_spinbox': self._create_double_spinbox_widget,
            'checkbox': self._create_checkbox_widget,
            'date': self._create_date_widget,
            'unit_value': self._create_unit_value_widget
        }

        # Statistics tracking (always-on)
        self._widget_creation_counts = {}  # widget_type -> count
        self._widget_type_determinations = {}  # decision_path -> count
        self._creation_errors = []  # List of (property_name, error_message)
        self._combo_population_stats = {
            'success': 0,
            'failed': 0,
            'empty': 0
        }
    
    def create_widget(self, property_metadata: PropertyMetadata) -> QWidget:
        """
        Create appropriate widget for a property based on its metadata.
        """
        try:
            # Determine widget type using systematic approach
            widget_type = self._determine_widget_type(property_metadata)

            logger.debug(
                f"Creating widget for {property_metadata.name}: "
                f"type={widget_type}, data_type={property_metadata.data_type}, "
                f"is_read_only={property_metadata.is_read_only}"
            )

            # Get widget creator function
            creator_func = self.widget_creators.get(widget_type, self._create_line_edit_widget)

            # Create widget
            widget = creator_func(property_metadata)

            # Apply common styling and constraints
            self._apply_common_properties(widget, property_metadata)

            # Track successful creation
            self._widget_creation_counts[widget_type] = self._widget_creation_counts.get(widget_type, 0) + 1

            return widget

        except Exception as e:
            logger.error(f"Failed to create widget for {property_metadata.name}: {e}")
            # Track error
            self._creation_errors.append((property_metadata.name, str(e)))
            return self._create_error_widget(f"Error: {str(e)}")

    def _determine_widget_type(self, prop: PropertyMetadata) -> str:
        """
        Determine the appropriate widget type for a property.

        Priority order:
        1. Read-only string properties -> label
        2. Measurement properties (has compatible_units) -> unit_value
        3. Object properties (data_type=object, references to individuals) -> object_combo
        4. Suggested widget type from metadata
        5. Fallback based on data_type

        Args:
            prop: Property metadata

        Returns:
            Widget type string
        """
        # Priority 1: Read-only string properties should use labels
        if prop.is_read_only and prop.data_type == 'string':
            logger.debug(f"{prop.name}: Read-only string property -> label widget")
            decision_path = "read_only_string->label"
            self._widget_type_determinations[decision_path] = self._widget_type_determinations.get(decision_path, 0) + 1
            return 'label'

        # Priority 2: Measurement properties with units (e.g., length, mass, temperature)
        if hasattr(prop, 'compatible_units') and prop.compatible_units:
            logger.debug(f"{prop.name}: Measurement property -> unit_value widget")
            decision_path = "has_compatible_units->unit_value"
            self._widget_type_determinations[decision_path] = self._widget_type_determinations.get(decision_path, 0) + 1
            return 'unit_value'

        # Priority 3: Object properties (references to ontology individuals)
        if prop.data_type == "object":
            # Check if it has a range_class (specific object type like Material, SpecimenRole)
            if hasattr(prop, 'range_class') and prop.range_class:
                # Check if property is functional (single-select) or not (multi-select)
                if hasattr(prop, 'is_functional') and not prop.is_functional:
                    logger.debug(f"{prop.name}: Non-functional object property (range: {prop.range_class}) -> object_multi_select widget")
                    decision_path = "object_property_non_functional->object_multi_select"
                    self._widget_type_determinations[decision_path] = self._widget_type_determinations.get(decision_path, 0) + 1
                    return 'object_multi_select'
                else:
                    logger.debug(f"{prop.name}: Functional object property (range: {prop.range_class}) -> object_combo widget")
                    decision_path = "object_property_functional->object_combo"
                    self._widget_type_determinations[decision_path] = self._widget_type_determinations.get(decision_path, 0) + 1
                    return 'object_combo'
            else:
                logger.debug(f"{prop.name}: Object property (no range) -> combo widget")
                decision_path = "object_no_range->combo"
                self._widget_type_determinations[decision_path] = self._widget_type_determinations.get(decision_path, 0) + 1
                return 'combo'

        # Priority 4: Use suggested widget type from metadata
        if prop.suggested_widget_type:
            logger.debug(f"{prop.name}: Using suggested type -> {prop.suggested_widget_type}")
            decision_path = f"suggested->{prop.suggested_widget_type}"
            self._widget_type_determinations[decision_path] = self._widget_type_determinations.get(decision_path, 0) + 1
            return prop.suggested_widget_type

        # Priority 5: Fallback mapping based on data_type
        type_mapping = {
            'string': 'line_edit',
            'integer': 'spinbox',
            'double': 'double_spinbox',
            'boolean': 'checkbox',
            'date': 'date'
        }

        fallback_type = type_mapping.get(prop.data_type, 'line_edit')
        logger.debug(f"{prop.name}: Fallback based on data_type={prop.data_type} -> {fallback_type}")
        decision_path = f"fallback_{prop.data_type}->{fallback_type}"
        self._widget_type_determinations[decision_path] = self._widget_type_determinations.get(decision_path, 0) + 1
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
                logger.debug(f"Created widget for {prop.name} (parent: {widget.parent() is not None})")
                
            except Exception as e:
                logger.error(f"Failed to create widget for {prop.name}: {e}")
                # Create error widget with parent
                error_widget = self._create_error_widget(f"Error: {prop.name}")
                if parent:
                    error_widget.setParent(parent)
                widgets[prop.uri] = error_widget
        
        logger.info(f"Created {len(widgets)} widgets (all with proper parents)")
        return widgets
    
    # ============================================================================
    # WIDGET CREATION METHODS
    # ============================================================================
    
    def _create_label_widget(self, prop: PropertyMetadata) -> QLabel:
        """Create a label widget for read-only display."""
        widget = QLabel()
        widget.setText("")  # Empty initially, will be filled by dependency manager

        # Style to match QLineEdit appearance
        widget.setFrameShape(QFrame.Shape.StyledPanel)
        widget.setFrameShadow(QFrame.Shadow.Sunken)
        widget.setMinimumHeight(24)  # Match typical line edit height

        if prop.description:
            widget.setToolTip(prop.description)

        return widget

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
                logger.info(f"Creating object combo for {prop.name}, range_class={prop.range_class}")

                # Get all individuals - should return URIs with names
                result = self.ontology_manager.domain_queries.get_instances_of_class(
                    prop.range_class,
                    include_subclasses=True
                )

                logger.info(f"Retrieved {len(result)} instances for {prop.range_class}")

                for instance in result:
                    # instance is a dict with 'uri' and 'name'
                    uri = instance['uri']
                    display_name = instance['name']

                    # Store URI in data, display name in text
                    widget.addItem(display_name, uri)
                    logger.info(f"  Added: '{display_name}' -> '{uri}'")

                logger.info(f"Loaded {widget.count() - 1} items for {prop.name}")

                # Track combo population success
                if len(result) > 0:
                    self._combo_population_stats['success'] += 1
                else:
                    self._combo_population_stats['empty'] += 1

        except Exception as e:
            logger.error(f"Could not load objects for {prop.name} ({prop.range_class}): {e}", exc_info=True)
            widget.addItem("(Error loading data)", "")
            # Track combo population failure
            self._combo_population_stats['failed'] += 1

        return widget

    def _create_multi_select_object_widget(self, prop: PropertyMetadata) -> QListWidget:
        """Create a multi-select list widget for non-functional object properties."""
        widget = QListWidget()
        widget.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        widget.setMaximumHeight(120)  # Limit height to show ~5 items

        if prop.description:
            widget.setToolTip(prop.description)

        try:
            # Query for objects of this type from ontology
            if hasattr(prop, 'range_class') and prop.range_class:
                logger.info(f"Creating multi-select list for {prop.name}, range_class={prop.range_class}")

                # Get all individuals - should return URIs with names
                result = self.ontology_manager.domain_queries.get_instances_of_class(
                    prop.range_class,
                    include_subclasses=True
                )

                logger.info(f"Retrieved {len(result)} instances for {prop.range_class}")

                for instance in result:
                    # instance is a dict with 'uri' and 'name'
                    uri = instance['uri']
                    display_name = instance['name']

                    # Create list item with display name and store URI in data
                    item = QListWidgetItem(display_name)
                    item.setData(Qt.ItemDataRole.UserRole, uri)
                    widget.addItem(item)
                    logger.info(f"  Added: '{display_name}' -> '{uri}'")

                logger.info(f"Loaded {widget.count()} items for {prop.name}")

                # Track combo population success
                if len(result) > 0:
                    self._combo_population_stats['success'] += 1
                else:
                    self._combo_population_stats['empty'] += 1

        except Exception as e:
            logger.error(f"Could not load objects for {prop.name} ({prop.range_class}): {e}", exc_info=True)
            error_item = QListWidgetItem("(Error loading data)")
            error_item.setData(Qt.ItemDataRole.UserRole, "")
            widget.addItem(error_item)
            # Track combo population failure
            self._combo_population_stats['failed'] += 1

        return widget

    def _create_spinbox_widget(self, prop: PropertyMetadata) -> QSpinBox:
        """Create an integer spin box widget."""
        widget = QSpinBox()
        widget.setMinimum(0)  # Default to 0 minimum (measurements are non-negative)
        widget.setMaximum(2147483647)
        widget.setValue(0)  # Default value

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
        widget.setMinimum(0.0)  # Default to 0 minimum (measurements are non-negative)
        widget.setMaximum(1e10)
        widget.setDecimals(6)
        widget.setSingleStep(0.1)
        widget.setValue(0.0)  # Default value

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
        widget.setDate(QDate.currentDate())  # Default to today

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
                logger.warning(f"No compatible units for {prop.name}, falling back to double spinbox")
                return self._create_double_spinbox_widget(prop)
            
            # Create unit value widget
            widget = UnitValueWidget(
                default_unit=default_unit,
                available_units=compatible_units,
                property_uri=prop.uri,
                reference_unit_uri=default_unit  # Pass dyn:hasUnit as reference for conversion
            )

            # Set tooltip if description available
            if prop.description:
                widget.setToolTip(prop.description)

            # Set validation constraints if available
            if hasattr(prop, 'min_value') and prop.min_value is not None:
                widget.setMinimum(prop.min_value)
            if hasattr(prop, 'max_value') and prop.max_value is not None:
                widget.setMaximum(prop.max_value)

            return widget
            
        except Exception as e:
            logger.error(f"Failed to create unit value widget for {prop.name}: {e}")
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

        # Apply read-only mode if specified
        if prop.is_read_only:
            logger.info(f"Applying read-only mode to {prop.name} (widget type: {type(widget).__name__})")

            # Different widgets have different methods for read-only
            if isinstance(widget, QLabel):
                # QLabel is naturally read-only, no action needed
                logger.info(f"QLabel {prop.name} is naturally read-only")
            elif hasattr(widget, 'setReadOnly'):
                # Best option: proper read-only mode (allows programmatic updates)
                widget.setReadOnly(True)
                logger.info(f"Set {prop.name} to read-only using setReadOnly()")
            elif isinstance(widget, QComboBox):
                # QComboBox doesn't have setReadOnly, but we can make it non-editable
                # and prevent user interaction while still allowing programmatic updates
                widget.setEditable(False)
                widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                logger.info(f"Set QComboBox {prop.name} to non-interactive mode")
            else:
                logger.warning(f"Widget {type(widget).__name__} doesn't support read-only mode directly")
        
    def _get_objects_for_class(self, class_uri: str) -> List[Dict[str, Any]]:
        """Get instances of a class from the ontology."""
        try:
            logger.debug(f"Getting objects for class: {class_uri}")
            
            # Use domain_queries for ALL classes (including Material)
            if hasattr(self.ontology_manager, 'domain_queries'):
                instances = self.ontology_manager.domain_queries.get_instances_of_class(
                    class_uri, 
                    include_subclasses=True
                )
                logger.debug(f"  Received {len(instances)} instances")
                
                for i, inst in enumerate(instances[:3]):
                    logger.debug(f"    Instance {i}: {inst}")
                
                return instances
            
            # FALLBACK: Use legacy get_all_individuals (returns list of URI strings)
            elif hasattr(self.ontology_manager, 'get_all_individuals'):
                logger.debug("  Using legacy get_all_individuals")
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
                
                logger.debug(f"  Converted {len(instances)} URIs to instances")
                return instances
            else:
                logger.error("OntologyManager has no domain_queries or get_all_individuals")
                return []
                
        except Exception as e:
            logger.error(f"Failed to get objects for class {class_uri}: {e}", exc_info=True)
            return []
    
    def _extract_local_name(self, uri: str) -> str:
        """Extract local name from URI."""
        if not uri:
            return "Unknown"
        return uri.split('#')[-1].split('/')[-1].replace('_', ' ')

    # ============================================================================
    # STATISTICS METHODS
    # ============================================================================

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive widget factory statistics for testing and debugging.

        Returns:
            Dictionary with statistics categories:
            - configuration: Component setup state
            - execution: Widget creation statistics
            - health: Component health indicators
            - errors: Error tracking
        """
        return {
            'configuration': {
                'available_widget_types': list(self.widget_creators.keys()),
                'ontology_manager_connected': self.ontology_manager is not None
            },
            'execution': {
                'widgets_created': dict(self._widget_creation_counts),
                'total_widgets': sum(self._widget_creation_counts.values()),
                'widget_type_determinations': dict(self._widget_type_determinations),
                'combo_population': self._combo_population_stats.copy()
            },
            'health': {
                'creation_errors': len(self._creation_errors),
                'combo_success_rate': (
                    self._combo_population_stats['success'] /
                    (self._combo_population_stats['success'] +
                     self._combo_population_stats['failed'] +
                     self._combo_population_stats['empty'])
                    if (self._combo_population_stats['success'] +
                        self._combo_population_stats['failed'] +
                        self._combo_population_stats['empty']) > 0
                    else 0.0
                )
            },
            'errors': {
                'total_errors': len(self._creation_errors),
                'recent_errors': self._creation_errors[-5:] if self._creation_errors else []
            }
        }

    def get_widget_type_coverage(self) -> Dict[str, int]:
        """
        Get coverage of widget types actually created.

        Returns:
            Dictionary mapping widget types to creation counts
        """
        return dict(self._widget_creation_counts)