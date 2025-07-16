"""
Updated GUI Form Generator with SHACL Integration

File location: dynamat/gui/forms.py

This updated version integrates the SHACL shapes system with the existing
PyQt6 GUI components for automatic form generation and validation.
"""

import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from dataclasses import dataclass
from enum import Enum

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QLabel, QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox, QDateEdit,
    QPushButton, QGroupBox, QTextEdit, QFrame, QScrollArea, QCheckBox,
    QSizePolicy, QMessageBox, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QDate, QTimer
from PyQt6.QtGui import QFont, QPalette, QColor, QValidator

try:
    from ..ontology.manager import get_ontology_manager
    from ..ontology.shape_manager import get_shape_manager
    from ..ontology.validators import SHACLValidator
except ImportError:
    # Fallback for testing
    def get_ontology_manager():
        return None
    def get_shape_manager():
        return None
    def SHACLValidator():
        return None


class ValidationState(Enum):
    """Validation states for form fields"""
    VALID = "valid"
    INVALID = "invalid"
    PENDING = "pending"
    UNKNOWN = "unknown"


@dataclass
class FieldValidator:
    """Field validation configuration"""
    required: bool = False
    datatype: Optional[str] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    pattern: Optional[str] = None
    valid_values: List[str] = None
    custom_validator: Optional[Callable] = None


class DynamatFormWidget(QWidget):
    """
    Enhanced form widget with SHACL integration.
    
    This widget automatically generates forms from SHACL shapes or ontology
    structure and provides real-time validation feedback.
    """
    
    # Signals
    data_changed = pyqtSignal(dict)  # Emitted when form data changes
    validation_changed = pyqtSignal(bool, list)  # Emitted when validation state changes
    form_submitted = pyqtSignal(dict)  # Emitted when form is submitted
    
    def __init__(self, class_name: str, parent=None, use_shacl: bool = True):
        super().__init__(parent)
        
        self.class_name = class_name
        self.use_shacl = use_shacl
        
        # Managers
        self.ontology_manager = get_ontology_manager()
        self.shape_manager = get_shape_manager()
        self.validator = SHACLValidator()
        
        # Form state
        self.form_data = {}
        self.field_widgets = {}
        self.field_validators = {}
        self.validation_state = {}
        self.validation_errors = []
        
        # Validation timer (for delayed validation)
        self.validation_timer = QTimer()
        self.validation_timer.setSingleShot(True)
        self.validation_timer.timeout.connect(self._perform_validation)
        
        # Initialize UI
        self._setup_ui()
        self._load_form_schema()
        self._setup_validation()
    
    def _setup_ui(self):
        """Setup the basic UI structure"""
        
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)
        self.setLayout(main_layout)
        
        # Title
        title_label = QLabel(f"{self.class_name} Data Entry")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
                margin-bottom: 10px;
            }
        """)
        main_layout.addWidget(title_label)
        
        # Scrollable form area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameStyle(QFrame.Shape.NoFrame)
        
        self.form_widget = QWidget()
        self.form_layout = QVBoxLayout()
        self.form_widget.setLayout(self.form_layout)
        scroll_area.setWidget(self.form_widget)
        
        main_layout.addWidget(scroll_area)
        
        # Validation status
        self.validation_label = QLabel("Validation: Ready")
        self.validation_label.setStyleSheet("""
            QLabel {
                padding: 8px;
                background-color: #ecf0f1;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                font-weight: bold;
            }
        """)
        main_layout.addWidget(self.validation_label)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        self.validate_button = QPushButton("Validate")
        self.validate_button.clicked.connect(self.validate_now)
        button_layout.addWidget(self.validate_button)
        
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_form)
        button_layout.addWidget(self.clear_button)
        
        self.save_button = QPushButton("Save TTL")
        self.save_button.clicked.connect(self.save_ttl)
        button_layout.addWidget(self.save_button)
        
        button_layout.addStretch()
        main_layout.addLayout(button_layout)
    
    def _load_form_schema(self):
        """Load form schema from SHACL shapes or ontology"""
        
        if not self.ontology_manager:
            self._show_error("Ontology manager not available")
            return
        
        try:
            # Get form schema
            schema = self.ontology_manager.get_form_schema(self.class_name, use_shacl=self.use_shacl)
            
            if not schema or not schema.properties:
                self._show_error(f"No properties found for {self.class_name}")
                return
            
            # Create form fields
            self._create_form_fields(schema)
            
        except Exception as e:
            self._show_error(f"Failed to load form schema: {e}")
    
    def _create_form_fields(self, schema):
        """Create form fields from schema"""
        
        # Group properties by group
        grouped_properties = {}
        
        for prop in schema.properties:
            group = prop.get('group', 'default')
            if group not in grouped_properties:
                grouped_properties[group] = []
            grouped_properties[group].append(prop)
        
        # Create grouped sections
        for group_name, properties in grouped_properties.items():
            self._create_property_group(group_name, properties, schema.groups or {})
    
    def _create_property_group(self, group_name: str, properties: List[Dict], group_labels: Dict[str, str]):
        """Create a group of properties"""
        
        # Group box
        group_label = group_labels.get(group_name, group_name.title())
        group_box = QGroupBox(group_label)
        group_box.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #bdc3c7;
                border-radius: 6px;
                margin-top: 1ex;
                padding: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        # Form layout for this group
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft)
        group_box.setLayout(form_layout)
        
        # Sort properties by order
        properties.sort(key=lambda p: p.get('order', 999))
        
        # Create widgets for each property
        for prop in properties:
            widget, validator = self._create_property_widget(prop)
            if widget:
                label = self._create_property_label(prop)
                form_layout.addRow(label, widget)
                
                # Store widget and validator
                prop_name = prop['name']
                self.field_widgets[prop_name] = widget
                self.field_validators[prop_name] = validator
                
                # Connect signals
                self._connect_widget_signals(widget, prop_name)
        
        self.form_layout.addWidget(group_box)
    
    def _create_property_label(self, prop: Dict) -> QLabel:
        """Create label for property"""
        
        display_name = prop.get('display_name', prop['name'])
        
        # Add required indicator
        if prop.get('required', False):
            display_name += " *"
        
        label = QLabel(display_name)
        
        # Add description as tooltip
        if prop.get('description'):
            label.setToolTip(prop['description'])
        
        # Style required fields
        if prop.get('required', False):
            label.setStyleSheet("QLabel { font-weight: bold; color: #e74c3c; }")
        
        return label
    
    def _create_property_widget(self, prop: Dict) -> Tuple[Optional[QWidget], FieldValidator]:
        """Create appropriate widget for property"""
        
        prop_name = prop['name']
        widget_hint = prop.get('widget_hint', 'lineedit')
        datatype = prop.get('datatype', 'xsd:string')
        
        # Create validator
        validator = FieldValidator(
            required=prop.get('required', False),
            datatype=datatype,
            min_value=prop.get('min_value'),
            max_value=prop.get('max_value'),
            pattern=prop.get('pattern'),
            valid_values=prop.get('valid_values', [])
        )
        
        widget = None
        
        # Object properties (dropdowns)
        if prop.get('type') == 'object' or prop.get('valid_values'):
            widget = QComboBox()
            widget.setEditable(False)
            
            # Add empty option for non-required fields
            if not prop.get('required', False):
                widget.addItem("(Select...)", "")
            
            # Add valid values
            valid_values = prop.get('valid_values', [])
            for value in valid_values:
                widget.addItem(value, value)
        
        # Date properties
        elif 'date' in datatype.lower() or widget_hint == 'dateedit':
            widget = QDateEdit()
            widget.setDate(QDate.currentDate())
            widget.setCalendarPopup(True)
        
        # Numeric properties
        elif datatype in ['xsd:integer', 'xsd:int'] or widget_hint == 'spinbox':
            widget = QSpinBox()
            widget.setRange(
                int(prop.get('min_value', -999999)),
                int(prop.get('max_value', 999999))
            )
        
        elif datatype in ['xsd:double', 'xsd:float'] or widget_hint == 'doublespinbox':
            widget = QDoubleSpinBox()
            widget.setRange(
                float(prop.get('min_value', -999999.0)),
                float(prop.get('max_value', 999999.0))
            )
            widget.setDecimals(3)
        
        # Boolean properties
        elif datatype == 'xsd:boolean' or widget_hint == 'checkbox':
            widget = QCheckBox()
        
        # Large text properties
        elif widget_hint == 'textedit':
            widget = QTextEdit()
            widget.setMaximumHeight(100)
        
        # Default: line edit
        else:
            widget = QLineEdit()
            
            # Add pattern validation if available
            if prop.get('pattern'):
                # Could add QRegularExpressionValidator here
                pass
        
        # Apply common styling
        if widget:
            widget.setProperty('prop_name', prop_name)
            self._apply_widget_styling(widget)
        
        return widget, validator
    
    def _apply_widget_styling(self, widget: QWidget):
        """Apply consistent styling to form widgets"""
        
        style = """
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit {
            padding: 6px;
            border: 2px solid #bdc3c7;
            border-radius: 4px;
            font-size: 12px;
        }
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus {
            border-color: #3498db;
        }
        QTextEdit {
            border: 2px solid #bdc3c7;
            border-radius: 4px;
            font-size: 12px;
        }
        QTextEdit:focus {
            border-color: #3498db;
        }
        """
        
        widget.setStyleSheet(style)
    
    def _connect_widget_signals(self, widget: QWidget, prop_name: str):
        """Connect widget signals for data change tracking"""
        
        if isinstance(widget, QLineEdit):
            widget.textChanged.connect(lambda: self._on_field_changed(prop_name))
        elif isinstance(widget, QComboBox):
            widget.currentTextChanged.connect(lambda: self._on_field_changed(prop_name))
        elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            widget.valueChanged.connect(lambda: self._on_field_changed(prop_name))
        elif isinstance(widget, QDateEdit):
            widget.dateChanged.connect(lambda: self._on_field_changed(prop_name))
        elif isinstance(widget, QCheckBox):
            widget.toggled.connect(lambda: self._on_field_changed(prop_name))
        elif isinstance(widget, QTextEdit):
            widget.textChanged.connect(lambda: self._on_field_changed(prop_name))
    
    def _on_field_changed(self, prop_name: str):
        """Handle field value changes"""
        
        # Update form data
        widget = self.field_widgets[prop_name]
        value = self._get_widget_value(widget)
        self.form_data[prop_name] = value
        
        # Update validation state for this field
        self._validate_field(prop_name, value)
        
        # Schedule delayed full validation
        self.validation_timer.stop()
        self.validation_timer.start(500)  # 500ms delay
        
        # Emit data changed signal
        self.data_changed.emit(self.form_data.copy())
    
    def _get_widget_value(self, widget: QWidget) -> Any:
        """Get value from widget"""
        
        if isinstance(widget, QLineEdit):
            return widget.text().strip()
        elif isinstance(widget, QComboBox):
            return widget.currentData() or widget.currentText()
        elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            return widget.value()
        elif isinstance(widget, QDateEdit):
            return widget.date().toString(Qt.DateFormat.ISODate)
        elif isinstance(widget, QCheckBox):
            return widget.isChecked()
        elif isinstance(widget, QTextEdit):
            return widget.toPlainText().strip()
        else:
            return None
    
    def _validate_field(self, prop_name: str, value: Any) -> ValidationState:
        """Validate individual field"""
        
        validator = self.field_validators.get(prop_name)
        if not validator:
            return ValidationState.UNKNOWN
        
        errors = []
        
        # Required field check
        if validator.required and not value:
            errors.append("This field is required")
        
        # Valid values check
        if value and validator.valid_values and value not in validator.valid_values:
            errors.append(f"Must be one of: {', '.join(validator.valid_values)}")
        
        # Numeric range checks
        if value is not None and isinstance(value, (int, float)):
            if validator.min_value is not None and value < validator.min_value:
                errors.append(f"Must be >= {validator.min_value}")
            if validator.max_value is not None and value > validator.max_value:
                errors.append(f"Must be <= {validator.max_value}")
        
        # Pattern check (could be enhanced)
        if value and validator.pattern:
            import re
            if not re.match(validator.pattern, str(value)):
                errors.append("Invalid format")
        
        # Update field styling
        widget = self.field_widgets[prop_name]
        if errors:
            self._set_field_error_style(widget, errors)
            self.validation_state[prop_name] = ValidationState.INVALID
        else:
            self._set_field_valid_style(widget)
            self.validation_state[prop_name] = ValidationState.VALID
        
        return self.validation_state[prop_name]
    
    def _set_field_error_style(self, widget: QWidget, errors: List[str]):
        """Apply error styling to field"""
        
        error_style = """
        border: 2px solid #e74c3c !important;
        background-color: #fadbd8;
        """
        
        # Add to existing style
        current_style = widget.styleSheet()
        widget.setStyleSheet(current_style + error_style)
        widget.setToolTip("\n".join(errors))
    
    def _set_field_valid_style(self, widget: QWidget):
        """Apply valid styling to field"""
        
        # Remove error styling
        style = widget.styleSheet()
        # This is a simplified approach - could be more sophisticated
        style = style.replace("border: 2px solid #e74c3c !important;", "")
        style = style.replace("background-color: #fadbd8;", "")
        widget.setStyleSheet(style)
        widget.setToolTip("")
    
    def _setup_validation(self):
        """Setup validation system"""
        
        # Initialize validation state
        for prop_name in self.field_widgets.keys():
            self.validation_state[prop_name] = ValidationState.UNKNOWN
    
    def _perform_validation(self):
        """Perform full form validation"""
        
        if not self.ontology_manager:
            return
        
        try:
            # Validate using ontology manager
            result = self.ontology_manager.validate_form_data(self.class_name, self.form_data)
            
            is_valid = result.get('valid', False)
            errors = result.get('errors', [])
            warnings = result.get('warnings', [])
            
            self.validation_errors = errors
            
            # Update validation display
            self._update_validation_display(is_valid, errors, warnings)
            
            # Emit validation changed signal
            self.validation_changed.emit(is_valid, errors)
            
        except Exception as e:
            self._update_validation_display(False, [f"Validation error: {e}"], [])
    
    def _update_validation_display(self, is_valid: bool, errors: List[str], warnings: List[str]):
        """Update validation status display"""
        
        if is_valid and not warnings:
            self.validation_label.setText("Validation: ✓ All fields valid")
            self.validation_label.setStyleSheet("""
                QLabel {
                    padding: 8px;
                    background-color: #d5f4e6;
                    border: 1px solid #27ae60;
                    border-radius: 4px;
                    color: #27ae60;
                    font-weight: bold;
                }
            """)
        elif is_valid and warnings:
            self.validation_label.setText(f"Validation: ⚠ Valid with {len(warnings)} warning(s)")
            self.validation_label.setStyleSheet("""
                QLabel {
                    padding: 8px;
                    background-color: #fef9e7;
                    border: 1px solid #f39c12;
                    border-radius: 4px;
                    color: #f39c12;
                    font-weight: bold;
                }
            """)
        else:
            self.validation_label.setText(f"Validation: ✗ {len(errors)} error(s)")
            self.validation_label.setStyleSheet("""
                QLabel {
                    padding: 8px;
                    background-color: #fadbd8;
                    border: 1px solid #e74c3c;
                    border-radius: 4px;
                    color: #e74c3c;
                    font-weight: bold;
                }
            """)
        
        # Set tooltip with detailed information
        tooltip_lines = []
        if errors:
            tooltip_lines.append("Errors:")
            tooltip_lines.extend([f"  • {error}" for error in errors])
        if warnings:
            tooltip_lines.append("Warnings:")
            tooltip_lines.extend([f"  • {warning}" for warning in warnings])
        
        self.validation_label.setToolTip("\n".join(tooltip_lines))
    
    def _show_error(self, message: str):
        """Show error message"""
        
        error_label = QLabel(f"Error: {message}")
        error_label.setStyleSheet("QLabel { color: red; font-weight: bold; }")
        self.form_layout.addWidget(error_label)
    
    # Public interface methods
    
    def validate_now(self):
        """Trigger immediate validation"""
        self._perform_validation()
    
    def clear_form(self):
        """Clear all form fields"""
        
        for widget in self.field_widgets.values():
            if isinstance(widget, QLineEdit):
                widget.clear()
            elif isinstance(widget, QComboBox):
                widget.setCurrentIndex(0)
            elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                widget.setValue(0)
            elif isinstance(widget, QDateEdit):
                widget.setDate(QDate.currentDate())
            elif isinstance(widget, QCheckBox):
                widget.setChecked(False)
            elif isinstance(widget, QTextEdit):
                widget.clear()
        
        self.form_data.clear()
        self.validation_errors.clear()
        self._update_validation_display(True, [], [])
    
    def get_form_data(self) -> Dict[str, Any]:
        """Get current form data"""
        return self.form_data.copy()
    
    def set_form_data(self, data: Dict[str, Any]):
        """Set form data"""
        
        for prop_name, value in data.items():
            if prop_name in self.field_widgets:
                widget = self.field_widgets[prop_name]
                
                if isinstance(widget, QLineEdit):
                    widget.setText(str(value) if value else "")
                elif isinstance(widget, QComboBox):
                    index = widget.findData(value)
                    if index >= 0:
                        widget.setCurrentIndex(index)
                elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                    widget.setValue(value if value is not None else 0)
                elif isinstance(widget, QCheckBox):
                    widget.setChecked(bool(value))
                elif isinstance(widget, QTextEdit):
                    widget.setPlainText(str(value) if value else "")
        
        self.form_data.update(data)
        self._perform_validation()
    
    def is_valid(self) -> bool:
        """Check if form is currently valid"""
        return len(self.validation_errors) == 0
    
    def get_validation_errors(self) -> List[str]:
        """Get current validation errors"""
        return self.validation_errors.copy()
    
    def save_ttl(self):
        """Save form data as TTL (placeholder - implement based on your needs)"""
        
        if not self.is_valid():
            QMessageBox.warning(self, "Validation Error", 
                              "Please fix all validation errors before saving.")
            return
        
        # This would integrate with your TTL generation system
        self.form_submitted.emit(self.form_data.copy())


# Usage example
def create_specimen_form(parent=None) -> DynamatFormWidget:
    """Create a specimen data entry form"""
    return DynamatFormWidget("Specimen", parent=parent)


def create_test_form(parent=None) -> DynamatFormWidget:
    """Create a mechanical test form"""
    return DynamatFormWidget("MechanicalTest", parent=parent)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Test the form widget
    form = create_specimen_form()
    form.show()
    
    sys.exit(app.exec())