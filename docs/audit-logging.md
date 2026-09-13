# Cryptographic Audit Logging Layer

## Overview
The AutoTrade AI Audit Logging Layer provides a deterministic, tamper-evident cryptographic record of all platform activities. By employing sequential sequence numbering and continuous SHA-256 hash chaining anchored to an immutable Genesis Block, AutoTrade AI guarantees institutional-grade mathematical verification without allowing manual record manipulation or retrospective tampering.

---

## Architectural Principles

1. **Strict Append-Only Policy**:
   - The `audit_events` table in SQLite accepts `INSERT` and `SELECT` operations only.
   - Any SQL `UPDATE` or `DELETE` is prohibited by architecture and verified by continuous chain hashing.
2. **Deterministic Hash Chaining**:
   - Every event references the hash of the immediately preceding event.
   - Genesis block ($H_0$) is fixed at 64 hexadecimal zeros:
     $$H_0 = \text{"0" \times 64}$$
   - For sequence number $n \ge 1$:
     $$H_n = \text{SHA-256}(\text{CanonicalJSON}(E_n) + H_{n-1})$$
3. **Canonical JSON Serialization**:
   - Dictionary keys sorted recursively.
   - Uniform separators `(",", ":")` with zero extraneous whitespace.
   - Floating point numbers rounded consistently to 8 decimal places.
   - Datetimes normalized to ISO 8601 UTC.
   - Enums resolved to string literals.

---

## Audit Event Schema

```sql
CREATE TABLE audit_events (
    event_id TEXT PRIMARY KEY,
    sequence_number INTEGER NOT NULL UNIQUE,
    session_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    model_id TEXT,
    trade_id TEXT,
    order_id TEXT,
    payload_json TEXT NOT NULL,
    previous_event_hash TEXT NOT NULL,
    event_hash TEXT NOT NULL
);
```

### Indexed Columns
- `sequence_number`: Quick sequential scans and continuity checks.
- `(session_id, sequence_number)`: Session-specific audit trail reconstruction.
- `model_id`: Per-model audit event filtering.
- `event_type`: Categorical event filtering.
- `trade_id`: Complete trade lifecycle tracing from proposal to exit.

---

## Supported Lifecycle Event Types (27 Events)

| Lifecycle Stage | Event Type | Description |
| :--- | :--- | :--- |
| **Session** | `SESSION_STARTED` | Daily trading session initialized (09:15 IST) |
| | `SESSION_CLOSED` | Daily trading session terminated and locked (15:30 IST) |
| | `SNAPSHOT_CREATED` | Market snapshot generated from live 5m candle |
| **Model Inference** | `LLM_RUN_STARTED` | Sequential scheduler initiated inference for model |
| | `LLM_RUN_COMPLETED` | Model inference finished successfully |
| | `LLM_RUN_FAILED` | Model inference errored or timed out |
| | `DECISION_CREATED` | Model produced candidate trade decision |
| | `DECISION_REJECTED` | Decision failed schema or confidence validation |
| | `DECISION_VALIDATED` | Decision successfully passed output validation |
| **Risk Engine** | `RISK_CHECK_PASSED` | Proposal passed all 7 deterministic risk rules |
| | `RISK_CHECK_FAILED` | Proposal blocked by risk limits (e.g. daily loss, sizing) |
| **Broker Execution** | `ORDER_CREATED` | Virtual order dispatched to PaperBroker |
| | `ORDER_REJECTED` | Order rejected (e.g. zero quantity, post-15:15) |
| | `ORDER_FILLED` | Order executed with statutory fees and slippage |
| **Position Lifecycle** | `POSITION_OPENED` | New intraday position opened |
| | `POSITION_UPDATED` | Position modified or marked-to-market |
| | `POSITION_CLOSED` | Position fully squared off |
| **Exit Triggers** | `STOP_LOSS_TRIGGERED` | Hard stop-loss price hit |
| | `TRAILING_STOP_TRIGGERED` | Dynamic trailing stop floor triggered |
| | `DAILY_TARGET_REACHED` | Model reached +10% daily equity target (locked) |
| | `DAILY_STOP_TRIGGERED` | Model breached -5% daily equity stop (locked) |
| | `AUTO_SQUARE_OFF` | Mandatory 15:15 IST intraday square-off executed |
| **Accounting** | `PORTFOLIO_MARK` | Mark-to-market snapshot of portfolio equity |
| | `DAILY_FINALIZED` | Session closed, performance metrics persisted |
| | `COMPOUNDING_APPLIED` | Realized balance compounded to next day's starting cash |
| **Reporting** | `REPORT_GENERATED` | Daily PDF executive report compiled and hashed |
| | `REPORT_FAILED` | Daily PDF compilation failed (isolated without trade rollback) |

---

## Tamper Detection & Verification Algorithm

The verification function `verify_audit_chain(events)` performs four strict tests across the sequence:
1. **Genesis Verification**: Confirms sequence 1 has `previous_event_hash == '0'*64`.
2. **Sequence Monotonicity**: Ensures sequence numbers strictly increment by 1 with zero gaps or duplicates.
3. **Chain Continuity**: Verifies each event's `previous_event_hash` matches `event_hash` of the preceding record.
4. **Payload Recalculation**: Recomputes `SHA256(canonical_json(core) + previous_event_hash)` for every row and flags discrepancies.

---

## CLI Usage

```bash
# Check audit logger summary and latest hash
mobitrade audit status

# Verify cryptographic chain integrity
mobitrade audit verify

# Verify specific session
mobitrade audit verify --session sim_20260911

# Inspect full canonical payload of single event
mobitrade audit inspect evt_78a1bc23e4f5

# View audit trail for a session
mobitrade audit session sim_20260911

# Trace complete lifecycle of a single trade
mobitrade audit trade trd_9a2f1b4c
```
