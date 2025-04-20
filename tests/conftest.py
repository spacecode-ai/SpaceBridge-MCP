import pytest
import os
import sys  # Add sys import
import respx  # Add respx import
from unittest.mock import patch  # Import patch
import openai  # Import openai for type hint
from spacebridge_mcp.spacebridge_client import SpaceBridgeClient

# --- Path Hack to find 'src' directory ---
# This helps pytest find the 'spacebridge_mcp' module when run from the root directory.
SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
# --- End Path Hack ---

# Import client classes (should work now)

# Define constants for API used across tests
MOCK_API_URL = "http://localhost:8000/api/v1"  # Corrected live server URL
MOCK_API_KEY = "7E98YMty38acelZAsJJpuHoi2tuX0trGANv7IkJG"  # Changed to provided API key
MOCK_OPENAI_KEY = "mock_openai_key"  # Doesn't need to be valid for mocking

# --- Pytest Hooks and Fixtures ---


@pytest.fixture(autouse=True)
def manage_respx_activation():
    """Starts respx only if RUN_LIVE_API_TESTS is not set."""
    if os.getenv("RUN_LIVE_API_TESTS") != "1":
        # print("\n>>> RESPX ACTIVE <<<") # Debug print
        respx.start()
        yield
        respx.stop()
    else:
        # print("\n>>> RESPX INACTIVE (Live API) <<<") # Debug print
        yield  # Do nothing if live tests are enabled


# Removed --live-api option and live_api_enabled fixture.
# Use environment variable RUN_LIVE_API_TESTS=1 to run live tests.


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """Automatically mock environment variables for all tests."""
    monkeypatch.setenv("SPACEBRIDGE_API_URL", MOCK_API_URL)
    monkeypatch.setenv("SPACEBRIDGE_API_KEY", MOCK_API_KEY)
    monkeypatch.setenv("OPENAI_API_KEY", MOCK_OPENAI_KEY)
    # Ensure FASTMCP_PORT doesn't conflict if server is run via tests (less common)
    monkeypatch.setenv("FASTMCP_PORT", "8099")


@pytest.fixture(scope="session")
def test_spacebridge_client():  # Removed live_api_enabled fixture dependency
    """
    Provides an initialized SpaceBridgeClient instance for tests.
    Uses MOCK_API_URL and MOCK_API_KEY defined above (which point to live server).
    """
    # Uses mocked env vars set by mock_env_vars, but overrides key if live
    api_key = MOCK_API_KEY  # This is now the live key from the previous step
    # No need to differentiate mock/live key here anymore as MOCK_API_KEY holds the live one.
    # url is also set to live url.
    return SpaceBridgeClient(api_url=MOCK_API_URL, api_key=api_key)


@pytest.fixture(scope="session")
def test_openai_client():
    """Provides an initialized OpenAI client instance for tests."""
    # Uses mocked env vars set by mock_env_vars
    # Return a real client instance, tests will mock its methods via @patch
    return openai.AsyncOpenAI(api_key=MOCK_OPENAI_KEY)


@pytest.fixture(autouse=True)
def patch_server_clients(test_spacebridge_client, test_openai_client):
    """
    Patches the global client variables in server.py for the duration of each test.
    This ensures handlers use the test clients configured with mock env vars.
    """
    # Use 'spacebridge_mcp.server' as the target module for patching
    with (
        patch("spacebridge_mcp.server.spacebridge_client", test_spacebridge_client),
        patch("spacebridge_mcp.server.openai_client", test_openai_client),
    ):
        yield


@pytest.fixture(scope="session")
def get_issue_test_id() -> str:
    """Returns the appropriate issue ID for get_issue tests based on environment."""
    if os.getenv("RUN_LIVE_API_TESTS") == "1":
        return "35#7"  # Actual ID created for live tests
    else:
        return "SB-123"  # Mock ID used in tests


@pytest.fixture(scope="session")
def update_issue_test_id() -> str:
    """Returns the appropriate issue ID for update_issue tests based on environment."""
    if os.getenv("RUN_LIVE_API_TESTS") == "1":
        return "35#8"  # Actual ID created for live tests
    else:
        return "SB-EXISTING"  # Mock ID used in tests
