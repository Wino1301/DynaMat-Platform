"""
DynaMat Platform Forms Module

File location: dynamat/gui/forms.py

This module builds complete forms using the reusable widgets from widgets.py.
Provides automatic form generation from ontology schemas with integrated validation.

Key Features:
1. Automatic form generation from ontology schemas
2. Built-in validation and error handling
3. Data collection and export capabilities
4. Template support for common configurations
5. Clean integration with the ontology system
"""

import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, field

# Add the parent directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QGroupBox, QScrollArea, QPushButton, QLabel, QFrame, 
    QSplitter, QTabWidget, QMessageBox, QProgressBar,
    QSizePolicy, QSpacerItem
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QPalette

try:
    from dynamat.gui.widgets import (
        OntologyWidget, WidgetData, WidgetFactory, MeasurementWidget,
        OntologySelector, TextWidget, NumberWidget, DateWidget, BooleanWidget,
        IndividualDefinitionWidget, WidgetState, RequiredRule, RangeRule
    )
    from dynamat.ontology.manager import get_ontology_manager
except ImportError:
    # Fallback for direct execution
    from widgets import (
        OntologyWidget, WidgetData, WidgetFactory, MeasurementWidget,
        OntologySelector, TextWidget, NumberWidget, DateWidget, BooleanWidget,
        IndividualDefinitionWidget, WidgetState, RequiredRule, RangeRule
    )
    from dynamat.ontology.manager import get_ontology_manager


# =============================================================================
# FORM DATA STRUCTURES
# =============================================================================

@dataclass
class FormSection:
    """Represents a section of a form"""
    title: str
    widgets: List[OntologyWidget] = field(default_factory=list)
    layout_type: str = "form"  # "form", "grid", "horizontal"
    collapsible: bool = False
    expanded: bool = True


@dataclass
class FormData:
    """Complete form data structure"""
    class_name: str
    object_properties: Dict[str, Any] = field(default_factory=dict)
    measurement_properties: Dict[str, Dict] = field(default_factory=dict)
    data_properties: Dict[str, Any] = field(default_factory=dict)
    validation_errors: List[str] = field(default_factory=list)
    is_valid: bool = True


@dataclass
class FormTemplate:
    """Template for form configurations"""
    name: str
    class_name: str
    default_values: Dict[str, Any] = field(default_factory=dict)
    hidden_properties: List[str] = field(default_factory=list)
    required_properties: List[str] = field(default_factory=list)
    property_groups: Dict[str, List[str]] = field(default_factory=dict)


# =============================================================================
# ENHANCED FORM GENERATOR
# =============================================================================

class OntologyFormGenerator:
    """
    Form generator that creates complete forms from ontology schemas.
    Provides automatic widget creation with validation and template support.
    """
    
    def __init__(self, ontology_manager=None):
        self.ontology_manager = ontology_manager or get_ontology_manager()
        self.templates: Dict[str, FormTemplate] = {}
        self._load_default_templates()
    
    def _load_default_templates(self):
        """Load templates from ontology or external files"""
        # Templates are now loaded from ontology or TTL files
        # No hardcoded templates - this ensures we work with actual ontology structure
        pass
    
    def create_class_form(
        self, 
        class_name: str, 
        parent: QWidget = None,
        template_name: str = None,
        on_change_callback: Optional[Callable] = None,
        validation_callback: Optional[Callable] = None
    ) -> 'OntologyForm':
        """
        Create a complete form for an ontology class.
        
        Args:
            class_name: The ontology class to create form for
            parent: Parent widget
            template_name: Optional template to apply
            on_change_callback: Called when any value changes
            validation_callback: Called when validation state changes
            
        Returns:
            OntologyForm instance
        """
        form = OntologyForm(
            class_name=class_name,
            ontology_manager=self.ontology_manager,
            parent=parent
        )
        
        # Apply template if specified
        if template_name and template_name in self.templates:
            form.apply_template(self.templates[template_name])
        
        # Connect callbacks
        if on_change_callback:
            form.dataChanged.connect(on_change_callback)
        if validation_callback:
            form.validationChanged.connect(validation_callback)
        
        # Generate the form
        form.generate_form()
        
        return form
    
    def create_template_from_ontology(self, class_name: str, template_name: str = None) -> FormTemplate:
        """Create template by analyzing actual ontology properties"""
        schema = self.ontology_manager.get_class_schema(class_name)
        
        if not template_name:
            template_name = f"Auto-generated {class_name}"
        
        # Group properties by logical sections based on their characteristics
        property_groups = {}
        
        # Group object properties by their range classes
        for prop in schema.get('object_properties', []):
            range_class = prop.get('range_class', 'Other')
            
            if 'material' in range_class.lower():
                group_name = "Material Properties"
            elif 'structure' in range_class.lower():
                group_name = "Structure Properties"
            elif 'shape' in range_class.lower():
                group_name = "Shape Properties"
            elif 'user' in range_class.lower() or 'role' in range_class.lower():
                group_name = "Identification"
            else:
                group_name = "Relationships"
            
            if group_name not in property_groups:
                property_groups[group_name] = []
            property_groups[group_name].append(prop['name'])
        
        # Add measurement properties to their own group
        if schema.get('measurement_properties'):
            property_groups["Measurements"] = [prop['name'] for prop in schema['measurement_properties']]
        
        # Add data properties
        if schema.get('data_properties'):
            property_groups["Data Properties"] = [prop['name'] for prop in schema['data_properties']]
        
        # Remove empty groups
        property_groups = {k: v for k, v in property_groups.items() if v}
        
        return FormTemplate(
            name=template_name,
            class_name=class_name,
            property_groups=property_groups,
            required_properties=[],  # Could be determined from ontology constraints later
            default_values={}        # Could be loaded from template TTL files later
        )
    
    def analyze_template_coverage(self, template: FormTemplate) -> Dict[str, Any]:
        """Analyze how well a template covers the actual ontology properties"""
        schema = self.ontology_manager.get_class_schema(template.class_name)
        
        analysis = {
            'template_name': template.name,
            'class_name': template.class_name,
            'ontology_properties': {
                'object_properties': [prop['name'] for prop in schema.get('object_properties', [])],
                'measurement_properties': [prop['name'] for prop in schema.get('measurement_properties', [])],
                'data_properties': [prop['name'] for prop in schema.get('data_properties', [])]
            },
            'template_properties': [],
            'coverage': {
                'covered': [],
                'missing_from_template': [],
                'extra_in_template': []
            }
        }
        
        # Get all properties mentioned in template
        for group_props in template.property_groups.values():
            analysis['template_properties'].extend(group_props)
        
        # Flatten all ontology properties
        all_ontology_props = (
            analysis['ontology_properties']['object_properties'] +
            analysis['ontology_properties']['measurement_properties'] +
            analysis['ontology_properties']['data_properties']
        )
        
        # Analyze coverage
        analysis['coverage']['covered'] = [
            prop for prop in analysis['template_properties'] 
            if prop in all_ontology_props
        ]
        
        analysis['coverage']['missing_from_template'] = [
            prop for prop in all_ontology_props 
            if prop not in analysis['template_properties']
        ]
        
        analysis['coverage']['extra_in_template'] = [
            prop for prop in analysis['template_properties'] 
            if prop not in all_ontology_props
        ]
        
        return analysis
    
    def register_template(self, template: FormTemplate):
        """Register a new form template"""
        self.templates[template.name.lower().replace(" ", "_")] = template
    
    def load_template_from_ttl(self, ttl_file_path: Path) -> Optional[FormTemplate]:
        """Load template from TTL file - placeholder for future implementation"""
        # This will be implemented when we add TTL-based template storage
        # For now, just return None to indicate no template loaded
        return None
    
    def save_template_to_ttl(self, template: FormTemplate, ttl_file_path: Path) -> bool:
        """Save template to TTL file - placeholder for future implementation"""
        # This will be implemented when we add TTL-based template storage
        # For now, just return False to indicate save failed
        return False
    
    def get_available_templates(self, class_name: str = None) -> List[str]:
        """Get available templates, optionally filtered by class"""
        if class_name:
            return [name for name, template in self.templates.items() 
                   if template.class_name == class_name]
        return list(self.templates.keys())


# =============================================================================
# MAIN FORM CLASS
# =============================================================================

class OntologyForm(QWidget):
    """
    Main form class that combines multiple widgets into a complete form.
    Provides validation, templates, and data management capabilities.
    """
    
    # Signals
    dataChanged = pyqtSignal(FormData)
    validationChanged = pyqtSignal(bool, list)  # is_valid, error_messages
    formCompleted = pyqtSignal(FormData)
    
    def __init__(self, class_name: str, ontology_manager=None, parent=None):
        super().__init__(parent)
        
        self.class_name = class_name
        self.ontology_manager = ontology_manager or get_ontology_manager()
        self.template: Optional[FormTemplate] = None
        
        # Widget tracking
        self.widgets: Dict[str, OntologyWidget] = {}
        self.sections: List[FormSection] = []
        
        # Validation
        self.validation_timer = QTimer()
        self.validation_timer.setSingleShot(True)
        self.validation_timer.timeout.connect(self._validate_form)
        
        # Setup
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the main form UI structure"""
        self.main_layout = QVBoxLayout()
        self.main_layout.setSpacing(10)
        
        # Header
        self._create_header()
        
        # Scrollable content area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout()
        self.content_widget.setLayout(self.content_layout)
        
        self.scroll_area.setWidget(self.content_widget)
        self.main_layout.addWidget(self.scroll_area)
        
        # Footer with validation info
        self._create_footer()
        
        self.setLayout(self.main_layout)
    
    def _create_header(self):
        """Create form header with title and info"""
        header_frame = QFrame()
        header_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        header_layout = QHBoxLayout()
        
        # Title
        title = QLabel(f"{self.class_name} Form")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        header_layout.addWidget(title)
        
        # Template info
        self.template_label = QLabel("")
        self.template_label.setFont(QFont("Arial", 10))
        self.template_label.setStyleSheet("color: #666;")
        header_layout.addWidget(self.template_label)
        
        header_layout.addStretch()
        header_frame.setLayout(header_layout)
        self.main_layout.addWidget(header_frame)
    
    def _create_footer(self):
        """Create form footer with validation and controls"""
        footer_frame = QFrame()
        footer_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        footer_layout = QVBoxLayout()
        
        # Validation status
        self.validation_label = QLabel("Form validation: Ready")
        self.validation_label.setFont(QFont("Arial", 9))
        footer_layout.addWidget(self.validation_label)
        
        # Progress bar for validation
        self.validation_progress = QProgressBar()
        self.validation_progress.setVisible(False)
        self.validation_progress.setMaximum(0)  # Indeterminate
        footer_layout.addWidget(self.validation_progress)
        
        footer_frame.setLayout(footer_layout)
        self.main_layout.addWidget(footer_frame)
    
    def generate_form(self):
        """Generate the complete form based on class schema"""
        # Clear existing content
        self._clear_content()
        
        # Get schema from ontology
        schema = self.ontology_manager.get_class_schema(self.class_name)
        
        # Organize properties into sections
        if self.template and self.template.property_groups:
            self._generate_from_template(schema)
        else:
            self._generate_default_sections(schema)
        
        # Create widgets and layouts
        for section in self.sections:
            self._create_section_widget(section)
        
        # Setup validation
        self._setup_validation()
        
        # Apply template defaults
        if self.template:
            self._apply_template_defaults()
    
    def _clear_content(self):
        """Clear existing form content"""
        # Remove all widgets from content layout
        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Clear tracking
        self.widgets.clear()
        self.sections.clear()
    
    def _generate_from_template(self, schema: Dict):
        """Generate form sections based on template"""
        template_groups = self.template.property_groups
        used_properties = set()
        
        # Create sections for each template group
        for group_name, property_names in template_groups.items():
            section = FormSection(title=group_name)
            
            for prop_name in property_names:
                widget = self._create_widget_for_property(prop_name, schema)
                if widget:
                    section.widgets.append(widget)
                    self.widgets[prop_name] = widget
                    used_properties.add(prop_name)
            
            if section.widgets:  # Only add sections with widgets
                self.sections.append(section)
        
        # Add remaining properties to "Other" section
        remaining_props = self._get_all_property_names(schema) - used_properties
        if remaining_props:
            other_section = FormSection(title="Other Properties")
            for prop_name in remaining_props:
                widget = self._create_widget_for_property(prop_name, schema)
                if widget:
                    other_section.widgets.append(widget)
                    self.widgets[prop_name] = widget
            
            if other_section.widgets:
                self.sections.append(other_section)
    
    def _generate_default_sections(self, schema: Dict):
        """Generate default form sections when no template is used"""
        # Selection section (object properties)
        if schema.get('object_properties'):
            selection_section = FormSection(title="Selections")
            for prop in schema['object_properties']:
                widget = WidgetFactory.create_widget(prop, self)
                selection_section.widgets.append(widget)
                self.widgets[prop['name']] = widget
            self.sections.append(selection_section)
        
        # Measurements section
        if schema.get('measurement_properties'):
            measurement_section = FormSection(title="Measurements")
            for prop in schema['measurement_properties']:
                widget = WidgetFactory.create_widget(prop, self)
                measurement_section.widgets.append(widget)
                self.widgets[prop['name']] = widget
            self.sections.append(measurement_section)
        
        # Data properties section
        if schema.get('data_properties'):
            data_section = FormSection(title="Properties")
            for prop in schema['data_properties']:
                widget = WidgetFactory.create_widget(prop, self)
                data_section.widgets.append(widget)
                self.widgets[prop['name']] = widget
            self.sections.append(data_section)
    
    def _create_widget_for_property(self, prop_name: str, schema: Dict) -> Optional[OntologyWidget]:
        """Create widget for a specific property from schema"""
        # Search in all property types
        for prop_type in ['object_properties', 'measurement_properties', 'data_properties']:
            for prop in schema.get(prop_type, []):
                if prop['name'] == prop_name:
                    return WidgetFactory.create_widget(prop, self)
        return None
    
    def _get_all_property_names(self, schema: Dict) -> set:
        """Get all property names from schema"""
        names = set()
        for prop_type in ['object_properties', 'measurement_properties', 'data_properties']:
            for prop in schema.get(prop_type, []):
                names.add(prop['name'])
        return names
    
    def _create_section_widget(self, section: FormSection):
        """Create and add a section widget to the form"""
        group_box = QGroupBox(section.title)
        group_box.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        
        # Choose layout based on section configuration
        if section.layout_type == "grid":
            layout = QGridLayout()
            # Add widgets in grid pattern
            for i, widget in enumerate(section.widgets):
                row, col = divmod(i, 2)
                layout.addWidget(QLabel(widget.label_text), row, col * 2)
                layout.addWidget(widget, row, col * 2 + 1)
        elif section.layout_type == "horizontal":
            layout = QHBoxLayout()
            for widget in section.widgets:
                widget_layout = QVBoxLayout()
                widget_layout.addWidget(QLabel(widget.label_text))
                widget_layout.addWidget(widget)
                layout.addLayout(widget_layout)
        else:  # Default form layout
            layout = QFormLayout()
            for widget in section.widgets:
                layout.addRow(widget.label_text, widget)
        
        group_box.setLayout(layout)
        self.content_layout.addWidget(group_box)
    
    def _setup_validation(self):
        """Setup validation for all widgets"""
        for widget in self.widgets.values():
            widget.valueChanged.connect(self._on_widget_changed)
            
            # Add required validation if specified in template
            if (self.template and 
                widget.property_name in self.template.required_properties):
                widget.add_validation_rule(RequiredRule())
                widget.required = True
                widget.set_state(WidgetState.REQUIRED)
    
    def _apply_template_defaults(self):
        """Apply default values from template"""
        if not self.template or not self.template.default_values:
            return
        
        for prop_name, default_value in self.template.default_values.items():
            if prop_name in self.widgets:
                self.widgets[prop_name].set_value(default_value)
    
    def _on_widget_changed(self, widget_data: WidgetData):
        """Handle widget value changes"""
        # Debounce validation
        self.validation_timer.stop()
        self.validation_timer.start(500)  # Validate 500ms after last change
        
        # Emit data changed signal
        form_data = self.get_form_data()
        self.dataChanged.emit(form_data)
    
    def _validate_form(self):
        """Validate the entire form"""
        self.validation_progress.setVisible(True)
        
        errors = []
        all_valid = True
        
        for widget in self.widgets.values():
            is_valid, error_msg = widget.validate()
            if not is_valid:
                all_valid = False
                errors.append(f"{widget.label_text}: {error_msg}")
                widget.set_state(WidgetState.INVALID)
            else:
                widget.set_state(WidgetState.VALID if widget.required 
                               else WidgetState.NORMAL)
        
        # Update validation display
        if all_valid:
            self.validation_label.setText("Form validation: ✓ All fields valid")
            self.validation_label.setStyleSheet("color: green;")
        else:
            self.validation_label.setText(f"Form validation: ✗ {len(errors)} error(s)")
            self.validation_label.setStyleSheet("color: red;")
        
        self.validation_progress.setVisible(False)
        
        # Emit validation changed signal
        self.validationChanged.emit(all_valid, errors)
    
    def apply_template(self, template: FormTemplate):
        """Apply a form template"""
        self.template = template
        self.template_label.setText(f"Template: {template.name}")
        
        # Regenerate form if already created
        if self.widgets:
            self.generate_form()
    
    def get_form_data(self) -> FormData:
        """Get current form data"""
        form_data = FormData(class_name=self.class_name)
        
        for prop_name, widget in self.widgets.items():
            widget_data = widget.get_widget_data()
            
            if widget_data.widget_type == "measurement":
                form_data.measurement_properties[prop_name] = widget_data.value
            elif widget_data.widget_type == "selector":
                form_data.object_properties[prop_name] = widget_data.value
            else:
                form_data.data_properties[prop_name] = widget_data.value
        
        # Add validation info
        is_valid, errors = self._get_current_validation()
        form_data.is_valid = is_valid
        form_data.validation_errors = errors
        
        return form_data
    
    def set_form_data(self, form_data: FormData):
        """Set form data"""
        # Set object properties
        for prop_name, value in form_data.object_properties.items():
            if prop_name in self.widgets:
                self.widgets[prop_name].set_value(value)
        
        # Set measurement properties
        for prop_name, value in form_data.measurement_properties.items():
            if prop_name in self.widgets:
                self.widgets[prop_name].set_value(value)
        
        # Set data properties
        for prop_name, value in form_data.data_properties.items():
            if prop_name in self.widgets:
                self.widgets[prop_name].set_value(value)
    
    def _get_current_validation(self) -> tuple[bool, List[str]]:
        """Get current validation state"""
        errors = []
        all_valid = True
        
        for widget in self.widgets.values():
            is_valid, error_msg = widget.validate()
            if not is_valid:
                all_valid = False
                errors.append(f"{widget.label_text}: {error_msg}")
        
        return all_valid, errors
    
    def reset_form(self):
        """Reset form to default state"""
        for widget in self.widgets.values():
            widget.set_value(None)
            widget.set_state(WidgetState.NORMAL)
        
        self.validation_label.setText("Form validation: Ready")
        self.validation_label.setStyleSheet("")
    
    def export_data(self) -> Dict[str, Any]:
        """Export form data in a format suitable for TTL generation"""
        form_data = self.get_form_data()
        
        return {
            'class_name': form_data.class_name,
            'object_properties': form_data.object_properties,
            'measurement_properties': form_data.measurement_properties,
            'data_properties': form_data.data_properties,
            'validation_status': {
                'is_valid': form_data.is_valid,
                'errors': form_data.validation_errors
            }
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_specimen_form(parent: QWidget = None, template: str = "standard") -> OntologyForm:
    """Create a specimen form with optional template"""
    generator = OntologyFormGenerator()
    template_name = f"specimen_{template}" if template else None
    return generator.create_class_form("Specimen", parent, template_name)


def create_test_form(test_type: str, parent: QWidget = None) -> OntologyForm:
    """Create a test form for specific test type"""
    generator = OntologyFormGenerator()
    template_name = f"{test_type.lower()}_test" if test_type in ["SHPB", "QuasiStatic"] else None
    return generator.create_class_form(test_type, parent, template_name)


def create_scrollable_form(form: OntologyForm) -> QScrollArea:
    """Wrap a form in a scrollable area (if not already scrollable)"""
    if hasattr(form, 'scroll_area'):
        return form  # Form already has scrolling
    
    scroll = QScrollArea()
    scroll.setWidget(form)
    scroll.setWidgetResizable(True)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    return scroll


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication, QMainWindow
    import sys
    
    app = QApplication(sys.argv)
    
    # Create main window
    main_window = QMainWindow()
    main_window.setWindowTitle("DynaMat Enhanced Form Example")
    main_window.resize(800, 600)
    
    # Create form generator
    generator = OntologyFormGenerator()
    
    # Create specimen form with template
    def on_data_changed(form_data: FormData):
        print(f"Form data changed. Valid: {form_data.is_valid}")
        if not form_data.is_valid:
            print(f"Errors: {form_data.validation_errors}")
    
    def on_validation_changed(is_valid: bool, errors: List[str]):
        print(f"Validation changed. Valid: {is_valid}")
        if errors:
            print(f"Errors: {errors}")
    
    # Create and setup form
    specimen_form = generator.create_class_form(
        "Specimen",
        template_name="specimen_standard",
        on_change_callback=on_data_changed,
        validation_callback=on_validation_changed
    )
    
    main_window.setCentralWidget(specimen_form)
    main_window.show()
    
    sys.exit(app.exec())