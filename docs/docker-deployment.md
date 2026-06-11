# Docker Deployment Notes

## Bring Up

```bash
docker compose up --build
```

## Health Checks

- Frontend: `http://localhost:3000`
- Backend health: `http://localhost:8007/api/v1/health`
- Chroma heartbeat: `http://localhost:8001/api/v2/heartbeat`

## PostgreSQL Backup

```bash
pg_dump -h localhost -p 5432 -U postgres -Fc -f marketgap.dump marketgap
```

## PostgreSQL Restore into Docker

```bash
docker compose exec -T postgres pg_restore -U postgres -d marketgap < marketgap.dump
```

## Chroma Reindex

```bash
docker compose exec backend python scripts/reindex_chroma_from_postgres.py
```

## Logs

```bash
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f postgres
docker compose logs -f chroma
```
