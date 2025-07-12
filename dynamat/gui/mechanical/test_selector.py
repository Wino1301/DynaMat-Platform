"""
Mechanical Test Type Selector

Provides an ontology-driven selector for mechanical test types with dynamic
form generation based on test requirements and available equipment.
"""

import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

# Add the parent directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QLabel, QComboBox, QPushButton, QGroupBox, QTextEdit, QFrame,
    QScrollArea, QSizePolicy, QMessageBox, QProgressBar
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QPalette, QColor

try:
    from dynamat.ontology.manager import get_ontology_manager
except ImportError:
    # Fallback for testing
    def get_ontology_manager():
        return None


@dataclass
class TestTypeInfo:
    """Information about a mechanical test type"""
    uri: str
    name: str
    display_name: str
    description: str
    required_equipment: List[str]
    optional_equipment: List[str]
    required_conditions: List[str]
    specimen_requirements: Dict[str, Any]


class TestTypeSelector(QWidget):
    """
    Widget for selecting mechanical test types from the ontology.
    Provides detailed information about test requirements and capabilities.
    """
    
    # Signals
    test_type_selected = pyqtSignal(str, dict)  # test_type_uri, test_info
    test_type_changed = pyqtSignal(str)  # test_type_uri
    
    def __init__(self, ontology_manager=None):
        super().__init__()
        
        self.ontology_manager = ontology_manager or get_ontology_manager()
        self.available_tests = {}
        self.current_test_type = None
        
        self._setup_ui()
        self._load_test_types()
    
    def _setup_ui(self):
        """Setup the test selector UI"""
        
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        self.setLayout(main_layout)
        
        # Title
        title = QLabel("Select Mechanical Test Type")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        main_layout.addWidget(title)
        
        # Test type selection
        self._create_test_selection_section(main_layout)
        
        # Test information display
        self._create_test_info_section(main_layout)
        
        # Action buttons
        self._create_action_buttons(main_layout)
    
    def _create_test_selection_section(self, parent_layout):
        """Create test type selection dropdown"""
        
        selection_group = QGroupBox("Test Type")
        selection_layout = QFormLayout()
        selection_group.setLayout(selection_layout)
        
        # Test type dropdown
        self.test_type_combo = QComboBox()
        self.test_type_combo.setMinimumWidth(300)
        self.test_type_combo.addItem("-- Make a Selection --", None)
        self.test_type_combo.currentTextChanged.connect(self._on_test_type_changed)
        selection_layout.addRow("Test Type:", self.test_type_combo)
        
        # Loading indicator
        self.loading_label = QLabel("Loading test types from ontology...")
        self.loading_label.setStyleSheet("color: #666; font-style: italic;")
        selection_layout.addRow("", self.loading_label)
        
        parent_layout.addWidget(selection_group)
    
    def _create_test_info_section(self, parent_layout):
        """Create test information display area"""
        
        # Scrollable area for test details
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumHeight(300)
        
        # Content widget
        self.info_widget = QWidget()
        self.info_layout = QVBoxLayout()
        self.info_widget.setLayout(self.info_layout)
        scroll_area.setWidget(self.info_widget)
        
        # Initial empty state
        self._show_empty_info()
        
        parent_layout.addWidget(scroll_area)
    
    def _create_action_buttons(self, parent_layout):
        """Create action buttons"""
        
        button_layout = QHBoxLayout()
        
        # Refresh button
        self.refresh_button = QPushButton("Refresh from Ontology")
        self.refresh_button.clicked.connect(self._load_test_types)
        button_layout.addWidget(self.refresh_button)
        
        button_layout.addStretch()
        
        # Configure button
        self.configure_button = QPushButton("Configure Test")
        self.configure_button.setEnabled(False)
        self.configure_button.clicked.connect(self._configure_selected_test)
        self.configure_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        button_layout.addWidget(self.configure_button)
        
        parent_layout.addLayout(button_layout)
    
    def _load_test_types(self):
        """Load mechanical test types from ontology"""
        
        self.loading_label.show()
        self.test_type_combo.clear()
        self.test_type_combo.addItem("Loading...", None)
        self.configure_button.setEnabled(False)
        
        # Use timer to allow UI to update
        QTimer.singleShot(100, self._do_load_test_types)
    
    def _do_load_test_types(self):
        """Actually load the test types"""
        
        try:
            if self.ontology_manager:
                # Query ontology for mechanical test types
                test_types = self._query_mechanical_test_types()
            else:
                # Show error if ontology is not available
                test_types = {}
                QMessageBox.warning(
                    self, 
                    "Ontology Error", 
                    "Ontology manager is not available. Cannot load test types."
                )
            
            # Update combo box
            self.test_type_combo.clear()
            self.test_type_combo.addItem("-- Make a Selection --", None)
            
            if test_types:
                for test_uri, test_info in test_types.items():
                    self.test_type_combo.addItem(test_info.display_name, test_info)
                
                self.available_tests = test_types
                self.loading_label.setText(f"Loaded {len(test_types)} test types from ontology")
                self.loading_label.setStyleSheet("color: green; font-style: italic;")
            else:
                self.loading_label.setText("No mechanical test types found in ontology")
                self.loading_label.setStyleSheet("color: orange; font-style: italic;")
            
        except Exception as e:
            self.loading_label.setText(f"Error loading test types: {str(e)}")
            self.loading_label.setStyleSheet("color: red; font-style: italic;")
            QMessageBox.warning(self, "Loading Error", f"Failed to load test types from ontology:\n{str(e)}")
    
    def _query_mechanical_test_types(self) -> Dict[str, TestTypeInfo]:
        """Query ontology for mechanical test types"""
        
        test_types = {}
        
        try:
            # Get all mechanical test classes from ontology
            mechanical_tests = self.ontology_manager.get_classes("MechanicalTest")
            
            if not mechanical_tests:
                # Try to find any test-related classes
                all_classes = self.ontology_manager.get_classes()
                test_classes = {name: info for name, info in all_classes.items() 
                              if 'test' in name.lower() or 'Test' in name}
                
                if not test_classes:
                    print("No test classes found in ontology")
                    return {}
                
                mechanical_tests = test_classes
            
            # Process each test type
            for test_name, class_info in mechanical_tests.items():
                try:
                    # Get properties for this test type
                    test_properties = self.ontology_manager.get_class_properties(test_name)
                    
                    # Extract equipment requirements
                    required_equipment = []
                    optional_equipment = []
                    required_conditions = []
                    
                    for prop in test_properties:
                        if 'equipment' in prop.name.lower() or 'bar' in prop.name.lower():
                            if 'required' in prop.name.lower():
                                required_equipment.append(prop.name)
                            else:
                                optional_equipment.append(prop.name)
                        elif 'condition' in prop.name.lower() or 'velocity' in prop.name.lower() or 'pressure' in prop.name.lower():
                            required_conditions.append(prop.name)
                    
                    # Get specimen requirements from ontology
                    specimen_requirements = {}
                    try:
                        # Query for specimen shapes and materials that work with this test
                        shapes = self.ontology_manager.get_individuals("Shape")
                        if shapes:
                            specimen_requirements['shapes'] = list(shapes.keys())
                    except:
                        pass
                    
                    # Create test type info
                    test_types[class_info.uri] = TestTypeInfo(
                        uri=class_info.uri,
                        name=test_name,
                        display_name=test_name.replace('Test', ' Test').replace('SHPB', 'SHPB '),
                        description=class_info.description or f"{test_name} - Description not available in ontology",
                        required_equipment=required_equipment,
                        optional_equipment=optional_equipment,
                        required_conditions=required_conditions,
                        specimen_requirements=specimen_requirements
                    )
                    
                except Exception as e:
                    print(f"Error processing test type {test_name}: {e}")
                    continue
            
        except Exception as e:
            print(f"Error querying ontology for test types: {e}")
            raise
        
        return test_types
    
    def _on_test_type_changed(self, text):
        """Handle test type selection change"""
        
        current_data = self.test_type_combo.currentData()
        
        if current_data is None:
            self._show_empty_info()
            self.configure_button.setEnabled(False)
            self.current_test_type = None
        else:
            self._show_test_info(current_data)
            self.configure_button.setEnabled(True)
            self.current_test_type = current_data.uri
            self.test_type_changed.emit(current_data.uri)
    
    def _show_empty_info(self):
        """Show empty state in info area"""
        
        # Clear existing content
        self._clear_info_layout()
        
        # Empty state message
        empty_label = QLabel("Select a test type to view requirements and configuration options.")
        empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_label.setStyleSheet("color: #666; font-size: 14px; padding: 40px;")
        self.info_layout.addWidget(empty_label)
    
    def _show_test_info(self, test_info: TestTypeInfo):
        """Show detailed information about selected test type"""
        
        # Clear existing content
        self._clear_info_layout()
        
        # Test description
        desc_group = QGroupBox("Description")
        desc_layout = QVBoxLayout()
        desc_text = QTextEdit()
        desc_text.setPlainText(test_info.description)
        desc_text.setReadOnly(True)
        desc_text.setMaximumHeight(80)
        desc_layout.addWidget(desc_text)
        desc_group.setLayout(desc_layout)
        self.info_layout.addWidget(desc_group)
        
        # Equipment requirements
        self._create_equipment_section(test_info)
        
        # Testing conditions
        self._create_conditions_section(test_info)
        
        # Specimen requirements
        self._create_specimen_section(test_info)
        
        # Add stretch to push everything to top
        self.info_layout.addStretch()
    
    def _create_equipment_section(self, test_info: TestTypeInfo):
        """Create equipment requirements section"""
        
        equipment_group = QGroupBox("Equipment Requirements (from Ontology)")
        equipment_layout = QVBoxLayout()
        
        # Required equipment
        if test_info.required_equipment:
            req_label = QLabel("Required:")
            req_label.setStyleSheet("font-weight: bold; color: #d32f2f;")
            equipment_layout.addWidget(req_label)
            
            for equipment in test_info.required_equipment:
                item_label = QLabel(f"• {equipment}")
                item_label.setStyleSheet("margin-left: 20px;")
                equipment_layout.addWidget(item_label)
        
        # Optional equipment
        if test_info.optional_equipment:
            opt_label = QLabel("Optional:")
            opt_label.setStyleSheet("font-weight: bold; color: #1976d2; margin-top: 10px;")
            equipment_layout.addWidget(opt_label)
            
            for equipment in test_info.optional_equipment:
                item_label = QLabel(f"• {equipment}")
                item_label.setStyleSheet("margin-left: 20px; color: #666;")
                equipment_layout.addWidget(item_label)
        
        if not test_info.required_equipment and not test_info.optional_equipment:
            no_equipment = QLabel("No equipment requirements found in ontology")
            no_equipment.setStyleSheet("color: #666; font-style: italic;")
            equipment_layout.addWidget(no_equipment)
        
        equipment_group.setLayout(equipment_layout)
        self.info_layout.addWidget(equipment_group)
    
    def _create_conditions_section(self, test_info: TestTypeInfo):
        """Create testing conditions section"""
        
        conditions_group = QGroupBox("Testing Conditions (from Ontology)")
        conditions_layout = QVBoxLayout()
        
        if test_info.required_conditions:
            for condition in test_info.required_conditions:
                item_label = QLabel(f"• {condition}")
                item_label.setStyleSheet("color: #d32f2f;")
                conditions_layout.addWidget(item_label)
        else:
            no_conditions = QLabel("No specific conditions found in ontology")
            no_conditions.setStyleSheet("color: #666; font-style: italic;")
            conditions_layout.addWidget(no_conditions)
        
        conditions_group.setLayout(conditions_layout)
        self.info_layout.addWidget(conditions_group)
    
    def _create_specimen_section(self, test_info: TestTypeInfo):
        """Create specimen requirements section"""
        
        specimen_group = QGroupBox("Specimen Requirements (from Ontology)")
        specimen_layout = QVBoxLayout()
        
        if test_info.specimen_requirements:
            for key, value in test_info.specimen_requirements.items():
                if isinstance(value, list):
                    label = QLabel(f"{key.replace('_', ' ').title()}: {', '.join(value)}")
                elif isinstance(value, tuple) and len(value) == 2:
                    label = QLabel(f"{key.replace('_', ' ').title()}: {value[0]} - {value[1]} mm")
                else:
                    label = QLabel(f"{key.replace('_', ' ').title()}: {value}")
                specimen_layout.addWidget(label)
        else:
            no_requirements = QLabel("No specific specimen requirements found in ontology")
            no_requirements.setStyleSheet("color: #666; font-style: italic;")
            specimen_layout.addWidget(no_requirements)
        
        specimen_group.setLayout(specimen_layout)
        self.info_layout.addWidget(specimen_group)
    
    def _clear_info_layout(self):
        """Clear all widgets from info layout"""
        while self.info_layout.count():
            child = self.info_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
    
    def _configure_selected_test(self):
        """Configure the selected test type"""
        if self.current_test_type:
            current_data = self.test_type_combo.currentData()
            test_info = {
                'uri': current_data.uri,
                'name': current_data.name,
                'display_name': current_data.display_name,
                'description': current_data.description,
                'requirements': {
                    'equipment': current_data.required_equipment,
                    'conditions': current_data.required_conditions,
                    'specimen': current_data.specimen_requirements
                }
            }
            self.test_type_selected.emit(self.current_test_type, test_info)
    
    def get_selected_test_type(self) -> Optional[str]:
        """Get currently selected test type URI"""
        return self.current_test_type
    
    def get_selected_test_info(self) -> Optional[TestTypeInfo]:
        """Get currently selected test type information"""
        current_data = self.test_type_combo.currentData()
        return current_data if isinstance(current_data, TestTypeInfo) else None


# =============================================================================
# EXAMPLE USAGE AND TESTING
# =============================================================================

def main():
    """Example usage of the test type selector"""
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # Create test selector
    selector = TestTypeSelector()
    
    # Connect signals
    selector.test_type_selected.connect(
        lambda uri, info: print(f"Test selected: {uri}\nInfo: {info}")
    )
    
    # Show selector
    selector.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()