import re
from datetime import datetime, timezone
from app.schemas.signals import Signal
from app.services.source_scoring import score_source
from app.utils.logging import get_logger

logger = get_logger("services.signal_quality")

SOURCE_RELIABILITY = {
    "github": 0.85,
    "hackernews": 0.90,
    "rss": 0.75,
    "stackexchange": 0.78,
    "reddit": 0.70,
    "google_trends": 0.80,
}

MIN_QUALITY_SCORE = 0.30

MARKET_KEYWORDS = [
    "marketing", "sales", "crm", "lead generation", "campaign", "seo", "content",
    "automation", "workflow", "recruitment", "recruiting", "restaurant", "pos",
    "legal", "contract", "document", "student", "study", "productivity", "hr",
    "startup", "saas", "market", "customer", "revenue", "growth",
    "demand", "pain", "problem", "solution", "tool", "platform",
    "automation", "ai", "machine learning", "api", "integration",
    "subscription", "pricing", "b2b", "b2c", "enterprise", "startup",
    "feedback", "feature", "mvp", "launch", "scale", "fundraising",
    "investor", "vc", "product-market fit", "churn", "retention",
    "acquisition", "conversion", "onboarding", "workflow", "no-code",
    "low-code", "developer", "open source", "freemium", "prosumer",
]

SPAM_PATTERNS = [
    r"\b(buy now|click here|limited offer|act fast|free money)\b",
    r"\b(earn \$|make money|passive income|financial freedom)\b",
    r"\b(crypto pump|guaranteed returns|100x)\b",
]


class SignalQualityService:
    def __init__(self) -> None:
        self._keyword_set = set(kw.lower() for kw in MARKET_KEYWORDS)
        self._spam_re = re.compile("|".join(SPAM_PATTERNS), re.IGNORECASE)

    def score_signal(self, signal: Signal) -> float:
        reliability = self._source_reliability(signal)
        recency = self._recency_score(signal)
        engagement = self._engagement_score(signal)
        content = self._content_quality(signal)
        keyword = self._keyword_relevance(signal)

        weights = {
            "reliability": 0.25,
            "recency": 0.20,
            "engagement": 0.20,
            "content": 0.15,
            "keyword": 0.20,
        }
        score = (
            weights["reliability"] * reliability
            + weights["recency"] * recency
            + weights["engagement"] * engagement
            + weights["content"] * content
            + weights["keyword"] * keyword
        )
        return round(min(1.0, max(0.0, score)), 3)

    def _source_reliability(self, signal: Signal) -> float:
        return SOURCE_RELIABILITY.get(signal.source, 0.50)

    def _recency_score(self, signal: Signal) -> float:
        now = datetime.now(timezone.utc)
        if signal.created_at:
            created_at = signal.created_at if signal.created_at.tzinfo else signal.created_at.replace(tzinfo=timezone.utc)
            age_hours = (now - created_at).total_seconds() / 3600
        elif signal.collected_at:
            collected_at = signal.collected_at if signal.collected_at.tzinfo else signal.collected_at.replace(tzinfo=timezone.utc)
            age_hours = (now - collected_at).total_seconds() / 3600
        else:
            return 0.50
        if age_hours < 1:
            return 1.0
        if age_hours < 24:
            return 0.90
        if age_hours < 168:
            return 0.70
        if age_hours < 720:
            return 0.50
        return 0.30

    def _engagement_score(self, signal: Signal) -> float:
        score = 0.0
        if signal.score > 1000:
            score += 0.40
        elif signal.score > 100:
            score += 0.30
        elif signal.score > 10:
            score += 0.20
        else:
            score += 0.10

        if signal.comments_count > 100:
            score += 0.30
        elif signal.comments_count > 20:
            score += 0.20
        elif signal.comments_count > 5:
            score += 0.10

        return min(1.0, score)

    def _content_quality(self, signal: Signal) -> float:
        score = 0.0
        if signal.title and len(signal.title) > 10:
            score += 0.30
        elif signal.title:
            score += 0.15

        if signal.content and len(signal.content) > 50:
            score += 0.40
        elif signal.content and len(signal.content) > 10:
            score += 0.20

        if signal.url:
            score += 0.15

        if signal.author:
            score += 0.15

        return min(1.0, score)

    def _keyword_relevance(self, signal: Signal) -> float:
        text = f"{signal.title} {signal.content}".lower()
        if not text.strip():
            return 0.0

        words = set(re.findall(r"\w+", text))
        matches = words & self._keyword_set
        if not matches:
            return 0.1

        ratio = len(matches) / len(self._keyword_set)
        return min(1.0, 0.3 + ratio * 5.0)

    def is_spam(self, signal: Signal) -> bool:
        text = f"{signal.title} {signal.content}"
        if self._spam_re.search(text):
            return True
        if signal.comments_count == 0 and signal.score == 0 and len(signal.content) < 5:
            return True
        return False

    def filter_signals(self, signals: list[Signal], min_score: float = MIN_QUALITY_SCORE) -> list[Signal]:
        filtered = []
        rejected = 0
        spam_rejected = 0
        for signal in signals:
            if self.is_spam(signal):
                spam_rejected += 1
                continue
            quality = self.score_signal(signal)
            if quality >= min_score:
                signal.metadata["quality_score"] = quality
                filtered.append(signal)
            else:
                rejected += 1
        if rejected or spam_rejected:
            logger.info(
                "Quality filter: %d/%d passed (score_rejected=%d, spam_rejected=%d)",
                len(filtered), len(signals), rejected, spam_rejected,
            )
        return filtered


quality_service = SignalQualityService()
