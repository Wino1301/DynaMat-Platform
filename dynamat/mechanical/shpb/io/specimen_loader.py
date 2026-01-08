"""
DynaMat Platform - SHPB Specimen Loader
Reusable class for loading and querying specimen data from RDF graphs
"""

import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
from decimal import Decimal

logger = logging.getLogger(__name__)


class SpecimenLoader:
    """
    High-level interface for loading and querying specimen data.

    Provides methods to:
    - Load specimen TTL files into the RDF graph
    - Query specimens with filters (material, shape, structure)
    - Retrieve detailed specimen data as dictionaries

    Example usage:
        >>> from dynamat.ontology import OntologyManager
        >>> from dynamat.mechanical.shpb.io import SpecimenLoader
        >>>
        >>> manager = OntologyManager()
        >>> loader = SpecimenLoader(manager)
        >>>
        >>> # Load all specimen files
        >>> loader.load_specimen_files()
        >>>
        >>> # Find specimens by material
        >>> specimens = loader.find_specimens(material_name="A356")
        >>>
        >>> # Get detailed data for a specific specimen
        >>> specimen_data = loader.get_specimen_data(specimens[0]['uri'])
    """

    def __init__(self, ontology_manager):
        """
        Initialize the specimen loader.

        Args:
            ontology_manager: OntologyManager instance
        """
        from dynamat.ontology import create_query_builder

        self.ontology_manager = ontology_manager
        self.query_builder = create_query_builder(ontology_manager)
        self.ns = ontology_manager.namespace_manager

        logger.info("SpecimenLoader initialized")

    def load_specimen_files(self, specimens_dir: Optional[Path] = None) -> int:
        """
        Load specimen TTL files from the specimens directory into the RDF graph.

        Args:
            specimens_dir: Path to specimens directory (defaults to config.SPECIMENS_DIR)

        Returns:
            Number of specimen files successfully loaded
        """
        from dynamat.config import config

        if specimens_dir is None:
            specimens_dir = config.SPECIMENS_DIR

        if not specimens_dir.exists():
            logger.warning(f"Specimens directory not found: {specimens_dir}")
            return 0

        files_loaded = 0

        logger.info(f"Loading specimen files from: {specimens_dir}")

        for specimen_folder in specimens_dir.iterdir():
            if specimen_folder.is_dir():
                # Each specimen has its own folder with TTL files
                for ttl_file in specimen_folder.glob("*.ttl"):
                    try:
                        self.ontology_manager.loader.graph.parse(ttl_file, format="turtle")
                        logger.debug(f"Loaded: {ttl_file.name}")
                        files_loaded += 1
                    except Exception as e:
                        logger.error(f"Error loading {ttl_file.name}: {e}")

        logger.info(f"Total specimen files loaded: {files_loaded}")
        return files_loaded

    def find_specimens(self,
                      material_name: Optional[str] = None,
                      shape: Optional[str] = None,
                      structure: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Find specimens with optional filters.

        Args:
            material_name: Filter by material name (e.g., "A356", "SS316", "dyn:A356",
                          or full URI like "https://dynamat.utep.edu/ontology#A356")
            shape: Filter by shape (e.g., "CubicShape", "CylindricalShape", "dyn:CubicShape",
                  or full URI)
            structure: Filter by structure type (e.g., "Monolithic", "Composite",
                      "dyn:Monolithic", or full URI)

        Returns:
            List of dictionaries with specimen information:
            [
                {
                    'uri': specimen URI,
                    'id': specimen ID,
                    'material_name': material name,
                    'material_uri': material URI,
                    'shape': shape URI,
                    'structure': structure URI,
                    'batch_id': batch ID,
                    'manufactured_date': date
                },
                ...
            ]
        """
        # Build the SPARQL query with filters
        filters = []

        if material_name:
            # Handle different material name formats
            if material_name.startswith('http'):
                # Full URI
                filters.append(f'?specimen dyn:hasMaterial <{material_name}>')
            elif material_name.startswith('dyn:'):
                # Prefixed URI - extract the local part
                local_part = material_name.split(':')[1]
                material_uri = str(self.ns.DYN[local_part])
                filters.append(f'?specimen dyn:hasMaterial <{material_uri}>')
            else:
                # Material name - query by name
                filters.append(f'?specimen dyn:hasMaterial/dyn:hasMaterialName "{material_name}"')

        if shape:
            # Handle different shape formats
            if shape.startswith('http'):
                filters.append(f'?specimen dyn:hasShape <{shape}>')
            elif shape.startswith('dyn:'):
                local_part = shape.split(':')[1]
                shape_uri = str(self.ns.DYN[local_part])
                filters.append(f'?specimen dyn:hasShape <{shape_uri}>')
            else:
                # Assume it's a local name like "CubicShape"
                shape_uri = str(self.ns.DYN[shape])
                filters.append(f'?specimen dyn:hasShape <{shape_uri}>')

        if structure:
            # Handle different structure formats
            if structure.startswith('http'):
                filters.append(f'?specimen dyn:hasStructure <{structure}>')
            elif structure.startswith('dyn:'):
                local_part = structure.split(':')[1]
                structure_uri = str(self.ns.DYN[local_part])
                filters.append(f'?specimen dyn:hasStructure <{structure_uri}>')
            else:
                # Assume it's a local name like "Monolithic"
                structure_uri = str(self.ns.DYN[structure])
                filters.append(f'?specimen dyn:hasStructure <{structure_uri}>')

        filter_clause = " . ".join(filters) if filters else ""

        query = f"""
        SELECT ?specimen ?specimenId ?material ?materialName ?shape ?structure ?batchId ?date WHERE {{
            ?specimen rdf:type/rdfs:subClassOf* dyn:Specimen .

            OPTIONAL {{ ?specimen dyn:hasSpecimenID ?specimenId }}
            OPTIONAL {{ ?specimen dyn:hasMaterial ?material }}
            OPTIONAL {{ ?specimen dyn:hasMaterial/dyn:hasMaterialName ?materialName }}
            OPTIONAL {{ ?specimen dyn:hasShape ?shape }}
            OPTIONAL {{ ?specimen dyn:hasStructure ?structure }}
            OPTIONAL {{ ?specimen dyn:hasSpecimenBatchID ?batchId }}
            OPTIONAL {{ ?specimen dyn:hasManufacturedDate ?date }}

            {filter_clause}
        }}
        ORDER BY DESC(?date) ?specimenId
        """

        results = self.query_builder.sparql.execute_query(query)

        # Format results into clean dictionaries
        specimens = []
        for result in results:
            specimen_dict = {
                'uri': str(result.get('specimen', '')),
                'id': str(result.get('specimenId', 'N/A')),
                'material_name': str(result.get('materialName', 'N/A')),
                'material_uri': str(result.get('material', '')),
                'shape': str(result.get('shape', '')),
                'structure': str(result.get('structure', '')),
                'batch_id': str(result.get('batchId', '')),
                'manufactured_date': str(result.get('date', ''))
            }
            specimens.append(specimen_dict)

        logger.info(f"Found {len(specimens)} specimens with filters: material={material_name}, shape={shape}, structure={structure}")
        return specimens

    def get_specimen_data(self, specimen_uri: str, print_data: bool = False) -> Dict[str, Any]:
        """
        Get detailed specimen data as a dictionary.

        Args:
            specimen_uri: URI of the specimen
            print_data: If True, prints formatted specimen data to console

        Returns:
            Dictionary with all specimen properties organized by category:
            {
                'uri': specimen URI,
                'id': specimen ID,
                'material': {...},
                'dimensions': {...},
                'manufacturing': {...},
                'metadata': {...},
                'properties': {...}  # All other properties
            }
        """
        # Query for all properties of the specimen
        query = f"""
        SELECT ?property ?value WHERE {{
            <{specimen_uri}> ?property ?value .
        }}
        """

        results = self.query_builder.sparql.execute_query(query)

        # Organize properties into categories
        specimen_data = {
            'uri': specimen_uri,
            'id': None,
            'material': {},
            'dimensions': {},
            'manufacturing': {},
            'metadata': {},
            'properties': {}
        }

        # Property categorization
        material_props = ['hasMaterial', 'hasStructure', 'hasShape']
        dimension_props = [
            'hasOriginalLength', 'hasOriginalDiameter', 'hasOriginalCrossSection',
            'hasFinalLength', 'hasFinalDiameter', 'hasFinalCrossSection'
        ]
        manufacturing_props = [
            'hasManufacturingMethod', 'hasManufacturedDate',
            'hasMoldTemperature', 'hasCastCoolingDuration'
        ]
        metadata_props = [
            'hasCreatedBy', 'hasCreatedDate', 'hasModifiedBy',
            'hasModifiedDate', 'hasAppVersion'
        ]

        for result in results:
            prop = str(result['property'])
            value = result['value']

            # Extract local name from property URI
            if '#' in prop:
                prop_local = prop.split('#')[-1]
            elif '/' in prop:
                prop_local = prop.split('/')[-1]
            else:
                prop_local = prop

            # Skip RDF type properties
            if prop_local in ['type']:
                continue

            # Store specimen ID
            if prop_local == 'hasSpecimenID':
                specimen_data['id'] = str(value)

            # Categorize properties
            if prop_local in material_props:
                specimen_data['material'][prop_local] = str(value)
            elif prop_local in dimension_props:
                specimen_data['dimensions'][prop_local] = value
            elif prop_local in manufacturing_props:
                specimen_data['manufacturing'][prop_local] = value
            elif prop_local in metadata_props:
                specimen_data['metadata'][prop_local] = value
            else:
                specimen_data['properties'][prop_local] = value

        # If material URI is available, get material details
        if 'hasMaterial' in specimen_data['material']:
            material_uri = specimen_data['material']['hasMaterial']
            material_query = f"""
            SELECT ?materialName ?materialCode ?alloyDesignation WHERE {{
                <{material_uri}> dyn:hasMaterialName ?materialName .
                OPTIONAL {{ <{material_uri}> dyn:hasMaterialCode ?materialCode }}
                OPTIONAL {{ <{material_uri}> dyn:hasAlloyDesignation ?alloyDesignation }}
            }}
            """
            material_results = self.query_builder.sparql.execute_query(material_query)
            if material_results:
                specimen_data['material']['materialName'] = str(material_results[0].get('materialName', ''))
                specimen_data['material']['materialCode'] = str(material_results[0].get('materialCode', ''))
                specimen_data['material']['alloyDesignation'] = str(material_results[0].get('alloyDesignation', ''))

        logger.debug(f"Retrieved data for specimen: {specimen_data.get('id', specimen_uri)}")

        # Print formatted data if requested
        if print_data:
            self._print_specimen_data(specimen_data)

        return specimen_data

    def _print_specimen_data(self, specimen_data: Dict[str, Any]) -> None:
        """
        Print formatted specimen data to console.

        Args:
            specimen_data: Dictionary returned by get_specimen_data()
        """
        print(f"\nSpecimen ID: {specimen_data['id']}")
        print(f"URI: {specimen_data['uri']}")
        print("=" * 60)

        # Material information
        if specimen_data['material']:
            print(f"\nMaterial:")
            for key, value in specimen_data['material'].items():
                # Clean up display
                if key == 'hasMaterial':
                    print(f"  Material URI: {value.split('#')[-1]}")
                elif key == 'hasShape':
                    print(f"  Shape: {value.split('#')[-1]}")
                elif key == 'hasStructure':
                    print(f"  Structure: {value.split('#')[-1]}")
                else:
                    print(f"  {key}: {value}")

        # Dimensions
        if specimen_data['dimensions']:
            print(f"\nDimensions:")
            for key, value in specimen_data['dimensions'].items():
                display_name = key.replace('has', '').replace('Original', 'Original ').replace('Final', 'Final ')
                print(f"  {display_name}: {value}")

        # Manufacturing details
        if specimen_data['manufacturing']:
            print(f"\nManufacturing:")
            for key, value in specimen_data['manufacturing'].items():
                display_name = key.replace('has', '')
                if key == 'hasManufacturingMethod':
                    print(f"  {display_name}: {value.split('#')[-1]}")
                else:
                    print(f"  {display_name}: {value}")

        # Metadata
        if specimen_data['metadata']:
            print(f"\nMetadata:")
            for key, value in specimen_data['metadata'].items():
                display_name = key.replace('has', '')
                if 'User_' in str(value):
                    print(f"  {display_name}: {value.split('User_')[-1]}")
                else:
                    print(f"  {display_name}: {value}")

        # Other properties
        if specimen_data['properties']:
            print(f"\nOther Properties:")
            for key, value in specimen_data['properties'].items():
                display_name = key.replace('has', '')
                print(f"  {display_name}: {value}")

        print("=" * 60)

    def get_individual_property(
        self,
        individual_uri: str,
        property_name: str,
        return_type: str = 'value'
    ) -> Any:
        """
        Get a specific property value from any individual in the ontology.

        This is a general-purpose helper for extracting inherited properties from
        equipment individuals (Bar, StrainGauge, MomentumTrap, PulseShaper, etc.)
        for use in analysis calculations.

        Args:
            individual_uri: URI of the individual (e.g., "dyn:StrikerBar_C350_2ft")
            property_name: Property to extract (e.g., "hasLength", "hasGaugeFactor")
                          Can be with or without 'dyn:' prefix
            return_type: Type of return value:
                        'value' - Return just the value (default)
                        'all' - Return dict with value, unit, and other metadata

        Returns:
            Property value (numeric, string, or dict depending on return_type)
            Returns None if property not found

        Example:
            >>> loader = SpecimenLoader(ontology_manager)
            >>> loader.load_specimen_files()
            >>>
            >>> # Get bar length
            >>> bar_length = loader.get_individual_property(
            ...     "dyn:IncidentBar_C350_6ft",
            ...     "hasLength"
            ... )
            >>> print(f"Incident bar length: {bar_length} mm")
            >>>
            >>> # Get strain gauge factor
            >>> gauge_factor = loader.get_individual_property(
            ...     "dyn:StrainGauge_INC_SG1",
            ...     "hasGaugeFactor"
            ... )
            >>> print(f"Gauge factor: {gauge_factor}")
            >>>
            >>> # Get material reference
            >>> bar_material = loader.get_individual_property(
            ...     "dyn:StrikerBar_C350_2ft",
            ...     "hasMaterial"
            ... )
            >>> print(f"Bar material: {bar_material}")
        """
        # Normalize URIs
        if not individual_uri.startswith('http'):
            if individual_uri.startswith('dyn:'):
                individual_uri = f"{self.ns.DYN}{individual_uri.replace('dyn:', '')}"
            else:
                individual_uri = f"{self.ns.DYN}{individual_uri}"

        # Normalize property name
        if not property_name.startswith('dyn:') and not property_name.startswith('http'):
            property_name = f"dyn:{property_name}"

        # Query for the property
        query = f"""
        PREFIX dyn: <{self.ns.DYN}>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX qudt: <http://qudt.org/schema/qudt/>
        PREFIX unit: <http://qudt.org/vocab/unit/>

        SELECT ?value ?unit ?quantityKind WHERE {{
            <{individual_uri}> {property_name} ?value .
            OPTIONAL {{ {property_name} qudt:hasUnit ?unit }}
            OPTIONAL {{ {property_name} qudt:hasQuantityKind ?quantityKind }}
        }}
        """

        results = self.query_builder.sparql.execute_query(query)

        if not results:
            logger.warning(f"Property '{property_name}' not found for individual '{individual_uri}'")
            return None

        result = results[0]
        value = result.get('value')

        # Convert value to appropriate Python type
        if hasattr(value, 'toPython'):
            value = value.toPython()

        # Convert Decimal to float for numeric properties
        # RDFLib returns Decimal for xsd:decimal literals, but we want float for consistency
        if isinstance(value, Decimal):
            value = float(value)
        elif isinstance(value, int):
            # Also convert int to float for consistency in numeric calculations
            value = float(value)

        if return_type == 'all':
            # Return full metadata
            return {
                'value': value,
                'unit': str(result.get('unit', '')).split('#')[-1] if result.get('unit') else None,
                'quantity_kind': str(result.get('quantityKind', '')).split('/')[-1] if result.get('quantityKind') else None,
                'raw_value': result.get('value')
            }
        else:
            # Return just the value
            return value

    def get_multiple_properties(
        self,
        individual_uri: str,
        property_names: List[str]
    ) -> Dict[str, Any]:
        """
        Get multiple properties from an individual at once.

        Args:
            individual_uri: URI of the individual
            property_names: List of property names to extract

        Returns:
            Dictionary mapping property names to values

        Example:
            >>> loader = SpecimenLoader(ontology_manager)
            >>> loader.load_specimen_files()
            >>>
            >>> # Get multiple bar properties
            >>> bar_props = loader.get_multiple_properties(
            ...     "dyn:IncidentBar_C350_6ft",
            ...     ["hasLength", "hasDiameter", "hasMaterial"]
            ... )
            >>> print(f"Length: {bar_props['hasLength']} mm")
            >>> print(f"Diameter: {bar_props['hasDiameter']} mm")
            >>> print(f"Material: {bar_props['hasMaterial']}")
            >>>
            >>> # Get strain gauge properties
            >>> gauge_props = loader.get_multiple_properties(
            ...     "dyn:StrainGauge_INC_SG1",
            ...     ["hasGaugeFactor", "hasGaugeResistance", "hasDistanceFromSpecimen"]
            ... )
        """
        properties = {}
        for prop_name in property_names:
            properties[prop_name] = self.get_individual_property(individual_uri, prop_name)

        return properties

    def get_shpb_equipment_properties(
        self,
        test_metadata
    ) -> Dict[str, Any]:
        """
        Extract all equipment properties needed for SHPB analysis calculations.

        Retrieves bar dimensions, material properties, and strain gauge
        parameters from equipment individuals referenced in test metadata.

        Args:
            test_metadata: SHPBTestMetadata instance with equipment URIs

        Returns:
            Dictionary with complete equipment configuration:
            {
                'striker_bar': {
                    'uri': 'dyn:StrikerBar_C350_2ft',
                    'length': 609.6,          # mm
                    'diameter': 19.05,         # mm
                    'cross_section': 285.024,  # mm²
                    'material_uri': 'dyn:C530_Maraging',
                    'wave_speed': 5000.0,      # m/s
                    'elastic_modulus': None    # GPa (if available)
                },
                'incident_bar': {...},
                'transmission_bar': {...},
                'incident_gauge': {
                    'uri': 'dyn:StrainGauge_INC_SG1',
                    'gauge_factor': 2.12,
                    'gauge_resistance': 350.0,      # Ohm
                    'distance_from_specimen': 915.0  # mm
                },
                'transmission_gauge': {...}
            }

        Example:
            >>> from dynamat.mechanical.shpb.io import SHPBTestMetadata, SpecimenLoader
            >>> from dynamat.ontology import OntologyManager
            >>>
            >>> manager = OntologyManager()
            >>> loader = SpecimenLoader(manager)
            >>> loader.load_specimen_files()
            >>>
            >>> metadata = SHPBTestMetadata(
            ...     test_id="TEST_001",
            ...     incident_bar_uri="dyn:IncidentBar_C350_6ft",
            ...     transmission_bar_uri="dyn:TransmissionBar_C350_6ft",
            ...     striker_bar_uri="dyn:StrikerBar_C350_2ft",
            ...     incident_strain_gauge_uri="dyn:StrainGauge_INC_SG1",
            ...     transmission_strain_gauge_uri="dyn:StrainGauge_TRA_SG1",
            ...     # ... other required fields
            ... )
            >>>
            >>> equipment = loader.get_shpb_equipment_properties(metadata)
            >>> print(f"Incident bar cross-section: {equipment['incident_bar']['cross_section']} mm²")
            >>> print(f"Wave speed: {equipment['incident_bar']['wave_speed']} m/s")
        """
        equipment = {}

        # Property lists for extraction
        bar_props = ['hasLength', 'hasDiameter', 'hasCrossSection', 'hasMaterial']
        gauge_props = ['hasGaugeFactor', 'hasGaugeResistance', 'hasDistanceFromSpecimen']
        material_props = ['hasWaveSpeed', 'hasElasticModulus']

        # Extract striker bar properties
        logger.debug(f"Extracting striker bar properties: {test_metadata.striker_bar_uri}")
        striker_props = self.get_multiple_properties(test_metadata.striker_bar_uri, bar_props)
        material_uri = striker_props.get('hasMaterial')

        if material_uri:
            material = self.get_multiple_properties(material_uri, material_props)
            striker_props['material_uri'] = material_uri
            striker_props['wave_speed'] = material.get('hasWaveSpeed')
            striker_props['elastic_modulus'] = material.get('hasElasticModulus')

        equipment['striker_bar'] = {
            'uri': test_metadata.striker_bar_uri,
            'length': striker_props.get('hasLength'),
            'diameter': striker_props.get('hasDiameter'),
            'cross_section': striker_props.get('hasCrossSection'),
            'material_uri': striker_props.get('material_uri'),
            'wave_speed': striker_props.get('wave_speed'),
            'elastic_modulus': striker_props.get('elastic_modulus')
        }

        # Extract incident bar properties
        logger.debug(f"Extracting incident bar properties: {test_metadata.incident_bar_uri}")
        incident_props = self.get_multiple_properties(test_metadata.incident_bar_uri, bar_props)
        material_uri = incident_props.get('hasMaterial')

        if material_uri:
            material = self.get_multiple_properties(material_uri, material_props)
            incident_props['material_uri'] = material_uri
            incident_props['wave_speed'] = material.get('hasWaveSpeed')
            incident_props['elastic_modulus'] = material.get('hasElasticModulus')

        equipment['incident_bar'] = {
            'uri': test_metadata.incident_bar_uri,
            'length': incident_props.get('hasLength'),
            'diameter': incident_props.get('hasDiameter'),
            'cross_section': incident_props.get('hasCrossSection'),
            'material_uri': incident_props.get('material_uri'),
            'wave_speed': incident_props.get('wave_speed'),
            'elastic_modulus': incident_props.get('elastic_modulus')
        }

        # Extract transmission bar properties
        logger.debug(f"Extracting transmission bar properties: {test_metadata.transmission_bar_uri}")
        transmission_props = self.get_multiple_properties(test_metadata.transmission_bar_uri, bar_props)
        material_uri = transmission_props.get('hasMaterial')

        if material_uri:
            material = self.get_multiple_properties(material_uri, material_props)
            transmission_props['material_uri'] = material_uri
            transmission_props['wave_speed'] = material.get('hasWaveSpeed')
            transmission_props['elastic_modulus'] = material.get('hasElasticModulus')

        equipment['transmission_bar'] = {
            'uri': test_metadata.transmission_bar_uri,
            'length': transmission_props.get('hasLength'),
            'diameter': transmission_props.get('hasDiameter'),
            'cross_section': transmission_props.get('hasCrossSection'),
            'material_uri': transmission_props.get('material_uri'),
            'wave_speed': transmission_props.get('wave_speed'),
            'elastic_modulus': transmission_props.get('elastic_modulus')
        }

        # Extract incident strain gauge properties
        logger.debug(f"Extracting incident gauge properties: {test_metadata.incident_strain_gauge_uri}")
        inc_gauge = self.get_multiple_properties(test_metadata.incident_strain_gauge_uri, gauge_props)
        equipment['incident_gauge'] = {
            'uri': test_metadata.incident_strain_gauge_uri,
            'gauge_factor': inc_gauge.get('hasGaugeFactor'),
            'gauge_resistance': inc_gauge.get('hasGaugeResistance'),
            'distance_from_specimen': inc_gauge.get('hasDistanceFromSpecimen')
        }

        # Extract transmission strain gauge properties
        logger.debug(f"Extracting transmission gauge properties: {test_metadata.transmission_strain_gauge_uri}")
        tra_gauge = self.get_multiple_properties(test_metadata.transmission_strain_gauge_uri, gauge_props)
        equipment['transmission_gauge'] = {
            'uri': test_metadata.transmission_strain_gauge_uri,
            'gauge_factor': tra_gauge.get('hasGaugeFactor'),
            'gauge_resistance': tra_gauge.get('hasGaugeResistance'),
            'distance_from_specimen': tra_gauge.get('hasDistanceFromSpecimen')
        }

        logger.info(f"Extracted SHPB equipment properties for {test_metadata.test_id}")
        return equipment
