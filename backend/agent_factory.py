from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastmcp.client import Client
from fastmcp.client.transports import StdioTransport
from openai import AsyncOpenAI
from pydantic_ai import Agent, RunContext, UsageLimits
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from .audit import AuditTrail, json_safe
from .models import AgentDependencies, AgentName


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
MODEL_NAME = "gpt-6-luna"
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"
MODEL_SETTINGS = {"max_tokens": 900, "openai_reasoning_effort": "none"}
RUN_LIMITS = UsageLimits(
    request_limit=4,
    tool_calls_limit=6,
    input_tokens_limit=6000,
    output_tokens_limit=900,
    total_tokens_limit=6900,
)
MAX_DELEGATIONS_PER_RUN = 3


def create_portkey_model() -> OpenAIChatModel:
    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.environ.get("PORTKEY_API_KEY", "").strip()
    if not api_key or api_key.lower() in {
        "your_portkey_api_key_here",
        "replace_me",
        "changeme",
    }:
        raise RuntimeError(
            "PORTKEY_API_KEY is missing or still a placeholder. Set a valid key in .env "
            "or in the process environment before building the agent team."
        )

    client = AsyncOpenAI(
        api_key="portkey",
        base_url=PORTKEY_BASE_URL,
        default_headers={"x-portkey-api-key": api_key},
        timeout=30,
        max_retries=1,
    )
    return OpenAIChatModel(
        MODEL_NAME,
        provider=OpenAIProvider(openai_client=client),
    )


def create_shop_toolset(audit: AuditTrail) -> MCPToolset[Any]:
    async def record_mcp_call(
        ctx: RunContext[AgentDependencies],
        call_tool: Any,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        current_agent = ctx.deps.path[-1].value
        audit.record(
            run_id=ctx.deps.run_id,
            actor=current_agent,
            event="mcp_tool.started",
            details={"tool_name": tool_name, "arguments": arguments},
        )
        try:
            result = await call_tool(tool_name, arguments)
        except Exception as error:
            audit.record(
                run_id=ctx.deps.run_id,
                actor=current_agent,
                event="mcp_tool.failed",
                details={
                    "tool_name": tool_name,
                    "error_type": type(error).__name__,
                    "error": str(error),
                },
            )
            raise
        audit.record(
            run_id=ctx.deps.run_id,
            actor=current_agent,
            event="mcp_tool.completed",
            details={"tool_name": tool_name, "output": json_safe(result)},
        )
        return result

    transport = StdioTransport(
        command="py",
        args=["-3", "-m", "mcp_server.server"],
        cwd=str(PROJECT_ROOT),
    )
    return MCPToolset(
        Client(transport, name="campus_customs_agent_team", timeout=60),
        process_tool_call=record_mcp_call,
        tool_error_behavior="error",
    )


async def ask_another_agent(
    ctx: RunContext[AgentDependencies],
    target_agent: AgentName,
    question: str,
) -> str:
    current_agent = ctx.deps.path[-1]
    if target_agent in ctx.deps.path:
        raise ValueError("That agent is already handling this request; avoid delegation loops.")
    if ctx.deps.delegation_budget.remaining <= 0:
        raise ValueError("The delegation limit for this request has been reached.")

    target = ctx.deps.agents.get(target_agent)
    if target is None:
        raise ValueError(f"Agent is not available: {target_agent.value}")

    ctx.deps.delegation_budget.remaining -= 1
    child_dependencies = replace(
        ctx.deps,
        path=(*ctx.deps.path, target_agent),
    )
    ctx.deps.audit.record(
        run_id=ctx.deps.run_id,
        actor=current_agent.value,
        event="agent.delegation.started",
        details={"target_agent": target_agent.value, "question": question},
    )
    try:
        result = await target.run(
            question,
            deps=child_dependencies,
            usage_limits=RUN_LIMITS,
        )
    except Exception as error:
        ctx.deps.audit.record(
            run_id=ctx.deps.run_id,
            actor=current_agent.value,
            event="agent.delegation.failed",
            details={
                "target_agent": target_agent.value,
                "error_type": type(error).__name__,
                "error": str(error),
            },
        )
        raise

    ctx.deps.audit.record(
        run_id=ctx.deps.run_id,
        actor=current_agent.value,
        event="agent.delegation.completed",
        details={"target_agent": target_agent.value, "response": result.output},
    )
    return result.output


def create_agent(
    name: AgentName,
    prompt_file: str,
    model: OpenAIChatModel,
    toolset: MCPToolset[Any],
) -> Agent[AgentDependencies, str]:
    prompt_path = PROMPTS_DIR / prompt_file
    instructions = prompt_path.read_text(encoding="utf-8")
    return Agent(
        model,
        name=name.value,
        instructions=instructions,
        deps_type=AgentDependencies,
        tools=[ask_another_agent],
        toolsets=[toolset],
        model_settings=MODEL_SETTINGS,
        retries=1,
        tool_timeout=30,
    )