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
        # Query for all constraints
        query = """
        SELECT ?constraint ?label ?comment ?type ?forClass ?triggers ?triggerLogic 
               ?whenValue ?affects ?action ?priority
               ?genTemplate ?genInputs ?calcFunc ?calcInputs
        WHERE {
            ?constraint a ?type .
            ?type rdfs:subClassOf* gui:Constraint .
            
            OPTIONAL { ?constraint rdfs:label ?label }
            OPTIONAL { ?constraint rdfs:comment ?comment }
            OPTIONAL { ?constraint gui:forClass ?forClass }
            OPTIONAL { ?constraint gui:triggers ?triggers }
            OPTIONAL { ?constraint gui:triggerLogic ?triggerLogic }
            OPTIONAL { ?constraint gui:whenValue ?whenValue }
            OPTIONAL { ?constraint gui:affects ?affects }
            OPTIONAL { ?constraint gui:action ?action }
            OPTIONAL { ?constraint gui:priority ?priority }
            
            # Generation-specific
            OPTIONAL { ?constraint gui:generationTemplate ?genTemplate }
            OPTIONAL { ?constraint gui:generationInputs ?genInputs }
            
            # Calculation-specific
            OPTIONAL { ?constraint gui:calculationFunction ?calcFunc }
            OPTIONAL { ?constraint gui:calculationInputs ?calcInputs }
        }
        """
        
        results = self.graph.query(query)
        
        for row in results:
            try:
                constraint = self._create_constraint_from_row(row)
                if constraint:
                    # Cache by URI
                    self.constraints_by_uri[constraint.uri] = constraint
                    
                    # Cache by class
                    if constraint.for_class not in self.constraints_by_class:
                        self.constraints_by_class[constraint.for_class] = []
                    self.constraints_by_class[constraint.for_class].append(constraint)
                    
            except Exception as e:
                self.logger.error(f"Failed to parse constraint: {e}")
    
    def _create_constraint_from_row(self, row) -> Optional[Constraint]:
        """Create a Constraint object from a SPARQL query row."""
        try:
            # Extract basic info
            uri = str(row.constraint)
            label = str(row.label) if row.label else ""
            comment = str(row.comment) if row.comment else ""
            
            # Determine constraint type
            type_uri = str(row.type)
            type_name = type_uri.split("#")[-1]
            constraint_type = ConstraintType(type_name)
            
            # Extract class
            for_class = str(row.forClass) if row.forClass else ""
            
            # Extract triggers (can be multiple)
            triggers = self._extract_list(row.triggers) if row.triggers else []
            
            # Extract trigger logic
            trigger_logic = None
            if row.triggerLogic:
                logic_name = str(row.triggerLogic).split("#")[-1]
                trigger_logic = TriggerLogic(logic_name)
            
            # Extract when values (can be multiple)
            when_values = self._extract_list(row.whenValue) if row.whenValue else []
            
            # Extract affects (can be multiple)
            affects = self._extract_list(row.affects) if row.affects else []
            
            # Extract action
            action_uri = str(row.action) if row.action else ""
            action_name = action_uri.split("#")[-1]
            action = Action(action_name)
            
            # Extract priority
            priority = int(row.priority) if row.priority else 999
            
            # Create constraint
            constraint = Constraint(
                uri=uri,
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
                constraint.generation_template = str(row.genTemplate) if row.genTemplate else None
                constraint.generation_inputs = self._extract_list(row.genInputs) if row.genInputs else []
            
            elif constraint_type == ConstraintType.CALCULATION:
                constraint.calculation_function = str(row.calcFunc) if row.calcFunc else None
                constraint.calculation_inputs = self._extract_list(row.calcInputs) if row.calcInputs else []
            
            return constraint
            
        except Exception as e:
            self.logger.error(f"Error creating constraint from row: {e}")
            return None
    
    def _extract_list(self, value: Any) -> List[str]:
        """Extract a list of URIs from an RDF value."""
        # Handle single values
        if isinstance(value, (URIRef, Literal)):
            return [str(value)]
        
        # Handle RDF lists
        if isinstance(value, list):
            return [str(v) for v in value]
        
        # Try to parse as RDF collection
        try:
            items = list(self.graph.items(value))
            return [str(item) for item in items]
        except:
            return [str(value)]
    
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