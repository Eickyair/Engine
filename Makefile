.PHONY: help build test up dev down restart logs ps shell health clean

IMAGE   ?= traffic-engine:local
COMPOSE ?= docker compose

help:
	@echo "traffic-engine — Docker shortcuts"
	@echo ""
	@echo "  make build     Build the API image (runs pytest as a stage)"
	@echo "  make test      Build only the test stage (no runtime image kept)"
	@echo "  make up        Start mongodb + api in background (production-like)"
	@echo "  make dev       Start with hot reload (mounts ./src, single worker)"
	@echo "  make down      Stop and remove containers (keeps mongo volume)"
	@echo "  make restart   Down + up --build"
	@echo "  make logs      Tail api logs"
	@echo "  make ps        Show container status"
	@echo "  make shell     Open a shell inside the api container"
	@echo "  make health    Hit /health on the running api"
	@echo "  make clean     down -v (also drops mongo volume) and prune dangling images"

build:
	docker build -t $(IMAGE) .

test:
	docker build --target test -t $(IMAGE)-test .

up:
	$(COMPOSE) up -d --build

dev:
	$(COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml up

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) down
	$(COMPOSE) up -d --build

logs:
	$(COMPOSE) logs -f api

ps:
	$(COMPOSE) ps

shell:
	$(COMPOSE) exec api sh

health:
	@curl -fsS http://127.0.0.1:8000/health && echo

clean:
	$(COMPOSE) down -v
	docker image prune -f
