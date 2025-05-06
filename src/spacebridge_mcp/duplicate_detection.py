# src/spacebridge_mcp/duplicate_detection.py
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Literal, Optional

from .tools import IssueSummary

logger = logging.getLogger(__name__)


# Decision structure returned by detectors
@dataclass
class DuplicateDecision:
    status: Literal["duplicate", "not_duplicate", "undetermined"]
    duplicate_issue: Optional[IssueSummary] = None  # Include full details if duplicate


# --- Abstract Base Class ---


class DuplicateDetector(ABC):
    """Abstract base class for duplicate issue detection strategies."""

    @abstractmethod
    async def check_duplicates(
        self,
        new_title: str,
        new_description: str,
        potential_duplicates: List[IssueSummary],
    ) -> DuplicateDecision:
        """
        Checks if a new issue is a duplicate among a list of potential candidates.

        Args:
            new_title: Title of the new issue.
            new_description: Description of the new issue.
            potential_duplicates: List of potential duplicates found via search.

        Returns:
            A DuplicateDecision object indicating the outcome.
        """
        pass


# --- Concrete Implementations ---


class OpenAIDuplicateDetector(DuplicateDetector):
    """Uses OpenAI's LLM to compare potential duplicates."""

    def __init__(self, client):
        if client is None:
            raise ValueError(
                "OpenAI client must be provided for OpenAIDuplicateDetector"
            )
        self.openai_client = client

    async def check_duplicates(
        self,
        new_title: str,
        new_description: str,
        potential_duplicates: List[IssueSummary],
    ) -> DuplicateDecision:
        """Performs LLM comparison to detect duplicates."""
        if not potential_duplicates:
            return DuplicateDecision(status="not_duplicate")

        top_n = 3  # Consider making this configurable
        duplicates_to_check = potential_duplicates[:top_n]
        duplicates_context = "\n\n".join(
            [
                f"Existing Issue ID: {dup.id}\nTitle: {dup.title}\nDescription: {dup.description or 'N/A'}\nScore: {dup.score or 'N/A'}"
                for dup in duplicates_to_check
            ]
        )

        prompt = f"""You are an expert issue tracker assistant. Your task is to determine if a new issue is a duplicate of existing issues.

New Issue Details:
Title: {new_title}
Description: {new_description}

Potential Existing Duplicates Found via Similarity Search:
---
{duplicates_context}
---

Based on the information above, is the 'New Issue' a likely duplicate of *any* of the 'Potential Existing Duplicates'?

Respond with ONLY one of the following:
1.  If it IS a duplicate: DUPLICATE: [ID of the existing issue, e.g., SB-123]
2.  If it is NOT a duplicate: NOT_DUPLICATE
"""
        logger.info(f"Sending comparison prompt to LLM for new issue '{new_title}'...")
        try:
            # Use environment variable for model name, fallback to gpt-4o
            model_name = os.getenv("OPENAI_MODEL", "gpt-4o")
            llm_response = await self.openai_client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=50,  # Increased slightly for safety
            )
            llm_decision_raw = llm_response.choices[0].message.content.strip()
            logger.info(f"LLM response received: '{llm_decision_raw}'")

            if llm_decision_raw.startswith("DUPLICATE:"):
                parts = llm_decision_raw.split(":", 1)
                if len(parts) == 2:
                    potential_id = parts[1].strip()
                    # Find the full IssueSummary object for the matched ID
                    matched_dup = next(
                        (dup for dup in duplicates_to_check if dup.id == potential_id),
                        None,
                    )
                    if matched_dup:
                        logger.info(f"LLM identified duplicate: {matched_dup.id}")
                        return DuplicateDecision(
                            status="duplicate", duplicate_issue=matched_dup
                        )
                    else:
                        logger.warning(
                            f"LLM reported duplicate ID '{potential_id}' but it wasn't in the top {top_n} checked."
                        )
                        return DuplicateDecision(status="undetermined")
                else:
                    logger.warning(
                        f"LLM response started with DUPLICATE: but format was unexpected: {llm_decision_raw}"
                    )
                    return DuplicateDecision(status="undetermined")

            elif llm_decision_raw == "NOT_DUPLICATE":
                logger.info("LLM confirmed not a duplicate.")
                return DuplicateDecision(status="not_duplicate")
            else:
                logger.warning(
                    f"LLM response was not in the expected format: {llm_decision_raw}"
                )
                return DuplicateDecision(status="undetermined")

        except Exception as llm_error:
            logger.error(
                f"Error calling OpenAI API for duplicate check: {llm_error}",
                exc_info=True,
            )
            return DuplicateDecision(status="undetermined")


class ThresholdDuplicateDetector(DuplicateDetector):
    """Compares the top similarity search result score against a threshold."""

    DEFAULT_THRESHOLD = 0.75  # Default threshold if env var is not set

    def __init__(self):
        self.threshold = self._get_threshold()
        logger.info(
            f"Initialized ThresholdDuplicateDetector with threshold: {self.threshold}"
        )

    def _get_threshold(self) -> float:
        """Gets the similarity threshold from env var or uses default."""
        try:
            threshold_str = os.environ.get("DUPLICATE_SIMILARITY_THRESHOLD")
            if threshold_str:
                return float(threshold_str)
            else:
                logger.info(
                    f"DUPLICATE_SIMILARITY_THRESHOLD not set, using default: {self.DEFAULT_THRESHOLD}"
                )
                return self.DEFAULT_THRESHOLD
        except ValueError:
            logger.warning(
                f"Invalid value for DUPLICATE_SIMILARITY_THRESHOLD: '{threshold_str}'. "
                f"Using default: {self.DEFAULT_THRESHOLD}"
            )
            return self.DEFAULT_THRESHOLD

    async def check_duplicates(
        self,
        new_title: str,
        new_description: str,
        potential_duplicates: List[IssueSummary],
    ) -> DuplicateDecision:
        """Checks if the top duplicate's score meets the threshold."""
        if not potential_duplicates:
            logger.debug("ThresholdDetector: No potential duplicates found.")
            return DuplicateDecision(status="not_duplicate")

        # Assuming potential_duplicates are sorted by score descending by the search client
        top_duplicate = potential_duplicates[0]

        # Check if the IssueSummary actually has a score
        if top_duplicate.score is None:
            logger.warning(
                f"ThresholdDetector: Top potential duplicate {top_duplicate.id} has no similarity score. Treating as undetermined."
            )
            # Cannot make a decision based on threshold without a score
            return DuplicateDecision(status="undetermined")

        logger.debug(
            f"ThresholdDetector: Top duplicate {top_duplicate.id} score: {top_duplicate.score:.4f}, Threshold: {self.threshold:.4f}"
        )

        if top_duplicate.score >= self.threshold:
            logger.info(
                f"ThresholdDetector: Score {top_duplicate.score:.4f} >= {self.threshold:.4f}. Found duplicate: {top_duplicate.id}"
            )
            return DuplicateDecision(status="duplicate", duplicate_issue=top_duplicate)
        else:
            logger.info(
                f"ThresholdDetector: Score {top_duplicate.score:.4f} < {self.threshold:.4f}. Not a duplicate."
            )
            return DuplicateDecision(status="not_duplicate")


# --- Factory ---


class DuplicateDetectorFactory:
    """Factory to create the appropriate duplicate detector based on config."""

    def __init__(self, client=None):
        """
        Initializes the factory.

        Args:
            client: The OpenAI client instance, needed if OpenAI detector might be used.
        """
        self.openai_client = client

    def get_detector(self) -> DuplicateDetector:
        """Gets the configured duplicate detector."""
        if os.environ.get("OPENAI_API_KEY"):
            if self.openai_client:
                logger.info("OpenAI API key found. Using OpenAIDuplicateDetector.")
                return OpenAIDuplicateDetector(client=self.openai_client)
            else:
                # Log warning but still proceed with ThresholdDetector if client is missing
                logger.warning(
                    "OpenAI API key found, but no OpenAI client provided to factory. Falling back to ThresholdDetector."
                )
                return ThresholdDuplicateDetector()
        else:
            logger.info("OpenAI API key not found. Using ThresholdDuplicateDetector.")
            return ThresholdDuplicateDetector()
