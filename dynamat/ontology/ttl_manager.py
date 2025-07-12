"""
General TTL File Manager

A general-purpose TTL file manager that can handle any TTL file creation,
not just experimental data. Manages the database folder structure and follows
the SPN-MaterialName-TestID naming convention.

Key Features:
1. Creates/updates temporary TTL files as user fills forms
2. Manages final TTL export with proper naming convention
3. Handles database folder structure creation
4. Works with any ontology class, not just experimental data
5. Supports multiple TTL files per specimen (specimen.ttl, test.ttl, etc.)
"""

import os
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

# Add the parent directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from rdflib import Graph, Namespace, URIRef, Literal, BNode
    from rdflib.namespace import RDF, RDFS, OWL, XSD
    from dynamat.ontology.manager import get_ontology_manager
    from dynamat.config import config
except ImportError:
    # Fallback for testing
    def get_ontology_manager():
        return None
    
    class Graph:
        pass
    class Namespace:
        pass
    class config:
        ONTOLOGY_URI = "https://github.com/Wino1301/DynaMat-Platform/ontology#"


@dataclass
class TTLFileInfo:
    """Information about a TTL file"""
    file_path: Path
    file_type: str  # e.g., 'specimen', 'test', 'characterization'
    class_name: str  # Primary ontology class
    individual_uri: str  # Main individual URI
    temp_file: Optional[Path] = None
    last_updated: Optional[datetime] = None


@dataclass
class SpecimenInfo:
    """Information about a specimen and its files"""
    specimen_id: str  # e.g., SPN-Al6061-001
    material_name: str  # e.g., Al6061
    test_id: str  # e.g., 001
    base_folder: Path  # database/specimens/SPN-Al6061-001/
    ttl_files: Dict[str, TTLFileInfo] = None  # file_type -> TTLFileInfo


class TTLFileManager:
    """
    General-purpose TTL file manager for the DynaMat platform.
    
    Handles creation, updating, and management of TTL files following
    the project's naming conventions and folder structure.
    """
    
    def __init__(self, ontology_manager=None, database_root: Optional[Path] = None):
        self.ontology_manager = ontology_manager or get_ontology_manager()
        
        # Set database root (default to project_root/database)
        if database_root:
            self.database_root = database_root
        else:
            # Find project root (look for dynamat folder)
            current_path = Path.cwd()
            while current_path.parent != current_path:
                if (current_path / "dynamat").exists():
                    self.database_root = current_path / "database"
                    break
                current_path = current_path.parent
            else:
                self.database_root = Path.cwd() / "database"
        
        # Create database folder structure
        self.database_root.mkdir(exist_ok=True)
        (self.database_root / "specimens").mkdir(exist_ok=True)
        
        # Temporary files directory
        self.temp_dir = Path(tempfile.gettempdir()) / "dynamat_temp"
        self.temp_dir.mkdir(exist_ok=True)
        
        # Ontology namespace
        self.dyn = Namespace(config.ONTOLOGY_URI)
        
        # Track active specimens and their files
        self.active_specimens: Dict[str, SpecimenInfo] = {}
    
    # =============================================================================
    # SPECIMEN MANAGEMENT
    # =============================================================================
    
    def create_specimen(self, material_name: str, test_id: Optional[str] = None) -> SpecimenInfo:
        """
        Create a new specimen with proper naming convention.
        
        Args:
            material_name: Name of the material (e.g., "Al6061", "Steel1018")
            test_id: Optional test ID (if None, will auto-increment)
            
        Returns:
            SpecimenInfo object for the new specimen
        """
        
        # Generate test ID if not provided
        if not test_id:
            test_id = self._get_next_test_id(material_name)
        
        # Create specimen ID following convention: SPN-MaterialName-TestID
        specimen_id = f"SPN-{material_name}-{test_id:03d}" if isinstance(test_id, int) else f"SPN-{material_name}-{test_id}"
        
        # Create specimen folder
        specimen_folder = self.database_root / "specimens" / specimen_id
        specimen_folder.mkdir(exist_ok=True)
        
        # Create subfolders
        (specimen_folder / "raw").mkdir(exist_ok=True)
        (specimen_folder / "processed").mkdir(exist_ok=True)
        
        # Create specimen info
        specimen_info = SpecimenInfo(
            specimen_id=specimen_id,
            material_name=material_name,
            test_id=str(test_id),
            base_folder=specimen_folder,
            ttl_files={}
        )
        
        # Track this specimen
        self.active_specimens[specimen_id] = specimen_info
        
        return specimen_info
    
    def get_specimen(self, specimen_id: str) -> Optional[SpecimenInfo]:
        """Get specimen info by ID"""
        
        if specimen_id in self.active_specimens:
            return self.active_specimens[specimen_id]
        
        # Try to load from disk
        specimen_folder = self.database_root / "specimens" / specimen_id
        if specimen_folder.exists():
            # Parse specimen ID to extract components
            parts = specimen_id.split('-')
            if len(parts) >= 3:
                material_name = parts[1]
                test_id = parts[2]
                
                specimen_info = SpecimenInfo(
                    specimen_id=specimen_id,
                    material_name=material_name,
                    test_id=test_id,
                    base_folder=specimen_folder,
                    ttl_files={}
                )
                
                # Load existing TTL files
                self._load_existing_ttl_files(specimen_info)
                
                self.active_specimens[specimen_id] = specimen_info
                return specimen_info
        
        return None
    
    def _get_next_test_id(self, material_name: str) -> int:
        """Get the next available test ID for a material"""
        
        specimens_dir = self.database_root / "specimens"
        if not specimens_dir.exists():
            return 1
        
        # Find existing specimens for this material
        prefix = f"SPN-{material_name}-"
        existing_ids = []
        
        for folder in specimens_dir.iterdir():
            if folder.is_dir() and folder.name.startswith(prefix):
                try:
                    test_id_str = folder.name[len(prefix):]
                    test_id = int(test_id_str)
                    existing_ids.append(test_id)
                except ValueError:
                    continue
        
        # Return next available ID
        return max(existing_ids, default=0) + 1
    
    def _load_existing_ttl_files(self, specimen_info: SpecimenInfo):
        """Load information about existing TTL files for a specimen"""
        
        for ttl_file in specimen_info.base_folder.glob("*.ttl"):
            # Determine file type from filename
            file_type = self._determine_file_type(ttl_file.name)
            
            # Create TTL file info
            ttl_info = TTLFileInfo(
                file_path=ttl_file,
                file_type=file_type,
                class_name="",  # Would need to parse to determine
                individual_uri="",  # Would need to parse to determine
                last_updated=datetime.fromtimestamp(ttl_file.stat().st_mtime)
            )
            
            specimen_info.ttl_files[file_type] = ttl_info
    
    def _determine_file_type(self, filename: str) -> str:
        """Determine file type from filename"""
        
        filename_lower = filename.lower()
        
        if 'specimen' in filename_lower:
            return 'specimen'
        elif 'test' in filename_lower:
            return 'test'
        elif 'characterization' in filename_lower:
            return 'characterization'
        elif 'analysis' in filename_lower:
            return 'analysis'
        else:
            return 'other'
    
    # =============================================================================
    # TTL FILE OPERATIONS
    # =============================================================================
    
    def create_ttl_file(
        self, 
        specimen_id: str, 
        file_type: str, 
        class_name: str, 
        initial_data: Optional[Dict[str, Any]] = None
    ) -> TTLFileInfo:
        """
        Create a new TTL file for a specimen.
        
        Args:
            specimen_id: The specimen ID (e.g., "SPN-Al6061-001")
            file_type: Type of file ('specimen', 'test', 'characterization', etc.)
            class_name: Primary ontology class for this file
            initial_data: Optional initial data to populate
            
        Returns:
            TTLFileInfo object for the new file
        """
        
        # Get or create specimen
        specimen_info = self.get_specimen(specimen_id)
        if not specimen_info:
            # Extract material name from specimen_id
            parts = specimen_id.split('-')
            if len(parts) >= 2:
                material_name = parts[1]
                specimen_info = self.create_specimen(material_name)
            else:
                raise ValueError(f"Invalid specimen ID format: {specimen_id}")
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d")
        filename = f"{specimen_id}_{file_type}_{timestamp}.ttl"
        file_path = specimen_info.base_folder / filename
        
        # Generate individual URI
        individual_uri = f"{config.ONTOLOGY_URI}{specimen_id}_{class_name}"
        
        # Create temporary file
        temp_file = self._create_temp_file(file_type, class_name)
        
        # Create TTL file info
        ttl_info = TTLFileInfo(
            file_path=file_path,
            file_type=file_type,
            class_name=class_name,
            individual_uri=individual_uri,
            temp_file=temp_file,
            last_updated=datetime.now()
        )
        
        # Initialize TTL content
        self._initialize_ttl_content(ttl_info, initial_data)
        
        # Track this file
        specimen_info.ttl_files[file_type] = ttl_info
        
        return ttl_info
    
    def update_ttl_file(self, specimen_id: str, file_type: str, data: Dict[str, Any]):
        """Update a TTL file with new data"""
        
        specimen_info = self.get_specimen(specimen_id)
        if not specimen_info:
            raise ValueError(f"Specimen {specimen_id} not found")
        
        if file_type not in specimen_info.ttl_files:
            raise ValueError(f"TTL file type {file_type} not found for specimen {specimen_id}")
        
        ttl_info = specimen_info.ttl_files[file_type]
        
        # Update temporary file
        self._update_ttl_content(ttl_info, data)
        
        # Update timestamp
        ttl_info.last_updated = datetime.now()
    
    def export_ttl_file(self, specimen_id: str, file_type: str) -> Path:
        """Export TTL file from temporary to final location"""
        
        specimen_info = self.get_specimen(specimen_id)
        if not specimen_info:
            raise ValueError(f"Specimen {specimen_id} not found")
        
        if file_type not in specimen_info.ttl_files:
            raise ValueError(f"TTL file type {file_type} not found for specimen {specimen_id}")
        
        ttl_info = specimen_info.ttl_files[file_type]
        
        # Copy from temporary file to final location
        if ttl_info.temp_file and ttl_info.temp_file.exists():
            # Read temporary content
            with open(ttl_info.temp_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Write to final location
            with open(ttl_info.file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return ttl_info.file_path
        else:
            raise ValueError(f"No temporary file found for {file_type}")
    
    def _create_temp_file(self, file_type: str, class_name: str) -> Path:
        """Create a temporary TTL file"""
        
        unique_id = str(uuid.uuid4())[:8]
        temp_filename = f"{file_type}_{class_name}_{unique_id}.ttl"
        return self.temp_dir / temp_filename
    
    def _initialize_ttl_content(self, ttl_info: TTLFileInfo, initial_data: Optional[Dict[str, Any]]):
        """Initialize TTL file content"""
        
        # Create RDF graph
        graph = Graph()
        graph.bind("dyn", self.dyn)
        graph.bind("rdf", RDF)
        graph.bind("rdfs", RDFS)
        graph.bind("owl", OWL)
        graph.bind("xsd", XSD)
        
        # Add main individual
        individual = URIRef(ttl_info.individual_uri)
        class_uri = URIRef(f"{config.ONTOLOGY_URI}{ttl_info.class_name}")
        
        graph.add((individual, RDF.type, class_uri))
        graph.add((individual, RDF.type, OWL.NamedIndividual))
        
        # Add initial data if provided
        if initial_data:
            self._add_data_to_graph(graph, individual, initial_data)
        
        # Add metadata
        self._add_metadata_to_graph(graph, individual)
        
        # Write to temporary file
        if ttl_info.temp_file:
            graph.serialize(destination=str(ttl_info.temp_file), format='turtle')
    
    def _update_ttl_content(self, ttl_info: TTLFileInfo, data: Dict[str, Any]):
        """Update TTL file content with new data"""
        
        if not ttl_info.temp_file or not ttl_info.temp_file.exists():
            # Create initial content if temp file doesn't exist
            self._initialize_ttl_content(ttl_info, data)
            return
        
        # Load existing graph
        graph = Graph()
        graph.parse(str(ttl_info.temp_file), format='turtle')
        
        # Update with new data
        individual = URIRef(ttl_info.individual_uri)
        self._add_data_to_graph(graph, individual, data)
        
        # Update modification time
        modified_time = Literal(datetime.now().isoformat(), datatype=XSD.dateTime)
        
        # Remove old modification time
        for triple in graph.triples((individual, self.dyn.lastModified, None)):
            graph.remove(triple)
        
        # Add new modification time
        graph.add((individual, self.dyn.lastModified, modified_time))
        
        # Write back to temporary file
        graph.serialize(destination=str(ttl_info.temp_file), format='turtle')
    
    def _add_data_to_graph(self, graph: Graph, individual: URIRef, data: Dict[str, Any]):
        """Add data dictionary to RDF graph"""
        
        for key, value in data.items():
            if value is None or value == "":
                continue
            
            property_uri = URIRef(f"{config.ONTOLOGY_URI}{key}")
            
            # Determine how to add the value based on its type
            if isinstance(value, bool):
                graph.add((individual, property_uri, Literal(value, datatype=XSD.boolean)))
            elif isinstance(value, int):
                graph.add((individual, property_uri, Literal(value, datatype=XSD.integer)))
            elif isinstance(value, float):
                graph.add((individual, property_uri, Literal(value, datatype=XSD.double)))
            elif isinstance(value, str):
                # Check if it looks like a URI (for object properties)
                if value.startswith("http") or ":" in value:
                    try:
                        value_uri = URIRef(value)
                        graph.add((individual, property_uri, value_uri))
                    except:
                        # If URI parsing fails, treat as string
                        graph.add((individual, property_uri, Literal(value)))
                else:
                    graph.add((individual, property_uri, Literal(value)))
            else:
                # Default to string representation
                graph.add((individual, property_uri, Literal(str(value))))
    
    def _add_metadata_to_graph(self, graph: Graph, individual: URIRef):
        """Add metadata to the graph"""
        
        # Creation time
        created_time = Literal(datetime.now().isoformat(), datatype=XSD.dateTime)
        graph.add((individual, self.dyn.dateCreated, created_time))
        
        # Creator (could be made configurable)
        graph.add((individual, self.dyn.createdBy, Literal("DynaMat Platform")))
        
        # Version
        graph.add((individual, self.dyn.version, Literal("1.0")))
    
    # =============================================================================
    # UTILITY METHODS
    # =============================================================================
    
    def list_specimens(self) -> List[str]:
        """List all available specimens"""
        
        specimens_dir = self.database_root / "specimens"
        if not specimens_dir.exists():
            return []
        
        return [folder.name for folder in specimens_dir.iterdir() if folder.is_dir()]
    
    def get_specimen_files(self, specimen_id: str) -> Dict[str, Path]:
        """Get all TTL files for a specimen"""
        
        specimen_info = self.get_specimen(specimen_id)
        if not specimen_info:
            return {}
        
        return {file_type: info.file_path for file_type, info in specimen_info.ttl_files.items()}
    
    def cleanup_temp_files(self):
        """Clean up temporary files"""
        
        for specimen_info in self.active_specimens.values():
            for ttl_info in specimen_info.ttl_files.values():
                if ttl_info.temp_file and ttl_info.temp_file.exists():
                    try:
                        ttl_info.temp_file.unlink()
                    except:
                        pass
        
        # Clean up old temp files
        try:
            for temp_file in self.temp_dir.glob("*.ttl"):
                if temp_file.stat().st_mtime < (datetime.now().timestamp() - 86400):  # 1 day old
                    temp_file.unlink()
        except:
            pass
    
    def validate_ttl_file(self, specimen_id: str, file_type: str) -> Tuple[bool, List[str]]:
        """Validate a TTL file"""
        
        specimen_info = self.get_specimen(specimen_id)
        if not specimen_info:
            return False, [f"Specimen {specimen_id} not found"]
        
        if file_type not in specimen_info.ttl_files:
            return False, [f"File type {file_type} not found"]
        
        ttl_info = specimen_info.ttl_files[file_type]
        
        if not ttl_info.temp_file or not ttl_info.temp_file.exists():
            return False, ["No temporary file found"]
        
        try:
            # Try to parse the TTL file
            graph = Graph()
            graph.parse(str(ttl_info.temp_file), format='turtle')
            
            # Basic validation: check that main individual exists
            individual = URIRef(ttl_info.individual_uri)
            if (individual, None, None) not in graph:
                return False, ["Main individual not found in graph"]
            
            return True, []
            
        except Exception as e:
            return False, [f"TTL parsing error: {str(e)}"]


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_specimen_ttl(material_name: str, specimen_data: Dict[str, Any]) -> Path:
    """Convenience function to create a specimen TTL file"""
    
    manager = TTLFileManager()
    
    # Create specimen
    specimen_info = manager.create_specimen(material_name)
    
    # Create specimen TTL file
    ttl_info = manager.create_ttl_file(
        specimen_info.specimen_id,
        'specimen',
        'Specimen',
        specimen_data
    )
    
    # Export immediately
    return manager.export_ttl_file(specimen_info.specimen_id, 'specimen')


def create_test_ttl(specimen_id: str, test_type: str, test_data: Dict[str, Any]) -> Path:
    """Convenience function to create a test TTL file"""
    
    manager = TTLFileManager()
    
    # Create test TTL file
    ttl_info = manager.create_ttl_file(
        specimen_id,
        'test',
        test_type,
        test_data
    )
    
    # Export immediately
    return manager.export_ttl_file(specimen_id, 'test')


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

def main():
    """Example usage of TTL file manager"""
    
    # Create manager
    manager = TTLFileManager()
    
    # Create a specimen
    specimen_info = manager.create_specimen("Al6061")
    print(f"Created specimen: {specimen_info.specimen_id}")
    print(f"Specimen folder: {specimen_info.base_folder}")
    
    # Create specimen TTL file
    specimen_data = {
        "hasMaterial": "Al6061",
        "hasStructure": "Solid",
        "hasShape": "Cylindrical",
        "originalDiameter": 6.35,
        "originalLength": 6.35
    }
    
    ttl_info = manager.create_ttl_file(
        specimen_info.specimen_id,
        'specimen',
        'Specimen',
        specimen_data
    )
    
    print(f"Created specimen TTL: {ttl_info.temp_file}")
    
    # Update with more data
    additional_data = {
        "hasSpecimenRole": "TestSpecimen",
        "dateCreated": "2025-01-14"
    }
    
    manager.update_ttl_file(specimen_info.specimen_id, 'specimen', additional_data)
    print("Updated specimen TTL with additional data")
    
    # Export final file
    final_path = manager.export_ttl_file(specimen_info.specimen_id, 'specimen')
    print(f"Exported final TTL: {final_path}")
    
    # Validate
    is_valid, errors = manager.validate_ttl_file(specimen_info.specimen_id, 'specimen')
    print(f"Validation result: {'Valid' if is_valid else 'Invalid'}")
    if errors:
        print(f"Errors: {errors}")


if __name__ == "__main__":
    main()