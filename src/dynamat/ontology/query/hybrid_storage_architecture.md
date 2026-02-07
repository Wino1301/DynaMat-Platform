# Hybrid Storage Architecture: TTL + SQLite Indexing

**Status**: 📋 Reference Document - NOT Currently Implemented

This document describes a future architectural approach for managing specimen and test data at scale while maintaining FAIR data principles.

---

## Overview

The DynaMat Platform will maintain **TTL files as the source of truth** for all specimen and test data, while using a **SQLite index** for fast queries and lookups. This hybrid approach balances FAIR data compliance with query performance.

### Core Principle

**TTL files remain authoritative, portable, and human-readable. The SQLite index is a generated cache that can be rebuilt at any time.**

```
specimens/
├── SPN-AL6061-001/
│   ├── SPN-AL6061-001_specimen.ttl        ← SOURCE OF TRUTH (versioned, portable)
│   ├── SPN-AL6061-001_SHPB_2024-01-15.ttl ← SOURCE OF TRUTH
│   └── raw/
│       └── test_2024-01-15.csv
│
├── SPN-SS316L-002/
│   └── ...
│
└── .index/
    └── dynamat.db                          ← GENERATED CACHE (can rebuild)
        ├── specimens table
        ├── tests table
        ├── materials table
        └── index_metadata
```

---

## Why This Architecture?

### Maintains FAIR Data Principles

✅ **Findable**: SQLite enables fast searches, TTL provides semantic metadata
✅ **Accessible**: TTL files readable by any RDF tool
✅ **Interoperable**: Standard RDF format, not locked to proprietary database
✅ **Reusable**: Copy `specimens/` folder = share complete dataset

### Scales Efficiently

| Dataset Size | Pure TTL Loading | With SQLite Index |
|--------------|------------------|-------------------|
| 10 specimens | ~100ms | ~100ms (no benefit) |
| 100 specimens | ~1s | <10ms (100x faster) |
| 1000 specimens | ~10s | <10ms (1000x faster) |
| 10000 specimens | ~100s | <10ms (10000x faster) |

### Graceful Degradation

- Delete `.index/` directory → application rebuilds it automatically
- Index corruption → rebuild from TTL files (source of truth)
- Share data → copy `specimens/` folder, recipient rebuilds index

---

## SQLite Index Schema

### Design Principles

1. **Store only frequently-queried fields** (IDs, material names, basic geometry, dates)
2. **Don't duplicate complex data** (full graphs remain in TTL)
3. **Include file paths** for loading complete graphs when needed
4. **Track modification times** for automatic index invalidation

### Schema Definition

```sql
-- Specimen index: Fast lookup by material, geometry, etc.
CREATE TABLE specimens (
    id TEXT PRIMARY KEY,                    -- SPN-AL6061-001
    material_name TEXT,                     -- Al6061-T6
    material_uri TEXT,                      -- Full URI for reasoning
    structure_type TEXT,                    -- Monolithic, Composite, Layered

    -- Basic geometry (for filtering)
    original_length REAL,                   -- mm
    original_diameter REAL,                 -- mm

    -- File management
    ttl_file_path TEXT NOT NULL,           -- Path to specimen.ttl
    last_modified INTEGER NOT NULL,        -- Unix timestamp

    -- Indexing
    created_date TEXT,                     -- ISO format: 2024-01-15
    created_by TEXT
);

CREATE INDEX idx_specimens_material ON specimens(material_name);
CREATE INDEX idx_specimens_structure ON specimens(structure_type);
CREATE INDEX idx_specimens_created ON specimens(created_date);

-- Test index: Fast lookup by type, date, specimen
CREATE TABLE tests (
    id TEXT PRIMARY KEY,                    -- Unique test ID
    specimen_id TEXT NOT NULL,             -- Foreign key to specimen
    test_type TEXT NOT NULL,               -- SHPBCompression, QuasistaticTension, etc.
    test_date TEXT,                        -- ISO format: 2024-01-15

    -- Key test parameters (for filtering)
    strain_rate REAL,                      -- 1/s
    temperature REAL,                      -- K

    -- File management
    ttl_file_path TEXT NOT NULL,
    last_modified INTEGER NOT NULL,

    -- Results summary (optional)
    is_valid BOOLEAN,                      -- Passed validation
    peak_stress REAL,                      -- MPa (for quick plotting)
    failure_strain REAL,                   -- Decimal

    FOREIGN KEY (specimen_id) REFERENCES specimens(id)
);

CREATE INDEX idx_tests_specimen ON tests(specimen_id);
CREATE INDEX idx_tests_type ON tests(test_type);
CREATE INDEX idx_tests_date ON tests(test_date);
CREATE INDEX idx_tests_valid ON tests(is_valid);

-- Material lookup: Predefined individuals from class_individuals/
CREATE TABLE materials (
    uri TEXT PRIMARY KEY,                  -- https://dynamat.utep.edu/ontology#Al6061_T6
    name TEXT NOT NULL,                    -- Al6061-T6
    category TEXT,                         -- AluminumAlloy, SteelAlloy, etc.
    nominal_density REAL,                  -- kg/m³

    -- From ontology individuals
    ttl_file_path TEXT NOT NULL
);

CREATE INDEX idx_materials_name ON materials(name);
CREATE INDEX idx_materials_category ON materials(category);

-- Index metadata: Track when index was built
CREATE TABLE index_metadata (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- Store last rebuild time
INSERT INTO index_metadata VALUES ('last_rebuild', datetime('now'));
INSERT INTO index_metadata VALUES ('version', '1.0');
```

---

## TTL File Management

### File Organization (Unchanged)

```
specimens/
└── SPN-{MaterialCode}-{Number}/
    ├── SPN-*_specimen.ttl                 # Specimen metadata
    ├── SPN-*_{TestType}_{Date}.ttl        # Test activities (multiple)
    ├── raw/
    │   ├── test_{date}_raw.csv            # Raw signal data
    │   └── ...
    └── processed/
        ├── test_{date}_processed.csv      # Calculated stress-strain
        └── ...
```

### TTL Files Remain Authoritative

All GUI edits save to TTL first:

```python
# User edits specimen in GUI
specimen_graph = build_specimen_graph(form_data)

# 1. Save to TTL (source of truth)
ttl_path = f"specimens/{specimen_id}/{specimen_id}_specimen.ttl"
specimen_graph.serialize(ttl_path, format="turtle")

# 2. Mark index as needing update
index_manager.mark_dirty()  # Lazy rebuild on next query

# OR immediate update (optional)
# index_manager.update_specimen_from_ttl(ttl_path)
```

---

## Synchronization Strategy

### Lazy Rebuild Approach (Recommended)

Simple, robust, minimal overhead:

```python
class IndexManager:
    def __init__(self, specimens_dir: Path, index_path: Path):
        self.specimens_dir = specimens_dir
        self.index_db = index_path
        self._ensure_index()

    def _ensure_index(self):
        """Rebuild index if outdated or missing"""
        if not self.index_db.exists():
            self._rebuild_full_index()
        elif self._index_is_stale():
            self._rebuild_full_index()

    def _index_is_stale(self) -> bool:
        """Check if any TTL file is newer than index"""
        conn = sqlite3.connect(self.index_db)
        cursor = conn.execute("SELECT value FROM index_metadata WHERE key = 'last_rebuild'")
        last_rebuild = cursor.fetchone()[0]
        index_time = datetime.fromisoformat(last_rebuild).timestamp()

        # Check all TTL files
        for ttl_file in self.specimens_dir.glob("*/*.ttl"):
            if ttl_file.stat().st_mtime > index_time:
                return True

        return False

    def _rebuild_full_index(self):
        """Parse all TTL files and populate SQLite"""
        print("Rebuilding index from TTL files...")
        conn = sqlite3.connect(self.index_db)

        # Clear existing data
        conn.execute("DELETE FROM specimens")
        conn.execute("DELETE FROM tests")

        # Parse all specimen files
        for specimen_ttl in self.specimens_dir.glob("*/SPN-*_specimen.ttl"):
            self._index_specimen_file(conn, specimen_ttl)

        # Parse all test files
        for test_ttl in self.specimens_dir.glob("*/SPN-*_*_*.ttl"):
            if "_specimen.ttl" not in str(test_ttl):
                self._index_test_file(conn, test_ttl)

        # Update metadata
        conn.execute("""
            UPDATE index_metadata
            SET value = datetime('now')
            WHERE key = 'last_rebuild'
        """)

        conn.commit()
        print("Index rebuilt successfully")

    def _index_specimen_file(self, conn, ttl_path: Path):
        """Extract key fields from specimen TTL"""
        g = Graph()
        g.parse(ttl_path, format="turtle")

        # Query for specimen data
        query = """
            SELECT ?specimen ?id ?material ?materialName ?structureType
                   ?length ?diameter ?createdDate
            WHERE {
                ?specimen a dyn:Specimen ;
                         dyn:hasSpecimenID ?id ;
                         dyn:hasMaterial ?material ;
                         dyn:hasStructureType ?structureType .

                ?material dyn:hasName ?materialName .

                OPTIONAL { ?specimen dyn:hasOriginalLength ?length }
                OPTIONAL { ?specimen dyn:hasOriginalDiameter ?diameter }
                OPTIONAL { ?specimen dyn:hasCreationDate ?createdDate }
            }
        """

        results = g.query(query)
        for row in results:
            conn.execute("""
                INSERT OR REPLACE INTO specimens
                (id, material_name, material_uri, structure_type,
                 original_length, original_diameter, ttl_file_path,
                 last_modified, created_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(row.id),
                str(row.materialName),
                str(row.material),
                str(row.structureType),
                float(row.length) if row.length else None,
                float(row.diameter) if row.diameter else None,
                str(ttl_path),
                int(ttl_path.stat().st_mtime),
                str(row.createdDate) if row.createdDate else None
            ))
```

### Query Workflow

```python
class SpecimenQueryManager:
    def __init__(self, index_manager: IndexManager):
        self.index = index_manager

    def find_specimens_by_material(self, material_name: str) -> List[str]:
        """Fast lookup using SQLite index"""
        conn = sqlite3.connect(self.index.index_db)
        cursor = conn.execute(
            "SELECT id FROM specimens WHERE material_name = ?",
            (material_name,)
        )
        return [row[0] for row in cursor.fetchall()]

    def get_specimen_graph(self, specimen_id: str) -> Graph:
        """Load full RDF graph for detailed reasoning"""
        conn = sqlite3.connect(self.index.index_db)
        cursor = conn.execute(
            "SELECT ttl_file_path FROM specimens WHERE id = ?",
            (specimen_id,)
        )
        ttl_path = cursor.fetchone()[0]

        # Load complete graph
        g = Graph()
        g.parse(ttl_path, format="turtle")
        return g

    def query_specimens_advanced(self, **filters):
        """
        Hybrid query: Filter in SQLite, reason in RDF

        Example:
            specimens = query_specimens_advanced(
                material="Al6061-T6",
                min_length=10.0,
                max_diameter=15.0
            )
        """
        # Step 1: Fast filtering with SQLite
        conditions = []
        params = []

        if 'material' in filters:
            conditions.append("material_name = ?")
            params.append(filters['material'])

        if 'min_length' in filters:
            conditions.append("original_length >= ?")
            params.append(filters['min_length'])

        if 'max_diameter' in filters:
            conditions.append("original_diameter <= ?")
            params.append(filters['max_diameter'])

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        conn = sqlite3.connect(self.index.index_db)
        cursor = conn.execute(
            f"SELECT id, ttl_file_path FROM specimens WHERE {where_clause}",
            params
        )

        candidates = cursor.fetchall()

        # Step 2: Load full graphs for complex reasoning (if needed)
        results = []
        for specimen_id, ttl_path in candidates:
            g = Graph()
            g.parse(ttl_path, format="turtle")

            # Apply additional SPARQL reasoning if needed
            # ...

            results.append({
                'id': specimen_id,
                'graph': g
            })

        return results
```

---

## Numerical Data: Parquet/HDF5

For large numerical datasets (stress-strain curves, time series signals), use columnar formats alongside TTL metadata.

### Use Case: Processed Test Results

```
specimens/
└── SPN-AL6061-001/
    ├── SPN-AL6061-001_specimen.ttl
    ├── SPN-AL6061-001_SHPB_2024-01-15.ttl      # Metadata + references data files
    ├── raw/
    │   └── test_2024-01-15_raw.csv             # Original signal data
    └── processed/
        ├── test_2024-01-15_stress_strain.parquet  # Columnar format
        └── test_2024-01-15_stress_strain.h5       # Or HDF5
```

### Example: Parquet for Stress-Strain Data

**TTL file references the Parquet file:**

```turtle
# SPN-AL6061-001_SHPB_2024-01-15.ttl

dyn:TEST_SHPB_001 a dyn:SHPBCompression ;
    dyn:hasTestID "TEST-SHPB-001" ;
    dyn:hasSpecimen dyn:SPN_AL6061_001 ;
    dyn:hasTestDate "2024-01-15"^^xsd:date ;

    # Reference to processed data
    dyn:hasProcessedDataFile [
        a dyn:DataFile ;
        dyn:hasFilePath "processed/test_2024-01-15_stress_strain.parquet" ;
        dyn:hasFileFormat "application/parquet" ;
        dyn:hasDescription "True stress-strain curve with engineering values" ;
        dyn:hasColumnSchema [
            dyn:hasColumn "time_us" ;           # Time (microseconds)
            dyn:hasColumn "true_strain" ;       # Decimal
            dyn:hasColumn "true_stress_MPa" ;   # MPa
            dyn:hasColumn "eng_strain" ;
            dyn:hasColumn "eng_stress_MPa" ;
            dyn:hasColumn "strain_rate_s" ;     # 1/s
        ]
    ] .
```

**Parquet file structure:**

```python
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# Create stress-strain data
data = {
    'time_us': [0.0, 10.5, 21.0, 31.5, ...],           # Microseconds
    'true_strain': [0.0, 0.001, 0.002, 0.003, ...],    # Decimal
    'true_stress_MPa': [0.0, 150.2, 298.5, 445.1, ...], # MPa
    'eng_strain': [0.0, 0.001, 0.002, 0.003, ...],
    'eng_stress_MPa': [0.0, 150.0, 297.0, 441.0, ...],
    'strain_rate_s': [2000, 2050, 2100, 2150, ...]     # 1/s
}

df = pd.DataFrame(data)

# Save as Parquet with metadata
table = pa.Table.from_pandas(df)
pq.write_table(
    table,
    'processed/test_2024-01-15_stress_strain.parquet',
    compression='snappy',  # Fast compression
    row_group_size=10000   # Optimize for reading chunks
)
```

**Fast analysis without loading full dataset:**

```python
import pyarrow.parquet as pq

# Read only specific columns (columnar advantage)
table = pq.read_table(
    'processed/test_2024-01-15_stress_strain.parquet',
    columns=['true_strain', 'true_stress_MPa']
)

# Convert to NumPy for plotting
strain = table['true_strain'].to_numpy()
stress = table['true_stress_MPa'].to_numpy()

# Plot without loading time, eng_strain, etc.
plt.plot(strain, stress)
```

**Benefits of Parquet:**
- **Columnar storage**: Read only needed columns (e.g., strain + stress, skip time)
- **Compression**: 5-10x smaller than CSV
- **Fast**: Optimized for analytical queries
- **Interoperable**: Works with Pandas, Polars, DuckDB, Spark, R
- **Schema embedded**: Self-describing with data types

### Example: HDF5 for Multi-Signal SHPB Data

**TTL file references HDF5:**

```turtle
dyn:TEST_SHPB_001
    dyn:hasRawDataFile [
        a dyn:DataFile ;
        dyn:hasFilePath "raw/test_2024-01-15_raw.h5" ;
        dyn:hasFileFormat "application/x-hdf5" ;
        dyn:hasDescription "Raw voltage signals from SHPB strain gauges" ;
        dyn:hasHDF5Structure [
            dyn:hasDataset "/incident_bar/voltage" ;     # Shape: (100000,)
            dyn:hasDataset "/transmitted_bar/voltage" ;  # Shape: (100000,)
            dyn:hasDataset "/time_us" ;                  # Shape: (100000,)
            dyn:hasAttribute "/metadata/sample_rate_MHz" ;
            dyn:hasAttribute "/metadata/gauge_factor" ;
        ]
    ] .
```

**HDF5 file structure:**

```python
import h5py
import numpy as np

# Create HDF5 file with hierarchical structure
with h5py.File('raw/test_2024-01-15_raw.h5', 'w') as f:
    # Time array
    time_us = np.linspace(0, 1000, 100000)  # 1ms test, 10 MHz sampling
    f.create_dataset('time_us', data=time_us, compression='gzip')

    # Incident bar signals
    incident_group = f.create_group('incident_bar')
    incident_group.create_dataset('voltage', data=incident_voltage, compression='gzip')
    incident_group.attrs['gauge_location_mm'] = 500.0
    incident_group.attrs['gauge_factor'] = 2.05

    # Transmitted bar signals
    transmitted_group = f.create_group('transmitted_bar')
    transmitted_group.create_dataset('voltage', data=transmitted_voltage, compression='gzip')
    transmitted_group.attrs['gauge_location_mm'] = 500.0
    transmitted_group.attrs['gauge_factor'] = 2.05

    # Metadata
    metadata = f.create_group('metadata')
    metadata.attrs['sample_rate_MHz'] = 10.0
    metadata.attrs['test_date'] = '2024-01-15'
    metadata.attrs['specimen_id'] = 'SPN-AL6061-001'
```

**Fast partial loading:**

```python
import h5py

# Open file (doesn't load data into memory)
with h5py.File('raw/test_2024-01-15_raw.h5', 'r') as f:
    # Read metadata without loading signals
    sample_rate = f['metadata'].attrs['sample_rate_MHz']

    # Load only incident bar (don't load transmitted)
    incident_voltage = f['incident_bar/voltage'][:]  # Load to memory

    # Or load slice (first 10,000 points)
    incident_slice = f['incident_bar/voltage'][:10000]
```

**Benefits of HDF5:**
- **Hierarchical**: Group related signals (incident bar, transmitted bar)
- **Partial loading**: Read slices without loading entire dataset
- **Metadata**: Store calibration factors, units with data
- **Numerical**: Optimized for NumPy arrays
- **Large files**: Handle GB-sized datasets efficiently

### When to Use Each Format

| Format | Best For | Example Use Case |
|--------|----------|------------------|
| **TTL** | Metadata, relationships, semantic queries | Specimen properties, test configuration |
| **Parquet** | Tabular data, analytical queries | Stress-strain curves, material properties |
| **HDF5** | Multi-dimensional arrays, hierarchical data | Raw SHPB signals, FEA simulation results |
| **CSV** | Simple exports, human inspection | Small datasets, legacy compatibility |

---

## Implementation Phases

### Phase 1: Current State (File-Based TTL)
✅ **Status**: Implemented
- All data in TTL files
- RDFLib in-memory graphs
- Suitable for <100 specimens

### Phase 2: SQLite Index for Metadata
📋 **Status**: Reference (this document)
**Triggers**:
- Dataset exceeds 100 specimens
- Query performance becomes noticeable (>1s)
- Multi-user access needed

**Implementation**:
1. Create `.index/dynamat.db` with schema above
2. Implement `IndexManager` with lazy rebuild
3. Update `OntologyManager` to use index for filtering
4. Keep TTL loading for detailed reasoning

### Phase 3: Parquet/HDF5 for Numerical Data
📋 **Status**: Reference (this document)
**Triggers**:
- Analyzing multiple tests (plot 50 stress-strain curves)
- Large signal datasets (>10 MB per test)
- Integration with analysis pipelines

**Implementation**:
1. Add Parquet export for processed results
2. Store raw signals in HDF5
3. TTL files reference data files
4. GUI loads data for visualization

### Phase 4: Triple-Store (Enterprise Scale)
📋 **Status**: Future consideration
**Triggers**:
- Dataset exceeds 10,000 specimens
- Multi-lab deployment
- Advanced reasoning needed

---

## Key Principles

1. **TTL is source of truth**: Always authoritative, never just a cache
2. **Index is disposable**: Can delete and rebuild at any time
3. **Hybrid queries**: Filter fast (SQLite), reason deep (RDF)
4. **Graceful degradation**: Application works without index (slower)
5. **FAIR compliance**: Data sharing = copy TTL files, recipient rebuilds index

---

## References

- **SQLite**: [https://www.sqlite.org/](https://www.sqlite.org/)
- **Apache Parquet**: [https://parquet.apache.org/](https://parquet.apache.org/)
- **HDF5**: [https://www.hdfgroup.org/solutions/hdf5/](https://www.hdfgroup.org/solutions/hdf5/)
- **RDFLib**: [https://rdflib.readthedocs.io/](https://rdflib.readthedocs.io/)

---

**Document Version**: 1.0
**Last Updated**: 2025-01-17
**Status**: Reference Only - Not Implemented
