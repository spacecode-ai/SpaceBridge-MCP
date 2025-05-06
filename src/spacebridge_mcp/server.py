# src/spacebridge_mcp/server.py
"""
Main entry point for the SpaceBridge MCP Server.
Initializes components and starts the server.
"""

import os
import logging
import configparser
import re
import argparse  # Added for command-line arguments
import openai  # Added for LLM integration
from dotenv import load_dotenv  # Added for .env support
from packaging.version import parse as parse_version  # Added for version comparison
import importlib.metadata  # Added to get own version
from mcp.server.fastmcp.server import FastMCP  # Use FastMCP
# Removed ResourceProvider and get_tools imports

from .spacebridge_client import SpaceBridgeClient
from .duplicate_detection import DuplicateDetectorFactory

# Import Pydantic models for tool function signatures
from .tools import (
    SearchIssuesOutput,
    CreateIssueOutput,
    UpdateIssueOutput,  # Added update schemas
    IssueSummary,  # Needed for create_issue logic
)
from typing import (
    List,
    Dict,
    Any,
    Literal,
    Optional,
)  # Add Dict, Any, Literal, Optional for type hints

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --- Configuration Loading ---
# Configuration will be loaded in main_sync using argparse, environment variables, and .env file.
# Precedence: Command-line args > Environment variables > .env file


def get_config_value(args, env_var_name: str) -> str | None:
    """
    Gets a configuration value based on precedence: command-line args, environment variables, .env file.
    Assumes load_dotenv() has been called.
    """
    # Command-line argument (convert env var name to arg name, e.g., SPACEBRIDGE_API_URL -> spacebridge_api_url)
    arg_name = env_var_name.lower()
    value = getattr(args, arg_name, None)
    if value:
        logger.debug(f"Using value from command-line argument for {env_var_name}")
        return value

    # Environment variable (which might have been loaded from .env)
    value = os.getenv(env_var_name)
    if value:
        logger.debug(
            f"Using value from environment variable (or .env) for {env_var_name}"
        )
        return value

    logger.debug(f"No value found for {env_var_name}")
    return None


# Module-level client instances are removed. They will be initialized in main_sync.
spacebridge_client = None
openai_client = None


# --- Git Configuration Extraction ---


def get_git_info(git_config_path=".git/config") -> tuple[str | None, str | None]:
    """
    Reads the .git/config file and extracts organization and project name
    from the remote 'origin' URL.

    Returns:
        A tuple (org_name, project_name), or (None, None) if not found or error.
    """
    org_name = None
    project_name = None
    try:
        if not os.path.exists(git_config_path):
            logger.warning(f"Git config file not found at: {git_config_path}")
            return None, None

        config = configparser.ConfigParser()
        config.read(git_config_path)

        remote_origin_url = config.get('remote "origin"', "url", fallback=None)

        if remote_origin_url:
            # Try to match common Git URL patterns (SSH and HTTPS)
            # Example SSH: git@github.com:org/repo.git
            # Example HTTPS: https://github.com/org/repo.git
            match = re.search(r"(?:[:/])([^/]+)/([^/]+?)(?:\.git)?$", remote_origin_url)
            if match:
                org_name = match.group(1)
                project_name = match.group(2)
                logger.info(
                    f"Extracted Git info: Org='{org_name}', Project='{project_name}'"
                )
            else:
                logger.warning(
                    f"Could not parse org/project from remote URL: {remote_origin_url}"
                )
        else:
            logger.warning("Remote 'origin' URL not found in git config.")

    except configparser.Error as e:
        logger.error(f"Error parsing git config file '{git_config_path}': {e}")
    except Exception as e:
        logger.error(f"Unexpected error reading git config: {e}", exc_info=True)

    return org_name, project_name


# Git info will be determined within main_sync based on configuration precedence.


# --- Create FastMCP App ---
# TODO: Update name/version/description as needed
app = FastMCP(
    name="spacebridge-issue-manager",
    # version="0.3.0-fastmcp", # Version can be set here or inferred
    description="MCP Server for interacting with SpaceBridge issue tracking via FastMCP.",
    # Pass settings directly if needed, e.g., log_level="DEBUG"
)

# --- Define Tool Handlers ---


# TODO: Change this back to an MCP resource handler when there is wider client support for MCP resources.
@app.tool(
    name="get_issue",
    description="Retrieves a specific issue by key, id or external id from SpaceBridge. Define project slug only if not part of issue key.",
)
async def get_issue_tool_handler(
    issue: str, org_name: Optional[str] = None, project: Optional[str] = None
) -> Dict[str, Any]:
    """
    Handles requests for retrieving a specific issue by its ID/key from SpaceBridge.
    """
    logger.info(f"Received tool request for get_issue: {issue}")
    try:
        # Use the globally initialized client
        # The client method might still use org_name/project_name for context if needed internally
        issue_data = spacebridge_client.get_issue(
            issue, org_name=org_name, project_name=project
        )

        # Return the raw issue data dictionary
        logger.info(f"Successfully retrieved issue data for {issue}")
        return issue_data
    except Exception as e:
        logger.error(f"Error processing tool request for {issue}: {e}", exc_info=True)
        raise


@app.tool(
    name="search_issues",
    description="Searches for issues in SpaceBridge. Always define project slug. Use similarity search for best results.",
)
async def search_issues_handler(
    query: str,
    search_type: Literal["full_text", "similarity"] = "similarity",
    org: Optional[str] = None,
    project: Optional[str] = None,
    status: Optional[str] = None,  # Added filter
    labels: Optional[str] = None,  # Added filter (comma-separated string)
    assignee: Optional[str] = None,  # Added filter
    priority: Optional[str] = None,  # Added filter
) -> SearchIssuesOutput:
    """Implements the 'search_issues' tool using FastMCP."""
    logger.info(
        f"Executing tool 'search_issues' with query: '{query}', type: {search_type}, "
        f"org: {org}, project: {project}, status: {status}, labels: {labels}, "
        f"assignee: {assignee}, priority: {priority}"
    )
    try:
        # Determine final context (Startup context takes priority)
        final_org = (
            spacebridge_client.org_name
            if spacebridge_client.org_name is not None
            else org
        )
        final_project = (
            spacebridge_client.project_name
            if spacebridge_client.project_name is not None
            else project
        )
        logger.debug(
            f"Search using context: Org='{final_org}', Project='{final_project}'"
        )

        # Use the globally initialized client, passing the determined context
        search_results_raw = spacebridge_client.search_issues(
            query=query,
            search_type=search_type,
            org_name=final_org,  # Pass final context
            project_name=final_project,  # Pass final context
            status=status,  # Pass filter
            labels=labels,  # Pass filter
            assignee=assignee,  # Pass filter
            priority=priority,  # Pass filter
        )

        # Format results into the output schema
        # Ensure the raw results match the IssueSummary model structure
        output_data = SearchIssuesOutput(
            results=[IssueSummary(**result) for result in search_results_raw]
        )

        logger.info("Tool 'search_issues' completed successfully.")
        return output_data

    except Exception as e:
        logger.error(f"Error executing tool 'search_issues': {e}", exc_info=True)
        # TODO: Raise specific FastMCP tool error?
        raise  # Let FastMCP handle the error reporting


@app.tool(
    name="create_issue",
    description="Creates a new issue in SpaceBridge, checking for duplicates. Always define project slug. Define org if known. Issue title and description should ALWAYS be in present tense.",
)
async def create_issue_handler(
    title: str,
    description: str,
    org: Optional[str] = None,
    project: Optional[str] = None,
    labels: Optional[List[str]] = None,
    assignee: Optional[str] = None,
    priority: Optional[str] = None,
    status: Optional[str] = None,
    similarity_search: Optional[bool] = True,
) -> CreateIssueOutput:
    """
    Implements the 'create_issue' tool using FastMCP.
    Includes modular duplicate detection.
    Uses tool parameters first, then startup context as fallback for org/project.
    """
    logger.info(
        f"Executing tool 'create_issue' for title: '{title}', "
        f"org: {org}, project: {project}, labels: {labels}"
    )
    try:
        # Determine final context (Tool arguments take priority)
        final_org = org or spacebridge_client.org_name
        final_project = project or spacebridge_client.project_name
        logger.debug(
            f"Create using context: Org='{final_org}', Project='{final_project}'"
        )

        combined_text = f"{title}\n\n{description}"
        output_data = None
        if similarity_search:
            # 1. Search for potential duplicates using final context
            logger.info(f"Searching for potential duplicates for: '{title}'")
            potential_duplicates: List[IssueSummary] = []
            search_failed = False
            try:
                potential_duplicates_raw = spacebridge_client.search_issues(
                    query=combined_text,
                    search_type="similarity",
                    org_name=final_org,
                    project_name=final_project,
                )
                # Ensure raw data is converted to IssueSummary objects
                potential_duplicates = [
                    IssueSummary(**dup)
                    for dup in potential_duplicates_raw
                    if isinstance(dup, dict)
                ]
                logger.info(f"Found {len(potential_duplicates)} potential duplicates.")
            except Exception as search_error:
                search_failed = True
                logger.warning(
                    f"Similarity search failed during duplicate check: {search_error}. "
                    f"Proceeding with creation without duplicate check."
                )
                # Continue without duplicate check if search fails

            # 2. Perform Duplicate Check using the appropriate strategy
            duplicate_decision = None
            # Only run detector if search didn't fail AND found potential duplicates
            if not search_failed and potential_duplicates:
                # Instantiate factory (pass openai_client if needed)
                # Assuming openai_client is available in this scope and imported
                factory = DuplicateDetectorFactory(client=openai_client)
                detector = factory.get_detector()
                try:
                    duplicate_decision = await detector.check_duplicates(
                        new_title=title,
                        new_description=description,
                        potential_duplicates=potential_duplicates,
                    )
                    logger.info(
                        f"Duplicate check decision: {duplicate_decision.status}"
                    )
                except Exception as detector_error:
                    logger.error(
                        f"Error during duplicate detection: {detector_error}",
                        exc_info=True,
                    )
                    # If detector fails, treat as undetermined to be safe and create issue
                    # Setting decision to None ensures creation block runs
                    duplicate_decision = None

            # 3. Create or return duplicate info based on decision
            output_data = None
            if duplicate_decision and duplicate_decision.status == "duplicate":
                dup_issue = duplicate_decision.duplicate_issue
                if dup_issue:
                    output_data = CreateIssueOutput(
                        issue_id=dup_issue.id,
                        status="existing_duplicate_found",
                        message=f"Duplicate detection determined this is a likely duplicate of issue {dup_issue.id}.",
                        url=dup_issue.url,
                    )
                    logger.info(
                        f"Tool 'create_issue' completed (found duplicate: {dup_issue.id})."
                    )
                else:
                    # This case indicates an internal logic error in the detector
                    logger.error(
                        "Duplicate status returned without duplicate issue details. Proceeding with creation."
                    )
                    # Fallback to creating a new issue by setting output_data back to None
                    output_data = None  # Force creation block to run

        # Create issue if:
        # - No potential duplicates were found initially
        # - Similarity search failed
        # - Duplicate detector failed
        # - Duplicate detector decided 'not_duplicate'
        # - Duplicate detector decided 'undetermined'
        # - Duplicate detector decided 'duplicate' but failed to provide details (handled above)
        if (
            output_data is None
        ):  # Checks if output_data wasn't set in the duplicate block
            action = (
                "Creating new issue"
                if not duplicate_decision
                else f"Creating new issue (detector status: {duplicate_decision.status})"
            )
            logger.info(f"{action}...")
            try:
                created_issue_data = spacebridge_client.create_issue(
                    title=title,
                    description=description,
                    org_name=final_org,
                    project_name=final_project,
                    labels=labels,
                )
                # Handle potential missing keys from API response defensively
                created_id = created_issue_data.get("id", "UNKNOWN")
                created_url = created_issue_data.get("url")
                output_data = CreateIssueOutput(
                    issue_id=created_id,
                    status="created",
                    message="Successfully created new issue.",
                    url=created_url,
                )
                logger.info(
                    f"Tool 'create_issue' completed (created new issue: {created_id})."
                )
            except Exception as create_error:
                logger.error(
                    f"Failed to create issue after duplicate check: {create_error}",
                    exc_info=True,
                )
                # Re-raising seems appropriate for FastMCP handler.
                raise create_error

        return output_data

    except Exception as e:
        # Log the error before re-raising to ensure it's captured
        logger.error(
            f"Unhandled error executing tool 'create_issue': {e}", exc_info=True
        )
        raise  # Let FastMCP handle the final error reporting


@app.tool(
    name="update_issue",
    description="Updates an existing issue in SpaceBridge. Always define project_name. Define org_name if known.",
)
async def update_issue_handler(
    issue: str,  # Issue key, ID, or external ID
    title: Optional[str] = None,
    description: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    assignee: Optional[str] = None,
    labels: Optional[List[str]] = None,
) -> UpdateIssueOutput:
    """
    Implements the 'update_issue' tool using FastMCP, aligning with the PUT /issues/issues/{issue} endpoint.
    Org/Project context is not needed for the update API call itself.
    """
    logger.info(f"Executing tool 'update_issue' for issue: {issue}")
    try:
        # Prepare the update payload based on provided arguments, aligning with IssueUpdate schema
        update_args = {
            "title": title,
            "description": description,
            "status": status,
            "priority": priority,
            "assignee": assignee,
            "labels": labels,
            # Add 'metadata' if needed in the future
        }
        # Filter out None values explicitly so only provided fields are sent
        update_payload = {k: v for k, v in update_args.items() if v is not None}

        if not update_payload:
            logger.warning(f"Update issue called for {issue} with no fields to update.")
            return UpdateIssueOutput(
                issue_id=issue,  # Use the input identifier
                status="failed",
                message="No fields provided to update.",
                url=None,
            )

        logger.debug(f"Update payload for issue {issue}: {update_payload}")

        # Use the globally initialized client
        # The client method should only require the issue identifier and the payload
        updated_issue_data = spacebridge_client.update_issue(
            issue=issue,  # Pass the issue identifier (ID or key)
            **update_payload,  # Pass filtered fields as keyword arguments
        )

        # Assuming the client returns the updated issue data including URL and ID
        returned_id = updated_issue_data.get(
            "id", issue
        )  # Prefer returned ID, fallback to input
        output_data = UpdateIssueOutput(
            issue_id=returned_id,
            status="updated",
            message=f"Successfully updated issue {issue}.",  # Log original identifier used
            url=updated_issue_data.get("url"),
        )
        logger.info(f"Tool 'update_issue' completed successfully for {issue}.")
        return output_data

    except Exception as e:
        logger.error(
            f"Error executing tool 'update_issue' for {issue}: {e}", exc_info=True
        )
        # Return a failed output
        return UpdateIssueOutput(
            issue_id=issue,  # Use the input identifier
            status="failed",
            message=f"An error occurred while updating issue {issue}: {e}",
            url=None,
        )
        # Or re-raise if FastMCP should handle it:
        # raise


# --- Main execution logic moved to main_sync ---
# The async main function is no longer needed with FastMCP's run method


def main_sync():
    """Parses arguments, loads config, initializes clients, performs version check, and runs the FastMCP server."""

    # 1. Load .env file first (if it exists) - values can be overridden by env vars or args
    dotenv_path = os.path.join(os.getcwd(), ".env")
    if os.path.exists(dotenv_path):
        logger.info(f"Loading environment variables from: {dotenv_path}")
        load_dotenv(
            dotenv_path=dotenv_path, override=False
        )  # override=False ensures env vars take precedence over .env
    else:
        logger.info(
            ".env file not found, relying on environment variables and command-line arguments."
        )

    # 2. Set up argument parser
    parser = argparse.ArgumentParser(description="Run the SpaceBridge MCP Server.")
    parser.add_argument(
        "--spacebridge-api-url",
        help="SpaceBridge API base URL (overrides SPACEBRIDGE_API_URL env var and .env)",
    )
    parser.add_argument(
        "--spacebridge-api-key",
        help="SpaceBridge API key (overrides SPACEBRIDGE_API_KEY env var and .env)",
    )
    parser.add_argument(
        "--openai-api-key",
        help="OpenAI API key (overrides OPENAI_API_KEY env var and .env)",
    )
    parser.add_argument(
        "--project-dir",
        help="Project directory path to find the git config (defaults to current working directory)",
    )
    parser.add_argument(
        "--org-name",
        help="Explicitly set the organization name (overrides env var and Git detection)",
    )
    parser.add_argument(
        "--project-name",
        help="Explicitly set the project name (overrides env var and Git detection)",
    )
    # Add other arguments as needed (e.g., --log-level)

    args = parser.parse_args()

    # 3. Determine final configuration values using precedence
    # Note: get_config_value already implements Command-line > Environment variable precedence
    # Since load_dotenv(override=False) was used, Environment variable > .env file is also handled.
    final_api_url = get_config_value(args, "SPACEBRIDGE_API_URL")
    final_api_key = get_config_value(args, "SPACEBRIDGE_API_KEY")
    final_openai_key = get_config_value(args, "OPENAI_API_KEY")

    # 4. Validate required configuration
    missing_config = []

    if not final_api_key:
        # API Key IS required for startup.
        missing_config.append("SpaceBridge API Key")
    if not final_openai_key:
        # OpenAI Key IS required for startup (for duplicate detection).
        missing_config.append("OpenAI API Key")

    if missing_config:  # Check if the list contains required missing items.
        error_message = (
            f"Missing required configuration: {', '.join(missing_config)}. "
            "Please provide via command-line arguments, environment variables, or a .env file."
        )
        logger.error(error_message)
        print(f"Error: {error_message}")
        parser.print_help()  # Show help message on config error
        return  # Exit if config is missing

    # 5. Initialize clients using final configuration
    global spacebridge_client, openai_client  # Need globals as handlers access these
    try:
        # Determine startup org and project context based on precedence
        startup_org_name = None
        startup_project_name = None

        # 1. Command-line arguments
        if getattr(args, "org_name", None):
            startup_org_name = args.org_name
            logger.info(
                f"Using organization name from command-line argument: {startup_org_name}"
            )
        if getattr(args, "project_name", None):
            startup_project_name = args.project_name
            logger.info(
                f"Using project name from command-line argument: {startup_project_name}"
            )

        # 2. Environment variables (only if not set by args)
        if startup_org_name is None:
            env_org = os.getenv("SPACEBRIDGE_ORG_NAME")
            if env_org:
                startup_org_name = env_org
                logger.info(
                    f"Using organization name from SPACEBRIDGE_ORG_NAME env var: {startup_org_name}"
                )
        if startup_project_name is None:
            env_project = os.getenv("SPACEBRIDGE_PROJECT_NAME")
            if env_project:
                startup_project_name = env_project
                logger.info(
                    f"Using project name from SPACEBRIDGE_PROJECT_NAME env var: {startup_project_name}"
                )

        # 3. Git detection (--project-dir or CWD) (only if not set by args or env vars)
        if startup_org_name is None or startup_project_name is None:
            project_dir_arg = getattr(args, "project_dir", None)
            git_config_dir = project_dir_arg or os.getcwd()
            git_config_path = os.path.join(git_config_dir, ".git/config")
            logger.info(f"Attempting Git context detection from: {git_config_path}")
            detected_org, detected_project = get_git_info(git_config_path)

            if startup_org_name is None and detected_org:
                startup_org_name = detected_org
                logger.info(
                    f"Using organization name from Git detection: {startup_org_name}"
                )
            if startup_project_name is None and detected_project:
                startup_project_name = detected_project
                logger.info(
                    f"Using project name from Git detection: {startup_project_name}"
                )

        # Log final determined context
        logger.info(
            f"Final startup context: Org='{startup_org_name}', Project='{startup_project_name}'"
        )

        logger.info("Initializing SpaceBridgeClient...")
        spacebridge_client = SpaceBridgeClient(
            api_url=final_api_url,
            api_key=final_api_key,
            org_name=startup_org_name,  # Use determined startup context
            project_name=startup_project_name,  # Use determined startup context
        )
        logger.info("Initializing OpenAI Client...")
        # Prepare OpenAI client parameters
        openai_params = {"api_key": final_openai_key}
        openai_api_base = os.environ.get("OPENAI_API_BASE")
        if openai_api_base:
            logger.info(f"Using custom OpenAI API URL: {openai_api_base}")
            openai_params["base_url"] = openai_api_base

        openai_client = openai.AsyncOpenAI(**openai_params)
        logger.info("Clients initialized successfully.")

        # 5a. Perform version check after client initialization
        if not perform_version_check(spacebridge_client):
            return  # Exit if version check fails critically (e.g., client too old)

    except ValueError as e:
        logger.error(f"Client Initialization Error: {e}")
        print(f"Error: Client Initialization Error: {e}")
        return  # Exit if clients can't be initialized
    except Exception as e:
        logger.error(
            f"Unexpected error during client initialization: {e}", exc_info=True
        )
        print(f"Error: Unexpected error during client initialization: {e}")
        return

    # 6. Start the server
    logger.info(f"Starting FastMCP server (PID: {os.getpid()})...")
    try:
        # Run the FastMCP app
        app.run()  # Uses stdio transport by default
    except KeyboardInterrupt:
        logger.info("Server stopped manually.")
    except Exception as e:
        logger.error(
            f"An unexpected error occurred while running the server: {e}", exc_info=True
        )
    finally:
        logger.info("SpaceBridge MCP Server shut down.")


def perform_version_check(client: SpaceBridgeClient):
    """Checks client/server version compatibility."""
    try:
        # Get own version
        try:
            client_version_str = importlib.metadata.version("spacebridge-mcp")
        except importlib.metadata.PackageNotFoundError:
            logger.warning(
                "Could not determine client version using importlib.metadata. Falling back to hardcoded '0.0.0'."
            )
            client_version_str = "0.0.0"  # Fallback or read from a constant

        client_version = parse_version(client_version_str)
        logger.info(f"SpaceBridge-MCP Client Version: {client_version}")

        # Get server version info
        version_info = client.get_version(client_version=str(client_version))
        server_version_str = version_info.get("server_version")
        min_client_str = version_info.get("min_client_version")
        max_client_str = version_info.get("max_client_version")

        if not server_version_str:
            logger.warning("Could not retrieve server version from SpaceBridge API.")
            return  # Continue if server version is unknown

        server_version = parse_version(server_version_str)
        logger.info(f"SpaceBridge API Server Version: {server_version}")

        # Check minimum version requirement
        if min_client_str:
            min_client_version = parse_version(min_client_str)
            if client_version < min_client_version:
                error_msg = f"Client version {client_version} is older than the minimum required version {min_client_version} by the server. Please upgrade."
                logger.error(error_msg)
                print(f"ERROR: {error_msg}")
                return False  # Indicate startup should fail

        # Check maximum version recommendation
        if max_client_str:
            max_client_version = parse_version(max_client_str)
            if client_version < max_client_version:
                warning_msg = f"Client version {client_version} is older than the latest recommended version {max_client_version}. Consider upgrading for new features/fixes."
                logger.warning(warning_msg)
                print(f"WARNING: {warning_msg}")

    except Exception as e:
        logger.error(f"Failed to perform server version check: {e}", exc_info=True)
        # Decide whether to proceed or fail if version check fails
        # For now, let's proceed with a warning
        print(
            "WARNING: Failed to perform server version check against SpaceBridge API."
        )

    return True  # Indicate startup can proceed
