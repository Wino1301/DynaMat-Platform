import pytest
from rdflib import Graph, URIRef, Literal, RDF, XSD, RDFS
from dynamat.ontology.validator import ValidationSeverity

class TestSHPBValidator:
    """Tests for specialized SHPB validation rules."""

    @pytest.fixture
    def valid_shpb_graph(self, ontology_manager):
        """Fixture for a basic valid SHPB graph."""
        g = Graph()
        dyn = ontology_manager.DYN
        test_uri = URIRef("https://dynamat.utep.edu/ontology#TEST-001")
        specimen_uri = URIRef("https://dynamat.utep.edu/ontology#SPN-001")
        
        g.add((test_uri, RDF.type, dyn.SHPBCompression))
        g.add((test_uri, dyn.hasTestID, Literal("TEST-2025-001")))
        g.add((test_uri, dyn.hasTestDate, Literal("2025-02-01", datatype=XSD.date)))
        g.add((test_uri, dyn.performedOn, specimen_uri))
        g.add((test_uri, dyn.hasUser, dyn.User_ErwinCazares))
        
        # Add required SHPB components
        g.add((test_uri, dyn.hasIncidentBar, dyn.IncidentBar_C350_6ft))
        g.add((dyn.IncidentBar_C350_6ft, RDF.type, dyn.Bar))  # Type the bar
        
        g.add((test_uri, dyn.hasTransmissionBar, dyn.TransmissionBar_C350_6ft))
        g.add((dyn.TransmissionBar_C350_6ft, RDF.type, dyn.Bar)) # Type the bar
        
        g.add((test_uri, dyn.hasStrikerBar, dyn.StrikerBar_C350_18in))
        g.add((dyn.StrikerBar_C350_18in, RDF.type, dyn.Bar)) # Type the bar
        
        # Add required striker velocity
        g.add((test_uri, dyn.hasStrikerVelocity, Literal(15.0, datatype=XSD.double)))
        
        g.add((test_uri, dyn.hasTestType, dyn.MaterialSpecimenTest))
        g.add((dyn.MaterialSpecimenTest, RDF.type, dyn.MechanicalTestType)) # Type the test type
        
        # Add the specimen so reference is valid
        g.add((specimen_uri, RDF.type, dyn.Specimen))
        g.add((specimen_uri, dyn.hasSpecimenID, Literal("DYNML-AL-0001")))
        g.add((specimen_uri, dyn.hasMaterial, dyn.Al6061_T6))
        # Ensure material is typed and has required properties
        g.add((dyn.Al6061_T6, RDF.type, dyn.Material))
        g.add((dyn.Al6061_T6, RDFS.label, Literal("Aluminum 6061-T6")))
        g.add((dyn.Al6061_T6, dyn.hasMaterialName, Literal("Al6061-T6")))
        
        g.add((specimen_uri, dyn.hasSpecimenRole, dyn.TestSpecimen))
        # Add required shape
        g.add((specimen_uri, dyn.hasShape, dyn.Cylindrical))
        
        # Add required creation metadata for specimen
        g.add((specimen_uri, dyn.hasCreatedBy, dyn.User_ErwinCazares))
        g.add((specimen_uri, dyn.hasCreatedDate, Literal("2025-01-01T12:00:00", datatype=XSD.dateTime)))
        g.add((specimen_uri, dyn.hasAppVersion, Literal("1.0.0")))
        
        return g, test_uri

    def test_pulse_shaper_rule(self, ontology_manager, valid_shpb_graph):
        """Test rule: Pulse shaper required if pulse shaping is enabled."""
        g, test_uri = valid_shpb_graph
        dyn = ontology_manager.DYN
        validator = ontology_manager.create_validator()

        # Case 1: Enabled but missing shaper (Should fail)
        g.add((test_uri, dyn.hasPulseShaping, Literal(True)))
        report = validator.validate_graph(g)
        assert report.conforms is False
        assert any("Pulse shaper must be specified" in r.message for r in report.results)

        # Case 2: Enabled and shaper present (Should pass)
        g.add((test_uri, dyn.hasPulseShaper, dyn.PulseShaper_Copper_0015in))
        report = validator.validate_graph(g)
        assert report.conforms is True

    def test_lubrication_rule(self, ontology_manager, valid_shpb_graph):
        """Test rule: Lubrication type required if lubrication is used."""
        g, test_uri = valid_shpb_graph
        dyn = ontology_manager.DYN
        validator = ontology_manager.create_validator()

        # Enable lubrication
        g.add((test_uri, dyn.hasLubricationUsed, Literal(True)))
        
        # Missing type
        report = validator.validate_graph(g)
        assert report.conforms is False
        assert any("Lubrication type must be specified" in r.message for r in report.results)

        # Type present
        g.add((test_uri, dyn.hasLubricationType, Literal("Moly Grease")))
        report = validator.validate_graph(g)
        assert report.conforms is True
