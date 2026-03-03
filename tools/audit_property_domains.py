"""Audit migrated TTL files: verify every dyn: property sits on the correct domain node."""

from rdflib import Graph, Namespace, URIRef, Literal, BNode
from rdflib.namespace import RDF, XSD
from pathlib import Path
from collections import defaultdict

DYN = Namespace("https://dynamat.utep.edu/ontology#")
QUDT = Namespace("http://qudt.org/schema/qudt/")

# ── Domain map: property URI → set of allowed domain classes ──
DOMAIN_MAP = {
    # === Specimen properties ===
    str(DYN.hasSpecimenID): {"Specimen"},
    str(DYN.hasSpecimenBatchID): {"Specimen"},
    str(DYN.hasSpecimenRole): {"Specimen"},
    str(DYN.hasMaterial): {"Specimen", "SpecimenBatchID"},
    str(DYN.hasCompositePhaseDescription): {"Specimen"},
    str(DYN.hasShape): {"Specimen"},
    str(DYN.hasStructure): {"Specimen"},
    str(DYN.hasOriginalLength): {"Specimen"},
    str(DYN.hasOriginalWidth): {"Specimen"},
    str(DYN.hasOriginalHeight): {"Specimen"},
    str(DYN.hasOriginalThickness): {"Specimen"},
    str(DYN.hasOriginalDiameter): {"Specimen"},
    str(DYN.hasOriginalCrossSection): {"Specimen"},
    str(DYN.hasOriginalMass): {"Specimen"},
    str(DYN.hasFinalLength): {"Specimen"},
    str(DYN.hasFinalWidth): {"Specimen"},
    str(DYN.hasFinalHeight): {"Specimen"},
    str(DYN.hasFinalThickness): {"Specimen"},
    str(DYN.hasFinalDiameter): {"Specimen"},
    str(DYN.hasFinalCrossSection): {"Specimen"},
    str(DYN.hasFinalMass): {"Specimen"},
    str(DYN.hasManufacturingMethod): {"Specimen", "SpecimenBatchID"},
    str(DYN.hasManufacturedDate): {"Specimen", "SpecimenBatchID"},
    str(DYN.hasHeatTreatment): {"Specimen"},
    str(DYN.hasSurfaceFinish): {"Specimen"},
    str(DYN.hasBuildOrientation): {"Specimen", "SpecimenBatchID"},
    str(DYN.hasLayerThickness): {"Specimen", "SpecimenBatchID"},
    str(DYN.hasMachiningTolerance): {"Specimen", "SpecimenBatchID"},
    str(DYN.hasMoltenMetalTemperature): {"Specimen", "SpecimenBatchID"},
    str(DYN.hasMoldTemperature): {"Specimen", "SpecimenBatchID"},
    str(DYN.hasCastCoolingDuration): {"Specimen", "SpecimenBatchID"},
    str(DYN.hasLatticeType): {"Specimen"},
    str(DYN.hasLatticeCellsX): {"Specimen"},
    str(DYN.hasLatticeCellsY): {"Specimen"},
    str(DYN.hasLatticeCellsZ): {"Specimen"},
    str(DYN.hasVoxelSize): {"Specimen"},
    str(DYN.hasLatticeStrutMinX): {"Specimen"},
    str(DYN.hasLatticeStrutMaxX): {"Specimen"},
    str(DYN.hasLatticeStrutMinY): {"Specimen"},
    str(DYN.hasLatticeStrutMaxY): {"Specimen"},
    str(DYN.hasLatticeStrutMinZ): {"Specimen"},
    str(DYN.hasLatticeStrutMaxZ): {"Specimen"},
    str(DYN.hasLatticeNx): {"Specimen"},
    str(DYN.hasLatticeNy): {"Specimen"},
    str(DYN.hasLatticeNz): {"Specimen"},
    str(DYN.hasMatrixVolumeFraction): {"Specimen"},
    str(DYN.hasReinforcementVolumeFraction): {"Specimen"},
    str(DYN.hasMatrixMaterial): {"Specimen"},
    str(DYN.hasReinforcementMaterial): {"Specimen"},
    str(DYN.hasSHPBCompressionTest): {"Specimen"},
    # === SHPBCompression properties ===
    str(DYN.hasStrikerBar): {"SHPBCompression"},
    str(DYN.hasIncidentBar): {"SHPBCompression"},
    str(DYN.hasTransmissionBar): {"SHPBCompression"},
    str(DYN.hasIncidentStrainGauge): {"SHPBCompression"},
    str(DYN.hasTransmissionStrainGauge): {"SHPBCompression"},
    str(DYN.hasMomentumTrap): {"SHPBCompression"},
    str(DYN.hasPulseShaper): {"SHPBCompression"},
    str(DYN.hasStrikerVelocity): {"SHPBCompression"},
    str(DYN.hasStrikerLaunchPressure): {"SHPBCompression"},
    str(DYN.hasBarrelOffset): {"SHPBCompression"},
    str(DYN.hasMomentumTrapTailoredDistance): {"SHPBCompression"},
    str(DYN.hasLubrication): {"SHPBCompression"},
    str(DYN.hasPulseDuration): {"SHPBCompression"},
    str(DYN.hasPulseLength): {"SHPBCompression"},
    str(DYN.hasPulseSpeed): {"SHPBCompression"},
    str(DYN.hasPulseStrainAmplitude): {"SHPBCompression"},
    str(DYN.hasPulseStressAmplitude): {"SHPBCompression"},
    str(DYN.hasPulseRiseTime): {"SHPBCompression"},
    str(DYN.hasTukeyAlphaParam): {"SHPBCompression"},
    str(DYN.hasAlignmentParams): {"SHPBCompression"},
    str(DYN.hasEquilibriumMetrics): {"SHPBCompression"},
    str(DYN.hasSegmentationParams): {"SHPBCompression"},
    str(DYN.hasAnalysisTimestamp): {"SHPBCompression"},
    str(DYN.hasDataSeries): {"MechanicalTest", "SHPBCompression"},
    str(DYN.hasAnalysisFile): {"MechanicalTest", "SHPBCompression"},
    str(DYN.hasPulseDetectionParams): {"SHPBCompression", "DataSeries", "RawSignal"},
    str(DYN.performedOn): {"SHPBCompression", "MechanicalTest"},
    str(DYN.hasTestDate): {"SHPBCompression", "MechanicalTest"},
    str(DYN.hasTestID): {"SHPBCompression", "MechanicalTest"},
    str(DYN.hasTestType): {"SHPBCompression", "MechanicalTest"},
    str(DYN.hasTestValidity): {"SHPBCompression", "MechanicalTest"},
    str(DYN.hasUser): {"SHPBCompression", "MechanicalTest"},
    str(DYN.hasValidityCriteria): {"SHPBCompression", "MechanicalTest"},
    str(DYN.hasValidityNotes): {"SHPBCompression", "MechanicalTest"},
    str(DYN.isValidityOverridden): {"SHPBCompression", "MechanicalTest"},
    # === DataSeries properties ===
    str(DYN.hasSeriesType): {"DataSeries"},
    str(DYN.hasAnalysisMethod): {"DataSeries"},
    str(DYN.hasDataFile): {"DataSeries"},
    str(DYN.hasColumnName): {"DataSeries"},
    str(DYN.hasColumnIndex): {"DataSeries"},
    str(DYN.hasLegendName): {"DataSeries"},
    str(DYN.hasSeriesUnit): {"DataSeries"},
    str(DYN.hasQuantityKind): {"DataSeries"},
    str(DYN.hasDataPointCount): {"DataSeries", "AnalysisFile"},
    str(DYN.hasProcessingMethod): {"DataSeries"},
    str(DYN.hasFilterApplied): {"DataSeries"},
    str(DYN.measuredBy): {"DataSeries"},
    str(DYN.derivedFrom): {"DataSeries"},
    str(DYN.hasSamplingRate): {"DataSeries", "RawSignal"},
    # === AlignmentParams properties ===
    str(DYN.hasKLinear): {"AlignmentParams"},
    str(DYN.hasCenteredSegmentPoints): {"AlignmentParams"},
    str(DYN.hasCorrelationWeight): {"AlignmentParams"},
    str(DYN.hasDisplacementWeight): {"AlignmentParams"},
    str(DYN.hasStrainRateWeight): {"AlignmentParams"},
    str(DYN.hasStrainWeight): {"AlignmentParams"},
    str(DYN.hasTransmittedSearchMin): {"AlignmentParams"},
    str(DYN.hasTransmittedSearchMax): {"AlignmentParams"},
    str(DYN.hasReflectedSearchMin): {"AlignmentParams"},
    str(DYN.hasReflectedSearchMax): {"AlignmentParams"},
    str(DYN.hasTransmittedShiftValue): {"AlignmentParams"},
    str(DYN.hasReflectedShiftValue): {"AlignmentParams"},
    str(DYN.hasFrontThreshold): {"AlignmentParams"},
    str(DYN.hasFrontIndex): {"AlignmentParams"},
    # === PulseDetectionParams ===
    str(DYN.hasPulsePoints): {"PulseDetectionParams"},
    str(DYN.hasKTrials): {"PulseDetectionParams"},
    str(DYN.hasDetectionPolarity): {"PulseDetectionParams"},
    str(DYN.hasMinSeparation): {"PulseDetectionParams"},
    str(DYN.hasDetectionLowerBound): {"PulseDetectionParams"},
    str(DYN.hasDetectionUpperBound): {"PulseDetectionParams"},
    str(DYN.hasSelectionMetric): {"PulseDetectionParams"},
    str(DYN.hasStartIndex): {"PulseDetectionParams"},
    str(DYN.hasEndIndex): {"PulseDetectionParams"},
    str(DYN.hasWindowLength): {"PulseDetectionParams"},
    str(DYN.appliedToSeries): {"PulseDetectionParams"},
    # === EquilibriumMetrics ===
    str(DYN.hasFBC): {"EquilibriumMetrics"},
    str(DYN.hasSEQI): {"EquilibriumMetrics"},
    str(DYN.hasSOI): {"EquilibriumMetrics"},
    str(DYN.hasDSUF): {"EquilibriumMetrics"},
    str(DYN.hasFBCLoading): {"EquilibriumMetrics"},
    str(DYN.hasDSUFLoading): {"EquilibriumMetrics"},
    str(DYN.hasFBCPlateau): {"EquilibriumMetrics"},
    str(DYN.hasDSUFPlateau): {"EquilibriumMetrics"},
    str(DYN.hasFBCUnloading): {"EquilibriumMetrics"},
    str(DYN.hasDSUFUnloading): {"EquilibriumMetrics"},
    # === SegmentationParams ===
    str(DYN.hasSegmentPoints): {"SegmentationParams"},
    str(DYN.hasSegmentThreshold): {"SegmentationParams"},
    # === AnalysisFile ===
    str(DYN.hasFilePath): {"AnalysisFile"},
    str(DYN.hasFileName): {"AnalysisFile"},
    str(DYN.hasFileSize): {"AnalysisFile"},
    str(DYN.hasFileFormat): {"AnalysisFile"},
    str(DYN.hasColumnCount): {"AnalysisFile"},
    str(DYN.hasCreatedDate): {"AnalysisFile", "Specimen"},
}

# Type hierarchy
TYPE_PARENTS = {
    "SHPBCompression": {"MechanicalTest"},
    "RawSignal": {"DataSeries"},
    "ProcessedData": {"DataSeries"},
}


def get_all_types(direct_types):
    all_types = set(direct_types)
    for t in list(all_types):
        if t in TYPE_PARENTS:
            all_types.update(TYPE_PARENTS[t])
    return all_types


def main():
    target = Path("user_data/specimens")
    violations = []
    files_checked = 0
    triples_checked = 0
    props_not_in_map = 0

    DYN_NS = str(DYN)

    for f in sorted(target.rglob("*.ttl")):
        g = Graph()
        g.parse(str(f), format="turtle")
        files_checked += 1

        # Build subject → types map
        subject_types = defaultdict(set)
        for s, _, o in g.triples((None, RDF.type, None)):
            type_name = str(o).split("#")[-1] if "#" in str(o) else str(o)
            if type_name == "QuantityValue":
                continue
            subject_types[s].add(type_name)

        # Check every dyn: property triple
        for s, p, o in g:
            p_str = str(p)
            if not p_str.startswith(DYN_NS):
                continue
            # Skip BNode subjects (QV internals)
            if isinstance(s, BNode):
                continue

            triples_checked += 1

            if p_str not in DOMAIN_MAP:
                props_not_in_map += 1
                continue

            allowed_domains = DOMAIN_MAP[p_str]
            subject_direct = subject_types.get(s, set())
            subject_all = get_all_types(subject_direct)

            if not subject_all & allowed_domains:
                prop_name = p_str.split("#")[-1]
                subj_name = str(s).split("#")[-1] if "#" in str(s) else str(s)
                violations.append({
                    "file": f.name,
                    "subject": subj_name,
                    "subject_types": subject_direct,
                    "property": prop_name,
                    "allowed_domains": allowed_domains,
                })

    print("=== PROPERTY DOMAIN PLACEMENT AUDIT ===")
    print()
    print(f"Files checked:       {files_checked}")
    print(f"dyn: triples checked:{triples_checked}")
    print(f"Props not in map:    {props_not_in_map} (generic/metadata)")
    print()

    if not violations:
        print("ALL PROPERTIES ON CORRECT DOMAIN NODES.")
    else:
        print(f"VIOLATIONS: {len(violations)}")
        print()
        by_prop = defaultdict(list)
        for v in violations:
            by_prop[v["property"]].append(v)
        for prop, vlist in sorted(by_prop.items()):
            print(f"  {prop} (expected on: {vlist[0]['allowed_domains']})")
            for v in vlist[:5]:
                print(f"    {v['file']}: {v['subject']} (typed as {v['subject_types']})")
            if len(vlist) > 5:
                print(f"    ... and {len(vlist) - 5} more")
            print()


if __name__ == "__main__":
    main()
