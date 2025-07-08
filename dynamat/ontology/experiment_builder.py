"""
DynaMat Experimental RDF Builder

Handles the creation of temporal RDF during GUI data entry and
final RDF generation after validation. Separate from reading/querying.

Workflow:
1. GUI input -> temporal RDF (captures triplets as user fills forms)
2. SHACL validation when complete
3. Generate final experimental TTL file
"""

from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from datetime import datetime
import rdflib
from rdflib import Graph, Namespace, URIRef, Literal, BNode
from rdflib.namespace import RDF, RDFS, OWL, XSD

from ..config import config


@dataclass
class MeasurementEntry:
    """Represents a measurement entry from GUI"""
    name: str
    value: float
    unit: str
    property_path: List[str]  # e.g., ["hasDimension", "OriginalLength"]


@dataclass  
class TemporalTriple:
    """Represents a triple being built during data entry"""
    subject: str
    predicate: str
    object: Union[str, float, int, bool, datetime]
    object_type: str  # "uri", "literal", "measurement"
    timestamp: datetime
    validated: bool = False


class ExperimentalRDFBuilder:
    """
    Builds experimental RDF data with unique URI management.
    
    URI Strategy:
    - Specimens: {base_uri}SPN-{MaterialCode}-{SerialNumber}
    - Tests: {base_uri}SPN-{MaterialCode}-{SerialNumber}_{TestType}_{Date}
    - Measurements: {parent_uri}_{MeasurementName}
    
    This ensures uniqueness across all experiments while maintaining readability.
    """
    
    def __init__(self, base_uri: Optional[str] = None, experiment_id: Optional[str] = None):
        """Initialize builder for new experimental data"""
        self.graph = Graph()
        self.temporal_triples = []  # Store triples as they're being built
        
        # Set up namespaces
        self.dyn = Namespace(config.ONTOLOGY_URI)
        self.base_uri = base_uri or config.SPECIMEN_URI
        
        # Experiment identification
        self.experiment_id = experiment_id or self._generate_experiment_id()
        
        self.graph.bind("dyn", self.dyn)
        self.graph.bind("rdf", RDF)
        self.graph.bind("rdfs", RDFS)
        self.graph.bind("owl", OWL)
        self.graph.bind("xsd", XSD)
        
        # Current session info
        self.current_specimen_uri = None
        self.current_test_uri = None
        self.session_timestamp = datetime.now()
        
        # URI uniqueness tracking
        self.uri_counter = {}  # Track counters for unique naming
    
    def _generate_experiment_id(self) -> str:
        """Generate unique experiment ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"EXP_{timestamp}"
    
    def _generate_unique_uri(self, base_name: str, uri_type: str) -> str:
        """
        Generate unique URI with collision avoidance.
        
        Args:
            base_name: Base name for the URI
            uri_type: Type of URI (specimen, test, measurement)
            
        Returns:
            Unique URI string
        """
        # Create counter key
        counter_key = f"{uri_type}_{base_name}"
        
        if counter_key not in self.uri_counter:
            self.uri_counter[counter_key] = 0
            unique_name = base_name
        else:
            self.uri_counter[counter_key] += 1
            unique_name = f"{base_name}_{self.uri_counter[counter_key]:03d}"
        
        return f"{self.base_uri}{unique_name}"
    
    # =============================================================================
    # SESSION MANAGEMENT
    # =============================================================================
    
    def start_specimen_session(self, specimen_id: str, material: str) -> str:
        """Start a new specimen data entry session"""
        self.current_specimen_uri = f"{self.base_uri}{specimen_id}"
        
        # Add basic specimen triples
        self.add_triple(
            subject=specimen_id,
            predicate="rdf:type",
            object="dyn:Specimen",
            object_type="uri"
        )
        
        self.add_triple(
            subject=specimen_id,
            predicate="dyn:hasSPN",
            object=specimen_id,
            object_type="literal"
        )
        
        # Set material if provided
        if material:
            self.add_triple(
                subject=specimen_id,
                predicate="dyn:hasMaterial",
                object=f"dyn:{material}",
                object_type="uri"
            )
        
        return self.current_specimen_uri
    
    def start_test_session(self, test_id: str, test_type: str, specimen_id: str) -> str:
        """Start a new test data entry session"""
        self.current_test_uri = f"{self.base_uri}{test_id}"
        
        # Add basic test triples
        self.add_triple(
            subject=test_id,
            predicate="rdf:type",
            object=f"dyn:{test_type}",
            object_type="uri"
        )
        
        # Link to specimen
        self.add_triple(
            subject=test_id,
            predicate="dyn:performedOn",
            object=specimen_id if specimen_id.startswith("dyn:") else f"dyn:{specimen_id}",
            object_type="uri"
        )
        
        # Add timestamp
        self.add_triple(
            subject=test_id,
            predicate="dyn:hasDate",
            object=datetime.now().strftime("%Y-%m-%d"),
            object_type="literal",
            datatype="xsd:date"
        )
        
        return self.current_test_uri
    
    # =============================================================================
    # DATA ENTRY METHODS (CALLED FROM GUI)
    # =============================================================================
    
    def add_measurement(self, measurement: MeasurementEntry, target_id: str):
        """Add a measurement from GUI (e.g., specimen dimension)"""
        
        # Create measurement individual
        measurement_uri = f"{target_id}_{measurement.name}"
        
        # Add measurement type
        self.add_triple(
            subject=measurement_uri,
            predicate="rdf:type",
            object="dyn:Geometry",
            object_type="uri"
        )
        
        # Add measurement name
        self.add_triple(
            subject=measurement_uri,
            predicate="rdfs:label",
            object=measurement.name,
            object_type="literal"
        )
        
        # Add value
        self.add_triple(
            subject=measurement_uri,
            predicate="dyn:hasValue",
            object=measurement.value,
            object_type="literal",
            datatype="xsd:float"
        )
        
        # Add unit
        self.add_triple(
            subject=measurement_uri,
            predicate="dyn:hasUnits",
            object=f"dyn:{measurement.unit}",
            object_type="uri"
        )
        
        # Link to target through property path
        if len(measurement.property_path) == 1:
            # Direct property
            self.add_triple(
                subject=target_id,
                predicate=f"dyn:{measurement.property_path[0]}",
                object=measurement_uri,
                object_type="uri"
            )
        else:
            # Through intermediate (e.g., hasDimension)
            self.add_triple(
                subject=target_id,
                predicate=f"dyn:{measurement.property_path[0]}",
                object=measurement_uri,
                object_type="uri"
            )
    
    def add_selector_choice(self, target_id: str, property_name: str, selected_value: str):
        """Add a selection from ComboBox (e.g., material, specimen role)"""
        self.add_triple(
            subject=target_id,
            predicate=f"dyn:{property_name}",
            object=f"dyn:{selected_value}",
            object_type="uri"
        )
    
    def add_test_condition(self, test_id: str, condition_name: str, condition_value: Any):
        """Add testing condition"""
        # Create testing conditions individual if not exists
        conditions_uri = f"{test_id}_conditions"
        
        # Link test to conditions
        self.add_triple(
            subject=test_id,
            predicate="dyn:hasTestingConditions",
            object=conditions_uri,
            object_type="uri"
        )
        
        # Add condition type
        self.add_triple(
            subject=conditions_uri,
            predicate="rdf:type",
            object="dyn:TestingConditions",
            object_type="uri"
        )
        
        # Add specific condition
        if isinstance(condition_value, (int, float)):
            datatype = "xsd:float" if isinstance(condition_value, float) else "xsd:int"
            self.add_triple(
                subject=conditions_uri,
                predicate=f"dyn:{condition_name}",
                object=condition_value,
                object_type="literal",
                datatype=datatype
            )
        else:
            self.add_triple(
                subject=conditions_uri,
                predicate=f"dyn:{condition_name}",
                object=str(condition_value),
                object_type="literal"
            )
    
    def add_test_result(self, test_id: str, result_name: str, values: List[float], unit: str):
        """Add test result series data"""
        # Create series data individual
        series_uri = f"{test_id}_{result_name.replace(' ', '')}"
        
        # Link test to series data
        self.add_triple(
            subject=test_id,
            predicate="dyn:hasSeriesData",
            object=series_uri,
            object_type="uri"
        )
        
        # Add series data type
        self.add_triple(
            subject=series_uri,
            predicate="rdf:type",
            object="dyn:SHPBSeriesData",
            object_type="uri"
        )
        
        # Add series name
        self.add_triple(
            subject=series_uri,
            predicate="rdfs:label",
            object=result_name,
            object_type="literal"
        )
        
        # Add unit
        self.add_triple(
            subject=series_uri,
            predicate="dyn:hasUnits",
            object=f"dyn:{unit}",
            object_type="uri"
        )
        
        # For now, store max value (could be enhanced to store arrays)
        if values:
            max_value = max(values)
            self.add_triple(
                subject=series_uri,
                predicate="dyn:hasValue",
                object=max_value,
                object_type="literal",
                datatype="xsd:float"
            )
    
    # =============================================================================
    # TRIPLE MANAGEMENT
    # =============================================================================
    
    def add_triple(
        self,
        subject: str,
        predicate: str,
        object: Any,
        object_type: str,
        datatype: Optional[str] = None
    ):
        """Add a triple to the temporal store"""
        
        # Store in temporal list
        triple = TemporalTriple(
            subject=subject,
            predicate=predicate,
            object=object,
            object_type=object_type,
            timestamp=datetime.now()
        )
        self.temporal_triples.append(triple)
        
        # Also add to graph immediately for queries
        subject_uri = self._ensure_uri(subject)
        predicate_uri = self._ensure_uri(predicate)
        
        if object_type == "uri":
            object_node = self._ensure_uri(object)
        elif object_type == "literal":
            if datatype:
                object_node = Literal(object, datatype=getattr(XSD, datatype.split(':')[1]))
            else:
                object_node = Literal(object)
        else:
            object_node = Literal(object)
        
        self.graph.add((
            URIRef(subject_uri),
            URIRef(predicate_uri),
            object_node
        ))
    
    def remove_triple(self, subject: str, predicate: str, object: Any = None):
        """Remove a triple (for corrections during data entry)"""
        subject_uri = URIRef(self._ensure_uri(subject))
        predicate_uri = URIRef(self._ensure_uri(predicate))
        
        if object:
            if isinstance(object, str) and object.startswith("dyn:"):
                object_node = URIRef(self._ensure_uri(object))
            else:
                object_node = Literal(object)
            self.graph.remove((subject_uri, predicate_uri, object_node))
        else:
            # Remove all matching subject/predicate
            self.graph.remove((subject_uri, predicate_uri, None))
        
        # Also remove from temporal triples
        self.temporal_triples = [
            t for t in self.temporal_triples 
            if not (t.subject == subject and t.predicate == predicate and 
                   (object is None or t.object == object))
        ]
    
    def get_current_state(self) -> Dict[str, Any]:
        """Get current state for GUI display"""
        return {
            'specimen_uri': self.current_specimen_uri,
            'test_uri': self.current_test_uri,
            'triple_count': len(self.temporal_triples),
            'last_modified': max([t.timestamp for t in self.temporal_triples]) if self.temporal_triples else None,
            'has_measurements': any(t.object_type == "measurement" for t in self.temporal_triples),
            'validated': all(t.validated for t in self.temporal_triples)
        }
    
    # =============================================================================
    # VALIDATION AND FINALIZATION
    # =============================================================================
    
    def validate_completeness(self) -> Dict[str, Any]:
        """
        Validate that all required fields are present.
        This happens before SHACL validation.
        """
        validation_result = {
            'is_complete': True,
            'missing_fields': [],
            'warnings': [],
            'errors': []
        }
        
        # Check for specimen basics
        if self.current_specimen_uri:
            specimen_id = self._extract_name(self.current_specimen_uri)
            has_material = any(
                t.subject == specimen_id and t.predicate == "dyn:hasMaterial" 
                for t in self.temporal_triples
            )
            if not has_material:
                validation_result['missing_fields'].append('specimen_material')
                validation_result['is_complete'] = False
        
        # Check for test basics
        if self.current_test_uri:
            test_id = self._extract_name(self.current_test_uri)
            has_conditions = any(
                t.subject == test_id and t.predicate == "dyn:hasTestingConditions"
                for t in self.temporal_triples
            )
            if not has_conditions:
                validation_result['missing_fields'].append('testing_conditions')
                validation_result['is_complete'] = False
        
        return validation_result
    
    def finalize_experiment(self, output_path: Path, validate: bool = True) -> bool:
        """
        Finalize the experimental data and save to TTL file.
        
        Returns True if successful, False if validation fails.
        """
        if validate:
            completeness = self.validate_completeness()
            if not completeness['is_complete']:
                print(f"Validation failed: {completeness['missing_fields']}")
                return False
        
        # Mark all triples as validated
        for triple in self.temporal_triples:
            triple.validated = True
        
        # Save to file
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(self.graph.serialize(format='turtle'))
            
            print(f"Experimental data saved to {output_path}")
            return True
            
        except Exception as e:
            print(f"Error saving experimental data: {e}")
            return False
    
    def export_csv_data(self, output_dir: Path) -> Dict[str, Path]:
        """Export measurement data to CSV files"""
        output_dir.mkdir(parents=True, exist_ok=True)
        csv_files = {}
        
        # This would extract numerical data and save as CSV
        # Implementation depends on how you want to structure the CSV output
        
        return csv_files
    
    # =============================================================================
    # PRIVATE HELPER METHODS
    # =============================================================================
    
    def _ensure_uri(self, uri_or_name: str) -> str:
        """Ensure input is a full URI"""
        if uri_or_name.startswith("http"):
            return uri_or_name
        elif uri_or_name.startswith("dyn:"):
            return uri_or_name.replace("dyn:", str(self.dyn))
        elif uri_or_name.startswith("rdf:"):
            return uri_or_name.replace("rdf:", str(RDF))
        elif uri_or_name.startswith("rdfs:"):
            return uri_or_name.replace("rdfs:", str(RDFS))
        elif uri_or_name.startswith("xsd:"):
            return uri_or_name.replace("xsd:", str(XSD))
        else:
            return f"{self.base_uri}{uri_or_name}"
    
    def _extract_name(self, uri: str) -> str:
        """Extract local name from URI"""
        if '#' in uri:
            return uri.split('#')[-1]
        elif '/' in uri:
            return uri.split('/')[-1]
        return uri


# =============================================================================
# CONVENIENCE FUNCTIONS FOR GUI INTEGRATION
# =============================================================================

def create_specimen_builder(specimen_id: str, material: str) -> ExperimentalRDFBuilder:
    """Create a builder for specimen data entry"""
    builder = ExperimentalRDFBuilder()
    builder.start_specimen_session(specimen_id, material)
    return builder


def create_test_builder(test_id: str, test_type: str, specimen_id: str) -> ExperimentalRDFBuilder:
    """Create a builder for test data entry"""
    builder = ExperimentalRDFBuilder()
    builder.start_test_session(test_id, test_type, specimen_id)
    return builder


def continue_experiment(ttl_file: Path) -> ExperimentalRDFBuilder:
    """Continue working on an existing experimental TTL file"""
    builder = ExperimentalRDFBuilder()
    builder.graph.parse(str(ttl_file), format="turtle")
    
    # Rebuild temporal triples from graph (simplified)
    # This would need a more sophisticated implementation
    
    return builder