#Iniciar la demo completa (levanta contenedores y genera la plantilla)
demo:
    docker compose up --build -d
    docker compose exec -T backend python scripts/generar_plantilla.py /app/plantilla_liga.xlsx
    @echo "Demo lista en http://localhost:5173/"

#Ver el estado de los contenedores
status:
    docker compose ps

#Ver logs del backend en tiempo real
logs-back:
    docker compose logs -f backend

#Detener los servicios sin borrar datos
stop:
    docker compose down

#Reiniciar desde cero (borra base de datos y reconstruye)
clean:
    docker compose down -v
    docker compose up --build -d