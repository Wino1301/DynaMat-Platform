"""
DynaMat Platform - Unit-Value Widget
Custom widget for entering dimensional values with units
"""

import logging
from typing import Dict, List, Optional, Any

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QDoubleSpinBox, QComboBox, QLabel
)
from PyQt6.QtCore import Qt, pyqtSignal

logger = logging.getLogger(__name__)


class UnitValueWidget(QWidget):
    """
    Custom widget for entering dimensional values with units.
    
    Combines a QDoubleSpinBox for the value with a QComboBox for the unit.
    """
    
    # Signals
    valueChanged = pyqtSignal(float)
    unitChanged = pyqtSignal(str)
    dataChanged = pyqtSignal()
    
    def __init__(self, default_unit: str = None, available_units: List[str] = None, parent=None):
        super().__init__(parent)
        
        self.default_unit = default_unit
        self.available_units = available_units or []
        
        self._setup_ui()
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
        layout.addWidget(self.value_spinbox, 1)  # Give more space to the value
        
        # Unit combobox
        self.unit_combobox = QComboBox()
        self.unit_combobox.setMinimumWidth(60)
        self.unit_combobox.setMaximumWidth(80)
        layout.addWidget(self.unit_combobox, 0)  # Fixed size for unit
        
        # Populate units
        self._populate_units()
    
    def _populate_units(self):
        """Populate the unit combobox"""
        self.unit_combobox.clear()
        
        if self.available_units:
            # Use provided units
            for unit in self.available_units:
                unit_symbol = self._extract_unit_symbol(unit)
                self.unit_combobox.addItem(unit_symbol, unit)
        else:
            # Default units based on default unit
            default_symbol = self._extract_unit_symbol(self.default_unit) if self.default_unit else "mm"
            
            # Add common units based on the default unit type
            if "length" in default_symbol.lower() or "mm" in default_symbol.lower() or "m" in default_symbol:
                self.unit_combobox.addItem("mm", "unit:MilliM")
                self.unit_combobox.addItem("cm", "unit:CentiM")  
                self.unit_combobox.addItem("m", "unit:M")
                self.unit_combobox.addItem("in", "unit:IN")
            elif "mass" in default_symbol.lower() or "g" in default_symbol:
                self.unit_combobox.addItem("g", "unit:GM")
                self.unit_combobox.addItem("kg", "unit:KiloGM")
                self.unit_combobox.addItem("mg", "unit:MilliGM")
            elif "area" in default_symbol.lower() or "²" in default_symbol:
                self.unit_combobox.addItem("mm²", "unit:MilliM2")
                self.unit_combobox.addItem("cm²", "unit:CentiM2")
                self.unit_combobox.addItem("m²", "unit:M2")
                self.unit_combobox.addItem("in²", "unit:IN2")
            else:
                # Generic unit
                self.unit_combobox.addItem(default_symbol, self.default_unit or "")
        
        # Set default unit if specified
        if self.default_unit:
            default_symbol = self._extract_unit_symbol(self.default_unit)
            for i in range(self.unit_combobox.count()):
                if self.unit_combobox.itemText(i) == default_symbol:
                    self.unit_combobox.setCurrentIndex(i)
                    break
    
    def _extract_unit_symbol(self, unit_uri: str) -> str:
        """Extract unit symbol from QUDT URI or unit string"""
        if not unit_uri:
            return "unit"
        
        # Handle QUDT URIs
        if "unit:" in unit_uri:
            unit_part = unit_uri.split("unit:")[-1]
            
            # Common unit mappings
            unit_mappings = {
                "MilliM": "mm", "MilliM2": "mm²", "MilliM3": "mm³",
                "CentiM": "cm", "CentiM2": "cm²", "CentiM3": "cm³",
                "M": "m", "M2": "m²", "M3": "m³",
                "IN": "in", "IN2": "in²", "IN3": "in³",
                "GM": "g", "KiloGM": "kg", "MilliGM": "mg",
                "PA": "Pa", "KiloPA": "kPa", "MegaPA": "MPa", "GigaPA": "GPa",
                "SEC": "s", "MIN": "min", "HR": "hr",
                "DEG_C": "°C", "DEG_F": "°F", "K": "K"
            }
            
            return unit_mappings.get(unit_part, unit_part.lower())
        
        # Handle direct unit symbols
        return unit_uri
    
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