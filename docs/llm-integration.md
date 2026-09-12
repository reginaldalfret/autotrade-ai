# 8-Model Local LLM Integration & Sequential Scheduler

## Overview
MobiTrade AI integrates 8 small language models running locally on consumer-tier hardware (8 GB system RAM, NVIDIA GeForce RTX 2050 4 GB VRAM). To prevent memory exhaustion and VRAM overflow, the architecture implements a strict **Sequential Execution Scheduler**.

Under this design:
- Only **one** model resides in VRAM at any given time.
- Models execute in a deterministic lifecycle: **Load $\rightarrow$ Infer $\rightarrow$ Validate $\rightarrow$ Record $\rightarrow$ Unload (`keep_alive=0`)**.
- All 8 models receive the **exact same frozen `MarketSnapshot`** per decision cycle.
- The decision cycle operates under frozen simulation time (`as_of_time` does not advance during the 8 model evaluations).
- LLMs act strictly as advisory proposal engines; they have **zero authority to bypass the deterministic `RiskEngine`** or override risk limits and stops.

---

## The 8 Local LLM Candidates

| Model ID | Display Name | Runtime Model Name | Parameters | Target Architecture |
|---|---|---|---|---|
| `nemotron` | NVIDIA Nemotron 3 Nano | `nemotron-3-nano:latest` | ~3.8B | Transformer / Reasoning |
| `qwen` | Qwen 2.5 Coder 1.5B | `qwen2.5-coder:1.5b` | 1.5B | Code / Structured JSON |
| `gemma` | Google Gemma 3 1B | `gemma3:1b` | 1.0B | Dense / Compact |
| `llama` | Meta Llama 3.2 1B | `llama3.2:1b` | 1.2B | General reasoning |
| `granite` | IBM Granite 4 1B-H | `granite4:1b-h` | ~1.5B | Hybrid / Enterprise |
| `phi` | Microsoft Phi-4 Mini | `phi4-mini:latest` | 3.8B | Compact reasoning |
| `smollm` | SmolLM2 1.7B | `smollm2:1.7b` | 1.7B | Lightweight instruction |
| `falcon` | Falcon 3 1B | `falcon3:1b-instruct-q4_K_M` | 1.0B | Quantized Causal LM |

---

## Sequential Execution Lifecycle

```
        ┌───────────────────────────────────────────────┐
        │ Frozen MarketSnapshot (Snapshot ID + Hash)   │
        └───────────────────────┬───────────────────────┘
                                │
                 For each model i in [1..8]:
                                │
                                ▼
                   1. Load Model i into VRAM
                                │
                                ▼
              2. Render Structured Prompt & Schema
                                │
                                ▼
              3. Local Inference (Ollama / Mock)
                                │
                                ▼
              4. Strict JSON Validation & Sanitization
                 - Valid: Parsed LLMDecisionRecord
                 - Malformed/Invalid: Fallback to HOLD (Flagged INVALID)
                                │
                                ▼
              5. Record Decision & Metrics to SQLite
                                │
                                ▼
              6. Evict Model i from VRAM (keep_alive=0)
                                │
                                ▼
                          Next Model
```

---

## Snapshot Immutability & Temporal Fairness

1. **Frozen Input State**: Each model receives the identical `MarketSnapshot` containing:
   - Candidate ranking and metadata (`top_candidates`)
   - Technical features (`features`)
   - Point-in-time external context (`context_items`)
   - Recent historical candles (`recent_candles`)
2. **Deterministic Fairness**:
   - Model 8 sees exactly what Model 1 saw.
   - Simulation time does not advance between Model 1 and Model 8.
   - Market data is never re-polled during a decision cycle.
3. **Account Isolation**:
   - Each model is backed by its own virtual ₹1,000 sub-account.
   - A model's decision affects only its own portfolio.

---

## Decision Validation & Fallback Safety

Models must respond with strict JSON adhering to `configs/prompts/trading_decision_v1.yaml`:
```json
{
  "action": "BUY" | "SELL" | "HOLD",
  "confidence": 0.0 to 1.0,
  "entry_rationale": "Clear rationale string",
  "proposed_stop_loss": float,
  "proposed_target": float,
  "holding_intent": "INTRADAY",
  "reasoning_summary": "Summary string"
}
```

- **Markdown Stripping**: Automatically strips ```json ... ``` code blocks and parses raw json.
- **Fail-Safe Fallback**: Any model output that fails JSON parsing, contains invalid action enums, has non-float confidence, or violates schema boundaries is marked `ValidationStatus.INVALID` and converted to a safe `HOLD` decision.
- **Failure Isolation**: If one model times out or crashes, the scheduler catches the exception, logs failure metrics, unloads the model, and proceeds with the remaining models.

---

## Persistence Schema

Stored in `database/mobitrade.db`:
- `models`: Model registry metadata and configurations.
- `model_runs`: Evaluation run metadata, snapshot ID, status, and aggregate cycle latency.
- `llm_decisions`: Per-model decisions, actions, confidence, rationales, validation statuses, and raw LLM text.
- `inference_metrics`: Load duration, prompt tokens, generation tokens, inference latency, and VRAM residency tracking.

---

## CLI Commands

- `mobitrade llm status`: Shows engine status, hardware constraints, and scheduler configuration.
- `mobitrade llm validate`: Validates prompt template and JSON schema.
- `mobitrade llm models`: Lists all 8 models and checks local runtime availability.
- `mobitrade llm test --model <id>`: Runs a non-trading inference verification test.
- `mobitrade llm evaluate-snapshot --snapshot <id>`: Executes sequential evaluation of all 8 models against a frozen snapshot.
