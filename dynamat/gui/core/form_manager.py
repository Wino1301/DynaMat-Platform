"""
DynaMat Platform - Form Manager
Coordinates form creation using specialized components
"""

import logging
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QScrollArea, QFormLayout

from PyQt6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QTextEdit, QComboBox, 
    QSpinBox, QDoubleSpinBox, QDateEdit, QCheckBox, 
    QHBoxLayout, QFrame
)

from ...ontology import OntologyManager, PropertyMetadata, ClassMetadata
from .widget_factory import WidgetFactory
from .data_handler import FormDataHandler
from ..builders.layout_manager import LayoutManager

logger = logging.getLogger(__name__)

class FormStyle(Enum):
    """Available form layout styles."""
    GROUPED = "grouped"
    SIMPLE = "simple"
    TWO_COLUMN = "two_column"
    TABBED = "tabbed"

@dataclass
class FormField:
    """Represents a form field with its widget and metadata."""
    widget: QWidget
    property_uri: str
    property_metadata: PropertyMetadata
    group_name: str
    required: bool = False
    label: Optional[str] = None

class FormManager:
    """
    Coordinates form creation using specialized components.
    
    This is the main coordinator that brings together:
    - Widget creation (WidgetFactory)
    - Layout management (LayoutManager)  
    - Data handling (FormDataHandler)
    - Ontology queries (OntologyManager)
    """
    
    def __init__(self, ontology_manager: OntologyManager):
        """
        Initialize the form manager.
        
        Args:
            ontology_manager: Ontology manager instance
        """
        if ontology_manager is None:
            raise ValueError("OntologyManager cannot be None")
        
        self.ontology_manager = ontology_manager
        self.logger = logging.getLogger(__name__)
        
        # Initialize specialized components
        self.widget_factory = WidgetFactory(ontology_manager)
        self.layout_manager = LayoutManager()
        self.data_handler = FormDataHandler()
        
        # Form cache for performance
        self._form_cache = {}
        self._metadata_cache = {}
        
        self.logger.info("Form manager initialized")
    
    # ============================================================================
    # MAIN FORM CREATION INTERFACE
    # ============================================================================
    
    def create_form(self, class_uri: str, 
                   style: FormStyle = FormStyle.GROUPED,
                   parent: Optional[QWidget] = None,
                   use_cache: bool = True) -> QWidget:
        """
        Create a complete form for the given class.
        
        Args:
            class_uri: URI of the ontology class
            style: Form layout style
            parent: Parent widget
            use_cache: Whether to use cached forms
            
        Returns:
            Complete form widget
        """
        try:
            self.logger.info(f"Creating form for class: {class_uri} with style: {style.value}")
    
            if self.ontology_manager is None:
                raise ValueError("OntologyManager is None")
    
            # Get class metadata from ontology
            try:
                class_metadata = self.ontology_manager.get_class_metadata_for_form(class_uri)
                self.logger.info(f"Retrieved metadata for {class_metadata.name}: {len(class_metadata.properties)} properties")
            except Exception as e:
                self.logger.error(f"Ontology error for {class_uri}: {str(e)}")
                return self._create_error_form(f"Ontology error: {str(e)}")
                
            # Check cache if requested (controlled by global config)
            from ...config import Config

            cache_key = f"{class_uri}_{style.value}"
            if use_cache and Config.USE_FORM_CACHE and cache_key in self._form_cache:
                self.logger.debug(f"Returning cached form for {class_uri}")
                cached_form = self._form_cache[cache_key]
                return self._clone_form(cached_form, parent)
            
            # Get class metadata (from cache or fresh)
            metadata = self._get_class_metadata(class_uri)
            if not metadata:
                return self._create_error_widget(f"Could not load metadata for class: {class_uri}")
            
            # Create widgets for all properties
            widgets = self._create_widgets(metadata)
            self.logger.info(f"Created {len(widgets)} widgets")
        
            if not widgets:
                self.logger.warning(f"No widgets created for {class_uri}")
                widgets = {}
            
            # Create form based on style
            form_widget = self._create_form_by_style(metadata, widgets, style, parent)

            # VERIFY that widgets were actually added to the form
            actual_widget_count = self._count_widgets_in_form(form_widget)
            self.logger.info(f"Widgets in form after layout: {actual_widget_count}")
            
            if actual_widget_count == 0 and len(widgets) > 0:
                self.logger.error("CRITICAL: Widgets created but not added to form layout!")
                # Create fallback simple layout
                form_widget = self._create_fallback_form(metadata, widgets, parent)
            
            # Ensure form widget has all expected attributes
            form_widget.class_uri = class_uri
            form_widget.class_metadata = metadata
            form_widget.form_style = style

            # Create form_fields dictionary for compatibility
            form_fields = self._create_form_fields_dict(metadata, widgets)
            form_widget.form_fields = form_fields

            # Additional attributes for debugging
            form_widget.widgets_created = len(widgets)
            form_widget.groups_created = len(metadata.form_groups)
            form_widget.creation_timestamp = datetime.now()
                      
            # Cache the form (controlled by global config)
            if use_cache and Config.USE_FORM_CACHE:
                self._form_cache[cache_key] = form_widget

            # FINAL VERIFICATION
            final_widget_count = self._count_widgets_in_form(form_widget)
            self.logger.info(f"FINAL: Form for {class_uri} has {final_widget_count} active widgets")
            
            return form_widget
            
        except Exception as e:
            self.logger.error(f"Failed to create form for {class_uri}: {e}", exc_info=True)
            return self._create_error_widget(f"Error creating form: {str(e)}")
    
    def create_form_from_metadata(self, metadata: ClassMetadata,
                                style: FormStyle = FormStyle.GROUPED,
                                parent: Optional[QWidget] = None) -> QWidget:
        """
        Create form directly from class metadata.
        
        Args:
            metadata: Class metadata
            style: Form layout style
            parent: Parent widget
            
        Returns:
            Complete form widget
        """
        try:
            self.logger.info(f"Creating form from metadata: {metadata.name}")
            
            # Create widgets
            widgets = self._create_widgets(metadata)
            if not widgets:
                return self._create_error_widget("No widgets could be created")
            
            # Create form
            form_widget = self._create_form_by_style(metadata, widgets, style, parent)
            
            # Add metadata
            form_widget.class_uri = metadata.uri
            form_widget.class_metadata = metadata
            form_widget.form_style = style
            
            return form_widget
            
        except Exception as e:
            self.logger.error(f"Failed to create form from metadata: {e}", exc_info=True)
            return self._create_error_widget(f"Error creating form: {str(e)}")
    
    # ============================================================================
    # FORM DATA OPERATIONS
    # ============================================================================
    
    def get_form_data(self, form_widget: QWidget) -> Dict[str, Any]:
        """
        Extract data from a form widget.
        
        Args:
            form_widget: Form widget created by this manager
            
        Returns:
            Dictionary of form data
        """
        try:
            return self.data_handler.extract_form_data(form_widget)
        except Exception as e:
            self.logger.error(f"Error getting form data: {e}")
            return {}
    
    def set_form_data(self, form_widget: QWidget, data: Dict[str, Any]) -> bool:
        """
        Set data in a form widget.
        
        Args:
            form_widget: Form widget created by this manager
            data: Dictionary of data to set
            
        Returns:f
            True if successful
        """
        try:
            return self.data_handler.populate_form_data(form_widget, data)
        except Exception as e:
            self.logger.error(f"Error setting form data: {e}")
            return False
    
    def validate_form(self, form_widget: QWidget) -> Dict[str, List[str]]:
        """
        Validate form data.
        
        Args:
            form_widget: Form widget to validate
            
        Returns:
            Dictionary of validation errors
        """
        try:
            return self.data_handler.validate_form_data(form_widget)
        except Exception as e:
            self.logger.error(f"Error validating form: {e}")
            return {"form": [f"Validation error: {e}"]}
    
    def clear_form(self, form_widget: QWidget) -> bool:
        """
        Clear all data in a form widget.
        
        Args:
            form_widget: Form widget to clear
            
        Returns:
            True if successful
        """
        try:
            if hasattr(form_widget, 'form_fields'):
                for form_field in form_widget.form_fields.values():
                    self.data_handler.set_widget_value(form_field.widget, "")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error clearing form: {e}")
            return False
    
    # ============================================================================
    # INTERNAL FORM CREATION
    # ============================================================================
    
    def _get_class_metadata(self, class_uri: str) -> Optional[ClassMetadata]:
        """Get class metadata with caching (controlled by global config)."""
        from ...config import Config

        if Config.USE_METADATA_CACHE and class_uri in self._metadata_cache:
            return self._metadata_cache[class_uri]

        try:
            metadata = self.ontology_manager.get_class_metadata_for_form(class_uri)
            if Config.USE_METADATA_CACHE:
                self._metadata_cache[class_uri] = metadata
            return metadata
        except Exception as e:
            self.logger.error(f"Error getting metadata for {class_uri}: {e}")
            return None
    
    def _create_widgets(self, metadata: ClassMetadata) -> Dict[str, QWidget]:
        """Create widgets for all properties in metadata."""
        try:
            widgets = self.widget_factory.create_widgets_for_properties(metadata.properties)
            self.logger.debug(f"Created {len(widgets)} widgets for {metadata.name}")
            return widgets
        except Exception as e:
            self.logger.error(f"Error creating widgets: {e}")
            return {}
    
    def _create_form_by_style(self, metadata: ClassMetadata, 
                            widgets: Dict[str, QWidget],
                            style: FormStyle,
                            parent: Optional[QWidget]) -> QWidget:
        """Create form using the specified style."""
        
        if style == FormStyle.GROUPED:
            return self.layout_manager.create_grouped_form(
                metadata.form_groups, widgets, parent
            )
        elif style == FormStyle.SIMPLE:
            return self.layout_manager.create_simple_form(
                metadata.properties, widgets, parent
            )
        elif style == FormStyle.TWO_COLUMN:
            return self.layout_manager.create_two_column_form(
                metadata.form_groups, widgets, parent
            )
        elif style == FormStyle.TABBED:
            return self.layout_manager.create_tabbed_form(
                metadata.form_groups, widgets, parent
            )
        else:
            self.logger.warning(f"Unknown form style: {style}, using grouped")
            return self.layout_manager.create_grouped_form(
                metadata.form_groups, widgets, parent
            )
    
    def _create_error_widget(self, error_message: str) -> QWidget:
        """Create a standardized error widget with expected attributes."""
        error_widget = QLabel(error_message)
        error_widget.setStyleSheet("""
            color: red; 
            padding: 20px; 
            background-color: #2a1a1a; 
            border: 1px solid red;
            border-radius: 5px;
        """)
        error_widget.setWordWrap(True)
        error_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Add ALL expected attributes for compatibility
        error_widget.form_fields = {}
        error_widget.class_uri = None
        error_widget.form_style = None
        error_widget.class_metadata = None
        error_widget.widgets_created = 0
        error_widget.groups_created = 0
        error_widget.creation_timestamp = datetime.now()
        
        return error_widget

    def _create_error_form(self, error_message: str) -> QWidget:
        """Create widget showing error message."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        label = QLabel(f"Error creating form:\n\n{error_message}\n\nCheck terminal for details.")
        label.setStyleSheet("""
            color: red; 
            padding: 20px; 
            background-color: #2a1a1a; 
            border: 1px solid red;
            text-align: center;
        """)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        
        layout.addWidget(label)
        return widget
    
    def _clone_form(self, original_form: QWidget, parent: Optional[QWidget]) -> QWidget:
        """
        Clone a form widget (simplified - returns new form).
        
        For now, just create a new form instead of true cloning.
        """
        try:
            if hasattr(original_form, 'class_uri'):
                return self.create_form(
                    original_form.class_uri, 
                    original_form.form_style,
                    parent,
                    use_cache=False
                )
            else:
                self.logger.warning("Cannot clone form without class_uri")
                return original_form
        except Exception as e:
            self.logger.error(f"Error cloning form: {e}")
            return original_form

    def _count_widgets_in_form(self, form_widget: QWidget) -> int:
        """Count actual widgets in the form layout."""
        count = 0
        try:
            # Recursively count all child widgets
            def count_children(widget):
                nonlocal count
                for child in widget.findChildren(QWidget):
                    if isinstance(child, (QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit, QCheckBox)):
                        count += 1
            
            count_children(form_widget)
            return count
        except Exception as e:
            self.logger.error(f"Error counting widgets: {e}")
            return 0

    def _create_fallback_form(self, metadata: ClassMetadata, widgets: Dict, parent: Optional[QWidget]) -> QWidget:
        """Create a simple fallback form when layout manager fails."""
        self.logger.warning("Creating fallback form due to layout failure")
        
        form_widget = QWidget(parent)
        layout = QVBoxLayout(form_widget)
        
        # Create a simple scrollable form
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        content_widget = QWidget()
        content_layout = QFormLayout(content_widget)
        
        # Add all widgets to a simple form layout
        for prop in metadata.properties:
            if prop.uri in widgets:
                widget = widgets[prop.uri]
                label = QLabel(prop.display_name or prop.name)
                content_layout.addRow(label, widget)
                # CRITICAL: Ensure widget has proper parent
                widget.setParent(content_widget)
        
        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area)
        
        self.logger.info(f"Fallback form created with {len(widgets)} widgets")
        return form_widget   

    def _create_form_fields_dict(self, metadata: ClassMetadata, widgets: Dict[str, QWidget]) -> Dict[str, FormField]:
        """
        Create the form_fields dictionary that maps property URIs to FormField objects.
        
        This method was referenced in the fixes but was missing from the original implementation.
        It creates the expected form_fields structure that other parts of the system depend on.
        
        Args:
            metadata: Class metadata containing property information
            widgets: Dictionary mapping property URIs to their widgets
            
        Returns:
            Dictionary mapping property URIs to FormField objects
        """
        form_fields = {}
        
        try:
            for prop in metadata.properties:
                if prop.uri in widgets:
                    widget = widgets[prop.uri]
                    
                    # Create FormField object
                    form_field = FormField(
                        widget=widget,
                        property_uri=prop.uri,
                        property_metadata=prop,
                        group_name=prop.form_group or "General",
                        required=getattr(prop, 'required', False),
                        label=prop.display_name or prop.name
                    )
                    
                    form_fields[prop.uri] = form_field
                    
            self.logger.debug(f"Created form_fields dictionary with {len(form_fields)} entries")
            return form_fields
            
        except Exception as e:
            self.logger.error(f"Error creating form_fields dictionary: {e}")
            return {}
    # ============================================================================
    # CACHE MANAGEMENT
    # ============================================================================
    
    def clear_cache(self):
        """Clear all cached forms and metadata."""
        self._form_cache.clear()
        self._metadata_cache.clear()
        self.logger.info("Form manager cache cleared")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get information about cached items."""
        return {
            'cached_forms': len(self._form_cache),
            'cached_metadata': len(self._metadata_cache),
            'form_cache_keys': list(self._form_cache.keys()),
            'metadata_cache_keys': list(self._metadata_cache.keys())
        }
    
    # ============================================================================
    # UTILITY METHODS
    # ============================================================================
    
    def get_form_summary(self, form_widget: QWidget) -> Dict[str, Any]:
        """Get summary information about a form."""
        summary = {
            'class_uri': getattr(form_widget, 'class_uri', 'unknown'),
            'form_style': getattr(form_widget, 'form_style', 'unknown'),
            'has_form_fields': hasattr(form_widget, 'form_fields'),
            'total_fields': 0,
            'groups_created': 0
        }
        
        if hasattr(form_widget, 'form_fields'):
            summary['total_fields'] = len(form_widget.form_fields)
        
        if hasattr(form_widget, 'groups_created'):
            summary['groups_created'] = form_widget.groups_created
        
        # Add data handler summary
        data_summary = self.data_handler.get_form_summary(form_widget)
        summary.update(data_summary)
        
        return summary
    
    def reload_form(self, form_widget: QWidget) -> QWidget:
        """
        Reload a form from its class URI.
        
        Args:
            form_widget: Existing form widget
            
        Returns:
            New form widget or the same widget if reload fails
        """
        try:
            if not hasattr(form_widget, 'class_uri'):
                self.logger.error("Cannot reload form without class_uri")
                return form_widget
            
            class_uri = form_widget.class_uri
            style = getattr(form_widget, 'form_style', FormStyle.GROUPED)
            parent = form_widget.parent()
            
            # Clear cache for this form
            cache_key = f"{class_uri}_{style.value}"
            if cache_key in self._form_cache:
                del self._form_cache[cache_key]
            
            # Create new form
            new_form = self.create_form(class_uri, style, parent, use_cache=False)
            
            self.logger.info(f"Reloaded form for {class_uri}")
            return new_form
            
        except Exception as e:
            self.logger.error(f"Error reloading form: {e}")
            return form_widget