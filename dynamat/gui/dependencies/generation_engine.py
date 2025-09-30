"""
DynaMat Platform - Generation Engine
Template-based value generation for form fields
"""

import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


class GenerationEngine:
    """
    Handles template-based value generation for form fields.
    
    Provides generators for IDs, codes, and other formatted values.
    """
    
    def __init__(self, ontology_manager):
        """
        Initialize the generation engine.
        
        Args:
            ontology_manager: Reference to ontology manager for queries
        """
        self.logger = logging.getLogger(__name__)
        self.ontology_manager = ontology_manager
        
        # Registry of generation functions
        self._generators: Dict[str, Callable] = {
            'specimen_id': self._generate_specimen_id,
            'material_code': self._generate_material_code,
            'batch_id': self._generate_batch_id,
            'test_id': self._generate_test_id,
            'timestamp': self._generate_timestamp,
        }
        
        self.logger.info("Generation engine initialized")
    
    # ============================================================================
    # PUBLIC API
    # ============================================================================
    
    def generate(self, template: str, inputs: Dict[str, Any]) -> str:
        """
        Generate a value from a template and inputs.
        
        Args:
            template: Template string with {placeholders}
            inputs: Dictionary of input values
            
        Returns:
            Generated string
            
        Example:
            template = "DYNML-{materialCode}-{sequence}"
            inputs = {"materialCode": "AL001", "sequence": 5}
            result = "DYNML-AL001-00005"
        """
        try:
            # Process inputs
            processed_inputs = self._process_inputs(inputs)
            
            # Format template
            result = template.format(**processed_inputs)
            
            self.logger.debug(f"Generated value: {result}")
            return result
            
        except KeyError as e:
            self.logger.error(f"Missing required input for template: {e}")
            return ""
        except Exception as e:
            self.logger.error(f"Generation failed: {e}")
            return ""
    
    def register_generator(self, name: str, generator_func: Callable):
        """
        Register a custom generator function.
        
        Args:
            name: Name of the generator
            generator_func: Function that generates values
        """
        self._generators[name] = generator_func
        self.logger.info(f"Registered generator: {name}")
    
    def get_available_generators(self) -> list:
        """Get list of available generator names."""
        return list(self._generators.keys())
    
    def call_generator(self, generator_name: str, **kwargs) -> Any:
        """
        Call a specific generator function.
        
        Args:
            generator_name: Name of the generator
            **kwargs: Arguments for the generator
            
        Returns:
            Generated value
        """
        if generator_name not in self._generators:
            self.logger.error(f"Generator not found: {generator_name}")
            return None
        
        try:
            return self._generators[generator_name](**kwargs)
        except Exception as e:
            self.logger.error(f"Generator {generator_name} failed: {e}")
            return None
    
    # ============================================================================
    # INPUT PROCESSING
    # ============================================================================
    
    def _process_inputs(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process inputs before template formatting.
        
        Handles special processing like:
        - URI extraction (materialCode from material URI)
        - Sequence number formatting
        - Date formatting
        """
        processed = {}
        
        for key, value in inputs.items():
            # Handle material URI -> material code
            if key == "materialCode" and isinstance(value, str) and "#" in value:
                processed[key] = self._extract_material_code(value)
            
            # Handle sequence number formatting
            elif key == "sequence" and isinstance(value, int):
                processed[key] = f"{value:05d}"  # 5-digit padding
            
            # Handle dates
            elif key == "date" and isinstance(value, datetime):
                processed[key] = value.strftime("%Y%m%d")
            
            # Pass through others
            else:
                processed[key] = value
        
        return processed
    
    def _extract_material_code(self, material_uri: str) -> str:
        """
        Extract material code from a material URI.
        
        Args:
            material_uri: Full URI of the material
            
        Returns:
            Material code string
        """
        try:
            # Query ontology for material code
            query = """
            SELECT ?code WHERE {
                ?material dyn:hasMaterialCode ?code .
            }
            """
            from rdflib import URIRef
            results = self.ontology_manager.graph.query(
                query,
                initBindings={"material": URIRef(material_uri)}
            )
            
            for row in results:
                return str(row.code)
            
            # Fallback: extract local name from URI
            return material_uri.split("#")[-1].split("/")[-1]
            
        except Exception as e:
            self.logger.error(f"Failed to extract material code: {e}")
            return "UNKNOWN"
    
    # ============================================================================
    # BUILT-IN GENERATORS
    # ============================================================================
    
    def _generate_specimen_id(self, material_uri: str) -> str:
        """
        Generate a specimen ID from material.
        
        Format: DYNML-{materialCode}-{sequence}
        """
        material_code = self._extract_material_code(material_uri)
        sequence = self._get_next_specimen_sequence(material_code)
        return f"DYNML-{material_code}-{sequence:05d}"
    
    def _generate_material_code(self, material_name: str) -> str:
        """Generate a material code from material name."""
        # Simple implementation: first 6 chars uppercase
        return material_name[:6].upper().replace(" ", "")
    
    def _generate_batch_id(self, material_code: str, date: Optional[datetime] = None) -> str:
        """Generate a batch ID."""
        date_str = (date or datetime.now()).strftime("%Y%m%d")
        return f"BATCH-{material_code}-{date_str}"
    
    def _generate_test_id(self, specimen_id: str, test_type: str, 
                         date: Optional[datetime] = None) -> str:
        """Generate a test ID."""
        date_str = (date or datetime.now()).strftime("%Y%m%d")
        test_abbr = test_type[:4].upper()
        return f"{specimen_id}_{test_abbr}_{date_str}"
    
    def _generate_timestamp(self) -> str:
        """Generate a timestamp string."""
        return datetime.now().isoformat()
    
    def _get_next_specimen_sequence(self, material_code: str) -> int:
        """
        Get the next sequence number for a specimen with given material code.
        
        Args:
            material_code: Material code to check
            
        Returns:
            Next sequence number
        """
        try:
            # Query existing specimens with this material code
            query = """
            SELECT ?specimenID WHERE {
                ?specimen rdf:type dyn:Specimen .
                ?specimen dyn:hasSpecimenID ?specimenID .
                FILTER(CONTAINS(?specimenID, ?materialFilter))
            }
            """
            
            from rdflib import Literal
            results = self.ontology_manager.graph.query(
                query,
                initBindings={"materialFilter": Literal(f"DYNML-{material_code}-")}
            )
            
            max_sequence = 0
            prefix = f"DYNML-{material_code}-"
            
            for row in results:
                specimen_id = str(row.specimenID)
                if specimen_id.startswith(prefix):
                    try:
                        # Extract sequence number
                        sequence_str = specimen_id[len(prefix):]
                        sequence_num = int(sequence_str)
                        max_sequence = max(max_sequence, sequence_num)
                    except ValueError:
                        continue
            
            return max_sequence + 1
            
        except Exception as e:
            self.logger.error(f"Failed to get next sequence: {e}")
            return 1
    
    # ============================================================================
    # UTILITY METHODS
    # ============================================================================
    
    def test_template(self, template: str, sample_inputs: Dict[str, Any]) -> str:
        """
        Test a template with sample inputs.
        
        Useful for debugging and validation.
        """
        try:
            result = self.generate(template, sample_inputs)
            self.logger.info(f"Template test successful: {template} -> {result}")
            return result
        except Exception as e:
            self.logger.error(f"Template test failed: {e}")
            return f"ERROR: {e}"
    
    def validate_template(self, template: str) -> tuple[bool, str]:
        """
        Validate a template string.
        
        Returns:
            (is_valid, error_message)
        """
        try:
            # Extract placeholders
            import re
            placeholders = re.findall(r'\{(\w+)\}', template)
            
            if not placeholders:
                return False, "Template has no placeholders"
            
            # Check for valid placeholder names
            for placeholder in placeholders:
                if not placeholder.replace("_", "").isalnum():
                    return False, f"Invalid placeholder name: {placeholder}"
            
            return True, "Template is valid"
            
        except Exception as e:
            return False, str(e)