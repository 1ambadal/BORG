.PHONY: setup run test clean help

# Variables
PYTHON = venv/bin/python
PIP = venv/bin/pip

help:
	@echo "Available commands:"
	@echo "  make setup   - Set up the environment and dependencies"
	@echo "  make run     - Run the application"
	@echo "  make test    - Run tests"
	@echo "  make clean   - Remove virtual environment and temporary files"

setup:
	@echo "🚀 Starting automated setup..."
	python3 setup.py

token:
	@echo "🔑 Generating Google OAuth token..."
	$(PYTHON) scripts/generate_token.py

run:
	@echo "🚀 Starting the application..."
	$(PYTHON) main.py

test:
	@echo "🧪 Running tests..."
	$(PYTHON) -m pytest

clean:
	@echo "🧹 Cleaning up..."
	rm -rf venv
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	@echo "✅ Cleaned."
