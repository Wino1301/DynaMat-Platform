# Automatically assess test validity based on equilibrium metrics
# This uses the assess_validity_from_metrics() method added to SHPBTestMetadata

print("=" * 60)
print("AUTOMATIC VALIDITY ASSESSMENT")
print("=" * 60)

# Assess validity from equilibrium metrics
test_metadata.assess_validity_from_metrics(metrics)

# Set test type (manual input for now)
test_metadata.test_type = "specimen"  # Options: "specimen", "calibration", "elastic"

print(f"\nTest Type: {test_metadata.test_type}")
print(f"Test Validity: {test_metadata.test_validity}")
print(f"\nValidity Notes:")
print(f"  {test_metadata.validity_notes}")

print("\n" + "=" * 60)
print("VALIDITY ASSESSMENT DETAILS")
print("=" * 60)

# Show detailed assessment breakdown
fbc = metrics['FBC']
seqi = metrics['SEQI']
soi = metrics['SOI']
dsuf = metrics['DSUF']

# Force equilibrium assessment
if fbc >= 0.90 and dsuf >= 0.90:
    force_eq_status = "✓ ACHIEVED"
elif fbc >= 0.75 or dsuf >= 0.75:
    force_eq_status = "⚠ PARTIALLY ACHIEVED"
else:
    force_eq_status = "✗ NOT ACHIEVED"

# Strain rate assessment
if soi <= 0.10:
    strain_rate_status = "✓ ACHIEVED"
elif soi <= 0.20:
    strain_rate_status = "⚠ PARTIALLY ACHIEVED"
else:
    strain_rate_status = "✗ NOT ACHIEVED"

print(f"\nForce Equilibrium: {force_eq_status}")
print(f"  FBC: {fbc:.4f} (target: ≥0.90)")
print(f"  DSUF: {dsuf:.4f} (target: ≥0.90)")

print(f"\nConstant Strain Rate: {strain_rate_status}")
print(f"  SOI: {soi:.4f} (target: ≤0.10)")

print(f"\nStress Equilibrium Quality:")
print(f"  SEQI: {seqi:.4f} (target: ≥0.90)")

print("\n" + "=" * 60)
print("CRITERIA SUMMARY")
print("=" * 60)

# Count passing criteria
strict_pass = sum([
    fbc >= 0.95,
    seqi >= 0.90,
    soi <= 0.05,
    dsuf >= 0.98
])

relaxed_pass = sum([
    fbc >= 0.85,
    seqi >= 0.80,
    soi <= 0.10,
    dsuf >= 0.90
])

print(f"Strict criteria passed: {strict_pass}/4")
print(f"Relaxed criteria passed: {relaxed_pass}/4")

if test_metadata.test_validity == "valid":
    print("\n✓ TEST VALID - Data meets quality standards for publication")
elif test_metadata.test_validity == "questionable":
    print("\n⚠ TEST QUESTIONABLE - Data may be usable but review carefully")
else:
    print("\n✗ TEST INVALID - Data does not meet quality standards")

print("=" * 60)
