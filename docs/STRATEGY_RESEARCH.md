# Strategy Research & Design Document

## Executive Summary

Based on academic literature review, momentum strategies demonstrate robust empirical evidence across multiple studies, outperforming mean-reversion strategies particularly in volatile markets. The Jegadeesh-Titman momentum strategy is selected as the primary candidate due to its:

- Strong statistical significance (p < 0.01 in original and follow-up studies)
- Persistence across different market regimes
- Clear economic intuition (underreaction to information)
- Survival of transaction costs in backtests
- Multiple independent replications

## Academic Literature Review

### Key Momentum Papers
- **Jegadeesh & Titman (1993)**: Original evidence of momentum profitability. 6-12 month formation periods with 3-6 month holding periods generate 0.95% monthly returns (t-stat 4.04).
- **Jegadeesh & Titman (2001)**: Momentum profits persist into 1990s, not data-snooping artifact. Supports behavioral explanations over risk-based.
- **Carhart (1997)**: Momentum as fourth factor in asset pricing models.
- **Asness et al. (2013)**: Momentum works across asset classes, not just equities.

### Key Mean-Reversion Papers
- **DeBondt & Thaler (1985)**: Long-term reversal (3-5 years) exists but economically small.
- **Jegadeesh (1990)**: Short-term reversal exists but transaction costs erode profits.
- **Moskowitz et al. (2012)**: Time-series momentum shows reversion at longer horizons but momentum dominates shorter ones.

### Comparative Studies
- **Balvers & Wu (2006)**: Momentum and mean-reversion coexist across international markets. Momentum stronger in bull markets, reversion in bear markets.
- **Barroso & Santa-Clara (2015)**: Momentum crashes exist but strategy survives with proper risk management.

## Strategy Evaluation Criteria

### Momentum Strategy Assessment
- **Statistical Significance**: p < 0.01 in multiple studies
- **Economic Intuition**: Underreaction to news/information flow
- **Robustness**: Works across US, international, commodities, currencies
- **Survivorship Bias**: Controlled in modern studies
- **Transaction Costs**: Survives 0.5-1% round-trip costs
- **Market Regimes**: Performs better in trending markets

### Mean-Reversion Strategy Assessment
- **Statistical Significance**: Mixed (strong short-term, weak long-term)
- **Economic Intuition**: Overreaction correction
- **Robustness**: Limited to certain market conditions
- **Survivorship Bias**: Problematic for long-term studies
- **Transaction Costs**: Erodes profits in short-term strategies
- **Market Regimes**: Works in range-bound, not trending markets

## Selected Strategy: Momentum

**Why Momentum?**
1. Strongest empirical evidence base
2. Clear behavioral foundation (underreaction)
3. Robust across time periods and markets
4. Better performance in volatile assets
5. Simpler implementation than mean-reversion

**Risks Identified:**
- Momentum crashes in extreme bear markets
- Higher volatility than buy-and-hold
- Potential regime dependence
- Implementation requires strict discipline

## Mechanical Rules Definition

### Entry Rules
- Rank stocks by cumulative return over past 6 months
- Buy top 10% performers (winners)
- Short bottom 10% performers (losers)
- Equal-weight portfolio

### Holding Period
- Hold positions for 6 months
- Rebalance monthly by adding/removing positions

### Exit Rules
- Close all positions after 6-month holding period
- No stop-losses or take-profits (maintain mechanical purity)

## Parameter Specification

**Formation Period:** 6 months
- Justification: Balances information content vs noise
- Economics: Captures fundamental momentum without over-reliance on short-term noise

**Holding Period:** 6 months
- Justification: Allows strategy to capture full momentum effect
- Economics: Matches typical information diffusion timelines

**Portfolio Size:** 10% winners + 10% losers
- Justification: Concentrates on strongest signals
- Economics: Extreme deciles capture most persistent effects

**Rebalancing:** Monthly
- Justification: Maintains exposure while controlling turnover
- Economics: Balances transaction costs vs signal freshness

## Theoretical Edge

**Mechanism:** Investors underreact to new information, causing gradual price adjustments. Momentum captures this by riding the trend until full adjustment.

**Why Persistent:** Behavioral biases (anchoring, confirmation bias) cause systematic underreaction. Market efficiency incomplete due to limits-to-arbitrage.

**Risk Factors:**
- Macro shocks can reverse trends abruptly
- Liquidity constraints during crises
- Correlation with market beta in down markets

## Falsifiable Hypotheses

1. **H1:** Momentum strategy generates positive excess returns (α > 0) after controlling for Fama-French factors.
2. **H2:** Returns are higher in bull markets vs bear markets.
3. **H3:** Strategy survives 1% round-trip transaction costs.
4. **H4:** Out-of-sample performance matches in-sample results.

## Statistical Power Analysis

**Effect Size:** Based on JT (1993), monthly return 0.95% (9.4% annualized)
**Volatility:** ~4% monthly for momentum portfolios
**Sample Size:** 300+ months needed for 80% power to detect effect at p<0.05
**Current Data:** 50+ years available → sufficient power

## Transaction Cost Analysis

**Estimated Costs:**
- Commissions: $0.005/share (0.05% round-trip)
- Bid-ask spread: 0.1-0.2% for liquid stocks
- Market impact: 0.2-0.5% for portfolio turnover
- **Total:** 0.4-0.8% round-trip

**Strategy Viability:** Momentum edge (0.95%/month) exceeds costs, leaving ~0.5% net return.

## Implementation Plan

1. Data requirements: Daily price data for broad universe (S&P 500 minimum)
2. Backtesting: Walk-forward optimization to avoid overfitting
3. Risk management: Position limits, drawdown controls
4. Validation: Out-of-sample testing across market regimes

## References

1. Jegadeesh, N., & Titman, S. (1993). Returns to buying winners and selling losers: Implications for stock market efficiency. The Journal of Finance, 48(1), 65-91.

2. Jegadeesh, N., & Titman, S. (2001). Profitability of momentum strategies: An evaluation of alternative explanations. The Journal of Finance, 56(2), 699-720.

3. Carhart, M. M. (1997). On persistence in mutual fund performance. The Journal of Finance, 52(1), 57-82.

4. Asness, C. S., Moskowitz, T. J., & Pedersen, L. H. (2013). Value and momentum everywhere. The Journal of Finance, 68(3), 929-985.

5. Balvers, R., & Wu, Y. (2006). Momentum and mean reversion across national equity markets. Journal of Empirical Finance, 13(1), 24-48.

6. Barroso, P., & Santa-Clara, P. (2015). Momentum has its moments. The Journal of Finance, 116(1), 111-120.

## Next Steps

- Implement strategy in code following Phase 2.4 requirements
- Conduct statistical backtesting per Phase 2.5
- Validate against roadmap success criteria
