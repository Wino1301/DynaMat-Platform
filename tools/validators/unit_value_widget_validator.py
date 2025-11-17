"""
DynaMat Platform - UnitValueWidget Validator
Specialized validation for UnitValueWidget instances.
"""

from typing import Dict, Any, List, Tuple, Optional
import logging

from PyQt6.QtWidgets import QDoubleSpinBox, QComboBox
from PyQt6.QtCore import Qt

logger = logging.getLogger(__name__)


def validate_unit_value_widget(
    widget: Any,
    property_metadata: Any,
    verbose: bool = False
) -> Tuple[bool, Dict[str, Any]]:
    """
    Validate a UnitValueWidget instance against its property metadata.

    Args:
        widget: The UnitValueWidget instance to validate
        property_metadata: PropertyMetadata for this widget
        verbose: Enable detailed logging

    Returns:
        Tuple of (passed: bool, details: dict)

    Details dictionary contains:
        - validation_checks: Dict[str, bool] - Individual check results
        - value_spinbox_info: Dict - Spinbox state information
        - unit_combobox_info: Dict - Combobox state information
        - unit_items: List[Dict] - Information about each unit item
        - errors: List[str] - List of validation errors
        - warnings: List[str] - List of validation warnings
    """
    details = {
        'validation_checks': {},
        'value_spinbox_info': {},
        'unit_combobox_info': {},
        'unit_items': [],
        'errors': [],
        'warnings': []
    }

    all_passed = True

    # Check that widget is actually a UnitValueWidget
    if widget.__class__.__name__ != 'UnitValueWidget':
        details['errors'].append(f"Widget is not UnitValueWidget, got {type(widget).__name__}")
        return False, details

    # Validate Value Spinbox
    spinbox_passed, spinbox_info = _validate_value_spinbox(
        widget, property_metadata, verbose
    )
    details['value_spinbox_info'] = spinbox_info
    details['validation_checks'].update(spinbox_info.get('checks', {}))
    all_passed = all_passed and spinbox_passed

    if not spinbox_passed:
        details['errors'].extend(spinbox_info.get('errors', []))

    # Validate Unit Combobox
    combobox_passed, combobox_info = _validate_unit_combobox(
        widget, property_metadata, verbose
    )
    details['unit_combobox_info'] = combobox_info
    details['validation_checks'].update(combobox_info.get('checks', {}))
    all_passed = all_passed and combobox_passed

    if not combobox_passed:
        details['errors'].extend(combobox_info.get('errors', []))

    # Validate Unit Items
    items_passed, items_info = _validate_unit_items(
        widget, property_metadata, verbose
    )
    details['unit_items'] = items_info.get('items', [])
    details['validation_checks'].update(items_info.get('checks', {}))
    all_passed = all_passed and items_passed

    if not items_passed:
        details['errors'].extend(items_info.get('errors', []))

    # Validate Default Unit Selection
    default_passed, default_info = _validate_default_unit_selection(
        widget, property_metadata, verbose
    )
    details['validation_checks'].update(default_info.get('checks', {}))
    details['unit_combobox_info'].update(default_info)
    all_passed = all_passed and default_passed

    if not default_passed:
        details['errors'].extend(default_info.get('errors', []))
    else:
        # Informational warning if default not matched
        if default_info.get('default_matched') == False:
            details['warnings'].append(
                f"Default unit not matched, using first unit: "
                f"{default_info.get('current_unit_symbol')}"
            )

    # Validate Read-Only State
    if property_metadata.is_read_only:
        readonly_passed, readonly_info = _validate_readonly_state(
            widget, property_metadata, verbose
        )
        details['validation_checks'].update(readonly_info.get('checks', {}))
        all_passed = all_passed and readonly_passed

        if not readonly_passed:
            details['errors'].extend(readonly_info.get('errors', []))

    # Overall Widget State
    widget_passed, widget_info = _validate_widget_state(
        widget, property_metadata, verbose
    )
    details['validation_checks'].update(widget_info.get('checks', {}))
    all_passed = all_passed and widget_passed

    if not widget_passed:
        details['errors'].extend(widget_info.get('errors', []))

    return all_passed, details


def _validate_value_spinbox(
    widget: Any,
    property_metadata: Any,
    verbose: bool
) -> Tuple[bool, Dict[str, Any]]:
    """Validate the value spinbox component."""
    info = {
        'checks': {},
        'errors': [],
        'value': None,
        'minimum': None,
        'maximum': None,
        'decimals': None,
        'single_step': None,
        'min_width': None,
        'is_enabled': None,
        'is_readonly': None
    }

    all_passed = True

    # Check spinbox exists
    if not hasattr(widget, 'value_spinbox'):
        info['checks']['value_spinbox_exists'] = False
        info['errors'].append("Widget missing 'value_spinbox' attribute")
        return False, info

    info['checks']['value_spinbox_exists'] = True
    spinbox = widget.value_spinbox

    # Check type
    if not isinstance(spinbox, QDoubleSpinBox):
        info['checks']['value_spinbox_type_correct'] = False
        info['errors'].append(f"value_spinbox is not QDoubleSpinBox: {type(spinbox).__name__}")
        return False, info

    info['checks']['value_spinbox_type_correct'] = True

    # Check initial value
    info['value'] = spinbox.value()
    if spinbox.value() == 0.0:
        info['checks']['value_spinbox_initial_value_is_zero'] = True
    else:
        info['checks']['value_spinbox_initial_value_is_zero'] = False
        info['errors'].append(f"Initial value should be 0.0, got {spinbox.value()}")
        all_passed = False

    # Check minimum
    info['minimum'] = spinbox.minimum()
    if spinbox.minimum() == -1e10:
        info['checks']['value_spinbox_minimum_correct'] = True
    else:
        info['checks']['value_spinbox_minimum_correct'] = False
        info['errors'].append(f"Minimum should be -1e10, got {spinbox.minimum()}")
        all_passed = False

    # Check maximum
    info['maximum'] = spinbox.maximum()
    if spinbox.maximum() == 1e10:
        info['checks']['value_spinbox_maximum_correct'] = True
    else:
        info['checks']['value_spinbox_maximum_correct'] = False
        info['errors'].append(f"Maximum should be 1e10, got {spinbox.maximum()}")
        all_passed = False

    # Check decimals
    info['decimals'] = spinbox.decimals()
    if spinbox.decimals() == 6:
        info['checks']['value_spinbox_decimals_correct'] = True
    else:
        info['checks']['value_spinbox_decimals_correct'] = False
        info['errors'].append(f"Decimals should be 6, got {spinbox.decimals()}")
        all_passed = False

    # Check single step
    info['single_step'] = spinbox.singleStep()
    if spinbox.singleStep() == 0.1:
        info['checks']['value_spinbox_step_correct'] = True
    else:
        info['checks']['value_spinbox_step_correct'] = False
        info['errors'].append(f"Single step should be 0.1, got {spinbox.singleStep()}")
        all_passed = False

    # Check minimum width
    info['min_width'] = spinbox.minimumWidth()
    if spinbox.minimumWidth() >= 100:
        info['checks']['value_spinbox_min_width_correct'] = True
    else:
        info['checks']['value_spinbox_min_width_correct'] = False
        info['errors'].append(f"Minimum width should be >= 100, got {spinbox.minimumWidth()}")
        all_passed = False

    # Check enabled state (unless read-only)
    info['is_enabled'] = spinbox.isEnabled()
    if not property_metadata.is_read_only:
        if spinbox.isEnabled():
            info['checks']['value_spinbox_enabled_state'] = True
        else:
            info['checks']['value_spinbox_enabled_state'] = False
            info['errors'].append("Spinbox should be enabled for non-read-only property")
            all_passed = False

    # Check readonly state
    info['is_readonly'] = spinbox.isReadOnly()

    if verbose:
        logger.debug(f"Value Spinbox: value={info['value']}, range=[{info['minimum']}, {info['maximum']}]")
        logger.debug(f"  decimals={info['decimals']}, step={info['single_step']}, width={info['min_width']}")

    return all_passed, info


def _validate_unit_combobox(
    widget: Any,
    property_metadata: Any,
    verbose: bool
) -> Tuple[bool, Dict[str, Any]]:
    """Validate the unit combobox component."""
    info = {
        'checks': {},
        'errors': [],
        'count': 0,
        'expected_count': 0,
        'min_width': None,
        'is_enabled': None,
        'current_index': None,
        'current_text': None,
        'current_data': None
    }

    all_passed = True

    # Check combobox exists
    if not hasattr(widget, 'unit_combobox'):
        info['checks']['unit_combobox_exists'] = False
        info['errors'].append("Widget missing 'unit_combobox' attribute")
        return False, info

    info['checks']['unit_combobox_exists'] = True
    combobox = widget.unit_combobox

    # Check type
    if not isinstance(combobox, QComboBox):
        info['checks']['unit_combobox_type_correct'] = False
        info['errors'].append(f"unit_combobox is not QComboBox: {type(combobox).__name__}")
        return False, info

    info['checks']['unit_combobox_type_correct'] = True

    # Check populated
    info['count'] = combobox.count()
    if combobox.count() > 0:
        info['checks']['unit_combobox_populated'] = True
    else:
        info['checks']['unit_combobox_populated'] = False
        info['errors'].append("Unit combobox is empty")
        all_passed = False

    # Check count matches metadata
    info['expected_count'] = len(property_metadata.compatible_units) if property_metadata.compatible_units else 0
    if combobox.count() == info['expected_count']:
        info['checks']['unit_combobox_count_matches_metadata'] = True
    else:
        info['checks']['unit_combobox_count_matches_metadata'] = False
        info['errors'].append(
            f"Unit count mismatch: expected {info['expected_count']}, got {combobox.count()}"
        )
        all_passed = False

    # Check minimum width
    info['min_width'] = combobox.minimumWidth()
    if combobox.minimumWidth() >= 100:
        info['checks']['unit_combobox_min_width_correct'] = True
    else:
        info['checks']['unit_combobox_min_width_correct'] = False
        info['errors'].append(f"Minimum width should be >= 100, got {combobox.minimumWidth()}")
        all_passed = False

    # Check enabled state (unless read-only)
    info['is_enabled'] = combobox.isEnabled()
    if not property_metadata.is_read_only:
        if combobox.isEnabled():
            info['checks']['unit_combobox_enabled_state'] = True
        else:
            info['checks']['unit_combobox_enabled_state'] = False
            info['errors'].append("Combobox should be enabled for non-read-only property")
            all_passed = False

    # Get current selection
    info['current_index'] = combobox.currentIndex()
    info['current_text'] = combobox.currentText()
    info['current_data'] = combobox.currentData()

    if verbose:
        logger.debug(f"Unit Combobox: count={info['count']}, expected={info['expected_count']}")
        logger.debug(f"  current_index={info['current_index']}, text='{info['current_text']}'")
        logger.debug(f"  current_data={info['current_data']}")

    return all_passed, info


def _validate_unit_items(
    widget: Any,
    property_metadata: Any,
    verbose: bool
) -> Tuple[bool, Dict[str, Any]]:
    """Validate individual unit items in the combobox."""
    info = {
        'checks': {},
        'errors': [],
        'items': []
    }

    all_passed = True
    combobox = widget.unit_combobox

    has_symbols = True
    has_uris = True
    has_tooltips = True

    for i in range(combobox.count()):
        item_info = {
            'index': i,
            'text': combobox.itemText(i),
            'data': combobox.itemData(i),
            'tooltip': combobox.itemData(i, Qt.ItemDataRole.ToolTipRole)
        }

        # Check has symbol (text)
        if not item_info['text']:
            has_symbols = False
            info['errors'].append(f"Item {i} has no symbol (text)")
            all_passed = False

        # Check has URI (data)
        if not item_info['data']:
            has_uris = False
            info['errors'].append(f"Item {i} has no URI (data)")
            all_passed = False

        # Tooltip is optional but nice to have
        if not item_info['tooltip']:
            has_tooltips = False

        info['items'].append(item_info)

        if verbose:
            logger.debug(f"  Unit {i}: '{item_info['text']}' ({item_info['data']})")

    info['checks']['unit_items_have_symbols'] = has_symbols
    info['checks']['unit_items_have_uris'] = has_uris
    info['checks']['unit_items_have_tooltips'] = has_tooltips

    return all_passed, info


def _validate_default_unit_selection(
    widget: Any,
    property_metadata: Any,
    verbose: bool
) -> Tuple[bool, Dict[str, Any]]:
    """Validate that the default unit is correctly selected."""
    info = {
        'checks': {},
        'errors': [],
        'expected_unit_uri': property_metadata.default_unit,
        'current_unit_uri': None,
        'current_unit_symbol': None,
        'default_matched': False
    }

    all_passed = True
    combobox = widget.unit_combobox

    # Get current selection
    info['current_unit_uri'] = combobox.currentData()
    info['current_unit_symbol'] = combobox.currentText()

    # Normalize URIs for comparison
    def normalize_uri(uri):
        if not uri:
            return None
        uri = str(uri).strip().strip('"\'')
        if ':' in uri and not uri.startswith('http'):
            prefix, local = uri.split(':', 1)
            if prefix == 'unit':
                uri = f'http://qudt.org/vocab/unit/{local}'
            elif prefix == 'qkdv':
                uri = f'http://qudt.org/vocab/quantitykind/{local}'
        return uri

    expected_normalized = normalize_uri(info['expected_unit_uri'])
    current_normalized = normalize_uri(info['current_unit_uri'])

    # Check if default unit is selected
    if expected_normalized and current_normalized:
        if expected_normalized == current_normalized:
            info['checks']['unit_combobox_default_unit_selected'] = True
            info['checks']['unit_combobox_default_unit_uri_matches'] = True
            info['default_matched'] = True
        else:
            info['checks']['unit_combobox_default_unit_selected'] = False
            info['checks']['unit_combobox_default_unit_uri_matches'] = False
            info['default_matched'] = False
            info['errors'].append(
                f"Default unit not selected. Expected: {expected_normalized}, "
                f"Got: {current_normalized}"
            )
            all_passed = False
    elif not expected_normalized:
        # No default specified, should select first unit
        if combobox.currentIndex() == 0:
            info['checks']['unit_combobox_default_unit_selected'] = True
            info['default_matched'] = False  # No default to match
        else:
            info['checks']['unit_combobox_default_unit_selected'] = False
            info['errors'].append("No default unit specified but first unit not selected")
            all_passed = False

    if verbose:
        logger.debug(f"Default unit validation:")
        logger.debug(f"  Expected: {expected_normalized}")
        logger.debug(f"  Current: {current_normalized}")
        logger.debug(f"  Matched: {info['default_matched']}")

    return all_passed, info


def _validate_readonly_state(
    widget: Any,
    property_metadata: Any,
    verbose: bool
) -> Tuple[bool, Dict[str, Any]]:
    """Validate read-only state configuration."""
    info = {
        'checks': {},
        'errors': []
    }

    all_passed = True

    spinbox = widget.value_spinbox
    combobox = widget.unit_combobox

    # Check spinbox is readonly
    if spinbox.isReadOnly():
        info['checks']['value_spinbox_readonly_correct'] = True
    else:
        info['checks']['value_spinbox_readonly_correct'] = False
        info['errors'].append("Read-only property: spinbox should have isReadOnly() = True")
        all_passed = False

    # Check combobox is disabled
    if not combobox.isEnabled():
        info['checks']['unit_combobox_readonly_correct'] = True
    else:
        info['checks']['unit_combobox_readonly_correct'] = False
        info['errors'].append("Read-only property: combobox should be disabled")
        all_passed = False

    if verbose:
        logger.debug(f"Read-only state: spinbox.isReadOnly()={spinbox.isReadOnly()}, "
                    f"combobox.isEnabled()={combobox.isEnabled()}")

    return all_passed, info


def _validate_widget_state(
    widget: Any,
    property_metadata: Any,
    verbose: bool
) -> Tuple[bool, Dict[str, Any]]:
    """Validate overall widget state."""
    info = {
        'checks': {},
        'errors': []
    }

    all_passed = True

    # Check enabled state (unless read-only)
    if not property_metadata.is_read_only:
        if widget.isEnabled():
            info['checks']['widget_enabled_state'] = True
        else:
            info['checks']['widget_enabled_state'] = False
            info['errors'].append("Widget should be enabled for non-read-only property")
            all_passed = False
    else:
        info['checks']['widget_enabled_state'] = True  # Read-only handled separately

    if verbose:
        logger.debug(f"Widget state: enabled={widget.isEnabled()}")

    return all_passed, info
