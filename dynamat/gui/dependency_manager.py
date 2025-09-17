"""
DynaMat Platform - Widget Dependency Manager
Manages form widget dependencies based on JSON configuration
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

from ..ontology.manager import OntologyManager


logger = logging.getLogger(__name__)


class DependencyManager(QObject):
    """
    Manages widget dependencies using JSON configuration.
    
    Handles visibility, auto-population, and other dynamic widget behaviors
    based on ontology-driven conditions.
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
        self.dependencies = {}
        self.active_form = None
        
        # Action handlers registry
        self.action_handlers = {
            'show': self._action_show,
            'hide': self._action_hide,
            'enable': self._action_enable,
            'disable': self._action_disable,
            'generate_template': self._action_generate_template,
            'calculate': self._action_calculate,
            'set_value': self._action_set_value
        }
        
        # Condition handlers registry
        self.condition_handlers = {
            'class_membership': self._condition_class_membership,
            'value_equals': self._condition_value_equals,
            'value_changed': self._condition_value_changed,
            'all_filled': self._condition_all_filled,
            'any_filled': self._condition_any_filled,
            'value_greater': self._condition_value_greater,
            'value_less': self._condition_value_less,
            'value_in_range': self._condition_value_in_range
        }
        
        self.logger = logger
        self._load_dependencies()
    
    def _get_default_config_path(self) -> str:
        """Get default configuration file path"""
        return str(Path(__file__).parent / "dependencies.json")
    
    def _load_dependencies(self):
        """Load dependencies from JSON configuration file"""
        try:
            if Path(self.config_path).exists():
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    self.dependencies = config.get('dependencies', {})
                    self.logger.info(f"Loaded {len(self.dependencies)} dependency rules")
            else:
                self.logger.warning(f"Dependency config file not found: {self.config_path}")
                self.dependencies = {}
        except Exception as e:
            self.logger.error(f"Failed to load dependencies: {e}")
            self.dependencies = {}
    
    def setup_dependencies(self, form_widget: QWidget, class_uri: str):
        """
        Set up dependencies for a form widget.
        
        Args:
            form_widget: The form widget containing form fields
            class_uri: URI of the class the form represents
        """
        self.active_form = form_widget
        
        if not hasattr(form_widget, 'form_fields'):
            self.logger.warning("Form widget has no form_fields attribute")
            return
        
        self.logger.info(f"Setting up {len(self.dependencies)} dependency rules for {class_uri}")
        
        # Connect trigger signals for each dependency rule
        for rule_name, rule in self.dependencies.items():
            self._setup_rule_triggers(rule_name, rule)
        
        # Set initial states
        self._apply_initial_states()
    
    def _setup_rule_triggers(self, rule_name: str, rule: dict):
        """Set up trigger connections for a dependency rule"""
        triggers = rule.get('trigger', [])
        if isinstance(triggers, str):
            triggers = [triggers]
        
        for trigger_uri in triggers:
            if trigger_uri in self.active_form.form_fields:
                field = self.active_form.form_fields[trigger_uri]
                self._connect_widget_signal(field.widget, rule_name, rule)
    
    def _connect_widget_signal(self, widget: QWidget, rule_name: str, rule: dict):
        """Connect appropriate signal based on widget type"""
        try:
            if isinstance(widget, QComboBox):
                self.logger.info(f"Connecting QComboBox signal for rule '{rule_name}'")
                widget.currentTextChanged.connect(
                    lambda: self._on_combo_changed(widget, rule_name)
                )
            elif isinstance(widget, QLineEdit):
                widget.textChanged.connect(
                    lambda value, r=rule_name: self._on_trigger_changed(r, value)
                )
            elif isinstance(widget, QSpinBox) or isinstance(widget, QDoubleSpinBox):
                widget.valueChanged.connect(
                    lambda value, r=rule_name: self._on_trigger_changed(r, value)
                )
            elif isinstance(widget, QCheckBox):
                widget.toggled.connect(
                    lambda value, r=rule_name: self._on_trigger_changed(r, value)
                )
            elif isinstance(widget, QTextEdit):
                widget.textChanged.connect(
                    lambda r=rule_name: self._on_trigger_changed(r, self._extract_widget_value(widget))
                )
        except Exception as e:
            self.logger.error(f"Error connecting signal for rule {rule_name}: {e}")
    
    def _on_trigger_changed(self, rule_name: str, trigger_value: Any = None):
        """Handle trigger value changes"""
        if rule_name not in self.dependencies:
            return
        
        rule = self.dependencies[rule_name]
        self.logger.debug(f"Trigger changed for rule '{rule_name}': {trigger_value}")
        
        # Evaluate condition and execute action if met
        self.evaluate_and_execute_rule(rule_name, rule)
    
    def _apply_initial_states(self):
        """Apply initial states for all dependency rules"""
        for rule_name, rule in self.dependencies.items():
            self.evaluate_and_execute_rule(rule_name, rule)
    
    def evaluate_and_execute_rule(self, rule_name: str, rule: dict):
        """Evaluate a dependency rule and execute action if condition is met"""
        try:
            self.logger.info(f"Evaluating rule '{rule_name}'")
            
            # Get current trigger values
            trigger_values = self._get_trigger_values(rule)
            self.logger.info(f"Trigger values for '{rule_name}': {trigger_values}")
            
            # Evaluate condition
            condition_met = self._evaluate_condition(rule, trigger_values)
            
            self.logger.info(f"Rule '{rule_name}' condition result: {condition_met}")
            
            # Execute action
            if condition_met:
                self.logger.info(f"Executing action for rule '{rule_name}'")
                self._execute_action(rule_name, rule, trigger_values)
            else:
                self.logger.info(f"Executing inverse action for rule '{rule_name}'")
                # Execute inverse action if condition not met
                self._execute_inverse_action(rule_name, rule)
                
        except Exception as e:
            self.logger.error(f"Error evaluating rule '{rule_name}': {e}")
    
    def _get_trigger_values(self, rule: dict) -> Dict[str, Any]:
        """Get current values from all trigger widgets"""
        triggers = rule.get('trigger', [])
        if isinstance(triggers, str):
            triggers = [triggers]
        
        values = {}
        for trigger_uri in triggers:
            if trigger_uri in self.active_form.form_fields:
                field = self.active_form.form_fields[trigger_uri]
                # Confirm URI is accessible
                self.logger.debug(f"Processing trigger {trigger_uri}, field property_uri: {field.property_uri}")
                try:
                    widget_value = self._extract_widget_value(field.widget)
                    values[trigger_uri] = widget_value
                    self.logger.debug(f"Extracted value for {trigger_uri}: {widget_value}")
                except Exception as e:
                    self.logger.error(f"Error extracting value for {trigger_uri}: {e}, widget type: {type(field.widget)}")
                    values[trigger_uri] = None
            else:
                self.logger.warning(f"Trigger URI not found in form fields: {trigger_uri}")
        
        return values
    
    def _extract_widget_value(self, widget: QWidget) -> Any:
        """Extract current value from a widget"""
        try:
            widget_type = type(widget).__name__
            self.logger.debug(f"Extracting value from {widget_type}")
            
            if isinstance(widget, QComboBox):
                # For ComboBox, try to get data first (URI), then text (display name)
                data = widget.currentData()
                text = widget.currentText()
                self.logger.debug(f"QComboBox - data: {data}, text: {text}")
                return data if data is not None and data != "" else text
            elif isinstance(widget, QLineEdit):
                value = widget.text()
                self.logger.debug(f"QLineEdit - text: {value}")
                return value
            elif isinstance(widget, QSpinBox) or isinstance(widget, QDoubleSpinBox):
                value = widget.value()
                self.logger.debug(f"SpinBox - value: {value}")
                return value
            elif isinstance(widget, QCheckBox):
                value = widget.isChecked()
                self.logger.debug(f"QCheckBox - checked: {value}")
                return value
            elif isinstance(widget, QTextEdit):
                value = widget.toPlainText()
                self.logger.debug(f"QTextEdit - text: {value}")
                return value
            elif isinstance(widget, QDateEdit):
                value = widget.date().toString()
                self.logger.debug(f"QDateEdit - date: {value}")
                return value
            else:
                # Try to handle compound widgets (like float with unit)
                self.logger.debug(f"Unknown widget type: {widget_type}, checking for layout")
                if hasattr(widget, 'layout') and widget.layout():
                    layout = widget.layout()
                    if layout.count() > 0:
                        first_widget = layout.itemAt(0).widget()
                        if first_widget:
                            self.logger.debug(f"Found nested widget: {type(first_widget).__name__}")
                            return self._extract_widget_value(first_widget)
        except AttributeError as e:
            self.logger.error(f"AttributeError extracting widget value from {type(widget).__name__}: {e}")
            self.logger.error(f"Widget attributes: {dir(widget)}")
        except Exception as e:
            self.logger.error(f"Error extracting widget value from {type(widget).__name__}: {e}")
        
        return None
    
    def _evaluate_condition(self, rule: dict, trigger_values: Dict[str, Any]) -> bool:
        """Evaluate the condition for a dependency rule"""
        condition_type = rule.get('condition', 'value_equals')
        condition_value = rule.get('value')
        
        if condition_type not in self.condition_handlers:
            self.logger.error(f"Unknown condition type: {condition_type}")
            return False
        
        handler = self.condition_handlers[condition_type]
        return handler(trigger_values, condition_value, rule)
    
    def _execute_action(self, rule_name: str, rule: dict, trigger_values: Dict[str, Any]):
        """Execute the action specified in the rule"""
        action_type = rule.get('action', 'show')
        
        if action_type not in self.action_handlers:
            self.logger.error(f"Unknown action type: {action_type}")
            return
        
        handler = self.action_handlers[action_type]
        result = handler(rule, trigger_values)
        
        self.action_executed.emit(rule_name, action_type, result)
        self.logger.debug(f"Executed action '{action_type}' for rule '{rule_name}'")
    
    def _execute_inverse_action(self, rule_name: str, rule: dict):
        """Execute the inverse action (e.g., hide if action is show)"""
        action_type = rule.get('action', 'show')
        inverse_actions = {
            'show': 'hide',
            'hide': 'show',
            'enable': 'disable',
            'disable': 'enable'
        }
        
        inverse_action = inverse_actions.get(action_type)
        if inverse_action and inverse_action in self.action_handlers:
            handler = self.action_handlers[inverse_action]
            handler(rule, {})
    
    # ============================================================================
    # CONDITION HANDLERS
    # ============================================================================
    
    def _condition_class_membership(self, trigger_values: Dict[str, Any], 
                                  condition_value: str, rule: dict) -> bool:
        """Check if trigger value belongs to specified class"""
        if not trigger_values:
            self.logger.debug("No trigger values provided")
            return False
        
        # Get the first trigger value (material selection)
        trigger_value = list(trigger_values.values())[0]
        
        self.logger.info(f"Checking class membership: '{trigger_value}' in '{condition_value}'")
        
        # Check if we have a valid URI value
        if not trigger_value or trigger_value == "" or trigger_value is None:
            self.logger.info("Trigger value is empty or None")
            return False
        
        # Check class membership using ontology manager
        try:
            result = self.ontology_manager.is_instance_of_class(trigger_value, condition_value)
            self.logger.info(f"Class membership result: {result}")
            return result
        except Exception as e:
            self.logger.error(f"Error checking class membership: {e}")
            return False
    
    def _condition_value_equals(self, trigger_values: Dict[str, Any], 
                              condition_value: Any, rule: dict) -> bool:
        """Check if trigger value equals condition value"""
        if not trigger_values:
            return False
        
        trigger_value = list(trigger_values.values())[0]
        return trigger_value == condition_value
    
    def _condition_value_changed(self, trigger_values: Dict[str, Any], 
                               condition_value: Any, rule: dict) -> bool:
        """Check if trigger value has changed (any non-empty value)"""
        if not trigger_values:
            return False
        
        trigger_value = list(trigger_values.values())[0]
        return trigger_value is not None and str(trigger_value).strip() != ""
    
    def _condition_all_filled(self, trigger_values: Dict[str, Any], 
                            condition_value: bool, rule: dict) -> bool:
        """Check if all trigger fields are filled"""
        if not trigger_values:
            return False
        
        all_filled = all(
            val is not None and str(val).strip() != "" 
            for val in trigger_values.values()
        )
        return all_filled == condition_value
    
    def _condition_any_filled(self, trigger_values: Dict[str, Any], 
                            condition_value: bool, rule: dict) -> bool:
        """Check if any trigger field is filled"""
        if not trigger_values:
            return False
        
        any_filled = any(
            val is not None and str(val).strip() != "" 
            for val in trigger_values.values()
        )
        return any_filled == condition_value
    
    def _condition_value_greater(self, trigger_values: Dict[str, Any], 
                               condition_value: float, rule: dict) -> bool:
        """Check if trigger value is greater than condition value"""
        if not trigger_values:
            return False
        
        try:
            trigger_value = float(list(trigger_values.values())[0])
            return trigger_value > condition_value
        except (ValueError, TypeError):
            return False
    
    def _condition_value_less(self, trigger_values: Dict[str, Any], 
                            condition_value: float, rule: dict) -> bool:
        """Check if trigger value is less than condition value"""
        if not trigger_values:
            return False
        
        try:
            trigger_value = float(list(trigger_values.values())[0])
            return trigger_value < condition_value
        except (ValueError, TypeError):
            return False
    
    def _condition_value_in_range(self, trigger_values: Dict[str, Any], 
                                condition_value: List[float], rule: dict) -> bool:
        """Check if trigger value is within specified range"""
        if not trigger_values or len(condition_value) != 2:
            return False
        
        try:
            trigger_value = float(list(trigger_values.values())[0])
            return condition_value[0] <= trigger_value <= condition_value[1]
        except (ValueError, TypeError):
            return False
    
    # ============================================================================
    # ACTION HANDLERS  
    # ============================================================================
    
    def _action_show(self, rule: dict, trigger_values: Dict[str, Any]) -> bool:
        """Show target widgets"""
        return self._set_widget_visibility(rule, True)
    
    def _action_hide(self, rule: dict, trigger_values: Dict[str, Any]) -> bool:
        """Hide target widgets"""
        return self._set_widget_visibility(rule, False)
    
    def _action_enable(self, rule: dict, trigger_values: Dict[str, Any]) -> bool:
        """Enable target widgets"""
        return self._set_widget_enabled(rule, True)
    
    def _action_disable(self, rule: dict, trigger_values: Dict[str, Any]) -> bool:
        """Disable target widgets"""
        return self._set_widget_enabled(rule, False)
    
    def _set_widget_visibility(self, rule: dict, visible: bool) -> bool:
        """Set visibility for target widgets"""
        targets = rule.get('target', [])
        if isinstance(targets, str):
            targets = [targets]
        
        success = True
        for target_uri in targets:
            if target_uri in self.active_form.form_fields:
                field = self.active_form.form_fields[target_uri]
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
            else:
                self.logger.warning(f"Target widget not found: {target_uri}")
                success = False
        
        return success
    
    def _set_widget_enabled(self, rule: dict, enabled: bool) -> bool:
        """Set enabled state for target widgets"""
        targets = rule.get('target', [])
        if isinstance(targets, str):
            targets = [targets]
        
        success = True
        for target_uri in targets:
            if target_uri in self.active_form.form_fields:
                field = self.active_form.form_fields[target_uri]
                field.widget.setEnabled(enabled)
            else:
                self.logger.warning(f"Target widget not found: {target_uri}")
                success = False
        
        return success
    
    def _action_generate_template(self, rule: dict, trigger_values: Dict[str, Any]) -> str:
        """Generate template-based values"""
        template = rule.get('template', '')
        
        if not template or not trigger_values:
            return ""
        
        try:
            # Create format dictionary from trigger values
            format_dict = {}
            for uri, value in trigger_values.items():
                # Extract property name from URI for template
                prop_name = self.ontology_manager._extract_local_name(uri).lower()
                format_dict[prop_name] = value
            
            # Handle material code extraction for specimen ID generation
            if 'materialcode' in template.lower():
                material_uri = trigger_values.get("https://dynamat.utep.edu/ontology#hasMaterial")
                if material_uri:
                    material_code = self._get_material_code(material_uri)
                    format_dict['materialcode'] = material_code
                    
                    # Generate sequence number for this material code
                    if 'sequence' in template:
                        format_dict['sequence'] = self._get_next_specimen_sequence(material_code)
            
            generated_value = template.format(**format_dict)
            
            # Set value in target widgets
            targets = rule.get('target', [])
            if isinstance(targets, str):
                targets = [targets]
            
            for target_uri in targets:
                if target_uri in self.active_form.form_fields:
                    field = self.active_form.form_fields[target_uri]
                    self._set_widget_value(field.widget, generated_value)
                    
                    # Make non-editable if specified
                    if not rule.get('editable', True):
                        field.widget.setReadOnly(True)
            
            return generated_value
            
        except Exception as e:
            self.logger.error(f"Template generation failed: {e}")
            return ""
    
    def _action_calculate(self, rule: dict, trigger_values: Dict[str, Any]) -> float:
        """Calculate value using formula"""
        formula = rule.get('formula', '')
        
        if not formula or not trigger_values:
            return 0.0
        
        try:
            # Create calculation dictionary from trigger values
            calc_dict = {}
            for uri, value in trigger_values.items():
                prop_name = self.ontology_manager._extract_local_name(uri).lower()
                calc_dict[prop_name] = float(value) if value else 0.0
            
            # Simple formula evaluation (could be enhanced)
            result = eval(formula.format(**calc_dict))
            
            # Set result in target widgets
            targets = rule.get('target', [])
            if isinstance(targets, str):
                targets = [targets]
            
            for target_uri in targets:
                if target_uri in self.active_form.form_fields:
                    field = self.active_form.form_fields[target_uri]
                    self._set_widget_value(field.widget, result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Calculation failed: {e}")
            return 0.0
    
    def _action_set_value(self, rule: dict, trigger_values: Dict[str, Any]) -> bool:
        """Set specific value in target widgets"""
        value = rule.get('value')
        targets = rule.get('target', [])
        if isinstance(targets, str):
            targets = [targets]
        
        success = True
        for target_uri in targets:
            if target_uri in self.active_form.form_fields:
                field = self.active_form.form_fields[target_uri]
                if not self._set_widget_value(field.widget, value):
                    success = False
            else:
                success = False
        
        return success
    
    def _set_widget_value(self, widget: QWidget, value: Any) -> bool:
        """Set value in a specific widget"""
        try:
            if isinstance(widget, QComboBox):
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
    
    def _check_rdf_database_folder(self):
        """Ensure the rdf_database folder structure exists"""
        try:
            from pathlib import Path
            
            # Get project root (assuming we're in dynamat/gui/dependency_manager.py)
            project_root = Path(__file__).parent.parent.parent
            rdf_database_path = project_root / "rdf_database"
            
            # Create the folder if it doesn't exist
            rdf_database_path.mkdir(exist_ok=True)
            
            self.logger.info(f"RDF database folder ensured at: {rdf_database_path}")
            return rdf_database_path
            
        except Exception as e:
            self.logger.error(f"Error ensuring RDF database folder: {e}")
            return None
    
    def _check_specimen_folder_exists(self, specimen_id: str) -> bool:
        """Check if specimen folder already exists in rdf_database"""
        try:
            rdf_database_path = self._check_rdf_database_folder()
            if not rdf_database_path:
                return False
            
            specimen_folder = rdf_database_path / specimen_id
            exists = specimen_folder.exists()
            
            if exists:
                self.logger.info(f"Specimen folder already exists: {specimen_folder}")
            
            return exists
            
        except Exception as e:
            self.logger.error(f"Error checking specimen folder for {specimen_id}: {e}")
            return False

    def _on_combo_changed(self, widget: QComboBox, rule_name: str):
        """Handle combo box changes with detailed logging"""
        try:
            current_text = widget.currentText()
            current_data = widget.currentData()
            
            self.logger.info(f"Combo changed for rule '{rule_name}': text='{current_text}', data='{current_data}'")
            
            # Extract the proper value
            extracted_value = self._extract_widget_value(widget)
            self.logger.info(f"Extracted value: '{extracted_value}'")
            
            # Call the trigger handler
            self._on_trigger_changed(rule_name, extracted_value)
            
        except Exception as e:
            self.logger.error(f"Error in combo change handler for rule '{rule_name}': {e}")