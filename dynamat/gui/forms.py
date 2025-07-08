"""
PyQt6 Form Generator

This module belongs in dynamat/gui/ and handles the conversion of 
ontology schemas to PyQt6 widgets and forms.

Separates GUI concerns from ontology concerns.
"""

from typing import Dict, List, Any, Optional, Callable
from PyQt6.QtWidgets import (
    QWidget, QFormLayout, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QSpinBox, QDoubleSpinBox, 
    QComboBox, QCheckBox, QDateEdit, QTextEdit,
    QGroupBox, QPushButton, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal, QDate
from PyQt6.QtGui import QFont

from ..ontology.manager import get_ontology_manager


class MeasurementWidget(QWidget):
    """Widget combining SpinBox + Unit ComboBox for measurements"""
    
    valueChanged = pyqtSignal(str, float, str)  # name, value, unit
    
    def __init__(self, name: str, units: List[str], description: str = ""):
        super().__init__()
        self.name = name
        
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Value input
        self.value_spinbox = QDoubleSpinBox()
        self.value_spinbox.setRange(-999999.99, 999999.99)
        self.value_spinbox.setDecimals(3)
        self.value_spinbox.valueChanged.connect(self._emit_change)
        
        # Unit selector
        self.unit_combo = QComboBox()
        self.unit_combo.addItems(units)
        self.unit_combo.currentTextChanged.connect(self._emit_change)
        
        layout.addWidget(self.value_spinbox, 3)
        layout.addWidget(self.unit_combo, 1)
        
        self.setLayout(layout)
        
        if description:
            self.setToolTip(description)
    
    def _emit_change(self):
        """Emit change signal with current values"""
        self.valueChanged.emit(
            self.name,
            self.value_spinbox.value(),
            self.unit_combo.currentText()
        )
    
    def get_value(self) -> tuple:
        """Get current value and unit"""
        return self.value_spinbox.value(), self.unit_combo.currentText()
    
    def set_value(self, value: float, unit: str):
        """Set value and unit"""
        self.value_spinbox.setValue(value)
        unit_index = self.unit_combo.findText(unit)
        if unit_index >= 0:
            self.unit_combo.setCurrentIndex(unit_index)


class SelectorWidget(QComboBox):
    """Enhanced ComboBox for selecting ontology individuals"""
    
    def __init__(self, name: str, options: List[str], description: str = ""):
        super().__init__()
        self.name = name
        
        self.addItem("-- Select --", None)  # Default empty option
        for option in options:
            self.addItem(option, option)
        
        if description:
            self.setToolTip(description)
    
    def get_selected_value(self) -> Optional[str]:
        """Get selected value (None if default option selected)"""
        return self.currentData()


class OntologyFormGenerator:
    """
    Generates PyQt6 forms from ontology schemas.
    
    Converts the GUI-agnostic schemas from OntologyManager into
    actual PyQt6 widgets and layouts.
    """
    
    def __init__(self, ontology_manager=None):
        self.ontology_manager = ontology_manager or get_ontology_manager()
    
    def create_class_form(
        self, 
        class_name: str, 
        parent: QWidget = None,
        on_change_callback: Optional[Callable] = None
    ) -> QWidget:
        """
        Create a complete form for a class.
        
        Args:
            class_name: The ontology class to create form for
            parent: Parent widget
            on_change_callback: Function called when values change
            
        Returns:
            QWidget containing the complete form
        """
        if parent is None:
            parent = QWidget()
        
        # Get raw schema from ontology
        schema = self.ontology_manager.get_class_schema(class_name)
        
        main_layout = QVBoxLayout()
        
        # Create sections for different property types
        if schema['object_properties']:
            selection_group = self._create_selection_section(
                schema['object_properties'], on_change_callback
            )
            main_layout.addWidget(selection_group)
        
        if schema['measurement_properties']:
            measurement_group = self._create_measurement_section(
                schema['measurement_properties'], on_change_callback
            )
            main_layout.addWidget(measurement_group)
        
        if schema['data_properties']:
            data_group = self._create_data_section(
                schema['data_properties'], on_change_callback
            )
            main_layout.addWidget(data_group)
        
        parent.setLayout(main_layout)
        return parent
    
    def _create_selection_section(
        self, 
        object_properties: List[Dict], 
        on_change_callback: Optional[Callable]
    ) -> QGroupBox:
        """Create section for object property selections"""
        group = QGroupBox("Selections")
        layout = QFormLayout()
        
        for prop in object_properties:
            if prop['available_values']:  # Only create if has options
                selector = SelectorWidget(
                    name=prop['name'],
                    options=prop['available_values'],
                    description=prop['description']
                )
                
                if on_change_callback:
                    selector.currentTextChanged.connect(
                        lambda text, p=prop: on_change_callback('selector', p['name'], text)
                    )
                
                # Create label with description
                label = QLabel(self._format_property_name(prop['name']))
                if prop['description']:
                    label.setToolTip(prop['description'])
                
                layout.addRow(label, selector)
        
        group.setLayout(layout)
        return group
    
    def _create_measurement_section(
        self, 
        measurement_properties: List[Dict], 
        on_change_callback: Optional[Callable]
    ) -> QGroupBox:
        """Create section for measurement inputs"""
        group = QGroupBox("Measurements")
        layout = QFormLayout()
        
        for prop in measurement_properties:
            measurement_widget = MeasurementWidget(
                name=prop['name'],
                units=prop['available_units'],
                description=prop['description']
            )
            
            if on_change_callback:
                measurement_widget.valueChanged.connect(
                    lambda name, value, unit, p=prop: 
                    on_change_callback('measurement', name, {'value': value, 'unit': unit})
                )
            
            # Create label
            label = QLabel(self._format_property_name(prop['name']))
            if prop['description']:
                label.setToolTip(prop['description'])
            
            layout.addRow(label, measurement_widget)
        
        group.setLayout(layout)
        return group
    
    def _create_data_section(
        self, 
        data_properties: List[Dict], 
        on_change_callback: Optional[Callable]
    ) -> QGroupBox:
        """Create section for data property inputs"""
        group = QGroupBox("Properties")
        layout = QFormLayout()
        
        for prop in data_properties:
            widget = self._create_data_widget(prop)
            
            if on_change_callback and widget:
                self._connect_data_widget(widget, prop, on_change_callback)
            
            # Create label
            label = QLabel(self._format_property_name(prop['name']))
            if prop['description']:
                label.setToolTip(prop['description'])
            
            layout.addRow(label, widget)
        
        group.setLayout(layout)
        return group
    
    def _create_data_widget(self, prop: Dict) -> QWidget:
        """Create appropriate widget for data property"""
        data_type = prop['data_type'].lower()
        
        if 'float' in data_type or 'double' in data_type:
            widget = QDoubleSpinBox()
            widget.setRange(-999999.99, 999999.99)
            widget.setDecimals(3)
            return widget
        
        elif 'int' in data_type:
            widget = QSpinBox()
            widget.setRange(-999999, 999999)
            return widget
        
        elif 'bool' in data_type:
            return QCheckBox()
        
        elif 'date' in data_type:
            widget = QDateEdit()
            widget.setDate(QDate.currentDate())
            widget.setCalendarPopup(True)
            return widget
        
        else:  # Default to text
            return QLineEdit()
    
    def _connect_data_widget(self, widget: QWidget, prop: Dict, callback: Callable):
        """Connect appropriate signal for data widget"""
        if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            widget.valueChanged.connect(
                lambda value: callback('data', prop['name'], value)
            )
        elif isinstance(widget, QLineEdit):
            widget.textChanged.connect(
                lambda text: callback('data', prop['name'], text)
            )
        elif isinstance(widget, QCheckBox):
            widget.toggled.connect(
                lambda checked: callback('data', prop['name'], checked)
            )
        elif isinstance(widget, QDateEdit):
            widget.dateChanged.connect(
                lambda date: callback('data', prop['name'], date.toString(Qt.DateFormat.ISODate))
            )
    
    def _format_property_name(self, name: str) -> str:
        """Convert property name to readable label"""
        # Convert camelCase to words
        import re
        # Add space before capital letters
        formatted = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
        # Remove common prefixes
        formatted = formatted.replace('has ', '').replace('is ', '')
        return formatted.title()
    
    def create_specimen_form(self, parent: QWidget = None) -> QWidget:
        """Convenience method for specimen forms"""
        return self.create_class_form("Specimen", parent)
    
    def create_test_form(self, test_type: str, parent: QWidget = None) -> QWidget:
        """Convenience method for test forms"""
        return self.create_class_form(test_type, parent)
    
    def extract_form_data(self, form_widget: QWidget) -> Dict[str, Any]:
        """Extract all data from a generated form"""
        data = {
            'selectors': {},
            'measurements': {},
            'data_properties': {}
        }
        
        # Recursively find our custom widgets
        def find_widgets(widget):
            if isinstance(widget, SelectorWidget):
                value = widget.get_selected_value()
                if value is not None:
                    data['selectors'][widget.name] = value
            
            elif isinstance(widget, MeasurementWidget):
                value, unit = widget.get_value()
                data['measurements'][widget.name] = {'value': value, 'unit': unit}
            
            elif hasattr(widget, 'property_name'):  # Our data widgets
                # Extract value based on widget type
                if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                    data['data_properties'][widget.property_name] = widget.value()
                elif isinstance(widget, QLineEdit):
                    data['data_properties'][widget.property_name] = widget.text()
                elif isinstance(widget, QCheckBox):
                    data['data_properties'][widget.property_name] = widget.isChecked()
                elif isinstance(widget, QDateEdit):
                    data['data_properties'][widget.property_name] = widget.date().toString(Qt.DateFormat.ISODate)
            
            # Recurse through children
            for child in widget.findChildren(QWidget):
                find_widgets(child)
        
        find_widgets(form_widget)
        return data


# =============================================================================
# CONVENIENCE FUNCTIONS FOR GUI MODULE
# =============================================================================

def create_specimen_form(parent: QWidget = None, on_change: Callable = None) -> QWidget:
    """Create a specimen data entry form"""
    generator = OntologyFormGenerator()
    return generator.create_class_form("Specimen", parent, on_change)


def create_test_form(test_type: str, parent: QWidget = None, on_change: Callable = None) -> QWidget:
    """Create a test data entry form"""
    generator = OntologyFormGenerator()
    return generator.create_class_form(test_type, parent, on_change)


def create_scrollable_form(form_widget: QWidget) -> QScrollArea:
    """Wrap a form in a scrollable area"""
    scroll = QScrollArea()
    scroll.setWidget(form_widget)
    scroll.setWidgetResizable(True)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    return scroll


# =============================================================================
# EXAMPLE USAGE (for testing/documentation)
# =============================================================================

if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication, QMainWindow
    import sys
    
    app = QApplication(sys.argv)
    
    def on_form_change(widget_type: str, property_name: str, value: Any):
        print(f"Changed {widget_type}.{property_name} = {value}")
    
    # Create specimen form
    main_window = QMainWindow()
    specimen_form = create_specimen_form(on_change=on_form_change)
    scrollable_form = create_scrollable_form(specimen_form)
    
    main_window.setCentralWidget(scrollable_form)
    main_window.setWindowTitle("DynaMat Specimen Form")
    main_window.resize(600, 800)
    main_window.show()
    
    sys.exit(app.exec())