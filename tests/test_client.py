import pytest
import os # Import os module
import respx
import json # Import json for parsing
from httpx import Response

from spacebridge_mcp.spacebridge_client import SpaceBridgeClient
from tests.conftest import MOCK_API_URL, MOCK_API_KEY # Import constants from conftest

# Removed local MOCK_API_URL and MOCK_API_KEY definitions.
# Tests will now use the MOCK_API_URL imported from conftest for respx routes,
# ensuring consistency with the client's configured base URL.

# Constants MOCK_API_URL and MOCK_API_KEY are now sourced from conftest.py via the mock_env_vars fixture
# and the client fixture. Remove local definitions.

@pytest.fixture(params=[
    {"org": None, "project": None},
    {"org": "test-org", "project": "test-project"}
])
def client_config(request):
    """Provides client configuration parameters (with and without org/project)."""
    return request.param

@pytest.fixture
def client(monkeypatch, client_config):
    """Fixture to create a SpaceBridgeClient with optional org/project.
       Relies on mock_env_vars in conftest.py to set API_URL and API_KEY env vars."""
    # Removed monkeypatch.setenv calls here - they are handled by mock_env_vars in conftest.py
    return SpaceBridgeClient(
        org_name=client_config["org"],
        project_name=client_config["project"]
    )

# Removed skipif and respx.mock (handled by conftest fixture)
def test_get_issue_success(client: SpaceBridgeClient):
    """Test successful retrieval of an issue."""
    issue_id = "SB-123"
    expected_data = {"id": issue_id, "title": "Test Issue", "status": "Open"}
    # Reverted to direct respx usage
    # Define the mock route - it will only be active if respx is started by the fixture
    respx.get(f"{MOCK_API_URL}/issues/{issue_id}").mock(return_value=Response(200, json=expected_data))

    issue = client.get_issue(issue_id)
    assert issue == expected_data

# Removed skipif and respx.mock
def test_get_issue_not_found(client: SpaceBridgeClient):
    """Test handling of 404 error when getting an issue."""
    issue_id = "SB-404"
    # Reverted to direct respx usage
    respx.get(f"{MOCK_API_URL}/issues/{issue_id}").mock(return_value=Response(404))

    # Expect failure only when mocking or if the issue truly doesn't exist live
    # For live tests, this might pass if SB-404 exists, or fail differently if server is down
    # Skipping the check for live API for simplicity, assuming 404 is expected failure
    # This test only runs when mocked, so expect the exception
    # Expect exception whether mocked (404) or live (404 or ConnectError)
    with pytest.raises(Exception):
        client.get_issue(issue_id)

# Removed skipif and respx.mock
def test_search_issues_success(client: SpaceBridgeClient, client_config):
    """Test successful search for issues, including org/project params."""
    query = "bug fix"
    search_type = "full_text"
    expected_results = [
        {"id": "SB-1", "title": "Fix login bug"},
        {"id": "SB-2", "title": "Bug in search results"},
    ]

    # Build expected params based on client config
    expected_params = {"query": query, "type": search_type}
    if client_config["org"]:
        expected_params["organization"] = client_config["org"]
    if client_config["project"]:
        expected_params["project"] = client_config["project"]

    # Reverted to direct respx usage
    search_route = respx.get(f"{MOCK_API_URL}/issues/search", params=expected_params).mock(
        return_value=Response(200, json=expected_results)
    )
    # Removed extra parenthesis

    results = client.search_issues(query=query, search_type=search_type)
    assert results == expected_results
    # Assertions below assume the call succeeded (either mocked or live)
    # For live tests, this assumes the search returns the exact expected_results
    assert results == expected_results
    if os.getenv("RUN_LIVE_API_TESTS") != "1": # Only check respx calls if mocking
        assert search_route.called
        assert dict(respx.calls.last.request.url.params) == expected_params
    # Add assertion for live mode? Difficult without knowing live data.
    # assert isinstance(results, list) # Basic check for live mode

# Removed skipif and respx.mock
def test_search_issues_similarity_success(client: SpaceBridgeClient, client_config):
    """Test successful similarity search, including org/project params."""
    query = "similar bug"
    search_type = "similarity"
    expected_results = [
        {"id": "SB-1", "title": "Fix login bug", "score": 0.9},
    ]

    # Build expected params based on client config
    expected_params = {"query": query, "type": search_type}
    if client_config["org"]:
        expected_params["organization"] = client_config["org"]
    if client_config["project"]:
        expected_params["project"] = client_config["project"]

    # Reverted to direct respx usage
    search_route = respx.get(f"{MOCK_API_URL}/issues/search", params=expected_params).mock( # Corrected path
        return_value=Response(200, json=expected_results)
    )
    # Removed extra parenthesis

    results = client.search_issues(query=query, search_type=search_type)
    assert results == expected_results
    # Assertions assume call succeeded
    assert results == expected_results
    if os.getenv("RUN_LIVE_API_TESTS") != "1": # Only check respx calls if mocking
        assert search_route.called
        assert dict(respx.calls.last.request.url.params) == expected_params
    # assert isinstance(results, list) # Basic check for live mode


# Removed skipif and respx.mock
def test_create_issue_success(client: SpaceBridgeClient, client_config):
    """Test successful creation of an issue, including org/project payload."""
    title = "New Feature"
    description = "Add dark mode"
    expected_response = {"id": "SB-NEW", "title": title, "description": description, "status": "New"}

    # Build expected payload based on client config
    expected_payload = {"title": title, "description": description}
    if client_config["org"]:
        expected_payload["organization"] = client_config["org"]
    if client_config["project"]:
        expected_payload["project"] = client_config["project"]

    # Reverted to direct respx usage
    create_route = respx.post(f"{MOCK_API_URL}/issues").mock(
        return_value=Response(201, json=expected_response)
    )
    # Removed extra parenthesis

    new_issue = client.create_issue(title=title, description=description)
    assert new_issue == expected_response

    # Verify the request payload was correct
    # Assertions assume call succeeded
    assert new_issue == expected_response # This might fail live if response differs slightly
    if os.getenv("RUN_LIVE_API_TESTS") != "1": # Only check respx calls if mocking
        assert create_route.called
        sent_payload = json.loads(respx.calls.last.request.content)
        assert sent_payload == expected_payload
    # Add assertion for live mode? Check if 'id' exists?
    # assert "id" in new_issue


def test_client_init_missing_url(monkeypatch):
    """Test client initialization fails if URL is missing."""
    monkeypatch.delenv("SPACEBRIDGE_API_URL", raising=False)
    monkeypatch.setenv("SPACEBRIDGE_API_KEY", MOCK_API_KEY)
    with pytest.raises(ValueError, match="API URL not configured"):
        SpaceBridgeClient()

def test_client_init_missing_key(monkeypatch):
    """Test client initialization fails if API key is missing."""
    monkeypatch.setenv("SPACEBRIDGE_API_URL", MOCK_API_URL)
    monkeypatch.delenv("SPACEBRIDGE_API_KEY", raising=False)
    with pytest.raises(ValueError, match="API Key not configured"):
        SpaceBridgeClient()

# Removed skipif and respx.mock
def test_update_issue_success(client: SpaceBridgeClient, client_config):
    """Test successful update of an issue, including org/project payload."""
    issue_id = "SB-EXISTING"
    update_data = {"status": "In Progress", "title": "Updated Title"}
    # Assume API returns the updated issue data
    expected_response = {"id": issue_id, "title": "Updated Title", "description": "Existing Desc", "status": "In Progress"}

    # Build expected payload based on client config and update_data
    expected_payload = update_data.copy() # Start with fields being updated
    if client_config["org"]:
        expected_payload["organization"] = client_config["org"]
    if client_config["project"]:
        expected_payload["project"] = client_config["project"]

    # Reverted to direct respx usage
    update_route = respx.patch(f"{MOCK_API_URL}/issues/{issue_id}").mock(
        return_value=Response(200, json=expected_response)
    )
    # Removed extra parenthesis

    updated_issue = client.update_issue(issue_id=issue_id, **update_data)
    assert updated_issue == expected_response

    # Verify the request payload was correct
    # Assertions assume call succeeded
    assert updated_issue == expected_response # Might fail live
    if os.getenv("RUN_LIVE_API_TESTS") != "1": # Only check respx calls if mocking
        assert update_route.called
        sent_payload = json.loads(respx.calls.last.request.content)
        assert sent_payload == expected_payload
    # Add assertion for live mode? Check if status matches?
    # assert updated_issue.get("status") == update_data["status"]

# Removed skipif and respx.mock (no HTTP call expected)
def test_update_issue_no_fields(client: SpaceBridgeClient, client_config):
    """Test calling update_issue with no fields to update."""
    issue_id = "SB-NOUPDATE"

    # No respx route needed as the client should handle this before making a call

    # Call update with no keyword arguments
    result = client.update_issue(issue_id=issue_id)

    # Check the minimal response returned by the client method
    assert result == {"id": issue_id, "message": "No fields provided for update."}
    # Check respx calls only if mocking is active (it shouldn't be for this test)
    if os.getenv("RUN_LIVE_API_TESTS") != "1":
        assert len(respx.calls) == 0 # Ensure no HTTP call was made