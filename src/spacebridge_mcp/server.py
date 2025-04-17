# src/spacebridge_mcp/server.py
"""
Main entry point for the SpaceBridge MCP Server.
Initializes components and starts the server.
"""

import asyncio
import os
import logging
import configparser
import re
import argparse # Added for command-line arguments
import openai # Added for LLM integration
from dotenv import load_dotenv # Added for .env support
from packaging.version import parse as parse_version # Added for version comparison
import importlib.metadata # Added to get own version
from mcp.server.fastmcp.server import FastMCP # Use FastMCP
from mcp.server.fastmcp.resources import Resource # Import Resource for return type hint
# Removed ResourceProvider and get_tools imports

from .spacebridge_client import SpaceBridgeClient
# Import Pydantic models for tool function signatures
from .tools import (
    SearchIssuesInput, SearchIssuesOutput,
    CreateIssueInput, CreateIssueOutput,
    UpdateIssueInput, UpdateIssueOutput, # Added update schemas
    IssueSummary # Needed for create_issue logic
)
from typing import List, Dict, Any, Literal, Optional # Add Dict, Any, Literal, Optional for type hints

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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
        logger.debug(f"Using value from environment variable (or .env) for {env_var_name}")
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

       remote_origin_url = config.get('remote "origin"', 'url', fallback=None)

       if remote_origin_url:
           # Try to match common Git URL patterns (SSH and HTTPS)
           # Example SSH: git@github.com:org/repo.git
           # Example HTTPS: https://github.com/org/repo.git
           match = re.search(r'(?:[:/])([^/]+)/([^/]+?)(?:\.git)?$', remote_origin_url)
           if match:
               org_name = match.group(1)
               project_name = match.group(2)
               logger.info(f"Extracted Git info: Org='{org_name}', Project='{project_name}'")
           else:
               logger.warning(f"Could not parse org/project from remote URL: {remote_origin_url}")
       else:
           logger.warning("Remote 'origin' URL not found in git config.")

   except configparser.Error as e:
       logger.error(f"Error parsing git config file '{git_config_path}': {e}")
   except Exception as e:
       logger.error(f"Unexpected error reading git config: {e}", exc_info=True)

   return org_name, project_name

# Attempt to get git info at module level (might be useful for client init)
# Use current working directory's .git/config by default
git_org_name, git_project_name = get_git_info(os.path.join(os.getcwd(), ".git/config"))


# --- Create FastMCP App ---
# TODO: Update name/version/description as needed
app = FastMCP(
    name="spacebridge-issue-manager",
    # version="0.3.0-fastmcp", # Version can be set here or inferred
    description="MCP Server for interacting with SpaceBridge issue tracking via FastMCP.",
    # Pass settings directly if needed, e.g., log_level="DEBUG"
)

# --- Define Resource Handlers ---

@app.resource("spacebridge://api/v1/issues/{issue_id}")
async def get_issue_resource_handler(issue_id: str) -> Dict[str, Any]: # Return dict directly
    """
    Handles requests for the 'spacebridge://api/v1/issues/{issue_id}' resource.
    """
    logger.info(f"Received resource request for URI: spacebridge://api/v1/issues/{issue_id}")
    try:
        # Use the globally initialized client
        issue_data = spacebridge_client.get_issue(issue_id)

        # Return the raw issue data dictionary
        # FastMCP should handle wrapping this into the appropriate response
        logger.info(f"Successfully retrieved resource data for {issue_id}")
        return issue_data
    except Exception as e:
        logger.error(f"Error processing resource request for {issue_id}: {e}", exc_info=True)
        # TODO: Raise a specific FastMCP exception? For now, let FastMCP handle it.
        raise

# --- Define Tool Handlers ---

@app.tool(name="search_issues", description="Searches for issues in SpaceBridge using full-text or similarity search.")
async def search_issues_handler(
    query: str, 
    search_type: Literal["full_text", "similarity"] = "full_text"
) -> SearchIssuesOutput:
    """Implements the 'search_issues' tool using FastMCP."""
    logger.info(f"Executing tool 'search_issues' with query: '{query}', type: {search_type}")
    try:
        # Use the globally initialized client
        search_results_raw = spacebridge_client.search_issues(
            query=query,
            search_type=search_type
        )

        # Format results into the output schema
        # Ensure the raw results match the IssueSummary model structure
        output_data = SearchIssuesOutput(results=[
             IssueSummary(**result) for result in search_results_raw
        ])

        logger.info(f"Tool 'search_issues' completed successfully.")
        return output_data

    except Exception as e:
        logger.error(f"Error executing tool 'search_issues': {e}", exc_info=True)
        # TODO: Raise specific FastMCP tool error?
        raise # Let FastMCP handle the error reporting

@app.tool(name="create_issue", description="Creates a new issue in SpaceBridge, checking for potential duplicates first using similarity search and LLM comparison. Issue title and description should ALWAYS be in present tense.")
async def create_issue_handler(
    title: str,
    description: str
) -> CreateIssueOutput:
    """
    Implements the 'create_issue' tool using FastMCP.
    Includes duplicate detection via similarity search followed by LLM comparison.
    """
    logger.info(f"Executing tool 'create_issue' for title: '{title}'")
    try:
        combined_text = f"{title}\n\n{description}"

        # 1. Search for potential duplicates
        logger.info(f"Searching for potential duplicates for: '{title}'")
        potential_duplicates: List[IssueSummary] = []
        try:
            potential_duplicates_raw = spacebridge_client.search_issues(
                query=combined_text,
                search_type="similarity"
            )
            potential_duplicates = [IssueSummary(**dup) for dup in potential_duplicates_raw]
            logger.info(f"Found {len(potential_duplicates)} potential duplicates.")
        except Exception as search_error:
            logger.warning(f"Similarity search failed during duplicate check: {search_error}. Proceeding with creation.")
            # Continue without duplicate check if search fails

        # 2. LLM Comparison Step
        duplicate_found = False
        existing_issue_id = None
        existing_issue_url = None

        if potential_duplicates:
            top_n = 3
            duplicates_to_check = potential_duplicates[:top_n]
            duplicates_context = "\n\n".join([
                f"Existing Issue ID: {dup.id}\nTitle: {dup.title}\nDescription: {dup.description or 'N/A'}\nScore: {dup.score or 'N/A'}"
                for dup in duplicates_to_check
            ])

            prompt = f"""You are an expert issue tracker assistant. Your task is to determine if a new issue is a duplicate of existing issues.

New Issue Details:
Title: {title}
Description: {description}

Potential Existing Duplicates Found via Similarity Search:
---
{duplicates_context}
---

Based on the information above, is the 'New Issue' a likely duplicate of *any* of the 'Potential Existing Duplicates'?

Respond with ONLY one of the following:
1.  If it IS a duplicate: DUPLICATE: [ID of the existing issue, e.g., SB-123]
2.  If it is NOT a duplicate: NOT_DUPLICATE
"""
            logger.info(f"Sending comparison prompt to LLM for new issue '{title}'...")
            try:
                llm_response = await openai_client.chat.completions.create(
                    model="gpt-4o", # TODO: Make configurable
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    max_tokens=50
                )
                llm_decision_raw = llm_response.choices[0].message.content.strip()
                logger.info(f"LLM response received: '{llm_decision_raw}'")

                if llm_decision_raw.startswith("DUPLICATE:"):
                    parts = llm_decision_raw.split(":", 1)
                    if len(parts) == 2:
                        potential_id = parts[1].strip()
                        matched_dup = next((dup for dup in duplicates_to_check if dup.id == potential_id), None)
                        if matched_dup:
                            duplicate_found = True
                            existing_issue_id = matched_dup.id
                            existing_issue_url = matched_dup.url
                            logger.info(f"LLM identified duplicate: {existing_issue_id}")
                        else:
                            logger.warning(f"LLM reported duplicate ID '{potential_id}' but it wasn't in the top {top_n} checked.")
                    else:
                        logger.warning(f"LLM response started with DUPLICATE: but format was unexpected: {llm_decision_raw}")
                elif llm_decision_raw == "NOT_DUPLICATE":
                    logger.info("LLM confirmed not a duplicate.")
                else:
                     logger.warning(f"LLM response was not in the expected format: {llm_decision_raw}")

            except Exception as llm_error:
                logger.error(f"Error calling OpenAI API for duplicate check: {llm_error}", exc_info=True)
                # Proceed as if not a duplicate if LLM fails
                duplicate_found = False

        # 3. Create or return duplicate info
        if not duplicate_found:
            logger.info(f"No significant duplicate found or LLM check failed/skipped. Creating new issue...")
            created_issue_data = spacebridge_client.create_issue(
                title=title,
                description=description
            )
            output_data = CreateIssueOutput(
                issue_id=created_issue_data.get("id", "UNKNOWN"),
                status="created",
                message=f"Successfully created new issue.",
                url=created_issue_data.get("url")
            )
            logger.info(f"Tool 'create_issue' completed (created new issue).")
        else:
            output_data = CreateIssueOutput(
                issue_id=existing_issue_id,
                status="existing_duplicate_found",
                message=f"LLM determined this is a likely duplicate of issue {existing_issue_id}. No new issue created.",
                url=existing_issue_url
            )
            logger.info(f"Tool 'create_issue' completed (found duplicate).")

        return output_data

    except Exception as e:
        logger.error(f"Error executing tool 'create_issue': {e}", exc_info=True)
        # TODO: Raise specific FastMCP tool error?
        raise # Let FastMCP handle the error reporting

@app.tool(name="update_issue", description="Updates an existing issue in SpaceBridge.")
async def update_issue_handler(
    issue_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    status: Optional[str] = None
) -> UpdateIssueOutput:
    """Implements the 'update_issue' tool using FastMCP."""
    logger.info(f"Executing tool 'update_issue' for issue ID: {issue_id}")
    try:
        # Prepare arguments for the client method, excluding issue_id and None values
        update_args = {
            "title": title,
            "description": description,
            "status": status,
            # Add other fields if they exist
        }
        # Filter out None values explicitly, as client method handles this, but good practice here too
        update_payload = {k: v for k, v in update_args.items() if v is not None}

        if not update_payload:
             logger.warning(f"Update issue called for {issue_id} with no fields to update.")
             return UpdateIssueOutput(
                 issue_id=issue_id,
                 status="failed",
                 message="No fields provided to update.",
                 url=None # Or potentially fetch current URL if needed
             )

        # Use the globally initialized client
        updated_issue_data = spacebridge_client.update_issue(
            issue_id=issue_id,
            **update_payload # Pass filtered fields as keyword arguments
        )

        # Assuming the client returns the updated issue data including URL
        output_data = UpdateIssueOutput(
            issue_id=updated_issue_data.get("id", issue_id), # Use returned ID or original
            status="updated",
            message=f"Successfully updated issue {issue_id}.",
            url=updated_issue_data.get("url")
        )
        logger.info(f"Tool 'update_issue' completed successfully for {issue_id}.")
        return output_data

    except Exception as e:
        logger.error(f"Error executing tool 'update_issue' for {issue_id}: {e}", exc_info=True)
        # Return a failed output
        return UpdateIssueOutput(
            issue_id=issue_id,
            status="failed",
            message=f"An error occurred: {e}",
            url=None
        )
        # Or re-raise if FastMCP should handle it:
        # raise

# --- Main execution logic moved to main_sync ---
# The async main function is no longer needed with FastMCP's run method


if __name__ == "__main__":
    # Set environment variables for testing if needed:
    # os.environ['SPACEBRIDGE_API_URL'] = 'http://localhost:8000/api' # Example URL
    # os.environ['SPACEBRIDGE_API_KEY'] = 'your_dummy_api_key'

    # Check if required env vars are set before running (updated check)
    required_env_vars_check = ["SPACEBRIDGE_API_URL", "SPACEBRIDGE_API_KEY", "OPENAI_API_KEY"]
    missing_vars_check = [var for var in required_env_vars_check if var not in os.environ]

    if missing_vars_check:
        print(f"Error: Missing required environment variables: {', '.join(missing_vars_check)}. Please set them.")
        print("Example Linux/macOS: export VAR_NAME='...'")
        print("Example Windows (cmd): set VAR_NAME=...")
    else:
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            print("\nServer stopped manually.")

def main_sync():
    """Parses arguments, loads config, initializes clients, performs version check, and runs the FastMCP server."""

    # 1. Load .env file first (if it exists) - values can be overridden by env vars or args
    dotenv_path = os.path.join(os.getcwd(), '.env')
    if os.path.exists(dotenv_path):
        logger.info(f"Loading environment variables from: {dotenv_path}")
        load_dotenv(dotenv_path=dotenv_path, override=False) # override=False ensures env vars take precedence over .env
    else:
        logger.info(".env file not found, relying on environment variables and command-line arguments.")

    # 2. Set up argument parser
    parser = argparse.ArgumentParser(description="Run the SpaceBridge MCP Server.")
    parser.add_argument(
        "--spacebridge-api-url",
        help="SpaceBridge API base URL (overrides SPACEBRIDGE_API_URL env var and .env)"
    )
    parser.add_argument(
        "--spacebridge-api-key",
        help="SpaceBridge API key (overrides SPACEBRIDGE_API_KEY env var and .env)"
    )
    parser.add_argument(
        "--openai-api-key",
        help="OpenAI API key (overrides OPENAI_API_KEY env var and .env)"
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
    if not final_api_url:
        missing_config.append("SpaceBridge API URL")
    if not final_api_key:
        missing_config.append("SpaceBridge API Key")
    if not final_openai_key:
        missing_config.append("OpenAI API Key")

    if missing_config:
        error_message = f"Missing required configuration: {', '.join(missing_config)}. " \
                        "Please provide via command-line arguments, environment variables, or a .env file."
        logger.error(error_message)
        print(f"Error: {error_message}")
        parser.print_help() # Show help message on config error
        return # Exit if config is missing

    # 5. Initialize clients using final configuration
    global spacebridge_client, openai_client # Need globals as handlers access these
    try:
        # Get Git info using the runtime CWD
        runtime_git_org, runtime_git_project = get_git_info(os.path.join(os.getcwd(), ".git/config"))

        logger.info("Initializing SpaceBridgeClient...")
        spacebridge_client = SpaceBridgeClient(
            api_url=final_api_url,
            api_key=final_api_key,
            org_name=runtime_git_org,
            project_name=runtime_git_project
        )
        logger.info("Initializing OpenAI Client...")
        openai_client = openai.AsyncOpenAI(api_key=final_openai_key)
        logger.info("Clients initialized successfully.")

        # 5a. Perform version check after client initialization
        if not perform_version_check(spacebridge_client):
            return # Exit if version check fails critically (e.g., client too old)

    except ValueError as e:
        logger.error(f"Client Initialization Error: {e}")
        print(f"Error: Client Initialization Error: {e}")
        return # Exit if clients can't be initialized
    except Exception as e:
        logger.error(f"Unexpected error during client initialization: {e}", exc_info=True)
        print(f"Error: Unexpected error during client initialization: {e}")
        return

    # 6. Start the server
    logger.info(f"Starting FastMCP server (PID: {os.getpid()})...")
    try:
        # Run the FastMCP app
        app.run() # Uses stdio transport by default
    except KeyboardInterrupt:
        logger.info("Server stopped manually.")
    except Exception as e:
        logger.error(f"An unexpected error occurred while running the server: {e}", exc_info=True)
    finally:
        logger.info("SpaceBridge MCP Server shut down.")

def perform_version_check(client: SpaceBridgeClient):
   """Checks client/server version compatibility."""
   try:
       # Get own version
       try:
           client_version_str = importlib.metadata.version("spacebridge-mcp")
       except importlib.metadata.PackageNotFoundError:
           logger.warning("Could not determine client version using importlib.metadata. Falling back to hardcoded '0.0.0'.")
           client_version_str = "0.0.0" # Fallback or read from a constant

       client_version = parse_version(client_version_str)
       logger.info(f"SpaceBridge-MCP Client Version: {client_version}")

       # Get server version info
       version_info = client.get_version(client_version=str(client_version))
       server_version_str = version_info.get("server_version")
       min_client_str = version_info.get("min_client_version")
       max_client_str = version_info.get("max_client_version")

       if not server_version_str:
           logger.warning("Could not retrieve server version from SpaceBridge API.")
           return # Continue if server version is unknown

       server_version = parse_version(server_version_str)
       logger.info(f"SpaceBridge API Server Version: {server_version}")

       # Check minimum version requirement
       if min_client_str:
           min_client_version = parse_version(min_client_str)
           if client_version < min_client_version:
               error_msg = f"Client version {client_version} is older than the minimum required version {min_client_version} by the server. Please upgrade."
               logger.error(error_msg)
               print(f"ERROR: {error_msg}")
               return False # Indicate startup should fail

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
       print("WARNING: Failed to perform server version check against SpaceBridge API.")

   return True # Indicate startup can proceed
