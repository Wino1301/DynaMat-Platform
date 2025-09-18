"""
DynaMat Platform - Widget Dependency Manager (Refactored)
Manages form widget dependencies using simplified rule-based configuration
"""

import json
import logging
import math
from typing import Dict, List, Optional, Any, Union
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox, 
    QCheckBox, QTextEdit, QDateEdit
)
from PyQt6.QtCore import QObject, pyqtSignal

from ..ontology.manager import OntologyManager
from .widgets.unit_value_widget import UnitValueWidget


logger = logging.getLogger(__name__)


class DependencyManager(QObject):
    """
    Simplified dependency manager with rule priorities and field groups.
    
    Uses a configuration-driven approach to handle form dependencies without
    requiring new methods for each rule type.
    """
    
    # Signals
    dependency_triggered = pyqtSignal(str, dict)  # rule_name, rule_data
    action_executed = pyqtSignal(str, str, object)  # rule_name, action_type, result
    
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
        self.logger = logger
        
        # Registry of calculation functions
        self.calculation_functions = {
            'circular_area_from_diameter': self._calc_circular_area_from_diameter,
            'circular_area_from_radius': self._calc_circular_area_from_radius,
            'rectangular_area': self._calc_rectangular_area,
            'volume_cube': self._calc_volume_cube,
            'volume_cylinder': self._calc_volume_cylinder
        }
        
        self._load_configuration()
    
    def _get_default_config_path(self) -> str:
        """Get default configuration file path"""
        return str(Path(__file__).parent / "dependencies.json")
    
    def _load_configuration(self):
        """Load the complete configuration including field groups and dependencies"""
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
            form_widget: The form widget containing form fields
            class_uri: URI of the class the form represents
        """
        self.active_form = form_widget
        
        if not hasattr(form_widget, 'form_fields'):
            self.logger.warning("Form widget has no form_fields attribute")
            return
        
        self.logger.info(f"Setting up dependencies for {class_uri}")
        
        # Connect signals for all triggers
        self._connect_all_triggers()
        
        # Apply initial states based on priority
        self._apply_initial_states()
    
    def _connect_all_triggers(self):
        """Connect signals for all trigger fields in all dependency groups"""
        dependencies = self.config.get('dependencies', {})
        
        for group_name, group_config in dependencies.items():
            # Handle main group trigger
            trigger_uri = group_config.get('trigger')
            if trigger_uri and trigger_uri in self.active_form.form_fields:
                field = self.active_form.form_fields[trigger_uri]
                self._connect_widget_signal(field.widget, group_name, group_config)
                self.logger.debug(f"Connected trigger for group: {group_name}")
            
            # Handle rules with individual triggers (like calculations)
            rules = group_config.get('rules', [])
            for i, rule in enumerate(rules):
                rule_trigger = rule.get('trigger')
                if rule_trigger and rule_trigger in self.active_form.form_fields:
                    field = self.active_form.form_fields[rule_trigger]
                    rule_name = f"{group_name}_rule_{i}"
                    self._connect_widget_signal(field.widget, rule_name, rule)
                    self.logger.debug(f"Connected trigger for rule: {rule_name}")
    
    def _connect_widget_signal(self, widget: QWidget, rule_name: str, rule_config: dict):
        """Connect appropriate signal based on widget type"""
        try:
            if isinstance(widget, UnitValueWidget):
                widget.valueChanged.connect(
                    lambda: self._on_trigger_changed(rule_name, rule_config)
                )
            elif isinstance(widget, QComboBox):
                widget.currentTextChanged.connect(
                    lambda: self._on_trigger_changed(rule_name, rule_config)
                )
            elif isinstance(widget, QLineEdit):
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
            elif isinstance(widget, QTextEdit):
                widget.textChanged.connect(
                    lambda: self._on_trigger_changed(rule_name, rule_config)
                )
        except Exception as e:
            self.logger.error(f"Error connecting signal for rule {rule_name}: {e}")
    
    def _on_trigger_changed(self, rule_name: str, rule_config: dict):
        """Handle any trigger change by re-evaluating all rules in priority order"""
        try:
            self.logger.debug(f"Trigger changed for rule '{rule_name}' - re-evaluating all rules")
            # Instead of evaluating just this rule, re-evaluate all rules in priority order
            self._apply_all_rules_by_priority()
        except Exception as e:
            self.logger.error(f"Error handling trigger change for {rule_name}: {e}")
    
    def _apply_all_rules_by_priority(self):
        """Apply all dependency rules in priority order"""
        dependencies = self.config.get('dependencies', {})
        
        # Sort by priority (lower numbers = higher priority)
        sorted_deps = sorted(dependencies.items(), key=lambda x: x[1].get('priority', 999))
        
        # Keep track of field states to handle conflicts
        field_states = {}  # field_uri -> (should_be_visible, priority, rule_name)
        
        for rule_name, rule_config in sorted_deps:
            try:
                # Get trigger values for this rule
                trigger_uri = rule_config.get('trigger')
                trigger_values = {}
                
                if trigger_uri and trigger_uri in self.active_form.form_fields:
                    field = self.active_form.form_fields[trigger_uri]
                    trigger_values[trigger_uri] = self._extract_widget_value(field.widget)
                
                # Process rules
                rules = rule_config.get('rules', [rule_config])
                rule_priority = rule_config.get('priority', 999)
                
                for rule in rules:
                    # Handle individual rule triggers
                    rule_trigger = rule.get('trigger')
                    if rule_trigger and rule_trigger != trigger_uri:
                        if rule_trigger in self.active_form.form_fields:
                            field = self.active_form.form_fields[rule_trigger]
                            trigger_values[rule_trigger] = self._extract_widget_value(field.widget)
                    
                    # Evaluate condition and determine field states
                    condition_met = self._evaluate_condition(rule, trigger_values)
                    
                    # Update field states based on this rule
                    self._update_field_states(rule, condition_met, rule_priority, rule_name, field_states)
                    
            except Exception as e:
                self.logger.error(f"Error evaluating rule {rule_name}: {e}")
        
        # Apply final field states (higher priority wins)
        self._apply_final_field_states(field_states)
    
    def _update_field_states(self, rule: dict, condition_met: bool, priority: int, rule_name: str, field_states: dict):
        """Update field visibility states based on rule evaluation"""
        action = rule.get('action')
        
        if action in ['show_fields', 'hide_fields']:
            target_fields = rule.get('target_fields', [])
            should_show = (action == 'show_fields') if condition_met else (action == 'hide_fields')
            
            for field_uri in target_fields:
                # Only update if this rule has higher priority (lower number)
                if field_uri not in field_states or field_states[field_uri][1] > priority:
                    field_states[field_uri] = (should_show, priority, rule_name)
        
        elif action == 'apply_configuration' and condition_met:
            # Handle configuration-based rules
            config_type = rule.get('config_type', 'shape_configurations')
            trigger_values = self._get_current_trigger_values(rule)
            
            if trigger_values:
                trigger_value = list(trigger_values.values())[0]
                configuration = self.config.get(config_type, {}).get(trigger_value, {})
                
                # Process show_fields
                show_fields = configuration.get('show_fields', [])
                for field_uri in show_fields:
                    if field_uri not in field_states or field_states[field_uri][1] > priority:
                        field_states[field_uri] = (True, priority, rule_name)
                
                # Process hide_fields
                hide_fields = configuration.get('hide_fields', [])
                for field_uri in hide_fields:
                    if field_uri not in field_states or field_states[field_uri][1] > priority:
                        field_states[field_uri] = (False, priority, rule_name)
    
    def _apply_final_field_states(self, field_states: dict):
        """Apply the final field visibility states"""
        for field_uri, (should_be_visible, priority, rule_name) in field_states.items():
            if field_uri in self.active_form.form_fields:
                field = self.active_form.form_fields[field_uri]
                current_visibility = field.widget.isVisible()
                
                if current_visibility != should_be_visible:
                    # Use the proper method that handles both widget and label
                    self._set_single_field_visibility(field_uri, should_be_visible)
                    action = "showing" if should_be_visible else "hiding"
                    self.logger.debug(f"Rule '{rule_name}' (priority {priority}): {action} {field_uri}")
    
    def _set_single_field_visibility(self, field_uri: str, visible: bool):
        """Set visibility for a single field and its label"""
        if field_uri in self.active_form.form_fields:
            field = self.active_form.form_fields[field_uri]
            field.widget.setVisible(visible)
            
            # Also hide/show the label if it exists
            if hasattr(field.widget.parent(), 'layout'):
                layout = field.widget.parent().layout()
                if layout:
                    # Find the label widget in the form layout
                    for i in range(layout.count()):
                        item = layout.itemAt(i)
                        if item and item.widget():
                            widget = item.widget()
                            # Check if this is a label for our field
                            if (hasattr(widget, 'buddy') and widget.buddy() == field.widget) or \
                               (hasattr(widget, 'text') and callable(getattr(widget, 'text', None)) and 
                                widget.text() and field.property_metadata.display_name in widget.text()):
                                widget.setVisible(visible)
                                break
    
    def _get_current_trigger_values(self, rule: dict) -> Dict[str, Any]:
        """Get current trigger values for a rule"""
        trigger_values = {}
        
        # Get main trigger
        trigger_uri = rule.get('trigger')
        if trigger_uri and trigger_uri in self.active_form.form_fields:
            field = self.active_form.form_fields[trigger_uri]
            trigger_values[trigger_uri] = self._extract_widget_value(field.widget)
        
        return trigger_values
    
    def _apply_special_actions(self):
        """Apply special actions like calculations and template generation"""
        dependencies = self.config.get('dependencies', {})
        
        # Sort by priority
        sorted_deps = sorted(dependencies.items(), key=lambda x: x[1].get('priority', 999))
        
        for rule_name, rule_config in sorted_deps:
            try:
                # Get trigger values
                trigger_uri = rule_config.get('trigger')
                trigger_values = {}
                
                if trigger_uri and trigger_uri in self.active_form.form_fields:
                    field = self.active_form.form_fields[trigger_uri]
                    trigger_values[trigger_uri] = self._extract_widget_value(field.widget)
                
                # Process rules for special actions
                rules = rule_config.get('rules', [rule_config])
                
                for rule in rules:
                    # Handle individual rule triggers
                    rule_trigger = rule.get('trigger')
                    if rule_trigger and rule_trigger != trigger_uri:
                        if rule_trigger in self.active_form.form_fields:
                            field = self.active_form.form_fields[rule_trigger]
                            trigger_values[rule_trigger] = self._extract_widget_value(field.widget)
                    
                    # Execute special actions
                    if self._evaluate_condition(rule, trigger_values):
                        action = rule.get('action')
                        if action in ['calculate', 'generate_template', 'apply_configuration']:
                            self._execute_special_action(rule, trigger_values)
                            
            except Exception as e:
                self.logger.error(f"Error applying special actions for {rule_name}: {e}")
    
    def _execute_special_action(self, rule: dict, trigger_values: Dict[str, Any]):
        """Execute special actions that don't affect field visibility"""
        action = rule.get('action')
        
        try:
            if action == 'calculate':
                self._action_calculate(rule, trigger_values)
            
            elif action == 'generate_template':
                self._action_generate_template(rule, trigger_values)
            
            elif action == 'apply_configuration':
                # Handle special behaviors only (equal dimensions, defaults)
                config_type = rule.get('config_type', 'shape_configurations')
                if trigger_values:
                    trigger_value = list(trigger_values.values())[0]
                    configuration = self.config.get(config_type, {}).get(trigger_value, {})
                    if configuration:
                        self._apply_special_behaviors(configuration)
                        
        except Exception as e:
            self.logger.error(f"Error executing special action '{action}': {e}")
    
    def _apply_initial_states(self):
        """Apply initial states for all dependency rules based on priority"""
        self.logger.info("Applying initial rule states in priority order")
        self._apply_all_rules_by_priority()
        
        # Handle special actions that don't affect visibility
        self._apply_special_actions()
    
    def _evaluate_and_execute_rules(self, rule_name: str, rule_config: dict):
        """Evaluate and execute rules based on current form state"""
        try:
            # Get trigger values
            trigger_uri = rule_config.get('trigger')
            trigger_values = {}
            
            if trigger_uri and trigger_uri in self.active_form.form_fields:
                field = self.active_form.form_fields[trigger_uri]
                trigger_values[trigger_uri] = self._extract_widget_value(field.widget)
            
            # Process rules
            rules = rule_config.get('rules', [rule_config])  # Support both single rule and rule list
            
            for rule in rules:
                # Handle individual rule triggers
                rule_trigger = rule.get('trigger')
                if rule_trigger and rule_trigger != trigger_uri:
                    if rule_trigger in self.active_form.form_fields:
                        field = self.active_form.form_fields[rule_trigger]
                        trigger_values[rule_trigger] = self._extract_widget_value(field.widget)
                
                if self._evaluate_condition(rule, trigger_values):
                    self._execute_action(rule, trigger_values)
                else:
                    self._execute_inverse_action(rule)
                    
        except Exception as e:
            self.logger.error(f"Error evaluating rules for {rule_name}: {e}")
    
    def _evaluate_condition(self, rule: dict, trigger_values: Dict[str, Any]) -> bool:
        """Evaluate a single condition"""
        condition = rule.get('condition', 'value_changed')
        condition_value = rule.get('value')
        
        if condition == 'value_changed':
            return bool(trigger_values and any(v for v in trigger_values.values() if v and str(v).strip()))
        
        elif condition == 'value_equals':
            trigger_value = list(trigger_values.values())[0] if trigger_values else None
            return trigger_value == condition_value
        
        elif condition == 'value_in_list':
            trigger_value = list(trigger_values.values())[0] if trigger_values else None
            return trigger_value in (condition_value or [])
        
        elif condition == 'class_membership':
            trigger_value = list(trigger_values.values())[0] if trigger_values else None
            if not trigger_value:
                return False
            try:
                return self.ontology_manager.is_instance_of_class(trigger_value, condition_value)
            except Exception as e:
                self.logger.error(f"Error checking class membership: {e}")
                return False
        
        return False
    
    def _execute_action(self, rule: dict, trigger_values: Dict[str, Any]):
        """Execute a rule action (legacy method - now mainly for special actions)"""
        action = rule.get('action')
        
        try:
            if action == 'calculate':
                self._action_calculate(rule, trigger_values)
            
            elif action == 'generate_template':
                self._action_generate_template(rule, trigger_values)
            
            elif action == 'apply_configuration':
                # For special behaviors only
                config_type = rule.get('config_type', 'shape_configurations')
                self._action_apply_configuration(trigger_values, config_type)
                
            self.action_executed.emit(action, str(rule), True)
            
        except Exception as e:
            self.logger.error(f"Error executing action '{action}': {e}")
    
    def _execute_inverse_action(self, rule: dict):
        """Execute inverse action when condition is not met (legacy method)"""
        # This is now handled by the priority system
        pass
    
    # ============================================================================
    # ACTION IMPLEMENTATIONS
    # ============================================================================
    
    def _action_show_groups(self, group_names: List[str]):
        """Show all fields in specified groups"""
        for group_name in group_names:
            field_uris = self.config.get('field_groups', {}).get(group_name, [])
            self.logger.debug(f"Showing group '{group_name}' with {len(field_uris)} fields")
            self._set_fields_visibility(field_uris, True)
    
    def _action_hide_groups(self, group_names: List[str]):
        """Hide all fields in specified groups"""
        for group_name in group_names:
            field_uris = self.config.get('field_groups', {}).get(group_name, [])
            self.logger.debug(f"Hiding group '{group_name}' with {len(field_uris)} fields")
            self._set_fields_visibility(field_uris, False)
    
    def _action_apply_configuration(self, trigger_values: Dict[str, Any], config_type: str = 'shape_configurations'):
        """
        Generic method to apply configuration based on trigger value.
        
        This can be used for shapes, materials, structures, or any other
        trigger-based configuration system.
        
        Args:
            trigger_values: Values from trigger widgets
            config_type: Type of configuration to apply (e.g., 'shape_configurations')
        """
        if not trigger_values:
            return
        
        trigger_value = list(trigger_values.values())[0]
        if not trigger_value:
            return
        
        self.logger.info(f"Applying {config_type} for: {trigger_value}")
        
        configuration = self.config.get(config_type, {}).get(trigger_value, {})
        if not configuration:
            self.logger.warning(f"No {config_type} found for: {trigger_value}")
            return
        
        # Show specific fields
        show_fields = configuration.get('show_fields', [])
        if show_fields:
            self._set_fields_visibility(show_fields, True)
            self.logger.debug(f"Showing {len(show_fields)} fields")
        
        # Hide specific fields
        hide_fields = configuration.get('hide_fields', [])
        if hide_fields:
            self._set_fields_visibility(hide_fields, False)
            self.logger.debug(f"Hiding {len(hide_fields)} fields")
        
        # Handle special behaviors
        self._apply_special_behaviors(configuration)
    
    def _apply_special_behaviors(self, configuration: dict):
        """Apply special behaviors defined in configuration"""
        # Handle equal dimensions (for cubic shapes, etc.)
        equal_dims = configuration.get('equal_dimensions', [])
        if len(equal_dims) > 1:
            self._setup_equal_dimensions(equal_dims)
        
        # Handle default values
        default_values = configuration.get('default_values', {})
        if default_values:
            self._set_default_values(default_values)
    
    def _set_default_values(self, default_values: Dict[str, Any]):
        """Set default values for fields"""
        for prop_name, default_value in default_values.items():
            prop_uri = f"https://dynamat.utep.edu/ontology#{prop_name}"
            if prop_uri in self.active_form.form_fields:
                field = self.active_form.form_fields[prop_uri]
                current_value = self._extract_widget_value(field.widget)
                if not current_value:  # Only set if field is empty
                    self._set_widget_value(field.widget, default_value)
    
    def _action_calculate(self, rule: dict, trigger_values: Dict[str, Any]):
        """Perform calculation using registered calculation functions"""
        try:
            calculation_function = rule.get('calculation_function')
            variables = rule.get('variables', {})
            target_uri = rule.get('target')
            
            if not calculation_function or not target_uri:
                self.logger.warning("Calculation rule missing function name or target")
                return
            
            if calculation_function not in self.calculation_functions:
                self.logger.error(f"Unknown calculation function: {calculation_function}")
                return
            
            # Build calculation context
            calc_values = {}
            for var_name, property_name in variables.items():
                # Get the actual property URI
                prop_uri = f"https://dynamat.utep.edu/ontology#{property_name}"
                if prop_uri in self.active_form.form_fields:
                    field = self.active_form.form_fields[prop_uri]
                    value = self._extract_widget_value(field.widget)
                    try:
                        calc_values[var_name] = float(value) if value else 0.0
                    except (ValueError, TypeError):
                        calc_values[var_name] = 0.0
            
            # Execute calculation function
            calc_func = self.calculation_functions[calculation_function]
            result = calc_func(**calc_values)
            
            # Set result
            if target_uri in self.active_form.form_fields:
                field = self.active_form.form_fields[target_uri]
                self._set_widget_value(field.widget, round(result, 3))
                self.logger.debug(f"Calculated {calculation_function} = {result}")
                
        except Exception as e:
            self.logger.error(f"Calculation failed: {e}")
    
    # ============================================================================
    # CALCULATION FUNCTIONS
    # ============================================================================
    
    def _calc_circular_area_from_diameter(self, diameter: float = 0.0, **kwargs) -> float:
        """Calculate circular area from diameter: π * (d/2)²"""
        return math.pi * (diameter / 2) ** 2
    
    def _calc_circular_area_from_radius(self, radius: float = 0.0, **kwargs) -> float:
        """Calculate circular area from radius: π * r²"""
        return math.pi * radius ** 2
    
    def _calc_rectangular_area(self, width: float = 0.0, height: float = 0.0, **kwargs) -> float:
        """Calculate rectangular area: width * height"""
        return width * height
    
    def _calc_volume_cube(self, length: float = 0.0, **kwargs) -> float:
        """Calculate cube volume: length³"""
        return length ** 3
    
    def _calc_volume_cylinder(self, diameter: float = 0.0, length: float = 0.0, **kwargs) -> float:
        """Calculate cylinder volume: π * (d/2)² * length"""
        return math.pi * (diameter / 2) ** 2 * length
    
    def _action_generate_template(self, rule: dict, trigger_values: Dict[str, Any]):
        """Generate template-based ID"""
        template = rule.get('template', '')
        target_uri = rule.get('target')
        
        if not template or not target_uri or not trigger_values:
            return
        
        try:
            # Get material URI and extract material code
            material_uri = list(trigger_values.values())[0]
            material_code = self._get_material_code(material_uri)
            sequence = self._get_next_specimen_sequence(material_code)
            
            generated_id = template.format(materialcode=material_code, sequence=sequence)
            
            if target_uri in self.active_form.form_fields:
                field = self.active_form.form_fields[target_uri]
                self._set_widget_value(field.widget, generated_id)
                field.widget.setReadOnly(not rule.get('editable', True))
                self.logger.info(f"Generated ID: {generated_id}")
                
        except Exception as e:
            self.logger.error(f"Template generation failed: {e}")
    
    def _setup_equal_dimensions(self, dimension_properties: List[str]):
        """Set up equal dimensions for cubic specimens"""
        if len(dimension_properties) < 2:
            return
        
        source_prop = dimension_properties[0]
        source_uri = f"https://dynamat.utep.edu/ontology#{source_prop}"
        
        if source_uri not in self.active_form.form_fields:
            return
        
        source_field = self.active_form.form_fields[source_uri]
        
        def sync_dimensions():
            value = self._extract_widget_value(source_field.widget)
            if value:
                for prop in dimension_properties[1:]:
                    target_uri = f"https://dynamat.utep.edu/ontology#{prop}"
                    if target_uri in self.active_form.form_fields:
                        target_field = self.active_form.form_fields[target_uri]
                        self._set_widget_value(target_field.widget, value)
        
        if isinstance(source_field.widget, UnitValueWidget):
            source_field.widget.valueChanged.connect(sync_dimensions)
        elif isinstance(source_field.widget, QLineEdit):
            source_field.widget.textChanged.connect(sync_dimensions)
        elif isinstance(source_field.widget, (QSpinBox, QDoubleSpinBox)):
            source_field.widget.valueChanged.connect(sync_dimensions)
    
    # ============================================================================
    # UTILITY METHODS
    # ============================================================================
    
    def _extract_widget_value(self, widget: QWidget) -> Any:
        """Extract current value from a widget"""
        try:
            if isinstance(widget, UnitValueWidget):
                return widget.getValue()
            elif isinstance(widget, QComboBox):
                # For ComboBox, try to get data first (URI), then text (display name)
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
            elif isinstance(widget, QDateEdit):
                return widget.date().toString()
            else:
                # Try to handle compound widgets (like float with unit)
                if hasattr(widget, 'layout') and widget.layout():
                    layout = widget.layout()
                    if layout.count() > 0:
                        first_widget = layout.itemAt(0).widget()
                        if first_widget:
                            return self._extract_widget_value(first_widget)
        except Exception as e:
            self.logger.error(f"Error extracting widget value from {type(widget).__name__}: {e}")
        
        return None
    
    def _set_widget_value(self, widget: QWidget, value: Any) -> bool:
        """Set value in a specific widget"""
        try:
            if isinstance(widget, UnitValueWidget):
                widget.setValue(float(value))
                return True
            elif isinstance(widget, QComboBox):
                # Try to set by data first, then by text
                index = widget.findData(value)
                if index >= 0:
                    widget.setCurrentIndex(index)
                else:
                    index = widget.findText(str(value))
                    if index >= 0:
                        widget.setCurrentIndex(index)
                    else:
                        return False
            elif isinstance(widget, QLineEdit):
                widget.setText(str(value))
            elif isinstance(widget, QSpinBox):
                widget.setValue(int(value))
            elif isinstance(widget, QDoubleSpinBox):
                widget.setValue(float(value))
            elif isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))
            elif isinstance(widget, QTextEdit):
                widget.setPlainText(str(value))
            else:
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set widget value: {e}")
            return False
    
    def _set_fields_visibility(self, field_uris: List[str], visible: bool):
        """Set visibility for multiple fields and their labels"""
        for uri in field_uris:
            if uri in self.active_form.form_fields:
                field = self.active_form.form_fields[uri]
                field.widget.setVisible(visible)
                
                # Find and hide/show the associated label
                self._set_field_label_visibility(field, visible)
    
    def _set_field_label_visibility(self, field, visible: bool):
        """Set visibility for a field's label"""
        try:
            # Get the parent form layout
            widget = field.widget
            parent = widget.parent()
            
            if not parent or not hasattr(parent, 'layout'):
                return
                
            layout = parent.layout()
            if not layout:
                return
            
            # For QFormLayout, find the label in the same row
            from PyQt6.QtWidgets import QFormLayout
            if isinstance(layout, QFormLayout):
                # Find which row this widget is in
                for i in range(layout.rowCount()):
                    if layout.itemAt(i, QFormLayout.ItemRole.FieldRole):
                        field_item = layout.itemAt(i, QFormLayout.ItemRole.FieldRole)
                        if field_item.widget() == widget:
                            # Found our widget, now get the label
                            label_item = layout.itemAt(i, QFormLayout.ItemRole.LabelRole)
                            if label_item and label_item.widget():
                                label_item.widget().setVisible(visible)
                            break
            else:
                # Fallback: search for label by text matching
                for i in range(layout.count()):
                    item = layout.itemAt(i)
                    if item and item.widget():
                        label_widget = item.widget()
                        if (hasattr(label_widget, 'text') and 
                            callable(getattr(label_widget, 'text', None)) and
                            hasattr(field, 'property_metadata') and
                            field.property_metadata.display_name in str(label_widget.text())):
                            label_widget.setVisible(visible)
                            break
                            
        except Exception as e:
            self.logger.error(f"Error setting label visibility: {e}")
    
    def _get_material_code(self, material_uri: str) -> str:
        """Get material code from material URI"""
        try:
            # Query to get material code
            query = """
            SELECT ?materialCode WHERE {
                ?material dyn:hasMaterialCode ?materialCode .
            }
            """
            
            from rdflib import URIRef
            results = self.ontology_manager.graph.query(
                query, 
                initBindings={"material": URIRef(material_uri)}
            )
            
            for row in results:
                material_code = str(row.materialCode)
                self.logger.info(f"Found material code: {material_code} for {material_uri}")
                return material_code
            
            # Fallback: extract from URI if no material code found
            fallback_code = self.ontology_manager._extract_local_name(material_uri)
            self.logger.warning(f"No material code found for {material_uri}, using fallback: {fallback_code}")
            return fallback_code
            
        except Exception as e:
            self.logger.error(f"Error getting material code for {material_uri}: {e}")
            # Ultimate fallback
            return self.ontology_manager._extract_local_name(material_uri)
    
    def _get_next_specimen_sequence(self, material_code: str) -> int:
        """Get next sequence number for specimen with given material code"""
        try:
            # Query existing specimens with this material code pattern
            # Look for specimens with IDs like DYNML-{material_code}-####
            query = """
            SELECT ?specimenID WHERE {
                ?specimen rdf:type dyn:Specimen .
                ?specimen dyn:hasSpecimenID ?specimenID .
                FILTER(CONTAINS(?specimenID, ?materialCode))
            }
            """
            
            from rdflib import Literal
            results = self.ontology_manager.graph.query(
                query,
                initBindings={"materialCode": Literal(f"DYNML-{material_code}-")}
            )
            
            max_sequence = 0
            pattern = f"DYNML-{material_code}-"
            
            for row in results:
                specimen_id = str(row.specimenID)
                if specimen_id.startswith(pattern):
                    try:
                        # Extract the sequence number
                        sequence_part = specimen_id[len(pattern):]
                        sequence_num = int(sequence_part)
                        max_sequence = max(max_sequence, sequence_num)
                    except ValueError:
                        # Skip if sequence part is not a valid number
                        continue
            
            next_sequence = max_sequence + 1
            self.logger.info(f"Next sequence for material code {material_code}: {next_sequence}")
            return next_sequence
            
        except Exception as e:
            self.logger.error(f"Error getting next sequence for material {material_code}: {e}")
            return 1