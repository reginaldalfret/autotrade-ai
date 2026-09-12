# MobiTrade AI — External Financial Information & Point-in-Time Context Layer (Phase 5)

## Overview
The **External Financial Information Layer** enriches quantitative scanner candidates with structured external financial information, official exchange disclosures, regulatory filings, corporate announcements, and macroeconomic releases.
Crucially, this layer operates under strict **point-in-time temporal safety** to prevent lookahead bias during historical replay and evaluation of local LLMs.

### Core Architecture Principles
1. **Context Augmentation Only**: The external layer provides qualitative context to accompany quantitative features; it does NOT replace technical indicators, place trades, or invoke LLMs.
2. **Strict Point-in-Time Gating**: For any decision timestamp $T$, only information with:
   $$\text{available\_at} \le T$$
   can be returned. Future articles, afternoon filings, and breaking news occurring after $T$ are strictly inaccessible.
3. **Publication vs. Availability Distinction**: `published_at`, `available_at`, `retrieved_at`, and `effective_at` are explicitly tracked. In cases of embargo or delayed dissemination, $\text{available\_at} > \text{published\_at}$ is honored.
4. **Source Priority & Authority**:
   - **Rank 1**: `OFFICIAL_EXCHANGE` (NSE announcements, company disclosures)
   - **Rank 2**: `REGULATORY_FILING` (SEBI, RBI, MCA circulars)
   - **Rank 3**: `REPUTABLE_NEWS` (Tier-1 financial media: Mint, ET, Business Standard)
   - **Rank 4**: `PUBLIC_MEDIA` (General public feeds)
5. **Deterministic Deduplication**: Cross-source duplicate announcements are deduplicated using composite keys: `(symbol, normalized_title, published_date, content_hash)`, prioritizing the highest authority record.
6. **Cryptographic Content Hashing**: Every document receives a deterministic SHA-256 digest over its contents.
7. **No LLM Summarization in Phase 5**: Text and structured metadata are ingested and assembled purely deterministically.

---

## Architecture Flow

```
Opportunity Candidates (Top-N)
        ↓
Targeted Multi-Provider Retrieval (NSE Corporate, Financial News, Macro/RBI)
        ↓
Cryptographic SHA-256 Hashing & Provenance Tagging
        ↓
Local Filesystem Caching (data/raw/external, data/processed/external)
        ↓
Point-in-Time Filter (available_at <= decision_timestamp)
        ↓
Deterministic Deduplication (Authority-aware consolidation)
        ↓
Relevance Ranking (HIGH for symbol match, MEDIUM for sector/macro, LOW for others)
        ↓
Immutable InformationContext (Metadata, counts, latest timestamp)
        ↓
Standardized MarketSnapshot (Candle + Features + Candidate + Context)
        ↓
SQLite Persistence (mobitrade.db)
```

---

## Domain Models

### `ExternalInformation`
- `information_id`: Unique identifier (e.g. `nse_92d54a68`).
- `source`: Provider identifier (e.g. `NSE_ANNOUNCEMENTS`).
- `source_type`: `SourceType` enum (`NSE_ANNOUNCEMENT`, `COMPANY_DISCLOSURE`, `FINANCIAL_NEWS`, `MACRO_ECONOMIC`).
- `publisher`: Entity name (e.g. `NSE`, `Economic Times`, `RBI`).
- `title`: Announcement / headline string.
- `url`: Direct canonical URL / filing reference.
- `symbol`: Specific NSE equity ticker (e.g. `RELIANCE`, `TCS`) or `None` for macro events.
- `published_at`: Timestamp of official publication (with timezone).
- `available_at`: Timestamp when the document was publicly accessible (with timezone).
- `retrieved_at`: UTC retrieval timestamp.
- `summary`: Short structured excerpt or description.
- `authority`: `SourceAuthority` enum (Rank 1 to 4).
- `relevance`: `RelevanceLevel` (`HIGH`, `MEDIUM`, `LOW`).
- `category`: `InformationCategory` enum (`EARNINGS`, `RESULTS`, `CORPORATE_ACTION`, `REGULATORY`, `ORDER_WIN`, `MACRO`, etc.).
- `content_hash`: 64-character SHA-256 digest.

### `InformationContext`
- `decision_timestamp`: Decision time $T$.
- `symbol`: Target ticker.
- `relevant_information`: Sorted list of deduplicated, eligible `ExternalInformation` items.
- `source_count`: Total items included.
- `high_authority_count`: Number of Rank 1 or Rank 2 items.
- `latest_available_information_time`: Timestamp of newest available information.
- `context_version`: Version string (`1.0.0`).

### `MarketSnapshot`
Unifies all platform layers into a single standardized input object for downstream local LLMs:
- Completed historical bar (`HistoricalCandle`)
- Point-in-time quantitative features (`TechnicalFeatures`)
- Opportunity scanner candidate evaluation (`OpportunityCandidate`)
- External information context (`InformationContext`)

---

## Storage & Database Schema

### Local Filesystem Cache
- Raw documents: `D:\Trading LLM\MobiTradeAI\data\raw\external\`
- Processed JSON documents: `D:\Trading LLM\MobiTradeAI\data\processed\external\`
- Context metadata: `D:\Trading LLM\MobiTradeAI\data\metadata\external\`

### SQLite Database (`database/mobitrade.db`)
- `external_information`: Stores individual document records, content hash, publisher, authority, and timestamps.
- `information_contexts`: Stores context query records indexed by `symbol` and `decision_timestamp`.
- `context_items`: Relational linkage mapping contexts to constituent documents with relevance flags.

---

## CLI Usage

```bash
# Check external layer status
mobitrade external status

# Validate YAML configuration
mobitrade external validate --config configs/external_information.yaml

# Inspect database records
mobitrade external inspect

# Test fetch across registered providers
mobitrade external fetch --symbol RELIANCE

# Query point-in-time InformationContext
mobitrade external context --symbol RELIANCE --timestamp "2026-09-11T10:00:00+05:30"
```
