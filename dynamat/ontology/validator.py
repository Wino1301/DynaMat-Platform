"""
DynaMat Platform - SHACL Validator
Validates instances and graphs against SHACL shapes for data quality assurance
Clean implementation using new architecture
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass
from enum import Enum

from rdflib import Graph, URIRef, Literal, BNode
from rdflib.namespace import RDF, RDFS, OWL, XSD

try:
    import pyshacl
    PYSHACL_AVAILABLE = True
except ImportError:
    PYSHACL_AVAILABLE = False

from .core.namespace_manager import NamespaceManager
from .query.sparql_executor import SPARQLExecutor
from ..config import config

logger = logging.getLogger(__name__)

if not PYSHACL_AVAILABLE:
    logger.warning("pyshacl not available, using basic validation only")


class ValidationSeverity(Enum):
    """Validation result severity levels"""
    INFO = "Info"
    WARNING = "Warning"
    VIOLATION = "Violation"
    ERROR = "Error"


@dataclass
class ValidationResult:
    """Single validation result"""
    severity: ValidationSeverity
    focus_node: str
    result_path: str
    value: str
    message: str
    source_constraint: str
    source_shape: str


@dataclass
class ValidationReport:
    """Complete validation report"""
    conforms: bool
    results: List[ValidationResult]
    graph_valid: bool
    total_results: int
    violations: int
    warnings: int
    infos: int


class SHACLValidator:
    """
    Validates RDF data against SHACL shapes for the DynaMat platform.
    
    Provides comprehensive validation with detailed error reporting
    and integration with the ontology management system.
    """
    
    def __init__(self, namespace_manager: NamespaceManager, sparql_executor: Optional[SPARQLExecutor] = None,
                 shapes_dir: Optional[Path] = None):
        """
        Initialize the SHACL validator.
        
        Args:
            namespace_manager: Namespace manager for URI handling
            sparql_executor: Optional SPARQL executor for advanced validation queries
            shapes_dir: Path to SHACL shapes directory
        """
        self.ns_manager = namespace_manager
        self.sparql_executor = sparql_executor
        self.shapes_dir = shapes_dir or (config.PROJECT_ROOT / "dynamat" / "ontology" / "shapes")
        
        # Load SHACL shapes
        self.shapes_graph = Graph()
        self.ns_manager.setup_graph_namespaces(self.shapes_graph)
        
        try:
            self._load_shacl_shapes()
        except Exception as e:
            logger.warning(f"Failed to load SHACL shapes: {e}")
        
        # Validation configuration
        self.strict_mode = False
        self.custom_rules = {}
        
        logger.info(f"SHACL validator initialized with {len(self.shapes_graph)} shape triples")
    
    def _load_shacl_shapes(self):
        """Load all SHACL shape files."""
        if not self.shapes_dir.exists():
            logger.warning(f"SHACL shapes directory not found: {self.shapes_dir}")
            return
        
        shape_files = list(self.shapes_dir.glob("*.ttl"))
        loaded_count = 0
        
        for shape_file in shape_files:
            try:
                self.shapes_graph.parse(shape_file, format="turtle")
                loaded_count += 1
                logger.debug(f"Loaded SHACL shapes from: {shape_file}")
            except Exception as e:
                logger.error(f"Failed to load SHACL shapes from {shape_file}: {e}")
        
        logger.info(f"Loaded SHACL shapes from {loaded_count} files")
    
    def validate_graph(self, data_graph: Graph, advanced_validation: bool = True) -> ValidationReport:
        """
        Validate an RDF graph against SHACL shapes.
        
        Args:
            data_graph: RDF graph to validate
            advanced_validation: Whether to perform advanced validation checks
            
        Returns:
            ValidationReport with detailed results
        """
        logger.info("Starting graph validation")
        
        # Basic validation results
        results = []
        
        # PyShacl validation if available
        if PYSHACL_AVAILABLE and len(self.shapes_graph) > 0:
            try:
                conforms, validation_graph, validation_text = pyshacl.validate(
                    data_graph,
                    shacl_graph=self.shapes_graph,
                    inference='rdfs',  # Enable RDFS inference
                    abort_on_first_error=False,
                    allow_warnings=True,
                    meta_shacl=False,
                    advanced=advanced_validation,
                    js=False  # Disable JavaScript execution
                )
                
                # Parse PyShacl results
                pyshacl_results = self._parse_pyshacl_results(validation_graph)
                results.extend(pyshacl_results)
                
                logger.info(f"PyShacl validation completed: conforms={conforms}")
                
            except Exception as e:
                logger.error(f"PyShacl validation failed: {e}")
                conforms = False
                results.append(ValidationResult(
                    severity=ValidationSeverity.ERROR,
                    focus_node="",
                    result_path="",
                    value="",
                    message=f"PyShacl validation error: {str(e)}",
                    source_constraint="",
                    source_shape=""
                ))
        else:
            # Fallback to basic validation
            logger.info("Using basic validation (PyShacl not available or no shapes loaded)")
            conforms = True
            basic_results = self._basic_validation(data_graph)
            results.extend(basic_results)
            conforms = all(r.severity != ValidationSeverity.VIOLATION for r in basic_results)
        
        # Custom validation rules
        custom_results = self._apply_custom_rules(data_graph)
        results.extend(custom_results)
        
        # Count results by severity
        violations = sum(1 for r in results if r.severity == ValidationSeverity.VIOLATION)
        warnings = sum(1 for r in results if r.severity == ValidationSeverity.WARNING)
        infos = sum(1 for r in results if r.severity == ValidationSeverity.INFO)
        
        # Update conformance based on violations
        if violations > 0:
            conforms = False
        
        report = ValidationReport(
            conforms=conforms,
            results=results,
            graph_valid=conforms,
            total_results=len(results),
            violations=violations,
            warnings=warnings,
            infos=infos
        )
        
        logger.info(f"Validation completed: {violations} violations, {warnings} warnings, {infos} info")
        return report
    
    def _parse_pyshacl_results(self, validation_graph: Graph) -> List[ValidationResult]:
        """Parse PyShacl validation results from the validation graph."""
        results = []
        
        # Query for validation results
        sh_namespace = self.ns_manager.SH
        
        for result_node in validation_graph.subjects(RDF.type, sh_namespace.ValidationResult):
            try:
                # Extract result details
                severity_node = validation_graph.value(result_node, sh_namespace.resultSeverity)
                focus_node = validation_graph.value(result_node, sh_namespace.focusNode)
                result_path = validation_graph.value(result_node, sh_namespace.resultPath)
                value = validation_graph.value(result_node, sh_namespace.value)
                message = validation_graph.value(result_node, sh_namespace.resultMessage)
                source_constraint = validation_graph.value(result_node, sh_namespace.sourceConstraintComponent)
                source_shape = validation_graph.value(result_node, sh_namespace.sourceShape)
                
                # Map severity
                severity = self._map_severity(str(severity_node) if severity_node else "")
                
                result = ValidationResult(
                    severity=severity,
                    focus_node=str(focus_node) if focus_node else "",
                    result_path=str(result_path) if result_path else "",
                    value=str(value) if value else "",
                    message=str(message) if message else "",
                    source_constraint=str(source_constraint) if source_constraint else "",
                    source_shape=str(source_shape) if source_shape else ""
                )
                
                results.append(result)
                
            except Exception as e:
                logger.error(f"Failed to parse validation result: {e}")
        
        return results
    
    def _map_severity(self, severity_uri: str) -> ValidationSeverity:
        """Map SHACL severity URI to ValidationSeverity enum."""
        if "Violation" in severity_uri:
            return ValidationSeverity.VIOLATION
        elif "Warning" in severity_uri:
            return ValidationSeverity.WARNING
        elif "Info" in severity_uri:
            return ValidationSeverity.INFO
        else:
            return ValidationSeverity.ERROR
    
    def _basic_validation(self, data_graph: Graph) -> List[ValidationResult]:
        """Perform basic validation when PyShacl is not available."""
        results = []
        
        # Check for basic RDF structure
        if len(data_graph) == 0:
            results.append(ValidationResult(
                severity=ValidationSeverity.WARNING,
                focus_node="",
                result_path="",
                value="",
                message="Graph is empty",
                source_constraint="basic_validation",
                source_shape="graph_structure"
            ))
        
        # Check for required classes
        required_classes = [self.ns_manager.DYN.Specimen, self.ns_manager.DYN.Material]
        
        for required_class in required_classes:
            instances = list(data_graph.subjects(RDF.type, required_class))
            if not instances:
                results.append(ValidationResult(
                    severity=ValidationSeverity.INFO,
                    focus_node="",
                    result_path="",
                    value="",
                    message=f"No instances of {required_class} found",
                    source_constraint="basic_validation",
                    source_shape="required_classes"
                ))
        
        # Check for orphaned resources
        all_subjects = set(data_graph.subjects())
        all_objects = set(obj for obj in data_graph.objects() if isinstance(obj, URIRef))
        
        orphaned = all_objects - all_subjects
        for orphan in orphaned:
            if str(orphan).startswith(str(self.ns_manager.DYN)):  # Only check our namespace
                results.append(ValidationResult(
                    severity=ValidationSeverity.WARNING,
                    focus_node=str(orphan),
                    result_path="",
                    value="",
                    message="Referenced resource not defined in graph",
                    source_constraint="basic_validation",
                    source_shape="orphaned_resources"
                ))
        
        return results
    
    def _apply_custom_rules(self, data_graph: Graph) -> List[ValidationResult]:
        """Apply custom validation rules."""
        results = []
        
        for rule_name, rule_func in self.custom_rules.items():
            try:
                rule_results = rule_func(data_graph, self.ns_manager)
                results.extend(rule_results)
            except Exception as e:
                logger.error(f"Custom rule {rule_name} failed: {e}")
                results.append(ValidationResult(
                    severity=ValidationSeverity.ERROR,
                    focus_node="",
                    result_path="",
                    value="",
                    message=f"Custom rule error: {str(e)}",
                    source_constraint=rule_name,
                    source_shape="custom_rules"
                ))
        
        return results
    
    def validate_instance(self, instance_uri: str, data_graph: Graph) -> ValidationReport:
        """
        Validate a specific instance.
        
        Args:
            instance_uri: URI of the instance to validate
            data_graph: Graph containing the instance
            
        Returns:
            ValidationReport for the specific instance
        """
        # Create a subgraph containing only the instance and related data
        instance_graph = Graph()
        self.ns_manager.setup_graph_namespaces(instance_graph)
        
        instance_ref = URIRef(instance_uri)
        
        # Add all triples where the instance is the subject
        for pred, obj in data_graph.predicate_objects(instance_ref):
            instance_graph.add((instance_ref, pred, obj))
        
        # Add type information and related resources
        for subj, pred, obj in data_graph:
            if obj == instance_ref:
                instance_graph.add((subj, pred, obj))
        
        # Validate the instance graph
        return self.validate_graph(instance_graph)
    
    def add_custom_rule(self, rule_name: str, rule_function):
        """
        Add a custom validation rule.
        
        Args:
            rule_name: Name of the custom rule
            rule_function: Function that takes (graph, namespace_manager) and returns List[ValidationResult]
        """
        self.custom_rules[rule_name] = rule_function
        logger.info(f"Added custom validation rule: {rule_name}")
    
    def remove_custom_rule(self, rule_name: str):
        """Remove a custom validation rule."""
        if rule_name in self.custom_rules:
            del self.custom_rules[rule_name]
            logger.info(f"Removed custom validation rule: {rule_name}")
    
    def get_shape_info(self) -> Dict[str, Any]:
        """Get information about loaded SHACL shapes."""
        if len(self.shapes_graph) == 0:
            return {"shapes_loaded": 0, "shapes_available": False}
        
        # Count different types of shapes
        sh_namespace = self.ns_manager.SH
        node_shapes = len(list(self.shapes_graph.subjects(RDF.type, sh_namespace.NodeShape)))
        property_shapes = len(list(self.shapes_graph.subjects(RDF.type, sh_namespace.PropertyShape)))
        
        return {
            "shapes_loaded": len(self.shapes_graph),
            "shapes_available": True,
            "node_shapes": node_shapes,
            "property_shapes": property_shapes,
            "pyshacl_available": PYSHACL_AVAILABLE,
            "shapes_directory": str(self.shapes_dir)
        }
    
    def reload_shapes(self):
        """Reload SHACL shapes from disk."""
        self.shapes_graph = Graph()
        self.ns_manager.setup_graph_namespaces(self.shapes_graph)
        self._load_shacl_shapes()
        logger.info("SHACL shapes reloaded from disk")
    
    def set_strict_mode(self, strict: bool):
        """Set strict validation mode."""
        self.strict_mode = strict
        logger.info(f"Strict validation mode: {'enabled' if strict else 'disabled'}")
    
    def validate_file(self, file_path: Path, file_format: str = "turtle") -> ValidationReport:
        """
        Validate a TTL file.
        
        Args:
            file_path: Path to the file to validate
            file_format: RDF format of the file
            
        Returns:
            ValidationReport for the file
        """
        try:
            # Load the file into a graph
            data_graph = Graph()
            self.ns_manager.setup_graph_namespaces(data_graph)
            data_graph.parse(file_path, format=file_format)
            
            logger.info(f"Validating file: {file_path}")
            return self.validate_graph(data_graph)
            
        except Exception as e:
            logger.error(f"Failed to validate file {file_path}: {e}")
            return ValidationReport(
                conforms=False,
                results=[ValidationResult(
                    severity=ValidationSeverity.ERROR,
                    focus_node="",
                    result_path="",
                    value="",
                    message=f"File validation error: {str(e)}",
                    source_constraint="file_validation",
                    source_shape=""
                )],
                graph_valid=False,
                total_results=1,
                violations=1,
                warnings=0,
                infos=0
            )