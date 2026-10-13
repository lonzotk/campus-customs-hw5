from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from pydantic_ai import Agent

from .accounting import build_agent as build_accounting_agent
from .audit import AuditTrail
from .boss import build_agent as build_boss_agent
from .customer_service import build_agent as build_customer_service_agent
from .facilities import build_agent as build_facilities_agent
from .agent_factory import (
    MAX_DELEGATIONS_PER_RUN,
    RUN_LIMITS,
    create_portkey_model,
    create_shop_toolset,
)
from .inventory import build_agent as build_inventory_agent
from .models import AgentAnswer, AgentDependencies, AgentName, AgentRequest, DelegationBudget


@dataclass
class AgentTeam:
    agents: dict[AgentName, Agent[AgentDependencies, str]]
    audit: AuditTrail

    async def run(self, request: AgentRequest) -> AgentAnswer:
        run_id = uuid.uuid4().hex
        dependencies = AgentDependencies(
            audit=self.audit,
            agents=self.agents,
            run_id=run_id,
            path=(request.agent,),
            delegation_budget=DelegationBudget(MAX_DELEGATIONS_PER_RUN),
        )
        self.audit.record(
            run_id=run_id,
            actor=request.agent.value,
            event="agent.run.started",
            details={"prompt": request.prompt},
        )
        try:
            result = await self.agents[request.agent].run(
                request.prompt,
                deps=dependencies,
                usage_limits=RUN_LIMITS,
            )
        except Exception as error:
            self.audit.record(
                run_id=run_id,
                actor=request.agent.value,
                event="agent.run.failed",
                details={
                    "error_type": type(error).__name__,
                    "error": str(error),
                },
            )
            raise

        usage = result.usage
        self.audit.record(
            run_id=run_id,
            actor=request.agent.value,
            event="agent.run.completed",
            details={"response": result.output, "usage": usage},
        )
        return AgentAnswer(
            agent=request.agent,
            run_id=run_id,
            response=result.output,
        )


def build_team(audit_path: Path | None = None) -> AgentTeam:
    audit = AuditTrail(audit_path) if audit_path is not None else AuditTrail()
    model = create_portkey_model()
    shop_toolset = create_shop_toolset(audit)
    agents = {
        AgentName.BOSS: build_boss_agent(model, shop_toolset),
        AgentName.INVENTORY: build_inventory_agent(model, shop_toolset),
        AgentName.ACCOUNTING: build_accounting_agent(model, shop_toolset),
        AgentName.FACILITIES: build_facilities_agent(model, shop_toolset),
        AgentName.CUSTOMER_SERVICE: build_customer_service_agent(model, shop_toolset),
    }
    return AgentTeam(agents=agents, audit=audit)