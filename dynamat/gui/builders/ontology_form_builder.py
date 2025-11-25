"""
DynaMat Platform - Ontology Form Builder (Refactored)
Simplified facade that orchestrates form building using specialized components
"""

import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal, Qt
from PyQt6.QtWidgets import QWidget, QLabel

from ...ontology import OntologyManager
from ..core.form_manager import FormManager
from .layout_manager import LayoutManager, LayoutStyle

logger = logging.getLogger(__name__)


class OntologyFormBuilder(QObject):
    """
    Simplified facade for building forms from ontology definitions.
    
    This class coordinates the specialized components to provide a clean,
    simple interface for creating ontology-based forms.
    """
    
    # Define signals
    form_error = pyqtSignal(str, str)  # class_uri, error_message
    form_created = pyqtSignal(str)     # class_uri    
    
    def __init__(self, ontology_manager, default_layout=LayoutStyle.GROUPED_FORM, constraint_dir: Optional[Path] = None):
        super().__init__() 
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

        # Statistics tracking (always-on)
        self._forms_created_count = {}  # class_uri -> count
        self._form_errors = {}  # class_uri -> error_count
        self._layout_usage = {}  # layout_style -> count

        # Initialize constraint-based dependency manager
        self.dependency_manager = None
        if constraint_dir or self._has_default_constraints():
            try:
                # Import here to avoid circular dependencies
                from ..dependencies.dependency_manager import DependencyManager
                
                self.dependency_manager = DependencyManager(
                    ontology_manager,
                    constraint_dir
                )
                self.logger.info("Constraint-based dependency manager initialized")
            except Exception as e:
                self.logger.warning(f"Failed to initialize dependency manager: {e}")
        
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
            
            # Validate inputs
            if not class_uri:
                raise ValueError("class_uri cannot be empty")
            
            if not isinstance(class_uri, str):
                raise ValueError("class_uri must be a string")
            
            # Use FormManager to create the base form
            form_widget = self.form_manager.create_form(class_uri)
            
            if not form_widget:
                raise RuntimeError("FormManager returned None")
            
            # Ensure form widget has expected attributes for compatibility
            if not hasattr(form_widget, 'form_fields'):
                form_widget.form_fields = {}
                self.logger.warning(f"Form widget missing form_fields attribute, added empty dict")
            
            if not hasattr(form_widget, 'class_uri'):
                form_widget.class_uri = class_uri
            
            # Set up dependencies if available
            if self.dependency_manager:
                try:
                    self.dependency_manager.setup_dependencies(form_widget, class_uri)
                    self.logger.info("TTL-based constraints configured successfully")
                except Exception as e:
                    self.logger.error(f"Failed to setup constraints: {e}")
                    # Don't fail entire form creation for constraint issues
            
            # Set parent if provided
            if parent:
                form_widget.setParent(parent)
            
            # Track successful form creation
            self._forms_created_count[class_uri] = self._forms_created_count.get(class_uri, 0) + 1
            if layout_style:
                style_name = layout_style.value if hasattr(layout_style, 'value') else str(layout_style)
                self._layout_usage[style_name] = self._layout_usage.get(style_name, 0) + 1

            # Emit success signal
            self.form_created.emit(class_uri)

            self.logger.info(f"Form built successfully for {class_uri}")
            return form_widget

        except Exception as e:
            error_msg = f"Failed to build form for {class_uri}: {e}"
            self.logger.error(error_msg, exc_info=True)

            # Track error
            self._form_errors[class_uri] = self._form_errors.get(class_uri, 0) + 1

            # Emit error signal - NOW THIS WORKS!
            self.form_error.emit(class_uri, str(e))

            # Return error form with expected attributes
            return self._create_error_form(error_msg, class_uri)
    
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
            from pathlib import Path  # ✅ ADD THIS
            from ..dependencies.dependency_manager import DependencyManager
            
            # Initialize dependency manager
            if config_path:
                # ✅ Convert string to Path object
                config_path_obj = Path(config_path) if isinstance(config_path, str) else config_path
                self.dependency_manager = DependencyManager(self.ontology_manager, config_path_obj)
            
            self.logger.info("Dependency management enabled")
            
        except Exception as e:
            self.logger.error(f"Failed to enable dependencies: {e}")
            self.dependency_manager = None
    
    def disable_dependencies(self):
        """Disable dependency management."""
        self.dependency_manager = None
        self.logger.info("Dependency management disabled")

    def set_loading_mode(self, enabled: bool):
        """
        Enable or disable loading mode for dependency manager.

        When enabled, generation constraints are suppressed during data loading
        to preserve loaded values (e.g., specimen ID). Other constraints (visibility,
        calculation, population) continue to work normally.

        Args:
            enabled: True to enable loading mode, False to disable
        """
        if self.dependency_manager:
            self.dependency_manager.set_loading_mode(enabled)
            self.logger.debug(f"Loading mode set to: {enabled}")

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

        During data loading, generation constraints are suppressed to preserve
        loaded values (e.g., specimen ID). Other constraints (visibility,
        calculation, population) continue to work normally.

        Args:
            form_widget: Form widget created by this builder
            data: Data to populate

        Returns:
            True if successful
        """
        # Enable loading mode to suppress generation constraints
        self.set_loading_mode(True)
        try:
            result = self.form_manager.set_form_data(form_widget, data)
            return result
        finally:
            # Always disable loading mode, even if error occurs
            self.set_loading_mode(False)
    
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
    
    def _create_error_form(self, error_message: str, class_uri: str = "") -> QWidget:
        """Create a standardized error form widget with expected attributes."""
        error_widget = QLabel(f"Form Creation Error:\n\n{error_message}")
        error_widget.setStyleSheet("""
            color: red; 
            padding: 20px; 
            background-color: #2a1a1a; 
            border: 1px solid red;
            border-radius: 5px;
        """)
        error_widget.setWordWrap(True)
        error_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Add expected attributes for compatibility
        error_widget.form_fields = {}
        error_widget.class_uri = class_uri
        error_widget.form_style = None
        error_widget.class_metadata = None
        
        return error_widget
    
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
    
    def refresh_ontology(self):
        """Refresh ontology and clear caches."""
        try:
            self.logger.info("Refreshing ontology and clearing caches")
            self.form_manager.clear_cache()
            # Also clear ontology manager caches if available
            if hasattr(self.ontology_manager, 'classes_cache'):
                self.ontology_manager.classes_cache.clear()
            if hasattr(self.ontology_manager, 'properties_cache'):
                self.ontology_manager.properties_cache.clear()
        except Exception as e:
            self.logger.error(f"Failed to refresh ontology: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive form builder statistics for testing and debugging.

        Returns:
            Dictionary with statistics categories:
            - configuration: Component setup state
            - execution: Form creation statistics
            - health: Component health indicators
            - component_stats: Statistics from sub-components
        """
        try:
            # Get stats from sub-components
            ontology_stats = self.ontology_manager.get_statistics() if self.ontology_manager else {}
            form_manager_cache = self.form_manager.get_cache_info() if hasattr(self.form_manager, 'get_cache_info') else {}
            dependency_stats = self.dependency_manager.get_statistics() if self.dependency_manager else {}

            return {
                # Configuration
                'configuration': {
                    'default_layout': self.default_layout.value if hasattr(self.default_layout, 'value') else str(self.default_layout),
                    'available_layouts': [style.value for style in LayoutStyle],
                    'dependencies_enabled': self.dependency_manager is not None
                },

                # Execution stats (from tracking)
                'execution': {
                    'forms_created': dict(self._forms_created_count),
                    'total_forms_created': sum(self._forms_created_count.values()),
                    'form_errors': dict(self._form_errors),
                    'total_errors': sum(self._form_errors.values()),
                    'layout_usage': dict(self._layout_usage)
                },

                # Health indicators
                'health': {
                    'components_initialized': {
                        'ontology_manager': self.ontology_manager is not None,
                        'form_manager': self.form_manager is not None,
                        'layout_manager': self.layout_manager is not None,
                        'dependency_manager': self.dependency_manager is not None
                    }
                },

                # Component stats
                'component_stats': {
                    'ontology_stats': ontology_stats,
                    'form_manager_cache': form_manager_cache,
                    'dependency_stats': dependency_stats
                }
            }
        except Exception as e:
            self.logger.error(f"Failed to get statistics: {e}")
            return {'error': str(e)}

    def get_form_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about forms created.

        Returns:
            Summary of form creation metrics
        """
        try:
            return {
                'forms_by_class': dict(self._forms_created_count),
                'errors_by_class': dict(self._form_errors),
                'success_rate_by_class': {
                    class_uri: (created / (created + self._form_errors.get(class_uri, 0)))
                    for class_uri, created in self._forms_created_count.items()
                    if created > 0
                }
            }
        except Exception as e:
            self.logger.error(f"Failed to get form statistics: {e}")
            return {'error': str(e)}
    
    def analyze_form_complexity(self, class_uri: str) -> Dict[str, Any]:
        """Analyze form complexity."""
        try:
            # Get class metadata
            metadata = self.ontology_manager.get_class_metadata_for_form(class_uri)
            
            complexity_analysis = {
                'class_uri': class_uri,
                'total_properties': len(metadata.properties),
                'form_groups': len(metadata.form_groups),
                'properties_per_group': {
                    group: len(props) for group, props in metadata.form_groups.items()
                },
                'complexity_score': self._calculate_complexity_score(metadata)
            }
            
            return complexity_analysis
        except Exception as e:
            self.logger.error(f"Failed to analyze form complexity: {e}")
            return {'error': str(e), 'class_uri': class_uri}
    
    def _calculate_complexity_score(self, metadata) -> str:
        """Calculate a simple complexity score."""
        total_props = len(metadata.properties)
        total_groups = len(metadata.form_groups)
        
        if total_props < 10:
            return "Simple"
        elif total_props < 25:
            return "Moderate"
        else:
            return "Complex"
    # ============================================================================
    # CONSTRAINT MANAGEMENT API
    # ============================================================================
    
    def reload_constraints(self):
        """Reload constraints from TTL files."""
        if self.dependency_manager:
            self.dependency_manager.reload_constraints()
            self.logger.info("Constraints reloaded")
    
    def get_constraint_statistics(self):
        """Get statistics about loaded constraints."""
        if self.dependency_manager:
            return self.dependency_manager.get_statistics()
        return {}

    def _has_default_constraints(self) -> bool:
        """Check if default constraint directory exists."""
        default_dir = Path(__file__).parent.parent.parent / "ontology" / "constraints"
        return default_dir.exists() and any(default_dir.glob("gui_*_rules.ttl"))