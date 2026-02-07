"""
SHPB Test Validity Assessment

Encapsulates all validity assessment logic for SHPB tests based on equilibrium metrics.
Extracted from SHPBTestMetadata for single responsibility and testability.
"""

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class ValidityAssessor:
    """
    Assesses SHPB test validity based on equilibrium metrics.

    Uses multi-level criteria with named threshold constants for clarity
    and maintainability. Provides methods for both overall validity
    assessment and specific criteria checking.

    Threshold Constants:
        Strict standards (all must pass for ValidTest):
        - FBC_STRICT: 0.95 (Force Balance Coefficient)
        - SEQI_STRICT: 0.90 (Stress Equilibrium Quality Index)
        - SOI_STRICT: 0.05 (Strain Offset Index - lower is better)
        - DSUF_STRICT: 0.98 (Dynamic Stress Uniformity Factor)

        Relaxed standards (at least 2/4 for QuestionableTest):
        - FBC_RELAXED: 0.85
        - SEQI_RELAXED: 0.80
        - SOI_RELAXED: 0.10
        - DSUF_RELAXED: 0.90

    Example:
        >>> assessor = ValidityAssessor()
        >>> metrics = {'FBC': 0.96, 'SEQI': 0.92, 'SOI': 0.04, 'DSUF': 0.99}
        >>> validity = assessor.determine_overall_validity(metrics)
        >>> print(validity)  # 'dyn:ValidTest'
    """

    # Strict thresholds - all must pass for ValidTest
    FBC_STRICT = 0.95
    SEQI_STRICT = 0.90
    SOI_STRICT = 0.05  # Lower is better
    DSUF_STRICT = 0.98

    # Relaxed thresholds - at least half must pass for QuestionableTest
    FBC_RELAXED = 0.85
    SEQI_RELAXED = 0.80
    SOI_RELAXED = 0.10  # Lower is better
    DSUF_RELAXED = 0.90

    # Partial achievement thresholds for force equilibrium
    FBC_PARTIAL = 0.75
    DSUF_PARTIAL = 0.75

    # Partial achievement threshold for strain rate
    SOI_PARTIAL = 0.20

    # Criteria achievement thresholds
    FORCE_EQUILIBRIUM_FBC = 0.90
    FORCE_EQUILIBRIUM_DSUF = 0.90
    CONSTANT_STRAIN_RATE_SOI = 0.10

    def assess_validity_from_metrics(self, metrics: Dict[str, float]) -> Dict[str, any]:
        """
        Assess test validity based on equilibrium metrics.

        Args:
            metrics: Dictionary from StressStrainCalculator.calculate_equilibrium_metrics()
                     Must contain keys: 'FBC', 'SEQI', 'SOI', 'DSUF'

        Returns:
            Dictionary with assessment results:
            {
                'test_validity': URI of validity status,
                'validity_notes': Human-readable description,
                'validity_criteria': List of criteria URIs achieved
            }

        Example:
            >>> assessor = ValidityAssessor()
            >>> metrics = {'FBC': 0.96, 'SEQI': 0.92, 'SOI': 0.04, 'DSUF': 0.99}
            >>> result = assessor.assess_validity_from_metrics(metrics)
            >>> print(result['test_validity'])  # 'dyn:ValidTest'
        """
        # Extract metrics
        fbc = metrics.get('FBC', 0.0)
        seqi = metrics.get('SEQI', 0.0)
        soi = metrics.get('SOI', 1.0)
        dsuf = metrics.get('DSUF', 0.0)

        # Assess force equilibrium
        force_equilibrium = self.assess_force_equilibrium(fbc, dsuf)

        # Assess constant strain rate
        constant_strain_rate = self.assess_strain_rate(soi)

        # Determine overall validity
        validity = self.determine_overall_validity(metrics)

        # Generate validity notes
        notes = self.generate_validity_notes(
            fbc, seqi, soi, dsuf,
            force_equilibrium, constant_strain_rate
        )

        # Get specific criteria URIs that were met
        criteria = self.get_validity_criteria(metrics)

        logger.info(f"Validity assessment complete: {validity}")
        if criteria:
            logger.info(f"Specific criteria met: {', '.join(criteria)}")
        logger.debug(f"Validity notes: {notes}")

        return {
            'test_validity': validity,
            'validity_notes': notes,
            'validity_criteria': criteria if criteria else None
        }

    def get_validity_criteria(self, metrics: Dict[str, float]) -> List[str]:
        """
        Get list of specific validity criteria URIs that were achieved.

        Args:
            metrics: Dictionary with keys: 'FBC', 'SEQI', 'SOI', 'DSUF'

        Returns:
            List of criteria URIs that were achieved:
            - "dyn:ForceEquilibrium" if force equilibrium was achieved
            - "dyn:ConstantStrainRate" if constant strain rate was achieved

        Example:
            >>> assessor = ValidityAssessor()
            >>> metrics = {'FBC': 0.92, 'DSUF': 0.95, 'SOI': 0.08}
            >>> criteria = assessor.get_validity_criteria(metrics)
            >>> print(criteria)  # ['dyn:ForceEquilibrium', 'dyn:ConstantStrainRate']
        """
        criteria = []

        fbc = metrics.get('FBC', 0.0)
        dsuf = metrics.get('DSUF', 0.0)
        soi = metrics.get('SOI', 1.0)

        # Check force equilibrium (strict criteria)
        if fbc >= self.FORCE_EQUILIBRIUM_FBC and dsuf >= self.FORCE_EQUILIBRIUM_DSUF:
            criteria.append('dyn:ForceEquilibrium')

        # Check constant strain rate (strict criteria)
        if soi <= self.CONSTANT_STRAIN_RATE_SOI:
            criteria.append('dyn:ConstantStrainRate')

        return criteria

    def assess_force_equilibrium(self, fbc: float, dsuf: float) -> str:
        """
        Assess if force equilibrium was achieved.

        Args:
            fbc: Force Balance Coefficient (0-1)
            dsuf: Dynamic Stress Uniformity Factor (0-1)

        Returns:
            "achieved", "partially_achieved", or "not_achieved"
        """
        if fbc >= self.FORCE_EQUILIBRIUM_FBC and dsuf >= self.FORCE_EQUILIBRIUM_DSUF:
            return "achieved"
        elif fbc >= self.FBC_PARTIAL or dsuf >= self.DSUF_PARTIAL:
            return "partially_achieved"
        else:
            return "not_achieved"

    def assess_strain_rate(self, soi: float) -> str:
        """
        Assess if constant strain rate was maintained.

        Args:
            soi: Strain Offset Index (0-1), measures strain rate oscillations

        Returns:
            "achieved", "partially_achieved", or "not_achieved"
        """
        if soi <= self.CONSTANT_STRAIN_RATE_SOI:
            return "achieved"
        elif soi <= self.SOI_PARTIAL:
            return "partially_achieved"
        else:
            return "not_achieved"

    def determine_overall_validity(self, metrics: Dict[str, float]) -> str:
        """
        Determine overall test validity based on all equilibrium metrics.

        Uses a multi-level approach:
        - "dyn:ValidTest": ALL 4 metrics meet strict standards
        - "dyn:QuestionableTest": At least half (2/4) of relaxed standards met
        - "dyn:InvalidTest": Less than half of relaxed standards met

        Args:
            metrics: Dictionary with keys: 'FBC', 'SEQI', 'SOI', 'DSUF'

        Returns:
            URI of validity status: "dyn:ValidTest", "dyn:QuestionableTest", or "dyn:InvalidTest"
        """
        fbc = metrics.get('FBC', 0.0)
        seqi = metrics.get('SEQI', 0.0)
        soi = metrics.get('SOI', 1.0)
        dsuf = metrics.get('DSUF', 0.0)

        # Count criteria meeting strict standards
        strict_pass = 0
        if fbc >= self.FBC_STRICT:
            strict_pass += 1
        if seqi >= self.SEQI_STRICT:
            strict_pass += 1
        if soi <= self.SOI_STRICT:
            strict_pass += 1
        if dsuf >= self.DSUF_STRICT:
            strict_pass += 1

        # Count criteria meeting relaxed standards
        relaxed_pass = 0
        if fbc >= self.FBC_RELAXED:
            relaxed_pass += 1
        if seqi >= self.SEQI_RELAXED:
            relaxed_pass += 1
        if soi <= self.SOI_RELAXED:
            relaxed_pass += 1
        if dsuf >= self.DSUF_RELAXED:
            relaxed_pass += 1

        # Decision logic - return ontology URIs
        if strict_pass == 4:
            # ALL strict criteria pass → VALID
            return "dyn:ValidTest"
        elif relaxed_pass >= 2:
            # At least half of relaxed criteria pass → QUESTIONABLE
            return "dyn:QuestionableTest"
        else:
            # Less than half of relaxed criteria pass → INVALID
            return "dyn:InvalidTest"

    def generate_validity_notes(
        self,
        fbc: float,
        seqi: float,
        soi: float,
        dsuf: float,
        force_eq: str,
        const_sr: str
    ) -> str:
        """
        Generate human-readable validity notes based on metrics.

        Args:
            fbc: Force Balance Coefficient
            seqi: Stress Equilibrium Quality Index
            soi: Strain Offset Index
            dsuf: Dynamic Stress Uniformity Factor
            force_eq: Force equilibrium assessment ("achieved", "partially_achieved", "not_achieved")
            const_sr: Constant strain rate assessment

        Returns:
            Human-readable string describing test validity
        """
        notes = []

        # Force equilibrium assessment
        if force_eq == "achieved":
            notes.append(f"Force equilibrium achieved (FBC={fbc:.3f}, DSUF={dsuf:.3f})")
        elif force_eq == "partially_achieved":
            notes.append(f"Force equilibrium partially achieved (FBC={fbc:.3f}, DSUF={dsuf:.3f})")
        else:
            notes.append(f"Force equilibrium NOT achieved (FBC={fbc:.3f}, DSUF={dsuf:.3f})")

        # Strain rate assessment
        if const_sr == "achieved":
            notes.append(f"Constant strain rate maintained (SOI={soi:.3f})")
        elif const_sr == "partially_achieved":
            notes.append(f"Strain rate oscillations detected (SOI={soi:.3f})")
        else:
            notes.append(f"Significant strain rate oscillations (SOI={soi:.3f})")

        # Stress equilibrium assessment
        if seqi >= self.SEQI_STRICT:
            notes.append(f"Good stress equilibrium (SEQI={seqi:.3f})")
        elif seqi >= self.SEQI_RELAXED:
            notes.append(f"Acceptable stress equilibrium (SEQI={seqi:.3f})")
        else:
            notes.append(f"Poor stress equilibrium (SEQI={seqi:.3f})")

        return "; ".join(notes)
