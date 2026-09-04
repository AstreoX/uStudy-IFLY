"""Server-side runtime for isolated teacher presentation agents.

The package is intentionally independent from the application's normal agent
implementation.  It is copied into the presentation-agent image and talks to
the backend exclusively through a scoped capability gateway.
"""

from presentation_agent.models import AgentScope, RunCreateRequest, RunStatus

__all__ = ["AgentScope", "RunCreateRequest", "RunStatus"]
