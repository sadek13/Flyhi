.PHONY: validate train actions shell api web test-unit test-nlu test-core test-all compile docker

validate:
	rasa data validate

train:
	rasa train

actions:
	set -a; . ./.env; set +a; rasa run actions

shell:
	set -a; . ./.env; set +a; rasa shell

api:
	set -a; . ./.env; set +a; rasa run --enable-api --cors "*" --port 5005

web:
	python -m http.server 8080 --directory web

compile:
	python -m py_compile actions/*.py

test-unit:
	pytest -q tests/test_validators.py tests/test_ranking.py tests/test_services.py

test-nlu:
	rasa test nlu --nlu tests/nlu_test.yml

test-core:
	rasa test core --stories tests/test_stories.yml

test-all: validate test-unit test-nlu test-core

docker:
	docker compose up --build
