from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class Actor(BaseModel):
    id: str
    role: str


class Claim(BaseModel):
    key: str
    value: Any
    text: str | None = None


class Candidate(BaseModel):
    text: str | None = None
    tool: str | None = None
    operation: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    claims: list[Claim] = Field(default_factory=list)


class ControlEvent(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    tenant_id: str = "saas-enterprise-demo"
    use_case: str
    event_type: Literal[
        "input",
        "candidate_response",
        "proposed_action",
        "post_action",
    ]
    actor: Actor
    candidate: Candidate
    trusted_context: dict[str, Any] = Field(default_factory=dict)
    policy_version: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_event_contract(self) -> ControlEvent:
        errors: list[str] = []

        policy_sources = self.trusted_context.get("policy_sources")
        if policy_sources is not None and not (
            isinstance(policy_sources, list)
            and policy_sources
            and all(isinstance(item, str) and item.strip() for item in policy_sources)
        ):
            errors.append(
                "trusted_context.policy_sources must be a non-empty list of strings"
            )

        if self.event_type == "candidate_response" and not (
            self.candidate.text or self.candidate.claims
        ):
            errors.append("candidate_response requires text or structured claims")

        if self.event_type == "proposed_action":
            if not any(
                isinstance(value, str) and value.strip()
                for value in (self.candidate.operation, self.candidate.tool)
            ):
                errors.append("proposed_action requires an operation or tool")
            if self.use_case.startswith("engineering"):
                for field in ("environment", "authorized"):
                    if field not in self.trusted_context:
                        errors.append(
                            f"engineering proposed_action requires trusted_context.{field}"
                        )
                environment = self.trusted_context.get("environment")
                if environment is not None and environment not in {
                    "development",
                    "production",
                }:
                    errors.append(
                        "trusted_context.environment must be 'development' or 'production'"
                    )
                expected_environment = {
                    "engineering.development": "development",
                    "engineering.production": "production",
                }.get(self.use_case)
                if (
                    expected_environment is not None
                    and environment is not None
                    and environment != expected_environment
                ):
                    errors.append(
                        f"{self.use_case} requires trusted_context.environment="
                        f"'{expected_environment}'"
                    )
                if "authorized" in self.trusted_context and not isinstance(
                    self.trusted_context["authorized"], bool
                ):
                    errors.append("trusted_context.authorized must be a boolean")
                if self.trusted_context.get("environment") == "production":
                    for field in ("approval_present", "rollback_available"):
                        if field not in self.trusted_context:
                            errors.append(
                                "production proposed_action requires "
                                f"trusted_context.{field}"
                            )
                        elif not isinstance(self.trusted_context[field], bool):
                            errors.append(f"trusted_context.{field} must be a boolean")
            if self.use_case.startswith("support"):
                for field in ("identity_verified", "eligible", "approval_present"):
                    if field not in self.trusted_context:
                        errors.append(
                            f"support proposed_action requires trusted_context.{field}"
                        )
                    elif not isinstance(self.trusted_context[field], bool):
                        errors.append(f"trusted_context.{field} must be a boolean")

        if self.use_case.startswith("support"):
            for field in ("identity_verified", "eligible", "approval_present"):
                if field in self.trusted_context and not isinstance(
                    self.trusted_context[field], bool
                ):
                    message = f"trusted_context.{field} must be a boolean"
                    if message not in errors:
                        errors.append(message)

        if errors:
            raise ValueError("; ".join(errors))
        return self

    def fingerprint(self) -> str:
        if self.candidate.operation or self.candidate.tool:
            subject = self.candidate.operation or self.candidate.tool
        elif self.candidate.claims:
            subject = "+".join(sorted({claim.key for claim in self.candidate.claims}))
        else:
            subject = "unstructured_response"
        return f"{self.use_case}:{self.event_type}:{subject}".lower()
