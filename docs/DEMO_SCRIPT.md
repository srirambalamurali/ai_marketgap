# Demo Script

## Project Intro

AI Market Gap Discovery Engine is a live market intelligence platform that collects signals from GitHub, Hacker News, RSS, Reddit, and Google Trends, then turns them into evidence-backed startup opportunities with scoring, explanations, and reports.

## Problem Statement

Founders and product teams spend too much time manually scanning fragmented signals to identify what to build next. This platform centralizes those signals, clusters recurring pain points, and ranks opportunities backed by evidence.

## Live Demo Steps

1. Start the backend API.
2. Start the frontend dashboard.
3. Open `/dashboard` to see live metrics and the demo action.
4. Click `Run Live Demo` to regenerate opportunities from real stored data.
5. Open `/opportunities` to browse ranked opportunities.
6. Open an opportunity detail page to inspect evidence and explanation.
7. Open `/signals` to inspect live collected signals and filters.
8. Open `/workflow` to review LangGraph execution state.
9. Open `/rag` to run a live retrieval search.
10. Open `/reports` to inspect generated reports.

## Tech Stack Explanation

- Next.js 15: app router, server rendering, and route-based dashboard structure
- TypeScript: typed integration with the backend APIs
- Tailwind CSS: design system and responsive styling
- TanStack Query: live API fetching, caching, and refresh
- Zustand: lightweight UI state
- Recharts: dashboard visualizations

## How the AI Stack Works

- LLM: used in backend analysis agents for trend/pain point/report generation
- RAG: retrieves live stored context and supports semantic search
- MCP: supports workspace-aware tooling and coordinated agent workflows in the platform environment
- LangGraph: orchestrates the live analysis workflow from signals to reports
- LangChain: supports LLM and retrieval abstractions used by backend services

## Demo Notes

- Demo Mode only uses live stored data in PostgreSQL.
- No mock data is shown in the main opportunity and signal flows.
- If ChromaDB or Reddit credentials are unavailable, those areas should be explained as environment-dependent limitations.

