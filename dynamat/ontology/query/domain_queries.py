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
        SELECT ?class ?subclass WHERE {{
            ?subclass rdfs:subClassOf* <{root_class}> .
            ?subclass rdfs:subClassOf ?class .
        }}
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
        
    def get_instances_of_class(self, class_uri: str, include_subclasses: bool = True) -> List[Dict[str, Any]]:
        """
        Get all instances of a specific class.
        
        Args:
            class_uri: URI of the class
            include_subclasses: Whether to include instances of subclasses
            
        Returns:
            List of dictionaries with instance information (uri, name/label)
        """
        if include_subclasses:
            query = """
            SELECT DISTINCT ?individual ?label ?name WHERE {{
                ?individual rdf:type ?instanceClass .
                ?instanceClass rdfs:subClassOf* <{class_uri}> .

                OPTIONAL {{ ?individual rdfs:label ?label }}
                OPTIONAL {{ ?individual dyn:hasName ?name }}
                OPTIONAL {{ ?individual dyn:hasMaterialName ?name }}
                OPTIONAL {{ ?individual dyn:hasSpecimenID ?name }}
            }}
            ORDER BY ?label ?name ?individual
            """.format(class_uri=class_uri)
        else:
            query = """
            SELECT DISTINCT ?individual ?label ?name WHERE {{
                ?individual rdf:type <{class_uri}> .

                OPTIONAL {{ ?individual rdfs:label ?label }}
                OPTIONAL {{ ?individual dyn:hasName ?name }}
                OPTIONAL {{ ?individual dyn:hasMaterialName ?name }}
                OPTIONAL {{ ?individual dyn:hasSpecimenID ?name }}
            }}
            ORDER BY ?label ?name ?individual
            """.format(class_uri=class_uri)
        
        try:
            results = self.sparql.execute_query(query)
            
            instances = []
            for result in results:
                # Extract display name (prefer name > label > extracted from URI)
                display_name = None
                if result.get('name'):
                    display_name = str(result['name'])
                elif result.get('label'):
                    display_name = str(result['label'])
                else:
                    # Extract from URI
                    uri = str(result['individual'])
                    display_name = uri.split('#')[-1].split('/')[-1].replace('_', ' ')
                
                instances.append({
                    'uri': str(result['individual']),
                    'name': display_name,
                    'label': str(result.get('label', ''))
                })
            
            logger.debug(f"Found {len(instances)} instances of {class_uri}")
            return instances
            
        except Exception as e:
            logger.error(f"Failed to get instances of class {class_uri}: {e}")
            return []
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
        SELECT ?material ?materialCode ?alloyDesignation ?description WHERE {{
            ?material rdf:type/rdfs:subClassOf* dyn:Material .
            ?material dyn:hasMaterialName ?name .
            FILTER(LCASE(STR(?name)) = LCASE("{material_name}"))

            OPTIONAL {{ ?material dyn:hasMaterialCode ?materialCode }}
            OPTIONAL {{ ?material dyn:hasAlloyDesignation ?alloyDesignation }}
            OPTIONAL {{ ?material rdfs:comment ?description }}
        }}
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
            filters.append(f'?specimen dyn:hasSpecimenBatchID "{batch_id}"')
        
        filter_clause = " . ".join(filters) if filters else ""
        
        query = f"""
        SELECT ?specimen ?specimenId ?material ?shape ?batchId ?date WHERE {{
            ?specimen rdf:type/rdfs:subClassOf* dyn:Specimen .

            OPTIONAL {{ ?specimen dyn:hasSpecimenID ?specimenId }}
            OPTIONAL {{ ?specimen dyn:hasMaterial ?material }}
            OPTIONAL {{ ?specimen dyn:hasShape ?shape }}
            OPTIONAL {{ ?specimen dyn:hasSpecimenBatchID ?batchId }}
            OPTIONAL {{ ?specimen dyn:hasManufacturedDate ?date }}

            {filter_clause}
        }}
        ORDER BY DESC(?date)
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
            filters.append(f'?test dyn:hasSpecimen/dyn:hasSpecimenID "{specimen_id}"')
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
        SELECT ?measurementType ?value ?unit ?description WHERE {{
            <{specimen_uri}> ?measurementType ?measurement .
            ?measurement rdf:type dyn:Measurement .

            ?measurement dyn:hasValue ?value .
            OPTIONAL {{ ?measurement dyn:hasUnit ?unit }}
            OPTIONAL {{ ?measurement rdfs:comment ?description }}
        }}
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
        SELECT ?resultType ?value ?unit ?description WHERE {{
            <{test_uri}> dyn:hasResult ?result .
            ?result rdf:type ?resultType .

            ?result dyn:hasValue ?value .
            OPTIONAL {{ ?result dyn:hasUnit ?unit }}
            OPTIONAL {{ ?result rdfs:comment ?description }}
        }}
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
            OPTIONAL {{ ?specimen dyn:hasManufacturedDate ?date }}
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
        SELECT ?specimen ?material ?structure ?processing ?test ?testType ?testDate WHERE {{
            ?specimen dyn:hasSpecimenID "{specimen_id}" .

            OPTIONAL {{ ?specimen dyn:hasMaterial ?material }}
            OPTIONAL {{ ?specimen dyn:hasStructure ?structure }}
            OPTIONAL {{ ?specimen dyn:hasProcessing ?processing }}

            OPTIONAL {{
                ?test dyn:hasSpecimen ?specimen .
                ?test rdf:type ?testType .
                ?test dyn:hasDate ?testDate
            }}
        }}
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

    # ============================================================================
    # SERIES TYPE QUERIES (CSV-to-RDF Metadata)
    # ============================================================================

    def get_series_type_metadata(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all SeriesType individuals with CSV mapping metadata.

        Returns:
            Dict mapping column names to metadata dict with keys:
                - series_type: URI of the SeriesType individual
                - quantity_kind: QUDT quantity kind URI
                - unit: QUDT unit URI
                - legend_template: Legend template string
                - class_uri: Default series class (RawSignal/ProcessedData)
                - requires_gauge: Whether strain gauge data is required

        Note:
            Derivation chains are handled by module-specific mappings (e.g., SHPB_DERIVATION_MAP)
            not stored in the ontology, since derivations depend on analysis method.
        """
        query = """
        SELECT ?seriesType ?columnName ?quantityKind ?unit ?legendTemplate
               ?seriesClass ?requiresGauge
        WHERE {
            ?seriesType rdf:type dyn:SeriesType .

            OPTIONAL { ?seriesType dyn:hasDefaultColumnName ?columnName }
            OPTIONAL { ?seriesType qudt:hasQuantityKind ?quantityKind }
            OPTIONAL { ?seriesType dyn:hasUnit ?unit }
            OPTIONAL { ?seriesType dyn:hasLegendTemplate ?legendTemplate }
            OPTIONAL { ?seriesType dyn:hasDefaultSeriesClass ?seriesClass }
            OPTIONAL { ?seriesType dyn:requiresStrainGauge ?requiresGauge }
        }
        ORDER BY ?seriesType
        """

        results = self.sparql.execute_query(query)

        # Process results into a dict keyed by column name
        metadata = {}
        for result in results:
            column_name = result.get('columnName')
            if not column_name:
                continue

            column_name = str(column_name)

            # Skip if already processed (handles duplicate rows)
            if column_name in metadata:
                continue

            series_type_uri = str(result.get('seriesType', ''))
            class_uri = str(result.get('seriesClass', ''))

            # Convert requires_gauge to boolean
            requires_gauge = result.get('requiresGauge')
            if isinstance(requires_gauge, str):
                requires_gauge = requires_gauge.lower() == 'true'
            elif requires_gauge is None:
                requires_gauge = False

            metadata[column_name] = {
                'series_type': series_type_uri,
                'quantity_kind': str(result.get('quantityKind', '')),
                'unit': str(result.get('unit', '')),
                'legend_template': str(result.get('legendTemplate', '')),
                'class_uri': class_uri if class_uri else 'https://dynamat.utep.edu/ontology#DataSeries',
                'requires_gauge': requires_gauge,
            }

        logger.debug(f"Retrieved metadata for {len(metadata)} series types from ontology")
        return metadata

    def get_series_metadata_for_shpb(self) -> Dict[str, Dict[str, Any]]:
        """
        Get SERIES_METADATA dict for SHPB, expanding templates to method-specific entries.

        This method transforms ontology SeriesType metadata into the format expected
        by the SHPB io module. It expands series with {analysis_method} placeholder
        in their legend template into multiple entries (e.g., stress -> stress_1w, stress_3w).

        Note:
            Derivation chains (derived_from) are NOT included here. They are handled
            by SHPB_DERIVATION_MAP in the SHPB module since derivations depend on the
            specific analysis method (1-wave vs 3-wave).

        Returns:
            Dict compatible with SERIES_METADATA format:
                - series_type: dyn:SeriesType URI
                - quantity_kind: QUDT quantity kind
                - unit: QUDT unit
                - legend_name: Formatted legend string
                - analysis_method: '1-wave' or '3-wave' (for processed data)
                - class_uri: dyn:RawSignal or dyn:ProcessedData
                - requires_gauge: bool (for raw signals)
        """
        base_metadata = self.get_series_type_metadata()
        expanded = {}

        # Analysis methods with their suffixes
        analysis_methods = [
            ('1-wave', '_1w'),
            ('3-wave', '_3w')
        ]

        for column_name, meta in base_metadata.items():
            legend_template = meta.get('legend_template', '')

            if '{analysis_method}' in legend_template:
                # Expand to method-specific entries (e.g., stress -> stress_1w, stress_3w)
                for method_name, suffix in analysis_methods:
                    new_column = f"{column_name}{suffix}"

                    expanded[new_column] = {
                        'series_type': meta['series_type'],
                        'quantity_kind': meta['quantity_kind'],
                        'unit': meta['unit'],
                        'legend_name': legend_template.format(analysis_method=method_name),
                        'analysis_method': method_name,
                        'class_uri': meta['class_uri'],
                    }
            else:
                # No expansion needed - raw signals or non-method-specific series
                entry = {
                    'series_type': meta['series_type'],
                    'quantity_kind': meta['quantity_kind'],
                    'unit': meta['unit'],
                    'legend_name': legend_template,
                    'class_uri': meta['class_uri'],
                }

                # Add requires_gauge for raw signals
                if meta.get('requires_gauge'):
                    entry['requires_gauge'] = True

                expanded[column_name] = entry

        logger.debug(f"Expanded series metadata to {len(expanded)} entries for SHPB")
        return expanded

    def get_windowed_series_metadata(self) -> Dict[str, Dict[str, Any]]:
        """
        Get metadata for windowed series types from ontology.

        Windowed series are intermediate processed signals between raw oscilloscope
        data and final stress-strain curves (e.g., incident_windowed, reflected_windowed).

        Returns:
            Dict mapping windowed column names to metadata:
                - series_type: dyn:SeriesType URI
                - quantity_kind: QUDT quantity kind
                - unit: QUDT unit
                - legend_name: Display legend
                - raw_source: Source raw column name (e.g., 'incident' for 'incident_windowed')
                - requires_gauge: Whether strain gauge is required
        """
        query = """
        SELECT ?seriesType ?columnName ?quantityKind ?unit ?legendTemplate
               ?seriesClass ?requiresGauge
        WHERE {
            ?seriesType rdf:type dyn:SeriesType .
            ?seriesType dyn:hasDefaultColumnName ?columnName .
            FILTER(CONTAINS(STR(?columnName), "_windowed"))

            OPTIONAL { ?seriesType qudt:hasQuantityKind ?quantityKind }
            OPTIONAL { ?seriesType dyn:hasUnit ?unit }
            OPTIONAL { ?seriesType dyn:hasLegendTemplate ?legendTemplate }
            OPTIONAL { ?seriesType dyn:hasDefaultSeriesClass ?seriesClass }
            OPTIONAL { ?seriesType dyn:requiresStrainGauge ?requiresGauge }
        }
        """

        results = self.sparql.execute_query(query)

        # Map windowed column names to raw source names
        raw_source_mapping = {
            'time_windowed': 'time',
            'incident_windowed': 'incident',
            'transmitted_windowed': 'transmitted',
            'reflected_windowed': 'incident',  # Reflected pulse is measured on incident bar
        }

        metadata = {}
        for result in results:
            column_name = str(result.get('columnName', ''))
            if not column_name or column_name in metadata:
                continue

            # Convert requires_gauge to boolean
            requires_gauge = result.get('requiresGauge')
            if isinstance(requires_gauge, str):
                requires_gauge = requires_gauge.lower() == 'true'
            elif requires_gauge is None:
                requires_gauge = False

            metadata[column_name] = {
                'series_type': str(result.get('seriesType', '')),
                'quantity_kind': str(result.get('quantityKind', '')),
                'unit': str(result.get('unit', '')),
                'legend_name': str(result.get('legendTemplate', '')),
                'raw_source': raw_source_mapping.get(column_name, ''),
                'requires_gauge': requires_gauge,
            }

        logger.debug(f"Retrieved metadata for {len(metadata)} windowed series types")
        return metadata

    # ============================================================================
    # INDIVIDUAL PROPERTY QUERIES (for GUI Property Display)
    # ============================================================================

    def get_individual_properties_with_labels(
        self,
        individual_uri: str,
        property_uris: List[str],
        follow_links: Optional[Dict[str, List[str]]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get property values WITH labels and units for a specific individual.

        This method is optimized for GUI display, returning rich metadata about
        each property including display labels and unit symbols.

        Args:
            individual_uri: URI of the individual to query
            property_uris: List of property URIs to retrieve
            follow_links: Optional mapping of object properties to nested properties
                          e.g., {'dyn:hasMaterial': ['dyn:hasWaveSpeed', 'dyn:hasElasticModulus']}
                          When specified, follows the object property link and retrieves
                          nested properties from the linked individual.

        Returns:
            Dictionary mapping property_uri -> {
                'value': Any,
                'label': str,  # from gui:hasDisplayName, rdfs:label, or auto-generated
                'unit': Optional[str],
                'unit_symbol': Optional[str]
            }

        Example:
            >>> props = domain_queries.get_individual_properties_with_labels(
            ...     "dyn:IncidentBar_C350",
            ...     ["dyn:hasWaveSpeed", "dyn:hasElasticModulus"],
            ...     follow_links={"dyn:hasMaterial": ["dyn:hasWaveSpeed", "dyn:hasElasticModulus"]}
            ... )
            >>> props["dyn:hasWaveSpeed"]
            {'value': 4953.3, 'label': 'Wave Speed', 'unit': 'unit:M-PER-SEC', 'unit_symbol': 'm/s'}
        """
        result = {}

        # Normalize individual URI
        if individual_uri.startswith('dyn:'):
            individual_uri = f"https://dynamat.utep.edu/ontology#{individual_uri[4:]}"

        # Determine which properties to query directly vs via links
        direct_properties = list(property_uris)
        linked_properties = {}

        if follow_links:
            for link_prop, nested_props in follow_links.items():
                # Remove nested properties from direct query
                for np in nested_props:
                    if np in direct_properties:
                        direct_properties.remove(np)
                linked_properties[link_prop] = nested_props

        # Query direct properties
        if direct_properties:
            direct_result = self._query_properties_with_labels(individual_uri, direct_properties)
            result.update(direct_result)

        # Query linked properties (follow object property links)
        if linked_properties:
            for link_prop, nested_props in linked_properties.items():
                # First, get the linked individual URI
                link_uri = self._normalize_property_uri(link_prop)
                linked_individual = self._get_linked_individual(individual_uri, link_uri)

                if linked_individual:
                    # Query properties from the linked individual
                    nested_result = self._query_properties_with_labels(linked_individual, nested_props)
                    result.update(nested_result)
                else:
                    logger.debug(f"No linked individual found for {link_prop} on {individual_uri}")

        return result

    def _query_properties_with_labels(
        self,
        individual_uri: str,
        property_uris: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Query properties with labels and units from ontology.

        Args:
            individual_uri: URI of the individual
            property_uris: List of property URIs to retrieve

        Returns:
            Dictionary mapping property_uri -> {value, label, unit, unit_symbol}
        """
        result = {}

        for prop_uri in property_uris:
            # Normalize property URI
            normalized_prop = self._normalize_property_uri(prop_uri)

            # Query for value, label, unit, and also the value's label if it's an object property
            # This handles both datatype properties (literal values) and object properties (URI values)
            query = f"""
            SELECT ?value ?displayName ?label ?unit ?unitSymbol ?valueLabel ?valuePlotLabel WHERE {{
                <{individual_uri}> <{normalized_prop}> ?value .

                OPTIONAL {{ <{normalized_prop}> gui:hasDisplayName ?displayName }}
                OPTIONAL {{ <{normalized_prop}> rdfs:label ?label }}
                OPTIONAL {{ <{normalized_prop}> dyn:hasUnit ?unit }}
                OPTIONAL {{ ?unit qudt:symbol ?unitSymbol }}

                # For object properties, get the label of the linked individual
                OPTIONAL {{ ?value rdfs:label ?valueLabel }}
                OPTIONAL {{ ?value dyn:hasPlottingLabel ?valuePlotLabel }}
            }}
            LIMIT 1
            """

            try:
                results = self.sparql.execute_query(query)

                if results:
                    row = results[0]
                    raw_value = row.get('value')
                    value = raw_value

                    # Check if value is a URI (object property) and resolve its label
                    value_is_uri = False
                    if value is not None:
                        value_str = str(value)
                        if value_str.startswith('http') or '#' in value_str:
                            value_is_uri = True
                            # Use rdfs:label first (descriptive), then plotting label, then formatted URI
                            value_label = row.get('valueLabel')
                            value_plot_label = row.get('valuePlotLabel')
                            if value_label:
                                value = str(value_label)
                            elif value_plot_label:
                                value = str(value_plot_label)
                            else:
                                # Fallback to formatted URI fragment
                                value = self._generate_label_from_uri(value_str)
                        else:
                            # Not a URI, try numeric conversion
                            try:
                                value = float(value)
                            except (ValueError, TypeError):
                                value = str(value)

                    # Determine display label (priority: displayName > label > auto-generated)
                    display_label = (
                        row.get('displayName') or
                        row.get('label') or
                        self._generate_label_from_uri(prop_uri)
                    )

                    # Get unit info (only for datatype properties)
                    unit = row.get('unit') if not value_is_uri else None
                    unit_symbol = row.get('unitSymbol') if not value_is_uri else None

                    # If no symbol from query, extract from unit URI
                    if unit and not unit_symbol:
                        unit_symbol = self._extract_unit_symbol_from_uri(str(unit))

                    result[prop_uri] = {
                        'value': value,
                        'label': str(display_label) if display_label else self._generate_label_from_uri(prop_uri),
                        'unit': str(unit) if unit else None,
                        'unit_symbol': str(unit_symbol) if unit_symbol else None
                    }

            except Exception as e:
                logger.warning(f"Failed to query property {prop_uri}: {e}")

        return result

    def _get_linked_individual(self, individual_uri: str, link_property_uri: str) -> Optional[str]:
        """
        Get the URI of a linked individual via an object property.

        Args:
            individual_uri: URI of the source individual
            link_property_uri: URI of the object property to follow

        Returns:
            URI of the linked individual, or None if not found
        """
        query = f"""
        SELECT ?linked WHERE {{
            <{individual_uri}> <{link_property_uri}> ?linked .
        }}
        LIMIT 1
        """

        try:
            results = self.sparql.execute_query(query)
            if results:
                return str(results[0]['linked'])
        except Exception as e:
            logger.warning(f"Failed to get linked individual: {e}")

        return None

    def _normalize_property_uri(self, prop_uri: str) -> str:
        """
        Normalize a property URI to full form.

        Args:
            prop_uri: Property URI (may be prefixed like 'dyn:hasWaveSpeed')

        Returns:
            Full URI string
        """
        if prop_uri.startswith('dyn:'):
            return f"https://dynamat.utep.edu/ontology#{prop_uri[4:]}"
        elif prop_uri.startswith('http'):
            return prop_uri
        elif '#' in prop_uri:
            return prop_uri
        else:
            # Assume dyn namespace
            return f"https://dynamat.utep.edu/ontology#{prop_uri}"

    def _generate_label_from_uri(self, uri: str) -> str:
        """
        Generate a human-readable label from a property URI.

        Args:
            uri: Property URI (e.g., 'dyn:hasWaveSpeed')

        Returns:
            Label string (e.g., 'Wave Speed')
        """
        # Extract local name
        if ':' in uri:
            local_name = uri.split(':')[-1]
        elif '/' in uri:
            local_name = uri.split('/')[-1]
        elif '#' in uri:
            local_name = uri.split('#')[-1]
        else:
            local_name = uri

        # Remove 'has' prefix if present
        if local_name.startswith('has'):
            local_name = local_name[3:]

        # Insert spaces before capital letters
        result = []
        for i, char in enumerate(local_name):
            if i > 0 and char.isupper():
                result.append(' ')
            result.append(char)

        return ''.join(result).strip()

    def _extract_unit_symbol_from_uri(self, unit_uri: str) -> str:
        """
        Extract a unit symbol from a unit URI.

        Args:
            unit_uri: Full unit URI (e.g., 'http://qudt.org/vocab/unit/M-PER-SEC')

        Returns:
            Symbol string (e.g., 'm/s')
        """
        # Common unit mappings
        unit_symbols = {
            'M-PER-SEC': 'm/s',
            'GigaPA': 'GPa',
            'MegaPA': 'MPa',
            'KiloGM-PER-M3': 'kg/m³',
            'GM-PER-CentiM3': 'g/cm³',
            'MilliM': 'mm',
            'M': 'm',
            'SEC': 's',
            'PER-SEC': '1/s',
            'GM': 'g',
            'KiloGM': 'kg',
            'NUM': '',  # Dimensionless
            'OHM': 'Ω',
            'V': 'V',
        }

        # Extract local name from URI
        if '/' in unit_uri:
            local_name = unit_uri.split('/')[-1]
        elif '#' in unit_uri:
            local_name = unit_uri.split('#')[-1]
        elif ':' in unit_uri:
            local_name = unit_uri.split(':')[-1]
        else:
            local_name = unit_uri

        return unit_symbols.get(local_name, local_name)