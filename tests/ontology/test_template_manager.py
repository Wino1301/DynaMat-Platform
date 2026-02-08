import pytest
from pathlib import Path

class TestTemplateManager:
    """Tests for TemplateManager."""

    def test_get_available_templates(self, ontology_manager):
        """Test listing available templates."""
        template_mgr = ontology_manager.create_template_manager()
        templates = template_mgr.get_available_templates()
        
        assert len(templates) > 0
        
        # Check categories
        categories = template_mgr.get_template_categories()
        assert "equipment" in categories

    # def test_load_shpb_template(self, ontology_manager):
    #     """Test loading the standard SHPB template."""
    #     template_mgr = ontology_manager.create_template_manager()
    #     
    #     # Look for SHPB standard setup
    #     shpb_template = next((t for t in template_mgr.get_available_templates() 
    #                          if "SHPB" in t.name), None)
    #     
    #     # If template exists (it should based on file structure), test loading
    #     if shpb_template:
    #         metadata, values = template_mgr.load_template(shpb_template.name)
    #         assert metadata.name == shpb_template.name
    #         assert "hasStrikerVelocity" in values or "hasStrikerBar" in values

    def test_apply_template(self, ontology_manager):
        """Test applying a template to a new instance."""
        template_mgr = ontology_manager.create_template_manager()
        
        # Find a template
        templates = template_mgr.get_available_templates()
        if templates:
            template = templates[0]
            instance_uri = "https://dynamat.utep.edu/ontology#TestInstance"
            
            data = template_mgr.apply_template(template.name, instance_uri)
            
            assert data["uri"] == instance_uri
            assert data["applied_template"] == template.name
            assert "template_applied_date" in data
