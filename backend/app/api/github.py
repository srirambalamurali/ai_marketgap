from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.postgres import get_db
from app.services.github_collector import GitHubCollector
from app.repositories.documents import bulk_insert_documents
from app.utils.logging import get_logger

router = APIRouter(prefix="/collect/github", tags=["github"])
logger = get_logger("api.github")


class GitHubCollectRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    repo_limit: int = Field(default=20, ge=1, le=100)
    issue_limit: int = Field(default=50, ge=1, le=100)


class GitHubCollectResponse(BaseModel):
    success: bool
    repositories_found: int
    issues_found: int
    documents_saved: int
    errors: list[str] = []


@router.post("", response_model=GitHubCollectResponse)
async def collect_github(
    request: GitHubCollectRequest,
    db: AsyncSession = Depends(get_db),
):
    collector = GitHubCollector()
    errors: list[str] = []

    try:
        repos = await collector.search_repositories(
            request.query, limit=request.repo_limit
        )
    except Exception as exc:
        logger.error("Repository collection failed: %s", exc)
        errors.append(f"Repository search failed: {exc}")
        repos = []

    try:
        issues = await collector.search_issues(
            request.query, limit=request.issue_limit
        )
    except Exception as exc:
        logger.error("Issue collection failed: %s", exc)
        errors.append(f"Issue search failed: {exc}")
        issues = []

    all_docs = repos + issues

    saved = 0
    if all_docs:
        try:
            saved = await bulk_insert_documents(db, all_docs)
            await db.commit()
        except Exception as exc:
            logger.error("Database save failed: %s", exc)
            errors.append(f"Database save failed: {exc}")
            await db.rollback()

    return GitHubCollectResponse(
        success=len(errors) == 0,
        repositories_found=len(repos),
        issues_found=len(issues),
        documents_saved=saved,
        errors=errors,
    )
