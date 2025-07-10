"""
DynaMat Platform GUI Widgets Module

This module provides reusable PyQt6 widgets that integrate with the ontology system.
Each widget handles specific data patterns with built-in validation and standardized signals.

Core Design Principles:
1. Each widget handles one specific data pattern from the ontology
2. Widgets emit standardized signals for data integration
3. Support for validation and error states
4. Clean separation between widget logic and ontology integration
5. Reusable across different forms and contexts
"""

import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, Union, Tuple
from enum import Enum
from dataclasses import dataclass

# Add the parent directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QFormLayout, QGridLayout,
    QLabel, QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, 
    QCheckBox, QDateEdit, QTimeEdit, QDateTimeEdit, QTextEdit,
    QGroupBox, QPushButton, QFrame, QScrollArea, QSizePolicy,
    QCompleter, QToolTip, QApplication
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QDate, QTime, QDateTime, 
    QStringListModel, QTimer, QRegularExpression
)
from PyQt6.QtGui import (
    QFont, QPalette, QColor, QValidator, QRegularExpressionValidator,
    QDoubleValidator, QIntValidator
)

try:
    from dynamat.ontology.manager import get_ontology_manager
except ImportError:
    # Fallback for direct execution - this would need to be properly configured
    # based on your actual project structure
    def get_ontology_manager():
        return None


# =============================================================================
# DATA STRUCTURES AND ENUMS
# =============================================================================

class WidgetState(Enum):
    """Widget validation states"""
    NORMAL = "normal"
    VALID = "valid"
    INVALID = "invalid"
    REQUIRED = "required"
    DISABLED = "disabled"


@dataclass
class WidgetData:
    """Standardized data structure for widget values"""
    widget_type: str
    property_name: str
    value: Any
    unit: Optional[str] = None
    is_valid: bool = True
    metadata: Optional[Dict] = None


class ValidationRule:
    """Base class for widget validation rules"""
    def __init__(self, message: str = "Invalid value"):
        self.message = message
    
    def validate(self, value: Any) -> Tuple[bool, str]:
        """Return (is_valid, error_message)"""
        raise NotImplementedError


# =============================================================================
# BASE WIDGET CLASS
# =============================================================================

class OntologyWidget(QWidget):
    """
    Base class for all DynaMat ontology-integrated widgets.
    Provides common functionality and standardized interface.
    """
    
    # Standardized signals
    valueChanged = pyqtSignal(WidgetData)  # Emitted when value changes
    validationChanged = pyqtSignal(bool)   # Emitted when validation state changes
    focusChanged = pyqtSignal(bool)        # Emitted on focus in/out
    
    def __init__(self, property_name: str, label: str = None, 
                 description: str = None, required: bool = False, parent=None):
        super().__init__(parent)
        
        self.property_name = property_name
        self.label_text = label or property_name
        self.description = description
        self.required = required
        self.validation_rules: List[ValidationRule] = []
        self.current_state = WidgetState.NORMAL
        
        # Setup tooltip if description provided
        if self.description:
            self.setToolTip(self.description)
        
        self._setup_ui()
        self._setup_styling()
        self._connect_signals()
    
    def _setup_ui(self):
        """Setup the widget UI - to be implemented by subclasses"""
        pass
    
    def _setup_styling(self):
        """Setup widget styling based on current state"""
        self._update_style()
    
    def _connect_signals(self):
        """Connect internal signals - to be implemented by subclasses"""
        pass
    
    def add_validation_rule(self, rule: ValidationRule):
        """Add a validation rule to this widget"""
        self.validation_rules.append(rule)
    
    def validate(self) -> Tuple[bool, str]:
        """Validate current value against all rules"""
        current_value = self.get_value()
        
        for rule in self.validation_rules:
            is_valid, message = rule.validate(current_value)
            if not is_valid:
                return False, message
        
        return True, ""
    
    def set_state(self, state: WidgetState):
        """Set widget visual state"""
        self.current_state = state
        self._update_style()
    
    def _update_style(self):
        """Update widget styling based on current state"""
        colors = {
            WidgetState.NORMAL: "#ffffff",
            WidgetState.VALID: "#e8f5e8",
            WidgetState.INVALID: "#ffe8e8",
            WidgetState.REQUIRED: "#fff8e1",
            WidgetState.DISABLED: "#f5f5f5"
        }
        
        color = colors.get(self.current_state, colors[WidgetState.NORMAL])
        self.setStyleSheet(f"background-color: {color};")
    
    def get_value(self) -> Any:
        """Get current widget value - to be implemented by subclasses"""
        raise NotImplementedError
    
    def set_value(self, value: Any):
        """Set widget value - to be implemented by subclasses"""
        raise NotImplementedError
    
    def get_widget_data(self) -> WidgetData:
        """Get standardized widget data"""
        is_valid, _ = self.validate()
        return WidgetData(
            widget_type=self.__class__.__name__,
            property_name=self.property_name,
            value=self.get_value(),
            is_valid=is_valid
        )
    
    def _emit_value_changed(self):
        """Emit value changed signal with standardized data"""
        self.valueChanged.emit(self.get_widget_data())


# =============================================================================
# MEASUREMENT WIDGETS (Value + Unit pairs)
# =============================================================================

class MeasurementWidget(OntologyWidget):
    """
    Measurement widget for value + unit pairs.
    Combines numeric input with unit selection in a single interface.
    """
    
    def __init__(self, property_name: str, units: List[str], 
                 label: str = None, description: str = None,
                 value_range: Tuple[float, float] = (-999999.99, 999999.99),
                 decimals: int = 3, default_unit: str = None, **kwargs):
        
        self.units = units
        self.value_range = value_range
        self.decimals = decimals
        self.default_unit = default_unit or (units[0] if units else "")
        
        super().__init__(property_name, label, description, **kwargs)
    
    def _setup_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # Value input with validation
        self.value_spinbox = QDoubleSpinBox()
        self.value_spinbox.setRange(*self.value_range)
        self.value_spinbox.setDecimals(self.decimals)
        self.value_spinbox.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        # Unit selector with search capability
        self.unit_combo = QComboBox()
        self.unit_combo.addItems(self.units)
        self.unit_combo.setEditable(True)  # Allow typing to search
        self.unit_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.unit_combo.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        
        # Set default unit
        if self.default_unit and self.default_unit in self.units:
            self.unit_combo.setCurrentText(self.default_unit)
        
        # Add completer for unit search
        if self.units:
            completer = QCompleter(self.units)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            self.unit_combo.setCompleter(completer)
        
        layout.addWidget(self.value_spinbox, 3)
        layout.addWidget(self.unit_combo, 1)
        
        self.setLayout(layout)
    
    def _connect_signals(self):
        self.value_spinbox.valueChanged.connect(self._emit_value_changed)
        self.unit_combo.currentTextChanged.connect(self._emit_value_changed)
    
    def get_value(self) -> Dict[str, Union[float, str]]:
        return {
            'value': self.value_spinbox.value(),
            'unit': self.unit_combo.currentText()
        }
    
    def set_value(self, value: Union[Dict, Tuple, float]):
        if isinstance(value, dict):
            self.value_spinbox.setValue(value.get('value', 0.0))
            unit = value.get('unit', self.default_unit)
            if unit in self.units:
                self.unit_combo.setCurrentText(unit)
        elif isinstance(value, (tuple, list)) and len(value) >= 2:
            self.value_spinbox.setValue(float(value[0]))
            if str(value[1]) in self.units:
                self.unit_combo.setCurrentText(str(value[1]))
        else:
            self.value_spinbox.setValue(float(value))
    
    def get_widget_data(self) -> WidgetData:
        is_valid, _ = self.validate()
        return WidgetData(
            widget_type="measurement",
            property_name=self.property_name,
            value=self.get_value(),
            is_valid=is_valid
        )


# =============================================================================
# SELECTOR WIDGETS (Ontology individual selection)
# =============================================================================

class OntologySelector(OntologyWidget):
    """
    Selector for ontology individuals with search and filtering capabilities.
    Provides dropdown selection with autocomplete for ontology-defined options.
    """
    
    def __init__(self, property_name: str, range_class: str = None,
                 options: List[str] = None, label: str = None, 
                 description: str = None, allow_custom: bool = False,
                 **kwargs):
        
        self.range_class = range_class
        self.allow_custom = allow_custom
        self._options = options or []
        
        # Load options from ontology if range_class provided
        if range_class and not options:
            manager = get_ontology_manager()
            individuals = manager.get_individuals(range_class)
            self._options = list(individuals.keys())
        
        super().__init__(property_name, label, description, **kwargs)
    
    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.combo_box = QComboBox()
        self.combo_box.setEditable(self.allow_custom)
        self.combo_box.setInsertPolicy(QComboBox.InsertPolicy.NoInsert if not self.allow_custom 
                                      else QComboBox.InsertPolicy.InsertAtBottom)
        
        # Add empty selection option
        self.combo_box.addItem("-- Select --", None)
        
        # Add options
        for option in self._options:
            self.combo_box.addItem(option, option)
        
        # Add search capability
        if self._options:
            completer = QCompleter(self._options)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            self.combo_box.setCompleter(completer)
        
        layout.addWidget(self.combo_box)
        self.setLayout(layout)
    
    def _connect_signals(self):
        self.combo_box.currentTextChanged.connect(self._emit_value_changed)
    
    def get_value(self) -> Optional[str]:
        current_data = self.combo_box.currentData()
        return current_data if current_data is not None else None
    
    def set_value(self, value: str):
        if value:
            index = self.combo_box.findData(value)
            if index >= 0:
                self.combo_box.setCurrentIndex(index)
            elif self.allow_custom:
                self.combo_box.addItem(value, value)
                self.combo_box.setCurrentText(value)
    
    def refresh_options(self):
        """Refresh options from ontology"""
        if self.range_class:
            manager = get_ontology_manager()
            individuals = manager.get_individuals(self.range_class)
            new_options = list(individuals.keys())
            
            # Update combo box
            current_value = self.get_value()
            self.combo_box.clear()
            self.combo_box.addItem("-- Select --", None)
            
            for option in new_options:
                self.combo_box.addItem(option, option)
            
            # Restore previous selection if still valid
            if current_value and current_value in new_options:
                self.set_value(current_value)
            
            self._options = new_options
    
    def get_widget_data(self) -> WidgetData:
        is_valid, _ = self.validate()
        return WidgetData(
            widget_type="selector",
            property_name=self.property_name,
            value=self.get_value(),
            is_valid=is_valid,
            metadata={'range_class': self.range_class}
        )


# =============================================================================
# DATA PROPERTY WIDGETS (Simple literal values)
# =============================================================================

class TextWidget(OntologyWidget):
    """Widget for text/string properties"""
    
    def __init__(self, property_name: str, label: str = None,
                 description: str = None, max_length: int = None,
                 placeholder: str = None, multiline: bool = False, **kwargs):
        
        self.max_length = max_length
        self.placeholder = placeholder
        self.multiline = multiline
        
        super().__init__(property_name, label, description, **kwargs)
    
    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        if self.multiline:
            self.text_edit = QTextEdit()
            self.text_edit.setMaximumHeight(100)  # Reasonable default
            if self.placeholder:
                self.text_edit.setPlaceholderText(self.placeholder)
            layout.addWidget(self.text_edit)
        else:
            self.line_edit = QLineEdit()
            if self.max_length:
                self.line_edit.setMaxLength(self.max_length)
            if self.placeholder:
                self.line_edit.setPlaceholderText(self.placeholder)
            layout.addWidget(self.line_edit)
        
        self.setLayout(layout)
    
    def _connect_signals(self):
        if self.multiline:
            self.text_edit.textChanged.connect(self._emit_value_changed)
        else:
            self.line_edit.textChanged.connect(self._emit_value_changed)
    
    def get_value(self) -> str:
        if self.multiline:
            return self.text_edit.toPlainText()
        else:
            return self.line_edit.text()
    
    def set_value(self, value: str):
        value = str(value) if value is not None else ""
        if self.multiline:
            self.text_edit.setPlainText(value)
        else:
            self.line_edit.setText(value)


class NumberWidget(OntologyWidget):
    """Widget for numeric properties (int or float)"""
    
    def __init__(self, property_name: str, label: str = None,
                 description: str = None, data_type: str = "float",
                 value_range: Tuple[float, float] = (-999999, 999999),
                 decimals: int = 2, **kwargs):
        
        self.data_type = data_type
        self.value_range = value_range
        self.decimals = decimals
        
        super().__init__(property_name, label, description, **kwargs)
    
    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        if self.data_type == "int":
            self.spin_box = QSpinBox()
            self.spin_box.setRange(int(self.value_range[0]), int(self.value_range[1]))
        else:
            self.spin_box = QDoubleSpinBox()
            self.spin_box.setRange(*self.value_range)
            self.spin_box.setDecimals(self.decimals)
        
        layout.addWidget(self.spin_box)
        self.setLayout(layout)
    
    def _connect_signals(self):
        self.spin_box.valueChanged.connect(self._emit_value_changed)
    
    def get_value(self) -> Union[int, float]:
        return self.spin_box.value()
    
    def set_value(self, value: Union[int, float]):
        if value is not None:
            self.spin_box.setValue(float(value))


class DateWidget(OntologyWidget):
    """Widget for date properties"""
    
    def __init__(self, property_name: str, label: str = None,
                 description: str = None, include_time: bool = False, **kwargs):
        
        self.include_time = include_time
        super().__init__(property_name, label, description, **kwargs)
    
    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        if self.include_time:
            self.date_edit = QDateTimeEdit()
            self.date_edit.setDateTime(QDateTime.currentDateTime())
        else:
            self.date_edit = QDateEdit()
            self.date_edit.setDate(QDate.currentDate())
        
        self.date_edit.setCalendarPopup(True)
        layout.addWidget(self.date_edit)
        self.setLayout(layout)
    
    def _connect_signals(self):
        if self.include_time:
            self.date_edit.dateTimeChanged.connect(self._emit_value_changed)
        else:
            self.date_edit.dateChanged.connect(self._emit_value_changed)
    
    def get_value(self) -> str:
        if self.include_time:
            return self.date_edit.dateTime().toString(Qt.DateFormat.ISODate)
        else:
            return self.date_edit.date().toString(Qt.DateFormat.ISODate)
    
    def set_value(self, value: str):
        if value:
            if self.include_time:
                dt = QDateTime.fromString(value, Qt.DateFormat.ISODate)
                if dt.isValid():
                    self.date_edit.setDateTime(dt)
            else:
                date = QDate.fromString(value, Qt.DateFormat.ISODate)
                if date.isValid():
                    self.date_edit.setDate(date)


class BooleanWidget(OntologyWidget):
    """Widget for boolean properties"""
    
    def __init__(self, property_name: str, label: str = None,
                 description: str = None, **kwargs):
        super().__init__(property_name, label, description, **kwargs)
    
    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.checkbox = QCheckBox(self.label_text)
        layout.addWidget(self.checkbox)
        self.setLayout(layout)
    
    def _connect_signals(self):
        self.checkbox.toggled.connect(self._emit_value_changed)
    
    def get_value(self) -> bool:
        return self.checkbox.isChecked()
    
    def set_value(self, value: bool):
        self.checkbox.setChecked(bool(value))


# =============================================================================
# COMPOSITE WIDGETS (Complex patterns)
# =============================================================================

class IndividualDefinitionWidget(OntologyWidget):
    """
    Widget for defining new ontology individuals with their properties.
    Useful for creating new materials, equipment configs, etc.
    """
    
    def __init__(self, property_name: str, target_class: str,
                 label: str = None, description: str = None, **kwargs):
        
        self.target_class = target_class
        self.property_widgets = {}
        
        super().__init__(property_name, label, description, **kwargs)
    
    def _setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Header with class name
        header = QLabel(f"Define New {self.target_class}")
        header.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        main_layout.addWidget(header)
        
        # Scroll area for properties
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(200)
        
        properties_widget = QWidget()
        self.properties_layout = QFormLayout()
        
        # Load class schema and create property widgets
        manager = get_ontology_manager()
        schema = manager.get_class_schema(self.target_class)
        
        # Create widgets for each property type
        for prop in schema.get('data_properties', []):
            widget = self._create_property_widget(prop)
            if widget:
                self.property_widgets[prop['name']] = widget
                self.properties_layout.addRow(prop['name'], widget)
        
        for prop in schema.get('measurement_properties', []):
            widget = MeasurementWidget(
                property_name=prop['name'],
                units=prop['available_units'],
                label=prop['name'],
                description=prop.get('description', '')
            )
            self.property_widgets[prop['name']] = widget
            self.properties_layout.addRow(prop['name'], widget)
        
        properties_widget.setLayout(self.properties_layout)
        scroll.setWidget(properties_widget)
        main_layout.addWidget(scroll)
        
        self.setLayout(main_layout)
    
    def _create_property_widget(self, prop: Dict) -> Optional[OntologyWidget]:
        """Create appropriate widget for a property"""
        prop_name = prop['name']
        data_type = prop.get('data_type', 'string')
        
        if data_type == 'boolean':
            return BooleanWidget(prop_name, prop_name, prop.get('description'))
        elif data_type in ['int', 'float']:
            return NumberWidget(prop_name, prop_name, prop.get('description'), data_type)
        elif data_type == 'date':
            return DateWidget(prop_name, prop_name, prop.get('description'))
        else:
            return TextWidget(prop_name, prop_name, prop.get('description'))
    
    def _connect_signals(self):
        # Connect all property widget signals
        for widget in self.property_widgets.values():
            widget.valueChanged.connect(self._emit_value_changed)
    
    def get_value(self) -> Dict[str, Any]:
        """Get all property values as a dictionary"""
        return {
            name: widget.get_value() 
            for name, widget in self.property_widgets.items()
        }
    
    def set_value(self, value: Dict[str, Any]):
        """Set property values from dictionary"""
        if isinstance(value, dict):
            for name, widget in self.property_widgets.items():
                if name in value:
                    widget.set_value(value[name])


# =============================================================================
# WIDGET FACTORY
# =============================================================================

class WidgetFactory:
    """Factory for creating appropriate widgets based on ontology schemas"""
    
    @staticmethod
    def create_widget(property_info: Dict, parent=None) -> OntologyWidget:
        """
        Create appropriate widget based on property information from ontology schema.
        
        Args:
            property_info: Property info dict from OntologyManager.get_class_schema()
            parent: Parent widget
            
        Returns:
            Appropriate OntologyWidget subclass
        """
        prop_name = property_info['name']
        
        # Measurement properties (value + unit)
        if 'available_units' in property_info:
            return MeasurementWidget(
                property_name=prop_name,
                units=property_info['available_units'],
                label=prop_name,
                description=property_info.get('description', ''),
                parent=parent
            )
        
        # Object properties (selectors)
        elif 'range_class' in property_info:
            return OntologySelector(
                property_name=prop_name,
                range_class=property_info['range_class'],
                options=property_info.get('available_values', []),
                label=prop_name,
                description=property_info.get('description', ''),
                parent=parent
            )
        
        # Data properties
        else:
            data_type = property_info.get('data_type', 'string')
            
            if data_type == 'boolean':
                return BooleanWidget(prop_name, prop_name, 
                                   property_info.get('description', ''), parent=parent)
            elif data_type in ['int', 'float']:
                return NumberWidget(prop_name, prop_name, 
                                  property_info.get('description', ''), 
                                  data_type=data_type, parent=parent)
            elif data_type == 'date':
                return DateWidget(prop_name, prop_name, 
                                property_info.get('description', ''), parent=parent)
            else:
                return TextWidget(prop_name, prop_name, 
                                property_info.get('description', ''), parent=parent)


# =============================================================================
# VALIDATION RULES
# =============================================================================

class RequiredRule(ValidationRule):
    """Validation rule for required fields"""
    def __init__(self):
        super().__init__("This field is required")
    
    def validate(self, value: Any) -> Tuple[bool, str]:
        if value is None or value == "" or value == []:
            return False, self.message
        return True, ""


class RangeRule(ValidationRule):
    """Validation rule for numeric ranges"""
    def __init__(self, min_val: float = None, max_val: float = None):
        self.min_val = min_val
        self.max_val = max_val
        super().__init__(f"Value must be between {min_val} and {max_val}")
    
    def validate(self, value: Any) -> Tuple[bool, str]:
        try:
            num_val = float(value)
            if self.min_val is not None and num_val < self.min_val:
                return False, f"Value must be at least {self.min_val}"
            if self.max_val is not None and num_val > self.max_val:
                return False, f"Value must be at most {self.max_val}"
            return True, ""
        except (ValueError, TypeError):
            return False, "Value must be a number"


# =============================================================================
# USAGE EXAMPLE (for testing/documentation)
# =============================================================================

if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
    import sys
    
    app = QApplication(sys.argv)
    
    # Example usage
    main_window = QMainWindow()
    central_widget = QWidget()
    layout = QVBoxLayout()
    
    # Create various widgets
    measurement = MeasurementWidget("length", ["mm", "inch", "m"], "Length")
    selector = OntologySelector("material", "Material", ["Al6061", "SS316"], "Material")
    text = TextWidget("name", "Name", "Enter specimen name")
    number = NumberWidget("count", "Count", "Number of specimens", "int")
    date = DateWidget("test_date", "Test Date", "Date of testing")
    boolean = BooleanWidget("active", "Active", "Is specimen active")
    
    # Add validation
    measurement.add_validation_rule(RequiredRule())
    measurement.add_validation_rule(RangeRule(0, 1000))
    
    # Connect signals
    def on_value_changed(data: WidgetData):
        print(f"Widget {data.widget_type}.{data.property_name} changed to: {data.value}")
    
    for widget in [measurement, selector, text, number, date, boolean]:
        widget.valueChanged.connect(on_value_changed)
        layout.addWidget(widget)
    
    central_widget.setLayout(layout)
    main_window.setCentralWidget(central_widget)
    main_window.setWindowTitle("DynaMat Widget Examples")
    main_window.resize(400, 600)
    main_window.show()
    
    sys.exit(app.exec())