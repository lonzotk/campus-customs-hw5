from __future__ import annotations

import argparse
import asyncio

from .models import AgentName, AgentRequest
from .team import build_team


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run one Campus Customs agent request.")
    parser.add_argument("agent", choices=[agent.value for agent in AgentName])
    parser.add_argument("prompt", help="A question or task for the selected agent.")
    arguments = parser.parse_args()

    team = build_team()
    answer = await team.run(
        AgentRequest(agent=AgentName(arguments.agent), prompt=arguments.prompt)
    )
    print(answer.response)


if __name__ == "__main__":
    asyncio.run(main())