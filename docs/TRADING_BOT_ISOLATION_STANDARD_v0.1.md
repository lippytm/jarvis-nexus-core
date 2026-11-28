# Trading Bot Isolation Standard v0.1

**Owner:** Intergalactic Corporate Services LLC  
**Date:** 2026-10-26  
**Status:** Architecture / R&D standard  
**Live-money status:** DISABLED / NOT AUTHORIZED BY THIS DOCUMENT

## 1. Core rule

**One Trading Bot = One Complete Separate System = One Dedicated AI Sandbox.**

A category-level sandbox is not sufficient. Crypto Bot 001 and Crypto Bot 002 are separate security, memory, risk, data and execution systems even if they trade the same asset class.

## 2. Bot system boundary

Each bot must own its own:

1. Bot identity / Agent Passport.
2. Mission and strategy definition.
3. Sandbox/VM/container boundary.
4. Network policy.
5. Credentials/service account.
6. Market-data adapter.
7. Local data cache.
8. Feature/indicator pipeline.
9. Strategy implementation/version.
10. Historical backtest engine.
11. Out-of-sample / walk-forward evaluator.
12. Paper execution simulator.
13. Paper ledger/account state.
14. Deterministic risk engine.
15. Pre-trade controls.
16. Post-trade controls.
17. MemPalace namespace.
18. Logs/traces/evidence.
19. Dashboard.
20. Kill switch.
21. Incident runbook.
22. Release/approval state.

No component that can mutate state is shared across bots unless it is explicitly designed as a multi-tenant service with hard isolation and separate identities.

## 3. Control Tower rule

The Trading Control Tower is read-only by default.

It may:
- compare bot performance;
- display risk;
- display evidence;
- rank experiments;
- identify correlated failures;
- stop or quarantine bots through a separately authorized control.

It must not:
- silently move capital between bots;
- copy one bot's credentials to another;
- merge strategy state without review;
- write into another bot's memory namespace;
- bypass bot-specific risk checks.

## 4. Lifecycle

A bot progresses independently:

`DESIGN`  
-> `BACKTEST`  
-> `STRESS_TEST`  
-> `OUT_OF_SAMPLE`  
-> `PAPER`  
-> `SHADOW_REVIEW`  
-> `BLOCKED` or `ELIGIBLE_FOR_HUMAN_REVIEW`

No live-money state is created by this standard.

A different bot's success cannot promote this bot.

## 5. AI role

The AI model may:
- summarize research;
- propose hypotheses;
- draft strategy code;
- explain indicators;
- diagnose test failures;
- propose a trade candidate;
- write a post-run review.

The AI model must not be the final risk authority.

**Model output = proposal.**

A deterministic rules engine must independently validate every candidate action.

## 6. Deterministic pre-trade controls

At minimum, the sandbox design should support:

- instrument/symbol allowlist;
- maximum order size;
- maximum order value;
- maximum orders per time interval;
- price-band checks;
- maximum position size;
- maximum gross/net exposure;
- maximum number of positions;
- daily loss ceiling;
- drawdown ceiling;
- duplicate/replay detection;
- stale-data detection;
- market/session state validation;
- fee/slippage assumptions;
- minimum liquidity rules where relevant;
- timeout/circuit-breaker behavior.

Any failed mandatory check blocks the candidate.

## 7. Automatic stop conditions

Immediately stop the bot if:

- market data is stale or inconsistent;
- risk telemetry is unavailable;
- clock/time synchronization fails materially;
- credentials change unexpectedly;
- network policy is breached;
- strategy hash/version differs from approved evidence;
- repeated API ambiguity occurs;
- duplicate orders are detected;
- daily loss/drawdown limit is reached;
- evidence logging fails;
- unauthorized cross-bot communication is detected.

Stopping should revoke network/credentials where feasible, not merely ask the model to stop.

## 8. Data-quality controls

Backtests must account for:

- timestamps/time zones;
- missing bars/ticks;
- delistings;
- splits/dividends/corporate actions where relevant;
- symbol changes;
- survivorship bias;
- look-ahead bias;
- leakage from future labels;
- fees;
- spread;
- slippage;
- latency assumptions.

The dataset revision/hash belongs in the evidence record.

## 9. Model-risk controls

For AI-assisted strategies:

- keep training/tuning data separate from evaluation data;
- use walk-forward and out-of-sample periods;
- track prompt/model/strategy versions;
- test regime changes;
- test noisy or contradictory news;
- treat news/social/web content as untrusted data;
- block prompt injection from external text;
- do not let external prose directly call execution tools;
- compare against simple baselines;
- record failed hypotheses, not only winners.

## 10. Sandbox architecture

Recommended high-level boundary:

`Market Data -> Read-only Adapter -> Bot Sandbox -> Strategy Proposal -> Deterministic Risk Engine -> Paper Executor -> Evidence Ledger`

Network:
- deny by default;
- allowlist only required data/provider endpoints;
- separate research browsing from execution network paths.

Filesystem:
- bot-specific writable volume;
- common reference data read-only where possible.

Credentials:
- bot-specific;
- environment-specific;
- least privilege;
- rotated/revocable;
- never placed in prompts or exported logs.

## 11. MemPalace namespace

Example:

`mempalace/trading/crypto/bot-001/`  
`mempalace/trading/crypto/bot-002/`  
`mempalace/trading/penny/bot-001/`  
`mempalace/trading/forex/bot-001/`

A bot may read approved shared research from:

`mempalace/trading/shared-research/`

but shared research is not executable instruction.

Cross-bot writes require an explicit service/API and policy decision.

## 12. Evidence record

Every run stores:

- bot ID;
- strategy ID/version/hash;
- model/provider/version if used;
- dataset ID/hash/window;
- sandbox version;
- risk policy version;
- start/end time;
- candidate decisions;
- blocked decisions and reasons;
- fills simulated;
- fees/slippage assumptions;
- P&L;
- drawdown;
- exposure;
- errors/retries;
- stop conditions;
- reviewer state.

Backtest, paper and any future live results must be labeled separately.

## 13. Comparison metrics

Do not optimize on raw return alone.

Track:
- return;
- volatility;
- drawdown;
- hit rate;
- turnover;
- transaction costs;
- exposure;
- concentration;
- number of trades;
- stability across periods;
- performance vs simple baseline;
- failure count;
- rule-block count.

A strategy that earns less but obeys constraints and generalizes may be more useful than an overfit strategy with high historical return.

## 14. Penny-stock educational sandbox

Current owner-defined research constraints may be represented in the paper sandbox as:

- model account: $100;
- maximum 5 positions;
- maximum allocation per stock: $20;
- maximum modeled trade: $5;
- paper/simulation first.

These are experiment constraints, not a recommendation to purchase any specific security.

## 15. Crypto sandbox

Keep crypto-specific elements isolated:
- 24/7 market timing;
- exchange/provider differences;
- wallet/custody concepts;
- chain/network state;
- fees;
- market fragmentation.

Blockchain education and trading research should remain separable. Understanding a blockchain is not evidence that a token is a good investment.

## 16. Forex sandbox

Keep forex-specific elements isolated:
- pairs;
- sessions;
- quote conventions;
- rollover/financing assumptions;
- leverage assumptions;
- spread/latency behavior.

Do not copy equity or crypto risk assumptions into forex without validation.

## 17. Security tests

Before higher permission levels:

- prompt-injection test;
- stale-data test;
- duplicated-message test;
- malformed-price test;
- network-deny test;
- credential-revocation test;
- kill-switch test;
- cross-bot isolation test;
- logging-failure test;
- strategy-hash mismatch test;
- risk-limit breach test.

## 18. Human review packet

Before any future real-money discussion, the reviewer should receive:

- exact strategy;
- code hash;
- data and evaluation windows;
- all performance metrics;
- known weaknesses;
- stress-test results;
- paper-trading history;
- risk limits;
- security review;
- incident/kill-switch evidence;
- provider/broker constraints;
- legal/compliance considerations;
- explicit statement that historical or simulated performance does not guarantee future returns.

## 19. ANIMA/RPG educational mapping

The trading system is also an educational environment:

**IF** — define a hypothesis.  
**Maybe** — identify alternate explanations.  
**Why Not?** — run a bounded experiment.  
**Don't Do That** — deterministic risk gate blocks a dangerous action.  
**I Told You Not To Do That!** — diagnose a failed or overfit strategy, repair and retest.

XP is awarded for reproducibility, risk discipline, evidence quality and detecting mistakes—not only simulated profit.

## 20. Acceptance criteria for one bot system

A bot sandbox is considered a valid prototype only when:

- identity is unique;
- writable state is isolated;
- credentials are isolated;
- strategy is versioned;
- deterministic risk checks exist;
- backtest is reproducible;
- out-of-sample test exists;
- paper execution works;
- stop conditions are tested;
- cross-bot isolation is tested;
- evidence is retained;
- human review state is explicit.

## References

- CFTC AI Trading Bots advisory: https://www.cftc.gov/LearnAndProtect/AdvisoriesAndArticles/AITradingBots.html
- OpenAI containment engineering: https://openai.com/index/securing-our-frontier-model-training-environment/
- NIST AI RMF: https://www.nist.gov/itl/ai-risk-management-framework
- OWASP Agentic Security Initiative: https://genai.owasp.org/initiatives/agentic-security-initiative/

**Rule:** Research before capital. Simulation before execution. Evidence before authority.
