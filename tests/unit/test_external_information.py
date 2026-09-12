import pytest
from datetime import datetime, timezone, timedelta
from mobitrade.domain.data_models import HistoricalCandle, Timeframe
from mobitrade.domain.feature_models import TechnicalFeatures, TrendClassification
from mobitrade.domain.scanner_models import OpportunityCandidate
from mobitrade.domain.information_models import (
    ExternalInformation,
    InformationContext,
    SourceType,
    SourceAuthority,
    InformationCategory,
    RelevanceLevel,
)
from mobitrade.domain.snapshot import MarketSnapshot
from mobitrade.sources.nse_provider import NSECorporateAnnouncementsProvider
from mobitrade.sources.news_provider import FinancialNewsProvider
from mobitrade.sources.macro_provider import MacroEconomicProvider
from mobitrade.sources.deduplication import InformationDeduplicator
from mobitrade.sources.relevance import RelevanceClassifier
from mobitrade.sources.persistence import InformationRepository
from mobitrade.sources.manager import ExternalInformationManager
from mobitrade.data.calendar import IST

# ============================================================
# 1. TEMPORAL SAFETY & LOOKAHEAD BLOCKING TESTS
# ============================================================

def test_temporal_safety_future_information_blocked():
    nse = NSECorporateAnnouncementsProvider()
    news = FinancialNewsProvider()
    macro = MacroEconomicProvider()

    decision_dt = datetime(2026, 9, 11, 10, 0, tzinfo=IST)

    # 1. Past NSE announcement at 09:30 (Available at 09:30) -> MUST BE INCLUDED
    doc_past = nse.ingest_document(
        symbol="RELIANCE",
        title="RELIANCE Morning Filing",
        summary="Board meeting results announced early morning.",
        published_at=datetime(2026, 9, 11, 9, 30, tzinfo=IST)
    )

    # 2. Exact boundary news at 10:00 (Available at 10:00) -> MUST BE INCLUDED
    doc_exact = news.ingest_article(
        title="RELIANCE Mid-morning Market Brief",
        summary="Stock rises 1.5% in early trading.",
        publisher="Economic Times",
        published_at=datetime(2026, 9, 11, 10, 0, tzinfo=IST),
        symbol="RELIANCE"
    )

    # 3. Future news article at 10:01 (Available at 10:01) -> MUST BE EXCLUDED
    doc_future_1001 = news.ingest_article(
        title="RELIANCE Post-10AM Analysis",
        summary="Late morning price movement commentary.",
        publisher="Mint",
        published_at=datetime(2026, 9, 11, 10, 1, tzinfo=IST),
        symbol="RELIANCE"
    )

    # 4. Future afternoon macro event at 14:00 -> MUST BE EXCLUDED
    doc_future_macro = macro.ingest_event(
        title="RBI Monetary Policy Stance Announcement",
        summary="RBI maintains repo rate at 6.5%.",
        publisher="RBI",
        published_at=datetime(2026, 9, 11, 14, 0, tzinfo=IST)
    )

    manager = ExternalInformationManager(providers=[nse, news, macro])
    docs_as_of = manager.get_information_as_of("RELIANCE", decision_dt)

    doc_ids = [d.information_id for d in docs_as_of]
    assert doc_past.information_id in doc_ids
    assert doc_exact.information_id in doc_ids
    assert doc_future_1001.information_id not in doc_ids
    assert doc_future_macro.information_id not in doc_ids

def test_publication_vs_availability_distinction():
    nse = NSECorporateAnnouncementsProvider()
    decision_dt = datetime(2026, 9, 11, 10, 0, tzinfo=IST)

    # Document published at 09:50, but embargoed/delayed availability until 10:15
    doc_delayed = nse.ingest_document(
        symbol="TCS",
        title="TCS Confidential Product Launch",
        summary="Major enterprise AI deployment announced.",
        published_at=datetime(2026, 9, 11, 9, 50, tzinfo=IST),
        available_at=datetime(2026, 9, 11, 10, 15, tzinfo=IST)
    )

    manager = ExternalInformationManager(providers=[nse])
    # At 10:00, the document is NOT yet available!
    docs_at_10 = manager.get_information_as_of("TCS", decision_dt)
    assert not any(d.information_id == doc_delayed.information_id for d in docs_at_10)

    # At 10:20, the document IS available!
    docs_at_1020 = manager.get_information_as_of("TCS", datetime(2026, 9, 11, 10, 20, tzinfo=IST))
    assert any(d.information_id == doc_delayed.information_id for d in docs_at_1020)

def test_future_information_cannot_alter_past_context():
    nse = NSECorporateAnnouncementsProvider()
    manager = ExternalInformationManager(providers=[nse])
    decision_dt = datetime(2026, 9, 11, 10, 0, tzinfo=IST)

    # Baseline: 1 morning document
    nse.ingest_document(
        symbol="INFY",
        title="INFY Q2 Guidance Affirmation",
        summary="Company reaffirms annual revenue growth guidance.",
        published_at=datetime(2026, 9, 11, 9, 15, tzinfo=IST)
    )
    context_baseline = manager.get_context_as_of("INFY", decision_dt, persist=False)
    assert context_baseline.source_count == 1

    # Now inject future breaking news at 15:00
    nse.ingest_document(
        symbol="INFY",
        title="INFY CEO Resignation Shock",
        summary="CEO announces surprise stepping down.",
        published_at=datetime(2026, 9, 11, 15, 0, tzinfo=IST)
    )

    # Re-query context as of 10:00
    context_after = manager.get_context_as_of("INFY", decision_dt, persist=False)
    assert context_after.source_count == 1
    assert context_after.relevant_information[0].title == "INFY Q2 Guidance Affirmation"

# ============================================================
# 2. CRYPTOGRAPHIC HASHING & PROVENANCE TESTS
# ============================================================

def test_cryptographic_content_hashing():
    h1 = ExternalInformation.generate_content_hash(
        "Quarterly Financial Results", "Net profit grew 12% YoY.", "NSE"
    )
    h2 = ExternalInformation.generate_content_hash(
        "Quarterly Financial Results", "Net profit grew 12% YoY.", "NSE"
    )
    h3 = ExternalInformation.generate_content_hash(
        "Quarterly Financial Results", "Net profit grew 14% YoY.", "NSE" # Modified content
    )

    assert len(h1) == 64 # Real SHA-256
    assert h1 == h2      # Identity
    assert h1 != h3      # Divergence on changed content

def test_source_provenance_retention():
    nse = NSECorporateAnnouncementsProvider()
    doc = nse.ingest_document(
        symbol="HDFCBANK",
        title="HDFCBANK Share Allotment",
        summary="Allotment of equity shares under ESOP scheme.",
        published_at=datetime(2026, 9, 11, 9, 45, tzinfo=IST),
        url="https://www.nseindia.com/filings/hdfc_001.pdf"
    )

    assert doc.source == "NSE_ANNOUNCEMENTS"
    assert doc.source_type == SourceType.NSE_ANNOUNCEMENT
    assert doc.publisher == "NSE"
    assert doc.url == "https://www.nseindia.com/filings/hdfc_001.pdf"
    assert doc.authority == SourceAuthority.OFFICIAL_EXCHANGE
    assert doc.retrieved_at is not None
    assert doc.published_at.tzinfo is not None

# ============================================================
# 3. DEDUPLICATION TESTS
# ============================================================

def test_deduplication_prefers_higher_authority():
    dedup = InformationDeduplicator()
    pub_dt = datetime(2026, 9, 11, 9, 30, tzinfo=IST)

    # Lower authority news report (Rank 3)
    news_doc = ExternalInformation(
        information_id="news_1",
        source="FINANCIAL_NEWS",
        source_type=SourceType.FINANCIAL_NEWS,
        publisher="MediaOutlet",
        title="TCS Signs 1B Cloud Deal",
        published_at=pub_dt,
        available_at=pub_dt,
        retrieved_at=pub_dt,
        summary="TCS announced a major multi-year digital transformation deal.",
        authority=SourceAuthority.REPUTABLE_NEWS,
        content_hash="hash1",
        symbol="TCS"
    )

    # Higher authority official NSE disclosure (Rank 1)
    nse_doc = ExternalInformation(
        information_id="nse_1",
        source="NSE_ANNOUNCEMENTS",
        source_type=SourceType.NSE_ANNOUNCEMENT,
        publisher="NSE",
        title="TCS Signs $1B Cloud Deal!", # Minor punctuation difference
        published_at=pub_dt,
        available_at=pub_dt,
        retrieved_at=pub_dt,
        summary="Official exchange disclosure: TCS signs strategic $1B engagement.",
        authority=SourceAuthority.OFFICIAL_EXCHANGE,
        content_hash="hash2",
        symbol="TCS"
    )

    deduped = dedup.deduplicate([news_doc, nse_doc])
    # Must consolidate into 1 item and pick the Rank 1 official disclosure
    assert len(deduped) == 1
    assert deduped[0].information_id == "nse_1"
    assert deduped[0].authority == SourceAuthority.OFFICIAL_EXCHANGE

# ============================================================
# 4. RELEVANCE CLASSIFICATION & RANKING TESTS
# ============================================================

def test_relevance_classification():
    classifier = RelevanceClassifier()
    dt = datetime(2026, 9, 11, 10, 0, tzinfo=IST)

    # Exact symbol match -> HIGH
    tcs_doc = ExternalInformation(
        information_id="d1", source="TEST", source_type=SourceType.FINANCIAL_NEWS,
        publisher="ET", title="TCS Expands UK Operations", summary="New center in London.",
        published_at=dt, available_at=dt, retrieved_at=dt, authority=SourceAuthority.REPUTABLE_NEWS,
        content_hash="h1", symbol="TCS"
    )
    assert classifier.classify_relevance(tcs_doc, "TCS", dt) == RelevanceLevel.HIGH

    # Sector match -> MEDIUM (INFY and TCS are both INFORMATION_TECHNOLOGY)
    infy_sector_doc = ExternalInformation(
        information_id="d2", source="TEST", source_type=SourceType.SECTOR_UPDATE,
        publisher="ET", title="Indian IT Sector Deal Wins Surge", summary="Overall IT margins stable.",
        published_at=dt, available_at=dt, retrieved_at=dt, authority=SourceAuthority.REPUTABLE_NEWS,
        content_hash="h2", symbol=None, sector="INFORMATION_TECHNOLOGY"
    )
    assert classifier.classify_relevance(infy_sector_doc, "TCS", dt) == RelevanceLevel.MEDIUM

    # Unrelated symbol -> LOW
    reliance_doc = ExternalInformation(
        information_id="d3", source="TEST", source_type=SourceType.FINANCIAL_NEWS,
        publisher="ET", title="RELIANCE Retail Store Expansion", summary="Opens 50 stores.",
        published_at=dt, available_at=dt, retrieved_at=dt, authority=SourceAuthority.REPUTABLE_NEWS,
        content_hash="h3", symbol="RELIANCE"
    )
    assert classifier.classify_relevance(reliance_doc, "TCS", dt) == RelevanceLevel.LOW

# ============================================================
# 5. MARKET SNAPSHOT INTEGRATION TESTS
# ============================================================

def test_market_snapshot_integration():
    nse = NSECorporateAnnouncementsProvider()
    decision_dt = datetime(2026, 9, 11, 10, 0, tzinfo=IST)

    nse.ingest_document(
        symbol="TCS",
        title="TCS Special Dividend Consideration",
        summary="Board to meet next week to consider special dividend.",
        published_at=datetime(2026, 9, 11, 9, 40, tzinfo=IST)
    )

    candle = HistoricalCandle(
        symbol="TCS", exchange="NSE", timeframe=Timeframe.M5,
        timestamp=datetime(2026, 9, 11, 9, 55, tzinfo=IST),
        open=1500.0, high=1510.0, low=1495.0, close=1505.0, volume=25000.0
    )

    candidate = OpportunityCandidate(
        symbol="TCS", exchange="NSE", decision_timestamp=decision_dt, timeframe=Timeframe.M5,
        price=1505.0, opportunity_score=82.5, candle_timestamp=datetime(2026, 9, 11, 9, 55, tzinfo=IST),
        feature_available_at=decision_dt
    )

    manager = ExternalInformationManager(providers=[nse])
    snapshot = manager.build_market_snapshot(
        symbol="TCS",
        decision_timestamp=decision_dt,
        timeframe=Timeframe.M5,
        candle=candle,
        candidate=candidate,
        persist_context=False
    )

    assert snapshot.symbol == "TCS"
    assert snapshot.decision_timestamp == decision_dt
    assert snapshot.candle.close == 1505.0
    assert snapshot.candidate.opportunity_score == 82.5
    assert snapshot.information_context is not None
    assert snapshot.information_context.source_count == 1
    assert snapshot.information_context.relevant_information[0].title == "TCS Special Dividend Consideration"

# ============================================================
# 6. SQLITE PERSISTENCE & CACHING TESTS
# ============================================================

def test_information_sqlite_persistence_and_caching(tmp_path):
    db_file = tmp_path / "test_mobitrade.db"
    repo = InformationRepository(db_path=str(db_file), base_cache_dir=str(tmp_path))

    dt = datetime(2026, 9, 11, 10, 0, tzinfo=IST)
    doc = ExternalInformation(
        information_id="test_doc_001",
        source="NSE_ANNOUNCEMENTS",
        source_type=SourceType.NSE_ANNOUNCEMENT,
        publisher="NSE",
        title="ICICIBANK Branch Network Milestone",
        published_at=dt - timedelta(minutes=15),
        available_at=dt - timedelta(minutes=15),
        retrieved_at=dt,
        summary="Bank inaugurates 500th digital branch.",
        authority=SourceAuthority.OFFICIAL_EXCHANGE,
        category=InformationCategory.OTHER,
        content_hash="hash_12345",
        symbol="ICICIBANK"
    )

    context = InformationContext(
        decision_timestamp=dt,
        symbol="ICICIBANK",
        relevant_information=[doc],
        source_count=1,
        high_authority_count=1,
        latest_available_information_time=dt - timedelta(minutes=15),
        created_at=dt
    )

    context_id = repo.save_context(context)
    assert context_id.startswith("ctx_ICICIBANK_")

    # Verify retrieval from SQLite
    loaded = repo.get_context(context_id)
    assert loaded is not None
    assert loaded["symbol"] == "ICICIBANK"
    assert len(loaded["items"]) == 1
    assert loaded["items"][0]["title"] == "ICICIBANK Branch Network Milestone"

    # Verify file cache on disk
    cache_doc_file = tmp_path / "processed" / "external" / "test_doc_001.json"
    cache_ctx_file = tmp_path / "metadata" / "external" / f"{context_id}.json"
    assert cache_doc_file.exists()
    assert cache_ctx_file.exists()
