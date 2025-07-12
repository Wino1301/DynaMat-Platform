"""
SHACL-Based Dynamic Form Generator

File location: dynamat/gui/shacl_forms.py

This module uses SHACL shapes to automatically generate forms from ontology definitions.
This approach is completely data-driven and automatically adapts to changes in the ontology.

Key Benefits:
1. No hardcoded form structures
2. Automatic updates when ontology changes
3. Built-in validation from SHACL constraints
4. Consistent with semantic web standards
"""

import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum

# Add the parent directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QLabel, QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox, QDateEdit,
    QPushButton, QGroupBox, QTextEdit, QFrame, QScrollArea, QCheckBox,
    QSizePolicy, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QDate
from PyQt6.QtGui import QFont, QPalette, QColor

try:
    from rdflib import Graph, Namespace, URIRef, Literal
    from rdflib.namespace import RDF, RDFS, OWL, SH
    from dynamat.ontology.manager import get_ontology_manager
except ImportError:
    # Fallback for testing
    def get_ontology_manager():
        return None
    
    # Mock classes for testing
    class Graph:
        pass
    class Namespace:
        pass
    class SH:
        pass


@dataclass
class SHACLProperty:
    """SHACL property constraint information"""
    path: str
    name: str
    display_name: str
    datatype: Optional[str] = None
    node_kind: Optional[str] = None
    class_constraint: Optional[str] = None
    min_count: Optional[int] = None
    max_count: Optional[int] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    pattern: Optional[str] = None
    description: Optional[str] = None
    group: Optional[str] = None
    order: Optional[int] = None
    valid_values: List[str] = None


@dataclass
class SHACLShape:
    """SHACL shape information"""
    target_class: str
    shape_uri: str
    label: str
    description: Optional[str] = None
    properties: List[SHACLProperty] = None
    groups: Dict[str, str] = None  # group_uri -> group_label


class SHACLFormGenerator:
    """
    Generate forms automatically from SHACL shapes.
    
    This class reads SHACL shapes from the ontology and generates
    corresponding GUI forms with proper validation and constraints.
    """
    
    def __init__(self, ontology_manager=None):
        self.ontology_manager = ontology_manager or get_ontology_manager()
        self.shapes_cache = {}
        
        # SHACL namespace
        self.sh = SH
        
        # Load SHACL shapes if available
        self._load_shapes()
    
    def _load_shapes(self):
        """Load SHACL shapes from the ontology"""
        
        if not self.ontology_manager or not hasattr(self.ontology_manager, 'graph'):
            return
        
        try:
            # Try to load shapes file if it exists
            shapes_path = Path(self.ontology_manager.ontology_path).parent.parent / "shapes"
            
            if shapes_path.exists():
                for shape_file in shapes_path.glob("*.ttl"):
                    self.ontology_manager.graph.parse(str(shape_file), format="turtle")
            
        except Exception as e:
            print(f"Could not load SHACL shapes: {e}")
    
    def get_shape_for_class(self, class_name: str) -> Optional[SHACLShape]:
        """Get SHACL shape for a specific class"""
        
        if class_name in self.shapes_cache:
            return self.shapes_cache[class_name]
        
        if not self.ontology_manager:
            return None
        
        try:
            # Query for shapes targeting this class
            class_uri = f"{self.ontology_manager.dyn}{class_name}"
            
            shape_query = f"""
            SELECT ?shape ?label ?description WHERE {{
                ?shape rdf:type sh:NodeShape .
                ?shape sh:targetClass <{class_uri}> .
                OPTIONAL {{ ?shape rdfs:label ?label }}
                OPTIONAL {{ ?shape rdfs:comment ?description }}
            }}
            """
            
            shape_results = list(self.ontology_manager.graph.query(shape_query))
            
            if not shape_results:
                # No explicit SHACL shape found - generate from ontology structure
                return self._generate_shape_from_ontology(class_name)
            
            # Process the first shape found
            shape_result = shape_results[0]
            shape_uri = str(shape_result.shape)
            
            # Get shape properties
            properties = self._get_shape_properties(shape_uri)
            
            # Get property groups
            groups = self._get_property_groups(shape_uri)
            
            shape = SHACLShape(
                target_class=class_name,
                shape_uri=shape_uri,
                label=str(shape_result.label) if shape_result.label else class_name,
                description=str(shape_result.description) if shape_result.description else None,
                properties=properties,
                groups=groups
            )
            
            self.shapes_cache[class_name] = shape
            return shape
            
        except Exception as e:
            print(f"Error getting SHACL shape for {class_name}: {e}")
            # Fallback to ontology-based generation
            return self._generate_shape_from_ontology(class_name)
    
    def _get_shape_properties(self, shape_uri: str) -> List[SHACLProperty]:
        """Get properties defined in a SHACL shape"""
        
        properties = []
        
        # Query for property shapes
        prop_query = f"""
        SELECT ?propShape ?path ?datatype ?nodeKind ?class ?minCount ?maxCount 
               ?minValue ?maxValue ?pattern ?name ?description ?group ?order WHERE {{
            <{shape_uri}> sh:property ?propShape .
            ?propShape sh:path ?path .
            
            OPTIONAL {{ ?propShape sh:datatype ?datatype }}
            OPTIONAL {{ ?propShape sh:nodeKind ?nodeKind }}
            OPTIONAL {{ ?propShape sh:class ?class }}
            OPTIONAL {{ ?propShape sh:minCount ?minCount }}
            OPTIONAL {{ ?propShape sh:maxCount ?maxCount }}
            OPTIONAL {{ ?propShape sh:minInclusive ?minValue }}
            OPTIONAL {{ ?propShape sh:maxInclusive ?maxValue }}
            OPTIONAL {{ ?propShape sh:pattern ?pattern }}
            OPTIONAL {{ ?propShape sh:name ?name }}
            OPTIONAL {{ ?propShape sh:description ?description }}
            OPTIONAL {{ ?propShape sh:group ?group }}
            OPTIONAL {{ ?propShape sh:order ?order }}
        }}
        ORDER BY ?order
        """
        
        for row in self.ontology_manager.graph.query(prop_query):
            path_uri = str(row.path)
            path_name = self.ontology_manager._extract_name_from_uri(path_uri)
            
            # Get display name
            display_name = str(row.name) if row.name else path_name
            
            # Get valid values if it's an object property with class constraint
            valid_values = []
            if row.class:
                class_name = self.ontology_manager._extract_name_from_uri(str(row.class))
                individuals = self.ontology_manager.get_individuals(class_name)
                valid_values = [info.display_name for info in individuals.values()]
            
            properties.append(SHACLProperty(
                path=path_name,
                name=path_name,
                display_name=display_name,
                datatype=str(row.datatype) if row.datatype else None,
                node_kind=str(row.nodeKind) if row.nodeKind else None,
                class_constraint=str(row.class) if row.class else None,
                min_count=int(row.minCount) if row.minCount else None,
                max_count=int(row.maxCount) if row.maxCount else None,
                min_value=float(row.minValue) if row.minValue else None,
                max_value=float(row.maxValue) if row.maxValue else None,
                pattern=str(row.pattern) if row.pattern else None,
                description=str(row.description) if row.description else None,
                group=str(row.group) if row.group else None,
                order=int(row.order) if row.order else 0,
                valid_values=valid_values
            ))
        
        return properties
    
    def _get_property_groups(self, shape_uri: str) -> Dict[str, str]:
        """Get property groups defined in the shape"""
        
        groups = {}
        
        group_query = f"""
        SELECT ?group ?label WHERE {{
            <{shape_uri}> sh:property ?propShape .
            ?propShape sh:group ?group .
            ?group rdfs:label ?label .
        }}
        """
        
        for row in self.ontology_manager.graph.query(group_query):
            group_uri = str(row.group)
            group_label = str(row.label)
            groups[group_uri] = group_label
        
        return groups
    
    def _generate_shape_from_ontology(self, class_name: str) -> SHACLShape:
        """Generate a shape from ontology structure when no SHACL shape exists"""
        
        properties = []
        
        # Get class properties from ontology
        class_properties = self.ontology_manager.get_class_properties(class_name)
        
        for i, prop in enumerate(class_properties):
            valid_values = []
            datatype = None
            class_constraint = None
            
            if prop.range_class:
                # Object property - get valid individuals
                individuals = self.ontology_manager.get_individuals(prop.range_class)
                valid_values = [info.display_name for info in individuals.values()]
                class_constraint = prop.range_class
            else:
                # Data property - assume string for now
                datatype = "xsd:string"
            
            properties.append(SHACLProperty(
                path=prop.name,
                name=prop.name,
                display_name=prop.name.replace('has', '').replace('_', ' ').title(),
                datatype=datatype,
                class_constraint=class_constraint,
                description=prop.description,
                order=i,
                valid_values=valid_values
            ))
        
        return SHACLShape(
            target_class=class_name,
            shape_uri=f"generated:{class_name}Shape",
            label=f"{class_name} Form",
            description=f"Auto-generated form for {class_name}",
            properties=properties,
            groups={}
        )
    
    def create_form_from_shape(self, class_name: str, parent: QWidget = None) -> 'SHACLForm':
        """Create a form widget from SHACL shape"""
        
        shape = self.get_shape_for_class(class_name)
        if not shape:
            raise ValueError(f"No SHACL shape found for class {class_name}")
        
        return SHACLForm(shape, self.ontology_manager, parent)


class SHACLForm(QWidget):
    """
    Auto-generated form based on SHACL shapes.
    
    This form automatically adapts to the SHACL shape definition and
    provides validation based on SHACL constraints.
    """
    
    # Signals
    data_changed = pyqtSignal(dict)
    validation_changed = pyqtSignal(bool, list)  # is_valid, errors
    
    def __init__(self, shape: SHACLShape, ontology_manager=None, parent=None):
        super().__init__(parent)
        
        self.shape = shape
        self.ontology_manager = ontology_manager
        self.widgets = {}
        self.validation_errors = []
        
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """Setup the form UI based on SHACL shape"""
        
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        self.setLayout(main_layout)
        
        # Form title
        title = QLabel(self.shape.label)
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        main_layout.addWidget(title)
        
        # Description if available
        if self.shape.description:
            desc = QLabel(self.shape.description)
            desc.setStyleSheet("color: #666; margin-bottom: 15px;")
            desc.setWordWrap(True)
            main_layout.addWidget(desc)
        
        # Scrollable content area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()
        scroll_widget.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_widget)
        main_layout.addWidget(scroll_area)
        
        # Group properties by group (if groups are defined)
        if self.shape.groups:
            self._create_grouped_properties(scroll_layout)
        else:
            self._create_flat_properties(scroll_layout)
        
        # Add stretch
        scroll_layout.addStretch()
        
        # Validation status
        self.validation_label = QLabel("Validation: Enter data to validate")
        self.validation_label.setStyleSheet("color: #666; font-style: italic; margin-top: 10px;")
        main_layout.addWidget(self.validation_label)
    
    def _create_grouped_properties(self, parent_layout):
        """Create properties organized by groups"""
        
        # Group properties by their group
        grouped_props = {}
        ungrouped_props = []
        
        for prop in self.shape.properties:
            if prop.group and prop.group in self.shape.groups:
                if prop.group not in grouped_props:
                    grouped_props[prop.group] = []
                grouped_props[prop.group].append(prop)
            else:
                ungrouped_props.append(prop)
        
        # Create group boxes
        for group_uri, group_label in self.shape.groups.items():
            if group_uri in grouped_props:
                group_box = QGroupBox(group_label)
                group_layout = QFormLayout()
                group_box.setLayout(group_layout)
                
                for prop in grouped_props[group_uri]:
                    self._create_property_widget(prop, group_layout)
                
                parent_layout.addWidget(group_box)
        
        # Add ungrouped properties
        if ungrouped_props:
            general_group = QGroupBox("General Properties")
            general_layout = QFormLayout()
            general_group.setLayout(general_layout)
            
            for prop in ungrouped_props:
                self._create_property_widget(prop, general_layout)
            
            parent_layout.addWidget(general_group)
    
    def _create_flat_properties(self, parent_layout):
        """Create properties in a flat layout"""
        
        form_layout = QFormLayout()
        
        # Sort properties by order
        sorted_props = sorted(self.shape.properties, key=lambda p: p.order or 0)
        
        for prop in sorted_props:
            self._create_property_widget(prop, form_layout)
        
        parent_layout.addLayout(form_layout)
    
    def _create_property_widget(self, prop: SHACLProperty, layout: QFormLayout):
        """Create a widget for a SHACL property"""
        
        # Create label
        label_text = prop.display_name
        if prop.min_count and prop.min_count > 0:
            label_text += " *"  # Required field indicator
        
        label = QLabel(label_text)
        if prop.description:
            label.setToolTip(prop.description)
        
        # Create widget based on property constraints
        widget = self._create_widget_for_property(prop)
        
        # Store widget reference
        self.widgets[prop.name] = widget
        
        # Add to layout
        layout.addRow(label, widget)
    
    def _create_widget_for_property(self, prop: SHACLProperty) -> QWidget:
        """Create appropriate widget based on property constraints"""
        
        # If valid values are specified, use combo box
        if prop.valid_values:
            combo = QComboBox()
            combo.addItem("-- Make a Selection --")
            for value in prop.valid_values:
                combo.addItem(value)
            combo.currentTextChanged.connect(self._on_data_changed)
            return combo
        
        # If datatype is specified, create appropriate widget
        if prop.datatype:
            if 'int' in prop.datatype.lower():
                spinbox = QSpinBox()
                spinbox.setRange(-999999, 999999)
                spinbox.setSpecialValueText("N/A")
                spinbox.setValue(spinbox.minimum())
                if prop.min_value is not None:
                    spinbox.setMinimum(int(prop.min_value))
                if prop.max_value is not None:
                    spinbox.setMaximum(int(prop.max_value))
                spinbox.valueChanged.connect(self._on_data_changed)
                return spinbox
            
            elif 'float' in prop.datatype.lower() or 'double' in prop.datatype.lower():
                spinbox = QDoubleSpinBox()
                spinbox.setRange(-999999.999, 999999.999)
                spinbox.setSpecialValueText("N/A")
                spinbox.setValue(spinbox.minimum())
                if prop.min_value is not None:
                    spinbox.setMinimum(prop.min_value)
                if prop.max_value is not None:
                    spinbox.setMaximum(prop.max_value)
                spinbox.valueChanged.connect(self._on_data_changed)
                return spinbox
            
            elif 'date' in prop.datatype.lower():
                date_edit = QDateEdit()
                date_edit.setDate(QDate.currentDate())
                date_edit.setCalendarPopup(True)
                date_edit.dateChanged.connect(self._on_data_changed)
                return date_edit
            
            elif 'bool' in prop.datatype.lower():
                checkbox = QCheckBox()
                checkbox.stateChanged.connect(self._on_data_changed)
                return checkbox
        
        # Default to line edit for strings
        line_edit = QLineEdit()
        if prop.pattern:
            # Could add regex validation here
            pass
        line_edit.textChanged.connect(self._on_data_changed)
        return line_edit
    
    def _connect_signals(self):
        """Connect internal signals"""
        self.data_changed.connect(self._validate_form)
    
    def _on_data_changed(self):
        """Handle data change events"""
        data = self.get_form_data()
        self.data_changed.emit(data)
    
    def get_form_data(self) -> dict:
        """Get current form data"""
        data = {}
        
        for prop_name, widget in self.widgets.items():
            if isinstance(widget, QComboBox):
                value = widget.currentText()
                if value.startswith("--"):
                    value = ""
                data[prop_name] = value
            
            elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                if widget.value() == widget.minimum():
                    data[prop_name] = None
                else:
                    data[prop_name] = widget.value()
            
            elif isinstance(widget, QDateEdit):
                data[prop_name] = widget.date().toString("yyyy-MM-dd")
            
            elif isinstance(widget, QCheckBox):
                data[prop_name] = widget.isChecked()
            
            elif isinstance(widget, QLineEdit):
                data[prop_name] = widget.text()
            
            else:
                data[prop_name] = str(widget.property("value")) if hasattr(widget, "property") else ""
        
        return data
    
    def _validate_form(self, data: dict):
        """Validate form data against SHACL constraints"""
        errors = []
        
        for prop in self.shape.properties:
            value = data.get(prop.name)
            
            # Check required fields
            if prop.min_count and prop.min_count > 0:
                if not value or (isinstance(value, str) and not value.strip()):
                    errors.append(f"{prop.display_name} is required")
            
            # Check valid values
            if prop.valid_values and value:
                if value not in prop.valid_values:
                    errors.append(f"{prop.display_name} must be one of: {', '.join(prop.valid_values)}")
            
            # Check numeric ranges
            if value is not None and isinstance(value, (int, float)):
                if prop.min_value is not None and value < prop.min_value:
                    errors.append(f"{prop.display_name} must be >= {prop.min_value}")
                if prop.max_value is not None and value > prop.max_value:
                    errors.append(f"{prop.display_name} must be <= {prop.max_value}")
        
        # Update validation status
        is_valid = len(errors) == 0
        self.validation_errors = errors
        
        if is_valid:
            self.validation_label.setText("Validation: ✓ All fields valid")
            self.validation_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.validation_label.setText(f"Validation: ✗ {len(errors)} error(s)")
            self.validation_label.setStyleSheet("color: red; font-weight: bold;")
            self.validation_label.setToolTip("\\n".join(errors))
        
        self.validation_changed.emit(is_valid, errors)
    
    def is_valid(self) -> bool:
        """Check if form is currently valid"""
        return len(self.validation_errors) == 0
    
    def get_validation_errors(self) -> List[str]:
        """Get current validation errors"""
        return self.validation_errors.copy()


# =============================================================================
# EXAMPLE SHACL SHAPE DEFINITIONS
# =============================================================================

EXAMPLE_SHACL_SHAPES = """
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix dyn: <https://github.com/Wino1301/DynaMat-Platform/ontology#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

# Specimen Shape
dyn:SpecimenShape
    a sh:NodeShape ;
    sh:targetClass dyn:Specimen ;
    rdfs:label "Specimen Form" ;
    rdfs:comment "Form for creating and editing specimen data" ;
    sh:property [
        sh:path dyn:hasMaterial ;
        sh:class dyn:Material ;
        sh:minCount 1 ;
        sh:maxCount 1 ;
        sh:name "Material" ;
        sh:description "The material of the specimen" ;
        sh:group dyn:MaterialGroup ;
        sh:order 1 ;
    ] ;
    sh:property [
        sh:path dyn:hasStructure ;
        sh:class dyn:Structure ;
        sh:minCount 1 ;
        sh:maxCount 1 ;
        sh:name "Structure" ;
        sh:description "The structural type of the specimen" ;
        sh:group dyn:MaterialGroup ;
        sh:order 2 ;
    ] ;
    sh:property [
        sh:path dyn:hasShape ;
        sh:class dyn:Shape ;
        sh:minCount 1 ;
        sh:maxCount 1 ;
        sh:name "Shape" ;
        sh:description "The geometric shape of the specimen" ;
        sh:group dyn:GeometryGroup ;
        sh:order 3 ;
    ] .

# SHPB Test Shape
dyn:SHPBTestShape
    a sh:NodeShape ;
    sh:targetClass dyn:SHPBTest ;
    rdfs:label "SHPB Test Configuration" ;
    rdfs:comment "Form for configuring SHPB test conditions" ;
    sh:property [
        sh:path dyn:hasStrikerVelocity ;
        sh:datatype xsd:double ;
        sh:minCount 1 ;
        sh:minInclusive 0.1 ;
        sh:maxInclusive 100.0 ;
        sh:name "Striker Velocity" ;
        sh:description "Initial velocity of the striker bar" ;
        sh:group dyn:StrikerConditions ;
        sh:order 1 ;
    ] ;
    sh:property [
        sh:path dyn:hasStrikerPressure ;
        sh:datatype xsd:double ;
        sh:minCount 1 ;
        sh:minInclusive 0.01 ;
        sh:maxInclusive 10.0 ;
        sh:name "Striker Pressure" ;
        sh:description "Gas pressure driving the striker" ;
        sh:group dyn:StrikerConditions ;
        sh:order 2 ;
    ] ;
    sh:property [
        sh:path dyn:hasMomentumTrap ;
        sh:class dyn:MomentumTrapState ;
        sh:minCount 1 ;
        sh:maxCount 1 ;
        sh:name "Momentum Trap" ;
        sh:description "Momentum trap configuration" ;
        sh:group dyn:EquipmentSetup ;
        sh:order 3 ;
    ] .

# Property Groups
dyn:MaterialGroup
    a sh:PropertyGroup ;
    rdfs:label "Material Properties" .

dyn:GeometryGroup
    a sh:PropertyGroup ;
    rdfs:label "Geometry" .

dyn:StrikerConditions
    a sh:PropertyGroup ;
    rdfs:label "Striker Conditions" .

dyn:EquipmentSetup
    a sh:PropertyGroup ;
    rdfs:label "Equipment Setup" .
"""


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

def main():
    """Example usage of SHACL-based form generation"""
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # Create SHACL form generator
    generator = SHACLFormGenerator()
    
    try:
        # Create form for Specimen class
        form = generator.create_form_from_shape("Specimen")
        
        # Connect signals
        form.data_changed.connect(
            lambda data: print(f"Data changed: {data}")
        )
        form.validation_changed.connect(
            lambda valid, errors: print(f"Validation: {'Valid' if valid else f'Errors: {errors}'}")
        )
        
        # Show form
        form.show()
        
        sys.exit(app.exec())
        
    except Exception as e:
        print(f"Error creating SHACL form: {e}")
        print("This is normal if no SHACL shapes are defined yet.")


if __name__ == "__main__":
    main()