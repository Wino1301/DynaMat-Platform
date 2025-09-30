"""
DynaMat Platform - Dependency Manager 
Manages form widget dependencies using TTL-based constraints
"""

import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

from PyQt6.QtWidgets import QWidget, QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox
from PyQt6.QtCore import QObject, pyqtSignal

from ...ontology import OntologyManager
from .constraint_manager import ConstraintManager, Constraint, ConstraintType, Action, TriggerLogic
from .calculation_engine import CalculationEngine
from .generation_engine import GenerationEngine

logger = logging.getLogger(__name__)


class DependencyManager(QObject):
    """
    Manages form widget dependencies using TTL-based constraint definitions.
    
    Coordinates constraint evaluation, calculations, and value generation
    with Qt signal-based dynamic updates.
    """
    
    # Signals
    constraint_triggered = pyqtSignal(str, str)  # constraint_uri, action
    calculation_performed = pyqtSignal(str, float)  # property_uri, result
    generation_performed = pyqtSignal(str, str)  # property_uri, result
    error_occurred = pyqtSignal(str, str)  # constraint_uri, error_message
    
    def __init__(self, ontology_manager: OntologyManager, 
                 constraint_dir: Optional[Path] = None):
        """
        Initialize dependency manager.
        
        Args:
            ontology_manager: OntologyManager instance
            constraint_dir: Path to constraint TTL files directory
        """
        super().__init__()
        
        self.ontology_manager = ontology_manager
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.constraint_manager = ConstraintManager(constraint_dir)
        self.calculation_engine = CalculationEngine()
        self.generation_engine = GenerationEngine(ontology_manager)
        
        # Active form tracking
        self.active_form = None
        self.active_class_uri = None
        self.constraints_by_trigger: Dict[str, List[Constraint]] = {}
        
        self.logger.info("Dependency manager initialized with constraint-based system")
    
    # ============================================================================
    # SETUP AND CONFIGURATION
    # ============================================================================
    
    def setup_dependencies(self, form_widget: QWidget, class_uri: str):
        """
        Set up all dependencies for a form widget.
        
        Args:
            form_widget: Form widget with form_fields attribute
            class_uri: URI of the class being displayed
        """
        try:
            self.active_form = form_widget
            self.active_class_uri = class_uri
            
            # Load constraints for this class
            constraints = self.constraint_manager.get_constraints_for_class(class_uri)
            self.logger.info(f"Setting up {len(constraints)} constraints for {class_uri}")
            
            # Organize constraints by trigger
            self.constraints_by_trigger.clear()
            for constraint in constraints:
                for trigger_property in constraint.triggers:
                    if trigger_property not in self.constraints_by_trigger:
                        self.constraints_by_trigger[trigger_property] = []
                    self.constraints_by_trigger[trigger_property].append(constraint)
            
            # Connect Qt signals for each trigger property
            for trigger_property in self.constraints_by_trigger.keys():
                self._connect_trigger_signal(trigger_property)
            
            # Initialize form state (evaluate all constraints once)
            self._evaluate_all_constraints()
            
            self.logger.info(f"Dependencies set up successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to setup dependencies: {e}", exc_info=True)
            self.error_occurred.emit("setup", str(e))
    
    def _connect_trigger_signal(self, trigger_property: str):
        """
        Connect appropriate Qt signal for a trigger property.
        
        Args:
            trigger_property: URI of the property that triggers constraints
        """
        if not hasattr(self.active_form, 'form_fields'):
            self.logger.warning("Form widget missing form_fields attribute")
            return
        
        if trigger_property not in self.active_form.form_fields:
            self.logger.debug(f"Trigger property not in form: {trigger_property}")
            return
        
        field = self.active_form.form_fields[trigger_property]
        widget = field.widget
        
        # Connect appropriate signal based on widget type
        if isinstance(widget, QComboBox):
            widget.currentTextChanged.connect(
                lambda: self._on_trigger_changed(trigger_property)
            )
        elif isinstance(widget, (QDoubleSpinBox, QSpinBox)):
            widget.valueChanged.connect(
                lambda: self._on_trigger_changed(trigger_property)
            )
        elif isinstance(widget, QLineEdit):
            widget.textChanged.connect(
                lambda: self._on_trigger_changed(trigger_property)
            )
        elif isinstance(widget, QCheckBox):
            widget.toggled.connect(
                lambda: self._on_trigger_changed(trigger_property)
            )
        
        self.logger.debug(f"Connected signal for trigger: {trigger_property}")
    
    # ============================================================================
    # CONSTRAINT EVALUATION
    # ============================================================================
    
    def _on_trigger_changed(self, trigger_property: str):
        """
        Handle change in a trigger property.
        
        Args:
            trigger_property: URI of the property that changed
        """
        try:
            self.logger.debug(f"Trigger changed: {trigger_property}")
            
            # Get all constraints for this trigger
            constraints = self.constraints_by_trigger.get(trigger_property, [])
            
            # Sort by priority (lower = higher priority)
            constraints = sorted(constraints, key=lambda c: c.priority)
            
            # Evaluate each constraint
            for constraint in constraints:
                self._evaluate_constraint(constraint)
                
        except Exception as e:
            self.logger.error(f"Error handling trigger change: {e}", exc_info=True)
            self.error_occurred.emit(trigger_property, str(e))
    
    def _evaluate_all_constraints(self):
        """Evaluate all constraints for initial form state."""
        try:
            # Get all constraints sorted by priority
            all_constraints = self.constraint_manager.get_constraints_for_class(
                self.active_class_uri
            )
            
            for constraint in all_constraints:
                self._evaluate_constraint(constraint)
                
        except Exception as e:
            self.logger.error(f"Error evaluating all constraints: {e}")
    
    def _evaluate_constraint(self, constraint: Constraint):
        """
        Evaluate a single constraint and apply its action.
        
        Args:
            constraint: Constraint to evaluate
        """
        try:
            # Get trigger values
            trigger_values = self._get_trigger_values(constraint.triggers)
            
            # Evaluate condition
            condition_met = self._evaluate_condition(
                trigger_values,
                constraint.when_values,
                constraint.trigger_logic
            )
            
            self.logger.debug(f"Constraint {constraint.uri}: condition_met={condition_met}")
            
            # Apply action based on constraint type
            if condition_met:
                self._apply_action(constraint, trigger_values)
            else:
                self._apply_inverse_action(constraint)
            
            # Emit signal
            self.constraint_triggered.emit(constraint.uri, constraint.action.value)
            
        except Exception as e:
            self.logger.error(f"Error evaluating constraint {constraint.uri}: {e}")
            self.error_occurred.emit(constraint.uri, str(e))
    
    def _get_trigger_values(self, trigger_properties: List[str]) -> Dict[str, Any]:
        """
        Get current values of trigger properties.
        
        Args:
            trigger_properties: List of property URIs
            
        Returns:
            Dictionary mapping property URI to current value
        """
        values = {}
        
        for prop_uri in trigger_properties:
            if prop_uri in self.active_form.form_fields:
                field = self.active_form.form_fields[prop_uri]
                values[prop_uri] = self._extract_widget_value(field.widget)
        
        return values
    
    def _evaluate_condition(self, trigger_values: Dict[str, Any], 
                           when_values: List[str],
                           trigger_logic: Optional[TriggerLogic]) -> bool:
        """
        Evaluate if constraint condition is met.
        
        Args:
            trigger_values: Current trigger property values
            when_values: Expected values (can be URIs or literals)
            trigger_logic: Logic gate (ANY, ALL, XOR)
            
        Returns:
            True if condition is met
        """
        if not trigger_values:
            return False
        
        # Handle special case: gui:anyValue
        if when_values and "anyValue" in str(when_values[0]):
            # Check if any trigger has a non-empty value
            return any(v and str(v).strip() for v in trigger_values.values())
        
        # Match trigger values to when_values
        matches = []
        for i, (trigger_prop, trigger_value) in enumerate(trigger_values.items()):
            # Get corresponding when_value (parallel list)
            when_value = when_values[i] if i < len(when_values) else None
            
            if when_value:
                # Check if trigger value matches when value
                # Handle both URI matching and class membership
                match = self._value_matches(trigger_value, when_value)
                matches.append(match)
            else:
                matches.append(False)
        
        # Apply logic gate
        if not trigger_logic or trigger_logic == TriggerLogic.ALL:
            return all(matches)
        elif trigger_logic == TriggerLogic.ANY:
            return any(matches)
        elif trigger_logic == TriggerLogic.XOR:
            return sum(matches) == 1
        
        return False
    
    def _value_matches(self, value: Any, expected: str) -> bool:
        """
        Check if a value matches an expected value.
        
        Handles:
        - Direct URI matching
        - Class membership checking (e.g., is material a Composite?)
        - String matching
        """
        if not value or not expected:
            return False
        
        value_str = str(value)
        
        # Direct match
        if value_str == expected:
            return True
        
        # Check if expected is a class URI (class membership check)
        if "#" in expected and "Composite" in expected:  # Heuristic for class URIs
            try:
                # Check if value is an instance of expected class
                return self._is_instance_of_class(value_str, expected)
            except:
                pass
        
        return False
    
    def _is_instance_of_class(self, instance_uri: str, class_uri: str) -> bool:
        """
        Check if an instance is a member of a class.
        
        Args:
            instance_uri: URI of the instance
            class_uri: URI of the class
            
        Returns:
            True if instance is of the class
        """
        try:
            from rdflib import URIRef
            query = """
            ASK {
                ?instance rdf:type/rdfs:subClassOf* ?class .
            }
            """
            result = self.ontology_manager.graph.query(
                query,
                initBindings={
                    "instance": URIRef(instance_uri),
                    "class": URIRef(class_uri)
                }
            )
            return bool(result)
        except Exception as e:
            self.logger.error(f"Class membership check failed: {e}")
            return False
    
    # ============================================================================
    # ACTION APPLICATION
    # ============================================================================
    
    def _apply_action(self, constraint: Constraint, trigger_values: Dict[str, Any]):
        """Apply the constraint's action."""
        if constraint.action == Action.SHOW:
            self._action_show_fields(constraint.affects)
        
        elif constraint.action == Action.HIDE:
            self._action_hide_fields(constraint.affects)
        
        elif constraint.action == Action.REQUIRE:
            self._action_require_fields(constraint.affects, True)
        
        elif constraint.action == Action.OPTIONAL:
            self._action_require_fields(constraint.affects, False)
        
        elif constraint.action == Action.CALCULATE:
            self._action_calculate(constraint)
        
        elif constraint.action == Action.GENERATE:
            self._action_generate(constraint, trigger_values)
        
        elif constraint.action == Action.ENABLE:
            self._action_enable_fields(constraint.affects, True)
        
        elif constraint.action == Action.DISABLE:
            self._action_enable_fields(constraint.affects, False)
    
    def _apply_inverse_action(self, constraint: Constraint):
        """Apply the inverse of the constraint's action."""
        if constraint.action == Action.SHOW:
            self._action_hide_fields(constraint.affects)
        
        elif constraint.action == Action.HIDE:
            self._action_show_fields(constraint.affects)
        
        elif constraint.action == Action.REQUIRE:
            self._action_require_fields(constraint.affects, False)
        
        elif constraint.action == Action.OPTIONAL:
            self._action_require_fields(constraint.affects, True)
    
    def _action_show_fields(self, field_uris: List[str]):
        """Show fields."""
        for field_uri in field_uris:
            self._set_field_visibility(field_uri, True)
    
    def _action_hide_fields(self, field_uris: List[str]):
        """Hide fields."""
        for field_uri in field_uris:
            self._set_field_visibility(field_uri, False)
    
    def _action_require_fields(self, field_uris: List[str], required: bool):
        """Set fields as required or optional."""
        for field_uri in field_uris:
            if field_uri in self.active_form.form_fields:
                field = self.active_form.form_fields[field_uri]
                field.required = required
                # Update visual indicator (e.g., asterisk in label)
    
    def _action_enable_fields(self, field_uris: List[str], enabled: bool):
        """Enable or disable fields."""
        for field_uri in field_uris:
            if field_uri in self.active_form.form_fields:
                field = self.active_form.form_fields[field_uri]
                field.widget.setEnabled(enabled)
    
    def _action_calculate(self, constraint: Constraint):
        """Perform calculation."""
        try:
            # Get input values
            input_values = {}
            for input_prop in constraint.calculation_inputs:
                if input_prop in self.active_form.form_fields:
                    field = self.active_form.form_fields[input_prop]
                    value = self._extract_widget_value(field.widget)
                    input_values[input_prop] = value
            
            # Perform calculation
            result = self.calculation_engine.calculate(
                constraint.calculation_function,
                **input_values
            )
            
            # Set result in target field(s)
            for target_uri in constraint.affects:
                self._set_widget_value(target_uri, result)
            
            self.calculation_performed.emit(constraint.affects[0], result)
            
        except Exception as e:
            self.logger.error(f"Calculation failed: {e}")
            self.error_occurred.emit(constraint.uri, str(e))
    
    def _action_generate(self, constraint: Constraint, trigger_values: Dict[str, Any]):
        """Generate value from template."""
        try:
            # Prepare inputs for generation
            inputs = {}
            for input_prop in constraint.generation_inputs:
                if input_prop in trigger_values:
                    inputs[input_prop] = trigger_values[input_prop]
            
            # Generate value
            result = self.generation_engine.generate(
                constraint.generation_template,
                inputs
            )
            
            # Set result in target field(s)
            for target_uri in constraint.affects:
                self._set_widget_value(target_uri, result)
            
            self.generation_performed.emit(constraint.affects[0], result)
            
        except Exception as e:
            self.logger.error(f"Generation failed: {e}")
            self.error_occurred.emit(constraint.uri, str(e))
    
    # ============================================================================
    # WIDGET VALUE HELPERS
    # ============================================================================
    
    def _extract_widget_value(self, widget: QWidget) -> Any:
        """Extract current value from a widget."""
        if isinstance(widget, QComboBox):
            return widget.currentData() or widget.currentText()
        elif isinstance(widget, QLineEdit):
            return widget.text()
        elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            return widget.value()
        elif isinstance(widget, QCheckBox):
            return widget.isChecked()
        return None
    
    def _set_widget_value(self, property_uri: str, value: Any):
        """Set value in a widget."""
        if property_uri not in self.active_form.form_fields:
            return
        
        field = self.active_form.form_fields[property_uri]
        widget = field.widget
        
        if isinstance(widget, QLineEdit):
            widget.setText(str(value))
        elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            widget.setValue(float(value))
        elif isinstance(widget, QCheckBox):
            widget.setChecked(bool(value))
        elif isinstance(widget, QComboBox):
            index = widget.findText(str(value))
            if index >= 0:
                widget.setCurrentIndex(index)
    
    def _set_field_visibility(self, field_uri: str, visible: bool):
        """Set visibility of a field and its label."""
        if field_uri not in self.active_form.form_fields:
            return
        
        field = self.active_form.form_fields[field_uri]
        field.widget.setVisible(visible)
        
        # Also hide/show label if it exists
        # This depends on your form layout implementation
    
    # ============================================================================
    # PUBLIC API
    # ============================================================================
    
    def reload_constraints(self):
        """Reload constraints from TTL files."""
        self.constraint_manager.reload()
        if self.active_form and self.active_class_uri:
            self.setup_dependencies(self.active_form, self.active_class_uri)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get dependency manager statistics."""
        return {
            **self.constraint_manager.get_statistics(),
            'active_form': self.active_form is not None,
            'active_class': self.active_class_uri,
            'available_calculations': len(self.calculation_engine.get_available_calculations()),
            'available_generators': len(self.generation_engine.get_available_generators())
        }