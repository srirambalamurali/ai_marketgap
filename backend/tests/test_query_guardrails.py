from app.services.query_guardrails import (
    calculate_query_relevance,
    calculate_query_relevance_score,
    infer_query_domain,
    is_github_repo_noise,
)


def test_infer_query_domain_fitness():
    assert infer_query_domain("Find opportunities in fitness technology") == "fitness"


def test_query_relevance_blocks_irrelevant_domains():
    fitness_query = "Find opportunities in fitness technology"
    assert calculate_query_relevance(fitness_query, "Workout tracker for gym members", domain="fitness") >= 0.8
    assert calculate_query_relevance_score(fitness_query, "Workout tracker for gym members", domain="fitness") >= 80
    assert calculate_query_relevance_score(fitness_query, "Enterprise AI Governance", domain="fitness") < 70
    assert calculate_query_relevance_score(fitness_query, "Rental Property Search", domain="fitness") < 70
    assert calculate_query_relevance_score(fitness_query, "Teacher Workload Automation Assistant", domain="fitness") < 70


def test_repo_noise_is_rejected():
    assert is_github_repo_noise("Reluctant2828 System-Fitness-Advisor-Skill", source="github") is True
    assert is_github_repo_noise("Javlonbek1233 Apex-Premium-Fitness", source="github") is True
    assert is_github_repo_noise("Personalized Course Recommendation Engine", source="github") is False
