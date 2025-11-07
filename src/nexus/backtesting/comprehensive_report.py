"""Comprehensive validation report synthesis.

Combines results from all validation methods into actionable insights
and professional reporting for strategy evaluation.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

import numpy as np
from .walk_forward import WalkForwardResult
from .validator import MonteCarloResult
from .regime_validator import RegimeValidationResult
from .holdout_validator import HoldoutValidationResult

logger = logging.getLogger(__name__)


@dataclass
class ValidationSummary:
    """Executive summary of validation results."""
    overall_confidence: str  # "High", "Medium", "Low"
    recommendation: str  # "Proceed", "Caution", "Reject"
    key_strengths: List[str]
    key_weaknesses: List[str]
    risk_assessment: str
    generalization_score: float  # 0-1 scale


@dataclass
class ComprehensiveValidationReport:
    """Complete validation report synthesis."""
    summary: ValidationSummary
    walk_forward_analysis: Optional[WalkForwardResult]
    monte_carlo_analysis: Optional[MonteCarloResult]
    regime_analysis: Optional[RegimeValidationResult]
    holdout_analysis: Optional[HoldoutValidationResult]

    # Derived insights
    overall_performance_score: float  # 0-1 scale
    robustness_score: float  # 0-1 scale
    risk_adjusted_score: float  # 0-1 scale

    # Recommendations
    suggested_improvements: List[str]
    risk_mitigation_strategies: List[str]
    deployment_readiness: str

    # Metadata
    generated_at: datetime
    validation_methods_used: List[str]


class ComprehensiveReportGenerator:
    """Generate comprehensive validation reports.

    Synthesizes results from multiple validation techniques into
    actionable insights and professional recommendations.
    """

    def __init__(self):
        """Initialize report generator."""
        self.generated_at = datetime.now()

    def generate_comprehensive_report(
        self,
        walk_forward: Optional[WalkForwardResult] = None,
        monte_carlo: Optional[MonteCarloResult] = None,
        regime_analysis: Optional[RegimeValidationResult] = None,
        holdout: Optional[HoldoutValidationResult] = None,
        strategy_name: str = "Strategy"
    ) -> ComprehensiveValidationReport:
        """Generate comprehensive validation report.

        Args:
            walk_forward: Walk-forward analysis results
            monte_carlo: Monte Carlo simulation results
            regime_analysis: Multi-regime analysis results
            holdout: Holdout validation results
            strategy_name: Name of the strategy being validated

        Returns:
            ComprehensiveValidationReport: Complete synthesized report
        """
        logger.info(f"Generating comprehensive report for {strategy_name}")

        # Track which methods were used
        methods_used = []
        if walk_forward:
            methods_used.append("walk_forward")
        if monte_carlo:
            methods_used.append("monte_carlo")
        if regime_analysis:
            methods_used.append("regime_analysis")
        if holdout:
            methods_used.append("holdout")

        # Calculate overall scores
        overall_score = self._calculate_overall_performance_score(
            walk_forward, monte_carlo, regime_analysis, holdout
        )

        robustness_score = self._calculate_robustness_score(
            walk_forward, monte_carlo, regime_analysis, holdout
        )

        risk_adjusted_score = self._calculate_risk_adjusted_score(
            walk_forward, monte_carlo, regime_analysis, holdout
        )

        # Generate summary
        summary = self._generate_validation_summary(
            overall_score, robustness_score, risk_adjusted_score,
            walk_forward, monte_carlo, regime_analysis, holdout
        )

        # Generate recommendations
        improvements = self._generate_suggested_improvements(
            walk_forward, monte_carlo, regime_analysis, holdout
        )

        risk_mitigation = self._generate_risk_mitigation_strategies(
            walk_forward, monte_carlo, regime_analysis, holdout
        )

        deployment_readiness = self._assess_deployment_readiness(
            overall_score, robustness_score, risk_adjusted_score
        )

        report = ComprehensiveValidationReport(
            summary=summary,
            walk_forward_analysis=walk_forward,
            monte_carlo_analysis=monte_carlo,
            regime_analysis=regime_analysis,
            holdout_analysis=holdout,
            overall_performance_score=overall_score,
            robustness_score=robustness_score,
            risk_adjusted_score=risk_adjusted_score,
            suggested_improvements=improvements,
            risk_mitigation_strategies=risk_mitigation,
            deployment_readiness=deployment_readiness,
            generated_at=self.generated_at,
            validation_methods_used=methods_used
        )

        logger.info(f"Report generated with overall score: {overall_score:.2f}")
        return report

    def _calculate_overall_performance_score(
        self,
        walk_forward: Optional[WalkForwardResult],
        monte_carlo: Optional[MonteCarloResult],
        regime: Optional[RegimeValidationResult],
        holdout: Optional[HoldoutValidationResult]
    ) -> float:
        """Calculate overall performance score (0-1).

        Args:
            walk_forward: Walk-forward results
            monte_carlo: Monte Carlo results
            regime: Regime analysis results
            holdout: Holdout results

        Returns:
            Overall performance score
        """
        scores = []
        weights = []

        # Walk-forward out-of-sample performance
        if walk_forward and walk_forward.out_of_sample_performance.sharpe_ratio > 0:
            wf_score = min(1.0, walk_forward.out_of_sample_performance.sharpe_ratio / 2.0)  # Scale to 0-1
            scores.append(wf_score)
            weights.append(0.3)

        # Monte Carlo failure rate (inverse)
        if monte_carlo:
            mc_score = 1.0 - monte_carlo.failure_rate  # Lower failure rate = higher score
            scores.append(mc_score)
            weights.append(0.2)

        # Regime adaptability
        if regime:
            regime_score = regime.regime_adaptability_score
            scores.append(regime_score)
            weights.append(0.2)

        # Holdout generalization
        if holdout:
            holdout_score = holdout.generalization_score
            scores.append(holdout_score)
            weights.append(0.3)

        if not scores:
            return 0.0

        # Weighted average
        if weights:
            return sum(s * w for s, w in zip(scores, weights)) / sum(weights)
        else:
            return sum(scores) / len(scores)

    def _calculate_robustness_score(
        self,
        walk_forward: Optional[WalkForwardResult],
        monte_carlo: Optional[MonteCarloResult],
        regime: Optional[RegimeValidationResult],
        holdout: Optional[HoldoutValidationResult]
    ) -> float:
        """Calculate robustness score (0-1).

        Measures consistency and stability across different conditions.
        """
        scores = []

        # Walk-forward stability
        if walk_forward and walk_forward.stability_score > 0:
            scores.append(walk_forward.stability_score)

        # Monte Carlo consistency (inverse of distribution spread)
        if monte_carlo and len(monte_carlo.sharpe_distribution) > 0:
            sharpe_std = np.std(monte_carlo.sharpe_distribution)
            sharpe_mean = np.mean(monte_carlo.sharpe_distribution)
            if sharpe_mean > 0:
                cv = sharpe_std / sharpe_mean  # Coefficient of variation
                robustness = 1 / (1 + cv)  # Lower CV = higher robustness
                scores.append(robustness)

        # Regime stability
        if regime and regime.regime_stability_score > 0:
            scores.append(regime.regime_stability_score)

        # Holdout stability
        if holdout and holdout.stability_score > 0:
            scores.append(holdout.stability_score)

        return sum(scores) / len(scores) if scores else 0.0

    def _calculate_risk_adjusted_score(
        self,
        walk_forward: Optional[WalkForwardResult],
        monte_carlo: Optional[MonteCarloResult],
        regime: Optional[RegimeValidationResult],
        holdout: Optional[HoldoutValidationResult]
    ) -> float:
        """Calculate risk-adjusted performance score (0-1).

        Focuses on risk-adjusted returns and drawdown management.
        """
        scores = []

        # Walk-forward risk-adjusted returns
        if walk_forward:
            oos_perf = walk_forward.out_of_sample_performance
            if oos_perf.max_drawdown > 0:
                calmar = oos_perf.annualized_return / oos_perf.max_drawdown
                risk_score = min(1.0, calmar / 2.0)  # Scale Calmar ratio to 0-1
                scores.append(risk_score)

        # Monte Carlo risk metrics
        if monte_carlo:
            # Lower VaR and CVaR = higher score
            var_score = 1.0 - min(1.0, abs(monte_carlo.var_95) * 5)  # Scale VaR
            scores.append(var_score)

        # Regime risk-adjusted alpha
        if regime:
            positive_alpha_regimes = sum(1 for alpha in regime.regime_risk_adjusted_alpha.values() if alpha > 0)
            total_regimes = len(regime.regime_risk_adjusted_alpha)
            if total_regimes > 0:
                alpha_score = positive_alpha_regimes / total_regimes
                scores.append(alpha_score)

        return sum(scores) / len(scores) if scores else 0.0

    def _generate_validation_summary(
        self,
        overall_score: float,
        robustness_score: float,
        risk_score: float,
        walk_forward: Optional[WalkForwardResult],
        monte_carlo: Optional[MonteCarloResult],
        regime: Optional[RegimeValidationResult],
        holdout: Optional[HoldoutValidationResult]
    ) -> ValidationSummary:
        """Generate executive summary of validation results."""

        # Determine overall confidence
        avg_score = (overall_score + robustness_score + risk_score) / 3

        if avg_score >= 0.7:
            confidence = "High"
        elif avg_score >= 0.5:
            confidence = "Medium"
        else:
            confidence = "Low"

        # Generate recommendation
        if avg_score >= 0.7:
            recommendation = "Proceed"
        elif avg_score >= 0.4:
            recommendation = "Caution"
        else:
            recommendation = "Reject"

        # Identify key strengths
        strengths = []
        if overall_score >= 0.6:
            strengths.append("Strong overall performance")
        if robustness_score >= 0.6:
            strengths.append("Consistent across different conditions")
        if risk_score >= 0.6:
            strengths.append("Good risk-adjusted returns")
        if walk_forward and walk_forward.stability_score >= 0.7:
            strengths.append("Stable parameter optimization")
        if monte_carlo and monte_carlo.failure_rate <= 0.3:
            strengths.append("Robust to random variations")
        if regime and regime.regime_adaptability_score >= 0.6:
            strengths.append("Works across market regimes")
        if holdout and not holdout.overfitting_detected:
            strengths.append("Good generalization to unseen data")

        # Identify key weaknesses
        weaknesses = []
        if overall_score < 0.4:
            weaknesses.append("Weak overall performance")
        if robustness_score < 0.4:
            weaknesses.append("Inconsistent results")
        if risk_score < 0.4:
            weaknesses.append("Poor risk management")
        if walk_forward and walk_forward.stability_score < 0.3:
            weaknesses.append("Unstable parameter optimization")
        if monte_carlo and monte_carlo.failure_rate > 0.6:
            weaknesses.append("High failure rate in simulations")
        if regime and regime.regime_adaptability_score < 0.3:
            weaknesses.append("Limited regime adaptability")
        if holdout and holdout.overfitting_detected:
            weaknesses.append("Signs of overfitting detected")

        # Risk assessment
        if risk_score >= 0.7:
            risk_assessment = "Low risk - well-managed drawdowns and volatility"
        elif risk_score >= 0.4:
            risk_assessment = "Moderate risk - acceptable but monitor closely"
        else:
            risk_assessment = "High risk - significant drawdown and volatility concerns"

        # Generalization score
        generalization = (robustness_score + (1 - (holdout.overfitting_score if holdout else 0.5))) / 2

        return ValidationSummary(
            overall_confidence=confidence,
            recommendation=recommendation,
            key_strengths=strengths,
            key_weaknesses=weaknesses,
            risk_assessment=risk_assessment,
            generalization_score=generalization
        )

    def _generate_suggested_improvements(
        self,
        walk_forward: Optional[WalkForwardResult],
        monte_carlo: Optional[MonteCarloResult],
        regime: Optional[RegimeValidationResult],
        holdout: Optional[HoldoutValidationResult]
    ) -> List[str]:
        """Generate suggested improvements based on validation results."""

        improvements = []

        # Walk-forward improvements
        if walk_forward and walk_forward.stability_score < 0.5:
            improvements.append("Improve parameter stability - consider constraining parameter ranges or using regularization")

        # Monte Carlo improvements
        if monte_carlo and monte_carlo.failure_rate > 0.4:
            improvements.append("Reduce strategy brittleness - add position sizing limits and stop-loss rules")

        # Regime improvements
        if regime and regime.regime_adaptability_score < 0.5:
            improvements.append("Enhance regime adaptability - add market regime filters or dynamic parameter adjustment")

        # Holdout improvements
        if holdout and holdout.overfitting_detected:
            improvements.append("Address overfitting - simplify strategy logic, reduce parameter count, or increase regularization")

        # General improvements
        if not any([walk_forward, monte_carlo, regime, holdout]):
            improvements.append("Implement comprehensive validation - add walk-forward, Monte Carlo, and regime testing")

        # Performance improvements
        if walk_forward and walk_forward.out_of_sample_performance.sharpe_ratio < 0.5:
            improvements.append("Improve risk-adjusted returns - focus on Sharpe ratio optimization rather than total returns")

        if monte_carlo and abs(monte_carlo.var_95) > 0.15:  # 15% VaR
            improvements.append("Reduce tail risk - implement maximum drawdown limits and diversification")

        return improvements if improvements else ["Strategy validation is comprehensive - monitor performance in live trading"]

    def _generate_risk_mitigation_strategies(
        self,
        walk_forward: Optional[WalkForwardResult],
        monte_carlo: Optional[MonteCarloResult],
        regime: Optional[RegimeValidationResult],
        holdout: Optional[HoldoutValidationResult]
    ) -> List[str]:
        """Generate risk mitigation strategies."""

        mitigations = []

        # Based on Monte Carlo results
        if monte_carlo:
            if monte_carlo.failure_rate > 0.3:
                mitigations.append("Implement position sizing based on Monte Carlo VaR estimates")
            if monte_carlo.max_drawdown_distribution.mean() > 0.2:
                mitigations.append("Add maximum drawdown stops based on historical stress testing")

        # Based on regime analysis
        if regime:
            worst_regime = regime.worst_regime
            if worst_regime:
                mitigations.append(f"Add regime filter to reduce exposure during {worst_regime} market conditions")

        # Based on walk-forward
        if walk_forward and walk_forward.stability_score < 0.5:
            mitigations.append("Use ensemble of parameter sets from walk-forward optimization rather than single optimal set")

        # Based on holdout
        if holdout and holdout.overfitting_detected:
            mitigations.append("Implement cross-validation during live trading to detect overfitting early")

        # General risk management
        mitigations.extend([
            "Diversify across uncorrelated assets",
            "Implement progressive position sizing",
            "Regular strategy re-validation every 3-6 months",
            "Maintain emergency stop-loss at portfolio level"
        ])

        return list(set(mitigations))  # Remove duplicates

    def _assess_deployment_readiness(
        self,
        overall_score: float,
        robustness_score: float,
        risk_score: float
    ) -> str:
        """Assess deployment readiness."""

        avg_score = (overall_score + robustness_score + risk_score) / 3

        if avg_score >= 0.75:
            return "Ready for full deployment"
        elif avg_score >= 0.6:
            return "Ready for limited deployment with monitoring"
        elif avg_score >= 0.4:
            return "Paper trading recommended before live deployment"
        else:
            return "Not ready for deployment - requires significant improvements"

    def export_report_to_dict(self, report: ComprehensiveValidationReport) -> Dict[str, Any]:
        """Export report to dictionary format for serialization."""

        return {
            "summary": {
                "overall_confidence": report.summary.overall_confidence,
                "recommendation": report.summary.recommendation,
                "key_strengths": report.summary.key_strengths,
                "key_weaknesses": report.summary.key_weaknesses,
                "risk_assessment": report.summary.risk_assessment,
                "generalization_score": report.summary.generalization_score
            },
            "scores": {
                "overall_performance": report.overall_performance_score,
                "robustness": report.robustness_score,
                "risk_adjusted": report.risk_adjusted_score
            },
            "recommendations": {
                "suggested_improvements": report.suggested_improvements,
                "risk_mitigation_strategies": report.risk_mitigation_strategies,
                "deployment_readiness": report.deployment_readiness
            },
            "metadata": {
                "generated_at": report.generated_at.isoformat(),
                "validation_methods_used": report.validation_methods_used
            }
        }

    def print_executive_summary(self, report: ComprehensiveValidationReport) -> None:
        """Print executive summary to console."""

        print("\n" + "="*60)
        print("COMPREHENSIVE STRATEGY VALIDATION REPORT")
        print("="*60)

        print(f"\nOVERALL CONFIDENCE: {report.summary.overall_confidence}")
        print(f"RECOMMENDATION: {report.summary.recommendation}")
        print(f"DEPLOYMENT READINESS: {report.deployment_readiness}")

        print(f"\nPERFORMANCE SCORES:")
        print(f"  Overall Performance: {report.overall_performance_score:.2f}")
        print(f"  Robustness: {report.robustness_score:.2f}")
        print(f"  Risk-Adjusted: {report.risk_adjusted_score:.2f}")
        print(f"  Generalization: {report.summary.generalization_score:.2f}")

        print(f"\nKEY STRENGTHS:")
        for strength in report.summary.key_strengths:
            print(f"  ✓ {strength}")

        print(f"\nKEY WEAKNESSES:")
        for weakness in report.summary.key_weaknesses:
            print(f"  ✗ {weakness}")

        print(f"\nRISK ASSESSMENT:")
        print(f"  {report.summary.risk_assessment}")

        if report.suggested_improvements:
            print(f"\nSUGGESTED IMPROVEMENTS:")
            for improvement in report.suggested_improvements:
                print(f"  • {improvement}")

        print(f"\nVALIDATION METHODS USED: {', '.join(report.validation_methods_used)}")
        print(f"REPORT GENERATED: {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
