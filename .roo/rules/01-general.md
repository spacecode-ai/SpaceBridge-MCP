## Commands
- Activate virtual environment: `source .venv/bin/activate`
- Install: `pip install -e ".[dev]"`
- Run server: `spacebridge-mcp-server`
- Run tests: `python -m pytest -vvv`
- Run single test: `python -m pytest -vvv tests/test_file.py::test_function`
- Run live API tests: `RUN_LIVE_API_TESTS=1 python -m pytest -vvv`


## Commit message Guidelines

- All commit messages should include references to relevant issues in the tracker with the word "Fixes" if the commit addresses the issue completely. Use the SpaceBridge-MCP tools to find or create issues for every change. Include the issue ID's in the commit message footer. Ensure issue title and description are clear and concise, always in present tense.
