import logging
from typing import List

from openai import APIError, AsyncOpenAI, AuthenticationError

from lib.config.env import config
from lib.services.preflight.models import (
    PreflightRequest,
    PreflightResult,
    ValidationIssue,
    ValidationSeverity,
)

logger = logging.getLogger(__name__)


class PreflightValidationService:
    """Validates API keys before starting analysis."""

    async def validate(self, request: PreflightRequest) -> PreflightResult:
        """Run all validators and aggregate results."""
        issues = await self._validate_api_key(request)
        has_errors = any(i.severity == ValidationSeverity.ERROR for i in issues)
        return PreflightResult(valid=not has_errors, issues=issues)

    async def _validate_api_key(
        self, request: PreflightRequest
    ) -> List[ValidationIssue]:
        """Validate OpenAI API key by making a lightweight API call."""
        api_key = request.openai_api_key or config.OPENAI_API_KEY
        if not api_key:
            return [
                ValidationIssue(
                    code="API_KEY_MISSING",
                    message="No OpenAI API key provided. Please enter your API key.",
                    severity=ValidationSeverity.ERROR,
                )
            ]

        async with AsyncOpenAI(api_key=api_key) as client:
            return await self._test_connection(client)

    async def _test_connection(
        self, client: AsyncOpenAI
    ) -> List[ValidationIssue]:
        """Test API connection with a lightweight call."""
        try:
            await client.models.list()
            logger.info("OpenAI API key validated successfully")
            return []
        except AuthenticationError:
            return [
                ValidationIssue(
                    code="API_KEY_INVALID",
                    message="Invalid OpenAI API key. Please check your key and try again.",
                    severity=ValidationSeverity.ERROR,
                )
            ]
        except APIError as e:
            return [
                ValidationIssue(
                    code="API_ERROR",
                    message=f"OpenAI error: {str(e)}",
                    severity=ValidationSeverity.ERROR,
                    details={"error_type": type(e).__name__},
                )
            ]
        except Exception as e:
            logger.warning(f"Unexpected error validating OpenAI key: {e}")
            return [
                ValidationIssue(
                    code="VALIDATION_FAILED",
                    message="Could not validate OpenAI configuration.",
                    severity=ValidationSeverity.WARNING,
                )
            ]


preflight_service = PreflightValidationService()
