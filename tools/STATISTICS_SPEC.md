# DynaMat Platform - Statistics Structure Specification

## Overview

This document defines the **unified statistics structure** that all managers in the DynaMat Platform must follow. The specification ensures consistency, predictability, and ease of use across all components.

**Version**: 1.0
**Status**: Active
**Last Updated**: 2025-01-14

---

## Why Unified Statistics?

### Problems Solved
- **Inconsistent APIs** - Before: Each manager used different structures
- **Validation Complexity** - Before: Tools needed manager-specific logic
- **Naming Confusion** - Before: `total_widgets` vs `files_loaded` vs `total_constraints`
- **Unpredictable Location** - Before: Errors in `health`? `errors`? Top-level?

### Benefits
- **Predictable API** - Same pattern across all managers
- **Simpler Tools** - Single validation logic works for all
- **Better Documentation** - Developers know where to find metrics
- **Dashboard Ready** - Consistent structure enables unified monitoring

---

## Core Structure (REQUIRED)

All managers **MUST** return this base structure:

```python
{
    'configuration': {
        # Manager setup state (read-only, doesn't change during runtime)
        # Examples: available_widget_types, caching_enabled, directory_paths
    },

    'execution': {
        # Runtime operation counters (increment during operations)
        # MUST include at least one primary metric
        # Examples: total_widgets, total_forms_created, total_builds
    },
    'health': {
        # Component health indicators (status checks, success rates)
        # Examples: components_initialized, success_rates, error_counts
    }
}
```

### Category Descriptions

#### `configuration`
**Purpose**: Static setup information that describes how the manager is configured

**Contains**:
- Available options (widget types, layouts, etc.)
- Directory paths
- Feature flags (caching_enabled, dependencies_enabled)
- Component connectivity status

**Type**: Always `dict`
**When updated**: Only during initialization
**Example keys**:
- `available_widget_types`
- `constraint_directory`
- `caching_enabled`
- `ontology_manager_connected`

#### `execution`
**Purpose**: Runtime operation counters that track actual work performed

**Contains**:
- Total operation counts
- Breakdown by category/type
- Averages and percentages
- Most active/recent operations

**Type**: Always `dict`
**When updated**: Every time an operation occurs
**Naming requirement**: Must include at least one `total_*` metric
**Example keys**:
- `total_widgets`
- `total_forms_created`
- `total_evaluations`
- `widgets_created` (breakdown dict)

#### `health`
**Purpose**: Component health and operational status

**Contains**:
- Component readiness checks
- Success/failure rates
- Active state information
- Performance indicators

**Type**: Always `dict`
**When updated**: As component state changes
**Example keys**:
- `components_initialized`
- `success_rate`
- `active_state`
- `signal_emissions`

---

## Optional Categories

Managers **MAY** include these standardized optional categories:

### `errors`
**When to use**: If manager tracks errors in detail

**Structure**:
```python
'errors': {
    'total_errors': int,        # REQUIRED if category exists
    'recent_errors': list,      # Last N errors (max 10)
    'error_breakdown': dict     # Optional: by_type, by_source, etc.
}
```

**Example** (WidgetFactory):
```python
'errors': {
    'total_errors': 3,
    'recent_errors': [
        ('hasInvalidProp', 'Property not found in ontology'),
        ('hasMissingType', 'Data type not specified')
    ]
}
```

### `performance`
**When to use**: If manager tracks timing/performance metrics

**Structure**:
```python
'performance': {
    'total_time_ms': float,
    'average_time_ms': float,
    'operation_counts': dict    # Per-second rates, etc.
}
```

**Example** (OntologyLoader):
```python
'performance': {
    'total_load_time_ms': 1250.5,
    'average_load_time_ms': 69.5
}
```

### `content`
**When to use**: For domain-specific content statistics (non-operational)

**Structure**: Flexible (domain-specific)

**Example** (GUISchemaBuilder):
```python
'content': {
    'widget_type_inferences': {
        'string': {'line_edit': 45, 'text_area': 3},
        'double': {'double_spinbox': 12, 'unit_value': 8}
    }
}
```

**Example** (ConstraintManager):
```python
'content': {
    'operations': {...},
    'priority_distribution': {...},
    'trigger_complexity': {...}
}
```

### `components`
**When to use**: If manager coordinates multiple sub-components

**Structure**:
```python
'components': {
    'component_name': component.get_statistics()
}
```

**Example** (OntologyManager):
```python
'components': {
    'loader': loader.get_statistics(),
    'schema_builder': schema_builder.get_statistics()
}
```

---

## Naming Conventions (ENFORCED)

### 1. Total Counters
**Pattern**: `total_<metric>`
**Type**: `int`
**Examples**:
- `total_widgets`
- `total_forms_created`
- `total_builds`
- `total_evaluations`
- `total_errors`

### 2. Success Rates
**Pattern**: `<operation>_success_rate`
**Type**: `float` (0.0 to 1.0)
**Examples**:
- `combo_success_rate`
- `unit_lookup_success_rate`
- `constraint_evaluation_success_rate`

### 3. Nested Breakdowns
**Pattern**: `by_<category>`
**Type**: `dict`
**Examples**:
- `by_class: {class_uri -> count}`
- `by_type: {type_name -> count}`
- `by_operation: {operation_name -> count}`

### 4. Averages
**Pattern**: `average_<metric>`
**Type**: `float`
**Examples**:
- `average_properties_per_class`
- `average_load_time_ms`
- `average_triggers_per_constraint`

### 5. Boolean Checks
**Pattern**: `<component>_ready` or `<feature>_enabled`
**Type**: `bool`
**Examples**:
- `loader_ready`
- `caching_enabled`
- `dependencies_enabled`
- `ontology_manager_connected`

---

## Structural Rules

### Rule 1: No Top-Level Primitives
❌ **WRONG**:
```python
{
    'total_widgets': 5,          # Primitive at top level
    'execution': {...}
}
```

✅ **CORRECT**:
```python
{
    'execution': {
        'total_widgets': 5        # Nested in category
    }
}
```

### Rule 2: Maximum Nesting Depth = 3
❌ **WRONG**:
```python
{
    'execution': {
        'level1': {
            'level2': {
                'level3': {
                    'level4': 'too deep'
                }
            }
        }
    }
}
```

✅ **CORRECT**:
```python
{
    'execution': {
        'metadata_builds': {
            'by_class': {'dyn:Specimen': 5}  # Max 3 levels
        }
    }
}
```

### Rule 3: JSON-Serializable Types Only
**Allowed types**:
- `int`, `float`, `str`, `bool`, `None`
- `list` (of allowed types)
- `dict` (with string keys, allowed type values)

**Forbidden types**:
- Objects, classes, functions
- URIRef, Literal (convert to string first)
- datetime (convert to ISO string or timestamp)

### Rule 4: One Metric, One Category
Each metric belongs to **exactly one** category. No duplication.

❌ **WRONG**:
```python
{
    'execution': {'total_widgets': 5},
    'health': {'total_widgets': 5}     # Duplicate!
}
```

---

## Complete Manager Examples

### WidgetFactory (Reference Implementation)

```python
{
    'configuration': {
        'available_widget_types': [
            'label', 'line_edit', 'combo', 'unit_value', ...
        ],
        'ontology_manager_connected': True
    },
    'execution': {
        'total_widgets': 42,
        'widgets_created': {
            'unit_value': 15,
            'object_combo': 12,
            'line_edit': 10,
            'checkbox': 5
        },
        'widget_type_determinations': {
            'measurement_property_path': 15,
            'object_property_path': 12,
            'data_property_path': 15
        },
        'combo_population': {
            'success': 10,
            'failed': 2,
            'empty': 0
        }
    },
    'health': {
        'creation_errors': 2,
        'combo_success_rate': 0.83
    },
    'errors': {
        'total_errors': 2,
        'recent_errors': [
            ('hasInvalidProp', 'Property not found'),
            ('hasBadRange', 'Range class missing')
        ]
    }
}
```

### GUISchemaBuilder

```python
{
    'configuration': {
        'caching_enabled': False,
        'sparql_executor_ready': True,
        'namespace_manager_ready': True,
        'cache_ready': True,
        'qudt_manager_ready': True
    },
    'execution': {
        'metadata_builds': {
            'by_class': {
                'https://dynamat.utep.edu/ontology#Specimen': 3,
                'https://dynamat.utep.edu/ontology#MechanicalTest': 1
            },
            'total_builds': 4,
            'unique_classes': 2
        },
        'property_extraction': {
            'by_class': {
                'https://dynamat.utep.edu/ontology#Specimen': 25,
                'https://dynamat.utep.edu/ontology#MechanicalTest': 18
            },
            'average_properties_per_class': 21.5
        },
        'form_groups': {
            'by_class': {
                'https://dynamat.utep.edu/ontology#Specimen': 4,
                'https://dynamat.utep.edu/ontology#MechanicalTest': 3
            },
            'average_groups_per_class': 3.5
        }
    },
    'health': {
        'unit_lookups': {
            'success': 15,
            'failed': 0,
            'no_quantity_kind': 10
        },
        'unit_lookup_success_rate': 1.0
    },
    'content': {
        'widget_type_inferences': {
            'string': {'line_edit': 45},
            'double': {'double_spinbox': 12, 'unit_value': 8}
        }
    }
}
```

### ConstraintManager

```python
{
    'configuration': {
        'constraint_directory': 'D:\\DynaMat-Platform\\dynamat\\ontology\\constraints',
        'total_constraints': 11,
        'classes_with_constraints': 1
    },
    'execution': {
        'total_lookups': 0  # Future: track constraint lookups
    },
    'content': {
        'operations': {
            'visibility': 9,
            'calculation': 6,
            'generation': 1,
            'filtering': 1,
            'multi_operation': 6
        },
        'priority_distribution': {
            'low (1-100)': 11,
            'medium (101-500)': 0,
            'high (501+)': 0
        },
        'trigger_complexity': {
            'single_trigger': 5,
            'multi_trigger': 6,
            'average_triggers_per_constraint': 1.73
        },
        'trigger_logic_usage': {
            'ANY': 1,
            'ALL': 10,
            'XOR': 0,
            'None': 0
        }
    }
}
```

### DependencyManager

```python
{
    'configuration': {
        'constraint_manager_loaded': True,
        'available_calculations': 15,
        'available_generators': 5
    },
    'execution': {
        'total_evaluations': 142,
        'constraint_evaluations': {
            'by_constraint': {
                'gui:specimen_c001': 23,
                'gui:specimen_c002': 45,
                'gui:specimen_c003': 74
            }
        },
        'operation_executions': {
            'by_type': {
                'visibility': 89,
                'calculation': 35,
                'generation': 12,
                'filtering': 6
            }
        },
        'trigger_fires': {
            'by_property': {
                'dyn:hasMaterial': 45,
                'dyn:hasStructureType': 38
            }
        },
        'most_active_trigger': 'dyn:hasMaterial'
    },
    'health': {
        'active_state': {
            'has_active_form': True,
            'active_class': 'dyn:Specimen',
            'active_triggers': 8,
            'connected_signals': 24
        },
        'signal_emissions': {
            'constraint_triggered': 142,
            'calculation_performed': 35,
            'generation_performed': 12,
            'error_occurred': 3
        }
    },
    'errors': {
        'total_errors': 3,
        'recent_errors': [
            'Calculation function not found: custom_calc',
            'Invalid constraint condition',
            'Missing trigger property'
        ]
    },
    'components': {
        'constraint_manager': {
            # Full ConstraintManager statistics nested here
        }
    }
}
```

### OntologyFormBuilder

```python
{
    'configuration': {
        'default_layout': 'grouped',
        'available_layouts': ['grouped', 'tabbed', 'single_column'],
        'dependencies_enabled': True
    },
    'execution': {
        'total_forms_created': 8,
        'forms_created': {
            'by_class': {
                'dyn:Specimen': 5,
                'dyn:MechanicalTest': 3
            }
        },
        'form_errors': {
            'by_class': {
                'dyn:Specimen': 0,
                'dyn:MechanicalTest': 0
            }
        },
        'total_errors': 0,
        'layout_usage': {
            'grouped': 6,
            'tabbed': 2,
            'single_column': 0
        }
    },
    'health': {
        'components_initialized': {
            'ontology_manager': True,
            'form_manager': True,
            'layout_manager': True,
            'dependency_manager': True
        }
    },
    'components': {
        'ontology_stats': {...},
        'form_manager_cache': {...},
        'dependency_stats': {...}
    }
}
```

### OntologyLoader

```python
{
    'configuration': {
        'ontology_directory': 'D:\\DynaMat-Platform\\dynamat\\ontology',
        'directory_exists': True
    },
    'execution': {
        'files_loaded': 18,
        'is_loaded': True,
        'graph_size': 7066,
        'loaded_files': [
            {'filename': 'DynaMat_core.ttl', 'triples_added': 245, 'load_time_ms': 45.2},
            {'filename': 'specimen_properties.ttl', 'triples_added': 892, 'load_time_ms': 78.3}
        ],
        'failed_files': []
    },
    'health': {
        'total_failures': 0,
        'success_rate': 1.0
    },
    'performance': {
        'total_load_time_ms': 1250.5,
        'average_load_time_ms': 69.5
    }
}
```

### OntologyManager

```python
{
    'configuration': {
        'ontology_directory': 'D:\\DynaMat-Platform\\dynamat\\ontology',
        'query_mode': 'memory'
    },
    'execution': {
        'total_queries': 0,  # Future: track queries if needed
        'cache_operations': {
            'classes_cached': 0,
            'properties_cached': 0,
            'cache_hit_ratio': 0.0,
            'query_cache_size': 0
        }
    },
    'health': {
        'components': {
            'loader_ready': True,
            'qudt_loaded': None,
            'graph_initialized': True
        }
    },
    'content': {
        'ontology_data': {
            'total_triples': 7066,
            'total_classes': 58,
            'total_individuals': 55,
            'namespaces_bound': 33
        }
    },
    'components': {
        'loader': {
            # Full OntologyLoader statistics nested here
        },
        'schema_builder': {
            # Full GUISchemaBuilder statistics nested here
        }
    }
}
```

---

## Quick Reference Table

| Metric | Manager | Category | Full Path |
|--------|---------|----------|-----------|
| Total widgets created | WidgetFactory | execution | `execution.total_widgets` |
| Widget creation errors | WidgetFactory | errors | `errors.total_errors` |
| Metadata builds | GUISchemaBuilder | execution | `execution.metadata_builds.total_builds` |
| Constraint evaluations | DependencyManager | execution | `execution.total_evaluations` |
| Forms created | OntologyFormBuilder | execution | `execution.total_forms_created` |
| Files loaded | OntologyLoader | execution | `execution.files_loaded` |
| Total triples | OntologyManager | content | `content.ontology_data.total_triples` |
| Total constraints | ConstraintManager | configuration | `configuration.total_constraints` |

---

## Migration Notes

### What Changed

| Old Structure | New Structure | Reason |
|---------------|---------------|--------|
| Top-level primitives | Nested in categories | Consistency |
| `execution_stats` | `execution` | Naming standard |
| Mixed categories | Clear separation | Organization |
| Manager-specific keys | Standardized names | Predictability |

### Breaking Changes

**ConstraintManager**:
- `stats['total_constraints']` → `stats['configuration']['total_constraints']`
- `stats['operations']` → `stats['content']['operations']`

**DependencyManager**:
- `stats['execution_stats']` → `stats['execution']`
- `stats['total_errors']` → `stats['errors']['total_errors']`
- ConstraintManager stats no longer spread at top level

**OntologyManager**:
- `stats['files_loaded']` → `stats['components']['loader']['execution']['files_loaded']`
- `stats['total_triples']` → `stats['content']['ontology_data']['total_triples']`
- `stats['ontology_directory']` → `stats['configuration']['ontology_directory']`

---

## Validation

All statistics dictionaries must pass these checks:

1. ✅ Has required categories: `configuration`, `execution`, `health`
2. ✅ All values are JSON-serializable
3. ✅ No top-level primitives (only dicts at top level)
4. ✅ Maximum nesting depth: 3 levels
5. ✅ `execution` category has at least one `total_*` metric
6. ✅ If `errors` category exists, has `total_errors`
7. ✅ Follows naming conventions for counters, rates, etc.

Use `tools/validate_statistics.py` to validate conformance.

---

## Questions or Issues?

- Review manager examples above
- Check `tools/validate_statistics.py` for validation logic
- See `STATISTICS_IMPLEMENTATION_SUMMARY.md` for implementation details
- Consult CLAUDE.md for overall project guidance

**Last Updated**: 2025-01-14
**Version**: 1.0
