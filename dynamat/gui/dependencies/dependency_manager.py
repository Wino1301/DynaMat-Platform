"""
DynaMat Platform - Dependency Manager (Refactored)
Manages form widget dependencies using calculation engine
"""

import json
import logging
from typing import Dict, List, Optional, Any, Union
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox, 
    QCheckBox, QTextEdit, QDateEdit
)
from PyQt6.QtCore import QObject, pyqtSignal

from ...ontology import OntologyManager
from .calculation_engine import CalculationEngine

logger = logging.getLogger(__name__)


class DependencyManager(QObject):
    """
    Manages form widget dependencies using a calculation engine.
    
    Uses configuration-driven rules to handle form field interactions,
    calculations, and dynamic updates.
    """
    
    # Signals
    dependency_triggered = pyqtSignal(str, dict)  # rule_name, rule_data
    calculation_performed = pyqtSignal(str, float)  # calculation_name, result
    error_occurred = pyqtSignal(str, str)  # rule_name, error_message
    
    def __init__(self, ontology_manager: OntologyManager, config_path: Optional[str] = None):
        """
        Initialize dependency manager.
        
        Args:
            ontology_manager: OntologyManager instance
            config_path: Path to dependency configuration JSON file
        """
        super().__init__()
        
        self.ontology_manager = ontology_manager
        self.config_path = config_path or self._get_default_config_path()
        self.config = {}
        self.active_form = None
        self.logger = logging.getLogger(__name__)
        
        # Initialize calculation engine
        self.calculation_engine = CalculationEngine()
        
        # Load configuration
        self._load_configuration()
        
        self.logger.info("Dependency manager initialized")
    
    def _get_default_config_path(self) -> str:
        """Get default configuration file path"""
        return str(Path(__file__).parent / "dependencies.json")
    
    def _load_configuration(self):
        """Load dependency configuration from JSON file"""
        try:
            if Path(self.config_path).exists():
                with open(self.config_path, 'r') as f:
                    self.config = json.load(f)
                    dependencies_count = len(self.config.get('dependencies', {}))
                    self.logger.info(f"Loaded configuration with {dependencies_count} dependency groups")
            else:
                self.logger.warning(f"Configuration file not found: {self.config_path}")
                self.config = {"shape_configurations": {}, "dependencies": {}}
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            self.config = {"shape_configurations": {}, "dependencies": {}}
    
    def setup_dependencies(self, form_widget: QWidget, class_uri: str):
        """
        Set up all dependencies for a form widget.
        
        Args:
            form_widget: The form widget containing form_fields
            class_uri: URI of the class the form represents
        """
        self.active_form = form_widget
        
        if not hasattr(form_widget, 'form_fields'):
            self.logger.warning("Form widget has no form_fields attribute")
            return
        
        self.logger.info(f"Setting up dependencies for {class_uri}")
        
        # Connect signals for all triggers
        self._connect_all_triggers()
        
        # Apply initial states
        self._apply_initial_states()
        
        self.logger.info("Dependencies configured successfully")
    
    def _connect_all_triggers(self):
        """Connect signals for all trigger fields in dependency rules"""
        dependencies = self.config.get('dependencies', {})
        
        for group_name, group_config in dependencies.items():
            self._connect_group_triggers(group_name, group_config)
    
    def _connect_group_triggers(self, group_name: str, group_config: dict):
        """Connect triggers for a specific dependency group"""
        # Connect main group trigger
        trigger_uri = group_config.get('trigger')
        if trigger_uri and self._has_field(trigger_uri):
            field = self.active_form.form_fields[trigger_uri]
            self._connect_widget_signal(field.widget, group_name, group_config)
            self.logger.debug(f"Connected main trigger for group: {group_name}")
        
        # Connect individual rule triggers (for calculations)
        rules = group_config.get('rules', [])
        for i, rule in enumerate(rules):
            rule_trigger = rule.get('trigger')
            if rule_trigger and self._has_field(rule_trigger):
                field = self.active_form.form_fields[rule_trigger]
                rule_name = f"{group_name}_rule_{i}"
                self._connect_widget_signal(field.widget, rule_name, rule)
                self.logger.debug(f"Connected rule trigger: {rule_name}")
    
    def _connect_widget_signal(self, widget: QWidget, rule_name: str, rule_config: dict):
        """Connect appropriate signal based on widget type"""
        try:
            # Handle UnitValueWidget
            if widget.__class__.__name__ == 'UnitValueWidget':
                widget.valueChanged.connect(
                    lambda: self._on_trigger_changed(rule_name, rule_config)
                )
            # Handle standard Qt widgets
            elif isinstance(widget, QComboBox):
                widget.currentTextChanged.connect(
                    lambda: self._on_trigger_changed(rule_name, rule_config)
                )
            elif isinstance(widget, (QLineEdit, QTextEdit)):
                widget.textChanged.connect(
                    lambda: self._on_trigger_changed(rule_name, rule_config)
                )
            elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                widget.valueChanged.connect(
                    lambda: self._on_trigger_changed(rule_name, rule_config)
                )
            elif isinstance(widget, QCheckBox):
                widget.toggled.connect(
                    lambda: self._on_trigger_changed(rule_name, rule_config)
                )
        except Exception as e:
            self.logger.error(f"Failed to connect widget signal for {rule_name}: {e}")
    
    def _on_trigger_changed(self, rule_name: str, rule_config: dict):
        """Handle trigger field value change"""
        try:
            self.logger.debug(f"Trigger changed for rule: {rule_name}")
            
            # Emit signal
            self.dependency_triggered.emit(rule_name, rule_config)
            
            # Process the rule
            self._process_rule(rule_name, rule_config)
            
        except Exception as e:
            self.logger.error(f"Error processing trigger for {rule_name}: {e}")
            self.error_occurred.emit(rule_name, str(e))
    
    def _process_rule(self, rule_name: str, rule_config: dict):
        """Process a dependency rule"""
        rule_type = rule_config.get('type', 'unknown')
        
        if rule_type == 'calculation':
            self._process_calculation_rule(rule_name, rule_config)
        elif rule_type == 'visibility':
            self._process_visibility_rule(rule_name, rule_config)
        elif rule_type == 'validation':
            self._process_validation_rule(rule_name, rule_config)
        elif rule_type == 'sync_dimensions':
            self._process_sync_dimensions_rule(rule_name, rule_config)
        else:
            self.logger.warning(f"Unknown rule type: {rule_type} for {rule_name}")
    
    def _process_calculation_rule(self, rule_name: str, rule_config: dict):
        """Process calculation rule using calculation engine"""
        try:
            calculation_name = rule_config.get('calculation')
            target_field = rule_config.get('target')
            input_fields = rule_config.get('inputs', [])
            
            if not calculation_name or not target_field:
                self.logger.error(f"Invalid calculation rule {rule_name}: missing calculation or target")
                return
            
            # Get input values
            inputs = {}
            for input_config in input_fields:
                field_uri = input_config.get('field')
                param_name = input_config.get('parameter')
                
                if field_uri and param_name and self._has_field(field_uri):
                    value = self._get_field_value(field_uri)
                    if value is not None:
                        inputs[param_name] = value
            
            # Validate inputs
            validation_errors = self.calculation_engine.validate_calculation_inputs(
                calculation_name, **inputs
            )
            
            if validation_errors:
                self.logger.warning(f"Calculation validation failed for {rule_name}: {validation_errors}")
                return
            
            # Perform calculation
            result = self.calculation_engine.calculate(calculation_name, **inputs)
            
            if result is not None:
                # Set result in target field
                self._set_field_value(target_field, result)
                self.calculation_performed.emit(calculation_name, result)
                self.logger.debug(f"Calculation {calculation_name} = {result}")
            else:
                self.logger.error(f"Calculation failed for {rule_name}")
                
        except Exception as e:
            self.logger.error(f"Error in calculation rule {rule_name}: {e}")
            self.error_occurred.emit(rule_name, str(e))
    
    def _process_visibility_rule(self, rule_name: str, rule_config: dict):
        """Process visibility rule"""
        try:
            trigger_field = rule_config.get('trigger')
            target_fields = rule_config.get('targets', [])
            condition = rule_config.get('condition', {})
            
            if not trigger_field or not target_fields:
                return
            
            # Get trigger value
            trigger_value = self._get_field_value(trigger_field)
            
            # Evaluate condition
            show_fields = self._evaluate_condition(trigger_value, condition)
            
            # Apply visibility
            for target_field in target_fields:
                if self._has_field(target_field):
                    field = self.active_form.form_fields[target_field]
                    field.widget.setVisible(show_fields)
                    # Also hide/show the label if it exists
                    if hasattr(field.widget.parent(), 'layout'):
                        layout = field.widget.parent().layout()
                        if layout:
                            for i in range(layout.count()):
                                item = layout.itemAt(i)
                                if item and item.widget() == field.widget:
                                    # Find associated label
                                    if i > 0:
                                        label_item = layout.itemAt(i - 1)
                                        if label_item and label_item.widget():
                                            label_item.widget().setVisible(show_fields)
                                    break
            
        except Exception as e:
            self.logger.error(f"Error in visibility rule {rule_name}: {e}")
    
    def _process_validation_rule(self, rule_name: str, rule_config: dict):
        """Process validation rule"""
        # TODO: Implement validation rules
        pass
    
    def _process_sync_dimensions_rule(self, rule_name: str, rule_config: dict):
        """Process dimension synchronization rule"""
        try:
            trigger_field = rule_config.get('trigger')
            target_fields = rule_config.get('targets', [])
            
            if not trigger_field or not target_fields:
                return
            
            # Get trigger value
            trigger_value = self._get_field_value(trigger_field)
            
            if trigger_value is not None:
                # Set same value to all target fields
                for target_field in target_fields:
                    if self._has_field(target_field) and target_field != trigger_field:
                        self._set_field_value(target_field, trigger_value)
            
        except Exception as e:
            self.logger.error(f"Error in sync dimensions rule {rule_name}: {e}")
    
    def _apply_initial_states(self):
        """Apply initial states based on current field values"""
        dependencies = self.config.get('dependencies', {})
        
        for group_name, group_config in dependencies.items():
            try:
                # Process main group rule
                if group_config.get('trigger'):
                    self._process_rule(group_name, group_config)
                
                # Process individual rules
                rules = group_config.get('rules', [])
                for i, rule in enumerate(rules):
                    rule_name = f"{group_name}_rule_{i}"
                    self._process_rule(rule_name, rule)
                    
            except Exception as e:
                self.logger.error(f"Failed to apply initial state for {group_name}: {e}")
    
    # ============================================================================
    # UTILITY METHODS
    # ============================================================================
    
    def _has_field(self, field_uri: str) -> bool:
        """Check if form has a field with given URI"""
        return (self.active_form and 
                hasattr(self.active_form, 'form_fields') and 
                field_uri in self.active_form.form_fields)
    
    def _get_field_value(self, field_uri: str) -> Any:
        """Get value from a form field"""
        if not self._has_field(field_uri):
            return None
        
        try:
            field = self.active_form.form_fields[field_uri]
            widget = field.widget
            
            # Handle UnitValueWidget
            if widget.__class__.__name__ == 'UnitValueWidget':
                return widget.getValue()
            # Handle standard widgets
            elif isinstance(widget, QComboBox):
                data = widget.currentData()
                text = widget.currentText()
                return data if data is not None and data != "" else text
            elif isinstance(widget, QLineEdit):
                return widget.text()
            elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                return widget.value()
            elif isinstance(widget, QCheckBox):
                return widget.isChecked()
            elif isinstance(widget, QTextEdit):
                return widget.toPlainText()
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting value for {field_uri}: {e}")
            return None
    
    def _set_field_value(self, field_uri: str, value: Any) -> bool:
        """Set value for a form field"""
        if not self._has_field(field_uri):
            return False
        
        try:
            field = self.active_form.form_fields[field_uri]
            widget = field.widget
            
            # Handle UnitValueWidget
            if widget.__class__.__name__ == 'UnitValueWidget':
                widget.setValue(float(value))
                return True
            # Handle standard widgets
            elif isinstance(widget, QLineEdit):
                widget.setText(str(value))
                return True
            elif isinstance(widget, QSpinBox):
                widget.setValue(int(value))
                return True
            elif isinstance(widget, QDoubleSpinBox):
                widget.setValue(float(value))
                return True
            elif isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))
                return True
            elif isinstance(widget, QTextEdit):
                widget.setPlainText(str(value))
                return True
            elif isinstance(widget, QComboBox):
                # Try to find and set by data first, then by text
                for i in range(widget.count()):
                    if widget.itemData(i) == value:
                        widget.setCurrentIndex(i)
                        return True
                # Try by text
                index = widget.findText(str(value))
                if index >= 0:
                    widget.setCurrentIndex(index)
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error setting value for {field_uri}: {e}")
            return False
    
    def _evaluate_condition(self, value: Any, condition: dict) -> bool:
        """Evaluate a condition against a value"""
        try:
            condition_type = condition.get('type', 'equals')
            condition_value = condition.get('value')
            
            if condition_type == 'equals':
                return value == condition_value
            elif condition_type == 'not_equals':
                return value != condition_value
            elif condition_type == 'contains':
                return condition_value in str(value)
            elif condition_type == 'not_empty':
                return value is not None and str(value).strip() != ""
            elif condition_type == 'empty':
                return value is None or str(value).strip() == ""
            elif condition_type == 'greater_than':
                return float(value) > float(condition_value)
            elif condition_type == 'less_than':
                return float(value) < float(condition_value)
            else:
                self.logger.warning(f"Unknown condition type: {condition_type}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error evaluating condition: {e}")
            return False
    
    # ============================================================================
    # PUBLIC METHODS
    # ============================================================================
    
    def reload_configuration(self):
        """Reload dependency configuration from file"""
        self._load_configuration()
        self.logger.info("Configuration reloaded")
    
    def get_configuration(self) -> dict:
        """Get current configuration"""
        return self.config.copy()
    
    def get_available_calculations(self) -> List[str]:
        """Get list of available calculations"""
        return self.calculation_engine.get_available_calculations()
    
    def test_calculation(self, calculation_name: str, **kwargs) -> Optional[float]:
        """Test a calculation with given parameters"""
        return self.calculation_engine.calculate(calculation_name, **kwargs)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get dependency manager statistics"""
        dependencies = self.config.get('dependencies', {})
        total_rules = sum(len(group.get('rules', [])) for group in dependencies.values())
        
        return {
            'config_loaded': bool(self.config),
            'dependency_groups': len(dependencies),
            'total_rules': total_rules,
            'available_calculations': len(self.calculation_engine.get_available_calculations()),
            'active_form': self.active_form is not None
        }