"""
DynaMat Platform - Constraint Manager

Loads and manages UI constraints from ontology TTL files. Parses constraint
definitions from TTL format into structured Constraint dataclass objects for
use by the DependencyManager.

Supports constraint types:
- Visibility: Show/hide fields based on trigger values
- Calculation: Compute derived values from inputs
- Generation: Generate IDs/codes from templates
- Population: Populate fields from selected individuals
- Filtering: Filter dropdown choices by class membership

Example:
    >>> from dynamat.gui.dependencies import ConstraintManager
    >>> manager = ConstraintManager(Path("ontology/constraints"))
    >>> constraints = manager.get_constraints_for_class("dyn:Specimen")
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS

logger = logging.getLogger(__name__)


class TriggerLogic(Enum):
    """
    Logic gates for evaluating multiple trigger conditions.

    Used when a constraint has multiple trigger properties to determine
    how their values should be combined.

    Attributes:
        ANY: Condition met if ANY trigger matches its expected value
        ALL: Condition met if ALL triggers match their expected values
        XOR: Condition met if exactly ONE trigger matches
    """
    ANY = "ANY"
    ALL = "ALL"
    XOR = "XOR"


@dataclass
class Constraint:
    """
    Represents a unified UI constraint with multiple possible operations.

    A constraint can perform multiple operations:
    - Visibility: show/hide fields
    - Calculation: compute derived values
    - Generation: generate IDs/codes from templates

    All operations within a constraint execute atomically when triggered.
    """
    uri: str
    label: str
    comment: str
    for_class: str
    triggers: List[str]
    trigger_logic: Optional[TriggerLogic]
    when_values: List[str]
    priority: int

    # Visibility operations
    show_fields: Optional[List[str]] = None
    hide_fields: Optional[List[str]] = None

    # Calculation operation
    calculation_function: Optional[str] = None
    calculation_target: Optional[str] = None
    calculation_inputs: Optional[List[str]] = None

    # Generation operation
    generation_template: Optional[str] = None
    generation_target: Optional[str] = None
    generation_inputs: Optional[List[str]] = None

    # Population operation
    populate_fields: Optional[List[tuple]] = None  # List of (source_property, target_property) tuples
    make_read_only: bool = False
    target_widget: Optional[str] = None  # Custom widget identifier (e.g., "BarMaterialProperties")

    # Filtering operations
    apply_to_fields: Optional[List[str]] = None
    exclude_classes: Optional[List[str]] = None
    filter_by_classes: Optional[List[str]] = None


    def has_visibility_ops(self) -> bool:
        """Check if constraint has visibility operations."""
        return bool(self.show_fields or self.hide_fields)

    def has_calculation_op(self) -> bool:
        """Check if constraint has calculation operation."""
        return bool(self.calculation_function and self.calculation_target)

    def has_generation_op(self) -> bool:
        """Check if constraint has generation operation."""
        return bool(self.generation_template and self.generation_target)

    def has_population_op(self) -> bool:
        """Check if constraint has population operation."""
        return bool(self.populate_fields)

    def has_filter_op(self) -> bool:
        """Check if constraint has filtering operations."""
        return bool(self.filter_by_classes or self.exclude_classes)

class ConstraintManager:
    """
    Manages UI constraints loaded from TTL files.
    
    Reads constraint definitions from the ontology and provides
    a structured interface for the dependency system.
    """
    
    def __init__(self, constraint_dir: Optional[Path] = None):
        """
        Initialize the constraint manager.
        
        Args:
            constraint_dir: Directory containing constraint TTL files
        """
        self.logger = logging.getLogger(__name__)
        self.constraint_dir = constraint_dir or self._get_default_constraint_dir()
        
        # Initialize RDF graph
        self.graph = Graph()
        
        # Define namespaces
        self.GUI = Namespace("https://dynamat.utep.edu/gui/constraints#")
        self.DYN = Namespace("https://dynamat.utep.edu/ontology#")
        self.graph.bind("gui", self.GUI)
        self.graph.bind("dyn", self.DYN)
        
        # Constraint cache
        self.constraints_by_class: Dict[str, List[Constraint]] = {}
        self.constraints_by_uri: Dict[str, Constraint] = {}
        
        # Load constraints
        self._load_constraints()
        
        self.logger.info(
            f"ConstraintManager initialized: {len(self.constraints_by_uri)} constraints "
            f"loaded for {len(self.constraints_by_class)} classes"
        )
    
    def _get_default_constraint_dir(self) -> Path:
        """Get default constraint directory."""
        # Assuming this file is in dynamat/gui/dependencies/
        return Path(__file__).parent.parent.parent / "ontology" / "constraints"
    
    def _load_constraints(self):
        """Load all constraint files from the constraint directory."""
        if not self.constraint_dir.exists():
            self.logger.warning(f"Constraint directory not found: {self.constraint_dir}")
            return
        
        # Load vocabulary first
        vocab_file = self.constraint_dir / "gui_constraint_vocabulary.ttl"
        if vocab_file.exists():
            try:
                self.graph.parse(vocab_file, format="turtle")
                self.logger.info(f"Loaded vocabulary from {vocab_file}")
            except Exception as e:
                self.logger.error(f"Failed to load vocabulary: {e}")
        
        # Load all rule files
        for rule_file in self.constraint_dir.glob("gui_*_rules.ttl"):
            try:
                self.graph.parse(rule_file, format="turtle")
                self.logger.info(f"Loaded rules from {rule_file}")
            except Exception as e:
                self.logger.error(f"Failed to load rules from {rule_file}: {e}")
        
        # Parse constraints from graph
        self._parse_constraints()
    
    def _parse_constraints(self):
        """Parse constraints from the RDF graph."""
        # Get all instances of gui:Constraint (unified type)
        constraint_query = """
        SELECT DISTINCT ?constraint
        WHERE {
            ?constraint a gui:Constraint .
        }
        """

        constraint_results = self.graph.query(constraint_query)

        # Process each constraint individually to collect all its properties
        for row in constraint_results:
            try:
                constraint_uri = str(row.constraint)
                constraint = self._parse_single_constraint(constraint_uri)

                if constraint:
                    # Cache by URI
                    self.constraints_by_uri[constraint.uri] = constraint

                    # Cache by class
                    if constraint.for_class not in self.constraints_by_class:
                        self.constraints_by_class[constraint.for_class] = []
                    self.constraints_by_class[constraint.for_class].append(constraint)

            except Exception as e:
                self.logger.error(f"Failed to parse constraint {row.constraint}: {e}", exc_info=True)

    def _parse_single_constraint(self, constraint_uri: str) -> Optional[Constraint]:
        """
        Parse a single constraint by URI, collecting all operation properties.

        Args:
            constraint_uri: URI of the constraint to parse

        Returns:
            Constraint object or None
        """
        from rdflib import URIRef

        constraint_ref = URIRef(constraint_uri)

        try:
            # Verify this is a Constraint instance
            if (constraint_ref, RDF.type, self.GUI.Constraint) not in self.graph:
                return None

            # Get core properties
            label = str(self.graph.value(constraint_ref, RDFS.label) or "")
            comment = str(self.graph.value(constraint_ref, RDFS.comment) or "")
            for_class = str(self.graph.value(constraint_ref, self.GUI.forClass) or "")
            trigger_logic_uri = self.graph.value(constraint_ref, self.GUI.triggerLogic)
            priority_val = self.graph.value(constraint_ref, self.GUI.priority)

            # Parse trigger logic
            trigger_logic = None
            if trigger_logic_uri:
                logic_name = str(trigger_logic_uri).split("#")[-1]
                trigger_logic = TriggerLogic(logic_name)

            # Parse priority
            priority = int(priority_val) if priority_val else 999

            # Get trigger properties
            triggers = self._get_all_values(constraint_ref, self.GUI.triggers)
            when_values = self._get_all_values(constraint_ref, self.GUI.whenValue)

            # Parse visibility operations
            show_fields = self._get_all_values(constraint_ref, self.GUI.showFields)
            hide_fields = self._get_all_values(constraint_ref, self.GUI.hideFields)

            # Parse calculation operation
            calc_func_uri = self.graph.value(constraint_ref, self.GUI.calculationFunction)
            calc_target_uri = self.graph.value(constraint_ref, self.GUI.calculationTarget)
            calc_inputs = self._get_all_values(constraint_ref, self.GUI.calculationInputs)

            calculation_function = str(calc_func_uri) if calc_func_uri else None
            calculation_target = str(calc_target_uri) if calc_target_uri else None

            # Parse generation operation
            gen_template_uri = self.graph.value(constraint_ref, self.GUI.generationTemplate)
            gen_target_uri = self.graph.value(constraint_ref, self.GUI.generationTarget)
            gen_inputs = self._get_all_values(constraint_ref, self.GUI.generationInputs)

            generation_template = str(gen_template_uri) if gen_template_uri else None
            generation_target = str(gen_target_uri) if gen_target_uri else None

            # Parse population operation
            populate_fields_raw = self._get_populate_fields(constraint_ref)
            make_read_only_val = self.graph.value(constraint_ref, self.GUI.makeReadOnly)
            make_read_only = bool(make_read_only_val) if make_read_only_val else False
            target_widget_val = self.graph.value(constraint_ref, self.GUI.targetWidget)
            target_widget = str(target_widget_val) if target_widget_val else None

            # Parse filtering operations
            apply_to_fields = self._get_all_values(constraint_ref, self.GUI.applyToFields)
            exclude_classes = self._get_all_values(constraint_ref, self.GUI.excludeClass)
            filter_by_classes = self._get_all_values(constraint_ref, self.GUI.filterByClass)

            # Create unified constraint
            constraint = Constraint(
                uri=constraint_uri,
                label=label,
                comment=comment,
                for_class=for_class,
                triggers=triggers,
                trigger_logic=trigger_logic,
                when_values=when_values,
                priority=priority,
                show_fields=show_fields if show_fields else None,
                hide_fields=hide_fields if hide_fields else None,
                calculation_function=calculation_function,
                calculation_target=calculation_target,
                calculation_inputs=calc_inputs if calc_inputs else None,
                generation_template=generation_template,
                generation_target=generation_target,
                generation_inputs=gen_inputs if gen_inputs else None,
                populate_fields=populate_fields_raw if populate_fields_raw else None,
                make_read_only=make_read_only,
                target_widget=target_widget,
                apply_to_fields=apply_to_fields if apply_to_fields else None,
                exclude_classes=exclude_classes if exclude_classes else None,
                filter_by_classes=filter_by_classes if filter_by_classes else None
            )

            # Log what operations this constraint has
            ops = []
            if constraint.has_visibility_ops():
                ops.append("visibility")
            if constraint.has_calculation_op():
                ops.append("calculation")
            if constraint.has_generation_op():
                ops.append("generation")
            if constraint.has_population_op():
                ops.append("population")
            if constraint.has_filter_op():
                ops.append("filtering")

            self.logger.debug(
                f"Parsed constraint {constraint.label}: "
                f"triggers={len(triggers)}, operations=[{', '.join(ops)}]"
            )

            return constraint

        except Exception as e:
            self.logger.error(f"Error parsing constraint {constraint_uri}: {e}", exc_info=True)
            return None

    def _get_all_values(self, subject: URIRef, predicate: URIRef) -> List[str]:
        """
        Get all values for a property (handles multiple property values and RDF lists).

        Args:
            subject: Subject URI
            predicate: Predicate URI

        Returns:
            List of all values as strings
        """
        from rdflib import RDF
        from rdflib.collection import Collection

        values = []
        for obj in self.graph.objects(subject, predicate):
            # Check if this is an RDF list (collection)
            if (obj, RDF.first, None) in self.graph:
                # This is an RDF list, parse it as a collection
                try:
                    collection = Collection(self.graph, obj)
                    for item in collection:
                        values.append(str(item))
                    self.logger.debug(f"Parsed RDF list with {len(values)} items")
                except Exception as e:
                    self.logger.error(f"Failed to parse RDF list: {e}")
                    values.append(str(obj))
            else:
                # Regular value
                values.append(str(obj))
        return values

    def _get_populate_fields(self, subject: URIRef) -> List[tuple]:
        """
        Parse gui:populateFields structure from TTL constraint.

        Expected structure in TTL:
        gui:populateFields (
            (dyn:hasMatrixMaterial "Matrix Material")
            (dyn:hasReinforcementMaterial "Reinforcement Material")
        ) ;

        Returns:
            List of (source_property_uri, display_label) tuples
        """
        from rdflib import RDF
        from rdflib.collection import Collection

        populate_fields = []

        # Get the RDF list for populateFields
        populate_list_obj = self.graph.value(subject, self.GUI.populateFields)

        if not populate_list_obj:
            return populate_fields

        try:
            # Parse outer list
            outer_collection = Collection(self.graph, populate_list_obj)

            for item in outer_collection:
                # Each item should be an inner list (pair)
                if (item, RDF.first, None) in self.graph:
                    inner_collection = Collection(self.graph, item)
                    inner_items = list(inner_collection)

                    if len(inner_items) >= 2:
                        # First is property URI, second is display label
                        property_uri = str(inner_items[0])
                        display_label = str(inner_items[1])
                        populate_fields.append((property_uri, display_label))
                    elif len(inner_items) == 1:
                        # Only property provided, use it as label too
                        property_uri = str(inner_items[0])
                        populate_fields.append((property_uri, property_uri))

        except Exception as e:
            self.logger.error(f"Failed to parse populateFields: {e}", exc_info=True)

        return populate_fields

    # ============================================================================
    # PUBLIC API
    # ============================================================================
    
    def get_constraints_for_class(self, class_uri: str) -> List[Constraint]:
        """
        Get all constraints for a specific class.

        Args:
            class_uri: URI of the class

        Returns:
            List of constraints, sorted by priority (higher values run first, lower values run last and can override)
        """
        constraints = self.constraints_by_class.get(class_uri, [])
        return sorted(constraints, key=lambda c: c.priority, reverse=True)
    
    def get_constraint(self, constraint_uri: str) -> Optional[Constraint]:
        """
        Get a specific constraint by URI.
        
        Args:
            constraint_uri: URI of the constraint
            
        Returns:
            Constraint object or None
        """
        return self.constraints_by_uri.get(constraint_uri)
    
    def get_constraints_by_trigger(self, class_uri: str, trigger_property: str) -> List[Constraint]:
        """
        Get all constraints triggered by a specific property.
        
        Args:
            class_uri: URI of the class
            trigger_property: URI of the trigger property
            
        Returns:
            List of constraints
        """
        all_constraints = self.get_constraints_for_class(class_uri)
        return [c for c in all_constraints if trigger_property in c.triggers]
    
    def get_generation_constraints(self, class_uri: str) -> List[Constraint]:
        """Get all constraints with generation operations for a class."""
        all_constraints = self.get_constraints_for_class(class_uri)
        return [c for c in all_constraints if c.has_generation_op()]

    def get_calculation_constraints(self, class_uri: str) -> List[Constraint]:
        """Get all constraints with calculation operations for a class."""
        all_constraints = self.get_constraints_for_class(class_uri)
        return [c for c in all_constraints if c.has_calculation_op()]

    def get_visibility_constraints(self, class_uri: str) -> List[Constraint]:
        """Get all constraints with visibility operations for a class."""
        all_constraints = self.get_constraints_for_class(class_uri)
        return [c for c in all_constraints if c.has_visibility_ops()]
    
    def reload(self):
        """Reload all constraints from files."""
        self.graph = Graph()
        self.graph.bind("gui", self.GUI)
        self.graph.bind("dyn", self.DYN)
        self.constraints_by_class.clear()
        self.constraints_by_uri.clear()
        self._load_constraints()
        self.logger.info("Constraints reloaded")
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive constraint manager statistics for testing and debugging.

        Returns:
            Dictionary following unified statistics structure:
            - configuration: Static setup (directory, counts)
            - execution: Runtime operations (future: lookups)
            - content: Domain-specific constraint characteristics
        """
        operation_counts = {
            'visibility': 0,
            'calculation': 0,
            'generation': 0,
            'population': 0,
            'filtering': 0,
            'multi_operation': 0
        }

        # Priority buckets
        priority_dist = {
            'low (1-100)': 0,
            'medium (101-500)': 0,
            'high (501+)': 0
        }

        # Trigger complexity
        trigger_complexity = {
            'single_trigger': 0,
            'multi_trigger': 0
        }

        # Trigger logic usage
        trigger_logic_usage = {
            'ANY': 0,
            'ALL': 0,
            'XOR': 0,
            'None': 0
        }

        for constraint in self.constraints_by_uri.values():
            # Count operations
            ops_count = 0
            if constraint.has_visibility_ops():
                operation_counts['visibility'] += 1
                ops_count += 1
            if constraint.has_calculation_op():
                operation_counts['calculation'] += 1
                ops_count += 1
            if constraint.has_generation_op():
                operation_counts['generation'] += 1
                ops_count += 1
            if constraint.has_population_op():
                operation_counts['population'] += 1
                ops_count += 1
            if constraint.has_filter_op():
                operation_counts['filtering'] += 1
                ops_count += 1
            if ops_count > 1:
                operation_counts['multi_operation'] += 1

            # Priority distribution
            if constraint.priority <= 100:
                priority_dist['low (1-100)'] += 1
            elif constraint.priority <= 500:
                priority_dist['medium (101-500)'] += 1
            else:
                priority_dist['high (501+)'] += 1

            # Trigger complexity
            if len(constraint.triggers) == 1:
                trigger_complexity['single_trigger'] += 1
            else:
                trigger_complexity['multi_trigger'] += 1

            # Trigger logic usage
            if constraint.trigger_logic == TriggerLogic.ANY:
                trigger_logic_usage['ANY'] += 1
            elif constraint.trigger_logic == TriggerLogic.ALL:
                trigger_logic_usage['ALL'] += 1
            elif constraint.trigger_logic == TriggerLogic.XOR:
                trigger_logic_usage['XOR'] += 1
            else:
                trigger_logic_usage['None'] += 1

        # Calculate average triggers per constraint
        total_triggers = sum(len(c.triggers) for c in self.constraints_by_uri.values())
        avg_triggers = total_triggers / len(self.constraints_by_uri) if self.constraints_by_uri else 0

        # Return unified structure
        return {
            'configuration': {
                'constraint_directory': str(self.constraint_dir),
                'total_constraints': len(self.constraints_by_uri),
                'classes_with_constraints': len(self.constraints_by_class)
            },
            'execution': {
                'total_lookups': 0  # Future: track constraint lookups
            },
            'health': {
                # Future: add constraint validation errors, load failures, etc.
            },
            'content': {
                'operations': operation_counts,
                'priority_distribution': priority_dist,
                'trigger_complexity': {
                    **trigger_complexity,
                    'average_triggers_per_constraint': round(avg_triggers, 2)
                },
                'trigger_logic_usage': trigger_logic_usage
            }
        }