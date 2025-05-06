# src/spacebridge_mcp/spacebridge_client.py
"""
Client for interacting with the SpaceBridge REST API.
"""

import requests  # Use requests instead of httpx
import os
from typing import Optional, Dict, Any, List
import logging
import urllib.parse

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SpaceBridgeClient:
    """Handles communication with the SpaceBridge API using requests."""

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        org_name: Optional[str] = None,
        project_name: Optional[str] = None,
    ):
        """
        Initializes the SpaceBridge client.

        Args:
            api_url: The base URL for the SpaceBridge API. Defaults to env var SPACEBRIDGE_API_URL.
            api_key: The API key for authentication. Defaults to env var SPACEBRIDGE_API_KEY.
            org_name: The organization name, potentially extracted from Git config.
            project_name: The project name, potentially extracted from Git config.
        """
        self.api_url = api_url or os.getenv(
            "SPACEBRIDGE_API_URL", "https://spacebridge.io"
        )
        self.api_key = api_key or os.getenv("SPACEBRIDGE_API_KEY")
        self.org_name = org_name
        self.project_name = project_name

        # API Key is required. Raise error if missing.
        if not self.api_key:
            raise ValueError(
                "SpaceBridge API Key not configured. Set SPACEBRIDGE_API_KEY environment variable."
            )

        # Initialize headers (API key is guaranteed to exist here)
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        # Ensure base URL doesn't end with a slash
        self.base_url = self.api_url.rstrip("/")
        # Ensure base URL ends with /api/v1
        if not self.base_url.endswith("/api/v1"):
            self.base_url += "/api/v1"

        # Initialize requests session once
        self._session = requests.Session()
        self._session.headers.update(self.headers)

    def _request(
        self, method: str, endpoint: str, **kwargs
    ) -> Dict[str, Any] | List[Dict[str, Any]]:
        """Makes a request to the SpaceBridge API using requests."""
        # Construct the full URL
        url = urllib.parse.urljoin(self.base_url + "/", endpoint.lstrip("/"))
        try:
            response = self._session.request(method, url, **kwargs)
            response.raise_for_status()  # Raise requests.exceptions.HTTPError for bad status codes (4xx or 5xx)
            # Handle cases where API might return empty body on success (e.g., 204 No Content)
            if response.status_code == 204:
                return {}  # Or None, depending on expected behavior
            # Check if response content is empty before trying to parse JSON
            if not response.content:
                return {}  # Or handle as appropriate, maybe log a warning
            return response.json()
        except requests.exceptions.HTTPError as e:
            # Log specific HTTP errors
            error_message = f"HTTP error calling SpaceBridge API ({e.request.url}): {e.response.status_code}"
            try:
                # Attempt to get more details from the response body if available
                error_details = e.response.json()
                error_message += f" - {error_details}"
            except requests.exceptions.JSONDecodeError:
                # Fallback if the error response is not JSON
                error_message += f" - {e.response.text}"
            logger.error(error_message)
            raise  # Re-raise the specific requests error
        except requests.exceptions.RequestException as e:
            # Log other request errors (connection, timeout, etc.)
            logger.error(
                f"Request error calling SpaceBridge API ({e.request.url}): {e}"
            )
            raise  # Re-raise the specific requests error

    def get_issue(
        self,
        issue: str,
        org_name: Optional[str] = None,
        project_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Retrieves an issue by its Key, ID or External ID.
        Corresponds to: GET /api/v1/issues/{issue}
        """
        # print(f"Fetching issue {issue} from SpaceBridge...") # Keep print for debugging? Optional.
        issue = urllib.parse.quote(issue, safe="")
        logger.info(f"Fetching issue {issue} from SpaceBridge...")
        params = (
            {"organization": org_name, "project": project_name}
            if org_name and project_name
            else {}
        )
        return self._request("GET", f"issues/{issue}", params=params)

    def search_issues(
        self,
        query: str,
        search_type: str = "similarity",
        org_name: Optional[str] = None,
        project_name: Optional[str] = None,
        status: Optional[str] = None,
        labels: Optional[str] = None,  # Comma-separated string
        assignee: Optional[str] = None,
        priority: Optional[str] = None,
        # Add other filters from OpenAPI spec as needed (e.g., last_updated_before/after)
    ) -> List[Dict[str, Any]]:
        """
        Searches for issues using full-text or similarity search with optional filters.
        Uses provided org/project context if available, otherwise falls back to client's startup context.
        Corresponds to: GET /api/v1/issues/search
        """
        # Start with mandatory params
        params = {"query": query, "search_type": search_type}

        # Determine context to use (passed arg takes precedence over startup context)
        final_org_name = org_name if org_name is not None else self.org_name
        final_project_name = (
            project_name if project_name is not None else self.project_name
        )

        # Add context and optional filters to params if they are provided (not None)
        if final_org_name:
            params["organization"] = final_org_name
        if final_project_name:
            params["project"] = final_project_name
        if status:
            params["status"] = status
        if labels:
            params["labels"] = labels  # API expects comma-separated string
        if assignee:
            params["assignee"] = assignee
        if priority:
            params["priority"] = priority
        # Add other filters here if implemented

        logger.info(f"Searching issues with params: {params}")
        # Pass filtered params to requests
        response_data = self._request("GET", "issues/search", params=params)

        # Assuming API returns a list directly based on previous logic and OpenAPI spec
        if isinstance(response_data, list):
            return response_data
        else:
            # Handle unexpected response format
            logger.warning(
                f"Warning: Unexpected format received from search API: {type(response_data)}. Expected list."
            )
            return []  # Return empty list if format is wrong

    def create_issue(
        self,
        title: str,
        description: str,
        org_name: Optional[str] = None,  # Added optional param
        project_name: Optional[str] = None,  # Added optional param
        labels: Optional[List[str]] = None,  # Added labels param
    ) -> Dict[str, Any]:
        """
        Creates a new issue.
        Uses provided org/project context if available, otherwise falls back to client's startup context.
        Corresponds to: POST /api/v1/issues
        """
        payload = {"title": title, "description": description}

        # Determine context to use (passed arg takes precedence over startup context)
        final_org_name = org_name if org_name is not None else self.org_name
        final_project_name = (
            project_name if project_name is not None else self.project_name
        )

        # Validate required project context before adding to payload
        if not final_project_name:
            raise ValueError("Project name is required to create an issue.")

        # Add context to payload (Org is optional, Project is required)
        payload["organization"] = (
            final_org_name if final_org_name is not None else ""
        )  # Send empty string if None
        payload["project"] = final_project_name

        # Add labels to payload if provided
        if labels:
            payload["labels"] = labels

        # Pass json payload directly to requests
        logger.info(f"Creating issue with payload: {payload}")
        return self._request("POST", "issues", json=payload)

    def update_issue(
        self,
        issue: str,
        org_name: Optional[str] = None,  # Added optional param
        project_name: Optional[str] = None,  # Added optional param
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Updates an existing issue using PATCH.
        Uses provided org/project context if available, otherwise falls back to client's startup context.

        Args:
            issue: The Key, ID or External ID of the issue to update.
            org_name: Optional organization context override.
            project_name: Optional project context override.
            **kwargs: Fields to update (e.g., title="New Title", status="Closed").
                      Only non-None values will be included in the request.

        Corresponds to: PATCH /api/v1/issues/{issue}
        """
        # Separate update fields from context args (though context args are named)
        update_fields = {k: v for k, v in kwargs.items() if v is not None}

        if not update_fields:
            logger.warning(f"Update issue called for {issue} with no fields to update.")
            return {"id": issue, "message": "No fields provided for update."}

        payload = update_fields.copy()  # Start payload with actual update fields

        # Determine context to use (passed arg takes precedence over startup context)
        final_org_name = org_name if org_name is not None else self.org_name
        final_project_name = (
            project_name if project_name is not None else self.project_name
        )

        # Add org and project context to payload if determined (API might use this for authorization/scoping)
        if final_org_name:
            payload["organization"] = final_org_name
        if final_project_name:
            payload["project"] = final_project_name

        logger.info(f"Updating issue {issue} with payload: {payload}")
        # Assuming PATCH returns the updated issue data
        # Endpoint already correct here, no change needed for PATCH
        # Changed from PATCH to PUT based on live API 405 error
        issue = urllib.parse.quote(issue, safe="")
        return self._request("PUT", f"issues/{issue}", json=payload)

    def get_version(self, client_version: str) -> Dict[str, Any]:
        """
        Retrieves server version info and checks compatibility.

        Args:
            client_version: The version of this MCP server client.

        Corresponds to: GET /api/v1/version
        Includes custom headers: X-Client-Version, X-Client-Organization, X-Client-Project
        """
        custom_headers = self.headers.copy()
        custom_headers["X-Client-Version"] = client_version
        if self.org_name:
            custom_headers["X-Client-Organization"] = self.org_name
        if self.project_name:
            custom_headers["X-Client-Project"] = self.project_name

        logger.info(f"Getting server version with client version {client_version}")
        # Make request with custom headers for this call only using requests
        # Note: _request now uses the session, which has base headers.
        # We need to merge headers carefully or make a one-off request.
        # For simplicity, let's use requests.get directly for this specific case.
        url = urllib.parse.urljoin(self.base_url + "/", "version")
        try:
            response = requests.get(url, headers=custom_headers)
            response.raise_for_status()
            if response.status_code == 204 or not response.content:
                return {}
            return response.json()
        except requests.exceptions.HTTPError as e:
            logger.error(
                f"HTTP error getting version ({e.request.url}): {e.response.status_code} - {e.response.text}"
            )
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error getting version ({e.request.url}): {e}")
            raise


# Example usage (for testing purposes)
if __name__ == "__main__":
    # Requires SPACEBRIDGE_API_URL and SPACEBRIDGE_API_KEY to be set in env.
    # This will now make *real* API calls. Ensure the target API is running and accessible.
    print("--- Running SpaceBridgeClient Test ---")
    print(
        "--- Ensure SPACEBRIDGE_API_URL and SPACEBRIDGE_API_KEY are set correctly in your environment. ---"
    )
    print("--- This will attempt to interact with the live API specified. ---")
    try:
        client = SpaceBridgeClient()
        print("\n--- Testing get_issue ---")
        issue = client.get_issue("SB-1")
        print(issue)

        print("\n--- Testing search_issues (full_text) ---")
        results_ft = client.search_issues("bug fix")
        print(results_ft)

        print("\n--- Testing search_issues (similarity) ---")
        results_sim = client.search_issues("fix login bug", search_type="similarity")
        print(results_sim)

        print("\n--- Testing create_issue ---")
        new_issue = client.create_issue("New Feature Request", "Implement dark mode.")
        print(new_issue)

    except ValueError as e:
        print(f"Configuration Error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
