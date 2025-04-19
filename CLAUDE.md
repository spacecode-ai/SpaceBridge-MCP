# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands
- Install: `pip install -e ".[dev]"`
- Run server: `spacebridge-mcp-server`
- Run tests: `python -m pytest -vvv`
- Run single test: `python -m pytest -vvv tests/test_file.py::test_function`
- Run live API tests: `RUN_LIVE_API_TESTS=1 python -m pytest -vvv`

## Commit message Guidelines

- All commit messages should include references to relevant issues in the tracker. Use the SpaceBridge-MCP tools to find or create issues for every change. Include the issue ID's in the commit message footer. Ensure issue title and description are clear and concise, always in present tense.

## Style Guidelines
- PEP 8 compliant code
- Type hints on all functions and variables
- Use Pydantic models for structured data
- Imports order: standard lib, third-party, local (with blank lines between)
- snake_case for variables/functions, PascalCase for classes
- Comprehensive docstrings for public functions and classes
- Prefer explicit error handling with try/except
- Descriptive variable names that reflect purpose
- Comprehensive test coverage for all new features