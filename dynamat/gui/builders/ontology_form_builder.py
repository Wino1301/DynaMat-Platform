"""
DynaMat Platform - Ontology Form Builder (Refactored)
Simplified facade that orchestrates form building using specialized components
"""

import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

from PyQt6.QtWidgets import QWidget

from ...ontology import OntologyManager
from ..core.form_manager import FormManager, FormStyle
from ..dependencies.dependency_manager import DependencyManager

logger = logging.getLogger(__name__)


class OntologyFormBuilder:
    """
    Simplified facade for building forms from ontology classes.
    
    This is the main entry point for GUI components that need to create forms.
    It orchestrates the specialized components:
    - FormManager: Coordinates form creation
    - DependencyManager: Handles form field dependencies
    """
    
    def __init__(self, ontology_manager: OntologyManager, 
                 dependency_config: Optional[str] = None):
        """
        Initialize the form builder.
        
        Args:
            ontology_manager: Ontology manager instance
            dependency_config: Path to dependency configuration file
        """
        self.ontology_manager = ontology_manager
        self.logger = logging.getLogger(__name__)
        
        # Initialize core components
        self.form_manager = FormManager(ontology_manager)
        
        # Initialize dependency manager
        self.dependency_manager = None
        self._setup_dependency_manager(dependency_config)
        
        self.logger.info("Ontology form builder initialized")
    
    def _setup_dependency_manager(self, dependency_config: Optional[str]):
        """Setup the dependency manager with proper error handling."""
        try:
            if dependency_config is not None:
                self.dependency_manager = DependencyManager(
                    self.ontology_manager, dependency_config
                )
                self.logger.info("Dependency manager initialized with custom config")
            else:
                # Try to find default config
                default_config = self._find_default_dependency_config()
                if default_config and default_config.exists():
                    self.dependency_manager = DependencyManager(
                        self.ontology_manager, str(default_config)
                    )
                    self.logger.info("Dependency manager initialized with default config")
                else:
                    self.dependency_manager = DependencyManager(self.ontology_manager)
                    self.logger.info("Dependency manager initialized without config")
        except Exception as e:
            self.logger.error(f"Failed to initialize dependency manager: {e}")
            self.dependency_manager = None
    
    def _find_default_dependency_config(self) -> Optional[Path]:
        """Find default dependency configuration file."""
        # Look for dependencies.json in gui directory
        gui_dir = Path(__file__).parent.parent
        config_path = gui_dir / "dependencies.json"
        
        if config_path.exists():
            return config_path
        
        # Look for it in the dependencies directory
        dep_config_path = gui_dir / "dependencies" / "dependencies.json"
        if dep_config_path.exists():
            return dep_config_path
        
        return None
    
    # ============================================================================
    # MAIN FORM BUILDING INTERFACE
    # ============================================================================
    
    def build_form(self, class_uri: str, 
                  parent: Optional[QWidget] = None,
                  style: FormStyle = FormStyle.GROUPED) -> QWidget:
        """
        Build a complete form for the given class.
        
        This is the main entry point used by GUI components.
        
        Args:
            class_uri: URI of the ontology class
            parent: Parent widget
            style: Form layout style
            
        Returns:
            Complete form widget with dependencies configured
        """
        try:
            self.logger.info(f"Building form for class: {class_uri}")
            
            # Create form using form manager
            form_widget = self.form_manager.create_form(
                class_uri, style=style, parent=parent
            )
            
            if not form_widget:
                self.logger.error("Form manager returned no widget")
                return self._create_error_widget("Form creation failed")
            
            # Setup dependencies if available
            if self.dependency_manager:
                try:
                    self.logger.debug("Setting up form dependencies...")
                    self.dependency_manager.setup_dependencies(form_widget, class_uri)
                    self.logger.debug("Dependencies configured successfully")
                except Exception as e:
                    self.logger.error(f"Failed to setup dependencies: {e}")
                    # Continue without dependencies rather than failing
            else:
                self.logger.info("No dependency manager available")
            
            # Add form builder reference to widget
            form_widget.form_builder = self
            
            self.logger.info(f"Successfully built form for {class_uri}")
            return form_widget
            
        except Exception as e:
            self.logger.error(f"Failed to build form for {class_uri}: {e}", exc_info=True)
            return self._create_error_widget(f"Error building form: {str(e)}")
    
    def build_form_with_style(self, class_uri: str,
                            style: str,
                            parent: Optional[QWidget] = None) -> QWidget:
        """
        Build form with style specified as string.
        
        Args:
            class_uri: URI of the ontology class
            style: Style name ('grouped', 'simple', 'two_column', 'tabbed')
            parent: Parent widget
            
        Returns:
            Complete form widget
        """
        try:
            # Convert string to FormStyle enum
            form_style = FormStyle(style.lower())
        except ValueError:
            self.logger.warning(f"Unknown form style: {style}, using grouped")
            form_style = FormStyle.GROUPED
        
        return self.build_form(class_uri, parent, form_style)
    
    # ============================================================================
    # FORM DATA OPERATIONS
    # ============================================================================
    
    def get_form_data(self, form_widget: QWidget) -> Dict[str, Any]:
        """
        Extract data from a form created by this builder.
        
        Args:
            form_widget: Form widget
            
        Returns:
            Dictionary of form data
        """
        return self.form_manager.get_form_data(form_widget)
    
    def populate_form(self, form_widget: QWidget, data: Dict[str, Any]) -> bool:
        """
        Populate form with data.
        
        Args:
            form_widget: Form widget
            data: Dictionary of data to populate
            
        Returns:
            True if successful
        """
        return self.form_manager.set_form_data(form_widget, data)
    
    def validate_form(self, form_widget: QWidget) -> Dict[str, List[str]]:
        """
        Validate form data.
        
        Args:
            form_widget: Form widget to validate
            
        Returns:
            Dictionary of validation errors (empty if valid)
        """
        return self.form_manager.validate_form(form_widget)
    
    def clear_form(self, form_widget: QWidget) -> bool:
        """
        Clear all form data.
        
        Args:
            form_widget: Form widget to clear
            
        Returns:
            True if successful
        """
        return self.form_manager.clear_form(form_widget)
    
    def is_form_valid(self, form_widget: QWidget) -> bool:
        """
        Check if form is valid.
        
        Args:
            form_widget: Form widget to check
            
        Returns:
            True if form is valid
        """
        errors = self.validate_form(form_widget)
        return len(errors) == 0
    
    # ============================================================================
    # FORM MANAGEMENT
    # ============================================================================
    
    def reload_form(self, form_widget: QWidget) -> QWidget:
        """
        Reload a form (useful after ontology changes).
        
        Args:
            form_widget: Existing form widget
            
        Returns:
            New form widget
        """
        return self.form_manager.reload_form(form_widget)
    
    def get_form_info(self, form_widget: QWidget) -> Dict[str, Any]:
        """
        Get information about a form.
        
        Args:
            form_widget: Form widget
            
        Returns:
            Dictionary with form information
        """
        info = self.form_manager.get_form_summary(form_widget)
        
        # Add builder-specific information
        info.update({
            'has_dependencies': self.dependency_manager is not None,
            'builder_type': 'OntologyFormBuilder'
        })
        
        return info
    
    # ============================================================================
    # CACHE MANAGEMENT
    # ============================================================================
    
    def clear_cache(self):
        """Clear all caches."""
        self.form_manager.clear_cache()
        if self.dependency_manager:
            # Clear dependency manager cache if it has one
            pass
        self.logger.info("Form builder caches cleared")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache information."""
        info = self.form_manager.get_cache_info()
        info['dependency_manager_available'] = self.dependency_manager is not None
        return info
    
    # ============================================================================
    # UTILITY METHODS
    # ============================================================================
    
    def _create_error_widget(self, message: str) -> QWidget:
        """Create an error display widget."""
        from PyQt6.QtWidgets import QLabel
        
        error_widget = QLabel(f"Form Builder Error:\n\n{message}\n\nCheck logs for details.")
        error_widget.setStyleSheet(
            "color: red; padding: 20px; background-color: #2a1a1a; "
            "border: 1px solid red; border-radius: 5px;"
        )
        error_widget.setWordWrap(True)
        return error_widget
    
    def get_available_classes(self) -> List[str]:
        """
        Get list of available ontology classes.
        
        Returns:
            List of class URIs
        """
        try:
            return self.ontology_manager.get_all_classes()
        except Exception as e:
            self.logger.error(f"Error getting available classes: {e}")
            return []
    
    def get_class_info(self, class_uri: str) -> Dict[str, Any]:
        """
        Get information about a class.
        
        Args:
            class_uri: Class URI
            
        Returns:
            Dictionary with class information
        """
        try:
            metadata = self.ontology_manager.get_class_metadata_for_form(class_uri)
            return {
                'uri': metadata.uri,
                'name': metadata.name,
                'label': metadata.label,
                'description': metadata.description,
                'property_count': len(metadata.properties),
                'group_count': len(metadata.form_groups),
                'is_abstract': metadata.is_abstract
            }
        except Exception as e:
            self.logger.error(f"Error getting class info for {class_uri}: {e}")
            return {'uri': class_uri, 'error': str(e)}
    
    # ============================================================================
    # DEPRECATED METHODS (for backward compatibility)
    # ============================================================================
    
    def build_form_group(self, group_name: str, properties: List, widgets: Dict) -> QWidget:
        """
        Deprecated: Use form_manager directly for advanced operations.
        """
        self.logger.warning("build_form_group is deprecated, use form_manager directly")
        return self.form_manager.layout_manager._create_group_widget(
            group_name, properties, widgets
        )[0]
    
    def create_widget_for_property(self, property_metadata) -> QWidget:
        """
        Deprecated: Use form_manager.widget_factory directly.
        """
        self.logger.warning("create_widget_for_property is deprecated, use widget_factory directly")
        return self.form_manager.widget_factory.create_widget(property_metadata)