from __future__ import annotations

import re
import hashlib
import uuid
from datetime import datetime, timedelta

import chromadb
from sqlalchemy import desc, or_, select

from app.config import get_settings
from app.database.postgres import async_session
from app.models.market_signal import MarketSignal
from app.rag.schemas import SearchResult
from app.rag.embeddings import EmbeddingService
from app.services.chromadb_service import get_chroma_service
from app.services.query_guardrails import calculate_query_relevance, infer_query_domain, is_github_repo_noise
from app.utils.logging import get_logger

logger = get_logger("rag.retrieval")

DEFAULT_COLLECTION_NAME = get_settings().chroma_collection


class VectorSearchService:
    def __init__(self, collection_name: str | None = None) -> None:
        self._collection_name = collection_name or DEFAULT_COLLECTION_NAME
        self._embedding_service = EmbeddingService()
        self._chroma = get_chroma_service()

    def infer_query_domain(self, query: str) -> str:
        return infer_query_domain(query)

    def _build_where(
        self,
        *,
        query_id: str | None = None,
        query_domain: str | None = None,
        source: str | None = None,
        source_type: str | None = None,
        where: dict | None = None,
    ) -> dict | None:
        filters = []
        if where:
            filters.append(where)
        if query_id:
            filters.append({"query_id": str(query_id)})
        if query_domain and query_domain != "general":
            filters.append({"query_domain": query_domain})
        if source:
            filters.append({"source": source})
        if source_type:
            filters.append({"source_type": source_type})
        if not filters:
            return None
        if len(filters) == 1:
            return filters[0]
        return {"$and": filters}

    def _relevant_results(
        self,
        results: list[SearchResult],
        *,
        query: str,
        threshold: float = 0.70,
        query_domain: str = "general",
    ) -> list[SearchResult]:
        filtered = []
        for item in results:
            if float(getattr(item, "score", 0.0) or 0.0) < threshold:
                continue
            metadata = getattr(item, "metadata", {}) or {}
            text = " ".join(
                [
                    getattr(item, "content", "") or "",
                    getattr(item, "source", "") or "",
                    getattr(item, "url", "") or "",
                    str(metadata.get("title") or ""),
                ]
            )
            if query_domain != "general":
                relevance = calculate_query_relevance(query, text, domain=query_domain, source=getattr(item, "source", None), source_type=metadata.get("source_type"))
                if relevance < threshold:
                    continue
                item.query_relevance_score = round(relevance * 100.0, 1)
            else:
                item.query_relevance_score = round(float(getattr(item, "score", 0.0) or 0.0) * 100.0, 1)
            if not self._text_matches_domain(text, query_domain):
                continue
            if is_github_repo_noise(text, source=getattr(item, "source", None), source_type=metadata.get("source_type")):
                continue
            item.query_domain = query_domain or item.query_domain
            item.query_id = metadata.get("query_id") or item.query_id
            filtered.append(item)
        return filtered

    def _domain_terms(self, domain: str) -> set[str]:
        return {
            "fitness": {"fitness", "workout", "gym", "wellness", "nutrition", "sports", "health", "coach", "member", "runner", "running", "treadmill", "cardio", "race"},
            "cybersecurity": {"cyber", "security", "threat", "incident", "alert", "siem", "soc", "vulnerability", "cloud", "identity"},
            "amazon": {"amazon", "seller", "marketplace", "inventory", "pricing", "review", "reviews", "listing", "ads", "fba"},
            "education": {"education", "learning", "student", "teacher", "course", "classroom", "exam", "study"},
            "productivity": {"student", "study", "productivity", "focus", "assignment", "notes", "habit", "time management"},
            "fintech": {"fintech", "finance", "payment", "fraud", "bank", "lending", "risk", "transaction"},
        }.get(domain, set())

    def _domain_negative_terms(self, domain: str) -> set[str]:
        return {
            "fitness": {"github copilot", "admin ui", "staging", "queue", "json api", "backend", "frontend", "codealpha", "exercise crud", "copy to clipboard", "build applications", "task", "application"},
            "cybersecurity": {"realestate", "rental property", "student", "education", "amazon", "seller"},
            "amazon": {"student", "education", "fitness", "workout", "realestate", "rental property"},
            "education": {"amazon", "seller", "fitness", "workout", "realestate", "rental property"},
            "productivity": {"amazon", "seller", "fitness", "workout", "realestate", "rental property"},
            "fintech": {"education", "student", "fitness", "workout", "realestate", "rental property"},
        }.get(domain, set())

    def _text_matches_domain(self, text: str, domain: str) -> bool:
        if domain == "general":
            return True
        terms = self._domain_terms(domain)
        if not terms:
            return True
        lowered = text.lower()
        if any(term in lowered for term in self._domain_negative_terms(domain)):
            return False
        if domain == "fitness":
            strong_terms = {"fitness", "workout", "gym", "wellness", "nutrition", "sports", "health", "coach", "member", "runner", "running", "treadmill", "cardio", "race"}
            weak_terms = {"training", "exercise", "routine", "habit", "progress"}
            if any(term in lowered for term in strong_terms):
                return True
            return sum(1 for term in weak_terms if term in lowered) >= 2
        return any(term in lowered for term in terms)

    async def _ensure_ready(self) -> None:
        health = await self._chroma.health(self._collection_name)
        if not health["chromadb_connected"]:
            settings = get_settings()
            chroma_target = settings.chroma_url or f"{settings.chroma_host}:{settings.chroma_port}"
            raise RuntimeError(
                f"ChromaDB unavailable at {chroma_target}. "
                "Start ChromaDB before using RAG."
            )

    def _build_results(self, raw: dict) -> list[SearchResult]:
        search_results = []
        ids = raw.get("ids") or []
        documents = raw.get("documents") or []
        metadatas = raw.get("metadatas") or []
        distances = raw.get("distances") or []
        if ids and ids[0]:
            for i, _doc_id in enumerate(ids[0]):
                metadata = metadatas[0][i] if metadatas and metadatas[0] else {}
                distance = distances[0][i] if distances and distances[0] else 0
                score = max(0.0, min(1.0, 1 - float(distance)))
                search_results.append(
                    SearchResult(
                        content=documents[0][i],
                        source=metadata.get("source"),
                        url=metadata.get("url"),
                        score=round(score, 4),
                        query_id=metadata.get("query_id") or None,
                        query_domain=metadata.get("query_domain") or "general",
                        query_relevance_score=float(metadata.get("query_relevance_score", 0.0) or 0.0),
                        timestamp=metadata.get("collected_at") or metadata.get("timestamp"),
                        collected_at=metadata.get("collected_at") or metadata.get("timestamp"),
                        metadata=metadata,
                    )
                )
        return search_results

    def _result_key(self, result: SearchResult) -> str:
        metadata = result.metadata or {}
        source = (result.source or metadata.get("source") or "unknown").lower().strip()
        url = (result.url or metadata.get("url") or "").lower().strip()
        raw_title = metadata.get("title")
        if not raw_title and result.content:
            raw_title = result.content.splitlines()[0]
        title = str(raw_title or "").lower().strip()
        content_hash = hashlib.sha1((result.content or "").strip().lower().encode("utf-8")).hexdigest()
        if url:
            return f"url:{source}:{url}"
        return f"{source}:{title}:{content_hash}"

    def _dedupe_and_diversify(self, results: list[SearchResult], top_k: int) -> list[SearchResult]:
        best_by_key: dict[str, SearchResult] = {}
        for item in results:
            key = self._result_key(item)
            existing = best_by_key.get(key)
            if not existing or item.score > existing.score:
                best_by_key[key] = item

        ordered = sorted(best_by_key.values(), key=lambda x: -x.score)
        diversified: list[SearchResult] = []
        per_source: dict[str, int] = {}
        for item in ordered:
            source = (item.source or "unknown").lower()
            if per_source.get(source, 0) >= 2:
                continue
            per_source[source] = per_source.get(source, 0) + 1
            diversified.append(item)
            if len(diversified) >= top_k:
                return diversified[:top_k]

        if len(diversified) < top_k:
            for item in ordered:
                if item in diversified:
                    continue
                diversified.append(item)
                if len(diversified) >= top_k:
                    break
        return diversified[:top_k]

    def _bm25_keyword_search(self, query: str, documents: list[str], k: int = 10) -> list[tuple[int, float]]:
        query_terms = re.findall(r"\w+", query.lower())
        if not query_terms:
            return []

        doc_scores = []
        for i, doc in enumerate(documents):
            doc_lower = doc.lower()
            score = sum(1 for term in query_terms if term in doc_lower)
            doc_scores.append((i, float(score)))
        doc_scores.sort(key=lambda x: -x[1])
        return doc_scores[:k]

    async def _postgres_fallback_search(
        self,
        query: str,
        top_k: int = 10,
        query_id: str | None = None,
        query_domain: str | None = None,
        source: str | None = None,
        source_type: str | None = None,
        hours_ago: int | None = None,
        days_ago: int | None = None,
    ) -> list[SearchResult]:
        query_terms = [term for term in re.findall(r"\w+", query.lower()) if len(term) > 2]
        async with async_session() as session:
            stmt = select(MarketSignal)
            conditions = []
            if query_id:
                try:
                    query_uuid = uuid.UUID(str(query_id))
                    conditions.append(MarketSignal.query_id == query_uuid)
                except Exception:
                    pass
            if query_domain and query_domain != "general":
                conditions.append(MarketSignal.query_domain == query_domain)
            if source:
                conditions.append(MarketSignal.source == source)
            if source_type:
                conditions.append(MarketSignal.source_type == source_type)
            if hours_ago is not None:
                cutoff = datetime.utcnow() - timedelta(hours=hours_ago)
                conditions.append(MarketSignal.collected_at >= cutoff)
            elif days_ago is not None:
                cutoff = datetime.utcnow() - timedelta(days=days_ago)
                conditions.append(MarketSignal.collected_at >= cutoff)
            if query_terms:
                text_filters = [MarketSignal.title.ilike(f"%{term}%") for term in query_terms[:4]]
                text_filters += [MarketSignal.content.ilike(f"%{term}%") for term in query_terms[:4]]
                conditions.append(or_(*text_filters))
            if conditions:
                stmt = stmt.where(*conditions)
            stmt = stmt.order_by(desc(MarketSignal.collected_at)).limit(top_k)
            result = await session.execute(stmt)
            signals = result.scalars().all()

        results: list[SearchResult] = []
        for signal in signals:
            text = f"{signal.title} {signal.content}".lower()
            score_hits = sum(1 for term in query_terms if term in text) if query_terms else 1
            score = min(1.0, score_hits / max(len(query_terms), 1)) if query_terms else 1.0
            results.append(
                SearchResult(
                    content=f"{signal.title}\n{signal.content}",
                    source=signal.source,
                    url=signal.url,
                    score=float(score),
                    timestamp=signal.collected_at.isoformat() if signal.collected_at else None,
                    collected_at=signal.collected_at.isoformat() if signal.collected_at else None,
                    metadata={
                        "source": signal.source,
                        "source_type": signal.source_type,
                        "url": signal.url,
                        "collected_at": signal.collected_at.isoformat() if signal.collected_at else None,
                    },
                )
            )
        return self._relevant_results(sorted(results, key=lambda x: -x.score), query=query, threshold=0.70, query_domain=query_domain or "general")[:top_k]

    async def similarity_search(
        self,
        query: str,
        top_k: int = 10,
        query_id: str | None = None,
        query_domain: str | None = None,
        where: dict | None = None,
    ) -> list[SearchResult]:
        await self._ensure_ready()
        resolved_domain = query_domain or self.infer_query_domain(query)
        query_where = self._build_where(query_id=query_id, query_domain=resolved_domain, where=where)
        try:
            query_embedding = await self._embedding_service.embed_text(query)
            query_kwargs = {
                "query_embeddings": [query_embedding],
                "n_results": top_k,
                "collection_name": self._collection_name,
            }
            if query_where is not None:
                query_kwargs["where"] = query_where
            raw = await self._chroma.query_documents(**query_kwargs)
            search_results = self._dedupe_and_diversify(self._relevant_results(self._build_results(raw), query=query, query_domain=resolved_domain), top_k)
            logger.info("Found %d results for query", len(search_results))
            if search_results:
                return search_results
        except Exception as exc:
            logger.warning("Vector similarity search degraded to PostgreSQL fallback for query=%r: %s", query, exc)
        return await self._postgres_fallback_search(
            query,
            top_k=top_k,
            query_id=query_id,
            query_domain=resolved_domain,
        )

    async def filtered_search(
        self,
        query: str,
        top_k: int = 10,
        query_id: str | None = None,
        query_domain: str | None = None,
        source: str | None = None,
        source_type: str | None = None,
        where: dict | None = None,
    ) -> list[SearchResult]:
        await self._ensure_ready()
        resolved_domain = query_domain or self.infer_query_domain(query)
        query_where = self._build_where(
            query_id=query_id,
            query_domain=resolved_domain,
            source=source,
            source_type=source_type,
            where=where,
        )

        try:
            query_embedding = await self._embedding_service.embed_text(query)
            query_kwargs = {
                "query_embeddings": [query_embedding],
                "n_results": top_k,
                "collection_name": self._collection_name,
            }
            if query_where is not None:
                query_kwargs["where"] = query_where
            raw = await self._chroma.query_documents(**query_kwargs)
            search_results = self._dedupe_and_diversify(self._relevant_results(self._build_results(raw), query=query, query_domain=resolved_domain), top_k)
            logger.info("Filtered search returned %d results (source=%s)", len(search_results), source)
            if search_results:
                return search_results
        except Exception as exc:
            logger.warning("Filtered RAG search degraded to PostgreSQL fallback for query=%r: %s", query, exc)
        return await self._postgres_fallback_search(
            query,
            top_k=top_k,
            query_id=query_id,
            query_domain=resolved_domain,
            source=source,
            source_type=source_type,
        )

    async def time_based_search(
        self,
        query: str,
        top_k: int = 10,
        query_id: str | None = None,
        query_domain: str | None = None,
        hours_ago: int | None = None,
        days_ago: int | None = None,
        where: dict | None = None,
    ) -> list[SearchResult]:
        await self._ensure_ready()
        resolved_domain = query_domain or self.infer_query_domain(query)
        where_filter = None
        if hours_ago is not None:
            cutoff = (datetime.utcnow() - timedelta(hours=hours_ago)).isoformat()
            where_filter = {"collected_at": {"$gte": cutoff}}
        elif days_ago is not None:
            cutoff = (datetime.utcnow() - timedelta(days=days_ago)).isoformat()
            where_filter = {"collected_at": {"$gte": cutoff}}
        if where:
            where_filter = {"$and": [where_filter, where]} if where_filter else where
        where_filter = self._build_where(query_id=query_id, query_domain=resolved_domain, where=where_filter)

        try:
            query_embedding = await self._embedding_service.embed_text(query)
            query_kwargs = {
                "query_embeddings": [query_embedding],
                "n_results": top_k,
                "collection_name": self._collection_name,
            }
            if where_filter is not None:
                query_kwargs["where"] = where_filter
            raw = await self._chroma.query_documents(**query_kwargs)
            search_results = self._dedupe_and_diversify(self._relevant_results(self._build_results(raw), query=query, query_domain=resolved_domain), top_k)
            logger.info(
                "Time-based search returned %d results (hours_ago=%s, days_ago=%s)",
                len(search_results),
                hours_ago,
                days_ago,
            )
            if search_results:
                return search_results
        except Exception as exc:
            logger.warning("Time-based RAG search degraded to PostgreSQL fallback for query=%r: %s", query, exc)
        return await self._postgres_fallback_search(
            query,
            top_k=top_k,
            query_id=query_id,
            query_domain=resolved_domain,
            hours_ago=hours_ago,
            days_ago=days_ago,
        )

    async def hybrid_search(
        self,
        query: str,
        top_k: int = 10,
        query_id: str | None = None,
        query_domain: str | None = None,
        source: str | None = None,
        source_type: str | None = None,
        where: dict | None = None,
    ) -> list[SearchResult]:
        vector_results = await self.filtered_search(
            query,
            top_k=top_k * 2,
            query_id=query_id,
            query_domain=query_domain,
            source=source,
            source_type=source_type,
            where=where,
        )

        keyword_hits = self._bm25_keyword_search(query, [r.content for r in vector_results], k=top_k * 2)
        keyword_indices = {idx for idx, _ in keyword_hits}

        combined = {}
        for i, result in enumerate(vector_results):
            boost = 0.2 if i in keyword_indices else 0.0
            combined[i] = SearchResult(
                content=result.content,
                source=result.source,
                url=result.url,
                score=round(result.score + boost, 4),
                timestamp=result.timestamp,
                collected_at=getattr(result, "collected_at", None) or result.timestamp,
                metadata=result.metadata,
            )

        sorted_results = self._dedupe_and_diversify(self._relevant_results(list(combined.values()), query=query, query_domain=query_domain or "general"), top_k)
        logger.info("Hybrid search returned %d results", len(sorted_results))
        return sorted_results

    async def search_evidence(
        self,
        query: str,
        top_k: int = 10,
        expanded_terms: list[str] | None = None,
        query_id: str | None = None,
        query_domain: str | None = None,
    ) -> list[SearchResult]:
        terms = expanded_terms or []
        expanded_query = " ".join([query, *terms]).strip()
        resolved_domain = query_domain or self.infer_query_domain(query)
        query_where = self._build_where(query_id=query_id, query_domain=resolved_domain)

        try:
            results = await self.hybrid_search(query, top_k=top_k, query_id=query_id, query_domain=resolved_domain, where=query_where)
            if len(results) >= 3:
                return results
        except Exception as exc:
            logger.warning("Primary RAG search failed for query=%r: %s", query, exc)

        if expanded_query and expanded_query != query:
            try:
                results = await self.hybrid_search(expanded_query, top_k=top_k, query_id=query_id, query_domain=resolved_domain, where=query_where)
                if len(results) >= 3:
                    return results
            except Exception as exc:
                logger.warning("Expanded RAG search failed for query=%r: %s", query, exc)

        fallback_terms = terms[:10] if terms else re.findall(r"\w+", query.lower())[:10]
        results = await self._postgres_fallback_search(
            expanded_query or query,
            top_k=top_k,
            query_id=query_id,
            query_domain=resolved_domain,
            hours_ago=24 * 30,
        )
        if len(results) < 3 and fallback_terms:
            fallback_query = " ".join(fallback_terms)
            more_results = await self._postgres_fallback_search(
                fallback_query,
                top_k=top_k,
                query_id=query_id,
                query_domain=resolved_domain,
                hours_ago=24 * 365,
            )
            results = self._dedupe_and_diversify(results + more_results, top_k)
        return self._dedupe_and_diversify(results, top_k)

    async def opportunity_search(self, query: str, top_k: int = 10) -> list[SearchResult]:
        opp_keywords = ["gap", "opportunity", "pain", "problem", "need", "missing", "lack", "frustration", "demand"]
        expanded_query = f"{query} {' '.join(opp_keywords[:3])}"
        results = await self.hybrid_search(expanded_query, top_k=top_k, query_domain=self.infer_query_domain(query))
        logger.info("Opportunity search returned %d results", len(results))
        return results

    async def multi_source_search(
        self,
        query: str,
        sources: list[str] | None = None,
        top_k: int = 10,
    ) -> list[SearchResult]:
        if not sources:
            return await self.hybrid_search(query, top_k=top_k, query_domain=self.infer_query_domain(query))

        all_results = []
        per_source = max(1, top_k // len(sources))
        for source in sources:
            results = await self.filtered_search(query, top_k=per_source, source=source, query_domain=self.infer_query_domain(query))
            all_results.extend(results)

        return self._dedupe_and_diversify(all_results, top_k)

    async def get_document_context(self, query: str, top_k: int = 10) -> list[SearchResult]:
        return await self.similarity_search(query, top_k, query_domain=self.infer_query_domain(query))
