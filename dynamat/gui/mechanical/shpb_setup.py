"""
SHPB Test Setup Form

Ontology-driven SHPB test conditions form. Queries actual ontology for
available units, materials, conditions, etc. Creates temporary TTL files
as user fills data and exports final TTL on save.
"""

import sys
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import tempfile
import uuid

# Add the parent directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QLabel, QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox, QDateEdit,
    QPushButton, QGroupBox, QTextEdit, QFrame, QScrollArea, QCheckBox,
    QTabWidget, QSizePolicy, QMessageBox, QProgressBar, QButtonGroup
)
from PyQt6.QtCore import Qt, pyqtSignal, QDate, QTimer
from PyQt6.QtGui import QFont, QPalette, QColor, QDoubleValidator

try:
    from dynamat.ontology.manager import get_ontology_manager
    from dynamat.ontology.builders import ExperimentalRDFBuilder
except ImportError:
    # Fallback for testing
    def get_ontology_manager():
        return None
    
    class ExperimentalRDFBuilder:
        def __init__(self):
            pass


@dataclass
class SHPBTestConditions:
    """Data structure for SHPB test conditions"""
    striker_velocity: Optional[float] = None
    striker_velocity_unit: str = ""
    striker_pressure: Optional[float] = None
    striker_pressure_unit: str = ""
    momentum_trap_condition: str = ""
    test_temperature: Optional[float] = None
    test_temperature_unit: str = ""
    test_date: str = ""
    test_name: str = ""
    user: str = ""
    notes: str = ""
    bar_material: str = ""
    strain_gauge_setup: str = ""
    daq_rate: Optional[int] = None
    humidity: Optional[float] = None


class SHPBConditionsForm(QWidget):
    """
    SHPB Test Conditions Configuration Form
    
    Ontology-driven form that queries actual ontology for available options.
    Creates temporary TTL files and supports specimen naming convention:
    SPN-MaterialName-TestID(xxx)
    """
    
    # Signals
    data_changed = pyqtSignal(dict)
    validation_changed = pyqtSignal(bool)
    conditions_confirmed = pyqtSignal(dict)
    ttl_exported = pyqtSignal(str)  # file_path
    
    def __init__(self, ontology_manager=None):
        super().__init__()
        
        self.ontology_manager = ontology_manager or get_ontology_manager()
        self.current_conditions = SHPBTestConditions()
        self.is_confirmed = False
        self.validation_errors = []
        
        # TTL file management
        self.temp_ttl_file = None
        self.experiment_builder = None
        
        # Widget references for data collection
        self.widgets = {}
        
        self._setup_ui()
        self._populate_from_ontology()
        self._connect_signals()
        self._initialize_temp_ttl()
    
    def _setup_ui(self):
        """Setup the SHPB conditions form UI"""
        
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        self.setLayout(main_layout)
        
        # Form title
        title = QLabel("SHPB Test Conditions")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        main_layout.addWidget(title)
        
        # Scrollable content area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()
        scroll_widget.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_widget)
        main_layout.addWidget(scroll_area)
        
        # Test metadata section
        self._create_test_metadata_section(scroll_layout)
        
        # Striker conditions section
        self._create_striker_conditions_section(scroll_layout)
        
        # Environmental conditions section
        self._create_environmental_section(scroll_layout)
        
        # Equipment setup section
        self._create_equipment_section(scroll_layout)
        
        # Notes section
        self._create_notes_section(scroll_layout)
        
        # Add stretch to push everything to top
        scroll_layout.addStretch()
        
        # Action buttons
        self._create_action_buttons(main_layout)
    
    def _create_test_metadata_section(self, parent_layout):
        """Create test metadata section"""
        
        metadata_group = QGroupBox("Test Metadata")
        metadata_layout = QFormLayout()
        metadata_group.setLayout(metadata_layout)
        
        # Test name
        self.test_name_edit = QLineEdit()
        self.test_name_edit.setPlaceholderText("Enter descriptive test name")
        self.test_name_edit.textChanged.connect(self._on_data_changed)
        metadata_layout.addRow("Test Name:", self.test_name_edit)
        self.widgets['test_name'] = self.test_name_edit
        
        # Test date
        self.test_date_edit = QDateEdit()
        self.test_date_edit.setDate(QDate.currentDate())
        self.test_date_edit.setCalendarPopup(True)
        self.test_date_edit.dateChanged.connect(self._on_data_changed)
        metadata_layout.addRow("Test Date:", self.test_date_edit)
        self.widgets['test_date'] = self.test_date_edit
        
        # User/Operator
        self.user_combo = QComboBox()
        self.user_combo.setEditable(True)
        self.user_combo.addItem("-- Make a Selection --")
        self.user_combo.currentTextChanged.connect(self._on_data_changed)
        metadata_layout.addRow("Operator:", self.user_combo)
        self.widgets['user'] = self.user_combo
        
        parent_layout.addWidget(metadata_group)
    
    def _create_striker_conditions_section(self, parent_layout):
        """Create striker conditions section"""
        
        striker_group = QGroupBox("Striker Conditions")
        striker_layout = QFormLayout()
        striker_group.setLayout(striker_layout)
        
        # Striker velocity
        velocity_widget = QWidget()
        velocity_layout = QHBoxLayout()
        velocity_layout.setContentsMargins(0, 0, 0, 0)
        velocity_widget.setLayout(velocity_layout)
        
        self.striker_velocity_spinbox = QDoubleSpinBox()
        self.striker_velocity_spinbox.setRange(-999999, 999999)
        self.striker_velocity_spinbox.setDecimals(2)
        self.striker_velocity_spinbox.setSpecialValueText("N/A")
        self.striker_velocity_spinbox.setValue(self.striker_velocity_spinbox.minimum())
        self.striker_velocity_spinbox.valueChanged.connect(self._on_data_changed)
        velocity_layout.addWidget(self.striker_velocity_spinbox)
        
        self.striker_velocity_unit_combo = QComboBox()
        self.striker_velocity_unit_combo.addItem("-- Make a Selection --")
        self.striker_velocity_unit_combo.currentTextChanged.connect(self._on_data_changed)
        velocity_layout.addWidget(self.striker_velocity_unit_combo)
        
        striker_layout.addRow("Striker Velocity:", velocity_widget)
        self.widgets['striker_velocity'] = self.striker_velocity_spinbox
        self.widgets['striker_velocity_unit'] = self.striker_velocity_unit_combo
        
        # Striker pressure
        pressure_widget = QWidget()
        pressure_layout = QHBoxLayout()
        pressure_layout.setContentsMargins(0, 0, 0, 0)
        pressure_widget.setLayout(pressure_layout)
        
        self.striker_pressure_spinbox = QDoubleSpinBox()
        self.striker_pressure_spinbox.setRange(-999999, 999999)
        self.striker_pressure_spinbox.setDecimals(3)
        self.striker_pressure_spinbox.setSpecialValueText("N/A")
        self.striker_pressure_spinbox.setValue(self.striker_pressure_spinbox.minimum())
        self.striker_pressure_spinbox.valueChanged.connect(self._on_data_changed)
        pressure_layout.addWidget(self.striker_pressure_spinbox)
        
        self.striker_pressure_unit_combo = QComboBox()
        self.striker_pressure_unit_combo.addItem("-- Make a Selection --")
        self.striker_pressure_unit_combo.currentTextChanged.connect(self._on_data_changed)
        pressure_layout.addWidget(self.striker_pressure_unit_combo)
        
        striker_layout.addRow("Striker Pressure:", pressure_widget)
        self.widgets['striker_pressure'] = self.striker_pressure_spinbox
        self.widgets['striker_pressure_unit'] = self.striker_pressure_unit_combo
        
        # Momentum trap condition
        self.momentum_trap_combo = QComboBox()
        self.momentum_trap_combo.addItem("-- Make a Selection --")
        self.momentum_trap_combo.currentTextChanged.connect(self._on_data_changed)
        striker_layout.addRow("Momentum Trap:", self.momentum_trap_combo)
        self.widgets['momentum_trap'] = self.momentum_trap_combo
        
        parent_layout.addWidget(striker_group)
    
    def _create_environmental_section(self, parent_layout):
        """Create environmental conditions section"""
        
        env_group = QGroupBox("Environmental Conditions")
        env_layout = QFormLayout()
        env_group.setLayout(env_layout)
        
        # Test temperature
        temp_widget = QWidget()
        temp_layout = QHBoxLayout()
        temp_layout.setContentsMargins(0, 0, 0, 0)
        temp_widget.setLayout(temp_layout)
        
        self.temperature_spinbox = QDoubleSpinBox()
        self.temperature_spinbox.setRange(-999999, 999999)
        self.temperature_spinbox.setDecimals(1)
        self.temperature_spinbox.setSpecialValueText("N/A")
        self.temperature_spinbox.setValue(self.temperature_spinbox.minimum())
        self.temperature_spinbox.valueChanged.connect(self._on_data_changed)
        temp_layout.addWidget(self.temperature_spinbox)
        
        self.temperature_unit_combo = QComboBox()
        self.temperature_unit_combo.addItem("-- Make a Selection --")
        self.temperature_unit_combo.currentTextChanged.connect(self._on_data_changed)
        temp_layout.addWidget(self.temperature_unit_combo)
        
        env_layout.addRow("Test Temperature:", temp_widget)
        self.widgets['temperature'] = self.temperature_spinbox
        self.widgets['temperature_unit'] = self.temperature_unit_combo
        
        # Humidity (optional)
        self.humidity_spinbox = QDoubleSpinBox()
        self.humidity_spinbox.setRange(-999999, 999999)
        self.humidity_spinbox.setDecimals(1)
        self.humidity_spinbox.setSpecialValueText("N/A")
        self.humidity_spinbox.setValue(self.humidity_spinbox.minimum())
        self.humidity_spinbox.setSuffix(" %")
        self.humidity_spinbox.valueChanged.connect(self._on_data_changed)
        env_layout.addRow("Humidity (%):", self.humidity_spinbox)
        self.widgets['humidity'] = self.humidity_spinbox
        
        parent_layout.addWidget(env_group)
    
    def _create_equipment_section(self, parent_layout):
        """Create equipment setup section"""
        
        equipment_group = QGroupBox("Equipment Setup")
        equipment_layout = QFormLayout()
        equipment_group.setLayout(equipment_layout)
        
        # Bar material selection
        self.bar_material_combo = QComboBox()
        self.bar_material_combo.addItem("-- Make a Selection --")
        self.bar_material_combo.currentTextChanged.connect(self._on_data_changed)
        equipment_layout.addRow("Bar Material:", self.bar_material_combo)
        self.widgets['bar_material'] = self.bar_material_combo
        
        # Strain gauge setup
        self.strain_gauge_combo = QComboBox()
        self.strain_gauge_combo.addItem("-- Make a Selection --")
        self.strain_gauge_combo.currentTextChanged.connect(self._on_data_changed)
        equipment_layout.addRow("Strain Gauge Setup:", self.strain_gauge_combo)
        self.widgets['strain_gauge_setup'] = self.strain_gauge_combo
        
        # Data acquisition rate
        self.daq_rate_spinbox = QSpinBox()
        self.daq_rate_spinbox.setRange(-999999, 999999999)
        self.daq_rate_spinbox.setSpecialValueText("N/A")
        self.daq_rate_spinbox.setValue(self.daq_rate_spinbox.minimum())
        self.daq_rate_spinbox.setSuffix(" Hz")
        self.daq_rate_spinbox.valueChanged.connect(self._on_data_changed)
        equipment_layout.addRow("DAQ Sample Rate:", self.daq_rate_spinbox)
        self.widgets['daq_rate'] = self.daq_rate_spinbox
        
        parent_layout.addWidget(equipment_group)
    
    def _create_notes_section(self, parent_layout):
        """Create notes section"""
        
        notes_group = QGroupBox("Additional Notes")
        notes_layout = QVBoxLayout()
        notes_group.setLayout(notes_layout)
        
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(100)
        self.notes_edit.setPlaceholderText("Enter any additional notes about the test setup, conditions, or special considerations...")
        self.notes_edit.textChanged.connect(self._on_data_changed)
        notes_layout.addWidget(self.notes_edit)
        self.widgets['notes'] = self.notes_edit
        
        parent_layout.addWidget(notes_group)
    
    def _create_action_buttons(self, parent_layout):
        """Create action buttons"""
        
        button_layout = QHBoxLayout()
        
        # Validation status
        self.validation_label = QLabel("Validation: Enter data to validate")
        self.validation_label.setStyleSheet("color: #666; font-style: italic;")
        button_layout.addWidget(self.validation_label)
        
        button_layout.addStretch()
        
        # Reset button
        self.reset_button = QPushButton("Reset to Defaults")
        self.reset_button.clicked.connect(self._reset_to_defaults)
        button_layout.addWidget(self.reset_button)
        
        # Validate button
        self.validate_button = QPushButton("Validate")
        self.validate_button.clicked.connect(self._validate_conditions)
        button_layout.addWidget(self.validate_button)
        
        # Export TTL button
        self.export_button = QPushButton("Export TTL")
        self.export_button.clicked.connect(self._export_ttl)
        self.export_button.setEnabled(False)
        button_layout.addWidget(self.export_button)
        
        # Confirm/Edit toggle button
        self.confirm_button = QPushButton("Confirm")
        self.confirm_button.clicked.connect(self._toggle_confirm_edit)
        self.confirm_button.setStyleSheet("""
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
        """)
        button_layout.addWidget(self.confirm_button)
        
        parent_layout.addLayout(button_layout)
    
    def _populate_from_ontology(self):
        """Populate form fields from ontology data"""
        
        try:
            if self.ontology_manager:
                # Populate users
                self._populate_users()
                
                # Populate velocity units
                self._populate_velocity_units()
                
                # Populate pressure units
                self._populate_pressure_units()
                
                # Populate temperature units
                self._populate_temperature_units()
                
                # Populate momentum trap conditions
                self._populate_momentum_trap_conditions()
                
                # Populate bar materials
                self._populate_bar_materials()
                
                # Populate strain gauge setups
                self._populate_strain_gauge_setups()
            else:
                QMessageBox.warning(
                    self, 
                    "Ontology Warning", 
                    "Ontology manager is not available. Form will use fallback data."
                )
                self._populate_fallback_data()
                
        except Exception as e:
            print(f"Error populating from ontology: {e}")
            QMessageBox.warning(
                self, 
                "Ontology Error", 
                f"Error loading data from ontology: {str(e)}\nUsing fallback data."
            )
            self._populate_fallback_data()
    
    def _populate_users(self):
        """Populate user dropdown from ontology"""
        
        try:
            users = self.ontology_manager.get_individuals("User")
            if users:
                for user_name, user_info in users.items():
                    display_name = user_info.name or user_name
                    self.user_combo.addItem(display_name)
            else:
                # No users found in ontology
                self.user_combo.addItem("Default User")
        except Exception as e:
            print(f"Error populating users: {e}")
            self.user_combo.addItem("Default User")
    
    def _populate_velocity_units(self):
        """Populate velocity units from ontology"""
        
        try:
            # Query for velocity-related units
            velocity_units = []
            
            # Try to get units for velocity from ontology
            units = self.ontology_manager.get_individuals("Unit")
            if units:
                for unit_name, unit_info in units.items():
                    # Look for velocity-related units
                    if any(vel_term in unit_name.lower() for vel_term in ['velocity', 'speed', 'meter', 'second']):
                        velocity_units.append(unit_name)
            
            if velocity_units:
                for unit in velocity_units:
                    self.striker_velocity_unit_combo.addItem(unit)
            else:
                # Fallback units
                self.striker_velocity_unit_combo.addItems(["m/s", "mm/s", "in/s", "ft/s"])
                
        except Exception as e:
            print(f"Error populating velocity units: {e}")
            self.striker_velocity_unit_combo.addItems(["m/s", "mm/s", "in/s", "ft/s"])
    
    def _populate_pressure_units(self):
        """Populate pressure units from ontology"""
        
        try:
            pressure_units = []
            
            units = self.ontology_manager.get_individuals("Unit")
            if units:
                for unit_name, unit_info in units.items():
                    # Look for pressure-related units
                    if any(press_term in unit_name.lower() for press_term in ['pressure', 'pascal', 'psi', 'bar']):
                        pressure_units.append(unit_name)
            
            if pressure_units:
                for unit in pressure_units:
                    self.striker_pressure_unit_combo.addItem(unit)
            else:
                # Fallback units
                self.striker_pressure_unit_combo.addItems(["MPa", "GPa", "Pa", "psi", "bar"])
                
        except Exception as e:
            print(f"Error populating pressure units: {e}")
            self.striker_pressure_unit_combo.addItems(["MPa", "GPa", "Pa", "psi", "bar"])
    
    def _populate_temperature_units(self):
        """Populate temperature units from ontology"""
        
        try:
            temp_units = []
            
            units = self.ontology_manager.get_individuals("Unit")
            if units:
                for unit_name, unit_info in units.items():
                    # Look for temperature-related units
                    if any(temp_term in unit_name.lower() for temp_term in ['temperature', 'celsius', 'fahrenheit', 'kelvin']):
                        temp_units.append(unit_name)
            
            if temp_units:
                for unit in temp_units:
                    self.temperature_unit_combo.addItem(unit)
            else:
                # Fallback units
                self.temperature_unit_combo.addItems(["°C", "°F", "K"])
                
        except Exception as e:
            print(f"Error populating temperature units: {e}")
            self.temperature_unit_combo.addItems(["°C", "°F", "K"])
    
    def _populate_momentum_trap_conditions(self):
        """Populate momentum trap conditions from ontology"""
        
        try:
            momentum_traps = self.ontology_manager.get_individuals("MomentumTrap")
            if momentum_traps:
                for trap_name, trap_info in momentum_traps.items():
                    display_name = trap_info.name or trap_name
                    self.momentum_trap_combo.addItem(display_name)
            else:
                # Fallback conditions
                self.momentum_trap_combo.addItems(["Engaged", "Disengaged", "Partially Engaged", "Not Available"])
                
        except Exception as e:
            print(f"Error populating momentum trap conditions: {e}")
            self.momentum_trap_combo.addItems(["Engaged", "Disengaged"])
    
    def _populate_bar_materials(self):
        """Populate bar material options from ontology"""
        
        try:
            materials = self.ontology_manager.get_individuals("Material")
            if materials:
                for material_name, material_info in materials.items():
                    display_name = material_info.name or material_name
                    self.bar_material_combo.addItem(display_name)
            else:
                # Fallback materials
                self.bar_material_combo.addItems(["Steel1018", "Steel C350", "Al6061", "Ti6Al4V"])
                
        except Exception as e:
            print(f"Error populating bar materials: {e}")
            self.bar_material_combo.addItems(["Steel1018", "Al6061"])
    
    def _populate_strain_gauge_setups(self):
        """Populate strain gauge setup options"""
        
        try:
            # For now, add standard options - could be extended to query ontology
            self.strain_gauge_combo.addItems([
                "Standard Setup", 
                "High-Temperature Setup", 
                "High-Frequency Setup",
                "Custom Setup"
            ])
        except Exception as e:
            print(f"Error populating strain gauge setups: {e}")
            self.strain_gauge_combo.addItems(["Standard Setup"])
    
    def _populate_fallback_data(self):
        """Populate with fallback data when ontology is not available"""
        
        self.user_combo.addItems(["Default User"])
        self.striker_velocity_unit_combo.addItems(["m/s", "mm/s", "in/s"])
        self.striker_pressure_unit_combo.addItems(["MPa", "GPa", "Pa"])
        self.temperature_unit_combo.addItems(["°C", "°F", "K"])
        self.momentum_trap_combo.addItems(["Engaged", "Disengaged"])
        self.bar_material_combo.addItems(["Steel1018", "Al6061"])
        self.strain_gauge_combo.addItems(["Standard Setup"])
    
    def _initialize_temp_ttl(self):
        """Initialize temporary TTL file"""
        
        try:
            # Create temporary file
            temp_dir = Path(tempfile.gettempdir()) / "dynamat_temp"
            temp_dir.mkdir(exist_ok=True)
            
            unique_id = str(uuid.uuid4())[:8]
            self.temp_ttl_file = temp_dir / f"shpb_conditions_{unique_id}.ttl"
            
            # Initialize experiment builder if available
            if hasattr(sys.modules.get('dynamat.ontology.builders'), 'ExperimentalRDFBuilder'):
                self.experiment_builder = ExperimentalRDFBuilder()
                
        except Exception as e:
            print(f"Error initializing temp TTL: {e}")
    
    def _connect_signals(self):
        """Connect internal signals"""
        
        # Auto-validate when data changes
        self.data_changed.connect(self._auto_validate)
        self.data_changed.connect(self._update_temp_ttl)
    
    def _on_data_changed(self):
        """Handle data change events"""
        
        # Collect current data
        current_data = self._collect_form_data()
        
        # Emit data changed signal
        self.data_changed.emit(current_data)
    
    def _collect_form_data(self) -> dict:
        """Collect data from all form fields"""
        
        # Helper function to get spinbox value or None if N/A
        def get_spinbox_value(spinbox):
            if spinbox.value() == spinbox.minimum():
                return None
            return spinbox.value()
        
        # Helper function to get combo value or empty string if no selection
        def get_combo_value(combo):
            current = combo.currentText()
            if current.startswith("--") or not current.strip():
                return ""
            return current
        
        data = {
            'test_name': self.test_name_edit.text(),
            'test_date': self.test_date_edit.date().toString("yyyy-MM-dd"),
            'user': get_combo_value(self.user_combo),
            'striker_velocity': get_spinbox_value(self.striker_velocity_spinbox),
            'striker_velocity_unit': get_combo_value(self.striker_velocity_unit_combo),
            'striker_pressure': get_spinbox_value(self.striker_pressure_spinbox),
            'striker_pressure_unit': get_combo_value(self.striker_pressure_unit_combo),
            'momentum_trap': get_combo_value(self.momentum_trap_combo),
            'temperature': get_spinbox_value(self.temperature_spinbox),
            'temperature_unit': get_combo_value(self.temperature_unit_combo),
            'humidity': get_spinbox_value(self.humidity_spinbox),
            'bar_material': get_combo_value(self.bar_material_combo),
            'strain_gauge_setup': get_combo_value(self.strain_gauge_combo),
            'daq_rate': get_spinbox_value(self.daq_rate_spinbox),
            'notes': self.notes_edit.toPlainText()
        }
        
        return data
    
    def _update_temp_ttl(self, data):
        """Update temporary TTL file with current data"""
        
        try:
            if self.temp_ttl_file and self.experiment_builder:
                # Update experiment builder with current data
                # This would use the actual builder methods
                pass
        except Exception as e:
            print(f"Error updating temp TTL: {e}")
    
    def _auto_validate(self):
        """Automatically validate form when data changes"""
        
        # Delay validation to avoid excessive calls
        if hasattr(self, '_validation_timer'):
            self._validation_timer.stop()
        
        self._validation_timer = QTimer()
        self._validation_timer.timeout.connect(self._validate_conditions)
        self._validation_timer.setSingleShot(True)
        self._validation_timer.start(500)  # 500ms delay
    
    def _validate_conditions(self):
        """Validate current test conditions"""
        
        self.validation_errors = []
        data = self._collect_form_data()
        
        # Check required fields
        if not data['test_name'].strip():
            self.validation_errors.append("Test name is required")
        
        if not data['user']:
            self.validation_errors.append("Operator selection is required")
        
        # Check that selections are made (not default values)
        required_selections = [
            ('striker_velocity_unit', 'Striker velocity unit'),
            ('striker_pressure_unit', 'Striker pressure unit'),
            ('momentum_trap', 'Momentum trap condition'),
            ('bar_material', 'Bar material')
        ]
        
        for field, field_name in required_selections:
            if not data[field]:
                self.validation_errors.append(f"{field_name} must be selected")
        
        # Check numeric values
        if data['striker_velocity'] is not None:
            if data['striker_velocity'] <= 0:
                self.validation_errors.append("Striker velocity must be greater than 0")
            elif data['striker_velocity'] > 100:  # Reasonable upper limit
                self.validation_errors.append("Striker velocity seems unusually high (>100)")
        
        if data['striker_pressure'] is not None:
            if data['striker_pressure'] <= 0:
                self.validation_errors.append("Striker pressure must be greater than 0")
            elif data['striker_pressure'] > 10:  # Reasonable upper limit
                self.validation_errors.append("Striker pressure seems unusually high (>10)")
        
        # Update validation status
        is_valid = len(self.validation_errors) == 0
        
        if is_valid:
            self.validation_label.setText("Validation: ✓ All conditions valid")
            self.validation_label.setStyleSheet("color: green; font-weight: bold;")
            self.export_button.setEnabled(True)
        else:
            error_text = f"Validation: ✗ {len(self.validation_errors)} error(s)"
            self.validation_label.setText(error_text)
            self.validation_label.setStyleSheet("color: red; font-weight: bold;")
            self.validation_label.setToolTip("\\n".join(self.validation_errors))
            self.export_button.setEnabled(False)
        
        # Emit validation status
        self.validation_changed.emit(is_valid)
        
        return is_valid
    
    def _export_ttl(self):
        """Export conditions to TTL file following naming convention"""
        
        if not self._validate_conditions():
            QMessageBox.warning(
                self,
                "Validation Error",
                "Please fix validation errors before exporting"
            )
            return
        
        try:
            # Generate specimen name following convention: SPN-MaterialName-TestID(xxx)
            data = self._collect_form_data()
            material_name = data['bar_material'].replace(' ', '')
            test_id = "001"  # This should be incremented based on existing files
            specimen_name = f"SPN-{material_name}-{test_id}"
            
            # Create database directory structure
            project_root = Path.cwd()
            database_dir = project_root / "database" / "specimens" / specimen_name
            database_dir.mkdir(parents=True, exist_ok=True)
            
            # Create TTL filename
            test_date = data['test_date'].replace('-', '')
            ttl_filename = f"{specimen_name}_TEST_{test_date}.ttl"
            ttl_path = database_dir / ttl_filename
            
            # Export TTL (placeholder - actual implementation would use experiment builder)
            self._write_ttl_file(ttl_path, data, specimen_name)
            
            QMessageBox.information(
                self,
                "Export Successful",
                f"SHPB test conditions exported to:\\n{ttl_path}"
            )
            
            self.ttl_exported.emit(str(ttl_path))
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Error",
                f"Failed to export TTL file:\\n{str(e)}"
            )
    
    def _write_ttl_file(self, file_path: Path, data: dict, specimen_name: str):
        """Write TTL file with current data"""
        
        # This is a placeholder implementation
        # Actual implementation would use the experiment builder
        ttl_content = f"""
@prefix dyn: <https://github.com/Wino1301/DynaMat-Platform/ontology#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

# SHPB Test Conditions for {specimen_name}
# Generated on {datetime.now().isoformat()}

dyn:{specimen_name}_SHPBTest rdf:type dyn:SHPBTest ;
    dyn:hasTestName "{data['test_name']}" ;
    dyn:hasTestDate "{data['test_date']}" ;
    dyn:hasOperator "{data['user']}" ;
    dyn:hasNotes "{data['notes']}" .

# Striker Conditions
"""
        
        if data['striker_velocity'] is not None:
            ttl_content += f"""
dyn:{specimen_name}_StrikerVelocity rdf:type dyn:Velocity ;
    dyn:hasValue {data['striker_velocity']} ;
    dyn:hasUnits "{data['striker_velocity_unit']}" .
"""
        
        if data['striker_pressure'] is not None:
            ttl_content += f"""
dyn:{specimen_name}_StrikerPressure rdf:type dyn:Pressure ;
    dyn:hasValue {data['striker_pressure']} ;
    dyn:hasUnits "{data['striker_pressure_unit']}" .
"""
        
        # Write to file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(ttl_content)
    
    def _toggle_confirm_edit(self):
        """Toggle between confirm and edit modes"""
        
        if self.is_confirmed:
            # Switch to edit mode
            self._set_form_enabled(True)
            self.confirm_button.setText("Confirm")
            self.is_confirmed = False
        else:
            # Validate before confirming
            if self._validate_conditions():
                # Switch to confirmed mode
                self._set_form_enabled(False)
                self.confirm_button.setText("Edit")
                self.is_confirmed = True
                
                # Emit confirmed signal with current data
                confirmed_data = self._collect_form_data()
                self.conditions_confirmed.emit(confirmed_data)
            else:
                QMessageBox.warning(
                    self, 
                    "Validation Errors",
                    "Please fix the following errors before confirming:\\n\\n" + 
                    "\\n".join(self.validation_errors)
                )
    
    def _set_form_enabled(self, enabled: bool):
        """Enable or disable all form fields"""
        
        for widget in self.widgets.values():
            widget.setEnabled(enabled)
        
        self.reset_button.setEnabled(enabled)
        self.validate_button.setEnabled(enabled)
    
    def _reset_to_defaults(self):
        """Reset form to default values"""
        
        reply = QMessageBox.question(
            self,
            "Reset Form",
            "Are you sure you want to reset all fields to default values?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Reset all fields to default state
            self.test_name_edit.clear()
            self.test_date_edit.setDate(QDate.currentDate())
            
            # Reset combo boxes to "Make a Selection"
            for combo in [self.user_combo, self.striker_velocity_unit_combo, 
                         self.striker_pressure_unit_combo, self.momentum_trap_combo,
                         self.temperature_unit_combo, self.bar_material_combo,
                         self.strain_gauge_combo]:
                combo.setCurrentIndex(0)
            
            # Reset spinboxes to N/A
            for spinbox in [self.striker_velocity_spinbox, self.striker_pressure_spinbox,
                           self.temperature_spinbox, self.humidity_spinbox]:
                spinbox.setValue(spinbox.minimum())
            
            self.daq_rate_spinbox.setValue(self.daq_rate_spinbox.minimum())
            self.notes_edit.clear()
            
            # Reset confirmation state
            if self.is_confirmed:
                self._toggle_confirm_edit()
    
    def get_conditions_data(self) -> dict:
        """Get current conditions data"""
        return self._collect_form_data()
    
    def set_conditions_data(self, data: dict):
        """Set form data from dictionary"""
        
        if 'test_name' in data:
            self.test_name_edit.setText(data['test_name'])
        if 'test_date' in data:
            date = QDate.fromString(data['test_date'], "yyyy-MM-dd")
            self.test_date_edit.setDate(date)
        if 'user' in data:
            self.user_combo.setCurrentText(data['user'])
        if 'striker_velocity' in data and data['striker_velocity'] is not None:
            self.striker_velocity_spinbox.setValue(data['striker_velocity'])
        if 'striker_velocity_unit' in data:
            self.striker_velocity_unit_combo.setCurrentText(data['striker_velocity_unit'])
        # ... continue for other fields
    
    def is_form_valid(self) -> bool:
        """Check if form is currently valid"""
        return len(self.validation_errors) == 0
    
    def get_validation_errors(self) -> List[str]:
        """Get current validation errors"""
        return self.validation_errors.copy()


# =============================================================================
# EXAMPLE USAGE AND TESTING
# =============================================================================

def main():
    """Example usage of the SHPB conditions form"""
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # Create form
    form = SHPBConditionsForm()
    
    # Connect signals
    form.data_changed.connect(
        lambda data: print(f"Data changed: {data['test_name']}")
    )
    form.validation_changed.connect(
        lambda valid: print(f"Validation: {'Valid' if valid else 'Invalid'}")
    )
    form.conditions_confirmed.connect(
        lambda data: print(f"Conditions confirmed: {data}")
    )
    form.ttl_exported.connect(
        lambda path: print(f"TTL exported to: {path}")
    )
    
    # Show form
    form.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()