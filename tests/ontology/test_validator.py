import pytest
from rdflib import Graph, URIRef, Literal, RDF, XSD, RDFS
from dynamat.ontology.validator import ValidationSeverity

class TestValidator:
    """Tests for SHACL validation."""

    def test_validate_valid_specimen(self, ontology_manager):
        """Test validation of a correctly constructed specimen graph."""
        validator = ontology_manager.create_validator()
        
        # Create a minimal valid specimen graph
        g = Graph()
        dyn = ontology_manager.DYN
        
        # Bind namespaces
        g.bind("dyn", dyn)
        
        specimen = URIRef("https://dynamat.utep.edu/ontology#SPN-TEST-001")
        g.add((specimen, RDF.type, dyn.Specimen))
        g.add((specimen, dyn.hasSpecimenID, Literal("DYNML-TEST-0001")))
        # Note: Material and Role are URI references
        g.add((specimen, dyn.hasMaterial, dyn.Al6061_T6))
        # Ensure Material has correct type and required properties for validation
        g.add((dyn.Al6061_T6, RDF.type, dyn.Material))
        g.add((dyn.Al6061_T6, RDFS.label, Literal("Aluminum 6061-T6")))
        g.add((dyn.Al6061_T6, dyn.hasMaterialName, Literal("Al6061-T6")))
        
        g.add((specimen, dyn.hasSpecimenRole, dyn.TestSpecimen))
        # Add valid shape
        g.add((specimen, dyn.hasShape, dyn.Cylindrical))
        
        # Add required creation metadata
        g.add((specimen, dyn.hasCreatedBy, dyn.User_ErwinCazares))
        g.add((specimen, dyn.hasCreatedDate, Literal("2025-01-01T12:00:00", datatype=XSD.dateTime)))
        g.add((specimen, dyn.hasAppVersion, Literal("1.0.0")))

        report = validator.validate_graph(g)
        
        # If it fails, print violations for debugging
        if not report.conforms:
            for result in report.results:
                if result.severity == ValidationSeverity.VIOLATION:
                    print(f"VIOLATION: {result.message} ({result.focus_node})")

        assert report.conforms is True

    def test_validate_invalid_specimen(self, ontology_manager):
        """Test validation failure when required fields are missing."""
        validator = ontology_manager.create_validator()
        
        # Create an INVALID specimen (missing ID)
        g = Graph()
        dyn = ontology_manager.DYN
        specimen = URIRef("https://dynamat.utep.edu/ontology#SPN-INVALID-001")
        g.add((specimen, RDF.type, dyn.Specimen))
        
        report = validator.validate_graph(g)
        
        assert report.conforms is False
        assert report.violations > 0
        
        # Check that SpecimenID violation is found
        messages = [r.message for r in report.results]
        assert any("Specimen ID" in m for m in messages)
