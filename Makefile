include .env
export

NETWORK_NAME := dev-network
VOLUME_NAMES := \
	uv-cache \
	claude-config

DEV_SERVICES := \
	dev
OWNER ?= $(USER_NAME):$(USER_NAME)
CHOWN_PATHS := \
	/opt/venv \
	/home/$(USER_NAME)/.local \
	/home/$(USER_NAME)/.cache

GHCR_OWNER ?= t-hoshino215
TAG ?= latest
DEPLOY_IMAGES := \
	BACKEND_IMAGE=ghcr.io/$(GHCR_OWNER)/web-practice-backend:$(TAG) \
	FRONTEND_IMAGE=ghcr.io/$(GHCR_OWNER)/web-practice-frontend:$(TAG)

.PHONY: setup setup-network setup-volumes chowns up-dev down-dev exec-dev up build-front deploy

# Create the Docker network + volumes and the mounted directory
setup-network:
	@docker network inspect $(NETWORK_NAME) >/dev/null 2>&1 \
		|| docker network create --driver bridge $(NETWORK_NAME)

setup-volumes:
	@for volume in $(VOLUME_NAMES); do \
		docker volume inspect "$$volume" >/dev/null 2>&1 \
			|| docker volume create "$$volume"; \
	done

setup:
	$(MAKE) setup-network
	$(MAKE) setup-volumes

chowns:
	@for service in $(DEV_SERVICES); do \
		if docker compose ps --status running --services $$service | grep -Fxq $$service; then \
			echo "Changing ownership of paths in $$service..."; \
			docker compose exec -T --user root $$service sh -c '\
				echo "Host name: $$(hostname)"; \
				for path in $(CHOWN_PATHS); do \
					if [ -e "$$path" ]; then \
						echo "Target: $$path"; \
						chown -R $(OWNER) "$$path"; \
					fi; \
				done; \
			'; \
		fi; \
	done

# Run the Docker Compose setup and start the containers
up-dev:
	$(MAKE) setup
	docker compose --env-file .env --env-file ./backend/.env --profile dev up -d --build dev
	$(MAKE) chowns

# Stop and remove the containers
down-dev:
	docker compose down dev

# Run a command in the dev container
exec-dev:
	docker compose --env-file .env --env-file ./backend/.env exec dev zsh

up:
	docker compose --env-file ./backend/.env up -d --build

# フロントエンドをビルドし直してCaddyへ反映する
build-front:
	docker compose --env-file ./backend/.env build caddy
	docker compose --env-file ./backend/.env up -d caddy

# Deploy services using the specified GHCR images
deploy:
	$(DEPLOY_IMAGES) docker compose --env-file ./backend/.env pull backend caddy
	$(DEPLOY_IMAGES) docker compose --env-file ./backend/.env up -d backend caddy
	docker compose --env-file ./backend/.env ps