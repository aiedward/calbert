deps: pyproject.toml
	poetry install

docker: 
	cp pyproject.toml docker
	cp poetry.lock docker
	docker build -t codegram/calbert ./docker

docker-push:
	docker push codegram/calbert:latest

test:
	poetry run py.test tests

lint:
	poetry run flake8 calbert/*.py tests/*.py

clean:
	rm -fr run calbert/__pycache__

.PHONY: test cast lint clean docker docker-push
