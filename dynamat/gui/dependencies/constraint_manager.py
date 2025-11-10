"""
DynaMat Platform - Constraint Manager
Loads and manages UI constraints from ontology TTL files
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
    """Logic gates for multiple triggers."""
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

    def has_visibility_ops(self) -> bool:
        """Check if constraint has visibility operations."""
        return bool(self.show_fields or self.hide_fields)

    def has_calculation_op(self) -> bool:
        """Check if constraint has calculation operation."""
        return bool(self.calculation_function and self.calculation_target)

    def has_generation_op(self) -> bool:
        """Check if constraint has generation operation."""
        return bool(self.generation_template and self.generation_target)


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
        
        self.logger.info(f"Constraint manager initialized with {len(self.constraints_by_uri)} constraints")
    
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
                generation_inputs=gen_inputs if gen_inputs else None
            )

            # Log what operations this constraint has
            ops = []
            if constraint.has_visibility_ops():
                ops.append("visibility")
            if constraint.has_calculation_op():
                ops.append("calculation")
            if constraint.has_generation_op():
                ops.append("generation")

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
    
    # ============================================================================
    # PUBLIC API
    # ============================================================================
    
    def get_constraints_for_class(self, class_uri: str) -> List[Constraint]:
        """
        Get all constraints for a specific class.
        
        Args:
            class_uri: URI of the class
            
        Returns:
            List of constraints, sorted by priority
        """
        constraints = self.constraints_by_class.get(class_uri, [])
        return sorted(constraints, key=lambda c: c.priority)
    
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
        """Get statistics about loaded constraints."""
        operation_counts = {
            'visibility': 0,
            'calculation': 0,
            'generation': 0,
            'multi_operation': 0
        }

        for constraint in self.constraints_by_uri.values():
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
            if ops_count > 1:
                operation_counts['multi_operation'] += 1

        return {
            'total_constraints': len(self.constraints_by_uri),
            'classes_with_constraints': len(self.constraints_by_class),
            'operations': operation_counts,
            'constraint_directory': str(self.constraint_dir)
        }