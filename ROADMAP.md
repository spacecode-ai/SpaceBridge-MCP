# SpaceBridge-MCP Roadmap

This document outlines the planned development stages for the SpaceBridge-MCP server.

## Phase 1: Core Functionality (MVP)

*   **[X] Project Setup:** Initialize project structure, README, ROADMAP, basic configuration handling.
*   **[ ] Dependencies:** Define initial dependencies in `requirements.txt` (e.g., `mcp-sdk`, `requests`, potentially an LLM client library).
*   **[ ] Configuration:** Implement loading of SpaceBridge API key/endpoint and LLM configuration (e.g., from environment variables).
*   **[ ] SpaceBridge Client:** Create a basic Python client/wrapper for interacting with the required SpaceBridge REST API endpoints (`/search`, `/issues/{id}`, `/issues`).
*   **[ ] MCP Server Boilerplate:** Set up the basic MCP server structure using `mcp-sdk`.
*   **[ ] Resource `get_issue_by_id`:**
    *   Define input schema (issue ID).
    *   Implement logic to call the SpaceBridge client (`/issues/{id}`).
    *   Define output schema (issue details).
    *   Register the resource with the MCP server.
*   **[ ] Tool `search_issues`:**
    *   Define input schema (query string, search type: `full_text` or `similarity`).
    *   Implement logic to call the SpaceBridge client (`/search`).
    *   Define output schema (list of matching issues).
    *   Register the tool with the MCP server.
*   **[ ] Tool `create_issue` (Initial Implementation):**
    *   Define input schema (title, description).
    *   Implement similarity search via SpaceBridge client.
    *   **Placeholder:** Skip LLM comparison for now.
    *   Implement issue creation via SpaceBridge client (`/issues`).
    *   Define output schema (new or existing issue ID).
    *   Register the tool with the MCP server.
*   **[ ] Basic Testing:** Add initial unit tests for core components (SpaceBridge client, tools/resources logic).
*   **[ ] Documentation:** Update README with detailed setup and usage instructions.

## Phase 2: Enhancements & Refinements

*   **[ ] LLM Integration for `create_issue`:**
    *   Integrate with the configured LLM.
    *   Implement the comparison logic between the new issue and potential duplicates found via similarity search.
    *   Refine the decision logic (thresholds, criteria) for identifying duplicates.
*   **[ ] Error Handling:** Improve error handling and reporting for API calls and internal logic. Provide informative error messages via MCP.
*   **[ ] Logging:** Implement structured logging throughout the server.
*   **[X] Git Context Integration:** Automatically detect Git organization/project name from `.git/config` and pass it to relevant SpaceBridge API calls (`search_issues`, `create_issue`).
*   **[ ] Advanced Configuration:**
    *   Support configuration via a file (e.g., YAML or TOML) in addition to environment variables.
    *   Support configuration via `.env` file.
*   **[ ] Enhanced Context:** Explore adding more context to API calls (e.g., current Git branch name).
*   **[ ] More Tools/Resources:**
    *   `update_issue` tool.
    *   Resource for listing available projects/repositories in SpaceBridge.
    *   Prompts for common issue management tasks.
*   **[ ] Comprehensive Testing:** Expand test coverage (integration tests, edge cases).
*   **[ ] Packaging:** Create `setup.py` or `pyproject.toml` for easier distribution/installation if needed.

## Phase 3: Production Readiness & Future Features

*   **[ ] Security Hardening:** Review security aspects (API key handling, input validation).
*   **[ ] Performance Optimization:** Profile and optimize critical code paths if necessary.
*   **[ ] Deployment:** Provide guidance or scripts for deploying the server (e.g., Dockerfile).
*   **[ ] Asynchronous Operations:** Consider using `asyncio` for improved concurrency if handling many simultaneous requests becomes a requirement (depends on `mcp-sdk` support).
*   **[ ] Extensibility:** Design for easier addition of new tools, resources, or integrations.

*(This roadmap is subject to change based on development progress and evolving requirements.)*