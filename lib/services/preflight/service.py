import logging
from typing import List, Union

from openai import APIError, AsyncAzureOpenAI, AsyncOpenAI, AuthenticationError

from lib.config.env import config
from lib.services.preflight.models import (
    PreflightRequest,
    PreflightResult,
    ValidationIssue,
    ValidationSeverity,
)

logger = logging.getLogger(__name__)

AsyncClient = Union[AsyncOpenAI, AsyncAzureOpenAI]


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
        """Validate OpenAI/Azure API key by making a lightweight API call."""
        is_azure = bool(config.AZURE_OPENAI_API_KEY and config.AZURE_OPENAI_ENDPOINT)

        if is_azure:
            return await self._validate_azure()

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
            return await self._test_connection(client, "OpenAI")

    async def _validate_azure(self) -> List[ValidationIssue]:
        """Validate Azure config and test connection."""
        if not config.AZURE_OPENAI_API_KEY:
            return [
                ValidationIssue(
                    code="AZURE_API_KEY_MISSING",
                    message="Azure OpenAI API key not configured on server.",
                    severity=ValidationSeverity.ERROR,
                )
            ]

        if not config.AZURE_OPENAI_ENDPOINT:
            return [
                ValidationIssue(
                    code="AZURE_ENDPOINT_MISSING",
                    message="Azure OpenAI endpoint not configured on server.",
                    severity=ValidationSeverity.ERROR,
                )
            ]

        async with AsyncAzureOpenAI(
            api_key=config.AZURE_OPENAI_API_KEY,
            azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
            api_version=config.OPENAI_API_VERSION or "2024-02-15-preview",
        ) as client:
            return await self._test_connection(client, "Azure OpenAI")

    async def _test_connection(
        self, client: AsyncClient, provider: str
    ) -> List[ValidationIssue]:
        """Test API connection with a lightweight call."""
        prefix = "AZURE_" if "Azure" in provider else ""

        try:
            await client.models.list()
            logger.info(f"{provider} API key validated successfully")
            return []
        except AuthenticationError:
            return [
                ValidationIssue(
                    code=f"{prefix}API_KEY_INVALID",
                    message=f"Invalid {provider} API key. Please check your key and try again.",
                    severity=ValidationSeverity.ERROR,
                )
            ]
        except APIError as e:
            return [
                ValidationIssue(
                    code=f"{prefix}API_ERROR",
                    message=f"{provider} error: {str(e)}",
                    severity=ValidationSeverity.ERROR,
                    details={"error_type": type(e).__name__},
                )
            ]
        except Exception as e:
            logger.warning(f"Unexpected error validating {provider} key: {e}")
            return [
                ValidationIssue(
                    code=f"{prefix}VALIDATION_FAILED",
                    message=f"Could not validate {provider} configuration.",
                    severity=ValidationSeverity.WARNING,
                )
            ]


preflight_service = PreflightValidationService()
