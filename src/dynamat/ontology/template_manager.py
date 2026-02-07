"""
DynaMat Platform - Template Manager
Manages configuration templates for pre-filling GUI forms and common setups
Clean implementation using new architecture
"""

import logging
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime
from dataclasses import dataclass

from rdflib import Graph, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL, XSD

from .core.namespace_manager import NamespaceManager
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
    
    def __init__(self, namespace_manager: NamespaceManager, template_dir: Optional[Path] = None):
        """
        Initialize the template manager.
        
        Args:
            namespace_manager: Namespace manager for URI handling
            template_dir: Path to templates directory
        """
        self.ns_manager = namespace_manager
        self.template_dir = template_dir or config.TEMPLATE_DIR
        
        # Template namespace
        self.TEMPLATE = self.ns_manager.get_namespace('dyn')  # Use DYN for templates
        
        # Ensure template directory structure exists
        self._ensure_template_structure()
        
        # Template cache
        self.template_cache = {}  # template_path -> (metadata, graph)
        self.metadata_cache = {}  # category -> list of metadata
        
        # Load all templates
        self._load_all_templates()
        
        logger.info(f"Template manager initialized with {len(self.template_cache)} templates")
    
    def _ensure_template_structure(self):
        """Create the template directory structure if it doesn't exist."""
        categories = ["equipment", "materials", "structures", "processes", "tests"]
        
        self.template_dir.mkdir(parents=True, exist_ok=True)
        
        for category in categories:
            category_dir = self.template_dir / category
            category_dir.mkdir(exist_ok=True)
            
            # Create a README if it doesn't exist
            readme_file = category_dir / "README.md"
            if not readme_file.exists():
                self._create_category_readme(readme_file, category)
    
    def _create_category_readme(self, readme_file: Path, category: str):
        """Create a README file for a template category."""
        content = f"""# {category.title()} Templates

This directory contains {category} configuration templates.

## Template Structure

Each template should include:
- Template metadata (name, description, etc.)
- Default property values
- Target class information

## Usage

Templates can be loaded and applied to new instances to provide
default configurations for common {category} setups.
"""
        readme_file.write_text(content)
    
    def _load_all_templates(self):
        """Load all template files from the template directory."""
        template_files = list(self.template_dir.rglob("*.ttl"))
        
        loaded_count = 0
        for template_file in template_files:
            try:
                self._load_template_file(template_file)
                loaded_count += 1
            except Exception as e:
                logger.warning(f"Failed to load template {template_file}: {e}")
        
        logger.info(f"Loaded {loaded_count} template files")
    
    def _load_template_file(self, template_file: Path):
        """Load a single template file and extract metadata."""
        graph = Graph()
        
        # Bind namespaces
        self.ns_manager.setup_graph_namespaces(graph)
        
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
        template_query = f"""
        SELECT ?template ?name ?description ?category ?version ?targetClass 
               ?author ?created ?modified WHERE {{
            ?template rdf:type dyn:Template .
            OPTIONAL {{ ?template dyn:hasName ?name }}
            OPTIONAL {{ ?template dyn:hasDescription ?description }}
            OPTIONAL {{ ?template dyn:hasCategory ?category }}
            OPTIONAL {{ ?template dyn:hasVersion ?version }}
            OPTIONAL {{ ?template dyn:hasTargetClass ?targetClass }}
            OPTIONAL {{ ?template dyn:hasAuthor ?author }}
            OPTIONAL {{ ?template dyn:hasCreatedDate ?created }}
            OPTIONAL {{ ?template dyn:hasModifiedDate ?modified }}
        }}
        """
        
        # Execute query manually since we don't have SPARQL executor here
        results = []
        for subj, pred, obj in graph:
            if pred == RDF.type and obj == self.ns_manager.DYN.Template:
                template_uri = subj
                # Extract metadata properties
                metadata_result = {'template': str(template_uri)}
                
                for prop, val in graph.predicate_objects(template_uri):
                    prop_name = str(prop).split('#')[-1] if '#' in str(prop) else str(prop).split('/')[-1]
                    if prop_name.startswith('has'):
                        prop_name = prop_name[3:].lower()
                    metadata_result[prop_name] = str(val)
                
                results.append(metadata_result)
                break
        
        if results:
            result = results[0]
            # Extract tags if they exist
            tags = []
            tag_pred = self.ns_manager.DYN.hasTag
            for obj in graph.objects(URIRef(result['template']), tag_pred):
                tags.append(str(obj))
            
            return TemplateMetadata(
                name=result.get('name', template_file.stem),
                description=result.get('description', ''),
                category=result.get('category', 'general'),
                version=result.get('version', '1.0'),
                target_class=result.get('targetclass', ''),
                author=result.get('author', ''),
                created_date=result.get('createddate', ''),
                last_modified=result.get('modifieddate', ''),
                tags=tags,
                file_path=str(template_file)
            )
        else:
            # Fallback metadata from file info
            return TemplateMetadata(
                name=template_file.stem,
                description=f"Template from {template_file.name}",
                category=template_file.parent.name,
                version="1.0",
                target_class="",
                author="",
                created_date=datetime.fromtimestamp(template_file.stat().st_ctime).isoformat(),
                last_modified=datetime.fromtimestamp(template_file.stat().st_mtime).isoformat(),
                tags=[],
                file_path=str(template_file)
            )
    
    def get_available_templates(self, category: Optional[str] = None) -> List[TemplateMetadata]:
        """
        Get list of available templates.
        
        Args:
            category: Optional category filter
            
        Returns:
            List of template metadata
        """
        if category:
            return self.metadata_cache.get(category, [])
        else:
            all_templates = []
            for templates in self.metadata_cache.values():
                all_templates.extend(templates)
            return all_templates
    
    def get_template_categories(self) -> List[str]:
        """Get list of available template categories."""
        return list(self.metadata_cache.keys())
    
    def load_template(self, template_name_or_path: str) -> Tuple[TemplateMetadata, Dict[str, Any]]:
        """
        Load a template and return its metadata and values.
        
        Args:
            template_name_or_path: Template name or file path
            
        Returns:
            Tuple of (metadata, template_values)
        """
        # Find the template
        template_key = None
        metadata = None
        graph = None
        
        # First try direct path lookup
        if template_name_or_path in self.template_cache:
            template_key = template_name_or_path
            metadata, graph = self.template_cache[template_key]
        else:
            # Search by name
            for key, (tmpl_metadata, tmpl_graph) in self.template_cache.items():
                if tmpl_metadata.name == template_name_or_path:
                    template_key = key
                    metadata = tmpl_metadata
                    graph = tmpl_graph
                    break
        
        if not template_key:
            raise ValueError(f"Template not found: {template_name_or_path}")
        
        # Extract template values
        template_values = self._extract_template_values(graph, metadata)
        
        return metadata, template_values
    
    def _extract_template_values(self, graph: Graph, metadata: TemplateMetadata) -> Dict[str, Any]:
        """Extract property values from a template graph."""
        values = {}
        
        # Find template instances
        for subj in graph.subjects(RDF.type, self.ns_manager.DYN.Template):
            # Get all properties of this template
            for pred, obj in graph.predicate_objects(subj):
                pred_name = str(pred).split('#')[-1] if '#' in str(pred) else str(pred).split('/')[-1]
                
                # Skip metadata properties
                if pred_name.startswith('has') and pred_name[3:].lower() in [
                    'name', 'description', 'category', 'version', 'targetclass', 
                    'author', 'createddate', 'modifieddate', 'tag'
                ]:
                    continue
                
                # Convert RDF value to Python value
                if isinstance(obj, URIRef):
                    values[pred_name] = str(obj)
                elif isinstance(obj, Literal):
                    values[pred_name] = obj.toPython()
                else:
                    values[pred_name] = str(obj)
        
        return values
    
    def apply_template(self, template_name_or_path: str, instance_uri: str, 
                      override_values: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Apply a template to an instance URI with optional value overrides.
        
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
            final_values.update(override_values)
        
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
        template_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Create template graph
        graph = Graph()
        self.ns_manager.setup_graph_namespaces(graph)
        
        # Create template metadata
        template_uri = self.ns_manager.DYN[safe_name]
        
        graph.add((template_uri, RDF.type, self.ns_manager.DYN.Template))
        graph.add((template_uri, self.ns_manager.DYN.hasName, Literal(template_name)))
        graph.add((template_uri, self.ns_manager.DYN.hasCategory, Literal(category)))
        graph.add((template_uri, self.ns_manager.DYN.hasTargetClass, URIRef(target_class)))
        graph.add((template_uri, self.ns_manager.DYN.hasVersion, Literal("1.0")))
        graph.add((template_uri, self.ns_manager.DYN.hasCreatedDate, 
                  Literal(datetime.now().isoformat())))
        
        # Add additional metadata
        if metadata:
            for key, value in metadata.items():
                if hasattr(self.ns_manager.DYN, f'has{key.title()}'):
                    prop = getattr(self.ns_manager.DYN, f'has{key.title()}')
                    graph.add((template_uri, prop, Literal(value)))
        
        # Add property values
        for prop_name, value in property_values.items():
            if prop_name.startswith('http'):
                prop_uri = URIRef(prop_name)
            else:
                prop_uri = self.ns_manager.DYN[prop_name]
            
            if isinstance(value, str) and value.startswith('http'):
                graph.add((template_uri, prop_uri, URIRef(value)))
            else:
                graph.add((template_uri, prop_uri, Literal(value)))
        
        # Save to file
        with template_file.open("w", encoding="utf-8") as f:
            f.write(graph.serialize(format="turtle"))
        
        # Reload templates to update cache
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
        metadata = None
        
        if template_name_or_path in self.template_cache:
            template_key = template_name_or_path
            metadata, _ = self.template_cache[template_key]
        else:
            # Search by name
            for key, (tmpl_metadata, _) in self.template_cache.items():
                if tmpl_metadata.name == template_name_or_path:
                    template_key = key
                    metadata = tmpl_metadata
                    break
        
        if not template_key:
            logger.warning(f"Template not found for deletion: {template_name_or_path}")
            return False
        
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
        total_templates = sum(len(templates) for templates in self.metadata_cache.values())
        
        return {
            'total_templates': total_templates,
            'categories': list(self.metadata_cache.keys()),
            'templates_by_category': {cat: len(templates) for cat, templates in self.metadata_cache.items()},
            'template_directory': str(self.template_dir)
        }
    
    def reload_templates(self):
        """Reload all templates from disk."""
        self.template_cache.clear()
        self.metadata_cache.clear()
        self._load_all_templates()
        logger.info("Templates reloaded from disk")