from __future__ import annotations

import asyncio
import re
import uuid
from datetime import datetime, timezone
import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.reports import store_report
from app.collectors.github_collector import GitHubIntelligenceCollector
from app.collectors.google_trends_collector import GoogleTrendsCollector
from app.collectors.hackernews_collector import HackerNewsCollector
from app.collectors.reddit_collector import RedditCollector
from app.collectors.rss_collector import RSSCollector
from app.models.collected_document import CollectedDocument
from app.schemas.signals import Signal
from app.repositories.market_signal_repository import bulk_create as bulk_create_signals
from app.rag.chunking import DocumentChunker
from app.rag.ingestion import VectorIngestionService
from app.rag.retrieval import VectorSearchService
from app.services.signal_quality_service import quality_service
from app.services.source_scoring import score_signal
from app.services.monitoring import pipeline_monitor
from app.services.opportunity_intelligence import opportunity_intelligence_service
from app.services.query_guardrails import calculate_domain_relevance_score, calculate_query_relevance_score, is_github_repo_noise
from app.utils.logging import get_logger

logger = get_logger("services.query_generation")

DOMAIN_EXPANSIONS = {
    "accounting": [
        "accounting",
        "bookkeeping",
        "small business accounting",
        "invoice reconciliation",
        "receipt scanning",
        "expense tracking",
        "cash flow forecasting",
        "tax compliance",
        "payroll automation",
        "financial reporting",
        "accounts payable",
        "accounts receivable",
    ],
    "education": ["education", "learning", "students", "teachers", "courses", "exams", "tutoring", "lms", "classroom", "study"],
    "amazon": ["amazon", "seller", "marketplace", "ecommerce", "fba", "inventory", "reviews", "product research", "listing optimization", "pricing", "ads"],
    "productivity": [
        "students",
        "student",
        "study planning",
        "focus",
        "assignments",
        "assignment",
        "notes",
        "habits",
        "time management",
        "exam prep",
        "learning",
        "education",
        "course",
        "classroom",
    ],
    "fitness": [
        "fitness",
        "fitness technology",
        "workout",
        "exercise",
        "gym",
        "wellness",
        "nutrition",
        "training",
        "sports",
        "health tracking",
    ],
    "cybersecurity": [
        "cybersecurity",
        "cyber security",
        "infosec",
        "security",
        "soc",
        "threat detection",
        "incident response",
        "compliance",
        "identity",
        "identity management",
        "cloud security",
        "vulnerability",
        "vulnerability management",
        "patch",
        "cve",
        "scanner",
        "oauth",
        "sso",
    ],
    "fintech": [
        "fintech",
        "finance",
        "banking",
        "ledger",
        "cash flow",
        "payments",
        "fraud",
        "risk",
        "lending",
        "reconciliation",
        "underwriting",
        "transaction monitoring",
        "kyc",
        "aml",
        "compliance",
        "portfolio",
    ],
    "healthcare": ["healthcare", "health tech", "patient", "clinical", "billing", "triage", "care coordination", "prior auth", "claims"],
    "hrtech": ["hr", "human resources", "recruiting", "onboarding", "employee engagement", "performance management", "payroll", "workforce"],
    "supply_chain": ["supply chain", "logistics", "procurement", "warehouse", "inventory visibility", "supplier risk", "demand planning"],
    "remote_work": ["remote work", "async", "collaboration", "meetings", "knowledge sharing", "task coordination", "status updates"],
    "climate_tech": ["climate", "carbon", "emissions", "energy", "sustainability", "reporting", "asset monitoring"],
    "developer_tools": ["developer tools", "devtools", "debugging", "observability", "testing", "ci/cd", "api monitoring", "documentation"],
    "marketing_automation": ["marketing automation", "campaign", "lead qualification", "attribution", "personalization", "content ops"],
    "legal_tech": ["legal", "contract", "case management", "compliance", "research", "billing", "discovery"],
    "travel_tech": ["travel", "booking", "itinerary", "expense", "travel policy", "support"],
    "gaming": ["gaming", "player retention", "live ops", "community moderation", "monetization", "anti-cheat"],
    "real_estate": ["real estate", "property", "tenant", "listing", "valuation", "lead management"],
    "construction": ["construction", "project tracking", "safety", "estimating", "procurement", "scheduling"],
    "manufacturing": ["manufacturing", "quality control", "maintenance", "production planning", "supply planning"],
}

DOMAIN_ALIASES = {
    "accounting": ("accounting", "bookkeeping", "invoice", "receipt", "expense", "cash flow", "payroll", "tax", "vat", "gst", "ledger", "reconciliation"),
    "cybersecurity": ("cybersecurity", "cyber security", "infosec", "security", "soc", "threat detection"),
    "fintech": ("fintech", "finance", "payments", "fraud", "lending", "banking"),
    "healthcare": ("healthcare", "health tech", "patient", "clinical", "hospital", "medical"),
    "fitness": ("fitness", "fitness technology", "workout", "exercise", "gym", "wellness", "nutrition", "training", "sports", "health tracking"),
    "hrtech": ("hr tech", "hrtech", "recruiting", "human resources", "onboarding", "payroll", "performance management"),
    "supply_chain": ("supply chain", "logistics", "procurement", "warehouse", "supplier", "inventory planning"),
    "remote_work": ("remote work", "async", "distributed team", "collaboration", "meeting", "knowledge sharing"),
    "climate_tech": ("climate tech", "climate", "carbon", "emissions", "energy", "sustainability"),
    "developer_tools": ("developer tools", "devtools", "debugging", "observability", "testing", "ci/cd", "api"),
    "marketing_automation": ("marketing automation", "marketing", "campaign", "lead gen", "attribution", "personalization"),
    "legal_tech": ("legal tech", "legal", "contract", "discovery", "case management", "compliance"),
    "travel_tech": ("travel tech", "travel", "booking", "itinerary", "expense", "travel policy"),
    "gaming": ("gaming", "player retention", "live ops", "anti-cheat", "monetization"),
    "real_estate": ("real estate", "property", "tenant", "listing", "valuation", "lead management"),
    "construction": ("construction", "project tracking", "safety", "estimating", "procurement", "scheduling"),
    "manufacturing": ("manufacturing", "quality control", "maintenance", "production planning", "supply planning"),
}


def _match_domain(query_lower: str) -> str:
    if any(alias in query_lower for alias in DOMAIN_ALIASES["accounting"]):
        return "accounting"
    for domain, aliases in DOMAIN_ALIASES.items():
        if domain == "accounting":
            continue
        if any(alias in query_lower for alias in aliases):
            return domain
    if "amazon" in query_lower or "seller" in query_lower or "marketplace" in query_lower:
        return "amazon"
    if "student" in query_lower or "productivity" in query_lower or "study" in query_lower:
        return "productivity"
    if "fitness" in query_lower or "fitness technology" in query_lower or "workout" in query_lower or "exercise" in query_lower or "gym" in query_lower or "wellness" in query_lower or "nutrition" in query_lower or "sports" in query_lower:
        return "fitness"
    if "education" in query_lower or "learning" in query_lower or "teacher" in query_lower or "course" in query_lower:
        return "education"
    return "general"

QUERY_FILLER_WORDS = {
    "find",
    "finds",
    "opportunity",
    "opportunities",
    "discover",
    "discovering",
    "startups",
    "startup",
    "market",
    "markets",
    "gap",
    "gaps",
    "best",
    "top",
    "new",
    "real",
    "live",
    "need",
    "needs",
}

SHORT_QUERY_TERMS = {
    "ai",
    "ml",
    "hr",
    "ux",
    "ui",
    "soc",
    "saas",
    "fba",
    "erp",
    "crm",
    "lms",
    "api",
    "b2b",
    "b2c",
    "iot",
    "it",
    "seo",
    "sem",
    "gdpr",
    "hipaa",
    "pci",
    "devops",
}


def _normalize_competition_level(level: str | None, score: float | int | None = None) -> str:
    if not level:
        value = float(score or 0)
        if value >= 75:
            return "High"
        if value >= 45:
            return "Medium"
        return "Low"
    normalized = str(level).strip().lower().replace("_", " ")
    if normalized in {"high", "medium", "low"}:
        return normalized.title()
    if normalized in {"high competition", "competition high"}:
        return "High"
    if normalized in {"medium competition", "competition medium"}:
        return "Medium"
    if normalized in {"low competition", "competition low"}:
        return "Low"
    value = float(score or 0)
    if value >= 75:
        return "High"
    if value >= 45:
        return "Medium"
    return "Low"


def _build_collection_query(domain: str, query: str, expanded_terms: list[str], original_terms: list[str]) -> str:
    domain_queries = {
    "accounting": [
        "small business accounting",
        "bookkeeping automation",
        "invoice reconciliation",
        "expense categorization",
        "cash flow forecasting",
        "tax compliance",
        "payroll automation",
        "financial reporting",
    ],
    "fitness": [
        "fitness workout logger",
        "coach analytics fitness",
        "endurance training fitness",
        "nutrition planning fitness",
        "health tracking fitness",
    ],
        "cybersecurity": [
            "cybersecurity threat detection",
            "incident response security",
            "cloud security identity",
            "vulnerability management security",
            "security compliance audit",
        ],
        "amazon": [
            "amazon seller inventory",
            "amazon review analysis",
            "amazon listing optimization",
            "amazon pricing repricing",
            "amazon ads optimization",
        ],
        "education": [
            "student progress tracking",
            "teacher workload automation",
            "course recommendation education",
            "exam prep study planning",
            "learning engagement",
        ],
        "productivity": [
            "student focus planner",
            "assignment tracking student",
            "time management student",
            "note organization study",
            "habit building student",
        ],
    }
    queries = list(domain_queries.get(domain, []))
    if not queries:
        base = " ".join(term for term in [query, *expanded_terms[:4], *original_terms[:2]] if term).strip()
        return base
    return " || ".join(queries)


def _build_google_keywords(domain: str, expanded_terms: list[str], original_terms: list[str]) -> list[str]:
    domain_keywords = {
        "accounting": ["accounting", "bookkeeping", "invoice", "receipt", "cash flow", "tax", "payroll", "expense"],
        "fitness": ["fitness", "workout", "gym", "wellness", "nutrition", "running"],
        "cybersecurity": ["cybersecurity", "security", "threat detection", "incident response"],
        "amazon": ["amazon seller", "marketplace seller", "inventory", "pricing", "listing optimization"],
        "education": ["education", "learning", "student progress", "study planning"],
        "productivity": ["student productivity", "study planning", "focus", "time management"],
    }
    keywords = list(domain_keywords.get(domain, []))
    if keywords:
        return keywords[:3]
    if expanded_terms:
        return expanded_terms[:3]
    return original_terms[:3]


def _signal_terms_for_domain(domain: str) -> tuple[set[str], set[str]]:
    positive = {
        "accounting": {"accounting", "bookkeeping", "invoice", "receipt", "expense", "cash flow", "payroll", "tax", "vat", "gst", "ledger", "reconciliation", "financial", "reporting"},
        "fitness": {"fitness", "workout", "gym", "wellness", "nutrition", "training", "sports", "health", "coach", "member", "runner", "running", "treadmill", "cardio", "race"},
        "cybersecurity": {"cyber", "security", "threat", "incident", "alert", "siem", "soc", "vulnerability", "cloud", "identity", "access", "detection"},
        "amazon": {"amazon", "seller", "marketplace", "ecommerce", "inventory", "pricing", "review", "reviews", "fulfillment", "listing", "product research", "ads", "fba"},
        "education": {"education", "learning", "student", "teacher", "course", "classroom", "tutor", "tutoring", "exam", "lms", "study"},
        "productivity": {"student", "study", "productivity", "focus", "assignment", "notes", "habit", "time management", "exam prep"},
    }
    negative = {
        "accounting": {"fitness", "workout", "gym", "student", "teacher", "course", "real estate", "rental property", "security", "cyber"},
        "fitness": {"github copilot", "admin ui", "staging", "queue", "json api", "backend", "frontend", "codealpha", "exercise crud", "copy to clipboard", "build applications", "task", "application"},
        "cybersecurity": {"realestate", "rental property", "student", "education", "amazon", "seller"},
        "amazon": {"student", "education", "fitness", "workout", "realestate", "rental property"},
        "education": {"amazon", "seller", "fitness", "workout", "realestate", "rental property"},
        "productivity": {"amazon", "seller", "fitness", "workout", "realestate", "rental property"},
    }
    return positive.get(domain, set()), negative.get(domain, set())


class QueryGenerationService:
    def _expand_query(self, query: str) -> tuple[str, list[str], str]:
        q = query.lower()
        domain = _match_domain(q)
        if domain in DOMAIN_EXPANSIONS:
            terms = DOMAIN_EXPANSIONS[domain]
            return domain, terms, _build_collection_query(domain, query, terms, self._query_keywords(query))
        terms = self._query_keywords(query)
        return "general", terms, " ".join(terms[:4])

    def _term_tokens(self, terms: list[str]) -> list[str]:
        tokens: list[str] = []
        for term in terms:
            tokens.extend([tok for tok in re.findall(r"[a-zA-Z][a-zA-Z0-9+.-]{2,}", term.lower()) if len(tok) > 2])
        deduped = []
        seen = set()
        for tok in tokens:
            if tok in seen:
                continue
            seen.add(tok)
            deduped.append(tok)
        return deduped

    async def generate(self, session: AsyncSession, query: str) -> dict:
        query_id = uuid.uuid4()
        collected: dict[str, dict] = {}
        live_signals: list[Signal] = []
        all_source_results: list[dict] = []
        domain, expanded_terms, collection_query = self._expand_query(query)
        original_terms = self._query_keywords(query)
        query_terms = [*original_terms, *[term for term in expanded_terms if term not in original_terms]]
        google_keywords = _build_google_keywords(domain, expanded_terms, original_terms)

        source_specs = [
            {
                "name": "github",
                "timeout": 15,
                "limit": 20,
                "factory": lambda: GitHubIntelligenceCollector(),
                "runner": lambda c: c.collect_all(collection_query or query),
            },
            {
                "name": "hackernews",
                "timeout": 15,
                "limit": 20,
                "factory": lambda: HackerNewsCollector(),
                "runner": lambda c: c.collect_all(limit_per_type=1),
            },
            {
                "name": "rss",
                "timeout": 10,
                "limit": 20,
                "factory": lambda: RSSCollector(),
                "runner": lambda c: c.collect_all(limit_per_feed=5),
            },
            {
                "name": "google_trends",
                "timeout": 15,
                "limit": 10,
                "factory": lambda: GoogleTrendsCollector(),
                "runner": lambda c: c.collect_all(google_keywords[:3] or google_keywords[:1]),
            },
            {
                "name": "reddit",
                "timeout": 10,
                "limit": 10,
                "factory": lambda: RedditCollector(),
                "runner": lambda c: c.collect_all(limit_per_sub=2, fast_mode=True),
            },
        ]

        async def _collect_source(spec: dict) -> tuple[str, dict]:
            name = spec["name"]
            started = time.perf_counter()
            try:
                collector = spec["factory"]()
            except RuntimeError as exc:
                return name, self._source_status(name, "CONFIG_BLOCKED", 0, time.perf_counter() - started, error=str(exc), limit=spec["limit"])

            try:
                batch = await asyncio.wait_for(spec["runner"](collector), timeout=spec["timeout"])
                signals = (batch.signals or [])[: spec["limit"]]
                return name, {
                    "status": "SUCCESS" if signals else "FAILED",
                    "error": "" if signals else "No live signals collected from source",
                    "signals": [signal.model_dump(mode="json") for signal in signals],
                    "signals_collected": len(signals),
                    "duration_ms": int((time.perf_counter() - started) * 1000),
                    "limit": spec["limit"],
                }
            except asyncio.TimeoutError:
                return name, self._source_status(name, "TIMEOUT", 0, time.perf_counter() - started, error="Collector timed out", limit=spec["limit"])
            except RuntimeError as exc:
                return name, self._source_status(name, "CONFIG_BLOCKED", 0, time.perf_counter() - started, error=str(exc), limit=spec["limit"])
            except Exception as exc:
                return name, self._source_status(name, "FAILED", 0, time.perf_counter() - started, error=str(exc), limit=spec["limit"])

        source_results = await asyncio.gather(*[_collect_source(spec) for spec in source_specs], return_exceptions=True)
        for result in source_results:
            if isinstance(result, Exception):
                logger.error("Collector task failed unexpectedly: %s", result)
                continue
            name, payload = result
            all_source_results.append(
                {
                    "source": name,
                    "status": payload["status"],
                    "error": payload.get("error", ""),
                    "duration_ms": payload.get("duration_ms", 0),
                    "signals_collected": payload.get("signals_collected", 0),
                    "limit": payload.get("limit", 0),
                }
            )
            collected[name] = {
                "status": payload["status"],
                "error": payload.get("error", ""),
                "signals_collected": payload.get("signals_collected", 0),
                "signals_ingested": 0,
                "quality_filtered": 0,
                "vectors_created": 0,
                "duration_ms": payload.get("duration_ms", 0),
                "limit": payload.get("limit", 0),
            }
            if payload["status"] != "SUCCESS":
                continue
            live_signals.extend([Signal.model_validate(item) for item in payload.get("signals", [])])

        quality_signals = quality_service.filter_signals(live_signals)
        if not quality_signals:
            logger.warning("No quality live signals collected for query=%r query_id=%s; falling back to same-domain historical evidence", query, query_id)

        relevant_signals: list[Signal] = []
        for signal in quality_signals:
            text = f"{signal.title} {signal.content} {signal.source} {signal.source_type}"
            signal_query_score = calculate_query_relevance_score(
                query,
                text,
                domain=domain,
                source=signal.source,
                source_type=signal.source_type,
            )
            signal_domain_score = calculate_domain_relevance_score(
                text,
                domain=domain,
                source=signal.source,
                source_type=signal.source_type,
            )
            if signal.source == "github" and is_github_repo_noise(f"{signal.title} {signal.content}", source=signal.source, source_type=signal.source_type):
                continue
            signal.query_id = str(query_id)
            signal.query_domain = domain
            signal.query_relevance_score = signal_query_score
            signal.domain_relevance_score = signal_domain_score
            signal.metadata = {
                **signal.metadata,
                "query_id": str(query_id),
                "query_domain": domain,
                "query_text": query,
                "domain": domain,
                "query_relevance_score": signal_query_score,
                "domain_relevance_score": signal_domain_score,
            }
            if signal_query_score >= 60 and signal_domain_score >= 60 and self._signal_domain_match(signal, domain):
                relevant_signals.append(signal)

        if not relevant_signals:
            logger.warning("No relevant live signals passed query relevance for query=%r query_id=%s; continuing with retrieval fallback", query, query_id)

        document_chunks = []
        accepted_by_source: dict[str, int] = {}
        for signal in relevant_signals:
            accepted_by_source[signal.source] = accepted_by_source.get(signal.source, 0) + 1
        bulk_payload = [
            {
                "source": signal.source,
                "source_type": signal.source_type,
                "source_id": signal.source_id,
                "query_id": query_id,
                "title": signal.title,
                "content": signal.content,
                "url": signal.url,
                "author": signal.author,
                "score": signal.score,
                "comments_count": signal.comments_count,
                "query_relevance_score": signal.metadata.get("query_relevance_score", 0.0),
                "domain_relevance_score": signal.metadata.get("domain_relevance_score", 0.0),
                "query_domain": domain,
                "credibility_score": round(
                    (signal.metadata.get("quality_score", 0.5) + score_signal(signal.model_dump())) / 2,
                    3,
                ),
                "created_at": signal.created_at or signal.collected_at,
                "collected_at": signal.collected_at,
                "extra_metadata": signal.metadata,
            }
            for signal in relevant_signals
        ]
        if bulk_payload:
            await bulk_create_signals(session, bulk_payload)

        for name, payload in collected.items():
            accepted = accepted_by_source.get(name, 0)
            payload["signals_accepted"] = accepted
            payload["signals_rejected"] = max(0, payload.get("signals_collected", 0) - accepted)

        ingested = len(bulk_payload)
        quality_filtered_total = len(live_signals) - ingested
        logger.info(
            "Signal ingestion committed query=%r query_id=%s ingested=%d filtered=%d",
            query,
            query_id,
            ingested,
            quality_filtered_total,
        )
        logger.info(
            "Query audit query=%r query_id=%s signals_collected=%d documents_created=%d",
            query,
            query_id,
            len(live_signals),
            len(document_chunks),
        )
        await session.commit()

        chunker = DocumentChunker()
        for signal in relevant_signals:
            document = CollectedDocument(
                source=signal.source,
                source_type=signal.source_type,
                query_id=query_id,
                title=signal.title,
                content=signal.content or signal.title,
                url=signal.url,
                created_at=signal.created_at or signal.collected_at,
                metadata_json={
                    **signal.metadata,
                    "query_id": str(query_id),
                    "query_domain": domain,
                    "query_relevance_score": signal.metadata.get("query_relevance_score", 0.0),
                    "query_text": query,
                    "source_id": signal.source_id,
                    "source": signal.source,
                    "source_type": signal.source_type,
                },
            )
            session.add(document)
            await session.flush()
            document_chunks.extend(
                chunker.chunk_document(
                    doc_id=str(document.id),
                    content=f"{signal.title}\n{signal.content}".strip(),
                    metadata={
                        "document_id": str(document.id),
                        "query_id": str(query_id),
                        "query_domain": domain,
                        "query_text": query,
                        "query_relevance_score": signal.metadata.get("query_relevance_score", 0.0),
                        "source": signal.source,
                        "source_type": signal.source_type,
                        "source_id": signal.source_id,
                        "url": signal.url,
                        "collected_at": (signal.collected_at or datetime.now(timezone.utc)).isoformat(),
                    },
                )
            )

        vectors_created = 0
        if document_chunks:
            try:
                vectors_created = await VectorIngestionService().ingest_documents(document_chunks)
            except Exception as exc:
                logger.warning("Vector ingestion failed for query=%r query_id=%s: %s", query, query_id, exc)

        await session.commit()

        rag_results = []
        rag_status = {
            "available": False,
            "status": "DEGRADED",
            "error": "ChromaDB unavailable or no evidence retrieved",
        }
        evidence_urls: set[str] = set()
        try:
            search_service = VectorSearchService()
            rag_results = await search_service.search_evidence(
                query=query,
                expanded_terms=expanded_terms,
                query_id=str(query_id),
                query_domain=domain,
                top_k=10,
            )
            evidence_urls = {item.url for item in rag_results if getattr(item, "url", None)}
            if rag_results:
                rag_status = {
                    "available": True,
                    "status": "HEALTHY",
                    "error": "",
                }
        except Exception as exc:
            logger.warning("RAG retrieval failed for query=%r query_id=%s: %s", query, query_id, exc)

        if not evidence_urls:
            evidence_urls = {signal.url for signal in relevant_signals if signal.url}
        logger.info(
            "Evidence audit query=%r query_id=%s retrieved=%d evidence_urls=%d",
            query,
            query_id,
            len(rag_results),
            len(evidence_urls),
        )

        logger.info("Opportunity generation stage starting query=%r query_id=%s", query, query_id)
        opportunities = await opportunity_intelligence_service.build_opportunities(
            session,
            limit=25,
            query=query,
            query_id=query_id,
            evidence_urls=evidence_urls,
        )
        logger.info(
            "Opportunity generation stage completed query=%r query_id=%s opportunities=%d",
            query,
            query_id,
            len(opportunities),
        )
        logger.info(
            "Opportunity audit query=%r query_id=%s candidates_created=%d discarded=%s",
            query,
            query_id,
            opportunity_intelligence_service.last_debug.get("candidates_created", 0),
            opportunity_intelligence_service.last_debug.get("candidates_discarded", {}),
        )
        if not opportunities:
            raise RuntimeError(f"{query_id}|No evidence-backed opportunities found for this query.")

        await session.commit()

        logger.info("Top opportunity fetch starting query=%r", query)
        top_opportunities = await opportunity_intelligence_service.get_opportunities(session, limit=10, query_id=query_id)
        logger.info("Top opportunity fetch completed query=%r count=%d", query, len(top_opportunities))
        logger.info("Report assembly starting query=%r", query)
        report = self._build_report(query, rag_results, opportunities, top_opportunities, collected)
        report_id = str(uuid.uuid4())
        report["id"] = report_id
        report["query_id"] = str(query_id)
        report["query_domain"] = domain
        report["created_at"] = datetime.now(timezone.utc).isoformat()
        report["source_statuses"] = all_source_results
        report["rag_status"] = rag_status
        logger.info("Report persistence starting query=%r report_id=%s", query, report_id)
        await store_report(session, report_id, report, query_id=query_id)
        await session.commit()
        logger.info("Report persistence completed query=%r report_id=%s", query, report_id)

        pipeline_monitor.record_pipeline_run(
            source="query_generation",
            metrics={
                "signals_collected": len(live_signals),
                "signals_ingested": ingested,
                "quality_filtered": quality_filtered_total,
                "vectors_created": vectors_created,
                "collection_latency_ms": sum(v.get("duration_ms", 0) for v in collected.values()),
                "ingestion_latency_ms": 0,
            },
            success=True,
        )

        opportunity_summaries = [self._serialize_opportunity_summary(item) for item in opportunities[:10]]
        for summary in opportunity_summaries:
            summary["report_id"] = report_id

        return {
            "query_id": str(query_id),
            "query_domain": domain,
            "query": query,
            "collection": collected,
            "source_statuses": all_source_results,
            "rag": [self._serialize_rag_item(item) for item in rag_results],
            "opportunities": opportunity_summaries,
            "opportunities_count": len(opportunities),
            "evidence_links_count": sum(int(item.get("evidence_count", 0)) for item in opportunities),
            "signals_collected": len(live_signals),
            "signals_accepted": ingested,
            "signals_rejected": quality_filtered_total,
            "report": report,
            "debug": self._build_debug_summary(collected, rag_results, opportunities, opportunity_intelligence_service.last_debug),
        }

    def _source_status(self, name: str, status: str, signals_collected: int, duration_seconds: float, *, error: str = "", limit: int = 0) -> dict:
        return {
            "status": status,
            "error": error,
            "signals": [],
            "signals_collected": signals_collected,
            "duration_ms": int(duration_seconds * 1000),
            "limit": limit,
        }

    def _signal_query_relevance(self, query_terms: list[str], signal: Signal) -> float:
        if not query_terms:
            return 0.0
        text = f"{signal.title} {signal.content} {signal.source} {signal.source_type}".lower()
        original_terms = self._term_tokens(query_terms[:3])
        expanded_terms = self._term_tokens(query_terms[3:])
        direct_hits = sum(1 for term in original_terms if term in text)
        expanded_hits = sum(1 for term in expanded_terms if term in text)
        title_hits = sum(1 for term in original_terms if term in signal.title.lower())
        source_bonus = 5.0 if signal.source in {"github", "hackernews", "rss", "google_trends", "reddit"} else 0.0
        quality_bonus = float(signal.metadata.get("quality_score", 0.5) or 0.5) * 12.0
        recency_bonus = 12.0
        score = min(100.0, direct_hits * 18.0 + expanded_hits * 9.0 + title_hits * 10.0 + source_bonus + quality_bonus + recency_bonus)
        return round(score, 1)

    def _signal_domain_match(self, signal: Signal, domain: str) -> bool:
        if domain == "general":
            return True
        text = f"{signal.title} {signal.content} {signal.source} {signal.source_type}".lower()
        domain_terms, negative_terms = _signal_terms_for_domain(domain)
        if not domain_terms:
            return True
        if any(term in text for term in negative_terms):
            return False
        if domain == "fitness":
            strong_terms = {"fitness", "workout", "gym", "wellness", "nutrition", "sports", "health", "coach", "member", "runner", "running", "treadmill", "cardio", "race"}
            weak_terms = {"training", "exercise", "routine", "habit", "progress"}
            if any(term in text for term in strong_terms):
                return True
            return sum(1 for term in weak_terms if term in text) >= 2
        return any(term in text for term in domain_terms)

    def _serialize_rag_item(self, item) -> dict:
        if hasattr(item, "model_dump"):
            return item.model_dump(mode="json")
        return {
            "content": getattr(item, "content", ""),
            "score": getattr(item, "score", 0),
            "metadata": getattr(item, "metadata", {}) or {},
        }

    def _serialize_opportunity_summary(self, opportunity: dict) -> dict:
        evidence = opportunity.get("evidence", {}).get("signals", []) if isinstance(opportunity.get("evidence"), dict) else []
        return {
            "id": opportunity.get("id"),
            "query_id": opportunity.get("query_id"),
            "query_domain": opportunity.get("query_domain"),
            "startup_name": opportunity.get("startup_name"),
            "name": opportunity.get("startup_name"),
            "problem": opportunity.get("problem"),
            "market_gap": opportunity.get("market_gap") or opportunity.get("problem"),
            "solution": opportunity.get("solution"),
            "market_score": opportunity.get("market_score"),
            "opportunity_score": opportunity.get("opportunity_score", opportunity.get("market_score")),
            "confidence_score": opportunity.get("confidence_score"),
            "demand_score": opportunity.get("demand_score"),
            "competition_score": opportunity.get("competition_score"),
            "competition_level": opportunity.get("competition_level"),
            "query_relevance_score": opportunity.get("query_relevance_score", 0),
            "domain_relevance_score": opportunity.get("domain_relevance_score", 0),
            "query_domain_similarity": opportunity.get("query_domain_similarity", round(float(opportunity.get("query_relevance_score", 0) or 0) / 100.0, 2)),
            "domain_similarity": opportunity.get("domain_similarity", round(float(opportunity.get("domain_relevance_score", 0) or 0) / 100.0, 2)),
            "evidence_count": len(evidence),
            "sources": opportunity.get("sources", []),
            "target_user": opportunity.get("target_user") or opportunity.get("target_customers"),
            "top_evidence": evidence[:3],
            "created_at": opportunity.get("created_at"),
        }

    def _query_keywords(self, query: str) -> list[str]:
        terms = [
            t
            for t in re.findall(r"[A-Za-z][A-Za-z0-9+.-]{2,}", query.lower())
            if (len(t) > 3 or t in SHORT_QUERY_TERMS) and t not in QUERY_FILLER_WORDS
        ]
        if not terms:
            return ["artificial intelligence"]
        return terms[:3]

    def _infer_domain(self, query: str) -> str:
        return _match_domain(query.lower())

    def _build_report(
        self,
        query: str,
        rag_results: list,
        opportunities: list[dict],
        top_opportunities: list[dict],
        collected: dict[str, dict],
    ) -> dict:
        def _norm(value: object) -> str:
            return re.sub(r"\s+", " ", str(value).lower()).strip()

        query_domain = self._infer_domain(query)

        def _opportunity_domain_match(opportunity: dict) -> bool:
            if query_domain == "general":
                return True
            text = " ".join(
                [
                    str(opportunity.get("startup_name", "")),
                    str(opportunity.get("problem", "")),
                    str(opportunity.get("market_gap", "")),
                    str(opportunity.get("solution", "")),
                    str(opportunity.get("target_user", "")),
                ]
            ).lower()
            domain_terms = set(DOMAIN_EXPANSIONS.get(query_domain, []))
            if not domain_terms:
                return True
            negative_terms = {
                "accounting": {"fitness", "workout", "amazon", "seller", "education", "student", "teacher", "real estate", "rental property", "cybersecurity"},
                "fitness": {"education", "student", "teacher", "course", "classroom", "rental property", "real estate"},
                "cybersecurity": {"rental property", "real estate", "student", "education"},
                "amazon": {"fitness", "workout", "education", "student", "teacher", "real estate", "rental property"},
                "education": {"fitness", "workout", "amazon", "seller", "real estate", "rental property"},
                "productivity": {"fitness", "workout", "amazon", "seller", "real estate", "rental property"},
            }.get(query_domain, set())
            if any(term in text for term in negative_terms):
                return False
            return any(term in text for term in domain_terms)

        def _opportunity_relevance(opportunity: dict) -> float:
            relevance = float(opportunity.get("query_relevance_score", 0) or 0)
            if relevance <= 0:
                relevance = float(opportunity.get("opportunity_score", opportunity.get("market_score", 0)) or 0)
            return relevance

        def _keep_opportunity(opportunity: dict) -> bool:
            return (
                _opportunity_relevance(opportunity) >= 80
                and float(opportunity.get("domain_relevance_score", 0) or 0) >= 80
                and _opportunity_domain_match(opportunity)
            )

        mixed_domain_discarded = sum(1 for opp in opportunities if not _keep_opportunity(opp))

        def _unique_opportunities(items: list[dict], limit: int = 5) -> list[dict]:
            selected: list[dict] = []
            seen: set[str] = set()
            ordered = sorted(
                [item for item in items if isinstance(item, dict)],
                key=lambda item: (
                    float(item.get("query_relevance_score", 0)),
                    float(item.get("market_score", 0)),
                    float(item.get("confidence_score", 0)),
                ),
                reverse=True,
            )
            for item in ordered:
                evidence_ids = tuple(sorted(set(item.get("evidence_ids") or [])))
                key = " :: ".join(
                    [
                        _norm(item.get("cluster_id") or ""),
                        _norm(item.get("startup_name") or item.get("name") or ""),
                        _norm(item.get("problem") or ""),
                        _norm(item.get("market_gap") or ""),
                        _norm(item.get("solution") or ""),
                        "|".join(evidence_ids),
                    ]
                )
                if not key or key in seen:
                    continue
                seen.add(key)
                selected.append(item)
                if len(selected) >= limit:
                    break
            return selected

        evidence = []
        seen_evidence: set[str] = set()
        for item in rag_results[:8]:
            meta = item.metadata or {}
            relevance_score = float(getattr(item, "query_relevance_score", 0.0) or 0.0)
            if relevance_score <= 0:
                relevance_score = float(getattr(item, "score", 0.0) or 0.0) * 100.0
            if relevance_score < 70.0:
                continue
            evidence_key = _norm(meta.get("url") or item.content or meta.get("source"))
            if evidence_key in seen_evidence:
                continue
            seen_evidence.add(evidence_key)
            evidence.append(
                {
                    "source": meta.get("source", "unknown"),
                    "source_type": meta.get("source_type", "unknown"),
                    "url": meta.get("url", ""),
                    "relevance_score": item.score,
                    "title": meta.get("title") or item.content[:120],
                    "snippet": item.content[:240],
                }
            )
        unique_opportunities = [opp for opp in _unique_opportunities(opportunities, limit=10) if _keep_opportunity(opp)]
        pain_points = []
        market_gaps = []
        seen_pain_titles: set[str] = set()
        for opp in unique_opportunities:
            evidence_signals = opp.get("evidence", {}).get("signals", []) if isinstance(opp.get("evidence"), dict) else []
            sources = sorted({sig.get("source", "unknown") for sig in evidence_signals if sig.get("source")})
            gap = opp.get("market_gap") or opp.get("solution") or "Existing tools do not fully solve this workflow."
            title = opp.get("problem", "Unknown problem")
            normalized_title = _norm(title)
            if normalized_title in seen_pain_titles:
                continue
            seen_pain_titles.add(normalized_title)
            pain_points.append(
                {
                    "title": title,
                    "description": f"Why current tools fail: {gap}. Evidence: {len(evidence_signals)} signals from {', '.join(sources) or 'live sources'}.",
                    "frequency": len(evidence_signals),
                    "severity_score": round(float(opp.get("pain_score", 0)) / 10, 1),
                    "evidence": [sig.get("url", "") for sig in evidence_signals[:3] if sig.get("url")],
                    "sources": sources,
                }
            )
            market_gaps.append(
                {
                    "title": opp.get("startup_name", "Untitled"),
                    "description": f"{opp.get('problem', '')} Why current tools fail: {gap}.",
                    "opportunity_score": opp.get("opportunity_score", opp.get("market_score", 0)),
                    "competition_level": _normalize_competition_level(opp.get("competition_level"), opp.get("competition_score")),
                    "pain_points": [opp.get("problem", "")],
                    "supporting_trends": sources,
                    "evidence_count": len(evidence_signals),
                    "demand_score": opp.get("demand_score", 0),
                    "competition_score": opp.get("competition_score", 0),
                    "evidence_score": opp.get("evidence_score", 0),
                    "whitespace_score": opp.get("whitespace_score", 0),
                    "query_relevance_score": opp.get("query_relevance_score", 0),
                    "domain_relevance_score": opp.get("domain_relevance_score", 0),
                    "target_user": opp.get("target_user") or opp.get("target_customers"),
                    "implementation_difficulty": "medium" if opp.get("feasibility_score", 0) < 60 else "low",
                    "mvp_suggestion": opp.get("solution", ""),
                    "sources": sources,
                    "problem": opp.get("problem", ""),
                }
            )
        unique_top_opportunities = [opp for opp in _unique_opportunities(top_opportunities, limit=10) if _keep_opportunity(opp)]
        validated = []
        for opp in unique_top_opportunities:
            evidence_signals = opp.get("evidence", {}).get("signals", []) if isinstance(opp.get("evidence"), dict) else []
            cluster_name = opp.get("cluster_name") or opp.get("cluster_id") or "focused opportunity"
            validated.append(
                {
                    "opportunity": {
                        "id": opp.get("id", ""),
                        "title": opp.get("startup_name", ""),
                        "description": opp.get("solution", ""),
                        "market_size_estimate": "derived from live signals",
                        "problem": opp.get("problem", ""),
                        "summary": f"{cluster_name}: {opp.get('problem', '')} Why current tools fail: {opp.get('market_gap', opp.get('problem', ''))}.",
                        "target_user": opp.get("target_user") or opp.get("target_customers"),
                        "confidence_score": opp.get("confidence_score", 0),
                        "opportunity_score": opp.get("opportunity_score", opp.get("market_score", 0)),
                        "evidence_score": opp.get("evidence_score", 0),
                        "whitespace_score": opp.get("whitespace_score", 0),
                        "implementation_difficulty": "medium" if opp.get("feasibility_score", 0) < 60 else "low",
                        "why_current_tools_fail": opp.get("market_gap", opp.get("problem", "")),
                        "evidence_count": len(evidence_signals),
                        "demand_score": opp.get("demand_score", 0),
                        "competition_score": opp.get("competition_score", 0),
                        "competition_level": _normalize_competition_level(opp.get("competition_level"), opp.get("competition_score")),
                        "query_relevance_score": opp.get("query_relevance_score", 0),
                        "domain_relevance_score": opp.get("domain_relevance_score", 0),
                        "sources": opp.get("sources", sources) if isinstance(opp.get("sources"), list) else sources,
                        "mvp_suggestion": opp.get("solution", ""),
                        "cluster_name": cluster_name,
                    },
                    "overall_score": opp.get("opportunity_score", opp.get("market_score", 0)),
                    "checks": [
                        {"check_name": "evidence_count", "passed": bool(evidence_signals), "score": 1.0 if evidence_signals else 0.0, "details": f"{len(evidence_signals)} evidence signals"},
                        {"check_name": "demand_validation", "passed": opp.get("demand_score", 0) > 0, "score": min(1.0, opp.get("demand_score", 0) / 100), "details": f"Demand score {opp.get('demand_score', 0)}"},
                    ],
                    "validated": True,
                }
            )
        market_confidence_score = max([opp.get("market_score", 0) for opp in unique_opportunities] or [0])
        return {
            "query": query,
            "query_domain": query_domain,
            "executive_summary": f"Live analysis for '{query}' using {sum(v['signals_collected'] for v in collected.values())} collected signals across GitHub, Reddit, Hacker News, RSS, and Google Trends.",
            "top_pain_points": pain_points,
            "top_trends": [gap["title"] for gap in market_gaps],
            "top_market_gaps": market_gaps,
            "top_opportunities": validated,
            "recommendation": "Prioritize the highest-scoring, evidence-backed opportunities and continue collecting live signals daily.",
            "evidence_links": evidence,
            "market_confidence_score": market_confidence_score,
            "metadata": {
                "sources": collected,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "query_domain": query_domain,
                "domain_validation": {
                    "invalid": mixed_domain_discarded > 0,
                    "discarded": mixed_domain_discarded,
                },
            },
        }

    def _build_debug_summary(
        self,
        collected: dict[str, dict],
        rag_results: list,
        opportunities: list[dict],
        opportunity_debug: dict | None,
    ) -> dict:
        discarded = (opportunity_debug or {}).get("candidates_discarded", {})
        return {
            "signals_collected": sum(int(v.get("signals_collected", 0)) for v in collected.values()),
            "evidence_retrieved": len(rag_results),
            "candidates_created": int((opportunity_debug or {}).get("candidates_created", 0)),
            "candidates_discarded": {
                "low_relevance": int(discarded.get("low_relevance", 0)),
                "duplicate": int(discarded.get("duplicate", 0)),
                "no_evidence": int(discarded.get("no_evidence", 0)),
                "wrong_domain": int(discarded.get("wrong_domain", 0)),
                "low_confidence": int(discarded.get("low_confidence", 0)),
                "salvaged": int(discarded.get("salvaged", 0)),
            },
            "opportunities_returned": len(opportunities),
        }


query_generation_service = QueryGenerationService()
