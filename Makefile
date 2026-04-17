.PHONY: help up down logs logs-backend logs-worker logs-frontend shell-backend shell-db shell-redis clean migrate

help:
	@echo "FPV Manager - Development Commands"
	@echo "===================================="
	@echo ""
	@echo "Docker Compose:"
	@echo "  make up              Start all services"
	@echo "  make down            Stop and remove all services"
	@echo "  make logs            Stream logs from all services"
	@echo "  make logs-backend    Stream only backend logs"
	@echo "  make logs-worker     Stream only worker logs"
	@echo "  make logs-frontend   Stream only frontend logs"
	@echo ""
	@echo "Interactive:"
	@echo "  make shell-backend   Open bash shell in backend container"
	@echo "  make shell-db        Open psql shell in postgres container"
	@echo "  make shell-redis     Open redis-cli in redis container"
	@echo "  make shell-minio     Open shell in minio container"
	@echo ""
	@echo "Development:"
	@echo "  make migrate         Run Alembic database migrations"
	@echo "  make clean           Prune Docker system (remove unused images/volumes)"
	@echo "  make rebuild         Rebuild all Docker images"
	@echo ""

up:
	@echo "🔍 Checking Docker Compose version..."
	@COMPOSE_VERSION=$$(docker compose version --short 2>/dev/null || echo "0.0.0"); \
	REQUIRED_VERSION="2.24.0"; \
	if printf '%s\n' "$$REQUIRED_VERSION" "$$COMPOSE_VERSION" | sort -V | head -n1 | grep -q "$$REQUIRED_VERSION"; then \
		echo "✅ Docker Compose version $$COMPOSE_VERSION meets requirement (>=2.24.0)"; \
	else \
		echo "❌ ERROR: Docker Compose version $$COMPOSE_VERSION is too old."; \
		echo "   This project requires Docker Compose v2.24.0+ for !override tag support."; \
		echo "   Please upgrade Docker Compose and try again."; \
		exit 1; \
	fi
	docker compose up -d
	@echo "✅ Services starting. Check health with 'docker compose ps'"

down:
	docker compose down
	@echo "✅ Services stopped"

logs:
	docker compose logs -f

logs-backend:
	docker compose logs -f backend

logs-worker:
	docker compose logs -f worker

logs-frontend:
	docker compose logs -f frontend

shell-backend:
	docker compose exec backend bash

shell-db:
	docker compose exec postgres psql -U ${POSTGRES_USER:-fpv_admin} -d ${POSTGRES_DB:-fpv_manager}

shell-redis:
	docker compose exec redis redis-cli

shell-minio:
	docker compose exec minio bash

migrate:
	docker compose exec backend alembic upgrade head
	@echo "✅ Database migrations applied"

rebuild:
	docker compose build --no-cache
	@echo "✅ Images rebuilt. Run 'make up' to start"

clean:
	docker system prune -a --volumes -f
	@echo "✅ Docker system cleaned"

status:
	docker compose ps