"""
DynaMat Platform - Layout Manager
Handles form layout creation and widget grouping
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
    QGroupBox, QLabel, QScrollArea, QFrame, QSplitter
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ...ontology import PropertyMetadata

logger = logging.getLogger(__name__)

class LayoutStyle(Enum):
    """Available layout styles for forms."""
    GROUPED_FORM = "grouped_form"       # Groups with form layouts (default)
    TABBED_FORM = "tabbed_form"         # Groups as tabs
    SINGLE_COLUMN = "single_column"     # Single column, no groups
    TWO_COLUMN = "two_column"           # Two columns with groups
    GRID_LAYOUT = "grid_layout"         # Grid-based layout
    

class LayoutManager:
    """
    Manages form layout creation and widget organization.
    
    Handles:
    - Creating grouped forms from property metadata
    - Organizing widgets into logical groups
    - Managing form layouts and styling
    - Creating scrollable and resizable forms
    """
    
    def __init__(self):
        """Initialize the layout manager."""
        self.logger = logging.getLogger(__name__)
        
        # Default styling
        self.group_style = """
        QGroupBox {
            font-weight: bold;
            border: 2px solid gray;
            border-radius: 5px;
            margin-top: 1ex;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
        }
        """
        
        self.required_field_style = """
        border-left: 3px solid orange;
        """
    
    # ============================================================================
    # MAIN FORM CREATION
    # ============================================================================
    
    def create_grouped_form(self, form_groups: Dict[str, List[PropertyMetadata]], 
                          widgets: Dict[str, QWidget],
                          parent: Optional[QWidget] = None) -> QWidget:
        """
        Create a complete form with grouped widgets.
        
        Args:
            form_groups: Dictionary mapping group names to property lists
            widgets: Dictionary mapping property URIs to widgets
            parent: Parent widget
            
        Returns:
            Complete form widget with all groups and widgets
        """
        try:
            self.logger.info(f"Creating grouped form with {len(form_groups)} groups")
            
            # Create main form widget
            form_widget = QWidget(parent)
            main_layout = QVBoxLayout(form_widget)
            main_layout.setContentsMargins(0, 0, 0, 0)
            main_layout.setSpacing(10)
            
            # Create scrollable area
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            
            # Create content widget
            content_widget = QWidget()
            content_layout = QVBoxLayout(content_widget)
            content_layout.setSpacing(15)
            
            # Create form fields dictionary for data handling
            form_fields = {}
            groups_created = 0
            total_fields = 0
            
            # Create groups in display order
            ordered_groups = self._get_ordered_groups(form_groups)
            
            for group_name in ordered_groups:
                properties = form_groups[group_name]
                
                if not properties:
                    continue
                
                # Create group widget
                group_widget, group_fields = self._create_group_widget(
                    group_name, properties, widgets
                )
                
                if group_widget:
                    content_layout.addWidget(group_widget)
                    form_fields.update(group_fields)
                    groups_created += 1
                    total_fields += len(group_fields)
            
            # Add stretch to push groups to top
            content_layout.addStretch()
            
            # Set content in scroll area
            scroll_area.setWidget(content_widget)
            main_layout.addWidget(scroll_area)
            
            # Store form fields for data handler
            form_widget.form_fields = form_fields
            form_widget.groups_created = groups_created
            form_widget.total_fields = total_fields
            
            self.logger.info(f"Created form with {groups_created} groups and {total_fields} fields")
            return form_widget
            
        except Exception as e:
            self.logger.error(f"Failed to create grouped form: {e}")
            # Return error widget
            error_widget = QLabel(f"Error creating form: {str(e)}")
            error_widget.setStyleSheet("color: red; padding: 20px;")
            return error_widget
    
    def create_simple_form(self, properties: List[PropertyMetadata],
                         widgets: Dict[str, QWidget],
                         parent: Optional[QWidget] = None) -> QWidget:
        """
        Create a simple form without grouping.
        
        Args:
            properties: List of properties
            widgets: Dictionary mapping property URIs to widgets
            parent: Parent widget
            
        Returns:
            Simple form widget
        """
        try:
            # Create single group with all properties
            form_groups = {"Properties": properties}
            return self.create_grouped_form(form_groups, widgets, parent)
            
        except Exception as e:
            self.logger.error(f"Failed to create simple form: {e}")
            error_widget = QLabel(f"Error creating form: {str(e)}")
            error_widget.setStyleSheet("color: red; padding: 20px;")
            return error_widget
    
    # ============================================================================
    # GROUP CREATION
    # ============================================================================
    
    def _create_group_widget(self, group_name: str, 
                           properties: List[PropertyMetadata],
                           widgets: Dict[str, QWidget]) -> QWidget:
        """
        Create a widget for a group of properties.
        
        Args:
            group_name: Name of the group
            properties: List of properties in the group
            widgets: Available widgets dictionary
            
        Returns:
            Tuple of (group_widget, form_fields_dict)
        """
        try:
            # Create group box
            group_box = QGroupBox(self._format_group_name(group_name))
            group_box.setStyleSheet(self.group_style)
            
            # Create form layout
            form_layout = QFormLayout(group_box)
            form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            form_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            form_layout.setSpacing(8)
            
            # Create form fields
            form_fields = {}
            fields_added = 0
            
            # Sort properties by display order
            sorted_properties = self._sort_properties_by_order(properties)
            
            for prop in sorted_properties:
                if prop.uri not in widgets:
                    self.logger.warning(f"No widget available for property: {prop.uri}")
                    continue
                
                widget = widgets[prop.uri]
                
                # Create label
                label_text = self._create_field_label(prop)
                label = QLabel(label_text)
                
                # Apply required styling
                if getattr(prop, 'is_required', False):
                    widget.setStyleSheet(
                        widget.styleSheet() + self.required_field_style
                    )
                
                # Add to form layout
                form_layout.addRow(label, widget)
                
                # Create form field
                form_field = FormField(
                    widget=widget,
                    property_uri=prop.uri,
                    property_metadata=prop,
                    group_name=group_name,
                    required=getattr(prop, 'is_required', False),
                    label=label_text
                )
                
                form_fields[prop.uri] = form_field
                fields_added += 1
            
            if fields_added == 0:
                self.logger.warning(f"No fields added to group: {group_name}")
                return None, {}
            
            self.logger.debug(f"Created group '{group_name}' with {fields_added} fields")
            return group_box, form_fields
            
        except Exception as e:
            self.logger.error(f"Error creating group '{group_name}': {e}")
            return None, {}
    
    # ============================================================================
    # LAYOUT UTILITIES
    # ============================================================================
    
    def _get_ordered_groups(self, form_groups: Dict[str, List[PropertyMetadata]]) -> List[str]:
        """
        Get groups ordered by their display priority.
        
        Args:
            form_groups: Dictionary of group names to properties
            
        Returns:
            List of group names in display order
        """
        def get_group_priority(group_name: str) -> int:
            """Determine group display priority."""
            priority_map = {
                'identification': 0,
                'basic': 1,
                'geometry': 2,
                'dimensions': 3,
                'material': 4,
                'properties': 5,
                'processing': 6,
                'testing': 7,
                'results': 8,
                'notes': 9,
                'general': 10
            }
            
            group_lower = group_name.lower()
            for key, priority in priority_map.items():
                if key in group_lower:
                    return priority
            
            # Default priority for unknown groups
            return 5
        
        # Sort groups by priority, then alphabetically
        return sorted(form_groups.keys(), 
                     key=lambda g: (get_group_priority(g), g.lower()))
    
    def _sort_properties_by_order(self, properties: List[PropertyMetadata]) -> List[PropertyMetadata]:
        """
        Sort properties by their display order.
        
        Args:
            properties: List of property metadata
            
        Returns:
            Sorted list of properties
        """
        def get_display_order(prop: PropertyMetadata) -> int:
            """Get display order for property."""
            if hasattr(prop, 'display_order') and prop.display_order is not None:
                return prop.display_order
            return 999  # Default order for properties without explicit order
        
        return sorted(properties, key=get_display_order)
    
    def _format_group_name(self, group_name: str) -> str:
        """
        Format group name for display.
        
        Args:
            group_name: Raw group name
            
        Returns:
            Formatted group name
        """
        if not group_name:
            return "General"
        
        # Convert camelCase and snake_case to Title Case
        formatted = group_name.replace('_', ' ').replace('-', ' ')
        
        # Split on capital letters for camelCase
        result = ""
        for i, char in enumerate(formatted):
            if char.isupper() and i > 0 and formatted[i-1].islower():
                result += " "
            result += char
        
        return result.title()
    
    def _create_field_label(self, prop: PropertyMetadata) -> str:
        """
        Create display label for a property.
        
        Args:
            prop: Property metadata
            
        Returns:
            Formatted label text
        """
        # Use display_name if available
        if hasattr(prop, 'display_name') and prop.display_name:
            label = prop.display_name
        elif hasattr(prop, 'label') and prop.label:
            label = prop.label
        else:
            label = self._format_property_name(prop.name)
        
        # Add required indicator
        if getattr(prop, 'is_required', False):
            label += " *"
        
        return label
    
    def _format_property_name(self, name: str) -> str:
        """
        Format property name for display.
        
        Args:
            name: Raw property name
            
        Returns:
            Formatted property name
        """
        if not name:
            return "Unknown"
        
        # Remove common prefixes
        if name.startswith("has") and len(name) > 3:
            name = name[3:]
        
        # Convert to readable format
        result = ""
        for i, char in enumerate(name):
            if char.isupper() and i > 0:
                result += " "
            result += char
        
        return result.title()
    
    # ============================================================================
    # SPECIALIZED LAYOUTS
    # ============================================================================
    
    def create_two_column_form(self, form_groups: Dict[str, List[PropertyMetadata]], 
                             widgets: Dict[str, QWidget],
                             parent: Optional[QWidget] = None) -> QWidget:
        """
        Create a two-column form layout.
        
        Args:
            form_groups: Dictionary mapping group names to property lists
            widgets: Dictionary mapping property URIs to widgets
            parent: Parent widget
            
        Returns:
            Two-column form widget
        """
        try:
            # Create main widget
            form_widget = QWidget(parent)
            main_layout = QHBoxLayout(form_widget)
            main_layout.setSpacing(20)
            
            # Split groups into two columns
            groups_list = list(form_groups.items())
            mid_point = len(groups_list) // 2
            
            left_groups = dict(groups_list[:mid_point])
            right_groups = dict(groups_list[mid_point:])
            
            # Create left column
            if left_groups:
                left_form = self.create_grouped_form(left_groups, widgets)
                main_layout.addWidget(left_form, 1)
            
            # Create right column
            if right_groups:
                right_form = self.create_grouped_form(right_groups, widgets)
                main_layout.addWidget(right_form, 1)
            
            # Combine form fields from both columns
            form_fields = {}
            if hasattr(left_form, 'form_fields'):
                form_fields.update(left_form.form_fields)
            if hasattr(right_form, 'form_fields'):
                form_fields.update(right_form.form_fields)
            
            form_widget.form_fields = form_fields
            
            return form_widget
            
        except Exception as e:
            self.logger.error(f"Error creating two-column form: {e}")
            # Fallback to single column
            return self.create_grouped_form(form_groups, widgets, parent)
    
    def create_tabbed_form(self, form_groups: Dict[str, List[PropertyMetadata]], 
                         widgets: Dict[str, QWidget],
                         parent: Optional[QWidget] = None) -> QWidget:
        """
        Create a tabbed form layout.
        
        Args:
            form_groups: Dictionary mapping group names to property lists
            widgets: Dictionary mapping property URIs to widgets
            parent: Parent widget
            
        Returns:
            Tabbed form widget
        """
        try:
            from PyQt6.QtWidgets import QTabWidget
            
            # Create tab widget
            tab_widget = QTabWidget(parent)
            
            # Create combined form fields
            form_fields = {}
            
            # Create tab for each group
            for group_name, properties in form_groups.items():
                if not properties:
                    continue
                
                # Create single group form
                group_form_groups = {group_name: properties}
                tab_form = self.create_grouped_form(group_form_groups, widgets)
                
                # Add tab
                tab_widget.addTab(tab_form, self._format_group_name(group_name))
                
                # Collect form fields
                if hasattr(tab_form, 'form_fields'):
                    form_fields.update(tab_form.form_fields)
            
            # Store form fields on tab widget
            tab_widget.form_fields = form_fields
            
            return tab_widget
            
        except Exception as e:
            self.logger.error(f"Error creating tabbed form: {e}")
            # Fallback to grouped form
            return self.create_grouped_form(form_groups, widgets, parent)
            
__all__ = ['LayoutManager', 'LayoutStyle']