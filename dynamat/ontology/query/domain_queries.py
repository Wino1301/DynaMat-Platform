"""
DynaMat Platform - Domain-Specific Queries
High-level query methods that hide SPARQL complexity
Extracted from manager.py and consolidated with query_builder.py functionality
"""

import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, date

from .sparql_executor import SPARQLExecutor
from ..core.namespace_manager import NamespaceManager

logger = logging.getLogger(__name__)


class DomainQueries:
    """
    High-level domain-specific query methods.
    
    Provides intuitive interfaces for common DynaMat operations
    without requiring SPARQL knowledge from users.
    
    Consolidates functionality from both manager.py exploration methods
    and query_builder.py domain queries.
    """
    
    def __init__(self, sparql_executor: SPARQLExecutor, namespace_manager: NamespaceManager):
        """
        Initialize domain queries.
        
        Args:
            sparql_executor: SPARQL executor for running queries
            namespace_manager: Namespace manager for query prefixes
        """
        self.sparql = sparql_executor
        self.ns = namespace_manager
        
        logger.info("Domain queries initialized")
    
    # ============================================================================
    # ONTOLOGY EXPLORATION - General ontology navigation
    # ============================================================================
    
    def get_all_classes(self, include_individuals: bool = False) -> List[str]:
        """
        Get all classes defined in the ontology.
        
        Args:
            include_individuals: Whether to include individual instances
            
        Returns:
            List of class URIs
        """
        query = """
        SELECT DISTINCT ?class WHERE {
            ?class rdf:type owl:Class .
        }
        ORDER BY ?class
        """
        
        results = self.sparql.execute_query(query)
        classes = [result['class'] for result in results]
        
        if include_individuals:
            individuals = self.get_all_individuals()
            classes.extend(individuals)
        
        return sorted(set(classes))
    
    def get_all_individuals(self) -> List[str]:
        """Get all individual instances in the ontology."""
        query = """
        SELECT DISTINCT ?individual WHERE {
            ?individual rdf:type ?class .
            ?class rdf:type owl:Class .
        }
        ORDER BY ?individual
        """
        
        results = self.sparql.execute_query(query)
        return [result['individual'] for result in results]
    
    def get_class_hierarchy(self, root_class: Optional[str] = None) -> Dict[str, List[str]]:
        """
        Get the class hierarchy starting from a root class.
        
        Args:
            root_class: Root class URI, defaults to dyn:Entity
            
        Returns:
            Dictionary mapping class URIs to their subclasses
        """
        if root_class is None:
            root_class = str(self.ns.DYN.Entity)
        
        query = """
        SELECT ?class ?subclass WHERE {
            ?subclass rdfs:subClassOf* <{root_class}> .
            ?subclass rdfs:subClassOf ?class .
        }
        """.format(root_class=root_class)
        
        results = self.sparql.execute_query(query)
        
        hierarchy = {}
        for result in results:
            parent = result['class']
            child = result['subclass']
            
            if parent not in hierarchy:
                hierarchy[parent] = []
            hierarchy[parent].append(child)
        
        return hierarchy
    
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
        
        results = self.sparql.execute_query(query)
        return results
    
    def get_material_by_name(self, material_name: str) -> Optional[Dict[str, Any]]:
        """Get material information by name."""
        query = """
        SELECT ?material ?materialCode ?alloyDesignation ?description WHERE {
            ?material rdf:type/rdfs:subClassOf* dyn:Material .
            ?material dyn:hasMaterialName ?name .
            FILTER(LCASE(STR(?name)) = LCASE("{material_name}"))
            
            OPTIONAL { ?material dyn:hasMaterialCode ?materialCode }
            OPTIONAL { ?material dyn:hasAlloyDesignation ?alloyDesignation }
            OPTIONAL { ?material rdfs:comment ?description }
        }
        """.format(material_name=material_name.lower())
        
        results = self.sparql.execute_query(query)
        return results[0] if results else None
    
    # ============================================================================
    # SPECIMEN QUERIES
    # ============================================================================
    
    def find_specimens(self, material_name: Optional[str] = None,
                      shape: Optional[str] = None,
                      batch_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Find specimens based on criteria.
        
        Args:
            material_name: Filter by material name
            shape: Filter by specimen shape  
            batch_id: Filter by batch ID
            
        Returns:
            List of matching specimens
        """
        filters = []
        if material_name:
            filters.append(f'?specimen dyn:hasMaterial/dyn:hasMaterialName "{material_name}"')
        if shape:
            filters.append(f'?specimen dyn:hasShape "{shape}"')
        if batch_id:
            filters.append(f'?specimen dyn:hasBatchId "{batch_id}"')
        
        filter_clause = " . ".join(filters) if filters else ""
        
        query = f"""
        SELECT ?specimen ?specimenId ?material ?shape ?batchId ?date WHERE {{
            ?specimen rdf:type/rdfs:subClassOf* dyn:Specimen .
            
            OPTIONAL {{ ?specimen dyn:hasSpecimenId ?specimenId }}
            OPTIONAL {{ ?specimen dyn:hasMaterial ?material }}  
            OPTIONAL {{ ?specimen dyn:hasShape ?shape }}
            OPTIONAL {{ ?specimen dyn:hasBatchId ?batchId }}
            OPTIONAL {{ ?specimen dyn:hasDate ?date }}
            
            {filter_clause}
        }}
        ORDER BY ?date DESC
        """
        
        return self.sparql.execute_query(query)
    
    # ============================================================================  
    # TEST QUERIES
    # ============================================================================
    
    def find_tests(self, specimen_id: Optional[str] = None,
                  material_name: Optional[str] = None,
                  test_type: Optional[str] = None,
                  date_from: Optional[Union[str, date]] = None,
                  date_to: Optional[Union[str, date]] = None) -> List[Dict[str, Any]]:
        """
        Find mechanical tests based on criteria.
        
        Args:
            specimen_id: Filter by specimen ID
            material_name: Filter by material name
            test_type: Filter by test type
            date_from: Filter by date range start
            date_to: Filter by date range end
            
        Returns:
            List of matching tests
        """
        filters = []
        
        if specimen_id:
            filters.append(f'?test dyn:hasSpecimen/dyn:hasSpecimenId "{specimen_id}"')
        if material_name:
            filters.append(f'?test dyn:hasSpecimen/dyn:hasMaterial/dyn:hasMaterialName "{material_name}"')
        if test_type:
            filters.append(f'?test rdf:type dyn:{test_type}')
        if date_from:
            date_str = date_from.isoformat() if hasattr(date_from, 'isoformat') else str(date_from)
            filters.append(f'?test dyn:hasDate ?date . FILTER(?date >= "{date_str}"^^xsd:date)')
        if date_to:
            date_str = date_to.isoformat() if hasattr(date_to, 'isoformat') else str(date_to)
            filters.append(f'?test dyn:hasDate ?date . FILTER(?date <= "{date_str}"^^xsd:date)')
        
        filter_clause = " . ".join(filters) if filters else ""
        
        query = f"""
        SELECT ?test ?testType ?specimen ?material ?date ?operator WHERE {{
            ?test rdf:type ?testType .
            ?testType rdfs:subClassOf* dyn:MechanicalTest .
            
            OPTIONAL {{ ?test dyn:hasSpecimen ?specimen }}
            OPTIONAL {{ ?test dyn:hasSpecimen/dyn:hasMaterial ?material }}
            OPTIONAL {{ ?test dyn:hasDate ?date }}
            OPTIONAL {{ ?test dyn:hasOperator ?operator }}
            
            {filter_clause}
        }}
        ORDER BY ?date DESC
        """
        
        return self.sparql.execute_query(query)
    
    # ============================================================================
    # MEASUREMENT QUERIES  
    # ============================================================================
    
    def get_specimen_measurements(self, specimen_uri: str) -> Dict[str, Any]:
        """Get all measurements for a specimen."""
        query = """
        SELECT ?measurementType ?value ?unit ?description WHERE {
            <{specimen_uri}> ?measurementType ?measurement .
            ?measurement rdf:type dyn:Measurement .
            
            ?measurement dyn:hasValue ?value .
            OPTIONAL { ?measurement dyn:hasUnit ?unit }
            OPTIONAL { ?measurement rdfs:comment ?description }
        }
        """.format(specimen_uri=specimen_uri)
        
        results = self.sparql.execute_query(query)
        
        measurements = {}
        for result in results:
            measurements[result['measurementType']] = {
                'value': result['value'],
                'unit': result.get('unit'),
                'description': result.get('description')
            }
        
        return measurements
    
    def get_test_results(self, test_uri: str) -> Dict[str, Any]:
        """Get all results/measurements for a test."""
        query = """
        SELECT ?resultType ?value ?unit ?description WHERE {
            <{test_uri}> dyn:hasResult ?result .
            ?result rdf:type ?resultType .
            
            ?result dyn:hasValue ?value .
            OPTIONAL { ?result dyn:hasUnit ?unit }
            OPTIONAL { ?result rdfs:comment ?description }
        }
        """.format(test_uri=test_uri)
        
        results = self.sparql.execute_query(query)
        
        test_results = {}
        for result in results:
            test_results[result['resultType']] = {
                'value': result['value'],
                'unit': result.get('unit'), 
                'description': result.get('description')
            }
        
        return test_results
    
    # ============================================================================
    # COMPARISON AND ANALYSIS QUERIES
    # ============================================================================
    
    def compare_materials(self, materials: List[str], 
                         measurement_name: str) -> Dict[str, List[Dict[str, Any]]]:
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
        SELECT ?materialName ?specimen ?value ?unit ?date WHERE {{
            ?specimen dyn:hasMaterial/dyn:hasMaterialName ?materialName .
            FILTER({material_filter})
            
            ?specimen dyn:{measurement_name} ?measurement .
            ?measurement dyn:hasValue ?value .
            OPTIONAL {{ ?measurement dyn:hasUnit ?unit }}
            OPTIONAL {{ ?specimen dyn:hasDate ?date }}
        }}
        ORDER BY ?materialName ?date
        """
        
        results = self.sparql.execute_query(query)
        
        comparison = {}
        for result in results:
            material = result['materialName']
            if material not in comparison:
                comparison[material] = []
            
            comparison[material].append({
                'specimen': result['specimen'],
                'value': result['value'],
                'unit': result.get('unit'),
                'date': result.get('date')
            })
        
        return comparison
    
    def get_specimen_history(self, specimen_id: str) -> Dict[str, Any]:
        """
        Get complete history of a specimen.
        
        Args:
            specimen_id: ID of the specimen
            
        Returns:
            Dictionary with specimen history including tests and measurements
        """
        query = """
        SELECT ?specimen ?material ?structure ?processing ?test ?testType ?testDate WHERE {
            ?specimen dyn:hasSpecimenId "{specimen_id}" .
            
            OPTIONAL { ?specimen dyn:hasMaterial ?material }
            OPTIONAL { ?specimen dyn:hasStructure ?structure }
            OPTIONAL { ?specimen dyn:hasProcessing ?processing }
            
            OPTIONAL { 
                ?test dyn:hasSpecimen ?specimen .
                ?test rdf:type ?testType .
                ?test dyn:hasDate ?testDate
            }
        }
        ORDER BY ?testDate
        """.format(specimen_id=specimen_id)
        
        results = self.sparql.execute_query(query)
        
        if not results:
            return {}
        
        # Organize results
        history = {
            'specimen_uri': results[0]['specimen'],
            'material': results[0].get('material'),
            'structure': results[0].get('structure'),
            'processing_steps': [r['processing'] for r in results if r.get('processing')],
            'tests_performed': []
        }
        
        # Add unique tests
        seen_tests = set()
        for result in results:
            if result.get('test') and result['test'] not in seen_tests:
                history['tests_performed'].append({
                    'test_uri': result['test'],
                    'test_type': result.get('testType'),
                    'date': result.get('testDate')
                })
                seen_tests.add(result['test'])
        
        return history