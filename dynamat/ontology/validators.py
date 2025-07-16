"""
DynaMat SHACL Validators

File location: dynamat/ontology/validators.py

This module provides SHACL validation functionality that integrates with
the existing DynaMat system and enables validation of TTL files against
the defined SHACL shapes.
"""

from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass
import logging
from datetime import datetime

try:
    from rdflib import Graph, Namespace, URIRef, Literal
    from rdflib.namespace import RDF, RDFS, OWL, SH, XSD
    import pyshacl
    PYSHACL_AVAILABLE = True
except ImportError:
    PYSHACL_AVAILABLE = False
    logging.warning("pyshacl not available. Install with: pip install pyshacl")

from .manager import get_ontology_manager
from .shape_manager import get_shape_manager


@dataclass
class ValidationResult:
    """Result of SHACL validation"""
    conforms: bool
    graph: Optional[Graph] = None
    report_text: Optional[str] = None
    report_graph: Optional[Graph] = None
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    errors: List[str] = None
    warnings: List[str] = None
    infos: List[str] = None


class SHACLValidator:
    """
    SHACL validator for DynaMat Platform.
    
    Provides validation services for individual TTL files and complete
    experimental datasets using the defined SHACL shapes.
    """
    
    def __init__(self, ontology_manager=None, shape_manager=None):
        self.ontology_manager = ontology_manager or get_ontology_manager()
        self.shape_manager = shape_manager or get_shape_manager()
        
        # Namespaces
        self.dyn = Namespace("https://github.com/Wino1301/DynaMat-Platform/ontology#")
        self.sh = SH
        
        # Validation settings
        self.default_inference = "rdfs"  # rdfs, owlrl, both, none
        self.advanced = True
        self.js = False  # JavaScript constraints (usually not needed)
        
        if not PYSHACL_AVAILABLE:
            logging.warning("pyshacl not available. Basic validation only.")
    
    def validate_file(self, ttl_file: Union[str, Path], 
                     class_name: Optional[str] = None,
                     shapes_file: Optional[Union[str, Path]] = None) -> ValidationResult:
        """
        Validate a single TTL file against SHACL shapes.
        
        Args:
            ttl_file: Path to TTL file to validate
            class_name: Expected class for validation (auto-detected if None)
            shapes_file: Custom shapes file (uses default if None)
        
        Returns:
            ValidationResult with detailed validation information
        """
        
        ttl_path = Path(ttl_file)
        if not ttl_path.exists():
            return ValidationResult(
                conforms=False,
                errors=[f"File not found: {ttl_path}"]
            )
        
        try:
            # Load data graph
            data_graph = Graph()
            data_graph.parse(str(ttl_path), format="turtle")
            
            # Auto-detect class if not provided
            if not class_name:
                class_name = self._detect_primary_class(data_graph)
            
            # Get shapes graph
            if shapes_file:
                shapes_graph = Graph()
                shapes_graph.parse(str(shapes_file), format="turtle")
            else:
                shapes_graph = self._get_shapes_graph(class_name)
            
            # Perform validation
            if PYSHACL_AVAILABLE and shapes_graph:
                return self._validate_with_pyshacl(data_graph, shapes_graph)
            else:
                return self._validate_basic(data_graph, class_name)
                
        except Exception as e:
            logging.error(f"Validation error for {ttl_path}: {e}")
            return ValidationResult(
                conforms=False,
                errors=[f"Validation failed: {str(e)}"]
            )
    
    def validate_specimen_folder(self, specimen_folder: Union[str, Path]) -> Dict[str, ValidationResult]:
        """
        Validate all TTL files in a specimen folder.
        
        Expected structure:
        SPN-MaterialID-XXX/
        ├── SPN-*_specimen.ttl
        ├── SPN-*_TEST_DATE.ttl
        └── ...
        
        Returns:
            Dictionary mapping file names to validation results
        """
        
        folder_path = Path(specimen_folder)
        if not folder_path.exists():
            return {"error": ValidationResult(
                conforms=False,
                errors=[f"Specimen folder not found: {folder_path}"]
            )}
        
        results = {}
        
        # Find and validate specimen file
        specimen_files = list(folder_path.glob("*_specimen.ttl"))
        if specimen_files:
            for specimen_file in specimen_files:
                results[specimen_file.name] = self.validate_file(
                    specimen_file, class_name="Specimen"
                )
        
        # Find and validate test files
        test_files = list(folder_path.glob("*_TEST_*.ttl"))
        for test_file in test_files:
            # Try to detect test type from filename or content
            test_class = self._detect_test_class(test_file)
            results[test_file.name] = self.validate_file(
                test_file, class_name=test_class
            )
        
        # Find and validate other TTL files
        other_files = [f for f in folder_path.glob("*.ttl") 
                      if f not in specimen_files and f not in test_files]
        for other_file in other_files:
            results[other_file.name] = self.validate_file(other_file)
        
        return results
    
    def validate_experimental_dataset(self, base_folder: Union[str, Path]) -> Dict[str, Any]:
        """
        Validate complete experimental dataset with multiple specimens.
        
        Args:
            base_folder: Base folder containing specimen subfolders
            
        Returns:
            Comprehensive validation report
        """
        
        base_path = Path(base_folder)
        if not base_path.exists():
            return {
                "conforms": False,
                "error": f"Base folder not found: {base_path}"
            }
        
        # Find all specimen folders
        specimen_folders = [d for d in base_path.iterdir() 
                          if d.is_dir() and d.name.startswith("SPN-")]
        
        dataset_results = {
            "base_folder": str(base_path),
            "validation_timestamp": datetime.now().isoformat(),
            "specimen_count": len(specimen_folders),
            "specimens": {},
            "summary": {
                "total_files": 0,
                "valid_files": 0,
                "invalid_files": 0,
                "error_files": 0
            }
        }
        
        # Validate each specimen folder
        for specimen_folder in specimen_folders:
            specimen_results = self.validate_specimen_folder(specimen_folder)
            dataset_results["specimens"][specimen_folder.name] = specimen_results
            
            # Update summary
            for file_name, result in specimen_results.items():
                dataset_results["summary"]["total_files"] += 1
                if result.conforms:
                    dataset_results["summary"]["valid_files"] += 1
                else:
                    dataset_results["summary"]["invalid_files"] += 1
                if result.errors:
                    dataset_results["summary"]["error_files"] += 1
        
        # Overall conformance
        dataset_results["conforms"] = (
            dataset_results["summary"]["invalid_files"] == 0 and
            dataset_results["summary"]["error_files"] == 0
        )
        
        return dataset_results
    
    def _validate_with_pyshacl(self, data_graph: Graph, shapes_graph: Graph) -> ValidationResult:
        """Perform validation using pyshacl library"""
        
        try:
            # Combine with ontology for inference
            ontology_graph = self.ontology_manager.graph if self.ontology_manager else None
            
            conforms, report_graph, report_text = pyshacl.validate(
                data_graph=data_graph,
                shacl_graph=shapes_graph,
                ont_graph=ontology_graph,
                inference=self.default_inference,
                advanced=self.advanced,
                js=self.js,
                debug=False
            )
            
            # Parse report for detailed information
            errors, warnings, infos = self._parse_validation_report(report_graph)
            
            return ValidationResult(
                conforms=conforms,
                graph=data_graph,
                report_text=report_text,
                report_graph=report_graph,
                error_count=len(errors),
                warning_count=len(warnings),
                info_count=len(infos),
                errors=errors,
                warnings=warnings,
                infos=infos
            )
            
        except Exception as e:
            logging.error(f"pyshacl validation failed: {e}")
            return ValidationResult(
                conforms=False,
                errors=[f"pyshacl validation error: {str(e)}"]
            )
    
    def _validate_basic(self, data_graph: Graph, class_name: str) -> ValidationResult:
        """Basic validation without pyshacl"""
        
        if not class_name:
            return ValidationResult(
                conforms=False,
                errors=["Cannot perform basic validation without class name"]
            )
        
        # Get shape for basic validation
        shape = self.shape_manager.get_shape(class_name)
        if not shape:
            return ValidationResult(
                conforms=False,
                warnings=[f"No shape found for {class_name}, skipping validation"]
            )
        
        errors = []
        warnings = []
        
        # Check for instances of the expected class
        class_uri = self.dyn[class_name]
        instances = list(data_graph.subjects(RDF.type, class_uri))
        
        if not instances:
            errors.append(f"No instances of {class_name} found in data")
            return ValidationResult(
                conforms=False,
                errors=errors
            )
        
        # Basic property validation for each instance
        for instance in instances:
            for prop in shape.properties:
                if prop.min_count and prop.min_count > 0:
                    prop_uri = self.dyn[prop.path]
                    values = list(data_graph.objects(instance, prop_uri))
                    
                    if len(values) < prop.min_count:
                        errors.append(
                            f"Required property {prop.display_name} missing for {instance}"
                        )
        
        return ValidationResult(
            conforms=len(errors) == 0,
            graph=data_graph,
            errors=errors,
            warnings=warnings,
            error_count=len(errors),
            warning_count=len(warnings)
        )
    
    def _get_shapes_graph(self, class_name: Optional[str]) -> Optional[Graph]:
        """Get appropriate shapes graph for validation"""
        
        if not self.shape_manager:
            return None
        
        # Try to load shapes from shape manager
        try:
            # Load all static shapes
            shapes_graph = Graph()
            
            # Bind namespaces
            shapes_graph.bind("dyn", self.dyn)
            shapes_graph.bind("sh", self.sh)
            shapes_graph.bind("rdfs", RDFS)
            shapes_graph.bind("xsd", XSD)
            
            # Load from shapes directory if available
            shapes_dir = self.shape_manager.shapes_dir
            if shapes_dir.exists():
                for shape_file in shapes_dir.glob("*.ttl"):
                    try:
                        shapes_graph.parse(str(shape_file), format="turtle")
                    except Exception as e:
                        logging.warning(f"Could not load shape file {shape_file}: {e}")
            
            return shapes_graph if len(shapes_graph) > 0 else None
            
        except Exception as e:
            logging.error(f"Failed to load shapes graph: {e}")
            return None
    
    def _detect_primary_class(self, graph: Graph) -> Optional[str]:
        """Detect the primary class type in a graph"""
        
        # Look for common DynaMat classes
        common_classes = [
            "Specimen", "MechanicalTest", "SHPBTest", "TensileTest", 
            "CompressionTest", "Material", "AluminiumAlloy", "User",
            "Equipment", "Characterization"
        ]
        
        for class_name in common_classes:
            class_uri = self.dyn[class_name]
            instances = list(graph.subjects(RDF.type, class_uri))
            if instances:
                return class_name
        
        # If nothing found, return None
        return None
    
    def _detect_test_class(self, test_file: Path) -> str:
        """Detect test class from filename or content"""
        
        filename = test_file.name.lower()
        
        if "shpb" in filename:
            return "SHPBTest"
        elif "tensile" in filename:
            return "TensileTest"
        elif "compression" in filename:
            return "CompressionTest"
        else:
            # Try to detect from file content
            try:
                graph = Graph()
                graph.parse(str(test_file), format="turtle")
                detected = self._detect_primary_class(graph)
                return detected or "MechanicalTest"
            except:
                return "MechanicalTest"
    
    def _parse_validation_report(self, report_graph: Graph) -> Tuple[List[str], List[str], List[str]]:
        """Parse SHACL validation report to extract messages"""
        
        errors = []
        warnings = []
        infos = []
        
        if not report_graph:
            return errors, warnings, infos
        
        # Query for validation results
        query = """
        SELECT ?severity ?message ?focusNode ?path WHERE {
            ?result a sh:ValidationResult .
            ?result sh:resultSeverity ?severity .
            ?result sh:resultMessage ?message .
            OPTIONAL { ?result sh:focusNode ?focusNode }
            OPTIONAL { ?result sh:resultPath ?path }
        }
        """
        
        for row in report_graph.query(query):
            severity = str(row.severity)
            message = str(row.message)
            
            # Add context if available
            if row.focusNode:
                focus = str(row.focusNode).split('#')[-1]
                message += f" (Focus: {focus})"
            
            if row.path:
                path = str(row.path).split('#')[-1]
                message += f" (Property: {path})"
            
            if "Violation" in severity:
                errors.append(message)
            elif "Warning" in severity:
                warnings.append(message)
            else:
                infos.append(message)
        
        return errors, warnings, infos
    
    def save_validation_report(self, result: ValidationResult, 
                              output_path: Union[str, Path]) -> Path:
        """Save validation report to file"""
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"# DynaMat Validation Report\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n\n")
            f.write(f"Conforms: {result.conforms}\n\n")
            
            if result.errors:
                f.write(f"## Errors ({len(result.errors)})\n")
                for error in result.errors:
                    f.write(f"- {error}\n")
                f.write("\n")
            
            if result.warnings:
                f.write(f"## Warnings ({len(result.warnings)})\n")
                for warning in result.warnings:
                    f.write(f"- {warning}\n")
                f.write("\n")
            
            if result.infos:
                f.write(f"## Information ({len(result.infos)})\n")
                for info in result.infos:
                    f.write(f"- {info}\n")
                f.write("\n")
            
            if result.report_text:
                f.write("## Full Report\n")
                f.write("```\n")
                f.write(result.report_text)
                f.write("\n```\n")
        
        return output_file


# Convenience functions
def validate_specimen_file(ttl_file: Union[str, Path]) -> ValidationResult:
    """Quick validation for specimen files"""
    validator = SHACLValidator()
    return validator.validate_file(ttl_file, class_name="Specimen")


def validate_test_file(ttl_file: Union[str, Path], 
                      test_type: str = "MechanicalTest") -> ValidationResult:
    """Quick validation for test files"""
    validator = SHACLValidator()
    return validator.validate_file(ttl_file, class_name=test_type)


def validate_spn_folder(folder_path: Union[str, Path]) -> Dict[str, ValidationResult]:
    """Quick validation for complete specimen folder"""
    validator = SHACLValidator()
    return validator.validate_specimen_folder(folder_path)


# Integration with existing validation workflow
def validate_with_shacl(shapes_file: Union[str, Path], 
                       data_file: Union[str, Path]) -> ValidationResult:
    """
    Validate data file against specific shapes file.
    This function maintains compatibility with existing validation calls.
    """
    validator = SHACLValidator()
    return validator.validate_file(data_file, shapes_file=shapes_file)