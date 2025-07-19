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
        
        shape_files = list(self.shapes_dir.glob("*.ttl"))
        
        for shape_file in shape_files:
            try:
                self.shapes_graph.parse(shape_file, format="turtle")
                logger.debug(f"Loaded SHACL shapes from {shape_file}")
            except Exception as e:
                logger.error(f"Failed to load SHACL shapes from {shape_file}: {e}")
        
        # Bind namespaces
        for prefix, namespace in self.manager.namespaces.items():
            self.shapes_graph.bind(prefix, namespace)
        self.shapes_graph.bind("sh", self.SH)
        
        logger.info(f"Loaded {len(self.shapes_graph)} SHACL shape triples from {len(shape_files)} files")
    
    def validate_instance(self, instance_uri: str, data_graph: Optional[Graph] = None) -> ValidationReport:
        """
        Validate a single instance against SHACL shapes.
        
        Args:
            instance_uri: URI of the instance to validate
            data_graph: Graph containing the instance data, uses main graph if None
            
        Returns:
            ValidationReport with results
        """
        if data_graph is None:
            data_graph = self.manager.graph
        
        if not PYSHACL_AVAILABLE:
            return self._basic_validation(instance_uri, data_graph)
        
        try:
            # Extract subgraph for this instance
            instance_graph = Graph()
            instance_ref = URIRef(instance_uri)
            
            # Get all triples where this instance is the subject
            for triple in data_graph.triples((instance_ref, None, None)):
                instance_graph.add(triple)
            
            # Validate using pyshacl
            conforms, results_graph, results_text = pyshacl.validate(
                data_graph=instance_graph,
                shacl_graph=self.shapes_graph,
                ont_graph=self.manager.graph,
                inference='rdfs',
                abort_on_first=not self.strict_mode,
                allow_infos=True,
                allow_warnings=True
            )
            
            # Parse results
            validation_results = self._parse_shacl_results(results_graph)
            
            # Apply custom rules
            custom_results = self._apply_custom_rules(instance_uri, data_graph)
            validation_results.extend(custom_results)
            
            # Create report
            report = self._create_validation_report(conforms, validation_results)
            
            logger.debug(f"Validated instance {instance_uri}: {'CONFORMS' if conforms else 'VIOLATIONS'}")
            return report
            
        except Exception as e:
            logger.error(f"SHACL validation failed for {instance_uri}: {e}")
            return ValidationReport(
                conforms=False,
                results=[],
                graph_valid=False,
                total_results=0,
                violations=1,
                warnings=0,
                infos=0
            )
    
    def validate_graph(self, data_graph: Graph) -> ValidationReport:
        """
        Validate an entire graph against SHACL shapes.
        
        Args:
            data_graph: Graph to validate
            
        Returns:
            ValidationReport with results
        """
        if not PYSHACL_AVAILABLE:
            return self._basic_graph_validation(data_graph)
        
        try:
            conforms, results_graph, results_text = pyshacl.validate(
                data_graph=data_graph,
                shacl_graph=self.shapes_graph,
                ont_graph=self.manager.graph,
                inference='rdfs',
                abort_on_first=not self.strict_mode,
                allow_infos=True,
                allow_warnings=True
            )
            
            # Parse results
            validation_results = self._parse_shacl_results(results_graph)
            
            # Create report
            report = self._create_validation_report(conforms, validation_results)
            
            logger.info(f"Graph validation: {'CONFORMS' if conforms else 'VIOLATIONS'} ({len(validation_results)} results)")
            return report
            
        except Exception as e:
            logger.error(f"Graph validation failed: {e}")
            return ValidationReport(
                conforms=False,
                results=[],
                graph_valid=False,
                total_results=0,
                violations=1,
                warnings=0,
                infos=0
            )
    
    def validate_file(self, file_path: Path) -> ValidationReport:
        """
        Validate a TTL file against SHACL shapes.
        
        Args:
            file_path: Path to TTL file to validate
            
        Returns:
            ValidationReport with results
        """
        try:
            data_graph = Graph()
            data_graph.parse(file_path, format="turtle")
            
            return self.validate_graph(data_graph)
            
        except Exception as e:
            logger.error(f"Failed to validate file {file_path}: {e}")
            return ValidationReport(
                conforms=False,
                results=[],
                graph_valid=False,
                total_results=0,
                violations=1,
                warnings=0,
                infos=0
            )
    
    def _parse_shacl_results(self, results_graph: Graph) -> List[ValidationResult]:
        """Parse SHACL validation results from results graph."""
        results = []
        
        # Query for validation results
        query = """
        SELECT ?result ?severity ?focusNode ?resultPath ?value ?message ?sourceConstraint ?sourceShape WHERE {
            ?result a sh:ValidationResult .
            ?result sh:resultSeverity ?severity .
            ?result sh:focusNode ?focusNode .
            OPTIONAL { ?result sh:resultPath ?resultPath }
            OPTIONAL { ?result sh:value ?value }
            OPTIONAL { ?result sh:resultMessage ?message }
            OPTIONAL { ?result sh:sourceConstraintComponent ?sourceConstraint }
            OPTIONAL { ?result sh:sourceShape ?sourceShape }
        }
        """
        
        query_results = results_graph.query(query)
        
        for row in query_results:
            # Map severity
            severity_uri = str(row.severity)
            if "Violation" in severity_uri:
                severity = ValidationSeverity.VIOLATION
            elif "Warning" in severity_uri:
                severity = ValidationSeverity.WARNING
            elif "Info" in severity_uri:
                severity = ValidationSeverity.INFO
            else:
                severity = ValidationSeverity.ERROR
            
            result = ValidationResult(
                severity=severity,
                focus_node=str(row.focusNode) if row.focusNode else "",
                result_path=str(row.resultPath) if row.resultPath else "",
                value=str(row.value) if row.value else "",
                message=str(row.message) if row.message else "",
                source_constraint=str(row.sourceConstraint) if row.sourceConstraint else "",
                source_shape=str(row.sourceShape) if row.sourceShape else ""
            )
            results.append(result)
        
        return results
    
    def _create_validation_report(self, conforms: bool, results: List[ValidationResult]) -> ValidationReport:
        """Create a validation report from results."""
        violations = sum(1 for r in results if r.severity == ValidationSeverity.VIOLATION)
        warnings = sum(1 for r in results if r.severity == ValidationSeverity.WARNING)
        infos = sum(1 for r in results if r.severity == ValidationSeverity.INFO)
        
        return ValidationReport(
            conforms=conforms,
            results=results,
            graph_valid=violations == 0,
            total_results=len(results),
            violations=violations,
            warnings=warnings,
            infos=infos
        )
    
    def _apply_custom_rules(self, instance_uri: str, data_graph: Graph) -> List[ValidationResult]:
        """Apply custom validation rules."""
        results = []
        
        for rule_name, rule_function in self.custom_rules.items():
            try:
                rule_results = rule_function(instance_uri, data_graph, self.manager)
                if isinstance(rule_results, list):
                    results.extend(rule_results)
                elif rule_results:
                    results.append(rule_results)
            except Exception as e:
                logger.error(f"Custom rule {rule_name} failed: {e}")
                results.append(ValidationResult(
                    severity=ValidationSeverity.ERROR,
                    focus_node=instance_uri,
                    result_path="",
                    value="",
                    message=f"Custom rule '{rule_name}' failed: {e}",
                    source_constraint=rule_name,
                    source_shape=""
                ))
        
        return results
    
    def _basic_validation(self, instance_uri: str, data_graph: Graph) -> ValidationReport:
        """Basic validation when pyshacl is not available."""
        results = []
        instance_ref = URIRef(instance_uri)
        
        # Check if instance has required rdf:type
        types = list(data_graph.objects(instance_ref, RDF.type))
        if not types:
            results.append(ValidationResult(
                severity=ValidationSeverity.VIOLATION,
                focus_node=instance_uri,
                result_path=str(RDF.type),
                value="",
                message="Instance must have at least one rdf:type",
                source_constraint="rdf:type requirement",
                source_shape="basic"
            ))
        
        # Check for basic DynaMat requirements
        has_name = bool(list(data_graph.objects(instance_ref, self.DYN.hasName)))
        if not has_name:
            results.append(ValidationResult(
                severity=ValidationSeverity.WARNING,
                focus_node=instance_uri,
                result_path=str(self.DYN.hasName),
                value="",
                message="Instance should have a name (dyn:hasName)",
                source_constraint="naming convention",
                source_shape="basic"
            ))
        
        return self._create_validation_report(len(results) == 0, results)
    
    def _basic_graph_validation(self, data_graph: Graph) -> ValidationReport:
        """Basic graph validation when pyshacl is not available."""
        results = []
        
        # Count instances without types
        query = """
        SELECT ?instance WHERE {
            ?instance ?p ?o .
            FILTER NOT EXISTS { ?instance rdf:type ?type }
        }
        """
        
        untyped_instances = data_graph.query(query)
        for row in untyped_instances:
            results.append(ValidationResult(
                severity=ValidationSeverity.WARNING,
                focus_node=str(row.instance),
                result_path=str(RDF.type),
                value="",
                message="Instance has no rdf:type declaration",
                source_constraint="type requirement",
                source_shape="basic"
            ))
        
        return self._create_validation_report(len(results) == 0, results)
    
    def generate_validation_report_html(self, report: ValidationReport) -> str:
        """Generate an HTML report from validation results."""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>DynaMat Validation Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #f0f0f0; padding: 10px; border-radius: 5px; }}
                .summary {{ margin: 20px 0; }}
                .result {{ margin: 10px 0; padding: 10px; border-left: 4px solid; }}
                .violation {{ border-color: #d32f2f; background-color: #ffebee; }}
                .warning {{ border-color: #f57c00; background-color: #fff3e0; }}
                .info {{ border-color: #1976d2; background-color: #e3f2fd; }}
                .error {{ border-color: #7b1fa2; background-color: #f3e5f5; }}
                .conforms {{ color: #388e3c; }}
                .violates {{ color: #d32f2f; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>DynaMat Validation Report</h1>
                <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
            
            <div class="summary">
                <h2>Summary</h2>
                <p><strong>Overall Status:</strong> 
                   <span class="{'conforms' if report.conforms else 'violates'}">
                   {'CONFORMS' if report.conforms else 'VIOLATIONS FOUND'}
                   </span>
                </p>
                <p><strong>Total Results:</strong> {report.total_results}</p>
                <p><strong>Violations:</strong> {report.violations}</p>
                <p><strong>Warnings:</strong> {report.warnings}</p>
                <p><strong>Info:</strong> {report.infos}</p>
            </div>
            
            <div class="results">
                <h2>Detailed Results</h2>
        """
        
        if not report.results:
            html += "<p>No validation issues found.</p>"
        else:
            for result in report.results:
                severity_class = result.severity.value.lower()
                html += f"""
                <div class="result {severity_class}">
                    <h3>{result.severity.value}</h3>
                    <p><strong>Focus Node:</strong> {result.focus_node}</p>
                    <p><strong>Path:</strong> {result.result_path}</p>
                    <p><strong>Value:</strong> {result.value}</p>
                    <p><strong>Message:</strong> {result.message}</p>
                    <p><strong>Source Shape:</strong> {result.source_shape}</p>
                    <p><strong>Constraint:</strong> {result.source_constraint}</p>
                </div>
                """
        
        html += """
            </div>
        </body>
        </html>
        """
        
        return html
    
    def validate_class_hierarchy(self, class_uri: str) -> List[str]:
        """Validate that a class hierarchy is consistent."""
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