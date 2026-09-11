# System Architecture

## Overview
MobiTrade AI is built as a strictly decoupled, layered research platform:

`
Market Data -> Feature Engine -> Opportunity Scanner -> Source Manager
       │
       ▼
Market Snapshot -> 8 Local LLMs -> Structured Trade Decision
                                            │
                                            ▼
                                       Risk Engine (Deterministic Limits: +10% target / -5% stop / max 20 trades)
                                            │
                                            ▼
                                       Paper Broker (Slippage + Regulatory Transaction Costs)
                                            │
                                            ▼
                                    Portfolio Manager (Daily Compounding)
                                            │
                                            ▼
                                  Model Benchmark & Audit Logger
                                            │
                                            ▼
                                      Daily PDF Reports
`
"@

    "docs\development-roadmap.md" = @"
# Development Roadmap

- Phase 0: Environment validation & discovery (WSL2 Fedora, Python, GPU, Ollama, D: drive).
- Phase 1: Project architecture, domain foundation, risk engine, paper broker, portfolio compounding, and test suite.
- Phase 2-18: Real data ingestion, scanner, model execution, benchmark leaderboards, and PDF generation.
