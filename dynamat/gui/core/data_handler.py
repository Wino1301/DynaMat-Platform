"""Form data handler for widget value operations.

This module provides centralized logic for extracting and populating data
from/to form widgets. It handles type-safe value operations across all
supported PyQt6 widget types.

Classes
-------
FormDataHandler
    Handles data extraction and population for form widgets.

Supported Widget Types
----------------------
- QLabel (read-only display)
- QLineEdit (single-line text)
- QTextEdit (multi-line text)
- QComboBox (dropdown selection)
- QListWidget (multi-select list)
- QSpinBox (integer values)
- QDoubleSpinBox (floating-point values)
- QDateEdit (date values)
- QCheckBox (boolean values)
- UnitValueWidget (measurement with units)

Example
-------
::

    handler = FormDataHandler()

    # Extract data from form
    data = handler.extract_form_data(form_widget)

    # Populate form with data
    handler.populate_form_data(form_widget, data)

    # Validate form data
    errors = handler.validate_form_data(form_widget)
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QTextEdit, QComboBox,
    QSpinBox, QDoubleSpinBox, QDateEdit, QCheckBox,
    QListWidget, QGroupBox, QFormLayout, QVBoxLayout, QHBoxLayout
)
from PyQt6.QtCore import QDate, Qt

logger = logging.getLogger(__name__)


class FormDataHandler:
    """Handles data extraction and population for form widgets.

    Provides centralized logic for getting/setting values from various
    widget types while maintaining type safety and proper error handling.
    Supports visibility-based filtering to exclude hidden fields from
    data extraction.

    Attributes
    ----------
    value_extractors : dict
        Mapping of widget types to extractor functions.
    value_setters : dict
        Mapping of widget types to setter functions.

    Example
    -------
    ::

        handler = FormDataHandler()

        # Get value from any widget
        value = handler.get_widget_value(widget)

        # Set value on any widget
        success = handler.set_widget_value(widget, new_value)
    """

    def __init__(self):
        
        # Value extractors by widget type
        self.value_extractors = {
            QLabel: self._extract_label_value,
            QLineEdit: self._extract_line_edit_value,
            QTextEdit: self._extract_text_edit_value,
            QComboBox: self._extract_combo_box_value,
            QListWidget: self._extract_list_widget_value,
            QSpinBox: self._extract_spinbox_value,
            QDoubleSpinBox: self._extract_double_spinbox_value,
            QDateEdit: self._extract_date_edit_value,
            QCheckBox: self._extract_checkbox_value,
        }
        
        # Value setters by widget type
        self.value_setters = {
            QLabel: self._set_label_value,
            QLineEdit: self._set_line_edit_value,
            QTextEdit: self._set_text_edit_value,
            QComboBox: self._set_combo_box_value,
            QListWidget: self._set_list_widget_value,
            QSpinBox: self._set_spinbox_value,
            QDoubleSpinBox: self._set_double_spinbox_value,
            QDateEdit: self._set_date_edit_value,
            QCheckBox: self._set_checkbox_value,
        }
    
    # ============================================================================
    # MAIN FORM DATA OPERATIONS
    # ============================================================================
    
    def extract_form_data(self, form_widget: QWidget) -> Dict[str, Any]:
        """
        Extract all data from a form widget.

        Only extracts data from visible widgets. Hidden widgets (due to dependencies
        or conditional display) are automatically excluded.

        Args:
            form_widget: The form widget containing form fields

        Returns:
            Dictionary mapping property URI to value
        """
        data = {}

        try:
            # Look for form_fields attribute (created by form builder)
            if hasattr(form_widget, 'form_fields'):
                form_fields = form_widget.form_fields

                for property_uri, form_field in form_fields.items():
                    try:
                        widget = form_field.widget

                        # VISIBILITY CHECK: Skip if widget or its parent is hidden
                        if not self._is_widget_visible(widget):
                            logger.debug(f"Skipping {property_uri}: widget not visible")
                            continue

                        # Extract value from visible widget
                        value = self.get_widget_value(widget)

                        # Skip None, empty strings, and placeholder values
                        if value is not None and value != "" and not self._is_placeholder_value(value, widget):
                            data[property_uri] = value
                        else:
                            logger.debug(f"Skipping {property_uri}: placeholder/empty value")

                    except Exception as e:
                        logger.error(f"Error extracting value for {property_uri}: {e}")

            else:
                logger.warning("Form widget has no form_fields attribute")

        except Exception as e:
            logger.error(f"Error extracting form data: {e}")

        logger.info(f"Extracted data for {len(data)} properties (visibility-filtered)")
        return data
    
    def populate_form_data(self, form_widget: QWidget, data: Dict[str, Any]) -> bool:
        """
        Populate form with data.
        
        Args:
            form_widget: The form widget to populate
            data: Dictionary mapping property URI to value
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not hasattr(form_widget, 'form_fields'):
                logger.error("Form widget has no form_fields attribute")
                return False
            
            form_fields = form_widget.form_fields
            populated_count = 0
            
            for property_uri, value in data.items():
                if property_uri in form_fields:
                    try:
                        widget = form_fields[property_uri].widget
                        widget_type = type(widget).__name__
                        if self.set_widget_value(widget, value):
                            logger.debug(f"SUCCESS: Set {property_uri} = '{value}' (widget: {widget_type})")
                            populated_count += 1
                        else:
                            logger.warning(f"FAILED: Could not set {property_uri} = '{value}' (widget: {widget_type})")
                    except Exception as e:
                        logger.error(f"Error setting value for {property_uri}: {e}")
                else:
                    # Extract short name for logging
                    short_name = property_uri.split('#')[-1].split('/')[-1] if '#' in property_uri or '/' in property_uri else property_uri
                    logger.warning(f"Property {short_name} not found in form (full URI: {property_uri})")

            logger.info(f"Populated {populated_count}/{len(data)} fields successfully")
            return populated_count > 0
            
        except Exception as e:
            logger.error(f"Error populating form data: {e}")
            return False
    
    def validate_form_data(self, form_widget: QWidget) -> Dict[str, List[str]]:
        """
        Validate form data and return validation errors.
        
        Args:
            form_widget: The form widget to validate
            
        Returns:
            Dictionary mapping property URI to list of error messages
        """
        errors = {}
        
        try:
            if not hasattr(form_widget, 'form_fields'):
                return {"form": ["Form has no fields to validate"]}
            
            form_fields = form_widget.form_fields
            
            for property_uri, form_field in form_fields.items():
                field_errors = []
                
                try:
                    # Check required fields
                    if form_field.required:
                        value = self.get_widget_value(form_field.widget)
                        if value is None or value == "":
                            field_errors.append("This field is required")
                    
                    # Add property-specific validation if needed
                    # This can be extended based on PropertyMetadata constraints
                    
                    if field_errors:
                        errors[property_uri] = field_errors
                        
                except Exception as e:
                    field_errors.append(f"Validation error: {e}")
                    errors[property_uri] = field_errors
            
        except Exception as e:
            errors["form"] = [f"Form validation error: {e}"]
        
        return errors
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================

    def _is_widget_visible(self, widget: QWidget) -> bool:
        """
        Check if a widget is visible (considering parent visibility).

        A widget is only truly visible if it AND all its parents are visible.
        This aligns with dependency system hiding/showing fields.

        Args:
            widget: Widget to check

        Returns:
            True if widget is visible and should be included in form data
        """
        if not widget:
            return False

        # Check widget itself
        if not widget.isVisible():
            return False

        # Check all parents up the hierarchy
        parent = widget.parent()
        while parent:
            if not parent.isVisible():
                return False
            parent = parent.parent()

        return True

    def _is_placeholder_value(self, value: Any, widget: QWidget = None) -> bool:
        """
        Check if a value is a placeholder (not real data).

        With visibility-based validation, this is much simpler:
        - String placeholders like "(Select...)"
        - For numeric values: only treat 0 as placeholder if it's the default AND field is optional

        Args:
            value: The value to check
            widget: Optional widget to check for context

        Returns:
            True if the value is a placeholder
        """
        # String placeholders
        if isinstance(value, str):
            placeholders = [
                "(Select...)",
                "(select...)",
                "Select...",
                "select...",
                "(None)",
                "(none)",
                "---",
                "N/A",
                "n/a",
                ""
            ]
            return value.strip() in placeholders

        # For unit value dictionaries, check if at default/unfilled state
        if isinstance(value, dict) and 'value' in value:
            numeric_val = value['value']
            # Only treat 0 as placeholder if widget is at its minimum value
            # This allows intentional 0 entries
            if numeric_val == 0 or numeric_val == 0.0:
                # Check if this is just default unfilled state
                if widget and hasattr(widget, 'value_spinbox'):
                    # If user hasn't changed from default, it's a placeholder
                    spinbox = widget.value_spinbox
                    return spinbox.value() == spinbox.minimum()
                # Default: treat 0 in dict as placeholder for backward compat
                return True
            return False

        # For plain numeric values (spinboxes without units)
        # Only treat 0 as placeholder if it's at the widget's minimum value
        if isinstance(value, (int, float)):
            if value == 0 or value == 0.0:
                # If we have widget context, check if user has changed it
                if widget and isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                    return widget.value() == widget.minimum()
                # Default: treat 0 as placeholder
                return True
            return False

        return False

    # ============================================================================
    # WIDGET VALUE OPERATIONS
    # ============================================================================

    def get_widget_value(self, widget: QWidget) -> Any:
        """
        Get value from any widget type.
        
        Args:
            widget: The widget to extract value from
            
        Returns:
            The widget's current value, or None if extraction fails
        """
        try:
            # Check for custom unit value widget
            if self._is_unit_value_widget(widget):
                return self._extract_unit_value_widget_value(widget)
            
            # Check standard widget types
            widget_type = type(widget)
            if widget_type in self.value_extractors:
                return self.value_extractors[widget_type](widget)
            
            # Handle compound widgets (widgets with layouts containing sub-widgets)
            if hasattr(widget, 'layout') and widget.layout():
                return self._extract_compound_widget_value(widget)
            
            logger.warning(f"No value extractor for widget type: {widget_type}")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting value from {type(widget)}: {e}")
            return None
    
    def set_widget_value(self, widget: QWidget, value: Any) -> bool:
        """
        Set value for any widget type.
        
        Args:
            widget: The widget to set value for
            value: The value to set
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Handle None/empty values
            if value is None:
                return False
            
            # Check for custom unit value widget
            if self._is_unit_value_widget(widget):
                return self._set_unit_value_widget_value(widget, value)
            
            # Check standard widget types
            widget_type = type(widget)
            if widget_type in self.value_setters:
                return self.value_setters[widget_type](widget, value)
            
            # Handle compound widgets
            if hasattr(widget, 'layout') and widget.layout():
                return self._set_compound_widget_value(widget, value)
            
            logger.warning(f"No value setter for widget type: {widget_type}")
            return False
            
        except Exception as e:
            logger.error(f"Error setting value for {type(widget)}: {e}")
            return False
    
    # ============================================================================
    # VALUE EXTRACTORS
    # ============================================================================

    def _extract_label_value(self, widget: QLabel) -> str:
        """Extract value from QLabel (for read-only fields)."""
        text = widget.text().strip()
        # Skip empty or placeholder values
        if text and text != "(auto-generated)" and text != "-":
            return text
        return None

    def _extract_line_edit_value(self, widget: QLineEdit) -> str:
        """Extract value from QLineEdit."""
        return widget.text().strip()
    
    def _extract_text_edit_value(self, widget: QTextEdit) -> str:
        """Extract value from QTextEdit."""
        return widget.toPlainText().strip()
    
    def _extract_combo_box_value(self, widget: QComboBox) -> Any:
        """Extract value from QComboBox."""
        # Try to get data first (URI), then text (display name)
        data = widget.currentData()
        if data is not None and data != "":
            return data
        return widget.currentText()

    def _extract_list_widget_value(self, widget: QListWidget) -> Union[List[str], str]:
        """
        Extract value from QListWidget (for multi-select fields like manufacturing methods).
        Returns list of selected items' data (URIs) or text if no data.
        """
        selected_items = widget.selectedItems()
        if not selected_items:
            return None

        values = []
        for item in selected_items:
            # Try to get data (URI) first, then fall back to text
            data = item.data(Qt.ItemDataRole.UserRole)
            if data is not None and data != "":
                values.append(data)
            else:
                values.append(item.text())

        # Return single value if only one selected, otherwise return list
        if len(values) == 1:
            return values[0]
        return values

    def _extract_spinbox_value(self, widget: QSpinBox) -> int:
        """Extract value from QSpinBox."""
        return widget.value()
    
    def _extract_double_spinbox_value(self, widget: QDoubleSpinBox) -> float:
        """Extract value from QDoubleSpinBox."""
        return widget.value()
    
    def _extract_date_edit_value(self, widget: QDateEdit) -> str:
        """Extract value from QDateEdit."""
        return widget.date().toString("yyyy-MM-dd")
    
    def _extract_checkbox_value(self, widget: QCheckBox) -> bool:
        """Extract value from QCheckBox."""
        return widget.isChecked()
    
    def _extract_unit_value_widget_value(self, widget: QWidget) -> Dict[str, Any]:
        """Extract value from UnitValueWidget."""
        try:
            data = {
                'value': widget.getValue(),
                'unit': widget.getUnit(),
                'unit_symbol': widget.getUnitSymbol()
            }

            # Add reference_unit if available (for unit conversion)
            if hasattr(widget, 'reference_unit_uri') and widget.reference_unit_uri:
                data['reference_unit'] = widget.reference_unit_uri

            return data
        except Exception as e:
            logger.error(f"Error extracting unit value widget: {e}")
            return None
    
    def _extract_compound_widget_value(self, widget: QWidget) -> Any:
        """Extract value from compound widgets (widgets with sub-widgets)."""
        layout = widget.layout()
        if layout and layout.count() > 0:
            # Try the first widget in the layout
            first_item = layout.itemAt(0)
            if first_item and first_item.widget():
                return self.get_widget_value(first_item.widget())
        return None
    
    # ============================================================================
    # VALUE SETTERS
    # ============================================================================
    
    def _set_label_value(self, widget: QLabel, value: Any) -> bool:
        """Set value for QLabel (read-only display fields)."""
        widget.setText(str(value))
        return True

    def _set_line_edit_value(self, widget: QLineEdit, value: Any) -> bool:
        """Set value for QLineEdit."""
        widget.setText(str(value))
        return True
    
    def _set_text_edit_value(self, widget: QTextEdit, value: Any) -> bool:
        """Set value for QTextEdit."""
        widget.setPlainText(str(value))
        return True
    
    def _set_combo_box_value(self, widget: QComboBox, value: Any) -> bool:
        """Set value for QComboBox."""
        # Try to find by data first
        for i in range(widget.count()):
            if widget.itemData(i) == value:
                widget.setCurrentIndex(i)
                return True

        # Try to find by text
        index = widget.findText(str(value))
        if index >= 0:
            widget.setCurrentIndex(index)
            return True

        # Set as editable text if not found
        if widget.isEditable():
            widget.setCurrentText(str(value))
            return True

        return False

    def _set_list_widget_value(self, widget: QListWidget, value: Any) -> bool:
        """
        Set value for QListWidget (for multi-select fields).
        Value can be a single item or a list of items.
        """
        # Clear current selection
        widget.clearSelection()

        # Normalize value to list
        if not isinstance(value, list):
            values = [value] if value else []
        else:
            values = value

        if not values:
            return False

        success = False
        for val in values:
            # Try to find and select by data first
            for i in range(widget.count()):
                item = widget.item(i)
                item_data = item.data(Qt.ItemDataRole.UserRole)
                if item_data == val or item.text() == str(val):
                    item.setSelected(True)
                    success = True
                    break

        return success

    def _set_spinbox_value(self, widget: QSpinBox, value: Any) -> bool:
        """Set value for QSpinBox."""
        try:
            widget.setValue(int(value))
            return True
        except (ValueError, TypeError):
            return False
    
    def _set_double_spinbox_value(self, widget: QDoubleSpinBox, value: Any) -> bool:
        """Set value for QDoubleSpinBox."""
        try:
            widget.setValue(float(value))
            return True
        except (ValueError, TypeError):
            return False
    
    def _set_date_edit_value(self, widget: QDateEdit, value: Any) -> bool:
        """Set value for QDateEdit."""
        try:
            if isinstance(value, str):
                date = QDate.fromString(value, "yyyy-MM-dd")
                if date.isValid():
                    widget.setDate(date)
                    return True
            return False
        except Exception:
            return False
    
    def _set_checkbox_value(self, widget: QCheckBox, value: Any) -> bool:
        """Set value for QCheckBox."""
        try:
            # Handle various boolean representations
            if isinstance(value, bool):
                widget.setChecked(value)
            elif isinstance(value, str):
                widget.setChecked(value.lower() in ('true', '1', 'yes', 'on'))
            elif isinstance(value, (int, float)):
                widget.setChecked(bool(value))
            else:
                widget.setChecked(bool(value))
            return True
        except Exception:
            return False
    
    def _set_unit_value_widget_value(self, widget: QWidget, value: Any) -> bool:
        """Set value for UnitValueWidget."""
        try:
            if isinstance(value, dict):
                # Set value and unit separately
                if 'value' in value:
                    widget.setValue(float(value['value']))
                if 'unit' in value:
                    widget.setUnit(value['unit'])
                return True
            else:
                # Set just the numeric value
                widget.setValue(float(value))
                return True
        except Exception as e:
            logger.error(f"Error setting unit value widget: {e}")
            return False
    
    def _set_compound_widget_value(self, widget: QWidget, value: Any) -> bool:
        """Set value for compound widgets."""
        layout = widget.layout()
        if layout and layout.count() > 0:
            # Try the first widget in the layout
            first_item = layout.itemAt(0)
            if first_item and first_item.widget():
                return self.set_widget_value(first_item.widget(), value)
        return False
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    def _is_unit_value_widget(self, widget: QWidget) -> bool:
        """Check if widget is a UnitValueWidget."""
        return (hasattr(widget, 'getValue') and 
                hasattr(widget, 'setValue') and 
                hasattr(widget, 'getUnit') and 
                hasattr(widget, 'setUnit'))
    
    def get_form_summary(self, form_widget: QWidget) -> Dict[str, Any]:
        """
        Get a summary of form data for debugging/logging.
        
        Args:
            form_widget: The form widget to summarize
            
        Returns:
            Dictionary with form summary information
        """
        summary = {
            'total_fields': 0,
            'filled_fields': 0,
            'empty_fields': 0,
            'error_fields': 0,
            'field_types': {}
        }
        
        try:
            if hasattr(form_widget, 'form_fields'):
                form_fields = form_widget.form_fields
                summary['total_fields'] = len(form_fields)
                
                for property_uri, form_field in form_fields.items():
                    widget_type = type(form_field.widget).__name__
                    summary['field_types'][widget_type] = summary['field_types'].get(widget_type, 0) + 1
                    
                    try:
                        value = self.get_widget_value(form_field.widget)
                        if value is not None and value != "":
                            summary['filled_fields'] += 1
                        else:
                            summary['empty_fields'] += 1
                    except Exception:
                        summary['error_fields'] += 1
                        
        except Exception as e:
            summary['error'] = str(e)
        
        return summary