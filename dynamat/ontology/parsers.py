"""
DynaMat RDF Parsers

Improved TTL parsing utilities that solve the nested relationship traversal problem.
This replaces the multiple callout approach with single-call methods.
"""

from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
import rdflib
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL

from ..config import config


@dataclass
class MeasurementValue:
    """Represents a measurement with value and units"""
    value: float
    unit: str
    property_name: str
    description: Optional[str] = None


@dataclass  
class ExperimentalData:
    """Structured representation of experimental RDF data"""
    specimen_id: str
    test_id: str
    measurements: Dict[str, MeasurementValue]
    properties: Dict[str, Any]
    relationships: Dict[str, str]
    metadata: Dict[str, Any]


class ImprovedRDFParser:
    """
    Improved RDF parser that handles multi-file experiments.
    
    Can correlate specimen TTL + activity TTLs + data files for complete experiments.
    Handles unique URI identification across multiple loaded experiments.
    """
    
    def __init__(self, rdf_file_path: Optional[Union[str, Path]] = None):
        """Initialize parser with optional RDF file"""
        self.graph = Graph()
        self.dyn = Namespace(config.ONTOLOGY_URI)
        
        # Track loaded files and their relationships
        self.loaded_files = []
        self.file_relationships = {}  # Maps experiment_id -> list of related files
        self.uri_registry = {}        # Maps local_name -> full_uri for uniqueness
        
        # Bind common namespaces
        self.graph.bind("dyn", self.dyn)
        self.graph.bind("rdf", RDF)
        self.graph.bind("rdfs", RDFS)
        self.graph.bind("owl", OWL)
        
        if rdf_file_path:
            self.load_file(rdf_file_path)
    
    def load_file(self, rdf_file_path: Union[str, Path], format: str = "turtle"):
        """Load an RDF file into the graph and track relationships"""
        try:
            file_path = Path(rdf_file_path)
            self.graph.parse(str(file_path), format=format)
            self.loaded_files.append(file_path)
            
            # Detect experiment relationships from filename patterns
            self._detect_file_relationships(file_path)
            
            # Register URIs for uniqueness tracking
            self._register_uris_from_file(file_path)
            
        except Exception as e:
            raise Exception(f"Failed to load RDF file {rdf_file_path}: {e}")
    
    def load_experiment_files(self, file_paths: List[Union[str, Path]]) -> str:
        """
        Load multiple related files for one experiment.
        
        Args:
            file_paths: List of TTL files (specimen, activities, etc.)
            
        Returns:
            experiment_id: Common identifier for the experiment
        """
        experiment_id = None
        
        for file_path in file_paths:
            self.load_file(file_path)
            
            # Determine experiment ID from filename or content
            current_exp_id = self._extract_experiment_id(Path(file_path))
            if experiment_id is None:
                experiment_id = current_exp_id
            elif experiment_id != current_exp_id:
                print(f"Warning: File {file_path} appears to belong to different experiment")
        
        return experiment_id
    
    def get_experiment_files(self, experiment_id: str) -> List[Path]:
        """Get all files related to an experiment"""
        return self.file_relationships.get(experiment_id, [])
    
    def get_all_experiments(self) -> List[str]:
        """Get all experiment IDs currently loaded"""
        return list(self.file_relationships.keys())
    
    def _detect_file_relationships(self, file_path: Path):
        """Detect which experiment this file belongs to based on naming patterns"""
        # Extract experiment ID from filename patterns like:
        # SPN-AL001_specimen.ttl
        # SPN-AL001_TEST_2025-01-15.ttl
        # SPN-AL001_characterization.ttl
        
        filename = file_path.stem
        
        # Pattern: SPN-MaterialID-XXX or similar
        if '_' in filename:
            potential_exp_id = filename.split('_')[0]
        else:
            potential_exp_id = filename
        
        # Extract actual experiment ID from content if needed
        experiment_id = self._extract_experiment_id(file_path)
        
        if experiment_id not in self.file_relationships:
            self.file_relationships[experiment_id] = []
        
        if file_path not in self.file_relationships[experiment_id]:
            self.file_relationships[experiment_id].append(file_path)
    
    def _extract_experiment_id(self, file_path: Path) -> str:
        """Extract experiment ID from file content or name"""
        # Try to find specimen or test URIs in the file content
        temp_graph = Graph()
        temp_graph.parse(str(file_path), format="turtle")
        
        # Look for specimen URIs
        specimen_query = """
        SELECT ?specimen WHERE {
            ?specimen a dyn:Specimen .
        }
        """
        
        for row in temp_graph.query(specimen_query):
            specimen_uri = str(row.specimen)
            return self._extract_name_from_uri(specimen_uri)
        
        # Look for test URIs
        test_query = """
        SELECT ?test WHERE {
            ?test a/rdfs:subClassOf* dyn:MechanicalTest .
        }
        """
        
        for row in temp_graph.query(test_query):
            test_uri = str(row.test)
            test_name = self._extract_name_from_uri(test_uri)
            # Extract specimen part from test name (assuming pattern like SPN-AL001_TEST_001)
            if '_' in test_name:
                return test_name.split('_')[0]
            return test_name
        
        # Fallback to filename
        return file_path.stem.split('_')[0]
    
    def _register_uris_from_file(self, file_path: Path):
        """Register URIs from file to track uniqueness"""
        temp_graph = Graph()
        temp_graph.parse(str(file_path), format="turtle")
        
        # Get all subjects that are not blank nodes
        for subject in temp_graph.subjects():
            if isinstance(subject, URIRef):
                local_name = self._extract_name_from_uri(str(subject))
                full_uri = str(subject)
                
                # Check for URI conflicts
                if local_name in self.uri_registry:
                    existing_uri = self.uri_registry[local_name]
                    if existing_uri != full_uri:
                        print(f"Warning: URI conflict for '{local_name}': {existing_uri} vs {full_uri}")
                
                self.uri_registry[local_name] = full_uri
    
    def merge_graph(self, other_graph: Graph):
        """Merge another graph into this one"""
        for triple in other_graph:
            self.graph.add(triple)
    
    # =============================================================================
    # SINGLE-CALL MEASUREMENT EXTRACTION - SOLVES NESTED TRAVERSAL
    # =============================================================================
    
    def get_specimen_measurements(self, specimen_uri: str) -> Dict[str, MeasurementValue]:
        """
        Get all measurements for a specimen in a single call.
        
        This replaces the nested approach:
        OLD: specimen -> dimensions -> original_length -> value + unit (3+ calls)
        NEW: get_specimen_measurements(specimen) -> all measurements (1 call)
        """
        measurements = {}
        specimen_uri = self._ensure_uri(specimen_uri)
        
        # Query for all measurements through various paths
        query = f"""
        SELECT ?measurement ?measurementName ?value ?unit ?unitName WHERE {{
            # Direct measurements
            {{
                <{specimen_uri}> ?prop ?measurement .
                ?measurement a/rdfs:subClassOf* dyn:Geometry .
                ?measurement rdfs:label ?measurementName .
                ?measurement dyn:hasValue ?value .
                ?measurement dyn:hasUnits ?unit .
                ?unit rdfs:label ?unitName .
            }}
            UNION
            # Through hasDimension
            {{
                <{specimen_uri}> dyn:hasDimension ?measurement .
                ?measurement rdfs:label ?measurementName .
                ?measurement dyn:hasValue ?value .
                ?measurement dyn:hasUnits ?unit .
                ?unit rdfs:label ?unitName .
            }}
            UNION
            # Through hasMechanicalProperty
            {{
                <{specimen_uri}> dyn:hasMechanicalProperty ?measurement .
                ?measurement rdfs:label ?measurementName .
                ?measurement dyn:hasValue ?value .
                ?measurement dyn:hasUnits ?unit .
                ?unit rdfs:label ?unitName .
            }}
        }}
        """
        
        for row in self.graph.query(query):
            measurement_name = str(row.measurementName)
            value = float(row.value) if row.value else None
            unit_name = str(row.unitName)
            
            measurements[measurement_name] = MeasurementValue(
                value=value,
                unit=unit_name,
                property_name=measurement_name
            )
        
        return measurements
    
    def get_test_results(self, test_uri: str) -> Dict[str, MeasurementValue]:
        """Get all test results (stress, strain, etc.) in a single call"""
        results = {}
        test_uri = self._ensure_uri(test_uri)
        
        query = f"""
        SELECT ?seriesData ?dataName ?value ?unit ?unitName WHERE {{
            <{test_uri}> dyn:hasSeriesData ?seriesData .
            ?seriesData rdfs:label ?dataName .
            ?seriesData dyn:hasValue ?value .
            ?seriesData dyn:hasUnits ?unit .
            ?unit rdfs:label ?unitName .
        }}
        """
        
        for row in self.graph.query(query):
            data_name = str(row.dataName)
            value = self._convert_literal(row.value)
            unit_name = str(row.unitName)
            
            results[data_name] = MeasurementValue(
                value=value,
                unit=unit_name,
                property_name=data_name
            )
        
        return results
    
    # =============================================================================
    # COMPLETE EXPERIMENTAL DATA EXTRACTION
    # =============================================================================
    
    def get_experimental_data(self, test_uri: str) -> ExperimentalData:
        """
        Extract complete experimental data in a single call.
        
        Returns all specimen info, test conditions, measurements, etc.
        """
        test_uri = self._ensure_uri(test_uri)
        
        # Get basic test info
        test_info = self._get_basic_info(test_uri)
        
        # Get specimen URI
        specimen_uri = self._get_specimen_for_test(test_uri)
        if not specimen_uri:
            raise ValueError(f"No specimen found for test {test_uri}")
        
        # Get all measurements
        specimen_measurements = self.get_specimen_measurements(specimen_uri)
        test_results = self.get_test_results(test_uri)
        
        # Combine measurements
        all_measurements = {**specimen_measurements, **test_results}
        
        # Get properties and relationships
        properties = self._get_data_properties(test_uri)
        relationships = self._get_object_properties(test_uri)
        
        return ExperimentalData(
            specimen_id=self._extract_name_from_uri(specimen_uri),
            test_id=self._extract_name_from_uri(test_uri),
            measurements=all_measurements,
            properties=properties,
            relationships=relationships,
            metadata=test_info
        )
    
    # =============================================================================
    # BACKWARD COMPATIBILITY AND GAP FILLING
    # =============================================================================
    
    def detect_missing_properties(self, ontology_manager) -> Dict[str, Dict[str, List[str]]]:
        """
        Detect missing properties in loaded experiments based on current ontology.
        
        Returns:
            Dictionary mapping experiment_id -> class_name -> [missing_properties]
        """
        missing_properties = {}
        
        for experiment_id in self.get_all_experiments():
            missing_properties[experiment_id] = {}
            
            # Check specimens in this experiment
            specimens = self.get_specimens_in_experiment(experiment_id)
            for specimen_uri in specimens:
                specimen_class = "Specimen"
                expected_props = ontology_manager.get_class_properties(specimen_class)
                existing_props = self._get_existing_properties(specimen_uri)
                
                missing = [prop.name for prop in expected_props 
                          if prop.name not in existing_props]
                
                if missing:
                    specimen_id = self._extract_name_from_uri(specimen_uri)
                    missing_properties[experiment_id][specimen_id] = missing
            
            # Check tests in this experiment
            tests = self.get_tests_in_experiment(experiment_id)
            for test_uri in tests:
                test_class = self._get_test_class(test_uri)
                expected_props = ontology_manager.get_class_properties(test_class)
                existing_props = self._get_existing_properties(test_uri)
                
                missing = [prop.name for prop in expected_props 
                          if prop.name not in existing_props]
                
                if missing:
                    test_id = self._extract_name_from_uri(test_uri)
                    missing_properties[experiment_id][test_id] = missing
        
        return missing_properties
    
    def suggest_property_updates(self, experiment_id: str, ontology_manager) -> Dict[str, Any]:
        """
        Suggest updates for an experiment based on missing properties.
        
        Returns:
            Dictionary with suggested updates and their importance levels
        """
        missing = self.detect_missing_properties(ontology_manager)
        experiment_missing = missing.get(experiment_id, {})
        
        suggestions = {
            'critical': [],      # Properties needed for validation
            'recommended': [],   # Properties that improve analysis
            'optional': []       # Nice-to-have properties
        }
        
        for entity_id, missing_props in experiment_missing.items():
            for prop in missing_props:
                # Categorize based on property importance (this could be enhanced)
                if prop in ['hasMaterial', 'hasTestingConditions', 'performedOn']:
                    suggestions['critical'].append({
                        'entity': entity_id,
                        'property': prop,
                        'reason': 'Required for validation'
                    })
                elif prop in ['hasUnits', 'hasValue', 'hasDate']:
                    suggestions['recommended'].append({
                        'entity': entity_id,
                        'property': prop,
                        'reason': 'Improves data analysis'
                    })
                else:
                    suggestions['optional'].append({
                        'entity': entity_id,
                        'property': prop,
                        'reason': 'Additional metadata'
                    })
        
        return suggestions
    
    def update_experiment_with_missing_properties(
        self, 
        experiment_id: str, 
        property_updates: Dict[str, Dict[str, Any]]
    ) -> bool:
        """
        Update an experiment's TTL files with missing properties.
        
        Args:
            experiment_id: The experiment to update
            property_updates: Dict mapping entity_id -> {property: value}
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get files for this experiment
            exp_files = self.get_experiment_files(experiment_id)
            
            for entity_id, updates in property_updates.items():
                # Find which file contains this entity
                entity_uri = self._find_entity_uri(entity_id)
                if not entity_uri:
                    continue
                
                # Add missing properties to graph
                for prop_name, value in updates.items():
                    self._add_property_to_graph(entity_uri, prop_name, value)
            
            # Save updated graphs back to files
            self._save_updated_files(experiment_id, exp_files)
            return True
            
        except Exception as e:
            print(f"Error updating experiment {experiment_id}: {e}")
            return False
    
    def get_specimens_in_experiment(self, experiment_id: str) -> List[str]:
        """Get all specimen URIs in an experiment"""
        query = f"""
        SELECT DISTINCT ?specimen WHERE {{
            ?specimen a dyn:Specimen .
            FILTER(CONTAINS(STR(?specimen), "{experiment_id}"))
        }}
        """
        return [str(row.specimen) for row in self.graph.query(query)]
    
    def get_tests_in_experiment(self, experiment_id: str) -> List[str]:
        """Get all test URIs in an experiment"""
        query = f"""
        SELECT DISTINCT ?test WHERE {{
            ?test a/rdfs:subClassOf* dyn:MechanicalTest .
            FILTER(CONTAINS(STR(?test), "{experiment_id}"))
        }}
        """
        return [str(row.test) for row in self.graph.query(query)]
    
    def _get_existing_properties(self, entity_uri: str) -> List[str]:
        """Get all existing properties for an entity"""
        query = f"""
        SELECT DISTINCT ?prop WHERE {{
            <{entity_uri}> ?prop ?value .
            FILTER(?prop != rdf:type && ?prop != rdfs:label)
        }}
        """
        return [self._extract_name_from_uri(str(row.prop)) for row in self.graph.query(query)]
    
    def _get_test_class(self, test_uri: str) -> str:
        """Get the class of a test"""
        query = f"""
        SELECT ?type WHERE {{
            <{test_uri}> a ?type .
            ?type rdfs:subClassOf* dyn:MechanicalTest .
        }}
        """
        for row in self.graph.query(query):
            return self._extract_name_from_uri(str(row.type))
        return "MechanicalTest"
    
    def _find_entity_uri(self, entity_id: str) -> Optional[str]:
        """Find the full URI for an entity ID"""
        if entity_id in self.uri_registry:
            return self.uri_registry[entity_id]
        
        # Search in loaded data
        query = f"""
        SELECT ?entity WHERE {{
            ?entity ?prop ?value .
            FILTER(CONTAINS(STR(?entity), "{entity_id}"))
        }}
        LIMIT 1
        """
        for row in self.graph.query(query):
            return str(row.entity)
        
        return None
    
    def _add_property_to_graph(self, entity_uri: str, prop_name: str, value: Any):
        """Add a property to the graph"""
        predicate_uri = f"{self.dyn}{prop_name}"
        
        if isinstance(value, str) and value.startswith("dyn:"):
            # Object property
            object_uri = value.replace("dyn:", str(self.dyn))
            self.graph.add((URIRef(entity_uri), URIRef(predicate_uri), URIRef(object_uri)))
        else:
            # Data property
            self.graph.add((URIRef(entity_uri), URIRef(predicate_uri), Literal(value)))
    
    def _save_updated_files(self, experiment_id: str, file_paths: List[Path]):
        """Save updated graphs back to their original files"""
        # This would need more sophisticated implementation to split
        # the combined graph back into separate files
        # For now, create a backup and save combined
        
        backup_dir = Path("backups") / experiment_id
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Create backup of original files
        for file_path in file_paths:
            backup_path = backup_dir / file_path.name
            backup_path.write_text(file_path.read_text())
        
        # Save updated graph (simplified - saves everything to one file)
        updated_file = backup_dir.parent / f"{experiment_id}_updated.ttl"
        with open(updated_file, 'w') as f:
            f.write(self.graph.serialize(format='turtle'))
        
        print(f"Updated experiment saved to {updated_file}")
        print(f"Original files backed up to {backup_dir}")
    
    def get_all_specimens(self) -> List[str]:
        """Get all specimen URIs in the graph"""
        query = """
        SELECT DISTINCT ?specimen WHERE {
            ?specimen a dyn:Specimen .
        }
        """
        return [str(row.specimen) for row in self.graph.query(query)]
    
    def get_all_tests(self) -> List[str]:
        """Get all test URIs in the graph"""
        query = """
        SELECT DISTINCT ?test WHERE {
            ?test a/rdfs:subClassOf* dyn:MechanicalTest .
        }
        """
        return [str(row.test) for row in self.graph.query(query)]
    
    def get_specimens_by_material(self, material_name: str) -> List[str]:
        """Get all specimens of a specific material"""
        query = f"""
        SELECT ?specimen WHERE {{
            ?specimen a dyn:Specimen .
            ?specimen dyn:hasMaterial ?material .
            ?material rdfs:label "{material_name}" .
        }}
        """
        return [str(row.specimen) for row in self.graph.query(query)]
    
    def get_tests_by_type(self, test_type: str) -> List[str]:
        """Get all tests of a specific type"""
        query = f"""
        SELECT ?test WHERE {{
            ?test a dyn:{test_type} .
        }}
        """
        return [str(row.test) for row in self.graph.query(query)]
    
    # =============================================================================
    # DATA EXPORT METHODS
    # =============================================================================
    
    def export_specimen_summary(self, specimen_uri: str) -> Dict[str, Any]:
        """Export complete specimen summary as dictionary"""
        specimen_uri = self._ensure_uri(specimen_uri)
        
        summary = {
            'specimen_id': self._extract_name_from_uri(specimen_uri),
            'measurements': {},
            'material': None,
            'structure': None,
            'processing_history': []
        }
        
        # Get measurements
        measurements = self.get_specimen_measurements(specimen_uri)
        summary['measurements'] = {
            name: {'value': m.value, 'unit': m.unit} 
            for name, m in measurements.items()
        }
        
        # Get material
        material_query = f"""
        SELECT ?material ?materialName WHERE {{
            <{specimen_uri}> dyn:hasMaterial ?material .
            ?material rdfs:label ?materialName .
        }}
        """
        for row in self.graph.query(material_query):
            summary['material'] = str(row.materialName)
            break
        
        # Get structure
        structure_query = f"""
        SELECT ?structure ?structureName WHERE {{
            <{specimen_uri}> dyn:hasStructure ?structure .
            ?structure rdfs:label ?structureName .
        }}
        """
        for row in self.graph.query(structure_query):
            summary['structure'] = str(row.structureName)
            break
        
        return summary
    
    def export_test_summary(self, test_uri: str) -> Dict[str, Any]:
        """Export complete test summary as dictionary"""
        test_uri = self._ensure_uri(test_uri)
        
        summary = {
            'test_id': self._extract_name_from_uri(test_uri),
            'test_type': None,
            'specimen_id': None,
            'conditions': {},
            'results': {}
        }
        
        # Get test type
        type_query = f"""
        SELECT ?type WHERE {{
            <{test_uri}> a ?type .
            ?type rdfs:subClassOf* dyn:MechanicalTest .
        }}
        """
        for row in self.graph.query(type_query):
            summary['test_type'] = self._extract_name_from_uri(str(row.type))
            break
        
        # Get specimen
        specimen_uri = self._get_specimen_for_test(test_uri)
        if specimen_uri:
            summary['specimen_id'] = self._extract_name_from_uri(specimen_uri)
        
        # Get test results
        results = self.get_test_results(test_uri)
        summary['results'] = {
            name: {'value': r.value, 'unit': r.unit}
            for name, r in results.items()
        }
        
        return summary
    
    # =============================================================================
    # PRIVATE HELPER METHODS
    # =============================================================================
    
    def _ensure_uri(self, uri_or_name: str) -> str:
        """Ensure input is a full URI"""
        if uri_or_name.startswith("http"):
            return uri_or_name
        else:
            return f"{config.ONTOLOGY_URI}{uri_or_name}"
    
    def _extract_name_from_uri(self, uri: str) -> str:
        """Extract local name from URI"""
        if '#' in uri:
            return uri.split('#')[-1]
        elif '/' in uri:
            return uri.split('/')[-1]
        return uri
    
    def _get_specimen_for_test(self, test_uri: str) -> Optional[str]:
        """Get the specimen URI for a test"""
        query = f"""
        SELECT ?specimen WHERE {{
            <{test_uri}> dyn:performedOn ?specimen .
        }}
        """
        for row in self.graph.query(query):
            return str(row.specimen)
        return None
    
    def _get_basic_info(self, uri: str) -> Dict[str, Any]:
        """Get basic RDF info (name, comment, etc.)"""
        info = {}
        query = f"""
        SELECT ?prop ?value WHERE {{
            <{uri}> ?prop ?value .
            FILTER(?prop IN (rdfs:label, rdfs:comment, dyn:hasName, dyn:hasDate))
        }}
        """
        for row in self.graph.query(query):
            prop_name = self._extract_name_from_uri(str(row.prop))
            info[prop_name] = str(row.value)
        return info
    
    def _get_data_properties(self, uri: str) -> Dict[str, Any]:
        """Get all data properties for a URI"""
        properties = {}
        query = f"""
        SELECT ?prop ?value WHERE {{
            <{uri}> ?prop ?value .
            FILTER(isLiteral(?value))
            FILTER(?prop NOT IN (rdfs:label, rdfs:comment, dyn:hasValue))
        }}
        """
        for row in self.graph.query(query):
            prop_name = self._extract_name_from_uri(str(row.prop))
            properties[prop_name] = self._convert_literal(row.value)
        return properties
    
    def _get_object_properties(self, uri: str) -> Dict[str, str]:
        """Get all object properties for a URI"""
        relationships = {}
        query = f"""
        SELECT ?prop ?value WHERE {{
            <{uri}> ?prop ?value .
            FILTER(isURI(?value))
            FILTER(?prop NOT IN (rdf:type, dyn:hasUnits))
        }}
        """
        for row in self.graph.query(query):
            prop_name = self._extract_name_from_uri(str(row.prop))
            relationships[prop_name] = self._extract_name_from_uri(str(row.value))
        return relationships
    
    def _convert_literal(self, literal: Literal) -> Any:
        """Convert RDF literal to appropriate Python type"""
        if literal.datatype:
            datatype = str(literal.datatype)
            if 'float' in datatype or 'double' in datatype:
                return float(literal)
            elif 'int' in datatype:
                return int(literal)
            elif 'boolean' in datatype:
                return bool(literal)
            elif 'date' in datatype:
                return str(literal)
        return str(literal)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def load_experimental_data(file_path: Union[str, Path]) -> ExperimentalData:
    """Convenience function to load experimental data from a TTL file"""
    parser = ImprovedRDFParser(file_path)
    
    # Find the test in the file
    tests = parser.get_all_tests()
    if not tests:
        raise ValueError(f"No tests found in {file_path}")
    
    # Return data for the first test found
    return parser.get_experimental_data(tests[0])


def merge_experimental_files(file_paths: List[Union[str, Path]]) -> ImprovedRDFParser:
    """Merge multiple experimental TTL files into one parser"""
    parser = ImprovedRDFParser()
    
    for file_path in file_paths:
        parser.load_file(file_path)
    
    return parser


def extract_measurements_to_dict(file_path: Union[str, Path]) -> Dict[str, Dict]:
    """Extract all measurements from a file as nested dictionaries"""
    parser = ImprovedRDFParser(file_path)
    
    result = {
        'specimens': {},
        'tests': {}
    }
    
    # Extract specimen measurements
    for specimen_uri in parser.get_all_specimens():
        specimen_id = parser._extract_name_from_uri(specimen_uri)
        measurements = parser.get_specimen_measurements(specimen_uri)
        
        result['specimens'][specimen_id] = {
            name: {'value': m.value, 'unit': m.unit}
            for name, m in measurements.items()
        }
    
    # Extract test results
    for test_uri in parser.get_all_tests():
        test_id = parser._extract_name_from_uri(test_uri)
        results = parser.get_test_results(test_uri)
        
        result['tests'][test_id] = {
            name: {'value': r.value, 'unit': r.unit}
            for name, r in results.items()
        }
    
    return result