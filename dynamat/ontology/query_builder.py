"""
DynaMat Platform - Query Builder
High-level query utilities for common DynaMat operations
Clean implementation using new architecture
"""

import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, date
from dataclasses import dataclass

from .query.sparql_executor import SPARQLExecutor
from .core.namespace_manager import NamespaceManager

logger = logging.getLogger(__name__)


@dataclass
class TestSearchCriteria:
    """Criteria for searching mechanical tests"""
    specimen_id: Optional[str] = None
    material_name: Optional[str] = None
    test_type: Optional[str] = None
    date_from: Optional[Union[str, date]] = None
    date_to: Optional[Union[str, date]] = None
    strain_rate_min: Optional[float] = None
    strain_rate_max: Optional[float] = None
    temperature_min: Optional[float] = None
    temperature_max: Optional[float] = None
    operator: Optional[str] = None


@dataclass
class SpecimenSearchCriteria:
    """Criteria for searching specimens"""
    material_name: Optional[str] = None
    structure_type: Optional[str] = None
    shape: Optional[str] = None
    batch_id: Optional[str] = None
    creation_date_from: Optional[Union[str, date]] = None
    creation_date_to: Optional[Union[str, date]] = None
    diameter_min: Optional[float] = None
    diameter_max: Optional[float] = None
    length_min: Optional[float] = None
    length_max: Optional[float] = None


class DynaMatQueryBuilder:
    """
    High-level query builder for common DynaMat operations.
    
    Provides domain-specific methods that hide SPARQL complexity
    and offer intuitive interfaces for materials testing data.
    """
    
    def __init__(self, sparql_executor: SPARQLExecutor, namespace_manager: NamespaceManager):
        """
        Initialize with core components.
        
        Args:
            sparql_executor: SPARQL executor for running queries
            namespace_manager: Namespace manager for URI handling
        """
        self.sparql = sparql_executor
        self.ns_manager = namespace_manager
        
        logger.info("DynaMatQueryBuilder initialized")
    
    # ============================================================================
    # MATERIAL QUERIES
    # ============================================================================
    
    def get_available_materials(self) -> List[Dict[str, Any]]:
        """Get all available materials with basic properties."""
        query = """
        SELECT ?material ?materialName ?materialCode ?alloyDesignation ?description WHERE {
            { ?material rdf:type dyn:Material }
            UNION 
            { ?material rdf:type ?materialType .
              ?materialType rdfs:subClassOf* dyn:Material }
            
            OPTIONAL { ?material dyn:hasMaterialName ?materialName }
            OPTIONAL { ?material dyn:hasMaterialCode ?materialCode }
            OPTIONAL { ?material dyn:hasAlloyDesignation ?alloyDesignation }
            OPTIONAL { ?material rdfs:comment ?description }
        }
        ORDER BY ?materialName ?material
        """
        
        return self.sparql.execute_query(query)
    
    def find_material_by_property(self, property_name: str, property_value: Any) -> List[Dict[str, Any]]:
        """
        Find materials by a specific property value.
        
        Args:
            property_name: Name of the property (e.g., 'hasDensity')
            property_value: Value to search for
            
        Returns:
            List of matching materials
        """
        query = f"""
        SELECT ?material ?materialName ?value WHERE {{
            ?material rdf:type/rdfs:subClassOf* dyn:Material .
            ?material dyn:{property_name} ?value .
            ?material dyn:hasMaterialName ?materialName .
            
            FILTER(?value = "{property_value}")
        }}
        ORDER BY ?materialName
        """
        
        return self.sparql.execute_query(query)
    
    # ============================================================================
    # SPECIMEN QUERIES
    # ============================================================================
    
    def find_specimens(self, criteria: Optional[SpecimenSearchCriteria] = None, **kwargs) -> List[Dict[str, Any]]:
        """
        Find specimens based on search criteria.
        
        Args:
            criteria: SpecimenSearchCriteria object with search parameters
            **kwargs: Individual search parameters (alternative to criteria)
            
        Returns:
            List of matching specimens
        """
        # Use criteria object or individual kwargs
        if criteria:
            search_params = criteria
        else:
            search_params = SpecimenSearchCriteria(**kwargs)
        
        # Build filter conditions
        filters = []
        
        if search_params.material_name:
            filters.append(f'?specimen dyn:hasMaterial/dyn:hasMaterialName "{search_params.material_name}"')
        
        if search_params.structure_type:
            filters.append(f'?specimen dyn:hasStructure/dyn:hasStructureType "{search_params.structure_type}"')
        
        if search_params.shape:
            filters.append(f'?specimen dyn:hasShape "{search_params.shape}"')
        
        if search_params.batch_id:
            filters.append(f'?specimen dyn:hasSpecimenBatchID "{search_params.batch_id}"')

        if search_params.creation_date_from:
            date_str = search_params.creation_date_from.isoformat() if hasattr(search_params.creation_date_from, 'isoformat') else str(search_params.creation_date_from)
            filters.append(f'?specimen dyn:hasManufacturedDate ?date . FILTER(?date >= "{date_str}"^^xsd:date)')

        if search_params.creation_date_to:
            date_str = search_params.creation_date_to.isoformat() if hasattr(search_params.creation_date_to, 'isoformat') else str(search_params.creation_date_to)
            filters.append(f'?specimen dyn:hasManufacturedDate ?date . FILTER(?date <= "{date_str}"^^xsd:date)')

        # Dimensional filters (measurements stored as direct xsd:double values)
        if search_params.diameter_min or search_params.diameter_max:
            filters.append('?specimen dyn:hasOriginalDiameter ?diameter')
            if search_params.diameter_min:
                filters.append(f'FILTER(?diameter >= {search_params.diameter_min})')
            if search_params.diameter_max:
                filters.append(f'FILTER(?diameter <= {search_params.diameter_max})')

        if search_params.length_min or search_params.length_max:
            filters.append('?specimen dyn:hasOriginalLength ?length')
            if search_params.length_min:
                filters.append(f'FILTER(?length >= {search_params.length_min})')
            if search_params.length_max:
                filters.append(f'FILTER(?length <= {search_params.length_max})')
        
        filter_clause = " . ".join(filters) if filters else ""
        
        query = f"""
        SELECT ?specimen ?specimenId ?material ?materialName ?shape ?batchId ?date WHERE {{
            ?specimen rdf:type/rdfs:subClassOf* dyn:Specimen .

            OPTIONAL {{ ?specimen dyn:hasSpecimenID ?specimenId }}
            OPTIONAL {{ ?specimen dyn:hasMaterial ?material }}
            OPTIONAL {{ ?specimen dyn:hasMaterial/dyn:hasMaterialName ?materialName }}
            OPTIONAL {{ ?specimen dyn:hasShape ?shape }}
            OPTIONAL {{ ?specimen dyn:hasSpecimenBatchID ?batchId }}
            OPTIONAL {{ ?specimen dyn:hasManufacturedDate ?date }}

            {filter_clause}
        }}
        ORDER BY DESC(?date) ?specimenId
        """
        
        return self.sparql.execute_query(query)
    
    def get_specimen_details(self, specimen_uri: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific specimen.

        Args:
            specimen_uri: URI of the specimen

        Returns:
            Dictionary with specimen details
        """
        query = """
        SELECT ?property ?value ?unit WHERE {{
            <{specimen_uri}> ?property ?value .

            # Get units for measurements
            OPTIONAL {{
                <{specimen_uri}> ?property ?measurement .
                ?measurement dyn:hasValue ?value .
                ?measurement dyn:hasUnit ?unit .
            }}
        }}
        """.format(specimen_uri=specimen_uri)
        
        results = self.sparql.execute_query(query)
        
        # Organize results into a structured dictionary
        details = {"uri": specimen_uri}
        measurements = {}
        
        for result in results:
            prop = result['property']
            value = result['value']
            unit = result.get('unit')
            
            # Extract property name
            prop_name = prop.split('#')[-1] if '#' in prop else prop.split('/')[-1]
            
            if unit:
                # This is a measurement
                measurements[prop_name] = {"value": value, "unit": unit}
            else:
                # Simple property
                details[prop_name] = value
        
        if measurements:
            details['measurements'] = measurements
        
        return details
    
    # ============================================================================
    # TEST QUERIES
    # ============================================================================
    
    def find_tests(self, criteria: Optional[TestSearchCriteria] = None, **kwargs) -> List[Dict[str, Any]]:
        """
        Find mechanical tests based on search criteria.
        
        Args:
            criteria: TestSearchCriteria object with search parameters
            **kwargs: Individual search parameters (alternative to criteria)
            
        Returns:
            List of matching tests
        """
        # Use criteria object or individual kwargs
        if criteria:
            search_params = criteria
        else:
            search_params = TestSearchCriteria(**kwargs)
        
        # Build filter conditions
        filters = []
        
        if search_params.specimen_id:
            filters.append(f'?test dyn:hasSpecimen/dyn:hasSpecimenID "{search_params.specimen_id}"')
        
        if search_params.material_name:
            filters.append(f'?test dyn:hasSpecimen/dyn:hasMaterial/dyn:hasMaterialName "{search_params.material_name}"')
        
        if search_params.test_type:
            filters.append(f'?test rdf:type dyn:{search_params.test_type}')
        
        if search_params.date_from:
            date_str = search_params.date_from.isoformat() if hasattr(search_params.date_from, 'isoformat') else str(search_params.date_from)
            filters.append(f'?test dyn:hasDate ?date . FILTER(?date >= "{date_str}"^^xsd:date)')
        
        if search_params.date_to:
            date_str = search_params.date_to.isoformat() if hasattr(search_params.date_to, 'isoformat') else str(search_params.date_to)
            filters.append(f'?test dyn:hasDate ?date . FILTER(?date <= "{date_str}"^^xsd:date)')
        
        if search_params.operator:
            filters.append(f'?test dyn:hasOperator "{search_params.operator}"')
        
        # Strain rate filters
        if search_params.strain_rate_min or search_params.strain_rate_max:
            filters.append('?test dyn:hasStrainRate/dyn:hasValue ?strainRate')
            if search_params.strain_rate_min:
                filters.append(f'FILTER(?strainRate >= {search_params.strain_rate_min})')
            if search_params.strain_rate_max:
                filters.append(f'FILTER(?strainRate <= {search_params.strain_rate_max})')
        
        # Temperature filters
        if search_params.temperature_min or search_params.temperature_max:
            filters.append('?test dyn:hasTemperature/dyn:hasValue ?temperature')
            if search_params.temperature_min:
                filters.append(f'FILTER(?temperature >= {search_params.temperature_min})')
            if search_params.temperature_max:
                filters.append(f'FILTER(?temperature <= {search_params.temperature_max})')
        
        filter_clause = " . ".join(filters) if filters else ""
        
        query = f"""
        SELECT ?test ?testType ?specimen ?specimenId ?material ?materialName ?date ?operator WHERE {{
            ?test rdf:type ?testType .
            ?testType rdfs:subClassOf* dyn:MechanicalTest .

            OPTIONAL {{ ?test dyn:hasSpecimen ?specimen }}
            OPTIONAL {{ ?test dyn:hasSpecimen/dyn:hasSpecimenID ?specimenId }}
            OPTIONAL {{ ?test dyn:hasSpecimen/dyn:hasMaterial ?material }}
            OPTIONAL {{ ?test dyn:hasSpecimen/dyn:hasMaterial/dyn:hasMaterialName ?materialName }}
            OPTIONAL {{ ?test dyn:hasDate ?date }}
            OPTIONAL {{ ?test dyn:hasOperator ?operator }}

            {filter_clause}
        }}
        ORDER BY DESC(?date) ?test
        """
        
        return self.sparql.execute_query(query)
    
    def get_test_results(self, test_uri: str) -> Dict[str, Any]:
        """
        Get detailed results for a specific test.

        Args:
            test_uri: URI of the test

        Returns:
            Dictionary with test results and measurements
        """
        query = """
        SELECT ?resultType ?measurement ?value ?unit ?description WHERE {{
            <{test_uri}> dyn:hasResult ?result .
            ?result rdf:type ?resultType .

            OPTIONAL {{
                ?result ?measurement ?measurementValue .
                ?measurementValue dyn:hasValue ?value .
                ?measurementValue dyn:hasUnit ?unit .
                OPTIONAL {{ ?measurementValue rdfs:comment ?description }}
            }}
        }}
        """.format(test_uri=test_uri)
        
        results = self.sparql.execute_query(query)
        
        # Organize results
        test_results = {"uri": test_uri, "results": {}}
        
        for result in results:
            result_type = result['resultType']
            measurement = result.get('measurement')
            value = result.get('value')
            unit = result.get('unit')
            description = result.get('description')
            
            result_type_name = result_type.split('#')[-1] if '#' in result_type else result_type.split('/')[-1]
            
            if measurement and value:
                measurement_name = measurement.split('#')[-1] if '#' in measurement else measurement.split('/')[-1]
                test_results["results"][measurement_name] = {
                    "value": value,
                    "unit": unit,
                    "description": description,
                    "result_type": result_type_name
                }
        
        return test_results
    
    # ============================================================================
    # ANALYSIS AND COMPARISON QUERIES
    # ============================================================================
    
    def compare_materials(self, materials: List[str], measurement_name: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Compare materials across a specific measurement.
        
        Args:
            materials: List of material names to compare
            measurement_name: Name of measurement to compare
            
        Returns:
            Dictionary mapping material names to their measurement data
        """
        material_filter = " || ".join([f'?materialName = "{mat}"' for mat in materials])
        
        query = f"""
        SELECT ?materialName ?specimen ?specimenId ?value ?unit ?date ?test WHERE {{
            ?specimen dyn:hasMaterial/dyn:hasMaterialName ?materialName .
            FILTER({material_filter})
            
            # Get measurements from specimens
            {{
                ?specimen dyn:{measurement_name} ?measurement .
                ?measurement dyn:hasValue ?value .
                OPTIONAL {{ ?measurement dyn:hasUnit ?unit }}
                OPTIONAL {{ ?specimen dyn:hasDate ?date }}
                OPTIONAL {{ ?specimen dyn:hasSpecimenId ?specimenId }}
                BIND("specimen" AS ?source)
            }}
            UNION
            {{
                # Get measurements from tests
                ?test dyn:hasSpecimen ?specimen .
                ?test dyn:hasResult/dyn:{measurement_name} ?measurement .
                ?measurement dyn:hasValue ?value .
                OPTIONAL {{ ?measurement dyn:hasUnit ?unit }}
                OPTIONAL {{ ?test dyn:hasDate ?date }}
                OPTIONAL {{ ?specimen dyn:hasSpecimenId ?specimenId }}
                BIND("test" AS ?source)
            }}
        }}
        ORDER BY ?materialName ?date
        """
        
        results = self.sparql.execute_query(query)
        
        # Organize by material
        comparison = {}
        for result in results:
            material = result['materialName']
            if material not in comparison:
                comparison[material] = []
            
            comparison[material].append({
                'specimen': result.get('specimen'),
                'specimen_id': result.get('specimenId'),
                'value': result['value'],
                'unit': result.get('unit'),
                'date': result.get('date'),
                'test': result.get('test'),
                'source': result.get('source', 'unknown')
            })
        
        return comparison
    
    def get_data_completeness(self, entity_uri: str) -> Dict[str, Any]:
        """
        Analyze data completeness for an entity.

        Args:
            entity_uri: URI of the entity to analyze

        Returns:
            Dictionary with completeness analysis
        """
        query = """
        SELECT ?property ?hasValue WHERE {{
            {{
                # Properties this entity has
                <{entity_uri}> ?property ?value .
                BIND(true AS ?hasValue)
            }}
            UNION
            {{
                # Expected properties (from class definition)
                <{entity_uri}> rdf:type ?type .
                ?property rdfs:domain ?type .
                BIND(false AS ?hasValue)

                # Only include if not already present
                FILTER NOT EXISTS {{
                    <{entity_uri}> ?property ?anyValue .
                }}
            }}
        }}
        """.format(entity_uri=entity_uri)
        
        results = self.sparql.execute_query(query)
        
        # Analyze completeness
        present_properties = []
        missing_properties = []
        
        for result in results:
            prop = result['property']
            has_value = result['hasValue']
            
            prop_name = prop.split('#')[-1] if '#' in prop else prop.split('/')[-1]
            
            if has_value:
                present_properties.append(prop_name)
            else:
                missing_properties.append(prop_name)
        
        total_expected = len(present_properties) + len(missing_properties)
        completeness_ratio = len(present_properties) / total_expected if total_expected > 0 else 1.0
        
        return {
            "entity_uri": entity_uri,
            "present_properties": present_properties,
            "missing_properties": missing_properties,
            "completeness_ratio": completeness_ratio,
            "completeness_percentage": completeness_ratio * 100
        }
    
    def find_invalid_tests(self) -> List[Dict[str, Any]]:
        """
        Find tests that may have data quality issues.
        
        Returns:
            List of potentially invalid tests with issues
        """
        query = """
        SELECT ?test ?issue ?description WHERE {
            {
                # Tests without specimens
                ?test rdf:type/rdfs:subClassOf* dyn:MechanicalTest .
                FILTER NOT EXISTS { ?test dyn:hasSpecimen ?specimen }
                BIND("missing_specimen" AS ?issue)
                BIND("Test has no associated specimen" AS ?description)
            }
            UNION
            {
                # Tests without dates
                ?test rdf:type/rdfs:subClassOf* dyn:MechanicalTest .
                FILTER NOT EXISTS { ?test dyn:hasDate ?date }
                BIND("missing_date" AS ?issue)
                BIND("Test has no date" AS ?description)
            }
            UNION
            {
                # Tests with invalid strain rates (negative or extremely high)
                ?test dyn:hasStrainRate/dyn:hasValue ?strainRate .
                FILTER(?strainRate < 0 || ?strainRate > 10000)
                BIND("invalid_strain_rate" AS ?issue)
                BIND(CONCAT("Invalid strain rate: ", STR(?strainRate)) AS ?description)
            }
        }
        ORDER BY ?test ?issue
        """
        
        return self.sparql.execute_query(query)
    
    # ============================================================================
    # UTILITY METHODS
    # ============================================================================
    
    def count_entities_by_type(self, entity_type: str) -> int:
        """
        Count entities of a specific type.
        
        Args:
            entity_type: Type of entity to count (e.g., 'Specimen', 'MechanicalTest')
            
        Returns:
            Number of entities
        """
        query = f"""
        SELECT (COUNT(?entity) AS ?count) WHERE {{
            ?entity rdf:type/rdfs:subClassOf* dyn:{entity_type} .
        }}
        """
        
        results = self.sparql.execute_query(query)
        return int(results[0]['count']) if results else 0
    
    def get_property_statistics(self, property_name: str) -> Dict[str, Any]:
        """
        Get statistics for a numeric property across all entities.
        
        Args:
            property_name: Name of the property to analyze
            
        Returns:
            Dictionary with statistical information
        """
        query = f"""
        SELECT ?value WHERE {{
            ?entity dyn:{property_name}/dyn:hasValue ?value .
            FILTER(isNumeric(?value))
        }}
        """
        
        results = self.sparql.execute_query(query)
        values = [float(r['value']) for r in results if r['value']]
        
        if not values:
            return {"property": property_name, "count": 0}
        
        return {
            "property": property_name,
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "average": sum(values) / len(values),
            "total": sum(values)
        }