from langgraph.graph import StateGraph, START, END

from app.models.state import MarketGapState
from app.agents.data_collector.agent import DataCollectorAgent
from app.agents.validation.agent import ValidationAgent
from app.agents.report.agent import ReportAgent
from app.agents.trend_analysis.agent import TrendAnalysisAgent
from app.agents.market_gap.agent import MarketGapAgent
from app.agents.opportunity_scoring.agent import OpportunityScoringAgent
from app.agents.opportunity_intelligence.agent import OpportunityIntelligenceAgent
from app.agents.trend_detector.agent import TrendDetectionAgent
from app.agents.pain_point.agent import PainPointAgent
from app.agents.gap_analysis.agent import GapAnalysisAgent
from app.agents.opportunity.agent import OpportunityAgent

data_collector = DataCollectorAgent()
trend_detector = TrendDetectionAgent()
pain_point = PainPointAgent()
gap_analysis = GapAnalysisAgent()
opportunity = OpportunityAgent()
validation = ValidationAgent()
report_agent = ReportAgent()
trend_analysis = TrendAnalysisAgent()
market_gap = MarketGapAgent()
opp_scoring = OpportunityScoringAgent()
opp_intel = OpportunityIntelligenceAgent()

AGENT_ORDER: list[tuple[str, object]] = [
    ("data_collector", data_collector),
    ("trend_detector", trend_detector),
    ("trend_analysis", trend_analysis),
    ("pain_point", pain_point),
    ("market_gap", market_gap),
    ("gap_analysis", gap_analysis),
    ("opportunity_intelligence", opp_intel),
    ("opportunity", opportunity),
    ("opp_scoring", opp_scoring),
    ("validation", validation),
    ("report", report_agent),
]


def _make_node(agent):
    async def node(state: MarketGapState) -> dict:
        return await agent.run(state)
    return node


_compiled = None


def build_graph():
    graph = StateGraph(MarketGapState)

    for name, agent in AGENT_ORDER:
        graph.add_node(name, _make_node(agent))

    graph.add_edge(START, "data_collector")

    for i in range(len(AGENT_ORDER) - 1):
        graph.add_edge(AGENT_ORDER[i][0], AGENT_ORDER[i + 1][0])

    graph.add_edge("report", END)

    return graph.compile()


def get_graph():
    global _compiled
    if _compiled is None:
        _compiled = build_graph()
    return _compiled


def print_graph_mermaid() -> str:
    compiled = get_graph()
    return compiled.get_graph().draw_mermaid()
