# src/spacebridge_mcp/tools.py
"""
MCP Tool definitions for SpaceBridge integration.
"""

# Imports related to ToolProvider, ParameterDefinition, ToolCallResult, Tool are removed
# as registration will happen via FastMCP decorators in server.py
from pydantic import BaseModel, Field
import logging  # Added for logging LLM calls
from typing import List, Optional, Literal

# Keep openai and client imports if needed for models, but likely only needed in server.py now
# import openai
# from openai import AsyncOpenAI
# from .spacebridge_client import SpaceBridgeClient
logger = logging.getLogger(__name__)  # Added logger

# --- Input/Output Schemas ---


class SearchIssuesInput(BaseModel):
    query: str = Field(..., description="The search query string.")
    search_type: Literal["full_text", "similarity"] = Field(
        default="full_text", description="The type of search to perform."
    )
    org_name: Optional[str] = Field(
        None,
        description="Optional: Override the server's detected/configured organization context.",
    )
    project_name: Optional[str] = Field(
        None,
        description="Optional: Override the server's detected/configured project context.",
    )


class IssueSummary(BaseModel):
    id: str = Field(..., description="The unique identifier of the issue.")
    title: str = Field(..., description="The title of the issue.")
    description: Optional[str] = Field(
        None,
        description="The description of the issue (might be truncated in search results).",
    )  # Added description field
    url: Optional[str] = Field(
        None, description="Direct URL to the issue in the tracker."
    )
    score: Optional[float] = Field(
        None, description="Relevance score (for similarity search)."
    )


class SearchIssuesOutput(BaseModel):
    results: List[IssueSummary] = Field(
        ..., description="A list of issues matching the search query."
    )


class CreateIssueInput(BaseModel):
    title: str = Field(..., description="The title for the new issue.")
    description: str = Field(
        ..., description="The detailed description for the new issue."
    )
    org_name: Optional[str] = Field(
        None,
        description="Optional: Override the server's detected/configured organization context.",
    )
    project_name: Optional[str] = Field(
        None,
        description="Optional: Override the server's detected/configured project context.",
    )
    labels: Optional[List[str]] = Field(
        None, description="Optional: A list of labels to apply to the new issue."
    )


class CreateIssueOutput(BaseModel):
    issue_id: Optional[str] = Field(
        None,
        description="The ID of the created or potentially duplicate existing issue. Can be None if undetermined initially.",
    )
    status: Literal["created", "existing_duplicate_found", "undetermined"] = Field(
        ...,
        description="Indicates if a new issue was created, a duplicate was found, or the check was undetermined.",
    )
    message: str = Field(..., description="A message describing the outcome.")
    url: Optional[str] = Field(
        None, description="Direct URL to the created/found issue."
    )


class UpdateIssueInput(BaseModel):
    issue_id: str = Field(..., description="The ID of the issue to update.")
    title: Optional[str] = Field(None, description="The new title for the issue.")
    description: Optional[str] = Field(
        None, description="The new description for the issue."
    )
    status: Optional[str] = Field(
        None,
        description="The new status for the issue (e.g., 'Open', 'In Progress', 'Closed'). Exact values depend on the tracker.",
    )
    # Add other updatable fields as needed (e.g., assignee, labels)
    org_name: Optional[str] = Field(
        None,
        description="Optional: Override the server's detected/configured organization context.",
    )
    project_name: Optional[str] = Field(
        None,
        description="Optional: Override the server's detected/configured project context.",
    )


class UpdateIssueOutput(BaseModel):
    issue_id: str = Field(..., description="The ID of the updated issue.")
    status: Literal["updated", "failed"] = Field(
        ..., description="Indicates if the update was successful."
    )
    message: str = Field(..., description="A message describing the outcome.")
    url: Optional[str] = Field(None, description="Direct URL to the updated issue.")


# ToolProvider class and get_tools function removed.
# Tool handler functions will be defined and registered in server.py using FastMCP decorators.
