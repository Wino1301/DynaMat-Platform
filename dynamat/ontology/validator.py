"""
DynaMat Platform - SHACL Validator
Validates instances and graphs against SHACL shapes for data quality assurance
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass
from enum import Enum

import rdflib
from rdflib import Graph, Namespace, URIRef, Literal, BNode
from rdflib.namespace import RDF, RDFS, OWL, XSD

try:
    import pyshacl
    PYSHACL_AVAILABLE = True
except ImportError:
    PYSHACL_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("pyshacl not available, using basic validation")

from .manager import OntologyManager
from ..config import config


logger = logging.getLogger(__name__)


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
    
    def __init__(self, ontology_manager: OntologyManager, shapes_dir: Optional[Path] = None):
        """
        Initialize the SHACL validator.
        
        Args:
            ontology_manager: Main ontology manager instance
            shapes_dir: Path to SHACL shapes directory
        """
        self.manager = ontology_manager
        self.shapes_dir = shapes_dir or (config.ONTOLOGY_DIR / "shapes")
        
        # Load SHACL shapes
        self.shapes_graph = Graph()
        self._load_shacl_shapes()
        
        # Setup namespaces
        self.DYN = self.manager.DYN
        self.SH = Namespace("http://www.w3.org/ns/shacl#")
        
        # Validation configuration
        self.strict_mode = False
        self.custom_rules = {}
        
        logger.info(f"SHACL validator initialized with {len(self.shapes_graph)} shape triples")
    
    def _load_shacl_shapes(self):
        """Load all SHACL shape files."""
        if not self.shapes_dir.exists():
            logger.warning(f"SHACL shapes directory not found: {self.shapes_dir}")
            return
        
        # Bind namespaces
        for prefix, namespace in self.manager.namespaces.items():
            self.shapes_graph.bind(prefix, namespace)
        self.shapes_graph.bind("sh", self.SH)
        
        # Load all TTL files in shapes directory
        shape_files = list(self.shapes_dir.glob("*.ttl"))
        
        for shape_file in shape_files:
            try:
                self.shapes_graph.parse(shape_file, format="turtle")
                logger.debug(f"Loaded SHACL shapes from {shape_file}")
            except Exception as e:
                logger.error(f"Failed to load SHACL shapes from {shape_file}: {e}")
        
        logger.info(f"Loaded {len(shape_files)} SHACL shape files")
    
    def validate_instance(self, instance_uri: str, data_graph: Optional[Graph] = None) -> ValidationReport:
        """
        Validate a single instance against applicable SHACL shapes.
        
        Args:
            instance_uri: URI of the instance to validate
            data_graph: Graph containing the instance, uses main graph if None
            
        Returns:
            ValidationReport with results
        """
        if data_graph is None:
            data_graph = self.manager.graph
        
        # Create a subgraph containing only the instance and related data
        instance_graph = self._extract_instance_graph(instance_uri, data_graph)
        
        # Perform validation
        return self._validate_graph(instance_graph, focus_node=instance_uri)
    
    def validate_graph(self, data_graph: Graph) -> ValidationReport:
        """
        Validate an entire graph against SHACL shapes.
        
        Args:
            data_graph: Graph to validate
            
        Returns:
            ValidationReport with results
        """
        return self._validate_graph(data_graph)
    
    def validate_file(self, file_path: Path) -> ValidationReport:
        """
        Validate a TTL file against SHACL shapes.
        
        Args:
            file_path: Path to TTL file to validate
            
        Returns:
            ValidationReport with results
        """
        # Load the file into a graph
        file_graph = Graph()
        
        # Bind namespaces
        for prefix, namespace in self.manager.namespaces.items():
            file_graph.bind(prefix, namespace)
        
        try:
            file_graph.parse(file_path, format="turtle")
        except Exception as e:
            logger.error(f"Failed to parse file {file_path}: {e}")
            return ValidationReport(
                conforms=False,
                results=[ValidationResult(
                    severity=ValidationSeverity.ERROR,
                    focus_node=str(file_path),
                    result_path="file:parse",
                    value="",
                    message=f"Failed to parse TTL file: {e}",
                    source_constraint="file:syntax",
                    source_shape="file:validation"
                )],
                graph_valid=False,
                total_results=1,
                violations=1,
                warnings=0,
                infos=0
            )
        
        return self._validate_graph(file_graph)
    
    def _validate_graph(self, data_graph: Graph, focus_node: Optional[str] = None) -> ValidationReport:
        """Internal method to validate a graph using available validation approach."""
        if PYSHACL_AVAILABLE:
            return self._validate_with_pyshacl(data_graph, focus_node)
        else:
            return self._validate_basic(data_graph, focus_node)
    
    def _validate_with_pyshacl(self, data_graph: Graph, focus_node: Optional[str] = None) -> ValidationReport:
        """Validate using the pyshacl library."""
        try:
            # Run SHACL validation
            conforms, results_graph, results_text = pyshacl.validate(
                data_graph=data_graph,
                shacl_graph=self.shapes_graph,
                ont_graph=self.manager.graph,
                inference='rdfs',
                abort_on_first=False,
                meta_shacl=False,
                debug=False
            )
            
            # Parse results
            validation_results = self._parse_pyshacl_results(results_graph, focus_node)
            
            # Count results by severity
            violations = sum(1 for r in validation_results if r.severity == ValidationSeverity.VIOLATION)
            warnings = sum(1 for r in validation_results if r.severity == ValidationSeverity.WARNING)
            infos = sum(1 for r in validation_results if r.severity == ValidationSeverity.INFO)
            
            return ValidationReport(
                conforms=conforms,
                results=validation_results,
                graph_valid=conforms,
                total_results=len(validation_results),
                violations=violations,
                warnings=warnings,
                infos=infos
            )
            
        except Exception as e:
            logger.error(f"SHACL validation failed: {e}")
            return ValidationReport(
                conforms=False,
                results=[ValidationResult(
                    severity=ValidationSeverity.ERROR,
                    focus_node=focus_node or "unknown",
                    result_path="validation:error",
                    value="",
                    message=f"Validation error: {e}",
                    source_constraint="validation:system",
                    source_shape="validation:system"
                )],
                graph_valid=False,
                total_results=1,
                violations=1,
                warnings=0,
                infos=0
            )
    
    def _validate_basic(self, data_graph: Graph, focus_node: Optional[str] = None) -> ValidationReport:
        """Basic validation without pyshacl - implements key SHACL constraints manually."""
        results = []
        
        # Get all instances to validate
        if focus_node:
            instances = [URIRef(focus_node)]
        else:
            instances = self._get_all_instances(data_graph)
        
        for instance in instances:
            instance_results = self._validate_instance_basic(data_graph, instance)
            results.extend(instance_results)
        
        # Count results by severity
        violations = sum(1 for r in results if r.severity == ValidationSeverity.VIOLATION)
        warnings = sum(1 for r in results if r.severity == ValidationSeverity.WARNING)
        infos = sum(1 for r in results if r.severity == ValidationSeverity.INFO)
        
        conforms = violations == 0
        
        return ValidationReport(
            conforms=conforms,
            results=results,
            graph_valid=conforms,
            total_results=len(results),
            violations=violations,
            warnings=warnings,
            infos=infos
        )
    
    def _validate_instance_basic(self, data_graph: Graph, instance: URIRef) -> List[ValidationResult]:
        """Basic validation for a single instance."""
        results = []
        
        # Get the instance's type(s)
        instance_types = list(data_graph.objects(instance, RDF.type))
        
        for instance_type in instance_types:
            if instance_type == OWL.NamedIndividual:
                continue  # Skip the generic individual type
            
            # Find applicable shapes for this type
            applicable_shapes = self._find_shapes_for_class(str(instance_type))
            
            for shape_uri in applicable_shapes:
                shape_results = self._validate_against_shape_basic(data_graph, instance, shape_uri)
                results.extend(shape_results)
        
        return results
    
    def _validate_against_shape_basic(self, data_graph: Graph, instance: URIRef, shape_uri: str) -> List[ValidationResult]:
        """Validate an instance against a specific shape using basic rules."""
        results = []
        
        # Get shape properties
        shape_ref = URIRef(shape_uri)
        
        # Check property constraints
        property_shapes = list(self.shapes_graph.objects(shape_ref, self.SH.property))
        
        for prop_shape in property_shapes:
            prop_results = self._validate_property_shape_basic(data_graph, instance, prop_shape, shape_uri)
            results.extend(prop_results)
        
        return results
    
    def _validate_property_shape_basic(self, data_graph: Graph, instance: URIRef, 
                                     property_shape: BNode, shape_uri: str) -> List[ValidationResult]:
        """Validate a property constraint."""
        results = []
        
        # Get property path
        property_paths = list(self.shapes_graph.objects(property_shape, self.SH.path))
        if not property_paths:
            return results
        
        property_path = property_paths[0]
        
        # Get current values for this property
        current_values = list(data_graph.objects(instance, property_path))
        
        # Check minCount constraint
        min_counts = list(self.shapes_graph.objects(property_shape, self.SH.minCount))
        if min_counts:
            min_count = int(min_counts[0])
            if len(current_values) < min_count:
                results.append(ValidationResult(
                    severity=ValidationSeverity.VIOLATION,
                    focus_node=str(instance),
                    result_path=str(property_path),
                    value=f"Found {len(current_values)} values",
                    message=f"Property {self.manager._extract_local_name(str(property_path))} requires at least {min_count} value(s), but found {len(current_values)}",
                    source_constraint=str(self.SH.minCount),
                    source_shape=shape_uri
                ))
        
        # Check maxCount constraint
        max_counts = list(self.shapes_graph.objects(property_shape, self.SH.maxCount))
        if max_counts:
            max_count = int(max_counts[0])
            if len(current_values) > max_count:
                results.append(ValidationResult(
                    severity=ValidationSeverity.VIOLATION,
                    focus_node=str(instance),
                    result_path=str(property_path),
                    value=f"Found {len(current_values)} values",
                    message=f"Property {self.manager._extract_local_name(str(property_path))} allows at most {max_count} value(s), but found {len(current_values)}",
                    source_constraint=str(self.SH.maxCount),
                    source_shape=shape_uri
                ))
        
        # Check datatype constraints
        datatypes = list(self.shapes_graph.objects(property_shape, self.SH.datatype))
        if datatypes and current_values:
            expected_datatype = datatypes[0]
            for value in current_values:
                if isinstance(value, Literal) and value.datatype != expected_datatype:
                    results.append(ValidationResult(
                        severity=ValidationSeverity.VIOLATION,
                        focus_node=str(instance),
                        result_path=str(property_path),
                        value=str(value),
                        message=f"Property {self.manager._extract_local_name(str(property_path))} expects datatype {expected_datatype}, but found {value.datatype}",
                        source_constraint=str(self.SH.datatype),
                        source_shape=shape_uri
                    ))
        
        # Check class constraints for object properties
        classes = list(self.shapes_graph.objects(property_shape, self.SH['class']))
        if classes and current_values:
            expected_class = classes[0]
            for value in current_values:
                if isinstance(value, URIRef):
                    # Check if the referenced instance is of the expected class
                    value_types = list(data_graph.objects(value, RDF.type))
                    if expected_class not in value_types:
                        # Check if any type is a subclass of the expected class
                        is_valid_type = False
                        for value_type in value_types:
                            if self._is_subclass_of(str(value_type), str(expected_class)):
                                is_valid_type = True
                                break
                        
                        if not is_valid_type:
                            results.append(ValidationResult(
                                severity=ValidationSeverity.VIOLATION,
                                focus_node=str(instance),
                                result_path=str(property_path),
                                value=str(value),
                                message=f"Property {self.manager._extract_local_name(str(property_path))} expects instance of class {self.manager._extract_local_name(str(expected_class))}",
                                source_constraint=str(self.SH['class']),
                                source_shape=shape_uri
                            ))
        
        # Check value range constraints
        min_inclusives = list(self.shapes_graph.objects(property_shape, self.SH.minInclusive))
        if min_inclusives and current_values:
            min_value = float(min_inclusives[0])
            for value in current_values:
                if isinstance(value, Literal) and value.datatype in (XSD.double, XSD.float, XSD.integer):
                    if float(value) < min_value:
                        results.append(ValidationResult(
                            severity=ValidationSeverity.VIOLATION,
                            focus_node=str(instance),
                            result_path=str(property_path),
                            value=str(value),
                            message=f"Property {self.manager._extract_local_name(str(property_path))} value {value} is below minimum {min_value}",
                            source_constraint=str(self.SH.minInclusive),
                            source_shape=shape_uri
                        ))
        
        max_inclusives = list(self.shapes_graph.objects(property_shape, self.SH.maxInclusive))
        if max_inclusives and current_values:
            max_value = float(max_inclusives[0])
            for value in current_values:
                if isinstance(value, Literal) and value.datatype in (XSD.double, XSD.float, XSD.integer):
                    if float(value) > max_value:
                        results.append(ValidationResult(
                            severity=ValidationSeverity.VIOLATION,
                            focus_node=str(instance),
                            result_path=str(property_path),
                            value=str(value),
                            message=f"Property {self.manager._extract_local_name(str(property_path))} value {value} is above maximum {max_value}",
                            source_constraint=str(self.SH.maxInclusive),
                            source_shape=shape_uri
                        ))
        
        return results
    
    def _parse_pyshacl_results(self, results_graph: Graph, focus_node: Optional[str] = None) -> List[ValidationResult]:
        """Parse validation results from pyshacl results graph."""
        results = []
        
        # Query for validation results
        query = """
        SELECT ?result ?focusNode ?resultPath ?value ?message ?sourceConstraint ?sourceShape ?severity WHERE {
            ?result rdf:type sh:ValidationResult .
            OPTIONAL { ?result sh:focusNode ?focusNode }
            OPTIONAL { ?result sh:resultPath ?resultPath }
            OPTIONAL { ?result sh:value ?value }
            OPTIONAL { ?result sh:resultMessage ?message }
            OPTIONAL { ?result sh:sourceConstraintComponent ?sourceConstraint }
            OPTIONAL { ?result sh:sourceShape ?sourceShape }
            OPTIONAL { ?result sh:resultSeverity ?severity }
        }
        """
        
        query_results = results_graph.query(query)
        
        for row in query_results:
            # Filter by focus node if specified
            if focus_node and row.focusNode and str(row.focusNode) != focus_node:
                continue
            
            # Determine severity
            severity = ValidationSeverity.VIOLATION  # Default
            if row.severity:
                severity_str = str(row.severity).split('#')[-1]
                if severity_str == "Warning":
                    severity = ValidationSeverity.WARNING
                elif severity_str == "Info":
                    severity = ValidationSeverity.INFO
            
            result = ValidationResult(
                severity=severity,
                focus_node=str(row.focusNode) if row.focusNode else "",
                result_path=str(row.resultPath) if row.resultPath else "",
                value=str(row.value) if row.value else "",
                message=str(row.message) if row.message else "Validation error",
                source_constraint=str(row.sourceConstraint) if row.sourceConstraint else "",
                source_shape=str(row.sourceShape) if row.sourceShape else ""
            )
            results.append(result)
        
        return results
    
    def _extract_instance_graph(self, instance_uri: str, data_graph: Graph) -> Graph:
        """Extract a subgraph containing an instance and related data."""
        instance_graph = Graph()
        
        # Bind namespaces
        for prefix, namespace in self.manager.namespaces.items():
            instance_graph.bind(prefix, namespace)
        
        instance_ref = URIRef(instance_uri)
        
        # Add all triples where the instance is the subject
        for triple in data_graph.triples((instance_ref, None, None)):
            instance_graph.add(triple)
        
        # Add related class information
        instance_types = list(data_graph.objects(instance_ref, RDF.type))
        for instance_type in instance_types:
            # Add class hierarchy information
            for triple in self.manager.graph.triples((instance_type, RDFS.subClassOf, None)):
                instance_graph.add(triple)
        
        return instance_graph
    
    def _get_all_instances(self, data_graph: Graph) -> List[URIRef]:
        """Get all named individuals from a graph."""
        instances = set()
        
        # Find all subjects that have rdf:type
        for subject in data_graph.subjects(RDF.type, None):
            if isinstance(subject, URIRef):
                instances.add(subject)
        
        return list(instances)
    
    def _find_shapes_for_class(self, class_uri: str) -> List[str]:
        """Find SHACL shapes that target a specific class."""
        shapes = []
        
        # Find shapes with sh:targetClass
        query = """
        SELECT ?shape WHERE {
            ?shape sh:targetClass ?class .
        }
        """
        
        results = self.shapes_graph.query(query, initBindings={"class": URIRef(class_uri)})
        
        for row in results:
            shapes.append(str(row.shape))
        
        # Also check for shapes targeting parent classes
        parent_classes = self._get_parent_classes(class_uri)
        for parent_class in parent_classes:
            parent_results = self.shapes_graph.query(query, initBindings={"class": URIRef(parent_class)})
            for row in parent_results:
                if str(row.shape) not in shapes:
                    shapes.append(str(row.shape))
        
        return shapes
    
    def _get_parent_classes(self, class_uri: str) -> List[str]:
        """Get all parent classes for a given class."""
        parents = []
        
        query = """
        SELECT ?parent WHERE {
            ?class rdfs:subClassOf+ ?parent .
        }
        """
        
        results = self.manager.graph.query(query, initBindings={"class": URIRef(class_uri)})
        
        for row in results:
            parents.append(str(row.parent))
        
        return parents
    
    def _is_subclass_of(self, class_uri: str, parent_class_uri: str) -> bool:
        """Check if a class is a subclass of another class."""
        query = """
        ASK {
            ?class rdfs:subClassOf* ?parent .
        }
        """
        
        result = self.manager.graph.query(
            query, 
            initBindings={
                "class": URIRef(class_uri),
                "parent": URIRef(parent_class_uri)
            }
        )
        
        return bool(result)
    
    def set_strict_mode(self, strict: bool):
        """Set strict validation mode."""
        self.strict_mode = strict
        logger.info(f"Validation strict mode: {strict}")
    
    def add_custom_rule(self, rule_name: str, rule_function):
        """Add a custom validation rule."""
        self.custom_rules[rule_name] = rule_function
        logger.info(f"Added custom validation rule: {rule_name}")
    
    def generate_validation_report_html(self, report: ValidationReport) -> str:
        """Generate an HTML report from validation results."""
        html = """
        <html>
        <head>
            <title>DynaMat Validation Report</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .summary { background-color: #f0f0f0; padding: 10px; border-radius: 5px; }
                .violation { color: red; }
                .warning { color: orange; }
                .info { color: blue; }
                .result { margin: 10px 0; padding: 10px; border-left: 3px solid; }
                .result.violation { border-color: red; background-color: #ffe6e6; }
                .result.warning { border-color: orange; background-color: #fff3e0; }
                .result.info { border-color: blue; background-color: #e3f2fd; }
            </style>
        </head>
        <body>
            <h1>DynaMat Validation Report</h1>
        """
        
        # Summary
        html += f"""
            <div class="summary">
                <h2>Summary</h2>
                <p><strong>Conforms:</strong> {'Yes' if report.conforms else 'No'}</p>
                <p><strong>Total Results:</strong> {report.total_results}</p>
                <p><strong>Violations:</strong> <span class="violation">{report.violations}</span></p>
                <p><strong>Warnings:</strong> <span class="warning">{report.warnings}</span></p>
                <p><strong>Info:</strong> <span class="info">{report.infos}</span></p>
            </div>
        """
        
        # Individual results
        if report.results:
            html += "<h2>Validation Results</h2>"
            
            for result in report.results:
                severity_class = result.severity.value.lower()
                html += f"""
                    <div class="result {severity_class}">
                        <p><strong>Severity:</strong> {result.severity.value}</p>
                        <p><strong>Focus Node:</strong> {self.manager._extract_local_name(result.focus_node)}</p>
                        <p><strong>Property:</strong> {self.manager._extract_local_name(result.result_path)}</p>
                        <p><strong>Value:</strong> {result.value}</p>
                        <p><strong>Message:</strong> {result.message}</p>
                    </div>
                """
        
        html += """
        </body>
        </html>
        """
        
        return html