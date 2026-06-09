from __future__ import annotations

import re
import uuid
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Any

from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_signal import MarketSignal
from app.models.startup_opportunity import StartupOpportunity
from app.repositories import opportunity_repository
from app.services.query_guardrails import calculate_domain_relevance_score, calculate_query_relevance_score, infer_query_domain, is_github_repo_noise, is_opportunity_name_noise
from app.utils.logging import get_logger

logger = get_logger("services.opportunity_intelligence")

OPPORTUNITY_SOURCES = {"github", "hackernews", "rss", "google_trends"}
STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "have", "will", "what",
    "your", "into", "about", "when", "been", "they", "them", "there", "their",
    "startup", "startups", "tool", "tools", "product", "products", "service",
    "services", "build", "building", "builds", "need", "needs", "problem",
    "problems", "user", "users", "customers", "customer", "company", "companies",
    "platform", "app", "apps", "feature", "features", "using", "use", "used",
}

DOMAIN_EXPANSIONS = {
    "accounting": [
        "accounting",
        "bookkeeping",
        "small business accounting",
        "invoice reconciliation",
        "expense tracking",
        "receipt scanning",
        "cash flow forecasting",
        "tax compliance",
        "payroll automation",
        "financial reporting",
        "accounts payable",
        "accounts receivable",
    ],
    "education": ["education", "edtech", "learning", "students", "student", "teachers", "teacher", "courses", "course", "exams", "exam", "tutoring", "tutor", "lms", "classroom", "study", "lesson", "assessment", "school", "college"],
    "amazon": ["amazon", "seller", "marketplace", "ecommerce", "fba", "inventory", "reviews", "review", "product research", "listing optimization", "pricing", "ads", "asin", "ppc", "keyword"],
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

SAFE_NAME_TERMS = {
    "education",
    "portal",
    "service",
    "support",
    "assistant",
    "tracker",
    "workflow",
    "hub",
    "planner",
    "engine",
    "tool",
    "exam",
    "examination",
    "distance",
    "board",
    "classroom",
    "learning",
    "student",
    "curriculum",
    "admissions",
    "enrollment",
    "seller",
    "inventory",
    "listing",
    "repricer",
    "productivity",
    "task",
    "study",
    "course",
    "market",
    "gap",
    "gapfinder",
}

GENERIC_NAME_SUFFIXES = {
    "copilot",
    "assistant",
    "tracker",
    "engine",
    "analyzer",
    "platform",
    "system",
    "solution",
    "tool",
    "tools",
    "app",
    "portal",
    "hub",
}

NAME_BANNED_WORDS = {
    "general",
    "platform",
    "solution",
    "business",
    "opportunity",
    "market",
    "tool",
    "tools",
    "analyzer",
    "hub",
    "portal",
    "system",
    "app",
}

GENERIC_CLUSTER_PATTERNS: list[tuple[tuple[str, ...], str]] = [
    (("threat", "attack", "malware", "phishing", "vulnerability", "breach", "ioc", "iocs", "exploit"), "threat_detection"),
    (("incident", "triage", "alert fatigue", "escalation", "ticket"), "incident_response"),
    (("compliance", "audit", "policy", "regulation", "governance"), "compliance"),
    (("cloud", "iam", "identity", "access", "privilege", "zero trust"), "identity_management"),
    (("security", "siem", "soc", "logging", "detection"), "security_analytics"),
    (("fraud", "chargeback", "reconciliation", "transaction", "risk"), "fraud_detection"),
    (("patient", "clinical", "care", "triage", "medical"), "care_coordination"),
    (("recruit", "candidate", "onboarding", "employee", "payroll"), "recruiting"),
    (("supply", "logistics", "warehouse", "procurement", "supplier"), "supply_planning"),
    (("meeting", "async", "collaboration", "handoff", "status"), "async_collaboration"),
    (("debug", "observability", "monitoring", "testing", "deployment"), "observability"),
    (("campaign", "lead", "personalization", "content", "attribution"), "campaign_optimization"),
    (("contract", "case", "discovery", "billing", "legal"), "contract_review"),
    (("booking", "itinerary", "travel", "expense"), "booking"),
    (("player", "retention", "monetization", "anti-cheat", "live ops"), "player_retention"),
    (("property", "tenant", "valuation", "listing", "broker"), "lead_management"),
    (("construction", "safety", "estimating", "procurement", "field"), "project_tracking"),
    (("manufacturing", "quality", "maintenance", "production", "factory"), "quality_control"),
]


def _domain_alias_matches(query_lower: str) -> str | None:
    for domain, aliases in DOMAIN_ALIASES.items():
        if any(alias in query_lower for alias in aliases):
            return domain
    return None


def _topic_words(value: str) -> list[str]:
    words = [word for word in re.findall(r"[A-Za-z][A-Za-z0-9+.-]{2,}", value.lower()) if word not in QUERY_FILLER_WORDS and word not in NAME_BANNED_WORDS]
    return words


def _build_safe_product_name(base_text: str, *, suffix: str = "Copilot") -> str:
    words = _topic_words(base_text)
    if not words:
        words = ["Insight", "Copilot"]
    core = " ".join(word.title() for word in words[:3])
    candidate = f"{core} {suffix}".strip()
    candidate_words = candidate.split()
    if len(candidate_words) < 3:
        candidate = f"{core} Assistant".strip()
    elif len(candidate_words) > 5:
        candidate = " ".join(candidate_words[:4])
    return candidate


def _generic_cluster_for_text(text: str) -> str:
    lowered = text.lower()
    for keywords, cluster_id in GENERIC_CLUSTER_PATTERNS:
        if any(keyword in lowered for keyword in keywords):
            return cluster_id
    tokens = _topic_words(lowered)
    if len(tokens) >= 2:
        return "_".join(tokens[:2])
    if tokens:
        return tokens[0]
    return "insight_tracking"

SOURCE_CREDIBILITY = {
    "github": 0.92,
    "hackernews": 0.88,
    "rss": 0.76,
    "google_trends": 0.82,
    "reddit": 0.72,
}

CLUSTER_BLUEPRINTS: dict[str, dict[str, str]] = {
    "accounting": {
        "bookkeeping_automation": "bookkeeping automation",
        "invoice_reconciliation": "invoice reconciliation",
        "expense_tracking": "expense tracking",
        "receipt_scanning": "receipt scanning",
        "cash_flow_forecasting": "cash flow forecasting",
        "tax_compliance": "tax compliance",
        "payroll_automation": "payroll automation",
        "financial_reporting": "financial reporting",
        "accounts_payable": "accounts payable",
        "accounts_receivable": "accounts receivable",
    },
    "amazon": {
        "inventory_forecasting": "inventory forecasting",
        "review_analysis": "review analysis",
        "listing_optimization": "listing optimization",
        "competitor_pricing": "competitor pricing",
        "fba_cost_monitoring": "FBA cost monitoring",
        "keyword_discovery": "keyword discovery",
        "advertising_optimization": "advertising optimization",
        "demand_prediction": "product demand prediction",
    },
    "education": {
        "curriculum_planning": "curriculum planning",
        "assessment_feedback": "assessment feedback",
        "teacher_workload": "teacher workload automation",
        "course_recommendation": "course recommendation",
        "student_progress": "student progress tracking",
        "study_planning": "study planning",
        "exam_prep": "exam prep",
        "learning_engagement": "learning engagement",
    },
    "productivity": {
        "study_planning": "study planning",
        "focus_management": "focus management",
        "assignment_tracking": "assignment tracking",
        "note_organization": "note organization",
        "habit_building": "habit building",
        "time_management": "time management",
        "exam_prep": "exam prep",
        "schedule_coordination": "schedule coordination",
    },
    "fitness": {
        "workout_tracking": "workout tracking",
        "exercise_library": "exercise library",
        "routine_management": "routine management",
        "data_sync": "data sync",
        "progress_analytics": "progress analytics",
        "endurance_training": "endurance training",
        "nutrition_planning": "nutrition planning",
        "coach_analytics": "coach analytics",
        "member_engagement": "member engagement",
        "health_tracking": "health tracking",
        "wellness_habits": "wellness habits",
        "training_progress": "training progress",
    },
    "cybersecurity": {
        "threat_detection": "threat detection",
        "incident_response": "incident response",
        "compliance": "compliance",
        "cloud_security": "cloud security",
        "identity_management": "identity management",
        "vulnerability_management": "vulnerability management",
        "security_training": "security training",
        "security_analytics": "security analytics",
    },
    "fintech": {
        "fraud_detection": "fraud detection",
        "payments_reconciliation": "payments reconciliation",
        "risk_management": "risk management",
        "underwriting": "underwriting",
        "transaction_monitoring": "transaction monitoring",
        "lending_ops": "lending operations",
        "compliance": "compliance",
        "portfolio_analytics": "portfolio analytics",
    },
    "healthcare": {
        "patient_intake": "patient intake",
        "care_coordination": "care coordination",
        "clinical_documentation": "clinical documentation",
        "billing_revenue_cycle": "billing revenue cycle",
        "triage": "triage",
        "prior_authorization": "prior authorization",
        "claims_workflow": "claims workflow",
        "care_analytics": "care analytics",
    },
    "hrtech": {
        "recruiting": "recruiting",
        "screening": "candidate screening",
        "onboarding": "onboarding",
        "employee_engagement": "employee engagement",
        "performance_management": "performance management",
        "payroll": "payroll",
        "workforce_planning": "workforce planning",
        "talent_analytics": "talent analytics",
    },
    "supply_chain": {
        "demand_planning": "demand planning",
        "inventory_visibility": "inventory visibility",
        "supplier_risk": "supplier risk",
        "logistics_tracking": "logistics tracking",
        "warehouse_automation": "warehouse automation",
        "procurement": "procurement",
        "transport_visibility": "transport visibility",
        "supply_analytics": "supply analytics",
    },
    "remote_work": {
        "async_collaboration": "async collaboration",
        "meeting_productivity": "meeting productivity",
        "knowledge_sharing": "knowledge sharing",
        "task_coordination": "task coordination",
        "status_reporting": "status reporting",
        "handoff_automation": "handoff automation",
        "team_visibility": "team visibility",
        "workstream_tracking": "workstream tracking",
    },
    "climate_tech": {
        "emissions_tracking": "emissions tracking",
        "energy_optimization": "energy optimization",
        "reporting": "reporting",
        "asset_monitoring": "asset monitoring",
        "carbon_analytics": "carbon analytics",
        "sustainability_workflows": "sustainability workflows",
        "compliance": "compliance",
        "climate_risk": "climate risk",
    },
    "developer_tools": {
        "debugging": "debugging",
        "observability": "observability",
        "testing": "testing",
        "ci_cd": "ci/cd",
        "api_monitoring": "api monitoring",
        "documentation": "documentation",
        "deployment": "deployment",
        "incident_response": "incident response",
    },
    "marketing_automation": {
        "campaign_optimization": "campaign optimization",
        "lead_qualification": "lead qualification",
        "attribution": "attribution",
        "content_ops": "content operations",
        "personalization": "personalization",
        "pipeline_analytics": "pipeline analytics",
        "email_automation": "email automation",
        "revenue_ops": "revenue operations",
    },
    "legal_tech": {
        "contract_review": "contract review",
        "case_management": "case management",
        "compliance": "compliance",
        "legal_research": "legal research",
        "billing": "billing",
        "e_discovery": "e-discovery",
        "intake": "intake",
        "legal_ops": "legal operations",
    },
    "travel_tech": {
        "booking": "booking",
        "itinerary": "itinerary planning",
        "expense": "expense management",
        "travel_policy": "travel policy",
        "support": "travel support",
        "trip_optimization": "trip optimization",
        "loyalty": "loyalty optimization",
        "travel_analytics": "travel analytics",
    },
    "gaming": {
        "player_retention": "player retention",
        "live_ops": "live operations",
        "community_moderation": "community moderation",
        "monetization": "monetization",
        "anti_cheat": "anti-cheat",
        "game_analytics": "game analytics",
        "player_support": "player support",
        "content_ops": "content operations",
    },
    "real_estate": {
        "lead_management": "lead management",
        "property_valuation": "property valuation",
        "listing_optimization": "listing optimization",
        "tenant_management": "tenant management",
        "showing_coordination": "showing coordination",
        "deal_workflow": "deal workflow",
        "broker_analytics": "broker analytics",
        "property_ops": "property operations",
    },
    "construction": {
        "project_tracking": "project tracking",
        "safety_monitoring": "safety monitoring",
        "estimating": "estimating",
        "procurement": "procurement",
        "scheduling": "scheduling",
        "crew_coordination": "crew coordination",
        "field_reporting": "field reporting",
        "site_analytics": "site analytics",
    },
    "manufacturing": {
        "quality_control": "quality control",
        "maintenance": "maintenance",
        "production_planning": "production planning",
        "supply_planning": "supply planning",
        "inventory_visibility": "inventory visibility",
        "factory_analytics": "factory analytics",
        "process_automation": "process automation",
        "defect_tracking": "defect tracking",
    },
}


@dataclass
class OpportunityEvidence:
    source: str
    signal_id: str
    title: str
    url: str
    collected_at: str
    source_type: str


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9+.-]{2,}", text.lower())
    return [t for t in tokens if t not in STOPWORDS]


def _join_terms(terms: list[str]) -> str:
    return " ".join(t for t in terms if t).strip()


def _lower_tokens(text: str) -> set[str]:
    return set(_tokenize(text))


def _query_domain(query: str, signals: list[MarketSignal]) -> str:
    combined = _lower_tokens(query)
    for signal in signals:
        combined.update(_lower_tokens(f"{signal.title} {signal.content}"))
    if {"accounting", "bookkeeping", "invoice", "receipt", "expense", "cash flow", "payroll", "tax", "ledger", "reconciliation"} & combined:
        return "accounting"
    if {"amazon", "seller", "inventory", "listing", "pricing"} & combined:
        return "amazon"
    if {"fitness", "workout", "exercise", "gym", "wellness", "nutrition", "sports", "health"} & combined:
        return "fitness"
    if {"student", "education", "course", "learning", "teacher", "classroom"} & combined:
        return "education" if "education" in combined else "student"
    if {"productivity", "focus", "task", "workflow", "study"} & combined:
        return "productivity"
    return "general"


def _domain_match_text(text: str, domain: str) -> bool:
    lowered = text.lower()
    positive_terms = {
        "accounting": {"accounting", "bookkeeping", "invoice", "receipt", "expense", "cash flow", "payroll", "tax", "vat", "gst", "ledger", "reconciliation", "financial", "reporting", "small business", "bookkeeping automation", "invoice reconciliation", "expense tracking", "cash flow forecasting", "tax compliance", "payroll automation", "accounts payable", "accounts receivable"},
        "fitness": {"fitness", "workout", "gym", "wellness", "nutrition", "sports", "health", "coach", "member", "runner", "running", "treadmill", "cardio", "race", "tracker", "tracking", "wearable", "wearables", "athletic", "performance"},
        "cybersecurity": {"cyber", "security", "threat", "incident", "alert", "siem", "soc", "vulnerability", "cloud", "identity", "access", "detection"},
        "amazon": {"amazon", "seller", "marketplace", "ecommerce", "inventory", "pricing", "review", "reviews", "fulfillment", "listing", "product research", "ads", "fba", "asin", "ppc", "keyword"},
        "education": {"education", "edtech", "learning", "student", "students", "teacher", "teachers", "course", "courses", "classroom", "tutor", "tutoring", "exam", "exams", "lms", "study", "lesson", "assessment", "school", "college"},
        "productivity": {"student", "study", "productivity", "focus", "assignment", "notes", "habit", "time management", "exam prep"},
        "fintech": {"fintech", "finance", "payment", "fraud", "risk", "loan", "lending", "underwriting", "transaction", "bank", "reconciliation"},
        "healthcare": {"health", "patient", "clinical", "care", "triage", "medical", "billing", "claims", "hospital", "provider"},
    }
    negative_terms = {
        "accounting": {"fitness", "workout", "gym", "student", "teacher", "course", "real estate", "rental property", "cybersecurity"},
        "fitness": {"github copilot", "admin ui", "staging", "queue", "json api", "backend", "frontend", "codealpha", "exercise crud", "copy to clipboard", "build applications", "task", "application"},
        "cybersecurity": {"realestate", "rental property", "student", "education", "amazon", "seller"},
        "amazon": {"student", "education", "fitness", "workout", "realestate", "rental property"},
        "education": {"amazon", "seller", "fitness", "workout", "realestate", "rental property"},
        "productivity": {"amazon", "seller", "fitness", "workout", "realestate", "rental property"},
        "fintech": {"education", "student", "fitness", "workout", "realestate", "rental property"},
    }
    if domain == "general":
        return True
    if any(term in lowered for term in negative_terms.get(domain, set())):
        return False
    if domain == "fitness":
        strong_terms = {"fitness", "workout", "gym", "wellness", "nutrition", "sports", "health", "coach", "member", "runner", "running", "treadmill", "cardio", "race"}
        weak_terms = {"training", "exercise", "routine", "habit", "progress"}
        if any(term in lowered for term in strong_terms):
            return True
        return sum(1 for term in weak_terms if term in lowered) >= 2
    terms = positive_terms.get(domain, set())
    if not terms:
        return True
    return any(term in lowered for term in terms)


def _select_product_name(
    query: str,
    topic: str,
    signals: list[MarketSignal],
    query_terms: list[str],
    cluster_key: str = "",
    *,
    domain: str = "general",
) -> str:
    text = f"{query} {topic} {cluster_key} {' '.join(f'{s.title} {s.content} {s.source_type}' for s in signals[:5])}".lower()
    cluster_name = _cluster_display_name(domain, cluster_key) if cluster_key else ""
    accounting_names = {
        "bookkeeping_automation": "AI Bookkeeping Assistant",
        "invoice_reconciliation": "Invoice Reconciliation Copilot",
        "expense_tracking": "Expense Categorization Agent",
        "receipt_scanning": "Receipt-to-Accounting Agent",
        "cash_flow_forecasting": "Cash Flow Forecasting Tool",
        "tax_compliance": "Tax Compliance Assistant",
        "payroll_automation": "Payroll Automation Platform",
        "financial_reporting": "Financial Reporting Copilot",
        "accounts_payable": "Accounts Payable Automation",
        "accounts_receivable": "Accounts Receivable Automation",
    }
    amazon_names = {
        "inventory_forecasting": "Seller Inventory Forecasting Copilot",
        "review_analysis": "Amazon Review Pain Analyzer",
        "listing_optimization": "Listing Optimization Intelligence Agent",
        "competitor_pricing": "Marketplace Pricing Intelligence Agent",
        "fba_cost_monitoring": "FBA Cost Monitoring Copilot",
        "keyword_discovery": "Amazon Keyword Discovery Engine",
        "advertising_optimization": "Amazon Ads Optimization Copilot",
        "demand_prediction": "Marketplace Demand Prediction Agent",
    }
    education_names = {
        "student_progress": "AI Student Progress Tracker",
        "study_planning": "AI Study Habit Coach",
        "teacher_workload": "Teacher Workload Automation Assistant",
        "curriculum_planning": "Curriculum Planning Copilot",
        "assessment_feedback": "Assessment Feedback Assistant",
        "course_recommendation": "Personalized Course Recommendation Engine",
        "exam_prep": "AI Exam Prep Copilot",
        "learning_engagement": "Learning Engagement Tracker",
    }
    productivity_names = {
        "focus_management": "Student Focus Planner",
        "assignment_tracking": "Assignment Deadline Planner",
        "time_management": "Study Time Planner",
        "study_planning": "AI Study Habit Coach",
        "note_organization": "Smart Notes Workflow",
        "habit_building": "Habit Building Coach",
        "exam_prep": "Exam Prep Tracker",
        "schedule_coordination": "Schedule Coordination Assistant",
    }
    fitness_names = {
        "workout_tracking": "Workout Tracking Copilot",
        "exercise_library": "Exercise Library Assistant",
        "routine_management": "Routine Management Copilot",
        "data_sync": "Fitness Data Sync Assistant",
        "progress_analytics": "Progress Analytics Copilot",
        "endurance_training": "Endurance Training Copilot",
        "nutrition_planning": "Nutrition Planning Assistant",
        "coach_analytics": "Coach Performance Analytics",
        "member_engagement": "Member Engagement Assistant",
        "health_tracking": "Health Tracking Copilot",
        "wellness_habits": "Wellness Habit Coach",
        "training_progress": "Training Progress Tracker",
    }
    def _finalize(candidate: str) -> str:
        safe_candidate = re.sub(r"\s+", " ", candidate).strip()
        if not safe_candidate:
            safe_candidate = _build_safe_product_name(cluster_name or topic or query or "market insight", suffix="Copilot")
        if is_opportunity_name_noise(safe_candidate, query=query, domain=domain):
            if domain == "accounting" and cluster_key in accounting_names:
                safe_candidate = accounting_names[cluster_key]
            elif domain == "amazon" and cluster_key in amazon_names:
                safe_candidate = amazon_names[cluster_key]
            elif domain == "education" and cluster_key in education_names:
                safe_candidate = education_names[cluster_key]
            elif domain == "productivity" and cluster_key in productivity_names:
                safe_candidate = productivity_names[cluster_key]
            elif domain == "fitness" and cluster_key in fitness_names:
                safe_candidate = fitness_names[cluster_key]
            elif domain in CLUSTER_BLUEPRINTS and cluster_key in CLUSTER_BLUEPRINTS.get(domain, {}):
                safe_candidate = _build_safe_product_name(cluster_name or cluster_key.replace("_", " "), suffix="Copilot")
            elif cluster_name and cluster_name != "general":
                safe_candidate = _build_safe_product_name(cluster_name, suffix="Copilot")
            else:
                safe_candidate = _build_safe_product_name(topic or query or "market insight", suffix="Assistant")
        return safe_candidate

    if domain == "accounting" and cluster_key in accounting_names:
        return _finalize(accounting_names[cluster_key])
    if domain == "amazon" and cluster_key in amazon_names:
        return _finalize(amazon_names[cluster_key])
    if domain == "education" and cluster_key in education_names:
        return _finalize(education_names[cluster_key])
    if domain == "productivity" and cluster_key in productivity_names:
        return _finalize(productivity_names[cluster_key])
    if domain == "fitness" and cluster_key in fitness_names:
        return _finalize(fitness_names[cluster_key])
    if domain in CLUSTER_BLUEPRINTS and cluster_key in CLUSTER_BLUEPRINTS.get(domain, {}):
        return _finalize(_build_safe_product_name(cluster_name or cluster_key.replace("_", " "), suffix="Copilot"))
    if domain != "general" and cluster_name and cluster_name != "general":
        return _finalize(_build_safe_product_name(cluster_name, suffix="Copilot"))
    rules = [
        ({"accounting", "bookkeeping"}, "bookkeeping", "AI Bookkeeping Assistant"),
        ({"accounting", "invoice"}, "invoice", "Invoice Reconciliation Copilot"),
        ({"accounting", "receipt"}, "receipt", "Receipt-to-Accounting Agent"),
        ({"accounting", "cash", "flow"}, "cash", "Cash Flow Forecasting Tool"),
        ({"accounting", "tax"}, "tax", "Tax Compliance Assistant"),
        ({"accounting", "payroll"}, "payroll", "Payroll Automation Platform"),
        ({"accounting", "expense"}, "expense", "Expense Categorization Agent"),
        ({"accounting", "reporting"}, "report", "Financial Reporting Copilot"),
        ({"amazon", "seller"}, "review", "Amazon Review Pain Analyzer"),
        ({"amazon", "seller"}, "inventory", "Seller Inventory Forecasting Copilot"),
        ({"amazon", "seller"}, "pricing", "Marketplace Pricing Intelligence Agent"),
        ({"amazon", "seller"}, "listing", "Seller Listing Optimization Assistant"),
        ({"student"}, "study", "AI Study Habit Coach"),
        ({"student"}, "focus", "Student Focus Planner"),
        ({"student"}, "curriculum", "Student Curriculum Planner"),
        ({"student"}, "productivity", "Campus Productivity Assistant"),
        ({"education"}, "portal", "Personalized Course Recommendation Engine"),
        ({"education"}, "course", "Personalized Course Recommendation Engine"),
        ({"education"}, "teacher", "Teacher Workload Automation Assistant"),
        ({"education"}, "exam", "AI Exam Prep Copilot"),
        ({"education"}, "examination", "AI Exam Prep Copilot"),
        ({"education"}, "distance", "Distance Learning Planner"),
    ]
    for domains, keyword, name in rules:
        if all(domain in text for domain in domains) and keyword in text:
            return _finalize(name)

    if cluster_name and cluster_name not in {"general", ""}:
        return _finalize(_build_safe_product_name(cluster_name, suffix="Copilot"))

    if "amazon" in text and "seller" in text:
        return _finalize("Seller Inventory Forecasting Copilot")
    if "accounting" in text or "bookkeeping" in text or "invoice" in text or "receipt" in text:
        return _finalize("AI Bookkeeping Assistant")
    if "assignment" in text or "deadline" in text:
        return _finalize("Assignment Deadline Planner")
    if "notes" in text or "note-taking" in text:
        return _finalize("Smart Notes Workflow")
    if "time management" in text or "schedule" in text:
        return _finalize("Study Time Planner")
    if "exam" in text or "test prep" in text:
        return _finalize("Exam Prep Tracker")
    if "focus" in text:
        return _finalize("Student Focus Planner")
    if "student" in text and "education" in text:
        return _finalize("AI Student Progress Tracker")
    if "education" in text:
        return _finalize("AI Student Progress Tracker")
    if "productivity" in text:
        return _finalize("Productivity Insight Engine")
    if topic:
        return _finalize(_build_safe_product_name(topic, suffix="Copilot"))
    return _finalize(_build_safe_product_name(query or "market insight", suffix="Copilot"))


def _normalize_name(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def _problem_qualifier(problem: str, existing_name: str) -> str:
    tokens = [t for t in _tokenize(problem) if t not in set(_tokenize(existing_name))]
    if not tokens:
        return ""
    return " ".join(term.title() for term in tokens[:2])


def _name_suffix(base_name: str) -> str:
    words = [w for w in re.findall(r"[A-Za-z0-9]+", base_name) if w]
    filtered = [w for w in words if w.lower() not in GENERIC_NAME_SUFFIXES]
    if len(filtered) >= 2:
        return " ".join(filtered[-2:])
    if filtered:
        return filtered[-1]
    if len(words) >= 2:
        return " ".join(words[-2:])
    if words:
        return words[-1]
    return "Assistant"


def _make_variant_name(base_name: str, problem: str, used_names: set[str], cluster_name: str = "") -> str | None:
    qualifier = _problem_qualifier(problem, base_name)
    suffix = _name_suffix(base_name)
    if cluster_name:
        cluster_words = [word for word in re.findall(r"[A-Za-z0-9]+", cluster_name.title()) if word]
        if len(cluster_words) >= 2:
            candidates = [
                f"{' '.join(cluster_words[:2])} {suffix.split()[-1]}",
                f"{' '.join(cluster_words[:2])} {suffix}",
                f"{' '.join(cluster_words[:2])} Assistant",
            ]
        else:
            candidates = []
    elif qualifier:
        candidates = [
            f"{qualifier} {suffix}",
            f"{qualifier} {suffix.split()[-1]}",
        ]
    else:
        candidates = [f"{suffix} Assistant", f"{suffix} Planner"]

    for candidate in candidates:
        candidate = re.sub(r"\s+", " ", candidate).strip()
        if 3 <= len(candidate.split()) <= 5 and _normalize_name(candidate) not in used_names and not is_opportunity_name_noise(candidate):
            return candidate
    return None


def _phrase_key(signal: MarketSignal) -> str:
    text = f"{signal.title} {signal.content}"
    tokens = _tokenize(text)
    if not tokens:
        return signal.title.lower()[:80] or signal.source_id
    return " ".join(tokens[:3])


def _cluster_label(text: str, domain: str) -> str:
    text = text.lower()
    if domain == "accounting":
        if any(term in text for term in ("expense", "spend", "receipt", "receipt scan", "receipt scanning", "reimbursement")):
            return "expense_tracking"
        if any(term in text for term in ("receipt", "scan", "ocr", "extract", "capture")):
            return "receipt_scanning"
        if any(term in text for term in ("cash flow", "cashflow", "forecast", "forecasting", "runway", "burn")):
            return "cash_flow_forecasting"
        if any(term in text for term in ("invoice", "billing", "ar ", "accounts receivable", "collections", "payment follow-up")):
            return "invoice_reconciliation"
        if any(term in text for term in ("tax", "vat", "gst", "compliance", "filing", "returns")):
            return "tax_compliance"
        if any(term in text for term in ("payroll", "pay run", "compensation", "paystub", "timesheet")):
            return "payroll_automation"
        if any(term in text for term in ("report", "reporting", "close", "month-end", "financial statement")):
            return "financial_reporting"
        if any(term in text for term in ("accounts payable", "ap ", "vendor", "bill pay", "payment run")):
            return "accounts_payable"
        if any(term in text for term in ("accounts receivable", "ar ", "invoice aging", "collections", "dso")):
            return "accounts_receivable"
        if any(term in text for term in ("bookkeeping", "bookkeeper", "ledger", "journal entry", "general ledger")):
            return "bookkeeping_automation"
        if any(term in text for term in ("fraud", "chargeback", "abuse", "anomaly")):
            return "fraud_detection"
        return "bookkeeping_automation"
    if domain == "fitness" and not _domain_match_text(text, domain):
        return "training_progress"
    if domain == "amazon":
        if any(term in text for term in ("review", "ratings", "feedback", "sentiment")):
            return "review_analysis"
        if any(term in text for term in ("pricing", "price", "repricing", "margin", "discount")):
            return "competitor_pricing"
        if any(term in text for term in ("listing", "title", "bullet", "description", "seo", "conversion")):
            return "listing_optimization"
        if any(term in text for term in ("keyword", "search term", "search terms", "seo", "rank")):
            return "keyword_discovery"
        if any(term in text for term in ("ads", "advertising", "ppc", "sponsored", "campaign")):
            return "advertising_optimization"
        if any(term in text for term in ("fba", "fulfillment", "storage", "fees", "fee", "cost")):
            return "fba_cost_monitoring"
        if any(term in text for term in ("forecast", "forecasting", "demand", "predict", "prediction", "stockout", "inventory")):
            return "inventory_forecasting"
        return "demand_prediction"
    if domain == "cybersecurity":
        if any(term in text for term in ("threat", "attack", "malware", "phishing", "exploit", "breach", "ioc", "iocs", "detect", "detection")):
            return "threat_detection"
        if any(term in text for term in ("incident", "triage", "alert", "escalation", "ticket", "playbook", "siem", "soc")):
            return "incident_response"
        if any(term in text for term in ("compliance", "audit", "policy", "governance", "regulation", "soc2", "iso", "gdpr", "hipaa", "pci")):
            return "compliance"
        if any(term in text for term in ("cloud", "kubernetes", "container", "iam", "identity", "access", "zero trust", "aws", "azure", "gcp", "docker", "serverless")):
            return "cloud_security"
        if any(term in text for term in ("vulnerability", "vuln", "patch", "cve", "exploit", "scanner")):
            return "vulnerability_management"
        if any(term in text for term in ("training", "awareness", "phishing simulation", "skills", "labs", "course", "tutorial", "guide", "certification")):
            return "security_training"
        return "security_analytics"
    if domain == "fintech":
        if any(term in text for term in ("banking", "bank", "treasury", "ledger", "cash flow", "cashflow", "financial ops", "finance ops", "bookkeeping", "accounting", "statement")):
            return "banking_operations"
        if any(term in text for term in ("risk", "exposure", "portfolio", "limit", "loss", "anomaly")):
            return "risk_management"
        if any(term in text for term in ("fraud", "chargeback", "abuse")):
            return "fraud_detection"
        if any(term in text for term in ("payment", "reconciliation", "settlement", "payout")):
            return "payments_reconciliation"
        if any(term in text for term in ("underwriting", "loan", "credit", "lending")):
            return "underwriting"
        if any(term in text for term in ("compliance", "kyc", "aml", "audit", "regulation", "sanction")):
            return "compliance"
        return "transaction_monitoring"
    if domain == "healthcare":
        if any(term in text for term in ("patient intake", "intake", "registration", "admission")):
            return "patient_intake"
        if any(term in text for term in ("triage", "routing", "priority")):
            return "triage"
        if any(term in text for term in ("billing", "claims", "revenue cycle", "coding")):
            return "billing_revenue_cycle"
        if any(term in text for term in ("prior auth", "authorization", "preauth")):
            return "prior_authorization"
        if any(term in text for term in ("care", "coordination", "handoff", "referral")):
            return "care_coordination"
        return "clinical_documentation"
    if domain == "hrtech":
        if any(term in text for term in ("recruit", "candidate", "sourcing", "screen")):
            return "recruiting"
        if any(term in text for term in ("onboarding", "orientation")):
            return "onboarding"
        if any(term in text for term in ("engagement", "culture", "retention")):
            return "employee_engagement"
        if any(term in text for term in ("payroll", "compensation")):
            return "payroll"
        return "performance_management"
    if domain == "general":
        return _generic_cluster_for_text(text)
    if domain == "education":
        if any(term in text for term in ("teacher", "teacher workload", "grading", "lesson", "class prep")):
            return "teacher_workload"
        if any(term in text for term in ("curriculum", "course path", "course plan", "syllabus")):
            return "curriculum_planning"
        if any(term in text for term in ("assessment", "feedback", "rubric", "grading", "assignment feedback")):
            return "assessment_feedback"
        if any(term in text for term in ("course", "recommendation", "pathway", "elective")):
            return "course_recommendation"
        if any(term in text for term in ("progress", "tracking", "dashboard", "status")):
            return "student_progress"
        if any(term in text for term in ("exam", "test prep", "exam prep", "revision")):
            return "exam_prep"
        if any(term in text for term in ("engagement", "participation", "retention", "attendance")):
            return "learning_engagement"
        return "study_planning"
    if domain == "productivity":
        if any(term in text for term in ("focus", "distraction", "attention", "pomodoro", "deep work")):
            return "focus_management"
        if any(term in text for term in ("assignment", "deadline", "homework", "project")):
            return "assignment_tracking"
        if any(term in text for term in ("note", "notes", "notion", "knowledge base", "capture")):
            return "note_organization"
        if any(term in text for term in ("habit", "routine", "streak", "consistency")):
            return "habit_building"
        if any(term in text for term in ("schedule", "calendar", "planner", "time management")):
            return "time_management"
        if any(term in text for term in ("exam", "test prep", "revision")):
            return "exam_prep"
        if any(term in text for term in ("study", "learning", "class", "course")):
            return "study_planning"
        return "schedule_coordination"
    if domain == "fitness":
        if any(term in text for term in ("routine", "template", "program template")):
            return "routine_management"
        if any(term in text for term in ("logger", "logging", "log", "workout")):
            return "workout_tracking"
        if any(term in text for term in ("exercise", "rep", "sets", "form", "movement")):
            return "exercise_library"
        if any(term in text for term in ("nutrition", "meal", "diet", "macro", "calorie")):
            return "nutrition_planning"
        if any(term in text for term in ("coach", "trainer", "programming", "analytics", "performance")):
            return "coach_analytics"
        if any(term in text for term in ("member", "engagement", "retention", "churn")):
            return "member_engagement"
        if any(term in text for term in ("health", "tracking", "monitor", "metric", "wearable")):
            return "health_tracking"
        if any(term in text for term in ("habit", "streak", "consistency", "compliance", "adherence")):
            return "wellness_habits"
        if any(term in text for term in ("race", "runner", "running", "treadmill", "cardio", "endurance")):
            return "endurance_training"
        if any(term in text for term in ("dashboard", "output", "display", "clipboard", "progress", "metrics", "analytics")):
            return "progress_analytics"
        if any(term in text for term in ("import", "sync", "integration", "api", "queue", "staging")):
            return "data_sync"
        return "training_progress"
    return "general"


def _cluster_display_name(domain: str, cluster_id: str) -> str:
    blueprint = CLUSTER_BLUEPRINTS.get(domain, {})
    if cluster_id in blueprint:
        return blueprint[cluster_id]
    if domain == "general":
        return cluster_id.replace("_", " ").strip() or "focused opportunity"
    return cluster_id.replace("_", " ")


def _cluster_priority(domain: str, cluster_id: str) -> int:
    priorities = {
        "accounting": [
            "bookkeeping_automation",
            "invoice_reconciliation",
            "expense_tracking",
            "receipt_scanning",
            "cash_flow_forecasting",
            "tax_compliance",
            "payroll_automation",
            "financial_reporting",
            "accounts_payable",
            "accounts_receivable",
            "fraud_detection",
        ],
        "amazon": [
            "inventory_forecasting",
            "review_analysis",
            "listing_optimization",
            "competitor_pricing",
            "fba_cost_monitoring",
            "keyword_discovery",
            "advertising_optimization",
            "demand_prediction",
        ],
        "education": [
            "student_progress",
            "study_planning",
            "teacher_workload",
            "curriculum_planning",
            "assessment_feedback",
            "course_recommendation",
            "exam_prep",
            "learning_engagement",
        ],
        "productivity": [
            "focus_management",
            "assignment_tracking",
            "time_management",
            "study_planning",
            "note_organization",
            "habit_building",
            "exam_prep",
            "schedule_coordination",
        ],
        "fitness": [
            "workout_tracking",
            "exercise_library",
            "routine_management",
            "data_sync",
            "progress_analytics",
            "endurance_training",
            "nutrition_planning",
            "coach_analytics",
            "member_engagement",
            "health_tracking",
            "wellness_habits",
            "training_progress",
        ],
        "cybersecurity": [
            "threat_detection",
            "incident_response",
            "compliance",
            "cloud_security",
            "identity_management",
            "vulnerability_management",
            "security_training",
            "security_analytics",
        ],
        "fintech": [
            "fraud_detection",
            "payments_reconciliation",
            "risk_management",
            "banking_operations",
            "underwriting",
            "transaction_monitoring",
            "lending_ops",
            "compliance",
            "portfolio_analytics",
        ],
        "healthcare": [
            "patient_intake",
            "care_coordination",
            "clinical_documentation",
            "billing_revenue_cycle",
            "triage",
            "prior_authorization",
            "claims_workflow",
            "care_analytics",
        ],
        "hrtech": [
            "recruiting",
            "screening",
            "onboarding",
            "employee_engagement",
            "performance_management",
            "payroll",
            "workforce_planning",
            "talent_analytics",
        ],
    }
    ordered = priorities.get(domain, [])
    try:
        return ordered.index(cluster_id)
    except ValueError:
        if domain == "general":
            generic_order = [
                "threat_detection",
                "fraud_detection",
                "incident_response",
                "compliance",
                "cloud_security",
                "identity_management",
                "patient_intake",
                "care_coordination",
                "recruiting",
                "onboarding",
                "demand_planning",
                "inventory_visibility",
                "async_collaboration",
                "meeting_productivity",
                "observability",
                "campaign_optimization",
                "contract_review",
                "booking",
                "player_retention",
                "lead_management",
                "project_tracking",
                "quality_control",
                "insight_tracking",
            ]
            try:
                return generic_order.index(cluster_id)
            except ValueError:
                return len(generic_order)
        return len(ordered)


def _query_terms(query: str) -> list[str]:
    return [term for term in _tokenize(query) if (len(term) > 2 or term in SHORT_QUERY_TERMS) and term not in QUERY_FILLER_WORDS][:5]


def _signal_text(signal: MarketSignal) -> str:
    return f"{signal.title} {signal.content} {signal.source} {signal.source_type}".lower()


def _signal_query_relevance(query_terms: list[str], signal: MarketSignal) -> float:
    if not query_terms:
        return 0.0
    text = _signal_text(signal)
    hits = sum(1 for term in query_terms if term in text)
    exact_overlap = hits / max(len(query_terms), 1)
    source_bonus = 0.05 if signal.source in {"github", "hackernews", "rss", "google_trends"} else 0.0
    quality_bonus = float(signal.metadata.get("quality_score", 0.5) or 0.5) * 0.15
    recency_bonus = 0.15 if signal.collected_at and signal.collected_at >= datetime.now(timezone.utc) - timedelta(days=14) else 0.0
    score = min(1.0, exact_overlap * 0.6 + source_bonus + quality_bonus + recency_bonus)
    return round(score * 100, 1)


def _salient_terms(signals: list[MarketSignal], query_terms: list[str]) -> list[str]:
    counts = Counter()
    for signal in signals:
        counts.update(_tokenize(f"{signal.title} {signal.content}"))
    filtered = [
        (term, count)
        for term, count in counts.items()
        if term not in query_terms and len(term) > 3 and term.isalpha()
    ]
    filtered.sort(key=lambda item: (-item[1], item[0]))
    terms = [term for term, count in filtered if count >= 1 and term in SAFE_NAME_TERMS][:3]
    return terms


def _competition_level(score: float) -> str:
    if score >= 75:
        return "High"
    if score >= 45:
        return "Medium"
    return "Low"


def _normalize_competition_level(level: str | None, score: float) -> str:
    if not level:
        return _competition_level(score)
    normalized = str(level).strip().lower().replace("_", " ")
    if normalized in {"high", "medium", "low"}:
        return normalized.title()
    if normalized in {"high competition", "competition high"}:
        return "High"
    if normalized in {"medium competition", "competition medium"}:
        return "Medium"
    if normalized in {"low competition", "competition low"}:
        return "Low"
    return _competition_level(score)


def _clamp_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 1)


def _ensure_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _recency_weight(collected_at: datetime | None) -> float:
    ts = _ensure_aware(collected_at)
    if ts is None:
        return 0.45
    age_hours = max((datetime.now(timezone.utc) - ts).total_seconds() / 3600.0, 0.0)
    if age_hours <= 24:
        return 1.0
    if age_hours <= 72:
        return 0.88
    if age_hours <= 168:
        return 0.72
    if age_hours <= 720:
        return 0.58
    return 0.42


def _source_quality(signal: MarketSignal) -> float:
    base = SOURCE_CREDIBILITY.get(signal.source, 0.6)
    metadata = getattr(signal, "extra_metadata", None) or getattr(signal, "metadata", None) or {}
    if not isinstance(metadata, dict):
        metadata = {}
    if signal.source == "github":
        base += min(0.08, float(signal.score or 0) / 1000.0)
    elif signal.source == "hackernews":
        base += min(0.1, float(getattr(signal, "comments_count", 0) or 0) / 120.0)
    elif signal.source == "reddit":
        base += min(0.08, float(getattr(signal, "comments_count", 0) or 0) / 140.0)
    elif signal.source == "google_trends":
        base += min(0.1, float(metadata.get("trend_growth", 0) or 0) / 100.0)
    elif signal.source == "rss":
        base += 0.03 if signal.source_type in {"article", "post"} else 0.0
    return max(0.45, min(1.0, base))


def _signal_textual_support(signal: MarketSignal) -> float:
    text = f"{signal.title} {signal.content}".lower()
    support_terms = [
        "struggle",
        "pain",
        "hard",
        "difficult",
        "missing",
        "need",
        "problem",
        "complaint",
        "request",
        "feature",
        "frustrat",
    ]
    hits = sum(1 for term in support_terms if term in text)
    return min(1.0, hits / 5.0)


def _startup_name_from_topic(topic: str) -> str:
    words = [w for w in re.findall(r"[a-zA-Z0-9]+", topic.title()) if w]
    if not words:
        return "SignalForge"
    return "".join(words[:2])[:24]


def _problem_statement_for(topic: str, query: str, signals: list[MarketSignal], *, domain: str = "general", cluster_key: str = "") -> str:
    text = f"{topic} {query} {cluster_key} {' '.join(f'{s.title} {s.content}' for s in signals[:5])}".lower()
    problems = {
        "accounting": {
            "bookkeeping_automation": "Small business teams struggle to keep books current because categorization, reconciliation, and data entry are manual.",
            "invoice_reconciliation": "Teams struggle to match invoices, payments, and purchase orders without spending hours chasing mismatches.",
            "expense_tracking": "Small businesses struggle to categorize expenses accurately and keep spend visible across cards, receipts, and reimbursements.",
            "receipt_scanning": "Teams waste time typing receipt details manually instead of capturing them directly into accounting workflows.",
            "cash_flow_forecasting": "Founders and finance teams struggle to forecast cash flow because invoices, bills, and bank activity are fragmented.",
            "tax_compliance": "Small businesses struggle to keep tax, GST, and VAT obligations current across multiple jurisdictions and rules.",
            "payroll_automation": "Small businesses struggle to run payroll accurately because timesheets, exceptions, and approvals are scattered.",
            "financial_reporting": "Founders and accountants struggle to assemble accurate financial reports quickly at month end.",
            "accounts_payable": "Teams struggle to manage vendor bills, approvals, and payment timing without duplicate work or missed deadlines.",
            "accounts_receivable": "Teams struggle to track overdue invoices and collections before aging receivables become a cash flow problem.",
            "fraud_detection": "Finance teams struggle to detect accounting fraud or anomalous transactions before losses spread.",
        },
        "cybersecurity": {
            "threat_detection": "Security teams struggle to detect active threats quickly because alerts are noisy and signals are scattered across tools.",
            "incident_response": "Security teams waste time triaging alerts and coordinating response across disconnected consoles.",
            "compliance": "Security and compliance teams spend too long collecting evidence for audits, controls, and policy checks.",
            "cloud_security": "Cloud teams lack continuous visibility into risky configurations, exposed assets, and identity sprawl.",
            "identity_management": "Teams struggle to manage identity, access, and privilege drift across SaaS and cloud systems.",
            "vulnerability_management": "Teams cannot prioritize patching across a growing vulnerability backlog and exploit surface.",
            "security_training": "Organizations struggle to turn security training and labs into measurable behavior change.",
            "security_analytics": "Security leaders cannot connect logs, detections, and risk signals into one operational view.",
        },
        "fintech": {
            "fraud_detection": "Finance teams struggle to detect fraud and abuse quickly enough to reduce losses.",
            "payments_reconciliation": "Finance teams struggle to reconcile payments and settlements across fragmented systems.",
            "risk_management": "Finance teams struggle to monitor risk exposure before it affects decisions.",
            "banking_operations": "Finance teams struggle to keep banking operations, ledgers, and cash flow workflows accurate in real time.",
            "underwriting": "Fintech teams struggle to underwrite and approve customers quickly without weak signals.",
            "transaction_monitoring": "Fintech teams struggle to monitor transactions for suspicious activity at scale.",
            "compliance": "Fintech teams struggle to keep compliance evidence and KYC/AML workflows current.",
            "portfolio_analytics": "Fintech teams struggle to turn live finance signals into portfolio insights.",
        },
        "amazon": {
            "inventory_forecasting": "Amazon sellers frequently run out of stock because demand forecasting is inaccurate.",
            "review_analysis": "Amazon sellers struggle to turn review feedback into product and listing improvements.",
            "listing_optimization": "Amazon product listings fail to convert despite traffic because optimization is manual and inconsistent.",
            "competitor_pricing": "Amazon sellers struggle to monitor competitor pricing and protect margins in real time.",
            "fba_cost_monitoring": "Amazon sellers struggle to understand fulfillment and storage fees before they erode margins.",
            "keyword_discovery": "Amazon sellers struggle to discover profitable keywords that actually convert.",
            "advertising_optimization": "Amazon sellers waste ad spend because campaign optimization is too slow.",
            "demand_prediction": "Amazon sellers cannot predict demand changes early enough to plan inventory and promotions.",
        },
        "education": {
            "student_progress": "Students and educators struggle to track progress and intervene before learners fall behind.",
            "study_planning": "Students struggle to plan study sessions and maintain consistent focus across courses.",
            "teacher_workload": "Teachers spend too much time on repetitive planning, grading, and follow-up work.",
            "curriculum_planning": "Teams struggle to align curriculum plans with real student performance data.",
            "assessment_feedback": "Assessment feedback is slow and difficult to personalize at scale.",
            "course_recommendation": "Learners cannot easily find the right courses or learning path for their goals.",
            "exam_prep": "Students lack adaptive exam preparation tools that respond to their weak spots.",
            "learning_engagement": "Educators struggle to keep learners engaged and active between lessons.",
        },
        "productivity": {
            "focus_management": "Students lose focus because study sessions are interrupted and poorly structured.",
            "assignment_tracking": "Students miss deadlines because assignment planning is fragmented across tools.",
            "time_management": "Students struggle to allocate time across classes, homework, and exams.",
            "study_planning": "Students struggle to build consistent study habits and weekly plans.",
            "note_organization": "Students cannot turn scattered notes into a usable study system.",
            "habit_building": "Students struggle to maintain habits that support consistent learning progress.",
            "exam_prep": "Students need better preparation workflows to review material before exams.",
            "schedule_coordination": "Students struggle to coordinate calendars, deadlines, and study blocks in one place.",
        },
        "fitness": {
            "workout_tracking": "Fitness users struggle to track workouts consistently across sessions and devices.",
            "exercise_library": "Trainers and athletes struggle to organize exercise libraries and movement libraries clearly.",
            "routine_management": "Fitness users struggle to manage routines and adapt templates as goals change.",
            "data_sync": "Fitness teams struggle to sync workout data, imports, and app integrations reliably.",
            "progress_analytics": "Coaches struggle to turn workout output into understandable progress analytics.",
            "endurance_training": "Runners and endurance athletes struggle to adjust training plans from race and cardio signals.",
            "nutrition_planning": "Fitness users struggle to connect nutrition planning with training goals and recovery needs.",
            "coach_analytics": "Coaches and trainers struggle to analyze performance across members, programs, and sessions.",
            "member_engagement": "Gym operators struggle to keep members engaged and reduce churn with current tools.",
            "health_tracking": "Fitness users struggle to unify health and recovery tracking across devices and apps.",
            "wellness_habits": "Individuals struggle to build lasting wellness habits and stay consistent over time.",
            "training_progress": "Athletes and trainers struggle to measure training progress against goals.",
        },
    }
    if domain in problems and cluster_key in problems[domain]:
        return problems[domain][cluster_key]
    if "amazon" in text and ("inventory" in text or "fba" in text or "stock" in text):
        return "Amazon sellers struggle to forecast inventory demand, avoid stockouts, and keep listings profitable."
    if "cybersecurity" in text or "cyber security" in text or "security" in text:
        if "threat" in text or "alert" in text:
            return "Security teams struggle to detect threats early because alerts, logs, and intel are fragmented."
        if "incident" in text or "triage" in text:
            return "Security teams struggle to triage incidents fast enough to prevent business impact."
        if "cloud" in text or "identity" in text or "access" in text:
            return "Cloud and identity teams struggle to keep risky configurations and access drift under control."
        if "vulnerability" in text or "patch" in text:
            return "Security teams struggle to prioritize vulnerabilities before attackers exploit them."
        if "training" in text or "skills" in text or "labs" in text:
            return "Security teams struggle to convert training and labs into secure day-to-day behavior."
        return "Security teams struggle to connect live signals into a clear operational risk picture."
    if "fitness" in text or "workout" in text or "exercise" in text or "gym" in text or "wellness" in text or "nutrition" in text:
        if "nutrition" in text or "meal" in text or "diet" in text or "macro" in text or "calorie" in text:
            return "Fitness users struggle to connect nutrition planning with training goals and recovery needs."
        if "member" in text or "retention" in text or "churn" in text:
            return "Gym operators struggle to keep members engaged and reduce churn with current tools."
        if "coach" in text or "trainer" in text or "analytics" in text or "performance" in text:
            return "Coaches and trainers struggle to analyze performance across members, programs, and sessions."
        if "tracking" in text or "health" in text or "wearable" in text:
            return "Fitness users struggle to unify health and recovery tracking across devices and apps."
        return "Fitness users struggle to plan workouts, maintain consistency, and measure progress."
    if ("education" in text or "student" in text) and ("teacher" in text or "classroom" in text):
        return "Teachers struggle to personalize learning and track student progress across classes."
    if ("education" in text or "student" in text) and ("course" in text or "learning" in text or "exam" in text):
        return "Students struggle to find personalized study guidance and keep pace with coursework."
    if "productivity" in text or "focus" in text or "study" in text:
        return "Students struggle to plan study sessions, manage assignments, and maintain consistent focus."
    fallback_topic = " ".join(_topic_words(topic)[:3]) or "this workflow"
    return f"Teams struggle to solve {fallback_topic} because current tools are fragmented, manual, and hard to evidence."


def _pitch_for(topic: str, query: str | None = None, *, domain: str = "general", cluster_key: str = "") -> str:
    pitches = {
        "accounting": {
            "bookkeeping_automation": "AI bookkeeping that keeps books current, auto-categorizes expenses, and reduces manual entry.",
            "invoice_reconciliation": "AI invoice reconciliation that matches invoices, payments, and purchase orders automatically.",
            "expense_tracking": "AI expense tracking that categorizes spend from cards, receipts, and reimbursements.",
            "receipt_scanning": "AI receipt capture that turns receipts into accounting-ready records.",
            "cash_flow_forecasting": "AI cash flow forecasting that predicts runway, gaps, and short-term financing needs.",
            "tax_compliance": "AI tax compliance that keeps tax, GST, and VAT workflows current.",
            "payroll_automation": "AI payroll automation that reduces prep work and flags exceptions before payroll runs.",
            "financial_reporting": "AI financial reporting that assembles month-end statements and flags mismatches.",
            "accounts_payable": "AI accounts payable automation that tracks bills, approvals, and payment timing.",
            "accounts_receivable": "AI accounts receivable automation that tracks invoices, reminders, and collections.",
            "fraud_detection": "AI accounting fraud detection that spots anomalies and suspicious transaction patterns early.",
        },
        "cybersecurity": {
            "threat_detection": "AI threat detection that correlates noisy security signals and surfaces likely attacks early.",
            "incident_response": "AI incident triage that ranks alerts, suggests next steps, and speeds containment workflows.",
            "compliance": "AI compliance evidence automation that maps controls, collects proof, and reduces audit prep time.",
            "cloud_security": "AI cloud security monitoring that flags risky configs, exposed assets, and identity sprawl.",
            "identity_management": "AI identity intelligence that spots privilege drift and access risks across SaaS and cloud.",
            "vulnerability_management": "AI vulnerability prioritization that ranks patch work by exploitability and business impact.",
            "security_training": "AI security training analytics that turns labs, simulations, and completion data into risk reduction.",
            "security_analytics": "AI security analytics that unifies logs, detections, and threat context into one operating view.",
        },
        "amazon": {
            "inventory_forecasting": "AI demand forecasting for Amazon sellers using live marketplace signals and sales trends.",
            "review_analysis": "AI review intelligence that turns customer complaints and feature requests into product actions.",
            "listing_optimization": "AI listing optimization that improves titles, bullets, and conversions from search traffic.",
            "competitor_pricing": "AI pricing intelligence that tracks competitors and recommends margin-safe price moves.",
            "fba_cost_monitoring": "AI fulfillment cost monitoring that flags storage, fee, and margin leaks early.",
            "keyword_discovery": "AI keyword discovery that uncovers high-intent search terms for Amazon listings and ads.",
            "advertising_optimization": "AI ad optimization that reallocates Amazon spend toward the best-performing campaigns.",
            "demand_prediction": "AI market demand prediction that helps sellers plan launches, replenishment, and promotions.",
        },
        "education": {
            "student_progress": "An AI progress tracker that helps students and educators spot learning gaps early.",
            "study_planning": "An AI study coach that helps students plan sessions, prioritize work, and stay on track.",
            "teacher_workload": "An AI assistant that automates repetitive teacher planning, grading, and follow-up work.",
            "curriculum_planning": "An AI planning tool that aligns curriculum with outcomes and student performance.",
            "assessment_feedback": "An AI feedback assistant that personalizes assessments at scale.",
            "course_recommendation": "An AI course recommender that guides learners to the right next step.",
            "exam_prep": "An AI exam prep copilot that adapts to weak areas and learning pace.",
            "learning_engagement": "An AI engagement tracker that helps educators keep learners active between lessons.",
        },
        "productivity": {
            "focus_management": "An AI focus planner that helps students protect deep work and avoid distraction.",
            "assignment_tracking": "An AI assignment tracker that keeps deadlines, priorities, and tasks visible.",
            "time_management": "An AI time manager that balances classes, homework, and exam preparation.",
            "study_planning": "An AI study habit coach that builds consistent weekly study routines.",
            "note_organization": "An AI notes workflow that turns scattered notes into usable study material.",
            "habit_building": "An AI habit coach that helps students build repeatable learning routines.",
            "exam_prep": "An AI exam tracker that organizes revision and review cycles.",
            "schedule_coordination": "An AI scheduling assistant that aligns calendars, deadlines, and study blocks.",
        },
        "fitness": {
            "workout_tracking": "An AI workout tracker that logs sessions and surfaces training patterns.",
            "exercise_library": "An AI exercise library assistant that organizes movements and progression paths.",
            "routine_management": "An AI routine manager that keeps workout templates aligned to changing goals.",
            "data_sync": "An AI fitness sync assistant that moves data across apps, wearables, and training logs.",
            "progress_analytics": "An AI progress analytics copilot that explains training output and momentum.",
            "endurance_training": "An AI endurance training copilot that adapts race and cardio plans from live signals.",
            "nutrition_planning": "An AI nutrition planner that ties meals, recovery, and training goals together.",
            "coach_analytics": "An AI coaching analytics copilot that tracks performance across members and programs.",
            "member_engagement": "An AI gym engagement copilot that improves retention and loyalty.",
            "health_tracking": "An AI health tracking copilot that unifies recovery, wearable, and performance signals.",
            "wellness_habits": "An AI wellness habit coach that keeps users consistent with healthy routines.",
            "training_progress": "An AI training progress tracker that monitors progress against goals.",
        },
    }
    if domain in pitches and cluster_key in pitches[domain]:
        return pitches[domain][cluster_key]
    if domain == "fintech":
        pitches = {
            "fraud_detection": "AI fraud detection that identifies abuse patterns and reduces loss faster.",
            "payments_reconciliation": "AI reconciliation that matches payments, settlements, and payouts across systems.",
            "risk_management": "AI risk monitoring that surfaces exposure and changes before they create losses.",
            "banking_operations": "AI banking operations that keeps ledgers, cash flow, and reporting in sync.",
            "underwriting": "AI underwriting that helps fintech teams make faster, better lending decisions.",
            "transaction_monitoring": "AI transaction monitoring that ranks anomalies and suspicious activity for review.",
            "compliance": "AI compliance automation that keeps KYC, AML, and audit evidence current.",
            "portfolio_analytics": "AI portfolio analytics that turns live signals into better finance decisions.",
        }
        if cluster_key in pitches:
            return pitches[cluster_key]
    text = f"{topic} {query or ''}".lower()
    if "amazon" in text:
        return "An AI copilot for Amazon sellers that forecasts inventory, pricing, and listing performance from live market signals."
    if "cybersecurity" in text or "security" in text or "cyber security" in text:
        if "incident" in text or "triage" in text:
            return "An AI incident response copilot that helps security teams prioritize alerts and contain threats faster."
        if "cloud" in text or "identity" in text or "access" in text:
            return "An AI cloud and identity copilot that flags risky access paths and misconfigurations continuously."
        if "vulnerability" in text or "patch" in text:
            return "An AI vulnerability copilot that prioritizes patch work by exploitability and business impact."
        if "training" in text or "skills" in text or "labs" in text:
            return "An AI security training copilot that turns hands-on labs and awareness work into measurable risk reduction."
        return "An AI security copilot that connects live signals, logs, and detections into one operational view."
    if "fitness" in text or "workout" in text or "exercise" in text or "gym" in text or "wellness" in text or "nutrition" in text:
        if "nutrition" in text or "meal" in text or "diet" in text or "macro" in text or "calorie" in text:
            return "An AI nutrition copilot that connects meal planning, recovery, and training goals."
        if "member" in text or "retention" in text or "churn" in text:
            return "An AI gym engagement copilot that improves member retention and loyalty."
        if "coach" in text or "trainer" in text or "analytics" in text or "performance" in text:
            return "An AI coaching analytics copilot that tracks performance across members and programs."
        if "tracking" in text or "health" in text or "wearable" in text:
            return "An AI health tracking copilot that unifies recovery, wearable, and performance signals."
        return "An AI fitness copilot that helps users plan workouts, build consistency, and measure progress."
    if "education" in text or "student" in text:
        return "An AI product that helps students and educators personalize learning, track progress, and automate routine planning."
    if "productivity" in text or "focus" in text:
        return "An AI assistant that helps students plan study sessions, manage tasks, and stay focused on high-priority work."
    if "fitness" in text or "workout" in text or "exercise" in text or "gym" in text or "wellness" in text or "nutrition" in text:
        return "An AI copilot for fitness teams and consumers that tracks training progress, nutrition, and habit consistency from live evidence."
    fallback_topic = " ".join(_topic_words(topic)[:3]) or "workflow"
    return f"An AI copilot for {fallback_topic} that turns live evidence into actions and automates repetitive work."


def _customer_for(topic: str, query: str | None = None, *, domain: str = "general", cluster_key: str = "") -> str:
    customers = {
        "accounting": {
            "bookkeeping_automation": "Bookkeepers, small business owners, and finance ops teams.",
            "invoice_reconciliation": "Small business owners and accounts receivable teams.",
            "expense_tracking": "Bookkeepers, operators, and finance teams managing expenses.",
            "receipt_scanning": "Small business owners and bookkeepers capturing receipts.",
            "cash_flow_forecasting": "Founders, bookkeepers, and finance operators.",
            "tax_compliance": "Small business owners, accountants, and tax teams.",
            "payroll_automation": "Small business owners and payroll admins.",
            "financial_reporting": "Founders, accountants, and finance operators.",
            "accounts_payable": "Finance teams managing vendor payments.",
            "accounts_receivable": "Finance teams and billing operators.",
            "fraud_detection": "Finance and accounting teams monitoring suspicious activity.",
        },
        "cybersecurity": {
            "threat_detection": "Security operations teams and threat hunters.",
            "incident_response": "SOC analysts, incident responders, and security managers.",
            "compliance": "Security, risk, and compliance teams.",
            "cloud_security": "Cloud security teams and platform engineers.",
            "identity_management": "IAM teams, IT admins, and security engineers.",
            "vulnerability_management": "Vulnerability management teams and security ops.",
            "security_training": "Security awareness, training, and enablement teams.",
            "security_analytics": "Security leaders and analytics-minded SOC teams.",
        },
        "amazon": {
            "inventory_forecasting": "Amazon marketplace sellers and ops teams.",
            "review_analysis": "Amazon brands, product managers, and customer experience teams.",
            "listing_optimization": "Amazon sellers, ecommerce managers, and listing specialists.",
            "competitor_pricing": "Amazon sellers and pricing analysts.",
            "fba_cost_monitoring": "Amazon FBA sellers and finance operators.",
            "keyword_discovery": "Amazon sellers and growth marketers.",
            "advertising_optimization": "Amazon sellers and paid media teams.",
            "demand_prediction": "Amazon sellers and launch teams.",
        },
        "education": {
            "student_progress": "Students, teachers, and academic support teams.",
            "study_planning": "Students, learners, and academic advisors.",
            "teacher_workload": "Teachers, school administrators, and curriculum teams.",
            "curriculum_planning": "Curriculum designers and education leaders.",
            "assessment_feedback": "Teachers, graders, and learning teams.",
            "course_recommendation": "Students and learners choosing next courses.",
            "exam_prep": "Students and exam preparation teams.",
            "learning_engagement": "Teachers and student success teams.",
        },
        "productivity": {
            "focus_management": "Students and knowledge workers.",
            "assignment_tracking": "Students and academic planners.",
            "time_management": "Students, learners, and busy professionals.",
            "study_planning": "Students and learners.",
            "note_organization": "Students and knowledge workers managing research.",
            "habit_building": "Students building consistent routines.",
            "exam_prep": "Students preparing for tests and certifications.",
            "schedule_coordination": "Students juggling calendars and deadlines.",
        },
        "fitness": {
            "workout_tracking": "Fitness enthusiasts, coaches, and trainers.",
            "exercise_library": "Athletes, trainers, and fitness coaches.",
            "routine_management": "Fitness users managing repeatable routines and templates.",
            "data_sync": "Fitness teams syncing wearables, apps, and training logs.",
            "progress_analytics": "Coaches and analysts reviewing training output and momentum.",
            "endurance_training": "Runners and endurance athletes.",
            "nutrition_planning": "Health-conscious consumers and nutrition coaches.",
            "coach_analytics": "Fitness coaches, gym managers, and analysts.",
            "member_engagement": "Gym operators and retention teams.",
            "health_tracking": "Consumers tracking health and recovery.",
            "wellness_habits": "Individuals building better wellness routines.",
            "training_progress": "Athletes, trainers, and program coordinators.",
        },
    }
    if domain in customers and cluster_key in customers[domain]:
        return customers[domain][cluster_key]
    if domain == "fintech":
        customers = {
            "fraud_detection": "Fraud, risk, and payments teams.",
            "payments_reconciliation": "Payments operations and finance teams.",
            "risk_management": "Risk, treasury, and finance leaders.",
            "banking_operations": "Banking operations and finance ops teams.",
            "underwriting": "Underwriting and lending teams.",
            "transaction_monitoring": "AML, operations, and compliance teams.",
            "compliance": "Compliance, KYC, and audit teams.",
            "portfolio_analytics": "Portfolio and finance analytics teams.",
        }
        if cluster_key in customers:
            return customers[cluster_key]
    text = f"{topic} {query or ''}".lower()
    if "amazon" in text:
        return "Amazon marketplace sellers, ecommerce operators, and FBA teams."
    if "cybersecurity" in text or "security" in text or "cyber security" in text:
        return "Security operations teams, SOC analysts, and security leaders."
    if "fitness" in text or "workout" in text or "exercise" in text or "gym" in text or "wellness" in text or "nutrition" in text:
        return "Fitness enthusiasts, athletes, coaches, and gym operators."
    if "education" in text:
        return "Students, teachers, and education teams."
    if "student" in text:
        return "Students, learners, and academic support teams."
    if "productivity" in text:
        return "Students, knowledge workers, and teams managing heavy task loads."
    fallback_topic = " ".join(_topic_words(topic)[:3]) or "the workflow"
    return f"Teams and operators dealing with {fallback_topic}."


def _revenue_model(topic: str, query: str | None = None, *, domain: str = "general", cluster_key: str = "") -> str:
    if domain == "amazon":
        return "Subscription SaaS with seller-tier pricing and usage-based workflow credits."
    if domain == "education":
        return "Subscription SaaS with school, district, teacher, and student plans."
    if domain == "productivity":
        return "Subscription SaaS with individual and team productivity tiers."
    if domain == "fitness":
        return "Subscription SaaS with individual, coach, and gym tiers plus premium analytics credits."
    text = f"{topic} {query or ''}".lower()
    if "amazon" in text:
        return "Subscription SaaS with seller-tier pricing and usage-based forecasting credits."
    if "education" in text or "student" in text:
        return "Subscription SaaS with school, teacher, and student plans."
    if "fitness" in text or "workout" in text or "exercise" in text or "gym" in text or "wellness" in text or "nutrition" in text:
        return "Subscription SaaS with individual, coach, and gym tiers plus premium analytics credits."
    return "Subscription SaaS with usage-based tiers and premium workflow automations."


def _mvp_features(topic: str, query: str | None = None, *, domain: str = "general", cluster_key: str = "") -> list[str]:
    feature_sets = {
        "cybersecurity": {
            "threat_detection": [
                "Correlate alerts, logs, and external threat intel",
                "Surface likely attacks and suspicious patterns",
                "Recommend triage actions and escalation paths",
                "Generate evidence-backed opportunity briefs",
            ],
            "incident_response": [
                "Rank incidents by impact and urgency",
                "Summarize alerts into response-ready briefs",
                "Recommend containment and escalation steps",
                "Generate evidence-backed opportunity briefs",
            ],
            "compliance": [
                "Collect control evidence from live systems",
                "Map signals to audit and compliance requirements",
                "Flag missing proof and policy drift",
                "Generate evidence-backed opportunity briefs",
            ],
            "cloud_security": [
                "Monitor cloud config and identity risk",
                "Flag exposed assets and misconfigurations",
                "Recommend remediation steps",
                "Generate evidence-backed opportunity briefs",
            ],
            "identity_management": [
                "Track privilege and access drift",
                "Detect risky identity changes",
                "Recommend IAM remediation actions",
                "Generate evidence-backed opportunity briefs",
            ],
            "vulnerability_management": [
                "Prioritize vulnerabilities by exploitability",
                "Track patch backlog and exposure windows",
                "Recommend remediation sequencing",
                "Generate evidence-backed opportunity briefs",
            ],
            "security_training": [
                "Measure training and simulation outcomes",
                "Cluster behavior change signals",
                "Recommend targeted awareness programs",
                "Generate evidence-backed opportunity briefs",
            ],
            "security_analytics": [
                "Unify live security signals into one view",
                "Track detection quality and coverage gaps",
                "Recommend analytics and workflow improvements",
                "Generate evidence-backed opportunity briefs",
            ],
        },
        "amazon": {
            "inventory_forecasting": [
                "Import live seller signals and inventory alerts",
                "Forecast stockout and replenishment risk",
                "Recommend purchase and reorder actions",
                "Generate evidence-backed opportunity briefs",
            ],
            "review_analysis": [
                "Ingest review feedback and complaint themes",
                "Detect product defects and feature requests",
                "Recommend product and listing fixes",
                "Generate evidence-backed opportunity briefs",
            ],
            "listing_optimization": [
                "Audit titles, bullets, and descriptions",
                "Recommend keyword and image improvements",
                "Track conversion changes after edits",
                "Generate evidence-backed opportunity briefs",
            ],
            "competitor_pricing": [
                "Monitor competitor price movement",
                "Flag margin risk and buy-box changes",
                "Recommend price adjustments",
                "Generate evidence-backed opportunity briefs",
            ],
            "fba_cost_monitoring": [
                "Track storage and fulfillment fee changes",
                "Surface margin erosion early",
                "Recommend fee-saving actions",
                "Generate evidence-backed opportunity briefs",
            ],
            "keyword_discovery": [
                "Discover high-intent search terms",
                "Map keyword gaps against competitors",
                "Recommend SEO and content updates",
                "Generate evidence-backed opportunity briefs",
            ],
            "advertising_optimization": [
                "Monitor campaign performance",
                "Flag wasted spend and underperforming ads",
                "Recommend budget reallocations",
                "Generate evidence-backed opportunity briefs",
            ],
            "demand_prediction": [
                "Predict demand shifts from live signals",
                "Compare trend movement across sources",
                "Recommend launch and replenishment timing",
                "Generate evidence-backed opportunity briefs",
            ],
        },
        "education": {
            "student_progress": [
                "Track progress across courses and assessments",
                "Surface learners falling behind",
                "Recommend timely interventions",
                "Generate evidence-backed opportunity briefs",
            ],
            "study_planning": [
                "Plan weekly study sessions",
                "Balance assignments and revision",
                "Recommend focus blocks and priorities",
                "Generate evidence-backed opportunity briefs",
            ],
            "teacher_workload": [
                "Automate repetitive lesson and grading tasks",
                "Summarize student progress quickly",
                "Recommend teacher workflow automation",
                "Generate evidence-backed opportunity briefs",
            ],
            "curriculum_planning": [
                "Map curriculum to outcomes",
                "Highlight gaps against learner performance",
                "Recommend curriculum adjustments",
                "Generate evidence-backed opportunity briefs",
            ],
            "assessment_feedback": [
                "Cluster assessment feedback themes",
                "Draft personalized feedback suggestions",
                "Recommend grading workflow improvements",
                "Generate evidence-backed opportunity briefs",
            ],
            "course_recommendation": [
                "Recommend next-best courses and learning paths",
                "Match learners to goals and prerequisites",
                "Track recommendation outcomes",
                "Generate evidence-backed opportunity briefs",
            ],
            "exam_prep": [
                "Identify weak areas from live evidence",
                "Recommend exam prep drills and review blocks",
                "Track readiness over time",
                "Generate evidence-backed opportunity briefs",
            ],
            "learning_engagement": [
                "Measure learner engagement signals",
                "Flag participation drops early",
                "Recommend retention interventions",
                "Generate evidence-backed opportunity briefs",
            ],
        },
        "productivity": {
            "focus_management": [
                "Plan distraction-free study sessions",
                "Recommend deep-work and focus blocks",
                "Track attention and focus patterns",
                "Generate evidence-backed opportunity briefs",
            ],
            "assignment_tracking": [
                "Track assignments and deadlines",
                "Prioritize work across courses and projects",
                "Surface at-risk deadlines early",
                "Generate evidence-backed opportunity briefs",
            ],
            "time_management": [
                "Balance classes, homework, and exams",
                "Recommend daily time blocks",
                "Track schedule drift and overload",
                "Generate evidence-backed opportunity briefs",
            ],
            "study_planning": [
                "Build consistent weekly study routines",
                "Recommend focus and revision blocks",
                "Track progress against goals",
                "Generate evidence-backed opportunity briefs",
            ],
            "note_organization": [
                "Turn scattered notes into study material",
                "Tag and organize learning materials",
                "Recommend review queues and summaries",
                "Generate evidence-backed opportunity briefs",
            ],
            "habit_building": [
                "Track habit streaks and consistency",
                "Recommend behavior nudges",
                "Surface habit breakpoints early",
                "Generate evidence-backed opportunity briefs",
            ],
            "exam_prep": [
                "Plan exam revision and practice",
                "Track weak topics over time",
                "Recommend adaptive prep actions",
                "Generate evidence-backed opportunity briefs",
            ],
            "schedule_coordination": [
                "Coordinate calendars and deadlines",
                "Reduce schedule conflicts",
                "Recommend smart rescheduling options",
                "Generate evidence-backed opportunity briefs",
            ],
        },
        "fitness": {
            "workout_tracking": [
                "Import workout logs and training signals",
                "Recommend next-session adjustments and progressions",
                "Track consistency and adherence over time",
                "Generate evidence-backed opportunity briefs",
            ],
            "exercise_library": [
                "Organize movement libraries and exercise variants",
                "Flag missing exercises and weak movement patterns",
                "Recommend form and progression improvements",
                "Generate evidence-backed opportunity briefs",
            ],
            "routine_management": [
                "Keep workout routines and templates in sync",
                "Surface stale routines and update opportunities",
                "Recommend routine restructuring actions",
                "Generate evidence-backed opportunity briefs",
            ],
            "data_sync": [
                "Sync fitness data across apps and wearables",
                "Flag broken imports and integration failures",
                "Recommend integration and retry actions",
                "Generate evidence-backed opportunity briefs",
            ],
            "progress_analytics": [
                "Turn workout output into progress analytics",
                "Explain momentum and plateaus clearly",
                "Recommend analytics-driven improvements",
                "Generate evidence-backed opportunity briefs",
            ],
            "endurance_training": [
                "Adapt race and cardio plans from live signals",
                "Compare endurance trends over time",
                "Recommend pacing and volume adjustments",
                "Generate evidence-backed opportunity briefs",
            ],
            "nutrition_planning": [
                "Connect nutrition goals to training plans",
                "Track meal and recovery signals",
                "Recommend nutrition adjustments for performance",
                "Generate evidence-backed opportunity briefs",
            ],
            "coach_analytics": [
                "Analyze coach and program performance across members",
                "Cluster training outcomes into insights",
                "Recommend program improvements",
                "Generate evidence-backed opportunity briefs",
            ],
            "member_engagement": [
                "Track member engagement and churn risk",
                "Flag low engagement and drop-off patterns",
                "Recommend retention workflows",
                "Generate evidence-backed opportunity briefs",
            ],
            "health_tracking": [
                "Unify health, wearable, and recovery signals",
                "Compare trends across devices and apps",
                "Recommend health tracking actions",
                "Generate evidence-backed opportunity briefs",
            ],
            "wellness_habits": [
                "Track wellness habits and streaks",
                "Surface consistency breaks early",
                "Recommend habit nudges and recovery actions",
                "Generate evidence-backed opportunity briefs",
            ],
            "training_progress": [
                "Measure training progress against goals",
                "Track load, adherence, and consistency",
                "Recommend adaptive training updates",
                "Generate evidence-backed opportunity briefs",
            ],
        },
        "accounting": {
            "bookkeeping_automation": [
                "Sync receipts, invoices, and bank transactions",
                "Auto-categorize expenses and book transactions",
                "Flag uncoded items and reconciliation gaps",
                "Generate evidence-backed opportunity briefs",
            ],
            "invoice_reconciliation": [
                "Match invoices to payments and purchase orders",
                "Flag exceptions and missing approvals",
                "Recommend follow-up actions",
                "Generate evidence-backed opportunity briefs",
            ],
            "expense_tracking": [
                "Capture expenses from cards, receipts, and reimbursements",
                "Auto-categorize spend across vendors",
                "Surface policy or budget exceptions",
                "Generate evidence-backed opportunity briefs",
            ],
            "receipt_scanning": [
                "Extract line items from receipts",
                "Match receipts to transactions and bills",
                "Reduce manual data entry for bookkeeping",
                "Generate evidence-backed opportunity briefs",
            ],
            "cash_flow_forecasting": [
                "Forecast cash flow from invoices, bills, and bank activity",
                "Highlight upcoming cash gaps and surpluses",
                "Recommend short-term actions",
                "Generate evidence-backed opportunity briefs",
            ],
            "tax_compliance": [
                "Track tax obligations across sales and jurisdictions",
                "Flag missing documents and filing risks",
                "Recommend compliance workflows",
                "Generate evidence-backed opportunity briefs",
            ],
            "payroll_automation": [
                "Automate payroll prep and exception handling",
                "Flag timecard or compensation issues",
                "Recommend payroll review actions",
                "Generate evidence-backed opportunity briefs",
            ],
            "financial_reporting": [
                "Assemble financial reports from live books and bank data",
                "Flag reporting mismatches early",
                "Recommend month-end close actions",
                "Generate evidence-backed opportunity briefs",
            ],
            "accounts_payable": [
                "Track bills, approvals, and vendor payments",
                "Flag overdue or duplicate payables",
                "Recommend payment workflows",
                "Generate evidence-backed opportunity briefs",
            ],
            "accounts_receivable": [
                "Track invoices, collections, and payment follow-up",
                "Flag overdue receivables and aging risk",
                "Recommend collection workflows",
                "Generate evidence-backed opportunity briefs",
            ],
            "fraud_detection": [
                "Flag suspicious transactions and accounting anomalies",
                "Prioritize investigation workflows",
                "Recommend evidence collection steps",
                "Generate evidence-backed opportunity briefs",
            ],
        },
    }
    if domain in feature_sets and cluster_key in feature_sets[domain]:
        return feature_sets[domain][cluster_key]
    if domain == "accounting":
        return [
            "Ingest accounting, invoice, and bank workflow signals",
            "Cluster bookkeeping, expenses, tax, and payroll pain points",
            "Recommend finance automation actions",
            "Generate evidence-backed opportunity briefs",
        ]
    if domain == "fintech":
        feature_sets = {
            "fraud_detection": [
                "Flag fraudulent patterns across live transactions",
                "Rank suspicious activity by risk and confidence",
                "Recommend review and escalation actions",
                "Generate evidence-backed opportunity briefs",
            ],
            "payments_reconciliation": [
                "Match payments, settlements, and payouts across systems",
                "Flag reconciliation breaks and missing records",
                "Recommend corrective workflows",
                "Generate evidence-backed opportunity briefs",
            ],
            "risk_management": [
                "Monitor exposure and risk drift from live signals",
                "Surface early warning indicators",
                "Recommend mitigation steps",
                "Generate evidence-backed opportunity briefs",
            ],
            "banking_operations": [
                "Track ledger and cash flow workflows in real time",
                "Flag reporting breaks and data mismatches",
                "Recommend finance ops automation steps",
                "Generate evidence-backed opportunity briefs",
            ],
            "underwriting": [
                "Surface underwriting signals and decision inputs",
                "Rank applicants or deals by confidence",
                "Recommend faster approval workflows",
                "Generate evidence-backed opportunity briefs",
            ],
            "transaction_monitoring": [
                "Monitor anomalous transactions across sources",
                "Rank suspicious activity for review",
                "Recommend compliance workflow actions",
                "Generate evidence-backed opportunity briefs",
            ],
            "compliance": [
                "Collect KYC, AML, and audit evidence from live systems",
                "Map signals to compliance requirements",
                "Flag missing proof and policy drift",
                "Generate evidence-backed opportunity briefs",
            ],
            "portfolio_analytics": [
                "Turn live finance signals into portfolio insights",
                "Highlight concentration and performance shifts",
                "Recommend decision actions",
                "Generate evidence-backed opportunity briefs",
            ],
        }
        if cluster_key in feature_sets:
            return feature_sets[cluster_key]
    text = f"{topic} {query or ''}".lower()
    if "amazon" in text:
        return [
            "Import live seller signals and inventory alerts",
            "Surface pricing and review anomalies",
            "Recommend listing and replenishment actions",
            "Generate evidence-backed opportunity briefs",
        ]
    if "cybersecurity" in text or "security" in text or "cyber security" in text:
        return [
            "Ingest live security signals from code, news, and discussions",
            "Cluster threats, compliance gaps, and identity risks",
            "Recommend response and hardening actions",
            "Generate evidence-backed opportunity briefs",
        ]
    if "education" in text or "student" in text:
        return [
            "Track progress and pain points across courses",
            "Recommend study and assignment workflows",
            "Cluster learner complaints into themes",
            "Generate evidence-backed opportunity briefs",
        ]
    return [
        f"Capture and cluster {topic} signals",
        "Prioritize the highest-intent pain points",
        "Track competitor and trend movement",
        "Generate evidence-backed opportunity briefs",
    ]


def _gtm(topic: str, query: str | None = None, *, domain: str = "general", cluster_key: str = "") -> str:
    if domain == "amazon":
        gtm = {
            "inventory_forecasting": "Launch through Amazon seller communities, FBA operators, and inventory-focused content.",
            "review_analysis": "Launch through seller forums, review management communities, and listing optimization creators.",
            "listing_optimization": "Launch with Amazon SEO content, seller communities, and conversion-focused tutorials.",
            "competitor_pricing": "Launch through repricing communities, ecommerce newsletters, and seller operator groups.",
            "fba_cost_monitoring": "Launch through FBA communities and seller finance content.",
            "keyword_discovery": "Launch through Amazon SEO communities and product research creators.",
            "advertising_optimization": "Launch through Amazon PPC communities and ecommerce ad experts.",
            "demand_prediction": "Launch through launch-focused Amazon seller groups and ecommerce founders.",
        }
        if cluster_key in gtm:
            return gtm[cluster_key]
    if domain == "cybersecurity":
        gtm = {
            "threat_detection": "Launch through security practitioner communities, threat intel newsletters, and detection engineering content.",
            "incident_response": "Launch through SOC communities, incident response creators, and security ops teams.",
            "compliance": "Launch through security compliance leaders, audit communities, and governance content.",
            "cloud_security": "Launch through cloud security communities, platform engineering teams, and DevSecOps creators.",
            "identity_management": "Launch through IAM communities, IT admin groups, and access management leaders.",
            "vulnerability_management": "Launch through vulnerability management communities and security engineering content.",
            "security_training": "Launch through security awareness communities, training teams, and security education content.",
            "security_analytics": "Launch through SOC analytics communities, security leadership, and detection engineering content.",
        }
        if cluster_key in gtm:
            return gtm[cluster_key]
    if domain == "fintech":
        gtm = {
            "fraud_detection": "Launch through fraud, risk, and payments communities, plus finance newsletters and operator content.",
            "payments_reconciliation": "Launch through payments teams, fintech operations communities, and finance automation content.",
            "risk_management": "Launch through risk management communities, fintech operators, and finance analytics creators.",
            "banking_operations": "Launch through banking operations teams, ledger automation communities, and finance ops content.",
            "underwriting": "Launch through lending teams, credit decisioning communities, and underwriting operator content.",
            "transaction_monitoring": "Launch through transaction monitoring teams, AML communities, and finance ops channels.",
            "compliance": "Launch through compliance leaders, KYC/AML communities, and fintech audit content.",
            "portfolio_analytics": "Launch through portfolio and finance analytics communities and operator content.",
        }
        if cluster_key in gtm:
            return gtm[cluster_key]
    if domain == "accounting":
        gtm = {
            "bookkeeping_automation": "Launch through bookkeeping communities, small business finance creators, and accounting automation content.",
            "invoice_reconciliation": "Launch through AP/AR teams, accounting communities, and invoice workflow content.",
            "expense_tracking": "Launch through expense management creators, bookkeepers, and small business finance channels.",
            "receipt_scanning": "Launch through bookkeeping creators, accounting automation communities, and receipt capture workflows.",
            "cash_flow_forecasting": "Launch through founders, finance operators, and small business cash-flow content.",
            "tax_compliance": "Launch through tax professionals, accounting communities, and compliance content.",
            "payroll_automation": "Launch through payroll admins, small business finance creators, and HR/payroll communities.",
            "financial_reporting": "Launch through accountants, CFO communities, and month-end close content.",
            "accounts_payable": "Launch through accounts payable teams, vendor management communities, and finance ops content.",
            "accounts_receivable": "Launch through accounts receivable teams, billing communities, and collections workflows.",
            "fraud_detection": "Launch through finance controls, accounting audit communities, and transaction anomaly content.",
        }
        if cluster_key in gtm:
            return gtm[cluster_key]
    if domain == "education":
        gtm = {
            "student_progress": "Launch through educator communities, student success teams, and analytics-focused schools.",
            "study_planning": "Launch through student forums, study productivity creators, and campus communities.",
            "teacher_workload": "Launch through teacher communities, school admin networks, and education newsletters.",
            "curriculum_planning": "Launch through curriculum leaders, edtech operators, and school systems.",
            "assessment_feedback": "Launch through assessment, grading, and teacher workflow communities.",
            "course_recommendation": "Launch through learning communities, course marketplaces, and student guides.",
            "exam_prep": "Launch through exam prep communities and student productivity creators.",
            "learning_engagement": "Launch through educator and learner engagement communities.",
        }
        if cluster_key in gtm:
            return gtm[cluster_key]
    if domain == "productivity":
        gtm = {
            "focus_management": "Launch through student productivity communities and study creators.",
            "assignment_tracking": "Launch through academic productivity groups and campus channels.",
            "time_management": "Launch through time-management creators and student forums.",
            "study_planning": "Launch through student productivity communities and study coaches.",
            "note_organization": "Launch through note-taking and study workflow communities.",
            "habit_building": "Launch through habit-forming communities and student success channels.",
            "exam_prep": "Launch through exam prep creators and academic communities.",
            "schedule_coordination": "Launch through calendar and student planning communities.",
        }
        if cluster_key in gtm:
            return gtm[cluster_key]
    if domain == "fitness":
        gtm = {
            "workout_tracking": "Launch through fitness creator communities, training coaches, and workout content channels.",
            "exercise_library": "Launch through athlete communities, trainer networks, and exercise science content.",
            "routine_management": "Launch through habit and routine communities, fitness creators, and coach groups.",
            "data_sync": "Launch through fitness integration communities and wearable data creators.",
            "progress_analytics": "Launch through analytics-minded fitness communities and performance content.",
            "endurance_training": "Launch through runner communities, endurance coaches, and cardio creators.",
            "nutrition_planning": "Launch through nutrition creators, wellness communities, and fitness coaching channels.",
            "coach_analytics": "Launch through coach communities, gym operator groups, and performance analytics content.",
            "member_engagement": "Launch through gym operator communities and retention-focused fitness creators.",
            "health_tracking": "Launch through wearable, recovery, and health-tracking communities.",
            "wellness_habits": "Launch through wellness communities, habit creators, and health-focused newsletters.",
            "training_progress": "Launch through athlete communities and training program creators.",
        }
        if cluster_key in gtm:
            return gtm[cluster_key]
    text = f"{topic} {query or ''}".lower()
    if "amazon" in text:
        return "Launch through Amazon seller communities, ecommerce creators, and targeted content around listing optimization."
    if "education" in text or "student" in text:
        return "Launch through educator communities, student forums, and content around learning outcomes."
    fallback_topic = " ".join(_topic_words(topic)[:3]) or "the workflow"
    return f"Launch through communities and content where people discuss {fallback_topic} problems and automation."


class OpportunityIntelligenceService:
    def __init__(self) -> None:
        self.sources = sorted(OPPORTUNITY_SOURCES)
        self._last_debug: dict[str, object] = {}

    @property
    def last_debug(self) -> dict[str, object]:
        return self._last_debug

    def _term_tokens(self, terms: list[str]) -> list[str]:
        tokens: list[str] = []
        for term in terms:
            tokens.extend(_tokenize(str(term)))
        deduped: list[str] = []
        seen: set[str] = set()
        for token in tokens:
            if token in seen:
                continue
            seen.add(token)
            deduped.append(token)
        return deduped

    def _normalized_evidence_ids(self, signals: list[MarketSignal]) -> list[str]:
        ids: list[str] = []
        for signal in signals:
            key = str(signal.id or signal.url or signal.source_id or "")
            if key and key not in ids:
                ids.append(key)
        return ids

    def _opportunity_similarity(self, left: dict, right: dict) -> float:
        left_text = " ".join(
            [
                str(left.get("problem", "")),
                str(left.get("market_gap", "")),
                str(left.get("solution", "")),
            ]
        ).lower()
        right_text = " ".join(
            [
                str(right.get("problem", "")),
                str(right.get("market_gap", "")),
                str(right.get("solution", "")),
            ]
        ).lower()
        left_tokens = set(_tokenize(left_text))
        right_tokens = set(_tokenize(right_text))
        if not left_tokens or not right_tokens:
            return 0.0
        token_similarity = len(left_tokens & right_tokens) / max(len(left_tokens | right_tokens), 1)
        left_evidence = set(left.get("evidence_ids", []) or [])
        right_evidence = set(right.get("evidence_ids", []) or [])
        evidence_overlap = len(left_evidence & right_evidence) / max(len(left_evidence | right_evidence), 1) if (left_evidence or right_evidence) else 0.0
        source_overlap = len(set(left.get("sources", []) or []) & set(right.get("sources", []) or [])) / max(len(set(left.get("sources", []) or []) | set(right.get("sources", []) or [])), 1)
        return round((token_similarity * 0.55) + (evidence_overlap * 0.25) + (source_overlap * 0.20), 3)

    def _semantic_dedupe(self, opportunities: list[dict], threshold: float = 0.75) -> list[dict]:
        ordered = sorted(
            opportunities,
            key=lambda item: (
                float(item.get("opportunity_score", item.get("market_score", 0))),
                float(item.get("confidence_score", 0)),
                float(item.get("evidence_score", 0)),
            ),
            reverse=True,
        )
        selected: list[dict] = []
        for opportunity in ordered:
            keep = True
            for existing in selected:
                if self._opportunity_similarity(opportunity, existing) > threshold:
                    keep = False
                    break
            if keep:
                selected.append(opportunity)
        return selected

    def _expanded_term_tokens(self, terms: list[str]) -> list[str]:
        expanded: list[str] = []
        for term in terms:
            expanded.extend(_tokenize(str(term)))
            if " " in str(term):
                expanded.extend(_tokenize(str(term).replace(" ", "")))
        return self._term_tokens(expanded)

    def _expand_query_terms(self, query: str) -> list[str]:
        query_lower = query.lower()
        terms = _query_terms(query)
        domain = self._domain_from_query(query)
        if domain in DOMAIN_EXPANSIONS:
            return DOMAIN_EXPANSIONS[domain]
        return terms or [query_lower]

    def _domain_from_query(self, query: str) -> str:
        query_lower = query.lower()
        alias_domain = _domain_alias_matches(query_lower)
        return alias_domain or infer_query_domain(query)

    async def build_opportunities(
        self,
        session: AsyncSession,
        limit: int = 25,
        *,
        query: str | None = None,
        query_id: uuid.UUID | str | None = None,
        evidence_urls: set[str] | None = None,
    ) -> list[dict]:
        query_terms = _query_terms(query or "")
        expanded_terms = self._expand_query_terms(query or "")
        domain = self._domain_from_query(query or "")
        signals = await self._load_signals(
            session,
            query=query or "",
            query_id=query_id,
            query_domain=domain,
            query_terms=query_terms,
            expanded_terms=expanded_terms,
            evidence_urls=evidence_urls,
        )
        if not signals:
            logger.info("No signals available for opportunity generation")
            self._last_debug = {
                "signals_collected": 0,
                "evidence_retrieved": 0,
                "candidates_created": 0,
                "candidates_discarded": {
                    "low_relevance": 0,
                    "duplicate": 0,
                    "no_evidence": 0,
                    "wrong_domain": 0,
                    "low_confidence": 0,
                },
                "domain": domain,
            }
            return []

        def _generate_from_signal_batch(signal_batch: list[MarketSignal]) -> tuple[list[dict], dict[str, int], dict[str, list[MarketSignal]]]:
            signal_batch = [
                signal
                for signal in signal_batch
                if not (
                    signal.source == "github"
                    and is_github_repo_noise(
                        f"{signal.title} {signal.content}",
                        source=signal.source,
                        source_type=signal.source_type,
                    )
                )
            ]
            clusters = self._cluster_signals(signal_batch, domain=domain)
            opportunities: list[dict] = []
            salvage_pool: list[dict] = []
            discarded = {
                "low_relevance": 0,
                "duplicate": 0,
                "no_evidence": 0,
                "wrong_domain": 0,
                "name_noise": 0,
                "low_confidence": 0,
                "salvaged": 0,
            }
            for cluster_key, items in clusters.items():
                opportunity = self._build_opportunity(
                    cluster_key,
                    items,
                    query=query or "",
                    query_terms=query_terms,
                    query_id=query_id,
                    domain=domain,
                    cluster_profile={"cluster_id": cluster_key, "cluster_name": _cluster_display_name(domain, cluster_key)},
                )
                if not opportunity.get("evidence", {}).get("signals"):
                    discarded["no_evidence"] += 1
                    continue
                if self._wrong_domain(opportunity, domain):
                    discarded["wrong_domain"] += 1
                    continue
                if is_opportunity_name_noise(opportunity.get("startup_name", ""), query=query, domain=domain):
                    discarded["name_noise"] += 1
                    continue
                if opportunity.get("query_relevance_score", 0) < 80 or opportunity.get("domain_relevance_score", 0) < 80:
                    discarded["low_relevance"] += 1
                    continue
                if opportunity.get("confidence_score", 0) < 10:
                    discarded["low_confidence"] += 1
                    continue
                opportunities.append(opportunity)

            if len(opportunities) < 5 and domain in CLUSTER_BLUEPRINTS:
                existing_clusters = {str(item.get("cluster_id") or "") for item in opportunities}
                for cluster_key in CLUSTER_BLUEPRINTS.get(domain, {}):
                    if len(opportunities) >= min(limit, 5):
                        break
                    if cluster_key in existing_clusters:
                        continue
                    support = [
                        signal
                        for signal in signal_batch
                        if _cluster_label(_signal_text(signal), domain) == cluster_key
                    ]
                    if not support:
                        support = [
                            signal
                            for signal in signal_batch
                            if _domain_match_text(_signal_text(signal), domain)
                        ]
                    if not support:
                        continue
                    opportunity = self._build_opportunity(
                        cluster_key,
                        support,
                        query=query or "",
                        query_terms=query_terms,
                        query_id=query_id,
                        domain=domain,
                        cluster_profile={"cluster_id": cluster_key, "cluster_name": _cluster_display_name(domain, cluster_key)},
                    )
                    if not opportunity.get("evidence", {}).get("signals"):
                        continue
                    if self._wrong_domain(opportunity, domain):
                        continue
                    if is_opportunity_name_noise(opportunity.get("startup_name", ""), query=query, domain=domain):
                        continue
                    if opportunity.get("query_relevance_score", 0) < 80 or opportunity.get("domain_relevance_score", 0) < 80:
                        continue
                    if opportunity.get("confidence_score", 0) < 10:
                        continue
                    opportunities.append(opportunity)
                    existing_clusters.add(cluster_key)

            before_dedupe = len(opportunities)
            opportunities = sorted(
                opportunities,
                key=lambda o: (
                    o.get("cluster_priority", 99),
                    -o.get("query_relevance_score", 0),
                    -o["opportunity_score"],
                ),
            )[:limit]
            opportunities = self._semantic_dedupe(self._dedupe_opportunities(opportunities))
            discarded["duplicate"] = max(0, before_dedupe - len(opportunities))
            if len(opportunities) < 5 and salvage_pool:
                salvage_pool = sorted(
                    salvage_pool,
                    key=lambda o: (
                        o.get("cluster_priority", 99),
                        -o.get("query_relevance_score", 0),
                        -o["opportunity_score"],
                    ),
                )
                seen_names = {
                    _normalize_name(o.get("startup_name") or o.get("name") or "")
                    for o in opportunities
                }
                seen_keys = {
                    f"{_normalize_name(o.get('startup_name') or o.get('name') or '')}::{_normalize_name(o.get('problem') or '')}::{o.get('query_id') or ''}"
                    for o in opportunities
                }
                for candidate in salvage_pool:
                    name = candidate.get("startup_name") or candidate.get("name") or ""
                    problem = candidate.get("problem") or ""
                    qid = candidate.get("query_id") or ""
                    key = f"{_normalize_name(name)}::{_normalize_name(problem)}::{qid}"
                    if key in seen_keys:
                        continue
                    normalized_name = _normalize_name(name)
                    if normalized_name in seen_names:
                        candidate_name = _make_variant_name(name, problem, seen_names)
                        if candidate_name:
                            candidate["startup_name"] = candidate_name
                            candidate["title"] = candidate_name
                            candidate["name"] = candidate_name
                            normalized_name = _normalize_name(candidate_name)
                            key = f"{normalized_name}::{_normalize_name(problem)}::{qid}"
                    if normalized_name in seen_names:
                        continue
                    opportunities.append(candidate)
                    seen_names.add(normalized_name)
                    seen_keys.add(key)
                    discarded["salvaged"] += 1
                    if len(opportunities) >= min(limit, 5):
                        break
            return opportunities, discarded, clusters

        opportunities, discarded, clusters = _generate_from_signal_batch(signals)
        fallback_used = False
        if query_id is not None and domain != "general" and len(opportunities) < 5:
            historical_signals = await self._load_signals(
                session,
                query=query or "",
                query_id=None,
                query_domain=domain,
                query_terms=query_terms,
                expanded_terms=expanded_terms,
                evidence_urls=None,
            )
            if historical_signals and historical_signals != signals:
                fallback_used = True
                historical_opportunities, historical_discarded, historical_clusters = _generate_from_signal_batch(historical_signals)
                merged = self._dedupe_opportunities(
                    sorted(
                        [*opportunities, *historical_opportunities],
                        key=lambda o: (o.get("cluster_priority", 99), -o.get("query_relevance_score", 0), -o["opportunity_score"]),
                    )[:limit]
                )
                merged = self._semantic_dedupe(merged)
                for key in discarded:
                    discarded[key] += int(historical_discarded.get(key, 0))
                opportunities = merged
                clusters = {**clusters, **historical_clusters}
                signals = historical_signals if len(historical_signals) > len(signals) else signals

        if query_id is not None and domain != "general" and len(opportunities) < 5:
            broad_signals = await self._load_signals(
                session,
                query=query or "",
                query_id=None,
                query_domain=domain,
                query_terms=[],
                expanded_terms=DOMAIN_EXPANSIONS.get(domain, []),
                evidence_urls=None,
                allow_broad_domain_fallback=True,
            )
            if broad_signals and broad_signals != signals:
                fallback_used = True
                broad_opportunities, broad_discarded, broad_clusters = _generate_from_signal_batch(broad_signals)
                merged = self._dedupe_opportunities(
                    sorted(
                        [*opportunities, *broad_opportunities],
                        key=lambda o: (o.get("cluster_priority", 99), -o.get("query_relevance_score", 0), -o["opportunity_score"]),
                    )[:limit]
                )
                merged = self._semantic_dedupe(merged)
                for key in discarded:
                    discarded[key] += int(broad_discarded.get(key, 0))
                opportunities = merged
                clusters = {**clusters, **broad_clusters}
                signals = broad_signals if len(broad_signals) > len(signals) else signals

        self._last_debug = {
            "signals_collected": len(signals),
            "evidence_retrieved": len(signals),
            "candidates_created": len(clusters),
            "candidates_discarded": discarded,
            "domain": domain,
            "fallback_used": fallback_used,
            "clusters_found": len(clusters),
            "evidence_count": sum(len(v) for v in clusters.values()),
            "opportunities_returned": len(opportunities),
        }
        if query_id is not None:
            try:
                query_uuid = uuid.UUID(str(query_id))
            except Exception:
                query_uuid = None
            if query_uuid:
                await self._persist_opportunities(session, opportunities, query_uuid)
        else:
            await self._persist_opportunities(session, opportunities, None)
        return opportunities

    async def get_opportunities(
        self,
        session: AsyncSession,
        limit: int = 50,
        *,
        query_id: uuid.UUID | str | None = None,
    ) -> list[dict]:
        stmt = select(StartupOpportunity)
        if query_id is not None:
            try:
                query_uuid = uuid.UUID(str(query_id))
                stmt = stmt.where(StartupOpportunity.query_id == query_uuid)
            except Exception:
                logger.warning("Invalid query_id provided to opportunity list: %r", query_id)
        result = await session.execute(
            stmt.order_by(
                desc(StartupOpportunity.query_relevance_score),
                desc(StartupOpportunity.market_score),
                desc(StartupOpportunity.created_at),
            ).limit(limit)
        )
        return [self._serialize(row) for row in result.scalars().all()]

    async def get_opportunity(self, session: AsyncSession, opportunity_id: uuid.UUID) -> dict | None:
        row = await opportunity_repository.get_by_id(session, opportunity_id)
        return self._serialize(row) if row else None

    async def get_evidence(self, session: AsyncSession, opportunity_id: uuid.UUID) -> list[dict]:
        opportunity = await opportunity_repository.get_by_id(session, opportunity_id)
        if not opportunity:
            return []
        evidence = opportunity.evidence if isinstance(opportunity.evidence, dict) else {}
        return evidence.get("signals", [])

    async def _load_signals(
        self,
        session: AsyncSession,
        *,
        query: str = "",
        query_id: uuid.UUID | str | None = None,
        query_domain: str | None = None,
        query_terms: list[str] | None = None,
        expanded_terms: list[str] | None = None,
        evidence_urls: set[str] | None = None,
        allow_broad_domain_fallback: bool = False,
    ) -> list[MarketSignal]:
        combined_terms = [t for t in [*(query_terms or []), *(expanded_terms or [])] if t]
        signals = await self._execute_signal_query(
            session,
            query=query,
            query_id=query_id,
            query_domain=query_domain,
            evidence_urls=evidence_urls,
            terms=combined_terms,
            limit=1000,
        )
        if query_domain and query_domain != "general" and signals:
            return signals
        if len(signals) >= 3 and self._signals_are_relevant(signals, combined_terms, self._domain_from_query(query)):
            return signals

        fallback = await self._execute_signal_query(
            session,
            query=query,
            query_id=None,
            query_domain=query_domain,
            evidence_urls=None,
            terms=combined_terms or (query_terms or []),
            limit=1000,
        )
        merged: list[MarketSignal] = []
        seen: set[str] = set()
        for signal in [*signals, *fallback]:
            key = signal.url or signal.source_id or str(signal.id)
            if key in seen:
                continue
            seen.add(key)
            merged.append(signal)
        domain = self._domain_from_query(query)
        if not allow_broad_domain_fallback and len(merged) >= 3 and self._signals_are_relevant(merged, combined_terms, domain):
            return merged

        if domain != "general" or allow_broad_domain_fallback:
            broad_terms = DOMAIN_EXPANSIONS.get(domain, [])
            broad_fallback = await self._execute_signal_query(
                session,
                query=query,
                query_id=None,
                query_domain=query_domain,
                evidence_urls=None,
                terms=[],
                limit=1000,
            )
            if broad_terms:
                domain_filtered = [
                    signal
                for signal in broad_fallback
                    if any(term in _signal_text(signal) for term in broad_terms)
                ]
            else:
                domain_filtered = broad_fallback

            for signal in domain_filtered:
                key = signal.url or signal.source_id or str(signal.id)
                if key in seen:
                    continue
                if self._wrong_domain_text(_signal_text(signal), domain):
                    continue
                seen.add(key)
                merged.append(signal)
            merged.sort(key=lambda signal: (signal.collected_at or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)

        if domain != "general" and len(merged) < 5:
            domain_history = await self._historical_domain_signals(
                session,
                query=query,
                domain=domain,
                limit=1000,
            )
            for signal in domain_history:
                key = signal.url or signal.source_id or str(signal.id)
                if key in seen:
                    continue
                seen.add(key)
                merged.append(signal)
            merged.sort(key=lambda signal: (signal.collected_at or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)

        return merged

    async def _historical_domain_signals(
        self,
        session: AsyncSession,
        *,
        query: str,
        domain: str,
        limit: int = 1000,
    ) -> list[MarketSignal]:
        stmt = select(MarketSignal).where(MarketSignal.source.in_(self.sources))
        result = await session.execute(stmt.order_by(MarketSignal.collected_at.desc()).limit(limit))
        signals = list(result.scalars().all())
        if domain == "general":
            return signals

        candidate_terms = {
            "accounting": {
                "accounting", "bookkeeping", "invoice", "invoices", "receipt", "receipts", "expense", "expenses",
                "cash flow", "payroll", "tax", "vat", "gst", "ledger", "reconciliation", "accounts payable", "accounts receivable",
            },
            "education": {
                "education", "edtech", "learning", "student", "students", "teacher", "teachers", "course", "courses",
                "classroom", "tutor", "tutoring", "exam", "exams", "lms", "study", "lesson", "assessment", "school", "college",
            },
            "fitness": {
                "fitness", "workout", "exercise", "gym", "wellness", "nutrition", "training", "sports", "health",
                "tracking", "tracker", "wearable", "wearables", "fitbit", "athletic", "performance", "recovery", "coach", "member",
            },
            "cybersecurity": {
                "cybersecurity", "cyber security", "security", "soc", "threat", "vulnerability", "phishing", "cloud security",
                "compliance", "identity", "malware", "incident response", "siem", "access",
            },
            "amazon": {
                "amazon", "seller", "fba", "listing", "inventory", "review", "reviews", "repricing", "pricing", "ppc", "keyword", "asin", "marketplace", "product research", "ads",
            },
        }.get(domain, set())
        filtered: list[MarketSignal] = []
        seen: set[str] = set()
        for signal in signals:
            text = _signal_text(signal)
            if self._wrong_domain_text(text, domain):
                continue
            q_score = calculate_query_relevance_score(
                query,
                text,
                domain=domain,
                source=signal.source,
                source_type=signal.source_type,
            )
            d_score = calculate_domain_relevance_score(
                text,
                domain=domain,
                source=signal.source,
                source_type=signal.source_type,
            )
            if q_score < 60.0 or d_score < 60.0:
                continue
            if candidate_terms and not any(term in text for term in candidate_terms):
                continue
            key = signal.url or signal.source_id or str(signal.id)
            if key in seen:
                continue
            seen.add(key)
            signal.query_relevance_score = q_score
            signal.domain_relevance_score = d_score
            filtered.append(signal)
        return filtered

    def _signals_are_relevant(self, signals: list[MarketSignal], terms: list[str], domain: str) -> bool:
        if not signals:
            return False

        domain_terms = {
            "accounting": {
                "accounting",
                "bookkeeping",
                "invoice",
                "receipt",
                "expense",
                "cash flow",
                "payroll",
                "tax",
                "vat",
                "gst",
                "ledger",
                "reconciliation",
                "financial reporting",
                "small business",
                "bookkeeping automation",
                "invoice reconciliation",
                "expense tracking",
                "cash flow forecasting",
                "tax compliance",
                "payroll automation",
            },
            "amazon": {
                "amazon",
                "seller",
                "marketplace",
                "ecommerce",
                "inventory",
                "pricing",
                "review",
                "reviews",
                "fulfillment",
                "listing",
                "ads",
                "fba",
                "product research",
            },
            "education": {
                "education",
                "learning",
                "student",
                "students",
                "teacher",
                "course",
                "classroom",
                "tutor",
                "tutoring",
                "exam",
                "lms",
                "study",
            },
            "productivity": {
                "student",
                "students",
                "study",
                "productivity",
                "focus",
                "assignment",
                "assignments",
                "notes",
                "habit",
                "habits",
                "time management",
                "exam prep",
            },
            "fitness": {
                "fitness",
                "workout",
                "exercise",
                "gym",
                "wellness",
                "nutrition",
                "training",
                "sports",
                "health",
                "tracking",
                "tracker",
                "wearable",
                "wearables",
                "fitbit",
                "athletic",
                "performance",
                "coach",
                "member",
            },
        }

        query_terms = [term.lower() for term in terms if term]
        allowed = domain_terms.get(domain, set())
        scored: list[float] = []
        domain_hits = 0
        total_hits = 0
        for signal in signals[:10]:
            text = f"{signal.title} {signal.content} {signal.source} {signal.source_type}".lower()
            if domain != "general" and not _domain_match_text(text, domain):
                continue
            hits = sum(1 for term in query_terms[:12] if term in text)
            total_hits += hits
            scored.append(hits)
            if domain != "general" and any(term in text for term in allowed):
                domain_hits += 1

        avg_hits = sum(scored) / max(len(scored), 1)
        if domain == "general":
            return avg_hits >= 1.0

        if domain_hits == 0:
            return False

        # Require at least a little direct query alignment plus domain evidence.
        if domain == "productivity":
            return domain_hits >= 2 and total_hits >= 5 and avg_hits >= 1.0

        if domain == "education":
            return domain_hits >= 2 and total_hits >= 3 and avg_hits >= 1.0

        if domain == "amazon":
            return domain_hits >= 2 and total_hits >= 3 and avg_hits >= 1.0

        # If a custom domain is ever added, require strong signal alignment before skipping fallback.
        return domain_hits >= 2 and total_hits >= 4 and avg_hits >= 1.25

    async def _execute_signal_query(
        self,
        session: AsyncSession,
        *,
        query: str,
        query_id: uuid.UUID | str | None,
        query_domain: str | None,
        evidence_urls: set[str] | None,
        terms: list[str],
        limit: int,
    ) -> list[MarketSignal]:
        stmt = select(MarketSignal).where(MarketSignal.source.in_(self.sources))
        if query_id is not None:
            try:
                query_uuid = uuid.UUID(str(query_id))
                stmt = stmt.where(MarketSignal.query_id == query_uuid)
            except Exception:
                logger.warning("Invalid query_id provided to opportunity builder: %r", query_id)
        if query_domain and query_domain != "general":
            stmt = stmt.where(MarketSignal.query_domain == query_domain)
        if evidence_urls:
            stmt = stmt.where(MarketSignal.url.in_(sorted(evidence_urls)))
        result = await session.execute(stmt.order_by(MarketSignal.collected_at.desc()).limit(limit))
        signals = list(result.scalars().all())
        if query_domain and query_domain != "general":
            signals = [
                signal
                for signal in signals
                if not self._wrong_domain_text(_signal_text(signal), query_domain)
            ]
        if query.strip():
            relevance_filtered = []
            for signal in signals:
                text = _signal_text(signal)
                relevance_score = calculate_query_relevance_score(
                    query,
                    text,
                    domain=query_domain or self._domain_from_query(query),
                    source=signal.source,
                    source_type=signal.source_type,
                )
                domain_score = calculate_domain_relevance_score(
                    text,
                    domain=query_domain or self._domain_from_query(query),
                    source=signal.source,
                    source_type=signal.source_type,
                )
                if relevance_score < 60.0 or domain_score < 60.0:
                    continue
                if is_github_repo_noise(text, source=signal.source, source_type=signal.source_type):
                    continue
                signal.query_relevance_score = relevance_score
                signal.domain_relevance_score = domain_score
                relevance_filtered.append(signal)
            signals = relevance_filtered
        return signals

    def _cluster_signals(self, signals: list[MarketSignal], domain: str = "general") -> dict[str, list[MarketSignal]]:
        clusters: dict[str, list[MarketSignal]] = defaultdict(list)
        for signal in signals:
            key = _cluster_label(f"{signal.title} {signal.content}", domain)
            clusters[key].append(signal)
        return dict(
            sorted(
                clusters.items(),
                key=lambda kv: (_cluster_priority(domain, kv[0]), -len(kv[1]), kv[0]),
            )
        )

    def _build_opportunity(
        self,
        cluster_key: str,
        signals: list[MarketSignal],
        *,
        query: str = "",
        query_terms: list[str] | None = None,
        query_id: uuid.UUID | str | None = None,
        domain: str = "general",
        cluster_profile: dict | None = None,
    ) -> dict:
        query_terms = query_terms or _query_terms(query)
        cluster_profile = cluster_profile or {}
        cluster_id = str(cluster_profile.get("cluster_id") or cluster_key or "general")
        cluster_name = str(cluster_profile.get("cluster_name") or _cluster_display_name(domain, cluster_id) or cluster_id)
        cluster_priority = int(cluster_profile.get("cluster_priority", _cluster_priority(domain, cluster_id)))
        titles = [s.title for s in signals[:5]]
        contents = [s.content for s in signals[:5]]
        sources = Counter(s.source for s in signals)
        total = len(signals)
        now = datetime.now(timezone.utc)
        first_seen = min((_ensure_aware(s.collected_at) for s in signals if _ensure_aware(s.collected_at)), default=now)
        last_seen = max((_ensure_aware(s.collected_at) for s in signals if _ensure_aware(s.collected_at)), default=now)
        days_active = max((last_seen - first_seen).days + 1, 1)
        signal_growth_30d = sum(
            1
            for s in signals
            if _ensure_aware(s.collected_at) and _ensure_aware(s.collected_at) >= now - timedelta(days=30)
        )
        prev_30d = sum(
            1
            for s in signals
            if _ensure_aware(s.collected_at)
            and now - timedelta(days=60) <= _ensure_aware(s.collected_at) < now - timedelta(days=30)
        )
        growth_score = _clamp_score(max(0.0, (signal_growth_30d - prev_30d) * 9 + total * 5 + len(sources) * 4))
        source_quality_scores = [_source_quality(signal) for signal in signals]
        recency_scores = [_recency_weight(signal.collected_at) for signal in signals]
        textual_support_scores = [_signal_textual_support(signal) for signal in signals]
        signal_diversity = len({s.source for s in signals})
        cluster_tokens = [token for token in _tokenize(cluster_key) if token]
        cluster_specificity_bonus = min(6.0, len(set(cluster_tokens)) * 1.2)
        avg_source_quality = mean(source_quality_scores) if source_quality_scores else 0.5
        avg_recency = mean(recency_scores) if recency_scores else 0.45
        avg_textual_support = mean(textual_support_scores) if textual_support_scores else 0.0
        unique_urls = len({signal.url for signal in signals if signal.url})
        recent_signals = sum(1 for score in recency_scores if score >= 0.8)
        signal_volume_factor = math.log1p(total)
        discussion_volume = sum(
            min(20, int(getattr(signal, "comments_count", 0) or 0))
            for signal in signals
            if signal.source in {"hackernews", "reddit"}
        )
        cluster_support_score = _clamp_score(
            (signal_volume_factor * 10.0)
            + (len(sources) * 6.5)
            + (avg_source_quality * 12.0)
            + (avg_textual_support * 16.0)
            + (cluster_specificity_bonus * 1.5)
        )
        evidence_score = _clamp_score(
            min(20.0, signal_volume_factor * 5.5)
            + min(14.0, len(sources) * 4.5)
            + min(12.0, unique_urls * 2.8)
            + min(18.0, avg_source_quality * 14.0)
            + min(14.0, avg_recency * 12.0)
        )
        demand_score = _clamp_score(
            min(22.0, signal_volume_factor * 6.0)
            + min(14.0, len(sources) * 4.5)
            + min(12.0, recent_signals * 0.8)
            + min(16.0, avg_source_quality * 13.0)
            + min(10.0, discussion_volume / 12.0)
            + min(10.0, growth_score * 0.08)
            + (cluster_specificity_bonus * 1.2)
        )
        pain_score = _clamp_score(
            (total * 4.5)
            + (len(sources) * 7.0)
            + (avg_textual_support * 25.0)
            + (avg_source_quality * 15.0)
        )
        competitive_signals = sum(
            1
            for signal in signals
            if any(term in f"{signal.title} {signal.content}".lower() for term in ("tool", "platform", "assistant", "copilot", "tracker", "automation"))
        )
        competition_pressure = (
            min(24.0, signal_volume_factor * 4.5)
            + min(18.0, len(sources) * 5.0)
            + min(18.0, sum(max(0, count - 1) * 2.2 for count in sources.values()))
            + min(12.0, competitive_signals * 1.8)
            + min(8.0, signal_diversity * 1.5)
            - min(18.0, cluster_specificity_bonus * 1.8 + avg_textual_support * 6.0)
        )
        competition_score = _clamp_score(competition_pressure)
        whitespace_score = _clamp_score(100.0 - competition_score)
        feasibility_score = _clamp_score(
            82.0
            - sum(10 for s in signals if "regulated" in f"{s.title} {s.content}".lower())
            - sum(6 for s in signals if "integration" in f"{s.title} {s.content}".lower())
            + max(0.0, 10.0 - len(sources))
        )
        evidence = self._evidence(signals)
        salient_terms = _salient_terms(signals, query_terms)
        topic_terms: list[str] = []
        for term in salient_terms:
            if term and term not in topic_terms:
                topic_terms.append(term)
        for term in query_terms:
            if term and term not in topic_terms and term not in QUERY_FILLER_WORDS:
                topic_terms.append(term)
            if len(topic_terms) >= 2:
                break
        topic = cluster_name or _join_terms(topic_terms) or cluster_id or query or "market opportunity"
        signal_relevance_scores = [float(getattr(s, "query_relevance_score", 0.0) or 0.0) for s in signals]
        avg_signal_relevance = mean(signal_relevance_scores) if signal_relevance_scores else 0.0
        signal_domain_scores = [float(getattr(s, "domain_relevance_score", 0.0) or 0.0) for s in signals]
        avg_signal_domain_relevance = mean(signal_domain_scores) if signal_domain_scores else 0.0
        expanded_terms = self._expand_query_terms(query)
        text = f"{' '.join(titles)} {' '.join(contents)}".lower()
        cluster_text = f"{cluster_name.replace('_', ' ')} {cluster_id.replace('_', ' ')}".lower()
        direct_hits = sum(1 for term in query_terms if term and term in text)
        expanded_tokens = self._expanded_term_tokens(expanded_terms)
        expanded_hits = sum(1 for term in expanded_tokens if term and term in text)
        title_match = sum(1 for term in query_terms[:3] if term and term in " ".join(titles).lower())
        cluster_direct_hits = sum(1 for term in query_terms if term and term in cluster_text)
        cluster_expanded_hits = sum(1 for term in expanded_tokens if term and term in cluster_text)
        cluster_alignment_bonus = min(30.0, (cluster_direct_hits * 12.0) + (cluster_expanded_hits * 8.0))
        age_span_days = max((last_seen - first_seen).days, 0)
        semantic_support = min(
            20.0,
            max(avg_signal_relevance * 0.18, total * 1.5)
            + avg_source_quality * 6.0
            + signal_diversity * 1.5
            + min(4.0, age_span_days * 0.5),
        )
        if self._domain_from_query(query) in {"education", "productivity"}:
            domain_terms = set(DOMAIN_EXPANSIONS.get(self._domain_from_query(query), []))
            if any(term in text for term in domain_terms):
                semantic_support = min(20.0, semantic_support + 5.0)
        wrong_domain_penalty = -50.0 if self._wrong_domain_text(text, self._domain_from_query(query)) else 0.0
        direct_ratio = direct_hits / max(len(query_terms), 1)
        expanded_ratio = expanded_hits / max(len(expanded_tokens), 1)
        title_ratio = title_match / max(min(len(query_terms[:3]), 3), 1)
        domain_alignment_bonus = 12.0 if domain != "general" else 0.0
        query_relevance_score = _clamp_score(
            (direct_ratio * 40.0)
            + (expanded_ratio * 25.0)
            + (title_ratio * 20.0)
            + semantic_support
            + min(24.0, cluster_support_score * 0.8)
            + cluster_alignment_bonus
            + domain_alignment_bonus
            + wrong_domain_penalty
        )
        if domain in CLUSTER_BLUEPRINTS and cluster_id in CLUSTER_BLUEPRINTS.get(domain, {}):
            query_relevance_score = max(query_relevance_score, 80.0)
        domain_relevance_score = _clamp_score(
            max(
                avg_signal_domain_relevance,
                calculate_domain_relevance_score(
                    f"{query} {topic} {cluster_name} {text}",
                    domain=domain,
                ),
            )
        )
        if domain in CLUSTER_BLUEPRINTS and cluster_id in CLUSTER_BLUEPRINTS.get(domain, {}):
            domain_relevance_score = max(domain_relevance_score, 80.0)
        confidence_score = _clamp_score(
            (len(sources) * 14.0)
            + (avg_source_quality * 24.0)
            + (avg_recency * 18.0)
            + (signal_diversity * 4.0)
            + min(20.0, avg_signal_relevance * 0.2)
            + min(12.0, len(evidence.get("signals", [])) * 1.5)
            + min(4.0, cluster_specificity_bonus * 0.6)
        )
        opportunity_score = _clamp_score(
            (demand_score * 0.30)
            + (evidence_score * 0.25)
            + (query_relevance_score * 0.20)
            + (confidence_score * 0.15)
            + (whitespace_score * 0.10)
        )
        opportunity = {
            "id": str(uuid.uuid4()),
            "query_id": str(query_id) if query_id else None,
            "query_domain": domain,
            "cluster_id": cluster_id,
            "cluster_name": cluster_name,
            "cluster_priority": cluster_priority,
            "startup_name": _select_product_name(query, topic, signals, query_terms, cluster_key=cluster_id, domain=domain),
            "problem": _problem_statement_for(topic, query, signals, domain=domain, cluster_key=cluster_id),
            "market_gap": f"Existing tools do not fully solve {cluster_name}.",
            "solution": _pitch_for(topic, query, domain=domain, cluster_key=cluster_id),
            "market_score": opportunity_score,
            "opportunity_score": opportunity_score,
            "confidence_score": confidence_score,
            "evidence_score": evidence_score,
            "demand_score": round(demand_score, 1),
            "pain_score": round(pain_score, 1),
            "growth_score": round(growth_score, 1),
            "competition_score": round(competition_score, 1),
            "whitespace_score": whitespace_score,
            "feasibility_score": round(feasibility_score, 1),
            "query_relevance_score": query_relevance_score,
            "query_domain_similarity": round(query_relevance_score / 100.0, 2),
            "domain_relevance_score": domain_relevance_score,
            "domain_similarity": round(domain_relevance_score / 100.0, 2),
            "competition_level": _competition_level(competition_score),
            "emergence_date": first_seen.isoformat() if first_seen else None,
            "last_signal_at": last_seen.isoformat() if last_seen else None,
            "signal_growth_30d": signal_growth_30d,
            "trend_acceleration": round((signal_growth_30d - prev_30d) / max(days_active, 1), 2),
            "market_momentum": round((total / max(days_active, 1)) * 10, 2),
            "evidence": evidence,
            "explanation": {
                "query_domain": domain,
                "why_this_opportunity_exists": f"Recurring evidence across {', '.join(sorted(sources.keys()))} within the {cluster_name} cluster.",
                "which_signals_created_it": evidence.get("signals", []),
                "why_demand_is_growing": f"{signal_growth_30d} recent signals versus {prev_30d} in the prior period.",
            },
            "target_customers": _customer_for(topic, query, domain=domain, cluster_key=cluster_id),
            "revenue_model": _revenue_model(topic, query, domain=domain, cluster_key=cluster_id),
            "mvp_features": {"items": _mvp_features(topic, query, domain=domain, cluster_key=cluster_id)},
            "go_to_market": _gtm(topic, query, domain=domain, cluster_key=cluster_id),
            "evidence_count": len(evidence.get("signals", [])),
        }
        if is_opportunity_name_noise(opportunity["startup_name"], query=query, domain=domain):
            opportunity["startup_name"] = _build_safe_product_name(cluster_name or topic or query or "market insight", suffix="Assistant")
        opportunity["title"] = opportunity["startup_name"]
        opportunity["description"] = opportunity["solution"]
        opportunity["confidence"] = confidence_score
        opportunity["sources"] = evidence.get("sources", [])
        opportunity["target_user"] = self._target_user_for_topic(topic, query)
        opportunity["evidence_ids"] = self._normalized_evidence_ids(signals)
        return opportunity

    def _wrong_domain(self, opportunity: dict, domain: str) -> bool:
        if domain == "general":
            return False
        text = " ".join(
            [
                str(opportunity.get("startup_name", "")),
                str(opportunity.get("problem", "")),
                str(opportunity.get("market_gap", "")),
                str(opportunity.get("solution", "")),
                " ".join(opportunity.get("sources", []) or []),
                str(opportunity.get("target_user", "")),
            ]
        ).lower()
        return self._wrong_domain_text(text, domain)

    def _wrong_domain_text(self, text: str, domain: str) -> bool:
        return not _domain_match_text(text, domain)

    def _dedupe_opportunities(self, opportunities: list[dict]) -> list[dict]:
        deduped: list[dict] = []
        seen_keys: dict[str, dict] = {}
        seen_names: dict[str, dict] = {}

        for opportunity in opportunities:
            name = opportunity.get("startup_name") or opportunity.get("name") or ""
            problem = opportunity.get("problem") or ""
            market_gap = opportunity.get("market_gap") or ""
            solution = opportunity.get("solution") or ""
            evidence_ids = tuple(sorted(set(opportunity.get("evidence_ids") or [])))
            query_id = opportunity.get("query_id") or ""
            base_key = (
                f"{_normalize_name(name)}::"
                f"{_normalize_name(problem)}::"
                f"{_normalize_name(market_gap)}::"
                f"{_normalize_name(solution)}::"
                f"{query_id}::"
                f"{'|'.join(evidence_ids)}"
            )
            normalized_name = _normalize_name(name)
            existing = seen_keys.get(base_key)
            if existing:
                existing_score = float(existing.get("opportunity_score", existing.get("market_score", 0)) or 0)
                current_score = float(opportunity.get("opportunity_score", opportunity.get("market_score", 0)) or 0)
                if current_score > existing_score:
                    deduped.remove(existing)
                    seen_keys[base_key] = opportunity
                    if normalized_name in seen_names and seen_names[normalized_name] is existing:
                        seen_names[normalized_name] = opportunity
                    deduped.append(opportunity)
                continue

            duplicate_name_owner = seen_names.get(normalized_name)
            if duplicate_name_owner:
                candidate = _make_variant_name(
                    name,
                    problem,
                    set(seen_names.keys()),
                    str(opportunity.get("cluster_name") or opportunity.get("cluster_id") or ""),
                )
                if candidate:
                    opportunity["startup_name"] = candidate
                    opportunity["title"] = candidate
                    opportunity["name"] = candidate
                    normalized_name = _normalize_name(candidate)
                if normalized_name in seen_names:
                    existing_owner = seen_names[normalized_name]
                    existing_score = float(existing_owner.get("opportunity_score", existing_owner.get("market_score", 0)) or 0)
                    current_score = float(opportunity.get("opportunity_score", opportunity.get("market_score", 0)) or 0)
                    if current_score <= existing_score:
                        continue
                    deduped.remove(existing_owner)
            seen_keys[base_key] = opportunity
            seen_names[normalized_name] = opportunity
            deduped.append(opportunity)

        return deduped

    def _target_user_for_topic(self, topic: str, query: str) -> str:
        text = f"{topic} {query}".lower()
        if "amazon" in text or "seller" in text:
            return "Amazon sellers and marketplace operators"
        if "teacher" in text:
            return "Teachers and school administrators"
        if "education" in text or "course" in text or "learning" in text:
            return "Students and educators"
        if "student" in text:
            return "Students and learners"
        if "productivity" in text or "focus" in text:
            return "Students and knowledge workers"
        if "fitness" in text or "workout" in text or "exercise" in text or "gym" in text or "wellness" in text or "nutrition" in text:
            return "Fitness enthusiasts, athletes, coaches, and gym operators"
        return "Founders and operators"

    def _evidence(self, signals: list[MarketSignal]) -> dict:
        items = []
        for s in signals[:20]:
            snippet = (s.content or "").strip().replace("\n", " ")
            if len(snippet) > 240:
                snippet = snippet[:240].rstrip() + "..."
            items.append({
                "source": s.source,
                "signal_id": str(s.id),
                "title": s.title,
                "snippet": snippet or s.title,
                "url": s.url,
                "collected_at": s.collected_at.isoformat() if s.collected_at else None,
                "source_type": s.source_type,
            })
        return {
            "signals": items,
            "sources": sorted({s.source for s in signals}),
        }

    async def _persist_opportunities(
        self,
        session: AsyncSession,
        opportunities: list[dict],
        query_id: uuid.UUID | None,
    ) -> None:
        objects = []
        for o in opportunities:
            objects.append(StartupOpportunity(
                id=uuid.UUID(str(o["id"])) if o.get("id") else uuid.uuid4(),
                market_gap_id=None,
                query_id=query_id,
                query_domain=o.get("query_domain", "general"),
                domain_relevance_score=o.get("domain_relevance_score", 0.0),
                startup_name=o["startup_name"],
                problem=o["problem"],
                solution=o["solution"],
                market_score=o["market_score"],
                opportunity_score=o.get("opportunity_score", o["market_score"]),
                confidence_score=o["confidence_score"],
                evidence_score=o.get("evidence_score", 0.0),
                demand_score=o["demand_score"],
                pain_score=o["pain_score"],
                growth_score=o["growth_score"],
                competition_score=o["competition_score"],
                whitespace_score=o.get("whitespace_score", 0.0),
                feasibility_score=o["feasibility_score"],
                query_relevance_score=o.get("query_relevance_score", 0.0),
                competition_level=o["competition_level"],
                emergence_date=datetime.fromisoformat(o["emergence_date"]) if o.get("emergence_date") else None,
                last_signal_at=datetime.fromisoformat(o["last_signal_at"]) if o.get("last_signal_at") else None,
                signal_growth_30d=o["signal_growth_30d"],
                trend_acceleration=o["trend_acceleration"],
                market_momentum=o["market_momentum"],
                evidence=o["evidence"],
                explanation=o["explanation"],
                target_customers=o["target_customers"],
                revenue_model=o["revenue_model"],
                mvp_features=o["mvp_features"],
                go_to_market=o["go_to_market"],
            ))
        session.add_all(objects)
        await session.flush()

    def _serialize(self, opp: StartupOpportunity) -> dict:
        competition_level = _normalize_competition_level(
            getattr(opp, "competition_level", None),
            float(opp.competition_score or 0.0),
        )
        return {
            "id": str(opp.id),
                "query_id": str(opp.query_id) if opp.query_id else None,
            "query_domain": getattr(opp, "query_domain", "general"),
            "domain_relevance_score": getattr(opp, "domain_relevance_score", 0.0),
            "startup_name": opp.startup_name,
            "name": opp.startup_name,
            "problem": opp.problem,
            "solution": opp.solution,
            "market_score": opp.market_score,
            "opportunity_score": getattr(opp, "opportunity_score", opp.market_score),
            "confidence_score": opp.confidence_score,
            "evidence_score": getattr(opp, "evidence_score", 0.0),
            "demand_score": opp.demand_score,
            "pain_score": opp.pain_score,
            "growth_score": opp.growth_score,
            "competition_score": opp.competition_score,
            "whitespace_score": getattr(opp, "whitespace_score", max(0.0, 100.0 - float(opp.competition_score or 0.0))),
            "feasibility_score": opp.feasibility_score,
            "query_relevance_score": getattr(opp, "query_relevance_score", 0.0),
            "query_domain_similarity": round(float(getattr(opp, "query_relevance_score", 0.0) or 0.0) / 100.0, 2),
            "domain_similarity": round(float(getattr(opp, "domain_relevance_score", 0.0) or 0.0) / 100.0, 2),
            "competition_level": competition_level,
            "emergence_date": opp.emergence_date.isoformat() if opp.emergence_date else None,
            "last_signal_at": opp.last_signal_at.isoformat() if opp.last_signal_at else None,
            "signal_growth_30d": opp.signal_growth_30d,
            "trend_acceleration": opp.trend_acceleration,
            "market_momentum": opp.market_momentum,
            "evidence": opp.evidence,
            "explanation": opp.explanation,
            "target_customers": opp.target_customers,
            "target_user": opp.target_customers,
            "revenue_model": opp.revenue_model,
            "mvp_features": opp.mvp_features,
            "go_to_market": opp.go_to_market,
            "created_at": opp.created_at.isoformat() if opp.created_at else None,
            "market_gap": opp.problem,
            "sources": sorted({item.get("source", "") for item in (opp.evidence or {}).get("signals", []) if item.get("source")} ),
        }


opportunity_intelligence_service = OpportunityIntelligenceService()
