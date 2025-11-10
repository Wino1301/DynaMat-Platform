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


class ConstraintType(Enum):
    """Types of constraints supported."""
    VISIBILITY = "VisibilityConstraint"
    REQUIREMENT = "RequirementConstraint"
    CALCULATION = "CalculationConstraint"
    GENERATION = "GenerationConstraint"
    MUTUAL_EXCLUSION = "MutualExclusionConstraint"


class TriggerLogic(Enum):
    """Logic gates for multiple triggers."""
    ANY = "ANY"
    ALL = "ALL"
    XOR = "XOR"


class Action(Enum):
    """Actions that constraints can perform."""
    SHOW = "show"
    HIDE = "hide"
    REQUIRE = "require"
    OPTIONAL = "optional"
    CALCULATE = "calculate"
    GENERATE = "generate"
    ENABLE = "enable"
    DISABLE = "disable"


@dataclass
class Constraint:
    """Represents a single UI constraint."""
    uri: str
    label: str
    comment: str
    constraint_type: ConstraintType
    for_class: str
    triggers: List[str]
    trigger_logic: Optional[TriggerLogic]
    when_values: List[str]
    affects: List[str]
    action: Action
    priority: int
    
    # Type-specific attributes
    generation_template: Optional[str] = None
    generation_inputs: Optional[List[str]] = None
    calculation_function: Optional[str] = None
    calculation_inputs: Optional[List[str]] = None


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
        # First, get all constraint URIs
        constraint_query = """
        SELECT DISTINCT ?constraint ?type
        WHERE {
            ?constraint a ?type .
            ?type rdfs:subClassOf* gui:Constraint .
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
        Parse a single constraint by URI, collecting all property values.

        Args:
            constraint_uri: URI of the constraint to parse

        Returns:
            Constraint object or None
        """
        from rdflib import URIRef

        constraint_ref = URIRef(constraint_uri)

        try:
            # Get constraint type
            type_uri = self.graph.value(constraint_ref, RDF.type)
            if not type_uri:
                return None

            type_name = str(type_uri).split("#")[-1]
            try:
                constraint_type = ConstraintType(type_name)
            except ValueError:
                self.logger.debug(f"Skipping non-constraint type: {type_name}")
                return None

            # Get single-value properties
            label = str(self.graph.value(constraint_ref, RDFS.label) or "")
            comment = str(self.graph.value(constraint_ref, RDFS.comment) or "")
            for_class = str(self.graph.value(constraint_ref, self.GUI.forClass) or "")
            trigger_logic_uri = self.graph.value(constraint_ref, self.GUI.triggerLogic)
            action_uri = self.graph.value(constraint_ref, self.GUI.action)
            priority_val = self.graph.value(constraint_ref, self.GUI.priority)

            # Parse trigger logic
            trigger_logic = None
            if trigger_logic_uri:
                logic_name = str(trigger_logic_uri).split("#")[-1]
                trigger_logic = TriggerLogic(logic_name)

            # Parse action
            if not action_uri:
                self.logger.warning(f"Constraint {constraint_uri} has no action")
                return None
            action_name = str(action_uri).split("#")[-1]
            action = Action(action_name)

            # Parse priority
            priority = int(priority_val) if priority_val else 999

            # Get multi-value properties (these can have multiple values)
            triggers = self._get_all_values(constraint_ref, self.GUI.triggers)
            when_values = self._get_all_values(constraint_ref, self.GUI.whenValue)
            affects = self._get_all_values(constraint_ref, self.GUI.affects)

            # Create constraint
            constraint = Constraint(
                uri=constraint_uri,
                label=label,
                comment=comment,
                constraint_type=constraint_type,
                for_class=for_class,
                triggers=triggers,
                trigger_logic=trigger_logic,
                when_values=when_values,
                affects=affects,
                action=action,
                priority=priority
            )

            # Add type-specific attributes
            if constraint_type == ConstraintType.GENERATION:
                gen_template = self.graph.value(constraint_ref, self.GUI.generationTemplate)
                constraint.generation_template = str(gen_template) if gen_template else None
                constraint.generation_inputs = self._get_all_values(constraint_ref, self.GUI.generationInputs)

            elif constraint_type == ConstraintType.CALCULATION:
                calc_func = self.graph.value(constraint_ref, self.GUI.calculationFunction)
                constraint.calculation_function = str(calc_func) if calc_func else None
                constraint.calculation_inputs = self._get_all_values(constraint_ref, self.GUI.calculationInputs)

            self.logger.debug(
                f"Parsed constraint {constraint.label}: "
                f"triggers={len(triggers)}, whenValues={len(when_values)}, affects={len(affects)}"
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
        """Get all generation constraints for a class."""
        all_constraints = self.get_constraints_for_class(class_uri)
        return [c for c in all_constraints if c.constraint_type == ConstraintType.GENERATION]
    
    def get_calculation_constraints(self, class_uri: str) -> List[Constraint]:
        """Get all calculation constraints for a class."""
        all_constraints = self.get_constraints_for_class(class_uri)
        return [c for c in all_constraints if c.constraint_type == ConstraintType.CALCULATION]
    
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
        type_counts = {}
        for constraint in self.constraints_by_uri.values():
            type_name = constraint.constraint_type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1
        
        return {
            'total_constraints': len(self.constraints_by_uri),
            'classes_with_constraints': len(self.constraints_by_class),
            'constraints_by_type': type_counts,
            'constraint_directory': str(self.constraint_dir)
        }