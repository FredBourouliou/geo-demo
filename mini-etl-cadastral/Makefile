.PHONY: help up down logs init-db venv load query reset psql clean status

# Default target
help:
	@echo "Mini-ETL Cadastral - Available commands:"
	@echo ""
	@echo "  make up         - Start PostgreSQL/PostGIS container"
	@echo "  make down       - Stop and remove containers"
	@echo "  make logs       - Show database logs"
	@echo "  make status     - Show container status"
	@echo "  make init-db    - Initialize PostGIS and create schema"
	@echo "  make venv       - Create Python virtual environment"
	@echo "  make load       - Load shapefile into PostGIS"
	@echo "  make query      - Run example spatial queries"
	@echo "  make psql       - Open PostgreSQL shell"
	@echo "  make reset      - Reset everything (down + up + init-db)"
	@echo "  make clean      - Remove virtual environment and outputs"
	@echo ""
	@echo "Quick start:"
	@echo "  1. cp .env.example .env"
	@echo "  2. make up"
	@echo "  3. make init-db"
	@echo "  4. make venv"
	@echo "  5. Place shapefile in data/sample_shapefile.shp"
	@echo "  6. make load"
	@echo "  7. make query"

# Docker commands
up:
	@echo "Starting PostgreSQL/PostGIS container..."
	@docker compose up -d
	@echo "Waiting for database to be ready..."
	@sleep 5
	@docker compose exec -T db pg_isready -U postgres
	@echo "✓ Database is ready!"

down:
	@echo "Stopping containers..."
	@docker compose down

down-volumes:
	@echo "Stopping containers and removing volumes..."
	@docker compose down -v

logs:
	@docker compose logs -f db

status:
	@docker compose ps
	@echo ""
	@docker compose exec -T db pg_isready -U postgres && echo "✓ Database is ready" || echo "✗ Database is not ready"

# Database initialization
init-db:
	@echo "Initializing PostGIS extension and schema..."
	@docker compose exec -T db psql -U postgres -d gis -f /docker-entrypoint-initdb.d/01-enable-postgis.sql
	@docker compose exec -T db psql -U postgres -d gis -f /docker-entrypoint-initdb.d/02-schema.sql
	@echo "✓ Database initialized"

# Python environment
venv:
	@if [ ! -d "venv" ]; then \
		echo "Creating Python virtual environment..."; \
		python3 -m venv venv; \
		echo "Installing dependencies..."; \
		./venv/bin/pip install --upgrade pip; \
		./venv/bin/pip install -r requirements.txt; \
		echo "✓ Virtual environment created and dependencies installed"; \
	else \
		echo "Virtual environment already exists. Updating dependencies..."; \
		./venv/bin/pip install -r requirements.txt; \
	fi

# Data loading
load:
	@if [ ! -f ".env" ]; then \
		echo "Error: .env file not found. Run: cp .env.example .env"; \
		exit 1; \
	fi
	@if [ ! -f "data/sample_shapefile.shp" ]; then \
		echo "Error: No shapefile found at data/sample_shapefile.shp"; \
		echo "Please place your shapefile in the data/ directory"; \
		exit 1; \
	fi
	@echo "Loading shapefile into PostGIS..."
	@./venv/bin/python scripts/load_shapefile.py --shp data/sample_shapefile.shp --infer-commune

load-custom:
	@if [ -z "$(SHP)" ]; then \
		echo "Usage: make load-custom SHP=/path/to/shapefile.shp [TABLE=mytable]"; \
		exit 1; \
	fi
	@./venv/bin/python scripts/load_shapefile.py --shp "$(SHP)" $(if $(TABLE),--table $(TABLE)) --infer-commune

# Query execution
query:
	@if [ ! -f ".env" ]; then \
		echo "Error: .env file not found. Run: cp .env.example .env"; \
		exit 1; \
	fi
	@echo "Executing spatial queries..."
	@./venv/bin/python scripts/query_examples.py --stats --export

query-commune:
	@if [ -z "$(COMMUNE)" ]; then \
		echo "Usage: make query-commune COMMUNE=\"Nom_Commune\""; \
		exit 1; \
	fi
	@./venv/bin/python scripts/query_examples.py --commune "$(COMMUNE)" --stats --export

# Database access
psql:
	@docker compose exec db psql -U postgres -d gis

psql-exec:
	@if [ -z "$(SQL)" ]; then \
		echo "Usage: make psql-exec SQL=\"SELECT COUNT(*) FROM parcelles;\""; \
		exit 1; \
	fi
	@docker compose exec -T db psql -U postgres -d gis -c "$(SQL)"

# Reset and clean
reset: down-volumes up init-db
	@echo "✓ Environment reset complete"

clean:
	@echo "Cleaning up..."
	@rm -rf venv
	@rm -rf data/outputs/*
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "✓ Cleanup complete"

clean-all: clean down-volumes
	@echo "✓ Full cleanup complete"

# Development helpers
test-connection:
	@echo "Testing database connection..."
	@./venv/bin/python -c "from scripts.db_utils import execute_query; execute_query('SELECT version();', fetch=True) and print('✓ Connection successful')"

list-tables:
	@docker compose exec -T db psql -U postgres -d gis -c "\dt"

describe-table:
	@if [ -z "$(TABLE)" ]; then \
		echo "Usage: make describe-table TABLE=parcelles"; \
		exit 1; \
	fi
	@docker compose exec -T db psql -U postgres -d gis -c "\d $(TABLE)"

table-stats:
	@docker compose exec -T db psql -U postgres -d gis -c "SELECT table_name, pg_size_pretty(pg_total_relation_size(table_name::regclass)) as size FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';"

# Installation check
check-deps:
	@echo "Checking system dependencies..."
	@which python3 >/dev/null 2>&1 && echo "✓ Python3 found" || echo "✗ Python3 not found"
	@which docker >/dev/null 2>&1 && echo "✓ Docker found" || echo "✗ Docker not found"
	@which docker-compose >/dev/null 2>&1 || which docker compose >/dev/null 2>&1 && echo "✓ Docker Compose found" || echo "✗ Docker Compose not found"
	@which gdal-config >/dev/null 2>&1 && echo "✓ GDAL found" || echo "⚠ GDAL not found (may be needed for some operations)"