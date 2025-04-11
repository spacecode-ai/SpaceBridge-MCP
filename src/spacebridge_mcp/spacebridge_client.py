# src/spacebridge_mcp/spacebridge_client.py
"""
Client for interacting with the SpaceBridge REST API.
"""

import httpx # Use httpx instead of requests
import os
from typing import Optional, Dict, Any, List
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SpaceBridgeClient:
    """Handles communication with the SpaceBridge API using httpx."""

    def __init__(self,
                 api_url: Optional[str] = None,
                 api_key: Optional[str] = None,
                 org_name: Optional[str] = None,
                 project_name: Optional[str] = None):
        """
        Initializes the SpaceBridge client.

        Args:
            api_url: The base URL for the SpaceBridge API. Defaults to env var SPACEBRIDGE_API_URL.
            api_key: The API key for authentication. Defaults to env var SPACEBRIDGE_API_KEY.
            org_name: The organization name, potentially extracted from Git config.
            project_name: The project name, potentially extracted from Git config.
        """
        self.api_url = api_url or os.getenv("SPACEBRIDGE_API_URL")
        self.api_key = api_key or os.getenv("SPACEBRIDGE_API_KEY")
        self.org_name = org_name
        self.project_name = project_name

        if not self.api_url:
            raise ValueError("SpaceBridge API URL not configured. Set SPACEBRIDGE_API_URL environment variable.")
        if not self.api_key:
            raise ValueError("SpaceBridge API Key not configured. Set SPACEBRIDGE_API_KEY environment variable.")

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        # Ensure base URL doesn't end with a slash
        self.api_url = self.api_url.rstrip('/')
        # Initialize httpx client once
        self._httpx_client = httpx.Client(base_url=self.api_url, headers=self.headers)


    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any] | List[Dict[str, Any]]:
        """Makes a request to the SpaceBridge API using httpx."""
        # url is handled by base_url in the client
        endpoint = endpoint.lstrip('/')
        try:
            response = self._httpx_client.request(method, endpoint, **kwargs)
            response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
            # Handle cases where API might return empty body on success (e.g., 204 No Content)
            if response.status_code == 204:
                return {} # Or None, depending on expected behavior
            return response.json()
        except httpx.HTTPStatusError as e:
            # Log specific HTTP errors
            print(f"HTTP error calling SpaceBridge API ({e.request.url}): {e.response.status_code} - {e.response.text}")
            raise # Re-raise the specific httpx error
        except httpx.RequestError as e:
            # Log other request errors (connection, timeout, etc.)
            print(f"Request error calling SpaceBridge API ({e.request.url}): {e}")
            raise # Re-raise the specific httpx error

    def get_issue(self, issue_id: str) -> Dict[str, Any]:
        """
        Retrieves an issue by its ID.
        Corresponds to: GET /api/v1/issues/{issue_id}
        """
        # print(f"Fetching issue {issue_id} from SpaceBridge...") # Keep print for debugging? Optional.
        return self._request("GET", f"/api/v1/issues/{issue_id}")


    def search_issues(self, query: str, search_type: str = "full_text") -> List[Dict[str, Any]]:
        """
        Searches for issues using full-text or similarity search.
        Corresponds to: GET issues/search?query={query}&type={search_type}
        """
        # print(f"Searching issues with query '{query}' (type: {search_type}) via SpaceBridge...") # Optional debug print
        params = {"query": query, "type": search_type}
        # Add org and project if available
        if self.org_name:
            params["organization"] = self.org_name
        if self.project_name:
            params["project"] = self.project_name

        logger.info(f"Searching issues with params: {params}")
        # Assuming the API returns a list directly or a dict containing a list key (e.g., 'results')
        # Adjust parsing if the API response structure is different.
        # Pass params directly to httpx request
        response_data = self._request("GET", "/api/v1/issues/search", params=params)
        # Assuming API returns a list directly based on previous logic
        if isinstance(response_data, list):
             return response_data
        # Add handling for nested results if necessary, e.g.:
        # elif isinstance(response_data, dict) and 'results' in response_data:
        #     return response_data['results']
        else:
             # Handle unexpected response format
             print(f"Warning: Unexpected format received from search API: {type(response_data)}")
             return [] # Return empty list if format is wrong

    def create_issue(self, title: str, description: str) -> Dict[str, Any]:
        """
        Creates a new issue.
        Corresponds to: POST /api/v1/issues
        """
        # print(f"Creating issue '{title}' via SpaceBridge...") # Optional debug print
        payload = {"title": title, "description": description}
        # Add org and project if available
        if self.org_name:
            payload["organization"] = self.org_name
        if self.project_name:
            payload["project"] = self.project_name

        # Pass json payload directly to httpx request
        logger.info(f"Creating issue with payload: {payload}")
        return self._request("POST", "/api/v1/issues", json=payload)

    def update_issue(self, issue_id: str, **kwargs) -> Dict[str, Any]:
        """
        Updates an existing issue using PATCH.

        Args:
            issue_id: The ID of the issue to update.
            **kwargs: Fields to update (e.g., title="New Title", status="Closed").
                      Only non-None values will be included in the request.

        Corresponds to: PATCH /api/v1/issues/{issue_id}
        """
        payload = {k: v for k, v in kwargs.items() if v is not None}

        if not payload:
            logger.warning(f"Update issue called for {issue_id} with no fields to update.")
            # Optionally return current issue data or raise an error
            # For now, return an empty dict or fetch current data? Let's return empty.
            # Consider fetching current data: return self.get_issue(issue_id)
            return {"id": issue_id, "message": "No fields provided for update."} # Return minimal info

        # Add org and project context if available (API might use this for authorization/scoping)
        if self.org_name:
            payload["organization"] = self.org_name
        if self.project_name:
            payload["project"] = self.project_name

        logger.info(f"Updating issue {issue_id} with payload: {payload}")
        # Assuming PATCH returns the updated issue data
        return self._request("PATCH", f"issues/{issue_id}", json=payload)

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
        # Make request with custom headers for this call only
        return self._request("GET", "/api/v1/version", headers=custom_headers)

# Example usage (for testing purposes)
if __name__ == "__main__":
    # Requires SPACEBRIDGE_API_URL and SPACEBRIDGE_API_KEY to be set in env.
    # This will now make *real* API calls. Ensure the target API is running and accessible.
    print("--- Running SpaceBridgeClient Test ---")
    print("--- Ensure SPACEBRIDGE_API_URL and SPACEBRIDGE_API_KEY are set correctly in your environment. ---")
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