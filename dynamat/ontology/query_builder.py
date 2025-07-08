"""
DynaMat Query Builder

Domain-specific query methods that hide SPARQL complexity from users.
Provides intuitive methods for common materials testing queries.
"""

from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass
from datetime import datetime
import rdflib
from rdflib import Graph, Namespace
from rdflib.namespace import RDF, RDFS, OWL

from ..config import config


@dataclass
class QueryFilter:
    """Represents a filter condition for queries"""
    property: str
    operator: str  # =, >, <, >=, <=, !=, contains
    value: Any
    unit: Optional[str] = None


@dataclass
class QueryResult:
    """Structured query result"""
    uri: str
    name: str
    properties: Dict[str, Any]
    measurements: Dict[str, Any]


class DomainQueryBuilder:
    """
    Domain-specific query builder for DynaMat.
    
    Provides intuitive methods like:
    - find_tests(material="Al6061", strain_rate_min=1000)
    - get_specimen_history(specimen_uri)
    - compare_materials(["Al6061", "SS316"])
    """
    
    def __init__(self, graph: Graph):
        """Initialize with an RDF graph"""
        self.graph = graph
        self.dyn = Namespace(config.ONTOLOGY_URI)
        
        # Common SPARQL prefixes
        self.prefixes = """
        PREFIX dyn: <{}>
        PREFIX rdf: <{}>
        PREFIX rdfs: <{}>
        PREFIX owl: <{}>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        """.format(config.ONTOLOGY_URI, RDF, RDFS, OWL)
    
    # =============================================================================
    # TEST FINDING METHODS
    # =============================================================================
    
    def find_tests(
        self,
        material: Optional[str] = None,
        test_type: Optional[str] = None,
        strain_rate_min: Optional[float] = None,
        strain_rate_max: Optional[float] = None,
        temperature: Optional[float] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        user: Optional[str] = None
    ) -> List[QueryResult]:
        """
        Find tests matching the specified criteria.
        
        Example usage:
        - find_tests(material="Al6061", strain_rate_min=1000)
        - find_tests(test_type="SHPBTest", temperature=25)
        """
        
        # Build WHERE clauses based on parameters
        where_clauses = [
            "?test a/rdfs:subClassOf* dyn:MechanicalTest .",
            "?test dyn:performedOn ?specimen ."
        ]
        
        if material:
            where_clauses.extend([
                "?specimen dyn:hasMaterial ?material .",
                f"?material rdfs:label \"{material}\" ."
            ])
        
        if test_type:
            where_clauses.append(f"?test a dyn:{test_type} .")
        
        if strain_rate_min or strain_rate_max:
            where_clauses.extend([
                "?test dyn:hasSeriesData ?strainRateData .",
                "?strainRateData rdfs:label \"Engineering Strain Rate\" .",
                "?strainRateData dyn:hasValue ?strainRate ."
            ])
            
            if strain_rate_min:
                where_clauses.append(f"FILTER(?strainRate >= {strain_rate_min})")
            if strain_rate_max:
                where_clauses.append(f"FILTER(?strainRate <= {strain_rate_max})")
        
        if temperature:
            where_clauses.extend([
                "?test dyn:hasTestingConditions ?conditions .",
                "?conditions dyn:TestingTemperature ?tempValue .",
                "?tempValue dyn:hasValue ?temp .",
                f"FILTER(?temp = {temperature})"
            ])
        
        if user:
            where_clauses.extend([
                "?test dyn:hasUser ?userObj .",
                f"?userObj dyn:hasName \"{user}\" ."
            ])
        
        if date_from or date_to:
            where_clauses.append("?test dyn:hasDate ?date .")
            if date_from:
                where_clauses.append(f"FILTER(?date >= \"{date_from.strftime('%Y-%m-%d')}\"^^xsd:date)")
            if date_to:
                where_clauses.append(f"FILTER(?date <= \"{date_to.strftime('%Y-%m-%d')}\"^^xsd:date)")
        
        # Build complete query
        query = f"""
        {self.prefixes}
        SELECT DISTINCT ?test ?testName WHERE {{
            {' '.join(where_clauses)}
            OPTIONAL {{ ?test rdfs:label ?testName }}
        }}
        ORDER BY ?test
        """
        
        results = []
        for row in self.graph.query(query):
            test_uri = str(row.test)
            test_name = str(row.testName) if row.testName else self._extract_name(test_uri)
            
            # Get additional info for each test
            test_info = self._get_test_details(test_uri)
            
            results.append(QueryResult(
                uri=test_uri,
                name=test_name,
                properties=test_info['properties'],
                measurements=test_info['measurements']
            ))
        
        return results
    
    def find_specimens(
        self,
        material: Optional[str] = None,
        structure: Optional[str] = None,
        processing: Optional[str] = None,
        role: Optional[str] = None,
        batch: Optional[str] = None
    ) -> List[QueryResult]:
        """Find specimens matching criteria"""
        
        where_clauses = ["?specimen a dyn:Specimen ."]
        
        if material:
            where_clauses.extend([
                "?specimen dyn:hasMaterial ?material .",
                f"?material rdfs:label \"{material}\" ."
            ])
        
        if structure:
            where_clauses.extend([
                "?specimen dyn:hasStructure ?structure .",
                f"?structure rdfs:label \"{structure}\" ."
            ])
        
        if processing:
            where_clauses.extend([
                "?specimen dyn:hasProcessingHistory ?process .",
                f"?process rdfs:label \"{processing}\" ."
            ])
        
        if role:
            where_clauses.extend([
                "?specimen dyn:hasSpecimenRole ?role .",
                f"?role rdfs:label \"{role}\" ."
            ])
        
        if batch:
            where_clauses.extend([
                "?specimen dyn:fromBatch ?batch .",
                f"?batch rdfs:label \"{batch}\" ."
            ])
        
        query = f"""
        {self.prefixes}
        SELECT DISTINCT ?specimen ?specimenName WHERE {{
            {' '.join(where_clauses)}
            OPTIONAL {{ ?specimen rdfs:label ?specimenName }}
        }}
        ORDER BY ?specimen
        """
        
        results = []
        for row in self.graph.query(query):
            specimen_uri = str(row.specimen)
            specimen_name = str(row.specimenName) if row.specimenName else self._extract_name(specimen_uri)
            
            specimen_info = self._get_specimen_details(specimen_uri)
            
            results.append(QueryResult(
                uri=specimen_uri,
                name=specimen_name,
                properties=specimen_info['properties'],
                measurements=specimen_info['measurements']
            ))
        
        return results
    
    # =============================================================================
    # MEASUREMENT AND COMPARISON METHODS
    # =============================================================================
    
    def get_measurement_range(
        self,
        measurement_name: str,
        material: Optional[str] = None,
        test_type: Optional[str] = None
    ) -> Dict[str, float]:
        """Get min/max/avg for a measurement across tests"""
        
        where_clauses = [
            "?test a/rdfs:subClassOf* dyn:MechanicalTest .",
            "?test dyn:hasSeriesData ?measurement .",
            f"?measurement rdfs:label \"{measurement_name}\" .",
            "?measurement dyn:hasValue ?value ."
        ]
        
        if material:
            where_clauses.extend([
                "?test dyn:performedOn ?specimen .",
                "?specimen dyn:hasMaterial ?material .",
                f"?material rdfs:label \"{material}\" ."
            ])
        
        if test_type:
            where_clauses.append(f"?test a dyn:{test_type} .")
        
        query = f"""
        {self.prefixes}
        SELECT (MIN(?value) AS ?min) (MAX(?value) AS ?max) (AVG(?value) AS ?avg) (COUNT(?value) AS ?count) WHERE {{
            {' '.join(where_clauses)}
        }}
        """
        
        for row in self.graph.query(query):
            return {
                'min': float(row.min) if row.min else None,
                'max': float(row.max) if row.max else None,
                'avg': float(row.avg) if row.avg else None,
                'count': int(row.count) if row.count else 0
            }
        
        return {'min': None, 'max': None, 'avg': None, 'count': 0}
    
    def compare_materials(
        self,
        materials: List[str],
        measurement_name: str,
        test_type: Optional[str] = None
    ) -> Dict[str, Dict[str, float]]:
        """Compare a measurement across different materials"""
        
        results = {}
        for material in materials:
            results[material] = self.get_measurement_range(
                measurement_name=measurement_name,
                material=material,
                test_type=test_type
            )
        
        return results
    
    def get_strain_rate_vs_strength(
        self,
        material: Optional[str] = None,
        test_type: str = "SHPBTest"
    ) -> List[Tuple[float, float]]:
        """Get strain rate vs yield strength data points"""
        
        where_clauses = [
            f"?test a dyn:{test_type} .",
            "?test dyn:hasSeriesData ?strainRate .",
            "?strainRate rdfs:label \"Engineering Strain Rate\" .",
            "?strainRate dyn:hasValue ?strainRateValue .",
            "?test dyn:hasSeriesData ?strength .",
            "?strength rdfs:label \"Engineering Stress\" .",
            "?strength dyn:hasValue ?strengthValue ."
        ]
        
        if material:
            where_clauses.extend([
                "?test dyn:performedOn ?specimen .",
                "?specimen dyn:hasMaterial ?materialObj .",
                f"?materialObj rdfs:label \"{material}\" ."
            ])
        
        query = f"""
        {self.prefixes}
        SELECT ?strainRateValue ?strengthValue WHERE {{
            {' '.join(where_clauses)}
        }}
        ORDER BY ?strainRateValue
        """
        
        data_points = []
        for row in self.graph.query(query):
            strain_rate = float(row.strainRateValue)
            strength = float(row.strengthValue)
            data_points.append((strain_rate, strength))
        
        return data_points
    
    # =============================================================================
    # HISTORY AND PROVENANCE METHODS
    # =============================================================================
    
    def get_specimen_history(self, specimen_uri: str) -> Dict[str, Any]:
        """Get complete history of a specimen including all tests"""
        
        specimen_uri = self._ensure_uri(specimen_uri)
        
        # Get basic specimen info
        history = {
            'specimen_id': self._extract_name(specimen_uri),
            'material': None,
            'structure': None,
            'processing_steps': [],
            'tests_performed': [],
            'measurements': {}
        }
        
        # Get material
        material_query = f"""
        {self.prefixes}
        SELECT ?material ?materialName WHERE {{
            <{specimen_uri}> dyn:hasMaterial ?material .
            ?material rdfs:label ?materialName .
        }}
        """
        for row in self.graph.query(material_query):
            history['material'] = str(row.materialName)
            break
        
        # Get structure
        structure_query = f"""
        {self.prefixes}
        SELECT ?structure ?structureName WHERE {{
            <{specimen_uri}> dyn:hasStructure ?structure .
            ?structure rdfs:label ?structureName .
        }}
        """
        for row in self.graph.query(structure_query):
            history['structure'] = str(row.structureName)
            break
        
        # Get processing steps
        processing_query = f"""
        {self.prefixes}
        SELECT ?process ?processName WHERE {{
            <{specimen_uri}> dyn:hasProcessingHistory ?process .
            ?process rdfs:label ?processName .
        }}
        ORDER BY ?process
        """
        for row in self.graph.query(processing_query):
            history['processing_steps'].append(str(row.processName))
        
        # Get all tests on this specimen
        tests_query = f"""
        {self.prefixes}
        SELECT ?test ?testType ?date WHERE {{
            ?test dyn:performedOn <{specimen_uri}> .
            ?test a ?testType .
            OPTIONAL {{ ?test dyn:hasDate ?date }}
        }}
        ORDER BY ?date
        """
        for row in self.graph.query(tests_query):
            test_name = self._extract_name(str(row.test))
            test_type = self._extract_name(str(row.testType))
            test_date = str(row.date) if row.date else None
            
            history['tests_performed'].append({
                'test_id': test_name,
                'test_type': test_type,
                'date': test_date
            })
        
        return history
    
    def get_test_lineage(self, test_uri: str) -> Dict[str, Any]:
        """Get the complete lineage of a test (specimen, material, equipment, etc.)"""
        
        test_uri = self._ensure_uri(test_uri)
        
        lineage = {
            'test_id': self._extract_name(test_uri),
            'specimen': None,
            'material': None,
            'equipment': [],
            'testing_conditions': {},
            'user': None,
            'laboratory': None,
            'date': None
        }
        
        # Get all related information in one query
        lineage_query = f"""
        {self.prefixes}
        SELECT ?specimen ?material ?equipment ?user ?lab ?date ?condition ?conditionValue WHERE {{
            <{test_uri}> dyn:performedOn ?specimen .
            ?specimen dyn:hasMaterial ?material .
            OPTIONAL {{ <{test_uri}> dyn:hasEquipment ?equipment }}
            OPTIONAL {{ <{test_uri}> dyn:hasUser ?user }}
            OPTIONAL {{ <{test_uri}> dyn:hasLaboratory ?lab }}
            OPTIONAL {{ <{test_uri}> dyn:hasDate ?date }}
            OPTIONAL {{ 
                <{test_uri}> dyn:hasTestingConditions ?conditions .
                ?conditions ?condition ?conditionValue .
            }}
        }}
        """
        
        for row in self.graph.query(lineage_query):
            if row.specimen:
                lineage['specimen'] = self._extract_name(str(row.specimen))
            if row.material:
                lineage['material'] = self._extract_name(str(row.material))
            if row.equipment:
                equipment_name = self._extract_name(str(row.equipment))
                if equipment_name not in lineage['equipment']:
                    lineage['equipment'].append(equipment_name)
            if row.user:
                lineage['user'] = self._extract_name(str(row.user))
            if row.lab:
                lineage['laboratory'] = self._extract_name(str(row.lab))
            if row.date:
                lineage['date'] = str(row.date)
            if row.condition and row.conditionValue:
                condition_name = self._extract_name(str(row.condition))
                lineage['testing_conditions'][condition_name] = str(row.conditionValue)
        
        return lineage
    
    # =============================================================================
    # VALIDATION AND QUALITY METHODS
    # =============================================================================
    
    def find_invalid_tests(self) -> List[Dict[str, Any]]:
        """Find tests that don't meet validity criteria"""
        
        query = f"""
        {self.prefixes}
        SELECT ?test ?criterion WHERE {{
            ?test a/rdfs:subClassOf* dyn:MechanicalTest .
            ?test dyn:SatisfiesValidationCriterion ?criterion .
            FILTER NOT EXISTS {{
                ?test dyn:SatisfiesValidationCriterion dyn:EquilibriumAchieved .
            }}
        }}
        """
        
        invalid_tests = []
        for row in self.graph.query(query):
            test_name = self._extract_name(str(row.test))
            criterion = self._extract_name(str(row.criterion))
            
            invalid_tests.append({
                'test_id': test_name,
                'missing_criterion': criterion
            })
        
        return invalid_tests
    
    def get_data_completeness(self, test_uri: str) -> Dict[str, Any]:
        """Check data completeness for a test"""
        
        test_uri = self._ensure_uri(test_uri)
        
        completeness = {
            'test_id': self._extract_name(test_uri),
            'has_specimen': False,
            'has_testing_conditions': False,
            'has_results': False,
            'has_validation': False,
            'missing_data': []
        }
        
        # Check for specimen
        specimen_query = f"""
        {self.prefixes}
        ASK {{ <{test_uri}> dyn:performedOn ?specimen }}
        """
        completeness['has_specimen'] = bool(self.graph.query(specimen_query))
        
        # Check for testing conditions
        conditions_query = f"""
        {self.prefixes}
        ASK {{ <{test_uri}> dyn:hasTestingConditions ?conditions }}
        """
        completeness['has_testing_conditions'] = bool(self.graph.query(conditions_query))
        
        # Check for results
        results_query = f"""
        {self.prefixes}
        ASK {{ <{test_uri}> dyn:hasSeriesData ?results }}
        """
        completeness['has_results'] = bool(self.graph.query(results_query))
        
        # Check for validation
        validation_query = f"""
        {self.prefixes}
        ASK {{ <{test_uri}> dyn:SatisfiesValidationCriterion ?validation }}
        """
        completeness['has_validation'] = bool(self.graph.query(validation_query))
        
        # Identify missing data
        if not completeness['has_specimen']:
            completeness['missing_data'].append('specimen')
        if not completeness['has_testing_conditions']:
            completeness['missing_data'].append('testing_conditions')
        if not completeness['has_results']:
            completeness['missing_data'].append('results')
        if not completeness['has_validation']:
            completeness['missing_data'].append('validation')
        
        return completeness
    
    # =============================================================================
    # PRIVATE HELPER METHODS
    # =============================================================================
    
    def _extract_name(self, uri: str) -> str:
        """Extract local name from URI"""
        if '#' in uri:
            return uri.split('#')[-1]
        elif '/' in uri:
            return uri.split('/')[-1]
        return uri
    
    def _ensure_uri(self, uri_or_name: str) -> str:
        """Ensure input is a full URI"""
        if uri_or_name.startswith("http"):
            return uri_or_name
        else:
            return f"{config.ONTOLOGY_URI}{uri_or_name}"
    
    def _get_test_details(self, test_uri: str) -> Dict[str, Any]:
        """Get detailed information about a test"""
        # Implementation would extract properties and measurements
        # Similar to the parser methods but focused on single test
        return {'properties': {}, 'measurements': {}}
    
    def _get_specimen_details(self, specimen_uri: str) -> Dict[str, Any]:
        """Get detailed information about a specimen"""
        # Implementation would extract properties and measurements
        # Similar to the parser methods but focused on single specimen
        return {'properties': {}, 'measurements': {}}


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_query_builder(graph: Graph) -> DomainQueryBuilder:
    """Create a query builder for a graph"""
    return DomainQueryBuilder(graph)


def quick_material_search(graph: Graph, material: str) -> Dict[str, Any]:
    """Quick search for all data related to a material"""
    builder = DomainQueryBuilder(graph)
    
    return {
        'specimens': builder.find_specimens(material=material),
        'tests': builder.find_tests(material=material),
        'strength_data': builder.get_measurement_range("Engineering Stress", material=material)
    }


def compare_test_conditions(graph: Graph, test_uris: List[str]) -> Dict[str, Dict]:
    """Compare testing conditions across multiple tests"""
    builder = DomainQueryBuilder(graph)
    
    comparisons = {}
    for test_uri in test_uris:
        test_name = builder._extract_name(test_uri)
        comparisons[test_name] = builder.get_test_lineage(test_uri)
    
    return comparisons