"""
DynaMat Platform - Template Manager
Manages configuration templates for pre-filling GUI forms and common setups
"""

import logging
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime
from dataclasses import dataclass

import rdflib
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL, XSD

from .manager import OntologyManager
from ..config import config


logger = logging.getLogger(__name__)


@dataclass
class TemplateMetadata:
    """Metadata for a configuration template"""
    name: str
    description: str
    category: str
    version: str
    target_class: str
    author: str
    created_date: str
    last_modified: str
    tags: List[str]
    file_path: str


class TemplateManager:
    """
    Manages configuration templates for common DynaMat setups.
    
    Templates are TTL files that contain default property values and
    configurations for frequent use cases like standard SHPB setups,
    common material property sets, etc.
    """
    
    def __init__(self, ontology_manager: OntologyManager, template_dir: Optional[Path] = None):
        """
        Initialize the template manager.
        
        Args:
            ontology_manager: Main ontology manager instance
            template_dir: Path to templates directory, defaults to config.TEMPLATE_DIR
        """
        self.manager = ontology_manager
        self.template_dir = template_dir or config.TEMPLATE_DIR
        
        # Ensure template directory structure exists
        self._ensure_template_structure()
        
        # Template cache
        self.template_cache = {}  # template_path -> (metadata, graph)
        self.metadata_cache = {}  # category -> list of metadata
        
        # Setup namespaces
        self.DYN = self.manager.DYN
        self.TEMPLATE = Namespace("https://dynamat.utep.edu/templates/")
        
        # Load all templates
        self._load_all_templates()
        
        logger.info(f"Template manager initialized with {len(self.template_cache)} templates")
    
    def _ensure_template_structure(self):
        """Create the template directory structure if it doesn't exist."""
        categories = ["equipment", "materials", "structures", "processes", "tests"]
        
        self.template_dir.mkdir(exist_ok=True)
        
        for category in categories:
            category_dir = self.template_dir / category
            category_dir.mkdir(exist_ok=True)
            
            # Create a README if it doesn't exist
            readme_file = category_dir / "README.md"
            if not readme_file.exists():
                with readme_file.open("w") as f:
                    f.write(f"# {category.title()} Templates\n\n")
                    f.write(f"This directory contains {category} configuration templates.\n\n")
                    f.write("## Template Structure\n\n")
                    f.write("Each template should include:\n")
                    f.write("- Template metadata (name, description, etc.)\n")
                    f.write("- Default property values\n")
                    f.write("- Target class information\n\n")
    
    def _load_all_templates(self):
        """Load all template files from the template directory."""
        template_files = list(self.template_dir.rglob("*.ttl"))
        
        for template_file in template_files:
            try:
                self._load_template_file(template_file)
            except Exception as e:
                logger.warning(f"Failed to load template {template_file}: {e}")
        
        logger.info(f"Loaded {len(template_files)} template files")
    
    def _load_template_file(self, template_file: Path):
        """Load a single template file and extract metadata."""
        graph = Graph()
        
        # Bind namespaces
        for prefix, namespace in self.manager.namespaces.items():
            graph.bind(prefix, namespace)
        graph.bind("template", self.TEMPLATE)
        
        # Parse the template file
        graph.parse(template_file, format="turtle")
        
        # Extract template metadata
        metadata = self._extract_template_metadata(graph, template_file)
        
        # Cache the template
        template_key = str(template_file.relative_to(self.template_dir))
        self.template_cache[template_key] = (metadata, graph)
        
        # Update category cache
        category = metadata.category
        if category not in self.metadata_cache:
            self.metadata_cache[category] = []
        self.metadata_cache[category].append(metadata)
    
    def _extract_template_metadata(self, graph: Graph, template_file: Path) -> TemplateMetadata:
        """Extract metadata from a template graph."""
        # Look for template metadata in the graph
        template_query = """
        SELECT ?template ?name ?description ?category ?version ?targetClass 
               ?author ?created ?modified ?tags WHERE {
            ?template rdf:type dyn:Template .
            OPTIONAL { ?template dyn:hasName ?name }
            OPTIONAL { ?template dyn:hasDescription ?description }
            OPTIONAL { ?template dyn:hasCategory ?category }
            OPTIONAL { ?template dyn:hasVersion ?version }
            OPTIONAL { ?template dyn:hasTargetClass ?targetClass }
            OPTIONAL { ?template dyn:hasAuthor ?author }
            OPTIONAL { ?template dyn:hasCreatedDate ?created }
            OPTIONAL { ?template dyn:hasLastModified ?modified }
            OPTIONAL { ?template dyn:hasTags ?tags }
        }
        """
        
        results = list(graph.query(template_query))
        
        if results:
            row = results[0]
            
            # Parse tags if present
            tags = []
            if row.tags:
                tags = [tag.strip() for tag in str(row.tags).split(",")]
            
            return TemplateMetadata(
                name=str(row.name) if row.name else template_file.stem,
                description=str(row.description) if row.description else "",
                category=str(row.category) if row.category else self._infer_category(template_file),
                version=str(row.version) if row.version else "1.0",
                target_class=str(row.targetClass) if row.targetClass else "",
                author=str(row.author) if row.author else "",
                created_date=str(row.created) if row.created else "",
                last_modified=str(row.modified) if row.modified else "",
                tags=tags,
                file_path=str(template_file)
            )
        else:
            # No explicit metadata, infer from file structure
            return TemplateMetadata(
                name=template_file.stem.replace("_", " ").title(),
                description=f"Template for {template_file.stem}",
                category=self._infer_category(template_file),
                version="1.0",
                target_class="",
                author="",
                created_date="",
                last_modified="",
                tags=[],
                file_path=str(template_file)
            )
    
    def _infer_category(self, template_file: Path) -> str:
        """Infer template category from file path."""
        parts = template_file.parts
        for part in parts:
            if part in ["equipment", "materials", "structures", "processes", "tests"]:
                return part
        return "general"
    
    def get_available_templates(self, category: Optional[str] = None) -> List[TemplateMetadata]:
        """
        Get list of available templates.
        
        Args:
            category: Filter by category, returns all if None
            
        Returns:
            List of template metadata
        """
        if category:
            return self.metadata_cache.get(category, [])
        else:
            all_templates = []
            for category_templates in self.metadata_cache.values():
                all_templates.extend(category_templates)
            return all_templates
    
    def get_template_categories(self) -> List[str]:
        """Get list of available template categories."""
        return list(self.metadata_cache.keys())
    
    def load_template(self, template_name_or_path: str) -> Tuple[TemplateMetadata, Dict[str, Any]]:
        """
        Load a template and return its metadata and property values.
        
        Args:
            template_name_or_path: Template name or file path
            
        Returns:
            Tuple of (metadata, property_values_dict)
        """
        # Find the template
        template_key = None
        
        if template_name_or_path in self.template_cache:
            template_key = template_name_or_path
        else:
            # Search by name
            for key, (metadata, graph) in self.template_cache.items():
                if metadata.name == template_name_or_path:
                    template_key = key
                    break
        
        if not template_key:
            raise ValueError(f"Template not found: {template_name_or_path}")
        
        metadata, graph = self.template_cache[template_key]
        
        # Extract property values from the template
        property_values = self._extract_template_values(graph)
        
        return metadata, property_values
    
    def _extract_template_values(self, graph: Graph) -> Dict[str, Any]:
        """Extract property values from a template graph."""
        values = {}
        
        # Look for template instance with default values
        template_query = """
        SELECT ?property ?value WHERE {
            ?templateInstance dyn:hasDefaultValue ?defaultValue .
            ?defaultValue dyn:hasProperty ?property .
            ?defaultValue dyn:hasValue ?value .
        }
        """
        
        results = list(graph.query(template_query))
        
        for row in results:
            property_uri = str(row.property)
            value = self._convert_from_rdf_value(row.value)
            
            # Use local name as key for easier access
            property_name = self.manager._extract_local_name(property_uri)
            values[property_name] = value
            values[property_uri] = value  # Also store full URI
        
        # If no explicit default values, extract all property-value pairs
        if not values:
            instance_query = """
            SELECT ?instance ?property ?value WHERE {
                ?instance rdf:type ?class .
                ?instance ?property ?value .
                FILTER(?property != rdf:type)
                FILTER(?property != dyn:hasName)
                FILTER(?property != dyn:hasDescription)
            }
            """
            
            results = list(graph.query(instance_query))
            
            for row in results:
                property_uri = str(row.property)
                value = self._convert_from_rdf_value(row.value)
                
                property_name = self.manager._extract_local_name(property_uri)
                
                # Handle multiple values for the same property
                if property_name in values:
                    if not isinstance(values[property_name], list):
                        values[property_name] = [values[property_name]]
                    values[property_name].append(value)
                else:
                    values[property_name] = value
                
                # Also store with full URI
                if property_uri in values:
                    if not isinstance(values[property_uri], list):
                        values[property_uri] = [values[property_uri]]
                    values[property_uri].append(value)
                else:
                    values[property_uri] = value
        
        return values
    
    def apply_template(self, template_name_or_path: str, instance_uri: str, 
                      override_values: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Apply a template to an instance, returning the combined property values.
        
        Args:
            template_name_or_path: Template to apply
            instance_uri: Target instance URI
            override_values: Values to override template defaults
            
        Returns:
            Dictionary of final property values
        """
        # Load the template
        metadata, template_values = self.load_template(template_name_or_path)
        
        # Start with template values
        final_values = template_values.copy()
        
        # Apply overrides
        if override_values:
            for key, value in override_values.items():
                final_values[key] = value
        
        # Add instance URI
        final_values["uri"] = instance_uri
        final_values["applied_template"] = metadata.name
        final_values["template_applied_date"] = datetime.now().isoformat()
        
        logger.info(f"Applied template '{metadata.name}' to instance {instance_uri}")
        return final_values
    
    def save_template(self, template_name: str, category: str, target_class: str,
                     property_values: Dict[str, Any], 
                     metadata: Optional[Dict[str, str]] = None) -> str:
        """
        Save a new template.
        
        Args:
            template_name: Name of the template
            category: Template category
            target_class: Target class URI
            property_values: Property values to save
            metadata: Additional metadata
            
        Returns:
            Path to saved template file
        """
        # Create template file path
        safe_name = template_name.lower().replace(" ", "_").replace("-", "_")
        template_file = self.template_dir / category / f"{safe_name}.ttl"
        
        # Ensure category directory exists
        template_file.parent.mkdir(exist_ok=True)
        
        # Create template graph
        graph = Graph()
        
        # Bind namespaces
        for prefix, namespace in self.manager.namespaces.items():
            graph.bind(prefix, namespace)
        graph.bind("template", self.TEMPLATE)
        
        # Create template metadata
        template_uri = self.TEMPLATE[safe_name]
        
        graph.add((template_uri, RDF.type, self.DYN.Template))
        graph.add((template_uri, self.DYN.hasName, Literal(template_name)))
        graph.add((template_uri, self.DYN.hasCategory, Literal(category)))
        graph.add((template_uri, self.DYN.hasTargetClass, URIRef(target_class)))
        graph.add((template_uri, self.DYN.hasCreatedDate, Literal(datetime.now().isoformat(), datatype=XSD.dateTime)))
        graph.add((template_uri, self.DYN.hasVersion, Literal("1.0")))
        
        # Add optional metadata
        if metadata:
            if "description" in metadata:
                graph.add((template_uri, self.DYN.hasDescription, Literal(metadata["description"])))
            if "author" in metadata:
                graph.add((template_uri, self.DYN.hasAuthor, Literal(metadata["author"])))
            if "tags" in metadata:
                graph.add((template_uri, self.DYN.hasTags, Literal(metadata["tags"])))
        
        # Create example instance with property values
        example_uri = self.TEMPLATE[f"{safe_name}_example"]
        graph.add((example_uri, RDF.type, URIRef(target_class)))
        graph.add((example_uri, RDF.type, OWL.NamedIndividual))
        
        # Add property values
        for property_name, value in property_values.items():
            if property_name.startswith("http"):
                property_uri = property_name
            else:
                property_uri = str(self.DYN[property_name])
            
            if value is not None and value != "":
                rdf_value = self._convert_to_rdf_value(value)
                graph.add((example_uri, URIRef(property_uri), rdf_value))
        
        # Save to file
        with template_file.open("w", encoding="utf-8") as f:
            f.write(graph.serialize(format="turtle").decode("utf-8"))
        
        # Reload template cache
        self._load_template_file(template_file)
        
        logger.info(f"Saved template '{template_name}' to {template_file}")
        return str(template_file)
    
    def delete_template(self, template_name_or_path: str) -> bool:
        """
        Delete a template.
        
        Args:
            template_name_or_path: Template to delete
            
        Returns:
            True if deletion was successful
        """
        # Find the template
        template_key = None
        
        if template_name_or_path in self.template_cache:
            template_key = template_name_or_path
        else:
            # Search by name
            for key, (metadata, graph) in self.template_cache.items():
                if metadata.name == template_name_or_path:
                    template_key = key
                    break
        
        if not template_key:
            logger.warning(f"Template not found for deletion: {template_name_or_path}")
            return False
        
        metadata, graph = self.template_cache[template_key]
        template_file = Path(metadata.file_path)
        
        try:
            # Remove file
            if template_file.exists():
                template_file.unlink()
            
            # Remove from cache
            del self.template_cache[template_key]
            
            # Update metadata cache
            if metadata.category in self.metadata_cache:
                self.metadata_cache[metadata.category] = [
                    m for m in self.metadata_cache[metadata.category] 
                    if m.file_path != metadata.file_path
                ]
            
            logger.info(f"Deleted template '{metadata.name}'")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete template '{metadata.name}': {e}")
            return False
    
    def search_templates(self, query: str, category: Optional[str] = None) -> List[TemplateMetadata]:
        """
        Search templates by name, description, or tags.
        
        Args:
            query: Search query
            category: Optional category filter
            
        Returns:
            List of matching templates
        """
        query_lower = query.lower()
        matches = []
        
        templates = self.get_available_templates(category)
        
        for template in templates:
            # Check name
            if query_lower in template.name.lower():
                matches.append(template)
                continue
            
            # Check description
            if query_lower in template.description.lower():
                matches.append(template)
                continue
            
            # Check tags
            if any(query_lower in tag.lower() for tag in template.tags):
                matches.append(template)
                continue
        
        return matches
    
    def get_template_usage_stats(self) -> Dict[str, Any]:
        """Get statistics about template usage and availability."""
        stats = {}
        
        # Count by category
        stats["by_category"] = {}
        for category, templates in self.metadata_cache.items():
            stats["by_category"][category] = len(templates)
        
        # Total count
        stats["total_templates"] = len(self.template_cache)
        
        # Most recent templates
        all_templates = self.get_available_templates()
        recent_templates = sorted(all_templates, 
                                key=lambda t: t.last_modified or t.created_date, 
                                reverse=True)[:5]
        stats["recent_templates"] = [t.name for t in recent_templates]
        
        return stats
    
    def _convert_to_rdf_value(self, value: Any) -> Union[URIRef, Literal]:
        """Convert Python value to appropriate RDF value."""
        if isinstance(value, str):
            if value.startswith("http"):
                return URIRef(value)
            else:
                return Literal(value)
        elif isinstance(value, bool):
            return Literal(value, datatype=XSD.boolean)
        elif isinstance(value, int):
            return Literal(value, datatype=XSD.integer)
        elif isinstance(value, float):
            return Literal(value, datatype=XSD.double)
        elif hasattr(value, 'isoformat'):  # datetime/date
            return Literal(value.isoformat(), datatype=XSD.dateTime)
        else:
            return Literal(str(value))
    
    def _convert_from_rdf_value(self, rdf_value: Union[URIRef, Literal]) -> Any:
        """Convert RDF value to appropriate Python value."""
        if isinstance(rdf_value, URIRef):
            return str(rdf_value)
        elif isinstance(rdf_value, Literal):
            if rdf_value.datatype == XSD.boolean:
                return bool(rdf_value)
            elif rdf_value.datatype == XSD.integer:
                return int(rdf_value)
            elif rdf_value.datatype == XSD.double:
                return float(rdf_value)
            elif rdf_value.datatype in (XSD.dateTime, XSD.date):
                return str(rdf_value)
            else:
                return str(rdf_value)
        else:
            return str(rdf_value)