from typing import Any

from pydantic_ai import Agent
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.models.openai import OpenAIChatModel

from .agent_factory import create_agent
from .models import AgentDependencies, AgentName


def build_agent(
    model: OpenAIChatModel, toolset: MCPToolset[Any]
) -> Agent[AgentDependencies, str]:
    return create_agent(AgentName.FACILITIES, "facilities.md", model, toolset)