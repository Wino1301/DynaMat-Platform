"""
DynaMat Platform - Form Validator
SHACL-based validation for RDF instance data
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from rdflib import Graph, URIRef, Literal, Namespace
from rdflib.namespace import RDF, RDFS, SH

try:
    from pyshacl import validate
    PYSHACL_AVAILABLE = True
except ImportError:
    PYSHACL_AVAILABLE = False
    logging.warning("pyshacl not available - SHACL validation will be skipped")

logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """SHACL validation severity levels"""
    VIOLATION = "Violation"  # Critical errors - blocks save
    WARNING = "Warning"      # Contextual issues - allows save with confirmation
    INFO = "Info"           # Suggestions - informational only


@dataclass
class ValidationIssue:
    """
    Represents a single SHACL validation issue.

    Attributes:
        severity: Severity level (Violation, Warning, Info)
        message: Human-readable error message from sh:message
        focus_node: The subject/instance that failed validation
        result_path: The property that failed (e.g., dyn:hasSpecimenID)
        value: The problematic value (if available)
        source_shape: The SHACL shape that generated this issue
    """
    severity: ValidationSeverity
    message: str
    focus_node: Optional[str] = None
    result_path: Optional[str] = None
    value: Optional[str] = None
    source_shape: Optional[str] = None

    def get_display_message(self) -> str:
        """Get formatted message for display"""
        parts = []

        if self.result_path:
            # Extract property name from URI
            prop_name = self._extract_uri_fragment(self.result_path)
            parts.append(f"[{prop_name}]")

        parts.append(self.message)

        if self.value:
            parts.append(f"(value: {self.value})")

        return " ".join(parts)

    @staticmethod
    def _extract_uri_fragment(uri: str) -> str:
        """Extract the fragment/name from a URI"""
        if "#" in uri:
            return uri.split("#")[-1]
        elif "/" in uri:
            return uri.split("/")[-1]
        return uri


@dataclass
class ValidationResult:
    """
    Results from SHACL validation.

    Attributes:
        conforms: True if no violations exist
        violations: Critical errors that block save
        warnings: Contextual issues that allow save with confirmation
        infos: Informational suggestions
        raw_report: Raw SHACL validation report text
    """
    conforms: bool
    violations: List[ValidationIssue] = field(default_factory=list)
    warnings: List[ValidationIssue] = field(default_factory=list)
    infos: List[ValidationIssue] = field(default_factory=list)
    raw_report: Optional[str] = None

    def has_blocking_issues(self) -> bool:
        """Returns True if violations exist (blocks save)"""
        return len(self.violations) > 0

    def has_any_issues(self) -> bool:
        """Returns True if any issues exist"""
        return len(self.violations) > 0 or len(self.warnings) > 0 or len(self.infos) > 0

    def get_all_issues(self) -> List[ValidationIssue]:
        """Get all issues sorted by severity"""
        return self.violations + self.warnings + self.infos

    def get_summary(self) -> str:
        """Get summary string"""
        parts = []
        if self.violations:
            parts.append(f"{len(self.violations)} violation(s)")
        if self.warnings:
            parts.append(f"{len(self.warnings)} warning(s)")
        if self.infos:
            parts.append(f"{len(self.infos)} info")

        if not parts:
            return "No issues found"

        return ", ".join(parts)


class SHACLValidator:
    """
    SHACL validator for RDF instance data.

    Validates RDF graphs against SHACL shapes and categorizes
    results by severity (Violation, Warning, Info).
    """

    def __init__(self, ontology_manager=None):
        """
        Initialize the SHACL validator.

        Args:
            ontology_manager: Optional ontology manager to access shapes
        """
        self.ontology_manager = ontology_manager
        self.shapes_graph = None

        if not PYSHACL_AVAILABLE:
            logger.error("pyshacl is not installed - validation will not work!")
            logger.error("Install with: pip install pyshacl")

        # Load SHACL shapes
        self._load_shapes()

    def _load_shapes(self):
        """Load SHACL shapes from ontology directory"""
        try:
            # Determine shapes directory
            if self.ontology_manager:
                # Use ontology manager's directory
                shapes_dir = Path(self.ontology_manager.ontology_dir) / "shapes"
            else:
                # Fallback: Use relative path
                current_file = Path(__file__).parent.parent.parent
                shapes_dir = current_file / "ontology" / "shapes"

            if not shapes_dir.exists():
                logger.error(f"Shapes directory not found: {shapes_dir}")
                return

            # Load all TTL files in shapes directory
            self.shapes_graph = Graph()
            shapes_loaded = 0

            for shapes_file in shapes_dir.glob("*.ttl"):
                logger.info(f"Loading SHACL shapes from: {shapes_file.name}")
                self.shapes_graph.parse(str(shapes_file), format="turtle")
                shapes_loaded += 1

            if shapes_loaded > 0:
                logger.info(f"Loaded {shapes_loaded} SHACL shape files")
            else:
                logger.warning(f"No SHACL shape files found in {shapes_dir}")

        except Exception as e:
            logger.error(f"Failed to load SHACL shapes: {e}", exc_info=True)
            self.shapes_graph = None

    def validate(self, data_graph: Graph) -> ValidationResult:
        """
        Validate RDF data graph against SHACL shapes.

        Args:
            data_graph: RDF graph containing instance data

        Returns:
            ValidationResult with violations, warnings, and infos
        """
        # Check if pyshacl is available
        if not PYSHACL_AVAILABLE:
            logger.error("pyshacl not available - skipping validation")
            return ValidationResult(
                conforms=True,  # Allow save if pyshacl not installed
                raw_report="SHACL validation skipped - pyshacl not installed"
            )

        # Check if shapes are loaded
        if not self.shapes_graph or len(self.shapes_graph) == 0:
            logger.warning("No SHACL shapes loaded - skipping validation")
            return ValidationResult(
                conforms=True,
                raw_report="SHACL validation skipped - no shapes loaded"
            )

        try:
            logger.info("Running SHACL validation...")

            # Run pyshacl validation
            conforms, results_graph, results_text = validate(
                data_graph=data_graph,
                shacl_graph=self.shapes_graph,
                ont_graph=None,  # Could include ontology for inference
                inference='rdfs',  # Use RDFS inference
                abort_on_first=False,  # Get all validation results
                allow_infos=True,  # Include sh:Info severity
                allow_warnings=True,  # Include sh:Warning severity
                meta_shacl=False,  # Don't validate the shapes themselves
                advanced=True,  # Enable advanced SHACL features
                js=False,  # No JavaScript validation
                debug=False
            )

            logger.info(f"SHACL validation complete: conforms={conforms}")

            # Parse results
            validation_result = self._parse_validation_results(
                conforms=conforms,
                results_graph=results_graph,
                results_text=results_text
            )

            # Log summary
            logger.info(f"Validation summary: {validation_result.get_summary()}")

            return validation_result

        except Exception as e:
            logger.error(f"SHACL validation failed: {e}", exc_info=True)
            # Return failure result
            return ValidationResult(
                conforms=False,
                violations=[ValidationIssue(
                    severity=ValidationSeverity.VIOLATION,
                    message=f"Validation system error: {str(e)}"
                )],
                raw_report=str(e)
            )

    def _parse_validation_results(self, conforms: bool, results_graph: Graph,
                                  results_text: str) -> ValidationResult:
        """
        Parse pyshacl validation results and categorize by severity.

        Args:
            conforms: Whether validation passed
            results_graph: RDF graph with validation results
            results_text: Text report from pyshacl

        Returns:
            ValidationResult with categorized issues
        """
        violations = []
        warnings = []
        infos = []

        # Query for validation results
        # pyshacl creates sh:ValidationResult instances for each issue
        query = """
        PREFIX sh: <http://www.w3.org/ns/shacl#>

        SELECT ?severity ?message ?focusNode ?resultPath ?value ?sourceShape
        WHERE {
            ?result a sh:ValidationResult ;
                    sh:resultSeverity ?severity ;
                    sh:resultMessage ?message .

            OPTIONAL { ?result sh:focusNode ?focusNode }
            OPTIONAL { ?result sh:resultPath ?resultPath }
            OPTIONAL { ?result sh:value ?value }
            OPTIONAL { ?result sh:sourceShape ?sourceShape }
        }
        ORDER BY ?severity ?resultPath
        """

        try:
            results = results_graph.query(query)

            for row in results:
                # Determine severity
                severity_uri = str(row.severity)

                if "Violation" in severity_uri:
                    severity = ValidationSeverity.VIOLATION
                elif "Warning" in severity_uri:
                    severity = ValidationSeverity.WARNING
                elif "Info" in severity_uri:
                    severity = ValidationSeverity.INFO
                else:
                    # Default to violation for unknown severity
                    severity = ValidationSeverity.VIOLATION
                    logger.warning(f"Unknown severity: {severity_uri}, treating as Violation")

                # Create issue
                issue = ValidationIssue(
                    severity=severity,
                    message=str(row.message) if row.message else "Validation failed",
                    focus_node=str(row.focusNode) if row.focusNode else None,
                    result_path=str(row.resultPath) if row.resultPath else None,
                    value=str(row.value) if row.value else None,
                    source_shape=str(row.sourceShape) if row.sourceShape else None
                )

                # Categorize by severity
                if severity == ValidationSeverity.VIOLATION:
                    violations.append(issue)
                elif severity == ValidationSeverity.WARNING:
                    warnings.append(issue)
                elif severity == ValidationSeverity.INFO:
                    infos.append(issue)

            logger.info(f"Parsed {len(violations)} violations, {len(warnings)} warnings, {len(infos)} infos")

        except Exception as e:
            logger.error(f"Failed to parse validation results: {e}", exc_info=True)

        return ValidationResult(
            conforms=conforms and len(violations) == 0,
            violations=violations,
            warnings=warnings,
            infos=infos,
            raw_report=results_text
        )

    def validate_form_data(self, form_data: Dict[str, Any],
                          class_uri: str, instance_id: str) -> ValidationResult:
        """
        Convenience method to validate form data directly.
        Converts form data to RDF graph and validates.

        Args:
            form_data: Form data dictionary
            class_uri: Class URI for the instance
            instance_id: Instance identifier

        Returns:
            ValidationResult

        Note: This requires converting form data to RDF.
        For now, this is a placeholder - validation happens in instance_writer
        after graph creation.
        """
        logger.warning("validate_form_data is a placeholder - use instance_writer for validation")
        return ValidationResult(conforms=True, raw_report="Placeholder validation")
