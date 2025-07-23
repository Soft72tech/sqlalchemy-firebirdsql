docker compose down -v firebird
docker compose up -d firebird
# source .venv/bin/activate
# pytest -vvv --dropfirst
docker compose run --rm tests
docker compose down -v firebird
