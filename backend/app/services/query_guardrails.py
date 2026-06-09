from __future__ import annotations

import re
from typing import Any

DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "accounting": (
        "accounting",
        "bookkeeping",
        "bookkeeper",
        "small business accounting",
        "small business",
        "invoice",
        "invoicing",
        "invoice reconciliation",
        "receipt",
        "receipt scanning",
        "expense",
        "expense tracking",
        "expenses",
        "cash flow",
        "cash flow forecasting",
        "cashflow",
        "payroll",
        "payroll automation",
        "tax",
        "tax compliance",
        "vat",
        "gst",
        "ledger",
        "reconciliation",
        "accounts payable",
        "accounts receivable",
        "financial reporting",
        "bookkeeping automation",
    ),
    "fitness": (
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
        "health",
        "tracker",
        "tracking",
        "wearable",
        "wearables",
        "fitbit",
        "athletic",
        "performance",
        "recovery",
        "coach",
        "member",
        "running",
        "runner",
        "cardio",
    ),
    "cybersecurity": (
        "cybersecurity",
        "cyber security",
        "infosec",
        "security",
        "soc",
        "threat detection",
        "incident response",
        "vulnerability",
        "identity",
        "cloud security",
        "access",
    ),
    "education": (
        "education",
        "learning",
        "student",
        "students",
        "teacher",
        "course",
        "classroom",
        "exam",
        "study",
        "tutor",
        "tutoring",
        "edtech",
        "school",
        "college",
        "lesson",
        "assessment",
        "lms",
    ),
    "amazon": (
        "amazon",
        "seller",
        "marketplace",
        "ecommerce",
        "fba",
        "inventory",
        "listing",
        "pricing",
        "reviews",
        "review",
        "ads",
        "asin",
        "ppc",
        "keyword",
        "product research",
    ),
    "productivity": (
        "productivity",
        "study",
        "focus",
        "assignment",
        "assignments",
        "notes",
        "habit",
        "time management",
        "student",
    ),
    "fintech": (
        "fintech",
        "finance",
        "banking",
        "payment",
        "payments",
        "fraud",
        "risk",
        "lending",
        "underwriting",
    ),
}

DOMAIN_NEGATIVE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "accounting": (
        "fitness",
        "workout",
        "gym",
        "education",
        "student",
        "teacher",
        "course",
        "real estate",
        "rental property",
        "cybersecurity",
    ),
    "fitness": (
        "education",
        "student",
        "teacher",
        "course",
        "classroom",
        "rental property",
        "real estate",
        "governance",
        "compliance",
    ),
    "cybersecurity": (
        "rental property",
        "real estate",
        "teacher",
        "student",
        "course",
    ),
    "education": (
        "fitness",
        "workout",
        "gym",
        "amazon",
        "seller",
        "rental property",
        "real estate",
    ),
    "amazon": (
        "fitness",
        "workout",
        "gym",
        "education",
        "student",
        "teacher",
        "rental property",
        "real estate",
    ),
    "productivity": (
        "fitness",
        "workout",
        "gym",
        "rental property",
        "real estate",
    ),
    "fintech": (
        "fitness",
        "workout",
        "gym",
        "education",
        "student",
        "teacher",
        "rental property",
        "real estate",
    ),
}

QUERY_FILLER_WORDS = {
    "find",
    "finds",
    "opportunity",
    "opportunities",
    "discover",
    "discovering",
    "startup",
    "startups",
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

REPO_LIKE_RE = re.compile(r"^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?$")
SLUGLIKE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{7,}$")
NUMERIC_USERNAME_RE = re.compile(r"^(?:[A-Za-z]+[0-9]{2,}|[0-9]{2,}[A-Za-z]+)$")


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def infer_query_domain(query: str) -> str:
    query_lower = normalize_text(query)
    if "student" in query_lower and "productivity" in query_lower:
        return "productivity"
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if any(keyword in query_lower for keyword in keywords):
            return domain
    return "general"


def query_terms(query: str) -> list[str]:
    terms = [
        term
        for term in re.findall(r"[A-Za-z][A-Za-z0-9+.-]{2,}", normalize_text(query))
        if term not in QUERY_FILLER_WORDS
    ]
    return terms[:6]


def _domain_keywords(domain: str) -> tuple[str, ...]:
    return DOMAIN_KEYWORDS.get(domain, ())


def _negative_keywords(domain: str) -> tuple[str, ...]:
    return DOMAIN_NEGATIVE_KEYWORDS.get(domain, ())


def has_negative_domain_terms(text: str, *, domain: str | None = None) -> bool:
    resolved_domain = domain or "general"
    lowered = normalize_text(text)
    return any(keyword in lowered for keyword in _negative_keywords(resolved_domain))


def is_github_repo_noise(text: str, *, source: str | None = None, source_type: str | None = None) -> bool:
    lowered = normalize_text(text)
    if source and source.lower() != "github" and (source_type or "").lower() not in {"repository", "repo", "issue", "pull_request"}:
        return False

    if "/" in lowered and REPO_LIKE_RE.match(lowered.replace(" ", "")):
        return True

    parts = [part for part in re.split(r"[\s/_-]+", lowered) if part]
    if len(parts) >= 3 and all(len(part) >= 3 for part in parts):
        if any(term in lowered for term in ("repo", "repository", "project", "skill", "copilot", "assistant", "tool", "platform")):
            return True

    if source and source.lower() == "github":
        if ("-" in lowered or "_" in lowered or "/" in lowered) and len(parts) >= 3:
            return True
    return False


def is_opportunity_name_noise(
    text: str,
    *,
    query: str | None = None,
    domain: str | None = None,
) -> bool:
    lowered = normalize_text(text)
    if not lowered:
        return True

    compact = re.sub(r"\s+", "", lowered)
    parts = [part for part in re.split(r"[\s/_-]+", lowered) if part]

    if "/" in lowered or ("-" in lowered and len(parts) >= 2):
        if len(parts) >= 3 or REPO_LIKE_RE.match(lowered.replace(" ", "")):
            return True

    if len(parts) == 1 and len(compact) >= 18 and SLUGLIKE_NAME_RE.match(compact):
        return True

    if len(parts) <= 3 and any(NUMERIC_USERNAME_RE.match(part) for part in parts):
        return True

    if any(len(part) >= 18 for part in parts):
        return True

    if len(parts) <= 2 and any(len(part) >= 18 for part in parts):
        return True

    return False


def extract_relevance_features(query: str, text: str, *, domain: str | None = None) -> tuple[int, int, int]:
    query = normalize_text(query)
    text = normalize_text(text)
    resolved_domain = domain or infer_query_domain(query)
    terms = query_terms(query)
    direct_hits = sum(1 for term in terms if term in text)
    domain_hits = sum(1 for keyword in _domain_keywords(resolved_domain) if keyword in text)
    negative_hits = sum(1 for keyword in _negative_keywords(resolved_domain) if keyword in text)
    return direct_hits, domain_hits, negative_hits


def calculate_query_relevance_score(query: str, text: str, *, domain: str | None = None, source: str | None = None, source_type: str | None = None) -> float:
    query = normalize_text(query)
    text = normalize_text(text)
    if not query or not text:
        return 0.0

    resolved_domain = domain or infer_query_domain(query)
    direct_hits, domain_hits, negative_hits = extract_relevance_features(query, text, domain=resolved_domain)
    query_token_count = max(len(query_terms(query)), 1)
    text_length_bonus = 1.0 if len(text) > 40 else 0.5 if len(text) > 15 else 0.0
    source_bonus = 1 if source and source.lower() in {"github", "hackernews", "reddit", "rss", "google_trends"} else 0
    source_bonus += 1 if source_type and source_type.lower() in {"repository", "story", "post", "article", "trend"} else 0

    score = (
        (direct_hits / query_token_count) * 30.0
        + min(55.0, domain_hits * 20.0)
        + min(15.0, text_length_bonus * 15.0)
        + min(20.0, source_bonus * 10.0)
    )

    if resolved_domain != "general":
        if negative_hits:
            score -= min(45.0, negative_hits * 14.0)
        if domain_hits == 0:
            score -= 25.0
        elif source and source.lower() in {"github", "hackernews", "reddit", "rss", "google_trends"}:
            score += 5.0
        elif domain_hits >= 3:
            score += 18.0
        elif domain_hits >= 2:
            score += 12.0

    if is_github_repo_noise(text, source=source, source_type=source_type):
        score -= 35.0

    return round(max(0.0, min(100.0, score)), 1)


def calculate_domain_relevance_score(text: str, *, domain: str, source: str | None = None, source_type: str | None = None) -> float:
    text = normalize_text(text)
    if not text:
        return 0.0

    if domain == "general":
        return 50.0

    domain_hits = sum(1 for keyword in _domain_keywords(domain) if keyword in text)
    negative_hits = sum(1 for keyword in _negative_keywords(domain) if keyword in text)
    text_length_bonus = 1.0 if len(text) > 40 else 0.5 if len(text) > 15 else 0.0
    source_bonus = 1 if source and source.lower() in {"github", "hackernews", "reddit", "rss", "google_trends"} else 0
    source_bonus += 1 if source_type and source_type.lower() in {"repository", "story", "post", "article", "trend"} else 0

    score = (
        min(60.0, domain_hits * 40.0)
        + min(15.0, text_length_bonus * 15.0)
        + min(25.0, source_bonus * 12.0)
    )
    if domain_hits == 0:
        score -= 30.0
    if negative_hits:
        score -= min(45.0, negative_hits * 15.0)
    elif source and source.lower() in {"github", "hackernews", "reddit", "rss", "google_trends"}:
        score += 5.0
    elif domain_hits >= 3:
        score += 15.0
    elif domain_hits >= 2:
        score += 9.0
    if is_github_repo_noise(text, source=source, source_type=source_type):
        score -= 35.0

    return round(max(0.0, min(100.0, score)), 1)


def calculate_query_relevance(query: str, text: str, *, domain: str | None = None, source: str | None = None, source_type: str | None = None) -> float:
    return round(calculate_query_relevance_score(query, text, domain=domain, source=source, source_type=source_type) / 100.0, 4)


def is_relevant_to_query(
    query: str,
    text: str,
    *,
    domain: str | None = None,
    threshold: float = 0.70,
    source: str | None = None,
    source_type: str | None = None,
) -> bool:
    return calculate_query_relevance(query, text, domain=domain, source=source, source_type=source_type) >= threshold


def is_query_consistent_with_domain(query: str, text: str, *, domain: str | None = None) -> bool:
    resolved_domain = domain or infer_query_domain(query)
    if resolved_domain == "general":
        return True
    return is_relevant_to_query(query, text, domain=resolved_domain, threshold=0.70)


def is_relevant_to_domain(text: str, *, domain: str, threshold: float = 0.80, source: str | None = None, source_type: str | None = None) -> bool:
    return calculate_domain_relevance_score(text, domain=domain, source=source, source_type=source_type) >= (threshold * 100 if threshold <= 1 else threshold)
