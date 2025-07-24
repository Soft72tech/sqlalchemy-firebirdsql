docker compose down -v firebird
docker compose up -d firebird

# for local use
# source .venv/bin/activate
# pytest -vvv --dropfirst --last-failed --tb=short

docker compose run --rm tests
docker compose down -v firebird
