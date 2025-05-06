import pytest
import httpx
import respx
from httpx import Response
import json
from unittest.mock import patch, Mock

from spacebridge_mcp.spacebridge_client import SpaceBridgeClient
from tests.conftest import MOCK_API_URL, MOCK_API_KEY


@pytest.fixture
def client():
    """Fixture to create a SpaceBridgeClient for testing error handling."""
    return SpaceBridgeClient(
        api_url=MOCK_API_URL,
        api_key=MOCK_API_KEY,
        org_name="test-org",
        project_name="test-project",
    )


def test_request_http_status_error(client):
    """Test _request method handling of HTTP status errors."""
    # Mock a 400 Bad Request response
    respx.get(f"{MOCK_API_URL}/issues/test-id").mock(
        return_value=Response(400, json={"error": "Bad request"})
    )

    # Verify the error is raised through
    with pytest.raises(httpx.HTTPStatusError):
        client.get_issue("test-id")


def test_request_connection_error(client):
    """Test _request method handling of connection errors."""
    # Mock a connection error
    with patch.object(client._httpx_client, "request") as mock_request:
        mock_request.side_effect = httpx.ConnectError(
            "Connection refused", request=Mock()
        )

        with pytest.raises(httpx.ConnectError):
            client.get_issue("test-id")


def test_request_timeout_error(client):
    """Test _request method handling of timeout errors."""
    # Mock a timeout error
    with patch.object(client._httpx_client, "request") as mock_request:
        mock_request.side_effect = httpx.TimeoutException(
            "Request timed out", request=Mock()
        )

        with pytest.raises(httpx.TimeoutException):
            client.get_issue("test-id")


def test_search_issues_unexpected_response_format(client):
    """Test search_issues handling of unexpected response format."""
    # Mock an unexpected response format (not a list)
    respx.get(f"{MOCK_API_URL}/issues/search").mock(
        return_value=Response(200, json={"not_a_list": "this is a dict"})
    )

    # The method should handle this gracefully and return an empty list
    results = client.search_issues("test query")
    assert results == []


def test_create_issue_with_labels(client):
    """Test create_issue with labels parameter."""
    title = "Test Issue"
    description = "Test Description"
    labels = ["bug", "priority:high"]
    expected_response = {
        "id": "SB-123",
        "title": title,
        "description": description,
        "labels": labels,
        "status": "New",
    }

    # Mock the API response
    respx.post(f"{MOCK_API_URL}/issues").mock(
        return_value=Response(201, json=expected_response)
    )

    # Call the method with labels
    response = client.create_issue(title=title, description=description, labels=labels)

    # Verify the response
    assert response == expected_response

    # Verify the request payload included labels
    request = respx.calls.last.request
    payload = json.loads(request.content)
    assert payload["labels"] == labels


def test_create_issue_missing_project(client):
    """Test create_issue fails properly when project is missing."""
    # Create a client without a project name
    client_no_project = SpaceBridgeClient(
        api_url=MOCK_API_URL,
        api_key=MOCK_API_KEY,
        org_name="test-org",
        project_name=None,
    )

    # Attempt to create an issue without providing project name
    with pytest.raises(ValueError, match="Project name is required"):
        client_no_project.create_issue("Test Title", "Test Description")


def test_get_version(client):
    """Test get_version method with custom headers."""
    client_version = "0.2.3"
    expected_response = {
        "version": "1.0.0",
        "compatible": True,
        "message": "API is compatible with client",
    }

    # Mock the API response
    respx.get(f"{MOCK_API_URL}/version").mock(
        return_value=Response(200, json=expected_response)
    )

    # Call the method
    response = client.get_version(client_version)

    # Verify the response
    assert response == expected_response

    # Verify the custom headers were sent
    request = respx.calls.last.request
    assert request.headers["X-Client-Version"] == client_version
    assert request.headers["X-Client-Organization"] == "test-org"
    assert request.headers["X-Client-Project"] == "test-project"


def test_request_204_response(client):
    """Test _request method handling of 204 No Content responses."""
    # Mock a 204 No Content response
    respx.put(f"{MOCK_API_URL}/issues/test-id").mock(return_value=Response(204))

    # The method should return an empty dictionary
    result = client.update_issue("test-id", status="Closed")
    assert result == {}


def test_update_issue_with_none_values(client):
    """Test update_issue properly filters out None values."""
    issue_id = "SB-123"
    update_data = {
        "title": "New Title",
        "description": None,  # Should be filtered out
        "status": "Closed",
    }
    expected_response = {"id": issue_id, "title": "New Title", "status": "Closed"}

    # Mock the API response
    respx.put(f"{MOCK_API_URL}/issues/{issue_id}").mock(
        return_value=Response(200, json=expected_response)
    )

    # Call update_issue with None values
    result = client.update_issue(
        issue_id=issue_id,
        title=update_data["title"],
        description=update_data["description"],
        status=update_data["status"],
    )

    # Verify the response
    assert result == expected_response

    # Verify None values were filtered from the payload
    request = respx.calls.last.request
    payload = json.loads(request.content)
    assert "title" in payload
    assert "status" in payload
    assert "description" not in payload
