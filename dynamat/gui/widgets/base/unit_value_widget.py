# Replace dynamat/gui/widgets/unit_value_widget.py

"""
DynaMat Platform - Unit-Value Widget
Custom widget for entering dimensional values with units from QUDT ontology
"""

import logging
from typing import Dict, List, Optional, Any, Union

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QDoubleSpinBox, QComboBox, QLabel
)
from PyQt6.QtCore import Qt, pyqtSignal

logger = logging.getLogger(__name__)


# Add debug output to your UnitValueWidget class

class UnitValueWidget(QWidget):
    """Enhanced UnitValueWidget with debugging"""

    # Signals 
    valueChanged = pyqtSignal(float)
    unitChanged = pyqtSignal(str)
    dataChanged = pyqtSignal()
    
    def __init__(self, default_unit: str = None, available_units: List = None,
                 property_uri: str = None, parent=None):
        super().__init__(parent)
        
        self.default_unit = default_unit
        self.available_units = available_units or []
        self.property_uri = property_uri
        
        self._setup_ui()
        self._populate_units()
        self._connect_signals()
        
    def _setup_ui(self):
        """Setup the widget UI"""
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # Value spinbox
        self.value_spinbox = QDoubleSpinBox()
        self.value_spinbox.setMinimum(-1e10)
        self.value_spinbox.setMaximum(1e10)
        self.value_spinbox.setDecimals(6)
        self.value_spinbox.setSingleStep(0.1)
        self.value_spinbox.setMinimumWidth(100)
        layout.addWidget(self.value_spinbox, 1)
        
        # Unit combobox - MAKE IT WIDER AND MORE VISIBLE
        self.unit_combobox = QComboBox()
        self.unit_combobox.setMinimumWidth(100)  # Increased from 60
        self.unit_combobox.setMaximumWidth(120)  # Increased from 80
        self.unit_combobox.setStyleSheet("QComboBox { border: 1px solid gray; padding: 2px; }")  # Make it more visible
        layout.addWidget(self.unit_combobox, 0)
            
    def _populate_units(self):
        """Populate the unit combobox from available units"""
        self.unit_combobox.clear()
        
        if not self.available_units:
            logger.warning("No available units to populate")
            self.unit_combobox.addItem("unit", "")
            return
        
        logger.info(f"Populating {len(self.available_units)} units")
        logger.info(f"  Default unit URI: {self.default_unit}")
        
        default_index = -1
        
        for i, unit_info in enumerate(self.available_units):
            try:
                # Handle UnitInfo objects
                symbol = unit_info.symbol
                uri = unit_info.uri
                
                # Add to combobox
                self.unit_combobox.addItem(symbol, uri)
                self.unit_combobox.setItemData(i, unit_info.name, Qt.ItemDataRole.ToolTipRole)
                
                # Check if this is the default unit (multiple ways)
                # 1. Direct URI match
                if self.default_unit and uri == self.default_unit:
                    default_index = i
                    logger.debug(f" Found default by URI match at index {i}")
                # 2. Check is_default flag
                elif hasattr(unit_info, 'is_default') and unit_info.is_default:
                    default_index = i
                    logger.debug(f" Found default by is_default flag at index {i}")
                # 3. Normalize and compare (handles namespace prefixes)
                elif self.default_unit:
                    default_normalized = self._normalize_uri(self.default_unit)
                    uri_normalized = self._normalize_uri(uri)
                    if default_normalized == uri_normalized:
                        default_index = i
                        logger.debug(f" Found default by normalized match at index {i}")
                        
            except Exception as e:
                logger.error(f"Error processing unit {i}: {e}", exc_info=True)
        
        # Set default unit
        if default_index >= 0:
            self.unit_combobox.setCurrentIndex(default_index)
            logger.info(f"Set default unit to index {default_index}: {self.unit_combobox.itemText(default_index)}")
        elif self.unit_combobox.count() > 0:
            # If no default specified, select the first unit
            self.unit_combobox.setCurrentIndex(0)
            logger.info(f"No default unit matched, selected first: {self.unit_combobox.itemText(0)}")
        
        logger.info(f"Combobox populated with {self.unit_combobox.count()} items")
    
    def _normalize_uri(self, uri: str) -> str:
        """Normalize URI for comparison."""
        if not uri:
            return ""
        uri = str(uri).strip().strip('"\'')
        
        # Handle namespace prefixes
        if ':' in uri and not uri.startswith('http'):
            prefix, local = uri.split(':', 1)
            if prefix == 'unit':
                uri = f'http://qudt.org/vocab/unit/{local}'
            elif prefix == 'qkdv':
                uri = f'http://qudt.org/vocab/quantitykind/{local}'
        
        return uri

# Also add debugging to the form builder's _create_unit_value_widget method:

    def _connect_signals(self):
        """Connect internal signals"""
        self.value_spinbox.valueChanged.connect(self.valueChanged.emit)
        self.value_spinbox.valueChanged.connect(self.dataChanged.emit)
        self.unit_combobox.currentTextChanged.connect(self.unitChanged.emit)
        self.unit_combobox.currentTextChanged.connect(self.dataChanged.emit)
    
    def getValue(self) -> float:
        """Get the current value"""
        return self.value_spinbox.value()
    
    def setValue(self, value: float):
        """Set the current value"""
        self.value_spinbox.setValue(value)
    
    def getUnit(self) -> str:
        """Get the current unit URI"""
        return self.unit_combobox.currentData() or ""
    
    def getUnitSymbol(self) -> str:
        """Get the current unit symbol"""
        return self.unit_combobox.currentText()
    
    def setUnit(self, unit_uri: str):
        """Set the current unit by URI"""
        for i in range(self.unit_combobox.count()):
            if self.unit_combobox.itemData(i) == unit_uri:
                self.unit_combobox.setCurrentIndex(i)
                break
    
    def setUnitBySymbol(self, unit_symbol: str):
        """Set the current unit by symbol"""
        for i in range(self.unit_combobox.count()):
            if self.unit_combobox.itemText(i) == unit_symbol:
                self.unit_combobox.setCurrentIndex(i)
                break
    
    def getData(self) -> Dict[str, Any]:
        """Get both value and unit as a dictionary"""
        return {
            'value': self.getValue(),
            'unit': self.getUnit(),
            'unit_symbol': self.getUnitSymbol()
        }
    
    def setData(self, data: Dict[str, Any]):
        """Set value and unit from dictionary"""
        if 'value' in data:
            self.setValue(data['value'])
        if 'unit' in data:
            self.setUnit(data['unit'])
        elif 'unit_symbol' in data:
            self.setUnitBySymbol(data['unit_symbol'])
    
    def clear(self):
        """Clear the widget"""
        self.value_spinbox.setValue(0.0)
        if self.unit_combobox.count() > 0:
            self.unit_combobox.setCurrentIndex(0)
    
    def setRange(self, minimum: float, maximum: float):
        """Set the range for the value spinbox"""
        self.value_spinbox.setMinimum(minimum)
        self.value_spinbox.setMaximum(maximum)
    
    def setDecimals(self, decimals: int):
        """Set the number of decimal places"""
        self.value_spinbox.setDecimals(decimals)
    
    def setSingleStep(self, step: float):
        """Set the single step for the spinbox"""
        self.value_spinbox.setSingleStep(step)
    
    def setReadOnly(self, read_only: bool):
        """Set read-only mode"""
        self.value_spinbox.setReadOnly(read_only)
        self.unit_combobox.setEnabled(not read_only)
    
    def isReadOnly(self) -> bool:
        """Check if widget is read-only"""
        return self.value_spinbox.isReadOnly()
    
    def setEnabled(self, enabled: bool):
        """Set enabled state"""
        super().setEnabled(enabled)
        self.value_spinbox.setEnabled(enabled)
        self.unit_combobox.setEnabled(enabled)