"""rdf_data_io.py
=================
Utility functions for **loading SHPB experiments stored as RDF/Turtle**,
finding experiments by material & processing route, retrieving raw gauge
traces, and extracting original specimen geometry.  The helpers compose the
first stage of the pre‑processing pipeline that feeds the PINN.

Dependencies
------------
* `rdflib`  – RDF parsing & SPARQL queries
* `pandas`  – tabular outputs
* `numpy`   – numerical helpers
* `SHPB_Toolkit` – provides ``scripts.rdf_wrapper.RDFWrapper``
  and ``scripts.SHPB_RDFSignalFetch.RawExperimentDataHandler`` for decoding
  Base‑64 sensor signals.

All heavy objects (raw traces) are returned as **NumPy / Pandas** objects so
that downstream steps can remain dependency‑light.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Tuple

import numpy as np
import pandas as pd
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF

# -----------------------------------------------------------------------------
# Toolkit imports – the calling notebook has already pushed both *scripts/*
# directories onto sys.path.  We repeat the import here so the module can be
# used standalone once the package layout is finalised.
# -----------------------------------------------------------------------------
import sys
nb_dir        = Path.cwd()                     # …/SHPB_Johnson_Cook/notebooks
proj_root     = nb_dir.parent                 # …/SHPB_Johnson_Cook
repo_root     = proj_root.parent              # one level higher
# ② SHPB_Toolkit/scripts          (original toolkit)
toolkit_path  = repo_root / "SHPB_Toolkit" / "scripts"
sys.path.insert(1, str(toolkit_path))         # keep as second–priority
from rdf_wrapper import RDFWrapper
from SHPB_RDFSignalFetch import RawExperimentDataHandler

# Namespace of the custom ontology
DYNAMAT: Namespace = Namespace(
    "https://github.com/UTEP-Dynamic-Materials-Lab/SHPB_Toolkit/tree/main/ontology#"
)

# -----------------------------------------------------------------------------
# 1. SPARQL‑based experiment search
# -----------------------------------------------------------------------------

_SP_TEMPLATE = """
PREFIX dynamat: <https://github.com/UTEP-Dynamic-Materials-Lab/SHPB_Toolkit/tree/main/ontology#>

SELECT ?exp WHERE {{
  ?exp  a dynamat:SHPBExperiment ;
        dynamat:hasMetadata          ?meta .
  ?meta dynamat:hasSpecimen          ?spec .

  ?spec dynamat:hasMaterial          ?mat ;
        dynamat:hasSpecimenProcessing ?proc .

  ?mat  dynamat:hasAbbreviation      ?mabbr .
  ?proc dynamat:hasAbbreviation      ?pabbr .

  FILTER (lcase(str(?mabbr)) = "{material}" &&
          lcase(str(?pabbr)) = "{processing}")
}}
"""

def find_experiments(
    root: str | Path,
    material_abbr: str,
    processing_abbr: str,
    debug: bool = False,
) -> List[Path]:
    """Recursively locate TTL files whose *specimen* matches the requested
    material and processing *abbreviations*.

    Parameters
    ----------
    root : str | Path
        Directory to search.
    material_abbr : str
        Abbreviation literal of the material, e.g. ``"SS316"``.
    processing_abbr : str
        Abbreviation literal of the processing route, e.g.
        ``"3D Printed Specimen"``.
    debug : bool, default False
        Prints per‑file match counts.

    Returns
    -------
    list[Path]
        TTL files that satisfy both criteria.
    """
    mat   = material_abbr.strip().lower()
    proc  = processing_abbr.strip().lower()
    query = _SP_TEMPLATE.format(material=mat, processing=proc)

    hits: List[Path] = []
    for ttl in Path(root).rglob("*.ttl"):
        g = Graph()
        try:
            g.parse(ttl, format="turtle")
        except Exception as exc:
            print(f"[warn] {ttl.name}: {exc}")
            continue
        rows = list(g.query(query))
        if debug:
            print(f"{ttl.name:<45s} → {len(rows)} match(es)")
        if rows:
            hits.append(ttl)
    return hits

# -----------------------------------------------------------------------------
# 2. Specimen geometry summary
# -----------------------------------------------------------------------------

def _get_original_dims(exp: RDFWrapper) -> Tuple[float, float, float]:
    """Return (length_mm, area_mm2, diameter_mm) from the specimen subtree.

    *Values are *NaN* if the corresponding triple is missing.*"""
    spec_uri = exp.get_instances_of_class("dynamat:SHPBSpecimen")[0]
    length = area = diam = np.nan
    for dim in exp.get_objects(spec_uri, "dynamat:hasDimension"):
        if "OriginalLength" in dim:
            length = float(exp.get_objects(dim, "dynamat:hasValue")[0])
        elif "OriginalCrossSectionalArea" in dim:
            area = float(exp.get_objects(dim, "dynamat:hasValue")[0])
        elif "OriginalDiameter" in dim:
            diam = float(exp.get_objects(dim, "dynamat:hasValue")[0])
    return length, area, diam


def summarise_specimens(ttl_paths: List[Path], debug: bool = False) -> pd.DataFrame:
    """Return a DataFrame with one row per TTL file and the specimen geometry.

    Columns
    -------
    * ``file`` – Path
    * ``length_mm``
    * ``area_mm2``
    * ``diameter_mm``
    """
    rows: List[Dict[str, object]] = []
    for ttl in ttl_paths:
        if debug:
            print(f"[specimen_summary] {ttl.name}")
        exp = RDFWrapper(ttl)
        length, area, diam = _get_original_dims(exp)
        rows.append({
            "file": ttl,
            "length_mm": length,
            "area_mm2": area,
            "diameter_mm": diam,
        })
    return pd.DataFrame(rows)

# -----------------------------------------------------------------------------
# 3. Raw gauge‑trace fetcher
# -----------------------------------------------------------------------------

def fetch_raw_pulse(ttl: Path, debug: bool = False) -> pd.DataFrame:
    """Decode **time, incident, transmitted** gauge traces from a Turtle file.

    Parameters
    ----------
    ttl : Path
        Path to the experiment’s TTL file.
    debug : bool, default False
        Prints the sample count when *True*.

    Returns
    -------
    pandas.DataFrame
        Columns: ``Time``, ``Incident Raw``, ``Transmitted Raw``
        (reflected gauge not present in current RDF schema).
    """
    exp = RDFWrapper(ttl)
    handler = RawExperimentDataHandler(exp)

    inc = handler.fetch_gauge_signals("dynamat:IncidentSensorSignal")
    tran = handler.fetch_gauge_signals("dynamat:TransmittedSensorSignal")
    time = handler.fetch_sensor_signals("dynamat:TimeSensorSignal")

    if debug:
        print(f"[raw_pulse] {ttl.name} → {len(time)} samples")

    return pd.DataFrame({
        "Time":           time.iloc[:, 0],
        "Incident Raw":   inc.iloc[:, 0],
        "Transmitted Raw": tran.iloc[:, 0],
    })

