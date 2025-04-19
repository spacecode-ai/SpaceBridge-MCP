# Plan: Enhance SpaceBridge-MCP Context Handling

This plan outlines the steps to improve how the SpaceBridge-MCP server handles organization and project context, addressing issues where automatic detection fails (e.g., in Windsurf/Cursor) while prioritizing context determined at server startup.

## Goals

1.  Provide explicit configuration options (command-line args, environment variables) for setting organization and project context.
2.  Allow context to be optionally provided via tool parameters as a fallback.
3.  Ensure context determined at server startup (via explicit config or Git detection) always takes precedence over context provided in tool calls.

## Implementation Steps

```mermaid
graph TD
    A[Start] --> B(Implement Explicit Config in server.py - Determine & Store Startup Context);
    B --> C(Modify Tool Schemas in tools.py - Add Optional org/project);
    C --> D(Modify Tool Handlers in server.py - Accept Optional Params & Implement Priority Logic);
    D --> E(Modify SpaceBridgeClient Methods - Accept Explicit org/project Args);
    E --> F(Update README.md - Document Both Approaches & Final Priority);
    F --> G(Add/Update Tests in test_server.py & test_client.py);
    G --> H[End];

    subgraph Determine Startup Context (Suggestion 1)
        B
    end
    subgraph Add Optional Params (Suggestion 2)
        C
        D
        E
    end
    subgraph Documentation & Testing
        F
        G
    end

    style B fill:#ccf,stroke:#333,stroke-width:2px
    style C fill:#f9f,stroke:#333,stroke-width:2px
    style D fill:#f9f,stroke:#333,stroke-width:2px
    style E fill:#f9f,stroke:#333,stroke-width:2px
    style F fill:#cfc,stroke:#333,stroke-width:2px
    style G fill:#cfc,stroke:#333,stroke-width:2px
```

**Detailed Steps:**

1.  **Implement Explicit Configuration (`src/spacebridge_mcp/server.py`):**
    *   Add command-line arguments (`--org-name`, `--project-name`) using `argparse`.
    *   Define corresponding environment variables (`SPACEBRIDGE_ORG_NAME`, `SPACEBRIDGE_PROJECT_NAME`).
    *   In `main_sync`, determine `startup_org_name` and `startup_project_name` based on the following precedence:
        1.  `--org-name` / `--project-name` command-line arguments.
        2.  `SPACEBRIDGE_ORG_NAME` / `SPACEBRIDGE_PROJECT_NAME` environment variables.
        3.  Git detection using `--project-dir` argument.
        4.  Git detection using current working directory (CWD).
    *   Initialize the `spacebridge_client` instance with this determined `startup_org_name` and `startup_project_name`.

2.  **Modify Tool Schemas (`src/spacebridge_mcp/tools.py`):**
    *   Add optional fields `org_name: Optional[str] = None` and `project_name: Optional[str] = None` to the input Pydantic models:
        *   `SearchIssuesInput`
        *   `CreateIssueInput`
        *   `UpdateIssueInput`
    *   Update field descriptions to indicate they are optional overrides if server context is unavailable.

3.  **Modify Tool Handlers (`src/spacebridge_mcp/server.py`):**
    *   Update the signatures of `search_issues_handler`, `create_issue_handler`, and `update_issue_handler` to accept the new optional `org_name` and `project_name` parameters from the tool call.
    *   Inside each handler, implement logic to determine the `final_org_name` and `final_project_name` to be used for the API call:
        *   **Priority 1:** Use `spacebridge_client.org_name` (the context determined at startup) if it exists.
        *   **Priority 2 (Fallback):** If startup context (`spacebridge_client.org_name`) is `None`, use the `org_name` provided in the tool call parameters (if provided).
        *   **Priority 3 (Fallback):** If neither startup context nor tool parameter is available, use `None`.
        *   Repeat the same logic for `project_name`.
    *   Pass this `final_org_name` and `final_project_name` explicitly when calling the corresponding `spacebridge_client` methods.

4.  **Modify SpaceBridgeClient Methods (`src/spacebridge_mcp/spacebridge_client.py`):**
    *   Update the method signatures for `search_issues`, `create_issue`, and `update_issue` to accept optional `org_name: Optional[str] = None` and `project_name: Optional[str] = None` arguments.
    *   Modify the internal logic of these methods to use the `org_name` and `project_name` arguments passed from the handlers when constructing API request parameters or payloads. (The priority is already handled by the handler logic).

5.  **Update Documentation (`README.md`):**
    *   Clearly document the new explicit configuration options (`--org-name`, `--project-name`, `SPACEBRIDGE_ORG_NAME`, `SPACEBRIDGE_PROJECT_NAME`) and the full precedence order for determining startup context.
    *   Document the optional tool parameters (`org_name`, `project_name`).
    *   Explain the final context priority: Startup context is always preferred; tool parameters serve only as a fallback when startup context could not be determined.
    *   Update client connection examples (e.g., `claude mcp add`) to show how to pass the new environment variables.

6.  **Add/Update Tests (`tests/test_server.py`, `tests/test_client.py`):**
    *   Add tests to verify the configuration precedence logic in `server.py`.
    *   Add tests for the handler logic, ensuring startup context is prioritized over tool parameters.
    *   Add tests for the client methods to confirm they correctly use the context arguments passed from the handlers.
    *   Test scenarios with and without explicit config, with and without Git detection, and with/without tool parameters provided.