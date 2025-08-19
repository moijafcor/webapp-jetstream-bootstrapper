.PHONY: test test-unit test-integration test-security test-cov clean lint help install-dev

# Default target
help:
	@echo "Available targets:"
	@echo "  install-dev    Install development dependencies"
	@echo "  test          Run all tests"
	@echo "  test-unit     Run unit tests only"
	@echo "  test-security Run security tests only"
	@echo "  test-cov      Run tests with coverage report"
	@echo "  lint          Run code linting"
	@echo "  clean         Clean up generated files"

install-dev:
	pip install -r requirements-dev.txt

test:
	python -m pytest test_setup_laravel_jetstream.py -v

test-unit:
	python -m pytest test_setup_laravel_jetstream.py -v -m "unit"

test-security:
	python -m pytest test_setup_laravel_jetstream.py -v -m "security"

test-cov:
	python -m pytest test_setup_laravel_jetstream.py -v --cov=setup_laravel_jetstream_sudo --cov-report=term-missing --cov-report=html

lint:
	python -m flake8 setup_laravel_jetstream_sudo.py test_setup_laravel_jetstream.py --max-line-length=120
	python -m bandit -r setup_laravel_jetstream_sudo.py
	python -m safety check

clean:
	rm -rf __pycache__ .pytest_cache .coverage htmlcov/ *.pyc
	find . -type d -name "__pycache__" -delete
	find . -type f -name "*.pyc" -delete