.DEFAULT_GOAL := help

COMPOSE ?= docker compose
API ?= http://localhost:5000/api
PLANTILLA ?= backend/plantilla_liga.xlsx

.PHONY: help demo init-env up esperar status logs logs-back logs-front logs-db shell-back shell-db plantilla import seed api open stop restart reset

help: ## Muestra los comandos disponibles
	@echo "ArbiLiga - comandos de desarrollo"
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  make %-14s %s\n", $$1, $$2}'

demo: up seed open ## Arranca todo, carga datos si no existen y abre la aplicación

init-env: ## Crea .env desde .env.example si todavía no existe
	@test -f .env || cp .env.example .env

up: init-env ## Construye y levanta los servicios, esperando a que estén listos
	$(COMPOSE) up --build -d
	$(MAKE) esperar

esperar: ## Espera a que base de datos y API estén disponibles
	@i=0; until $(COMPOSE) ps db | grep -q 'healthy'; do i=$$((i+1)); test $$i -lt 46 || (echo "La base de datos no quedó saludable." && exit 1); sleep 2; done
	@i=0; until curl -fsS $(API)/health >/dev/null; do i=$$((i+1)); test $$i -lt 46 || (echo "La API no respondió a tiempo." && exit 1); sleep 2; done
	@echo "Servicios listos."

status: ## Muestra el estado de los contenedores
	$(COMPOSE) ps

logs: ## Muestra los logs de todos los servicios
	$(COMPOSE) logs -f

logs-back: ## Muestra los logs del backend
	$(COMPOSE) logs -f backend

logs-front: ## Muestra los logs del frontend
	$(COMPOSE) logs -f frontend

logs-db: ## Muestra los logs de MariaDB
	$(COMPOSE) logs -f db

shell-back: ## Abre una terminal dentro del backend
	$(COMPOSE) exec backend sh

shell-db: ## Abre el cliente MariaDB dentro de la base de datos
	$(COMPOSE) exec db mariadb -u$${DB_USER:-liga_user} -p$${DB_PASSWORD:-cambia_esta_password} $${DB_NAME:-liga_arbitros_db}

plantilla: ## Genera backend/plantilla_liga.xlsx
	$(COMPOSE) exec -T backend python scripts/generar_plantilla.py /app/plantilla_liga.xlsx

import: plantilla ## Importa la plantilla a través de la API
	curl -fsS -X POST -F "file=@$(PLANTILLA)" $(API)/upload-excel
	@echo

seed: ## Carga la plantilla solo cuando todavía no hay partidos
	@total=$$(curl -fsS $(API)/partidos | grep -o '"id"' | wc -l); if [ "$$total" -eq 0 ]; then $(MAKE) import; else echo "Ya existen $$total partido(s); se omite la importación para evitar duplicados."; fi

api: ## Comprueba salud y muestra los partidos registrados
	curl -fsS $(API)/health
	@echo
	curl -fsS $(API)/partidos
	@echo

open: ## Abre el frontend en el navegador (Windows, macOS o Linux)
	@{ command -v xdg-open >/dev/null && xdg-open http://localhost:5173; } || { command -v open >/dev/null && open http://localhost:5173; } || { command -v cmd.exe >/dev/null && cmd.exe /c start http://localhost:5173; } || true

stop: ## Detiene los servicios sin borrar los datos
	$(COMPOSE) down

restart: stop up ## Reinicia los servicios sin borrar los datos

reset: ## Borra todos los datos y vuelve a levantar la aplicación
	@printf "Esto borrará la base de datos local. ¿Continuar? [s/N] "; read respuesta; test "$$respuesta" = "s" -o "$$respuesta" = "S"
	$(COMPOSE) down -v
	$(MAKE) demo
