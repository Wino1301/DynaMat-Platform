"""
DynaMat Platform - Dependency Manager

Manages form widget dependencies using TTL-based constraints. Acts as the main
orchestrator that connects form widgets to constraints defined in TTL files,
handling signal connections, constraint evaluation, and operation execution.

Key responsibilities:
- Connect Qt widget signals to constraint triggers
- Evaluate constraint conditions when trigger values change
- Execute operations (visibility, calculation, generation, population, filtering)
- Track statistics for debugging and testing

Example:
    >>> from dynamat.gui.dependencies import DependencyManager
    >>> dep_manager = DependencyManager(ontology_manager, constraint_dir)
    >>> dep_manager.setup_dependencies(form_widget, "dyn:Specimen")
"""

import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

from PyQt6.QtWidgets import QWidget, QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox, QListWidget
from PyQt6.QtCore import QObject, pyqtSignal, Qt

from ...ontology import OntologyManager
from .constraint_manager import ConstraintManager, Constraint, TriggerLogic
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
    constraint_triggered = pyqtSignal(str, list)  # constraint_uri, operations_performed
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

        # Property display widgets (for population constraints with gui:targetWidget)
        self.property_display_widgets: Dict[str, QWidget] = {}  # constraint_uri -> PropertyDisplayWidget

        # Statistics tracking (always-on)
        self._constraint_evaluation_counts = {}  # constraint_uri -> count
        self._operation_execution_counts = {
            'visibility': 0,
            'calculation': 0,
            'generation': 0,
            'population': 0,
            'filtering': 0
        }
        self._trigger_fire_counts = {}  # trigger_property -> count
        self._signal_emission_counts = {
            'constraint_triggered': 0,
            'calculation_performed': 0,
            'generation_performed': 0,
            'error_occurred': 0
        }
        self._recent_errors = []  # Last 10 errors: (constraint_uri, error_message)

        # Loading mode flag - when True, generation constraints are suppressed
        self._loading_mode = False

        self.logger.info(
            f"DependencyManager initialized: "
            f"{len(self.calculation_engine.get_available_calculations())} calculations, "
            f"{len(self.generation_engine.get_available_generators())} generators available"
        )

    # ============================================================================
    # LOADING MODE CONTROL
    # ============================================================================

    def set_loading_mode(self, enabled: bool):
        """
        Enable or disable loading mode.

        When loading mode is enabled, generation constraints are suppressed to preserve
        loaded values (e.g., specimen ID). Other constraints (visibility, calculation,
        population) continue to work normally.

        Args:
            enabled: True to enable loading mode, False to disable
        """
        self._loading_mode = enabled
        self.logger.debug(f"Loading mode: {'enabled' if enabled else 'disabled'}")

    def is_loading_mode(self) -> bool:
        """
        Check if currently in loading mode.

        Returns:
            True if loading mode is active
        """
        return self._loading_mode

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
            
            # Create and insert PropertyDisplayWidget instances for constraints with targetWidget
            self._setup_property_display_widgets(constraints)

            # Connect Qt signals for each trigger property
            for trigger_property in self.constraints_by_trigger.keys():
                self._connect_trigger_signal(trigger_property)

            # Initialize form state (evaluate all constraints once)
            self._evaluate_all_constraints()

            self.logger.info(
                f"Dependencies setup complete for {class_uri}: "
                f"{len(self.constraints_by_trigger)} trigger properties connected, "
                f"{len(self.property_display_widgets)} property display widgets created"
            )

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

        # Import UnitValueWidget here to avoid circular imports
        try:
            from ..widgets.base.unit_value_widget import UnitValueWidget
        except ImportError:
            UnitValueWidget = None

        # Connect appropriate signal based on widget type
        if isinstance(widget, QComboBox):
            widget.currentTextChanged.connect(
                lambda: self._on_trigger_changed(trigger_property)
            )
        elif isinstance(widget, (QDoubleSpinBox, QSpinBox)):
            widget.valueChanged.connect(
                lambda: self._on_trigger_changed(trigger_property)
            )
        elif UnitValueWidget and isinstance(widget, UnitValueWidget):
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
        elif isinstance(widget, QListWidget):
            widget.itemSelectionChanged.connect(
                lambda: self._on_trigger_changed(trigger_property)
            )

        self.logger.debug(f"Connected signal for trigger: {trigger_property} (widget type: {type(widget).__name__})")

    def _setup_property_display_widgets(self, constraints: List[Constraint]):
        """
        Create and insert PropertyDisplayWidget instances for population constraints.

        Constraints with gui:targetWidget are rendered as read-only PropertyDisplayWidget
        instances inserted below the trigger field's group in the form layout.

        Args:
            constraints: List of all constraints for the current form class
        """
        try:
            from ..widgets.base.property_display import PropertyDisplayWidget, PropertyDisplayConfig
        except ImportError:
            self.logger.warning("PropertyDisplayWidget not available, skipping display widget setup")
            return

        self.property_display_widgets.clear()

        # Find constraints with targetWidget (these are property display constraints)
        display_constraints = [c for c in constraints if hasattr(c, 'target_widget') and c.target_widget]

        if not display_constraints:
            return

        self.logger.info(f"Setting up {len(display_constraints)} property display widgets")

        # For each display constraint, create widget and insert into layout
        for constraint in display_constraints:
            try:
                # Extract title from constraint label or target_widget value
                title = constraint.label or constraint.target_widget.replace("Properties", " Properties")

                # Build PropertyDisplayConfig from constraint definition
                properties = [prop_uri for prop_uri, _ in constraint.populate_fields]
                labels = {prop_uri: label for prop_uri, label in constraint.populate_fields if label}

                # Infer follow_links for nested properties (e.g., material properties on bars)
                follow_links = self._infer_follow_links(properties)

                config = PropertyDisplayConfig(
                    title=title,
                    properties=properties,
                    property_labels=labels if labels else None,
                    follow_links=follow_links if follow_links else None
                )

                # Create PropertyDisplayWidget with ontology-driven config
                display_widget = PropertyDisplayWidget(
                    config=config,
                    ontology_manager=self.ontology_manager
                )

                # Find trigger widget to determine where to insert this display widget
                if not constraint.triggers:
                    self.logger.warning(f"Display constraint {constraint.uri} has no triggers")
                    continue

                trigger_property = constraint.triggers[0]  # Use first trigger

                # Find the trigger widget's parent group widget
                if trigger_property not in self.active_form.form_fields:
                    self.logger.warning(f"Trigger property {trigger_property} not in form fields")
                    continue

                trigger_field = self.active_form.form_fields[trigger_property]
                trigger_widget = trigger_field.widget

                # Traverse up to find the group widget (QGroupBox)
                parent = trigger_widget.parent()
                while parent and parent.parent() is not None:
                    # Look for QGroupBox or similar container
                    if parent.__class__.__name__ == 'QGroupBox':
                        # Found the group box - add display widget to its layout
                        group_layout = parent.layout()
                        if group_layout:
                            group_layout.addWidget(display_widget)
                            self.logger.debug(
                                f"Inserted PropertyDisplayWidget '{title}' into group for {trigger_property}"
                            )
                            break
                    parent = parent.parent()
                else:
                    self.logger.warning(
                        f"Could not find group box for trigger {trigger_property}, "
                        f"adding display widget to main layout"
                    )
                    # Fallback: add to scroll area content if we can find it
                    # This is less ideal but ensures the widget is visible
                    scroll_content = self._find_scroll_content_widget()
                    if scroll_content and scroll_content.layout():
                        # Insert before the final stretch
                        layout = scroll_content.layout()
                        insert_index = layout.count() - 1  # Before stretch
                        layout.insertWidget(max(0, insert_index), display_widget)

                # Store reference to widget keyed by constraint URI
                self.property_display_widgets[constraint.uri] = display_widget

            except Exception as e:
                self.logger.error(
                    f"Failed to create PropertyDisplayWidget for constraint {constraint.uri}: {e}",
                    exc_info=True
                )

        self.logger.info(f"Created {len(self.property_display_widgets)} property display widgets")

    def _find_scroll_content_widget(self) -> Optional[QWidget]:
        """
        Find the scroll area content widget in the form.

        Returns:
            QWidget that contains the form content, or None if not found
        """
        from PyQt6.QtWidgets import QScrollArea

        # The form structure is: form_widget -> QVBoxLayout -> QScrollArea -> content widget
        if not self.active_form:
            return None

        layout = self.active_form.layout()
        if not layout:
            return None

        # Find QScrollArea
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                if isinstance(widget, QScrollArea):
                    return widget.widget()  # The content widget

        return None

    def _infer_follow_links(self, properties: List[str]) -> Optional[Dict[str, List[str]]]:
        """
        Infer which object properties need to be followed for nested property values.

        Material properties (hasWaveSpeed, hasElasticModulus, hasDensity, hasPoissonRatio)
        typically live on the Material individual, so when querying a Bar or equipment,
        we need to follow the hasMaterial link to get these values.

        Args:
            properties: List of property URIs to check

        Returns:
            Dictionary mapping link property to nested properties, or None if no links needed
        """
        # Material properties that typically need hasMaterial followed
        material_property_patterns = [
            'hasWaveSpeed', 'WaveSpeed',
            'hasElasticModulus', 'ElasticModulus',
            'hasDensity', 'Density',
            'hasPoissonRatio', 'PoissonRatio',
            'hasYieldStrength', 'YieldStrength',
        ]

        # Check which properties need material link
        needs_material = []
        for prop in properties:
            # Extract local name from URI
            local_name = prop.split(':')[-1].split('#')[-1].split('/')[-1]
            if any(pattern in local_name for pattern in material_property_patterns):
                needs_material.append(prop)

        if needs_material:
            return {'dyn:hasMaterial': needs_material}

        return None

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
            # Track trigger fire
            self._trigger_fire_counts[trigger_property] = self._trigger_fire_counts.get(trigger_property, 0) + 1

            # Get current value for debugging
            if trigger_property in self.active_form.form_fields:
                field = self.active_form.form_fields[trigger_property]
                widget = field.widget
                current_value = self._extract_widget_value(widget)

                # Check if value is URI for combo boxes
                if isinstance(widget, QComboBox):
                    data = widget.currentData()
                    text = widget.currentText()
                    self.logger.info(
                        f"Trigger changed: {trigger_property} = '{current_value}' "
                        f"(currentData={data}, currentText={text})"
                    )
                else:
                    self.logger.info(f"Trigger changed: {trigger_property} = '{current_value}'")
            else:
                self.logger.debug(f"Trigger changed: {trigger_property}")

            # Get all constraints for this trigger
            constraints = self.constraints_by_trigger.get(trigger_property, [])
            self.logger.debug(f"Found {len(constraints)} constraints for this trigger")

            # Sort by priority (higher values run first, lower values run last and can override)
            constraints = sorted(constraints, key=lambda c: c.priority, reverse=True)

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
        Evaluate a single constraint and apply its operations.

        Args:
            constraint: Constraint to evaluate
        """
        try:
            # Track constraint evaluation
            self._constraint_evaluation_counts[constraint.uri] = self._constraint_evaluation_counts.get(constraint.uri, 0) + 1

            # Get trigger values
            trigger_values = self._get_trigger_values(constraint.triggers)

            # Determine what operations this constraint has
            ops = []
            if constraint.has_visibility_ops():
                ops.append("visibility")
            if constraint.has_calculation_op():
                ops.append("calculation")
            if constraint.has_generation_op():
                ops.append("generation")
            if constraint.has_population_op():
                ops.append("population")

            self.logger.debug(
                f"Evaluating constraint '{constraint.label}' (priority {constraint.priority})"
            )
            self.logger.debug(f"  Operations: {ops}")
            self.logger.debug(f"  Trigger values: {trigger_values}")
            self.logger.debug(f"  Expected when_values: {constraint.when_values}")
            self.logger.debug(f"  Trigger logic: {constraint.trigger_logic}")

            # Evaluate condition
            condition_met = self._evaluate_condition(
                trigger_values,
                constraint.when_values,
                constraint.trigger_logic
            )

            self.logger.debug(f"  Condition met: {condition_met}")

            # Apply operations
            operations_performed = []

            # Population operations always execute (to handle both populate and clear)
            if constraint.has_population_op():
                self._action_populate(constraint, trigger_values)
                operations_performed.append("population")
                self._operation_execution_counts['population'] += 1

            if condition_met:
                # Apply other operations (visibility, calculation, generation, filtering)
                # But skip population since we already handled it above
                other_ops = self._apply_operations(constraint, trigger_values, skip_population=True)
                operations_performed.extend(other_ops)
            else:
                # Only apply inverse for constraints that manage one visibility direction
                # Constraints with both showFields AND hideFields are "complete" and don't need inversion
                # (e.g., shape constraints that explicitly define which fields to show AND hide)
                if self._should_apply_inverse(constraint):
                    inverse_ops = self._apply_inverse_operations(constraint)
                    operations_performed.extend(inverse_ops)

            # Emit signal and track emission
            self.constraint_triggered.emit(constraint.uri, operations_performed)
            self._signal_emission_counts['constraint_triggered'] += 1

        except Exception as e:
            self.logger.error(f"Error evaluating constraint {constraint.uri}: {e}", exc_info=True)
            self.error_occurred.emit(constraint.uri, str(e))
            self._signal_emission_counts['error_occurred'] += 1
            # Track error (keep last 10)
            self._recent_errors.append((constraint.uri, str(e)))
            if len(self._recent_errors) > 10:
                self._recent_errors.pop(0)
    
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

        Handles multiple patterns:
        1. Single trigger, multiple when_values: Check if trigger matches ANY/ALL when_values
        2. Multiple triggers, parallel when_values: Check each trigger against it's when_value
        3. Multiple triggers, single when_value: Check if ANY/ALL triggers match the when_value
        4. Cascade triggers: Handled by priority system

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

        num_triggers = len(trigger_values)
        num_when_values = len(when_values)

        # Pattern 1: Single trigger with multiple when_values
        # Example: hasSpecimenRole triggers, check if value is CharacterizationSpecimen OR ReferenceSpecimen OR CalibrationSpecimen
        if num_triggers == 1 and num_when_values > 1:
            trigger_value = list(trigger_values.values())[0]
            matches = [self._value_matches(trigger_value, when_val) for when_val in when_values]

            # Apply logic gate
            if not trigger_logic or trigger_logic == TriggerLogic.ANY:
                return any(matches)  # Match if value equals ANY of the when_values
            elif trigger_logic == TriggerLogic.ALL:
                return all(matches)  # Match if value equals ALL (rarely used)
            elif trigger_logic == TriggerLogic.XOR:
                return sum(matches) == 1  # Match exactly one

        # Pattern 2: Multiple triggers with single when_value
        # Example: Multiple properties should all equal the same value
        elif num_triggers > 1 and num_when_values == 1:
            when_value = when_values[0]
            matches = [self._value_matches(val, when_value) for val in trigger_values.values()]

            # Apply logic gate
            if not trigger_logic or trigger_logic == TriggerLogic.ALL:
                return all(matches)  # All triggers must match
            elif trigger_logic == TriggerLogic.ANY:
                return any(matches)  # At least one trigger matches
            elif trigger_logic == TriggerLogic.XOR:
                return sum(matches) == 1  # Exactly one trigger matches

        # Pattern 3: Parallel matching - equal number of triggers and when_values
        # Example: trigger[0] matches when_value[0], trigger[1] matches when_value[1]
        elif num_triggers == num_when_values:
            matches = []
            for i, (trigger_prop, trigger_value) in enumerate(trigger_values.items()):
                when_value = when_values[i]
                match = self._value_matches(trigger_value, when_value)
                matches.append(match)

            # Apply logic gate
            if not trigger_logic or trigger_logic == TriggerLogic.ALL:
                return all(matches)
            elif trigger_logic == TriggerLogic.ANY:
                return any(matches)
            elif trigger_logic == TriggerLogic.XOR:
                return sum(matches) == 1

        # Pattern 4: Mismatched counts - fall back to best effort
        # Check if any trigger value matches any when_value
        else:
            self.logger.warning(
                f"Mismatched trigger/when_value counts: {num_triggers} triggers, "
                f"{num_when_values} when_values. Using fallback matching."
            )
            matches = []
            for trigger_value in trigger_values.values():
                for when_value in when_values:
                    if self._value_matches(trigger_value, when_value):
                        matches.append(True)
                        break
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
        - List values (multi-select) - checks if ANY item matches
        - gui:anyValue - matches any non-None/non-empty value
        - gui:noValue - matches when value is None or empty
        - Direct URI matching (exact match)
        - Partial URI matching (fragment/local name match)
        - Class membership checking (e.g., is material a Composite?)
        - String matching (case-insensitive)
        """
        # Handle special cases: gui:anyValue and gui:noValue
        expected_str = str(expected).strip() if expected else ""

        # gui:anyValue - matches any non-None/non-empty value
        if "anyValue" in expected_str:
            if isinstance(value, list):
                has_value = len(value) > 0
            else:
                has_value = value is not None and str(value).strip() != ""
            self.logger.debug(f"    Match (anyValue): value={'present' if has_value else 'absent'}")
            return has_value

        # gui:noValue - matches when value is None or empty
        if "noValue" in expected_str:
            if isinstance(value, list):
                is_empty = len(value) == 0
            else:
                is_empty = value is None or str(value).strip() == ""
            self.logger.debug(f"    Match (noValue): value={'absent' if is_empty else 'present'}")
            return is_empty

        # Handle list values (multi-select widgets)
        # For lists, check if ANY item in the list matches the expected value
        if isinstance(value, list):
            if not value:  # Empty list
                return False
            for item in value:
                if self._value_matches_single(item, expected_str):
                    self.logger.debug(f"    Match (list item): {item} matches {expected_str}")
                    return True
            return False

        # Regular matching requires both value and expected to be non-empty
        if not value or not expected:
            return False

        return self._value_matches_single(value, expected_str)

    def _value_matches_single(self, value: Any, expected_str: str) -> bool:
        """
        Check if a single value matches an expected value.

        Helper method for _value_matches to handle individual value comparisons.
        """
        if not value:
            return False

        value_str = str(value).strip()

        # Direct match (exact)
        if value_str == expected_str:
            self.logger.debug(f"    Match (exact): '{value_str}' == '{expected_str}'")
            return True

        # Extract local name from URIs for comparison
        # Example: "https://dynamat.utep.edu/ontology#CharacterizationSpecimen" -> "CharacterizationSpecimen"
        value_local = value_str.split('#')[-1].split('/')[-1]
        expected_local = expected_str.split('#')[-1].split('/')[-1]

        # Match on local names
        if value_local == expected_local:
            self.logger.debug(f"    Match (local): '{value_local}' == '{expected_local}'")
            return True

        # Case-insensitive string match
        if value_str.lower() == expected_str.lower():
            self.logger.debug(f"    Match (case-insensitive): '{value_str}' == '{expected_str}'")
            return True

        # Check if expected is a class URI (attempt class membership check)
        # Only do this if both value and expected look like URIs (contain # or /)
        if ('#' in expected_str or '/' in expected_str) and ('#' in value_str or '/' in value_str):
            try:
                # Check if value is an instance of expected class
                if self._is_instance_of_class(value_str, expected_str):
                    self.logger.debug(f"    Match (class membership): '{value_str}' is instance of '{expected_str}'")
                    return True
            except Exception as e:
                self.logger.debug(f"    Class membership check skipped: {e}")

        self.logger.debug(f"    No match: '{value_str}' != '{expected_str}' (locals: '{value_local}' vs '{expected_local}')")
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
    # OPERATION APPLICATION
    # ============================================================================

    def _apply_operations(self, constraint: Constraint, trigger_values: Dict[str, Any],
                          skip_population: bool = False) -> List[str]:
        """
        Apply all operations defined in the constraint.

        Operations are executed in order:
        1. Visibility (show/hide fields)
        2. Calculations (compute derived values)
        3. Generation (generate IDs/codes)
        4. Population (populate fields from selected individual)

        Args:
            constraint: Constraint to apply
            trigger_values: Current trigger values
            skip_population: If True, skip population operations (default False)

        Returns:
            List of operation names that were performed
        """
        operations_performed = []

        # 1. Visibility operations
        if constraint.has_visibility_ops():
            if constraint.show_fields:
                self._action_show_fields(constraint.show_fields)
            if constraint.hide_fields:
                self._action_hide_fields(constraint.hide_fields)
            operations_performed.append("visibility")
            self._operation_execution_counts['visibility'] += 1

        # 2. Calculation operation
        if constraint.has_calculation_op():
            self._action_calculate(constraint)
            operations_performed.append("calculation")
            self._operation_execution_counts['calculation'] += 1

        # 3. Generation operation
        if constraint.has_generation_op():
            self._action_generate(constraint, trigger_values)
            operations_performed.append("generation")
            self._operation_execution_counts['generation'] += 1

        # 4. Population operation (can be skipped if already executed)
        if constraint.has_population_op() and not skip_population:
            self._action_populate(constraint, trigger_values)
            operations_performed.append("population")
            self._operation_execution_counts['population'] += 1

        # 5. Filtering operation
        if constraint.has_filter_op():
            self._action_filter(constraint, trigger_values)
            operations_performed.append("filtering")
            self._operation_execution_counts['filtering'] += 1

        return operations_performed

    def _should_apply_inverse(self, constraint: Constraint) -> bool:
        """
        Determine if inverse operations should be applied for this constraint.

        Inverse operations are only applied for constraints that manage visibility
        in ONE direction (either showFields OR hideFields, but not both).

        Constraints with both showFields AND hideFields are "complete" constraints
        that explicitly define the entire visibility state, so they don't need inversion.
        This prevents conflicts in mutually exclusive constraints (e.g., shape selection).

        Args:
            constraint: Constraint to check

        Returns:
            True if inverse operations should be applied
        """
        if not constraint.has_visibility_ops():
            return False

        # Check if constraint has both show and hide operations
        has_show = constraint.show_fields is not None and len(constraint.show_fields) > 0
        has_hide = constraint.hide_fields is not None and len(constraint.hide_fields) > 0

        # Only apply inverse if constraint has EITHER show OR hide, but not both
        return has_show != has_hide  # XOR: True if only one is True

    def _apply_inverse_operations(self, constraint: Constraint) -> List[str]:
        """
        Apply inverse operations when condition is not met.

        Only visibility operations have meaningful inverses.
        Calculations and generations are not inversed (they're skipped).

        Args:
            constraint: Constraint to apply inverse

        Returns:
            List of operation names that were inversed
        """
        operations_performed = []

        # Only invert visibility operations
        if constraint.has_visibility_ops():
            if constraint.show_fields:
                self._action_hide_fields(constraint.show_fields)
            if constraint.hide_fields:
                self._action_show_fields(constraint.hide_fields)
            operations_performed.append("visibility_inverse")

        return operations_performed
    
    def _action_show_fields(self, field_uris: List[str]):
        """
        Show specified fields in the form.

        Args:
            field_uris: List of property URIs to show
        """
        for field_uri in field_uris:
            self._set_field_visibility(field_uri, True)
        self.logger.debug(f"Showing {len(field_uris)} fields")

    def _action_hide_fields(self, field_uris: List[str]):
        """
        Hide specified fields in the form.

        Args:
            field_uris: List of property URIs to hide
        """
        for field_uri in field_uris:
            self._set_field_visibility(field_uri, False)
        self.logger.debug(f"Hiding {len(field_uris)} fields")

    def _action_require_fields(self, field_uris: List[str], required: bool):
        """
        Set fields as required or optional.

        Args:
            field_uris: List of property URIs to update
            required: True to mark as required, False for optional
        """
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
        """Perform calculation operation."""
        try:
            # Get input values (pass property URIs directly)
            input_values = {}
            for input_prop in constraint.calculation_inputs:
                if input_prop in self.active_form.form_fields:
                    field = self.active_form.form_fields[input_prop]
                    value = self._extract_widget_value(field.widget)
                    input_values[input_prop] = value
                    self.logger.debug(f"Calculation input: {input_prop} = {value}")

            # Perform calculation
            result = self.calculation_engine.calculate(
                constraint.calculation_function,
                **input_values
            )

            if result is not None:
                # Set result in target field
                self._set_widget_value(constraint.calculation_target, result)
                self.logger.info(
                    f"Calculation result: {constraint.calculation_function} = {result} "
                    f"-> {constraint.calculation_target}"
                )
                self.calculation_performed.emit(constraint.calculation_target, result)
                self._signal_emission_counts['calculation_performed'] += 1

        except Exception as e:
            self.logger.error(f"Calculation failed: {e}", exc_info=True)
            self.error_occurred.emit(constraint.uri, str(e))
    
    def _action_generate(self, constraint: Constraint, trigger_values: Dict[str, Any]):
        """Generate value from template operation."""
        try:
            # Skip generation during loading mode to preserve loaded values
            if self._loading_mode:
                self.logger.debug(
                    f"Skipping generation for {constraint.generation_target} (loading mode active)"
                )
                return

            # Prepare inputs for generation (pass property URIs directly)
            inputs = {}
            for input_prop in constraint.generation_inputs:
                if input_prop in trigger_values:
                    inputs[input_prop] = trigger_values[input_prop]
                    self.logger.debug(f"Generation input: {input_prop} = {trigger_values[input_prop]}")

            # Extract material code using the generation engine
            # The engine will search for any key containing 'Material'
            material_code = self.generation_engine._extract_material_code(**inputs)
            self.logger.debug(f"Extracted material code: '{material_code}'")

            # Prepare template inputs with simple names
            template_inputs = {"materialCode": material_code}

            # Check if template requires sequence number and add it automatically
            if "{sequence}" in constraint.generation_template:
                if material_code and material_code != "UNKNOWN":
                    # Get next sequence number for this material
                    sequence = self.generation_engine._get_next_specimen_sequence(material_code)
                    self.logger.debug(f"Generated sequence number {sequence} for material code '{material_code}'")
                else:
                    # Default to sequence 1 if material code unavailable
                    sequence = 1
                    self.logger.warning(f"Material code extraction failed (got '{material_code}'), using sequence 1")

                # Add sequence to template inputs
                template_inputs["sequence"] = sequence

            # Generate value
            result = self.generation_engine.generate(
                constraint.generation_template,
                template_inputs
            )

            # Set result in target field
            self._set_widget_value(constraint.generation_target, result)
            self.logger.info(
                f"Generation result: '{result}' -> {constraint.generation_target}"
            )
            self.generation_performed.emit(constraint.generation_target, result)
            self._signal_emission_counts['generation_performed'] += 1

        except Exception as e:
            self.logger.error(f"Generation failed: {e}")
            self.error_occurred.emit(constraint.uri, str(e))

    def _action_filter(self, constraint: Constraint, trigger_values: Dict[str, Any]):
        """
          Apply filtering operations to ObjectProperty dropdown widgets.

          This filters the available choices in dropdown widgets based on class membership.
          Only affects fields specified in apply_to_fields.

          Args:
              constraint: Constraint with filter operations
              trigger_values: Current trigger values (not currently used but kept for consistency)
          """

        try:
            # Determine which fields the filtering applies to
            target_fields = constraint.apply_to_fields if constraint.apply_to_fields is not None else []

            if not target_fields:
                self.logger.warning(f"Filter constraint {constraint.label} has no target fields")

            self.logger.info(f"Applying filters to {len(target_fields)} fields")

            # Apply filters to each target field
            for field_uri in target_fields:
                widget_info = self.active_form.form_fields.get(field_uri)

                if not widget_info:
                    self.logger.warning(f"Field {field_uri} not found in form")
                    continue

                widget = widget_info.widget

                # Only apply to QComboBox widgets (ObjectProperty dropdowns)
                if not isinstance(widget, QComboBox):
                    self.logger.debug(f"Skipping {field_uri} - not a combo box")
                    continue

                # Get the property metadata to find the range class
                prop_metadata =  widget_info.property_metadata
                if not prop_metadata or not hasattr(prop_metadata, 'range_class'):
                    self.logger.warning(f"Cannot filter {field_uri} - no range class info")
                    continue

                # Apply the filter by repopulating the combo box
                self._repopulate_combo_with_filter(
                    widget=widget,
                    range_class=prop_metadata.range_class,
                    exclude_classes=constraint.exclude_classes,
                    filter_by_classes=constraint.filter_by_classes,
                    is_required=prop_metadata.is_required
                )

                self.logger.info(f"Applied filter to {field_uri}")

        except Exception as e:
            self.logger.error(f"Filter operation failed: {e}", exc_info=True)
            self.error_occurred.emit(constraint.uri, str(e))

    def _action_populate(self, constraint: Constraint, trigger_values: Dict[str, Any]):
        """
        Apply population operations - populate fields from a selected individual's properties.

        This operation queries the ontology for the selected individual's properties
        and populates corresponding form fields or PropertyDisplayWidget instances.

        Args:
            constraint: Constraint with population operations
            trigger_values: Current trigger values (should contain the selected individual URI)
        """
        try:
            if not constraint.populate_fields:
                return

            # Get the trigger value (selected individual URI)
            # Assume single trigger for population constraints
            if not constraint.triggers:
                self.logger.warning("Population constraint has no triggers")
                return

            trigger_property = constraint.triggers[0]
            selected_individual_uri = trigger_values.get(trigger_property)

            # Check if no valid individual selected (None, empty, or placeholder text)
            is_placeholder = (
                not selected_individual_uri or
                selected_individual_uri == "" or
                str(selected_individual_uri).startswith("(")
            )

            # Check if this is a PropertyDisplayWidget constraint
            is_display_widget = constraint.target_widget is not None

            if is_placeholder:
                self.logger.debug("No individual selected for population")

                if is_display_widget:
                    # Clear PropertyDisplayWidget
                    display_widget = self.property_display_widgets.get(constraint.uri)
                    if display_widget:
                        display_widget.clear()
                else:
                    # Reset populated fields to defaults and re-enable them when selection is cleared
                    for property_uri, _ in constraint.populate_fields:
                        if property_uri in self.active_form.form_fields:
                            self._reset_widget_to_default(property_uri)
                            # Always re-enable fields when clearing selection
                            # (make_read_only only applies when a batch IS selected)
                            self._set_widget_enabled(property_uri, True)
                return

            self.logger.info(
                f"Populating {len(constraint.populate_fields)} fields from {selected_individual_uri}"
            )

            # Query property values from ontology - need to handle nested properties
            # For bar material properties, query both bar properties and follow material link
            property_values = self._query_nested_properties(
                selected_individual_uri,
                constraint.populate_fields
            )

            if is_display_widget:
                # Populate PropertyDisplayWidget using the new ontology-driven API
                display_widget = self.property_display_widgets.get(constraint.uri)
                if display_widget:
                    # Use setIndividual for ontology-driven property display
                    # The widget's config (set during setup) handles property resolution
                    display_widget.setIndividual(selected_individual_uri)
                    self.logger.debug(f"Updated PropertyDisplayWidget with {len(display_data)} properties")
            else:
                # Populate regular form fields
                populated_trigger_properties = []
                for property_uri, display_label in constraint.populate_fields:
                    value = property_values.get(property_uri)

                    if value:
                        self.logger.debug(f"  Setting {property_uri} = {value}")
                        self._set_widget_value(property_uri, value)

                        # Make read-only if requested
                        if constraint.make_read_only:
                            self._set_widget_enabled(property_uri, False)

                        # Track if this is a trigger property for any constraint
                        if self._is_trigger_property(property_uri):
                            populated_trigger_properties.append(property_uri)
                    else:
                        # No value found - reset to default, keep read-only state
                        self.logger.debug(f"  No value found for {property_uri}, resetting to default")
                        self._reset_widget_to_default(property_uri)
                        # Keep disabled if make_read_only is True
                        if not constraint.make_read_only:
                            self._set_widget_enabled(property_uri, True)

                # Re-evaluate constraints for any populated trigger properties
                # This ensures visibility/other constraints respond to programmatically set values
                for trigger_prop in populated_trigger_properties:
                    self.logger.debug(f"Re-evaluating constraints for populated trigger: {trigger_prop}")
                    self._on_trigger_changed(trigger_prop)

        except Exception as e:
            self.logger.error(f"Population operation failed: {e}", exc_info=True)
            self.error_occurred.emit(constraint.uri, str(e))

    def _query_nested_properties(self, individual_uri: str, populate_fields: List[tuple]) -> Dict[str, Any]:
        """
        Query properties, following object property links when needed.

        For bar individuals, this queries the bar's direct properties and follows
        the hasMaterial link to get material properties.

        Args:
            individual_uri: URI of the individual to query
            populate_fields: List of (property_uri, display_label) tuples

        Returns:
            Dictionary mapping property URIs to values
        """
        property_uris = [prop_uri for prop_uri, _ in populate_fields]

        # First, query direct properties
        property_values = self.ontology_manager.get_individual_property_values(
            individual_uri,
            property_uris
        )

        # Check if any requested properties are missing (they might be on a related individual)
        missing_properties = [uri for uri in property_uris if uri not in property_values]

        if missing_properties:
            # Check if this individual has a hasMaterial property
            material_uri_result = self.ontology_manager.get_individual_property_values(
                individual_uri,
                ['dyn:hasMaterial']
            )

            material_uri = material_uri_result.get('dyn:hasMaterial')
            if material_uri:
                # Query material properties
                material_properties = self.ontology_manager.get_individual_property_values(
                    material_uri,
                    missing_properties
                )
                # Merge material properties into result
                property_values.update(material_properties)

                # Also add the material name/URI itself if requested
                if 'dyn:hasMaterial' in property_uris:
                    property_values['dyn:hasMaterial'] = material_uri

        return property_values

    def _is_trigger_property(self, property_uri: str) -> bool:
        """
        Check if a property is a trigger for any constraint.

        Args:
            property_uri: URI of the property to check

        Returns:
            True if property is a trigger for any constraint
        """
        return property_uri in self.constraints_by_trigger

    # ============================================================================
    # WIDGET VALUE HELPERS
    # ============================================================================
    
    def _extract_widget_value(self, widget: QWidget) -> Any:
        """Extract current value from a widget.

        For QComboBox: Returns URI from currentData() if available, otherwise currentText()
        For QListWidget: Returns list of URIs from selected items
        For other widgets: Returns their native value
        """
        # Import UnitValueWidget here to avoid circular imports
        try:
            from ..widgets.base.unit_value_widget import UnitValueWidget
        except ImportError:
            UnitValueWidget = None

        if isinstance(widget, QComboBox):
            # QComboBox should store URI in currentData()
            data = widget.currentData()
            # Check if data is empty string (e.g., "(Select...)" option)
            if data == "":
                # Return the text so constraints can match against placeholder text
                return widget.currentText()
            if data:
                # Check if it's a URI
                data_str = str(data)
                if '#' in data_str or '/' in data_str:
                    return data_str
                # If not a URI, might be stored differently
                return data
            # Fallback to text if no data stored (for combos without proper data setup)
            return widget.currentText()
        elif isinstance(widget, QListWidget):
            # QListWidget (multi-select) returns list of URIs
            selected_uris = []
            for item in widget.selectedItems():
                uri = item.data(Qt.ItemDataRole.UserRole)
                if uri:
                    selected_uris.append(str(uri))
            return selected_uris if selected_uris else None
        elif isinstance(widget, QLineEdit):
            return widget.text()
        elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            return widget.value()
        elif UnitValueWidget and isinstance(widget, UnitValueWidget):
            return widget.getValue()
        elif isinstance(widget, QCheckBox):
            return widget.isChecked()
        return None
    
    def _set_widget_value(self, property_uri: str, value: Any):
        """Set value in a widget."""
        if property_uri not in self.active_form.form_fields:
            return

        field = self.active_form.form_fields[property_uri]
        widget = field.widget

        from PyQt6.QtWidgets import QLabel

        # Import UnitValueWidget here to avoid circular imports
        try:
            from ..widgets.base.unit_value_widget import UnitValueWidget
        except ImportError:
            UnitValueWidget = None

        if isinstance(widget, QLabel):
            widget.setText(str(value))
        elif isinstance(widget, QLineEdit):
            widget.setText(str(value))
        elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            widget.setValue(float(value))
        elif UnitValueWidget and isinstance(widget, UnitValueWidget):
            widget.setValue(float(value))
        elif isinstance(widget, QCheckBox):
            widget.setChecked(bool(value))
        elif isinstance(widget, QComboBox):
            # For ObjectProperty combos, value is a URI - search by data
            value_str = str(value)

            # First try finding by data (URI)
            index = widget.findData(value_str)

            # If not found by data, try by text as fallback
            if index < 0:
                index = widget.findText(value_str)

            if index >= 0:
                widget.setCurrentIndex(index)
            else:
                self.logger.warning(f"Could not find combo item for value: {value_str}")
        elif isinstance(widget, QListWidget):
            # For multi-select QListWidget, value can be a single URI or list of URIs
            # Clear current selection
            widget.clearSelection()

            # Ensure value is a list
            if value is None:
                return
            value_list = value if isinstance(value, list) else [value]

            # Convert all values to strings
            value_strs = [str(v) for v in value_list]

            # Iterate through list items and select matching ones
            for i in range(widget.count()):
                item = widget.item(i)
                item_uri = item.data(Qt.ItemDataRole.UserRole)
                if item_uri and str(item_uri) in value_strs:
                    item.setSelected(True)
    
    def _set_field_visibility(self, field_uri: str, visible: bool):
        """Set visibility of a field and its label."""
        if field_uri not in self.active_form.form_fields:
            return

        field = self.active_form.form_fields[field_uri]

        # Hide/show the widget
        field.widget.setVisible(visible)

        # Hide/show the label if it exists
        if field.label_widget is not None:
            field.label_widget.setVisible(visible)

    def _set_widget_enabled(self, property_uri: str, enabled: bool):
        """
        Set enabled/disabled state of a widget.

        Args:
            property_uri: URI of the property
            enabled: True to enable, False to disable (make read-only)
        """
        if property_uri not in self.active_form.form_fields:
            return

        field = self.active_form.form_fields[property_uri]
        widget = field.widget

        # Set enabled state on the widget
        widget.setEnabled(enabled)

    def _reset_widget_to_default(self, property_uri: str):
        """
        Reset a widget to its default value.

        Args:
            property_uri: URI of the property
        """
        if property_uri not in self.active_form.form_fields:
            return

        field = self.active_form.form_fields[property_uri]
        widget = field.widget

        # Import UnitValueWidget here to avoid circular imports
        try:
            from ..widgets.base.unit_value_widget import UnitValueWidget
        except ImportError:
            UnitValueWidget = None

        # Reset to default based on widget type
        if isinstance(widget, QComboBox):
            # Reset to first item (usually "(Select...)")
            widget.setCurrentIndex(0)
        elif isinstance(widget, QListWidget):
            # Clear all selections
            widget.clearSelection()
        elif isinstance(widget, QLineEdit):
            widget.clear()
        elif isinstance(widget, QSpinBox):
            widget.setValue(0)
        elif isinstance(widget, QDoubleSpinBox):
            widget.setValue(0.0)
        elif UnitValueWidget and isinstance(widget, UnitValueWidget):
            widget.setValue(0.0)
        elif isinstance(widget, QCheckBox):
            widget.setChecked(False)

    def _repopulate_combo_with_filter(self, widget: QComboBox, range_class: str,
                                          exclude_classes: Optional[List[str]] = None,
                                          filter_by_classes: Optional[List[str]] = None,
                                          is_required: bool = False):
        """
        Repopulate a combo box with filtered choices.

        Args:
            widget: QComboBox to repopulate
            range_class: The range class for the property
            exclude_classes: List of class URIs to exclude individuals from
            filter_by_classes: List of class URIs to only include individuals from
            is_required: Whether the field is required (affects empty option)
        """
        # Store current selection
        current_value = widget.currentData()

        # Clear and repopulate
        widget.clear()

        # Add empty option for non-required fields
        if not is_required:
            widget.addItem("(Select...)", "")

        try:
            # Get all individuals of the range class
            result = self.ontology_manager.domain_queries.get_instances_of_class(
                range_class,
                include_subclasses=True
            )

            # Filter the results
            filtered_result = []
            for instance in result:
                instance_uri = instance['uri']

                # Apply exclude filter
                if exclude_classes:
                    should_exclude = False
                    for exclude_class in exclude_classes:
                        if self._is_instance_of_class(instance_uri, exclude_class):
                            should_exclude = True
                            self.logger.debug(f"Excluding {instance_uri} (instance of {exclude_class})")
                            break
                    if should_exclude:
                        continue

                # Apply positive filter
                if filter_by_classes:
                    should_include = False
                    for filter_class in filter_by_classes:
                        if self._is_instance_of_class(instance_uri, filter_class):
                            should_include = True
                            break
                    if not should_include:
                        self.logger.debug(f"Filtering out {instance_uri} (not instance of filter classes)")
                        continue

                # Passed all filters
                filtered_result.append(instance)

            # Add filtered items to combo box
            for instance in filtered_result:
                uri = instance['uri']
                display_name = instance['name']
                widget.addItem(display_name, uri)

            # Restore selection if it's still in the list
            if current_value:
                index = widget.findData(current_value)
                if index >= 0:
                    widget.setCurrentIndex(index)

            self.logger.info(f"Filtered combo box: {len(result)} -> {len(filtered_result)} items")

        except Exception as e:
            self.logger.error(f"Failed to repopulate combo with filter: {e}", exc_info=True)
            widget.addItem("(Error loading data)", "")
    
    # ============================================================================
    # PUBLIC API
    # ============================================================================
    
    def reload_constraints(self):
        """Reload constraints from TTL files."""
        self.constraint_manager.reload()
        if self.active_form and self.active_class_uri:
            self.setup_dependencies(self.active_form, self.active_class_uri)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive dependency manager statistics for testing and debugging.

        Returns:
            Dictionary following unified statistics structure:
            - configuration: Static setup (capabilities, manager status)
            - execution: Runtime operations (evaluations, executions, triggers)
            - health: Component health (active state, signal emissions)
            - errors: Error tracking
            - components: Nested ConstraintManager statistics
        """
        return {
            'configuration': {
                'constraint_manager_loaded': self.constraint_manager is not None,
                'available_calculations': len(self.calculation_engine.get_available_calculations()),
                'available_generators': len(self.generation_engine.get_available_generators())
            },
            'execution': {
                'total_evaluations': sum(self._constraint_evaluation_counts.values()),
                'constraint_evaluations': {
                    'by_constraint': dict(self._constraint_evaluation_counts)
                },
                'operation_executions': {
                    'by_type': dict(self._operation_execution_counts)
                },
                'trigger_fires': {
                    'by_property': dict(self._trigger_fire_counts)
                },
                'most_active_trigger': max(self._trigger_fire_counts.items(), key=lambda x: x[1])[0] if self._trigger_fire_counts else None
            },
            'health': {
                'active_state': {
                    'has_active_form': self.active_form is not None,
                    'active_class': self.active_class_uri,
                    'active_triggers': len(self.constraints_by_trigger),
                    'connected_signals': sum(len(constraints) for constraints in self.constraints_by_trigger.values())
                },
                'signal_emissions': dict(self._signal_emission_counts)
            },
            'errors': {
                'total_errors': len(self._recent_errors),
                'recent_errors': self._recent_errors[-5:]
            },
            'components': {
                'constraint_manager': self.constraint_manager.get_statistics()
            }
        }

    def get_constraint_activity(self) -> Dict[str, Any]:
        """
        Get detailed constraint activity report.

        Returns:
            Detailed activity metrics by constraint
        """
        return {
            'evaluations_by_constraint': dict(self._constraint_evaluation_counts),
            'triggers_by_frequency': sorted(
                self._trigger_fire_counts.items(),
                key=lambda x: x[1],
                reverse=True
            ),
            'operations_breakdown': dict(self._operation_execution_counts)
        }