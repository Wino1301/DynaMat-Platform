"""
DynaMat Platform - Query Builder
High-level query utilities for common DynaMat operations
"""

import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, date
from dataclasses import dataclass

from .manager import OntologyManager, QueryMode


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
    
    def __init__(self, ontology_manager: OntologyManager):
        """
        Initialize with an ontology manager instance.
        
        Args:
            ontology_manager: Initialized OntologyManager instance
        """
        self.manager = ontology_manager
        self.dyn = ontology_manager.DYN
    
    # ============================================================================
    # MATERIAL QUERIES
    # ============================================================================
    
    def get_available_materials(self) -> List[Dict[str, Any]]:
        """Get all available materials with basic properties"""
        query = """
        SELECT ?material ?materialName ?materialCode ?alloyDesignation ?description WHERE {
            { ?material rdf:type dyn:Material }
            UNION 
            { ?material rdf:type ?materialType . ?materialType rdfs:subClassOf* dyn:Material }
            OPTIONAL { ?material dyn:hasMaterialName ?materialName }
            OPTIONAL { ?material dyn:hasName ?materialName }
            OPTIONAL { ?material dyn:hasMaterialCode ?materialCode }
            OPTIONAL { ?material dyn:hasAlloyDesignation ?alloyDesignation }
            OPTIONAL { ?material dyn:hasDescription ?description }
        }
        ORDER BY ?materialName ?materialCode
        """
        
        results = self.manager._execute_query(query)
        
        materials = []
        for row in results:
            material_data = {
                "uri": str(row.material),
                "materialName": str(row.materialName) if row.materialName else "",
                "materialCode": str(row.materialCode) if row.materialCode else "",
                "alloyDesignation": str(row.alloyDesignation) if row.alloyDesignation else "",
                "description": str(row.description) if row.description else ""
            }
            materials.append(material_data)
        
        return materials
    
    def get_material_properties(self, material_uri: str) -> Dict[str, Any]:
        """Get comprehensive material properties including provenance"""
        query = """
        SELECT ?property ?value ?unit ?uncertainty ?provenance ?source WHERE {
            ?material dyn:hasPropertyValue ?propertyValue .
            ?propertyValue dyn:hasProperty ?property .
            ?propertyValue dyn:hasValue ?value .
            OPTIONAL { ?propertyValue dyn:hasUnit ?unit }
            OPTIONAL { ?propertyValue dyn:hasUncertainty ?uncertainty }
            OPTIONAL { ?propertyValue dyn:hasProvenance ?provenance }
            OPTIONAL { ?propertyValue dyn:hasSource ?source }
        }
        """
        
        results = self.manager._execute_query(query, {"material": self.manager.URIRef(material_uri)})
        
        properties = {}
        for row in results:
            prop_name = self.manager._extract_local_name(str(row.property))
            prop_data = {
                "value": float(row.value) if row.value else None,
                "unit": str(row.unit) if row.unit else None,
                "uncertainty": float(row.uncertainty) if row.uncertainty else None,
                "provenance": str(row.provenance) if row.provenance else None,
                "source": str(row.source) if row.source else None
            }
            properties[prop_name] = prop_data
        
        return properties
    
    def find_materials_by_property(self, property_name: str, 
                                 value_min: Optional[float] = None,
                                 value_max: Optional[float] = None) -> List[Dict[str, Any]]:
        """Find materials based on property value ranges"""
        conditions = []
        bindings = {}
        
        if value_min is not None:
            conditions.append("FILTER(?value >= ?minValue)")
            bindings["minValue"] = self.manager.Literal(value_min)
        
        if value_max is not None:
            conditions.append("FILTER(?value <= ?maxValue)")
            bindings["maxValue"] = self.manager.Literal(value_max)
        
        # Try both direct property and PropertyValue pattern
        query = f"""
        SELECT DISTINCT ?material ?materialName ?value ?unit WHERE {{
            {{
                # Direct property pattern
                ?material dyn:has{property_name} ?value .
                OPTIONAL {{ ?material dyn:hasMaterialName ?materialName }}
                {' '.join(conditions)}
            }}
            UNION
            {{
                # PropertyValue pattern
                ?material dyn:hasPropertyValue ?propertyValue .
                ?propertyValue dyn:hasProperty dyn:{property_name} .
                ?propertyValue dyn:hasValue ?value .
                OPTIONAL {{ ?propertyValue dyn:hasUnit ?unit }}
                OPTIONAL {{ ?material dyn:hasMaterialName ?materialName }}
                {' '.join(conditions)}
            }}
        }}
        ORDER BY ?value
        """
        
        results = self.manager._execute_query(query, bindings)
        
        materials = []
        for row in results:
            material_data = {
                "uri": str(row.material),
                "name": str(row.materialName) if row.materialName else "",
                "value": float(row.value) if row.value else None,
                "unit": str(row.unit) if row.unit else None
            }
            materials.append(material_data)
        
        return materials
    
    # ============================================================================
    # SPECIMEN QUERIES
    # ============================================================================
    
    def search_specimens(self, criteria: SpecimenSearchCriteria) -> List[Dict[str, Any]]:
        """Search specimens using structured criteria"""
        conditions = []
        bindings = {}
        
        if criteria.material_name:
            conditions.append("""
                ?specimen dyn:hasMaterial ?material .
                ?material dyn:hasMaterialName ?materialName .
                FILTER(CONTAINS(LCASE(?materialName), LCASE(?materialFilter)))
            """)
            bindings["materialFilter"] = self.manager.Literal(criteria.material_name)
        
        if criteria.structure_type:
            conditions.append("""
                ?specimen dyn:hasStructure ?structure .
                ?structure dyn:hasName ?structureName .
                FILTER(CONTAINS(LCASE(?structureName), LCASE(?structureFilter)))
            """)
            bindings["structureFilter"] = self.manager.Literal(criteria.structure_type)
        
        if criteria.shape:
            conditions.append("""
                ?specimen dyn:hasShape ?shape .
                ?shape dyn:hasName ?shapeName .
                FILTER(CONTAINS(LCASE(?shapeName), LCASE(?shapeFilter)))
            """)
            bindings["shapeFilter"] = self.manager.Literal(criteria.shape)
        
        if criteria.batch_id:
            conditions.append("?specimen dyn:hasSpecimenBatchID ?batchId .")
            bindings["batchId"] = self.manager.Literal(criteria.batch_id)
        
        if criteria.creation_date_from:
            date_str = criteria.creation_date_from if isinstance(criteria.creation_date_from, str) else criteria.creation_date_from.isoformat()
            conditions.append("?specimen dyn:hasCreationDate ?creationDate . FILTER(?creationDate >= ?dateFrom)")
            bindings["dateFrom"] = self.manager.Literal(date_str, datatype=self.manager.XSD.date)
        
        if criteria.creation_date_to:
            date_str = criteria.creation_date_to if isinstance(criteria.creation_date_to, str) else criteria.creation_date_to.isoformat()
            conditions.append("?specimen dyn:hasCreationDate ?creationDate . FILTER(?creationDate <= ?dateTo)")
            bindings["dateTo"] = self.manager.Literal(date_str, datatype=self.manager.XSD.date)
        
        if criteria.diameter_min:
            conditions.append("?specimen dyn:hasOriginalDiameter ?diameter . FILTER(?diameter >= ?diameterMin)")
            bindings["diameterMin"] = self.manager.Literal(criteria.diameter_min)
        
        if criteria.diameter_max:
            conditions.append("?specimen dyn:hasOriginalDiameter ?diameter . FILTER(?diameter <= ?diameterMax)")
            bindings["diameterMax"] = self.manager.Literal(criteria.diameter_max)
        
        if criteria.length_min:
            conditions.append("?specimen dyn:hasOriginalLength ?length . FILTER(?length >= ?lengthMin)")
            bindings["lengthMin"] = self.manager.Literal(criteria.length_min)
        
        if criteria.length_max:
            conditions.append("?specimen dyn:hasOriginalLength ?length . FILTER(?length <= ?lengthMax)")
            bindings["lengthMax"] = self.manager.Literal(criteria.length_max)
        
        query = f"""
        SELECT ?specimen ?specimenID ?materialName ?structureName ?shapeName 
               ?diameter ?length ?creationDate ?description WHERE {{
            ?specimen rdf:type dyn:Specimen .
            ?specimen dyn:hasSpecimenID ?specimenID .
            
            OPTIONAL {{
                ?specimen dyn:hasMaterial ?material .
                ?material dyn:hasMaterialName ?materialName .
            }}
            
            OPTIONAL {{
                ?specimen dyn:hasStructure ?structure .
                ?structure dyn:hasName ?structureName .
            }}
            
            OPTIONAL {{
                ?specimen dyn:hasShape ?shape .
                ?shape dyn:hasName ?shapeName .
            }}
            
            OPTIONAL {{ ?specimen dyn:hasOriginalDiameter ?diameter }}
            OPTIONAL {{ ?specimen dyn:hasOriginalLength ?length }}
            OPTIONAL {{ ?specimen dyn:hasCreationDate ?creationDate }}
            OPTIONAL {{ ?specimen dyn:hasDescription ?description }}
            
            {' '.join(conditions)}
        }}
        ORDER BY ?specimenID
        """
        
        results = self.manager._execute_query(query, bindings)
        
        specimens = []
        for row in results:
            specimen_data = {
                "uri": str(row.specimen),
                "specimen_id": str(row.specimenID) if row.specimenID else "",
                "material": str(row.materialName) if row.materialName else "",
                "structure": str(row.structureName) if row.structureName else "",
                "shape": str(row.shapeName) if row.shapeName else "",
                "diameter": float(row.diameter) if row.diameter else None,
                "length": float(row.length) if row.length else None,
                "creation_date": str(row.creationDate) if row.creationDate else "",
                "description": str(row.description) if row.description else ""
            }
            specimens.append(specimen_data)
        
        return specimens
    
    def get_specimen_test_history(self, specimen_uri: str) -> List[Dict[str, Any]]:
        """Get all tests performed on a specimen"""
        query = """
        SELECT ?test ?testID ?testDate ?testType ?operator WHERE {
            ?test dyn:performedOn ?specimen .
            ?test dyn:hasTestID ?testID .
            ?test rdf:type ?testType .
            OPTIONAL { ?test dyn:hasTestDate ?testDate }
            OPTIONAL { 
                ?test dyn:hasUser ?user .
                ?user dyn:hasName ?operator 
            }
        }
        ORDER BY DESC(?testDate)
        """
        
        results = self.manager._execute_query(query, {"specimen": self.manager.URIRef(specimen_uri)})
        
        tests = []
        for row in results:
            test_data = {
                "uri": str(row.test),
                "test_id": str(row.testID) if row.testID else "",
                "test_date": str(row.testDate) if row.testDate else "",
                "test_type": self.manager._extract_local_name(str(row.testType)),
                "operator": str(row.operator) if row.operator else ""
            }
            tests.append(test_data)
        
        return tests
    
    # ============================================================================
    # TEST QUERIES
    # ============================================================================
    
    def search_tests(self, criteria: TestSearchCriteria) -> List[Dict[str, Any]]:
        """Search tests using structured criteria"""
        conditions = []
        bindings = {}
        
        if criteria.specimen_id:
            conditions.append("""
                ?test dyn:performedOn ?specimen .
                ?specimen dyn:hasSpecimenID ?specimenID .
                FILTER(?specimenID = ?targetSpecimenID)
            """)
            bindings["targetSpecimenID"] = self.manager.Literal(criteria.specimen_id)
        
        if criteria.material_name:
            conditions.append("""
                ?test dyn:performedOn ?specimen .
                ?specimen dyn:hasMaterial ?material .
                ?material dyn:hasMaterialName ?materialName .
                FILTER(CONTAINS(LCASE(?materialName), LCASE(?materialFilter)))
            """)
            bindings["materialFilter"] = self.manager.Literal(criteria.material_name)
        
        if criteria.test_type:
            # Map common test type names
            type_mapping = {
                "SHPB": "SHPBCompression",
                "Quasistatic": "QuasistaticTest", 
                "Tensile": "TensileTest"
            }
            test_type = type_mapping.get(criteria.test_type, criteria.test_type)
            conditions.append("?test rdf:type dyn:%s ." % test_type)
        
        if criteria.date_from:
            date_str = criteria.date_from if isinstance(criteria.date_from, str) else criteria.date_from.isoformat()
            conditions.append("?test dyn:hasTestDate ?testDate . FILTER(?testDate >= ?dateFrom)")
            bindings["dateFrom"] = self.manager.Literal(date_str, datatype=self.manager.XSD.date)
        
        if criteria.date_to:
            date_str = criteria.date_to if isinstance(criteria.date_to, str) else criteria.date_to.isoformat()
            conditions.append("?test dyn:hasTestDate ?testDate . FILTER(?testDate <= ?dateTo)")
            bindings["dateTo"] = self.manager.Literal(date_str, datatype=self.manager.XSD.date)
        
        if criteria.strain_rate_min:
            conditions.append("?test dyn:hasTargetStrainRate ?strainRate . FILTER(?strainRate >= ?strainRateMin)")
            bindings["strainRateMin"] = self.manager.Literal(criteria.strain_rate_min)
        
        if criteria.strain_rate_max:
            conditions.append("?test dyn:hasTargetStrainRate ?strainRate . FILTER(?strainRate <= ?strainRateMax)")
            bindings["strainRateMax"] = self.manager.Literal(criteria.strain_rate_max)
        
        if criteria.temperature_min:
            conditions.append("?test dyn:hasTestTemperature ?temperature . FILTER(?temperature >= ?tempMin)")
            bindings["tempMin"] = self.manager.Literal(criteria.temperature_min)
        
        if criteria.temperature_max:
            conditions.append("?test dyn:hasTestTemperature ?temperature . FILTER(?temperature <= ?tempMax)")
            bindings["tempMax"] = self.manager.Literal(criteria.temperature_max)
        
        if criteria.operator:
            conditions.append("""
                ?test dyn:hasUser ?user .
                ?user dyn:hasName ?userName .
                FILTER(CONTAINS(LCASE(?userName), LCASE(?operatorFilter)))
            """)
            bindings["operatorFilter"] = self.manager.Literal(criteria.operator)
        
        query = f"""
        SELECT ?test ?testID ?testDate ?testType ?specimenID ?materialName 
               ?strainRate ?temperature ?operator WHERE {{
            ?test rdf:type dyn:MechanicalTest .
            ?test dyn:hasTestID ?testID .
            ?test rdf:type ?testType .
            
            OPTIONAL {{ ?test dyn:hasTestDate ?testDate }}
            OPTIONAL {{ ?test dyn:hasTargetStrainRate ?strainRate }}
            OPTIONAL {{ ?test dyn:hasTestTemperature ?temperature }}
            
            OPTIONAL {{
                ?test dyn:performedOn ?specimen .
                ?specimen dyn:hasSpecimenID ?specimenID .
                OPTIONAL {{
                    ?specimen dyn:hasMaterial ?material .
                    ?material dyn:hasMaterialName ?materialName .
                }}
            }}
            
            OPTIONAL {{
                ?test dyn:hasUser ?user .
                ?user dyn:hasName ?operator .
            }}
            
            {' '.join(conditions)}
        }}
        ORDER BY DESC(?testDate) ?testID
        """
        
        results = self.manager._execute_query(query, bindings)
        
        tests = []
        for row in results:
            test_data = {
                "uri": str(row.test),
                "test_id": str(row.testID) if row.testID else "",
                "test_date": str(row.testDate) if row.testDate else "",
                "test_type": self.manager._extract_local_name(str(row.testType)),
                "specimen_id": str(row.specimenID) if row.specimenID else "",
                "material": str(row.materialName) if row.materialName else "",
                "strain_rate": float(row.strainRate) if row.strainRate else None,
                "temperature": float(row.temperature) if row.temperature else None,
                "operator": str(row.operator) if row.operator else ""
            }
            tests.append(test_data)
        
        return tests
    
    def get_test_data_files(self, test_uri: str) -> List[Dict[str, Any]]:
        """Get all data files associated with a test"""
        query = """
        SELECT ?dataFile ?fileName ?relativePath ?fileSize ?fileType WHERE {
            ?test dyn:hasDataFile ?dataFile .
            OPTIONAL { ?dataFile dyn:hasFileName ?fileName }
            OPTIONAL { ?dataFile dyn:hasRelativePath ?relativePath }
            OPTIONAL { ?dataFile dyn:hasFileSize ?fileSize }
            OPTIONAL { ?dataFile dyn:hasFormat ?fileType }
        }
        ORDER BY ?fileName
        """
        
        results = self.manager._execute_query(query, {"test": self.manager.URIRef(test_uri)})
        
        files = []
        for row in results:
            file_data = {
                "uri": str(row.dataFile),
                "filename": str(row.fileName) if row.fileName else "",
                "path": str(row.relativePath) if row.relativePath else "",
                "size": int(row.fileSize) if row.fileSize else 0,
                "type": str(row.fileType) if row.fileType else ""
            }
            files.append(file_data)
        
        return files

    def get_available_tests(self, test_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get available tests, optionally filtered by type"""
        conditions = []
        if test_type:
            conditions.append(f"?test rdf:type dyn:{test_type} .")
        
        query = f"""
        SELECT ?test ?testID ?testDate ?testType ?operator ?materialName WHERE {{
            {{ ?test rdf:type dyn:MechanicalTest }}
            UNION 
            {{ ?test rdf:type ?testType . ?testType rdfs:subClassOf* dyn:MechanicalTest }}
            
            OPTIONAL {{ ?test dyn:hasTestID ?testID }}
            OPTIONAL {{ ?test dyn:hasTestDate ?testDate }}
            OPTIONAL {{ ?test rdf:type ?testType }}
            OPTIONAL {{
                ?test dyn:hasUser ?user .
                ?user dyn:hasName ?operator
            }}
            OPTIONAL {{
                ?test dyn:performedOn ?specimen .
                ?specimen dyn:hasMaterial ?material .
                ?material dyn:hasMaterialName ?materialName
            }}
            
            {' '.join(conditions)}
        }}
        ORDER BY DESC(?testDate) ?testID
        """
        
        results = self.manager._execute_query(query)
        
        tests = []
        for row in results:
            # Use testID if available, otherwise use extracted local name
            test_name = (str(row.testID) if row.testID else 
                        self.manager._extract_local_name(str(row.test)))
            
            test_data = {
                "uri": str(row.test),
                "testId": test_name,
                "testDate": str(row.testDate) if row.testDate else "",
                "testType": self.manager._extract_local_name(str(row.testType)) if row.testType else "",
                "operator": str(row.operator) if row.operator else "",
                "materialName": str(row.materialName) if row.materialName else ""
            }
            tests.append(test_data)
        
        return tests
    
    # ============================================================================
    # EQUIPMENT QUERIES
    # ============================================================================
    
    def get_available_equipment(self, equipment_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get available equipment, optionally filtered by type"""
        conditions = []
        if equipment_type:
            conditions.append(f"?equipment rdf:type dyn:{equipment_type} .")
        
        query = f"""
        SELECT ?equipment ?name ?model ?manufacturer ?description WHERE {{
            ?equipment rdf:type dyn:Equipment .
            OPTIONAL {{ ?equipment dyn:hasName ?name }}
            OPTIONAL {{ ?equipment dyn:hasModel ?model }}
            OPTIONAL {{ ?equipment dyn:hasManufacturer ?manufacturer }}
            OPTIONAL {{ ?equipment dyn:hasDescription ?description }}
            
            {' '.join(conditions)}
        }}
        ORDER BY ?name
        """
        
        results = self.manager._execute_query(query)
        
        equipment = []
        for row in results:
            # Use name if available, otherwise use model, otherwise use extracted local name
            equipment_name = (str(row.name) if row.name else 
                             str(row.model) if row.model else 
                             self.manager._extract_local_name(str(row.equipment)))
            
            equip_data = {
                "uri": str(row.equipment),
                "equipmentName": equipment_name,
                "model": str(row.model) if row.model else "",
                "manufacturer": str(row.manufacturer) if row.manufacturer else "",
                "description": str(row.description) if row.description else ""
            }
            equipment.append(equip_data)
        
        return equipment
    
    # ============================================================================
    # STATISTICAL QUERIES
    # ============================================================================
    
    def get_test_statistics(self) -> Dict[str, Any]:
        """Get statistics about tests in the database"""
        stats = {}
        
        # Total test count
        query = "SELECT (COUNT(?test) AS ?count) WHERE { ?test rdf:type dyn:MechanicalTest }"
        result = self.manager._execute_query(query)
        stats["total_tests"] = int(result[0].count) if result else 0
        
        # Tests by type
        query = """
        SELECT ?testType (COUNT(?test) AS ?count) WHERE {
            ?test rdf:type ?testType .
            ?testType rdfs:subClassOf dyn:MechanicalTest .
        }
        GROUP BY ?testType
        ORDER BY DESC(?count)
        """
        results = self.manager._execute_query(query)
        stats["tests_by_type"] = {}
        for row in results:
            test_type = self.manager._extract_local_name(str(row.testType))
            stats["tests_by_type"][test_type] = int(row.count)
        
        # Tests by material
        query = """
        SELECT ?materialName (COUNT(?test) AS ?count) WHERE {
            ?test dyn:performedOn ?specimen .
            ?specimen dyn:hasMaterial ?material .
            ?material dyn:hasMaterialName ?materialName .
        }
        GROUP BY ?materialName
        ORDER BY DESC(?count)
        """
        results = self.manager._execute_query(query)
        stats["tests_by_material"] = {}
        for row in results:
            material = str(row.materialName)
            stats["tests_by_material"][material] = int(row.count)
        
        return stats
    
    def get_specimen_statistics(self) -> Dict[str, Any]:
        """Get statistics about specimens in the database"""
        stats = {}
        
        # Total specimen count
        query = "SELECT (COUNT(?specimen) AS ?count) WHERE { ?specimen rdf:type dyn:Specimen }"
        result = self.manager._execute_query(query)
        stats["total_specimens"] = int(result[0].count) if result else 0
        
        # Specimens by material
        query = """
        SELECT ?materialName (COUNT(?specimen) AS ?count) WHERE {
            ?specimen dyn:hasMaterial ?material .
            ?material dyn:hasMaterialName ?materialName .
        }
        GROUP BY ?materialName
        ORDER BY DESC(?count)
        """
        results = self.manager._execute_query(query)
        stats["specimens_by_material"] = {}
        for row in results:
            material = str(row.materialName)
            stats["specimens_by_material"][material] = int(row.count)
        
        # Specimens by structure
        query = """
        SELECT ?structureName (COUNT(?specimen) AS ?count) WHERE {
            ?specimen dyn:hasStructure ?structure .
            ?structure dyn:hasName ?structureName .
        }
        GROUP BY ?structureName
        ORDER BY DESC(?count)
        """
        results = self.manager._execute_query(query)
        stats["specimens_by_structure"] = {}
        for row in results:
            structure = str(row.structureName)
            stats["specimens_by_structure"][structure] = int(row.count)
        
        return stats