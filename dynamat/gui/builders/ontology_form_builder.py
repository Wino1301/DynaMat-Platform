"""
DynaMat Platform - Ontology Form Builder (Refactored)
Simplified facade that orchestrates form building using specialized components
"""

import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

from PyQt6.QtWidgets import QWidget

from ...ontology import OntologyManager
from ..core.form_manager import FormManager
from .layout_manager import LayoutManager, LayoutStyle

logger = logging.getLogger(__name__)


class OntologyFormBuilder:
    """
    Simplified facade for building forms from ontology definitions.
    
    This class coordinates the specialized components to provide a clean,
    simple interface for creating ontology-based forms.
    """
    
    def __init__(self, ontology_manager: OntologyManager, 
                 default_layout: LayoutStyle = LayoutStyle.GROUPED_FORM):
        """
        Initialize the form builder.
        
        Args:
            ontology_manager: The ontology manager instance
            default_layout: Default layout style to use
        """
        self.ontology_manager = ontology_manager
        self.default_layout = default_layout
        self.logger = logging.getLogger(__name__)
        
        # Initialize specialized components
        self.form_manager = FormManager(ontology_manager)
        self.layout_manager = LayoutManager()
        
        # Optional dependency manager (will be initialized if needed)
        self.dependency_manager = None
        
        self.logger.info("Ontology form builder initialized")
    
    def build_form(self, class_uri: str, parent: Optional[QWidget] = None, 
                   layout_style: Optional[LayoutStyle] = None) -> QWidget:
        """
        Build a complete form for the given class.
        
        This is the main entry point that delegates to specialized components.
        
        Args:
            class_uri: URI of the ontology class
            parent: Parent widget (optional)
            layout_style: Layout style override (optional)
            
        Returns:
            Complete form widget ready for use
        """
        try:
            self.logger.info(f"Building form for class: {class_uri}")
            
            # Use FormManager to create the base form
            form_widget = self.form_manager.create_form(class_uri)
            
            # Set up dependencies if available
            if self.dependency_manager:
                try:
                    self.dependency_manager.setup_dependencies(form_widget, class_uri)
                    self.logger.info("Dependencies configured successfully")
                except Exception as e:
                    self.logger.error(f"Failed to setup dependencies: {e}")
            
            # Set parent if provided
            if parent:
                form_widget.setParent(parent)
            
            self.logger.info(f"Form built successfully for {class_uri}")
            return form_widget
            
        except Exception as e:
            error_msg = f"Failed to build form for {class_uri}: {e}"
            self.logger.error(error_msg, exc_info=True)
            
            # Emit error signal
            self.form_error.emit(class_uri, str(e))
            
            # Return error form
            return self._create_error_form(error_msg)
    
    def build_form_with_layout(self, class_uri: str, layout_style: LayoutStyle, 
                               parent: Optional[QWidget] = None) -> QWidget:
        """
        Build form with specific layout style.
        
        Args:
            class_uri: URI of the ontology class
            layout_style: Specific layout style to use
            parent: Parent widget (optional)
            
        Returns:
            Form widget with specified layout
        """
        return self.build_form(class_uri, parent, layout_style)
    
    def enable_dependencies(self, config_path: Optional[str] = None):
        """
        Enable dependency management for forms.
        
        Args:
            config_path: Path to dependency configuration file
        """
        try:
            from ..dependencies.dependency_manager import DependencyManager
            
            # Initialize dependency manager
            if config_path:
                self.dependency_manager = DependencyManager(self.ontology_manager, config_path)
            else:
                # Try default config path
                default_path = Path(__file__).parent.parent / "dependencies.json"
                if default_path.exists():
                    self.dependency_manager = DependencyManager(self.ontology_manager, str(default_path))
                else:
                    self.dependency_manager = DependencyManager(self.ontology_manager)
            
            self.logger.info("Dependency management enabled")
            
        except Exception as e:
            self.logger.error(f"Failed to enable dependencies: {e}")
            self.dependency_manager = None
    
    def disable_dependencies(self):
        """Disable dependency management."""
        self.dependency_manager = None
        self.logger.info("Dependency management disabled")
    
    # ============================================================================
    # FORM DATA METHODS (Delegated to FormManager)
    # ============================================================================
    
    def get_form_data(self, form_widget: QWidget) -> Dict[str, Any]:
        """
        Extract data from a form widget.
        
        Args:
            form_widget: Form widget created by this builder
            
        Returns:
            Dictionary of form data
        """
        return self.form_manager.get_form_data(form_widget)
    
    def set_form_data(self, form_widget: QWidget, data: Dict[str, Any]) -> bool:
        """
        Populate form widget with data.
        
        Args:
            form_widget: Form widget created by this builder
            data: Data to populate
            
        Returns:
            True if successful
        """
        return self.form_manager.set_form_data(form_widget, data)
    
    def validate_form(self, form_widget: QWidget) -> Dict[str, List[str]]:
        """
        Validate form data and return errors.
        
        Args:
            form_widget: Form widget created by this builder
            
        Returns:
            Dictionary mapping property URIs to lists of error messages
        """
        return self.form_manager.validate_form(form_widget)
    
    def clear_form(self, form_widget: QWidget):
        """
        Clear all form data.
        
        Args:
            form_widget: Form widget created by this builder
        """
        self.form_manager.clear_form(form_widget)
    
    def is_form_modified(self, form_widget: QWidget, original_data: Dict[str, Any]) -> bool:
        """
        Check if form has been modified from original data.
        
        Args:
            form_widget: Form widget created by this builder
            original_data: Original data to compare against
            
        Returns:
            True if form has been modified
        """
        return self.form_manager.is_form_modified(form_widget, original_data)
    
    # ============================================================================
    # LAYOUT METHODS (Delegated to LayoutManager)
    # ============================================================================
    
    def get_layout_suggestion(self, class_uri: str) -> LayoutStyle:
        """
        Get suggested layout style for a class.
        
        Args:
            class_uri: URI of the ontology class
            
        Returns:
            Suggested layout style
        """
        try:
            # Get class metadata
            class_metadata = self.ontology_manager.get_class_metadata_for_form(class_uri)
            return self.layout_manager.suggest_layout_style(class_metadata.form_groups)
            
        except Exception as e:
            self.logger.error(f"Failed to get layout suggestion for {class_uri}: {e}")
            return LayoutStyle.GROUPED_FORM
    
    def analyze_form_complexity(self, class_uri: str) -> Dict[str, Any]:
        """
        Analyze complexity of a form.
        
        Args:
            class_uri: URI of the ontology class
            
        Returns:
            Dictionary with complexity analysis
        """
        try:
            class_metadata = self.ontology_manager.get_class_metadata_for_form(class_uri)
            return self.layout_manager.analyze_form_complexity(class_metadata.form_groups)
            
        except Exception as e:
            self.logger.error(f"Failed to analyze form complexity for {class_uri}: {e}")
            return {}
    
    # ============================================================================
    # UTILITY METHODS
    # ============================================================================
    
    def _create_error_form(self, error_message: str) -> QWidget:
        """Create a form widget showing an error message."""
        return self.form_manager._create_error_form(error_message)
    
    def get_available_classes(self) -> List[str]:
        """
        Get list of available classes for form building.
        
        Returns:
            List of class URIs
        """
        try:
            return self.ontology_manager.get_all_classes()
        except Exception as e:
            self.logger.error(f"Failed to get available classes: {e}")
            return []
    
    def get_class_info(self, class_uri: str) -> Dict[str, Any]:
        """
        Get basic information about a class.
        
        Args:
            class_uri: URI of the ontology class
            
        Returns:
            Dictionary with class information
        """
        try:
            class_metadata = self.ontology_manager.get_class_metadata_for_form(class_uri)
            return {
                'uri': class_metadata.uri,
                'name': class_metadata.name,
                'label': class_metadata.label,
                'description': class_metadata.description,
                'property_count': len(class_metadata.properties),
                'group_count': len(class_metadata.form_groups),
                'is_abstract': class_metadata.is_abstract
            }
        except Exception as e:
            self.logger.error(f"Failed to get class info for {class_uri}: {e}")
            return {}
    
    def refresh_ontology(self):
        """Refresh the underlying ontology data."""
        try:
            self.ontology_manager.clear_caches()
            self.logger.info("Ontology data refreshed")
        except Exception as e:
            self.logger.error(f"Failed to refresh ontology: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the form builder.
        
        Returns:
            Dictionary with statistics
        """
        try:
            ontology_stats = self.ontology_manager.get_statistics()
            return {
                'ontology_stats': ontology_stats,
                'default_layout': self.default_layout.value,
                'dependencies_enabled': self.dependency_manager is not None,
                'available_layouts': [style.value for style in LayoutStyle]
            }
        except Exception as e:
            self.logger.error(f"Failed to get statistics: {e}")
            return {}