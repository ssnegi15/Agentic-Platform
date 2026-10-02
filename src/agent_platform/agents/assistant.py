from agent_platform.agents.runtime import AgentRequest, AgentResponse, RunContext
from agent_platform.llm.base import LLMMessage, LLMRequest


class AssistantAgent:
    name = "assistant"
    prompt_version = "assistant-v1"

    def __init__(self, provider_name: str, model: str) -> None:
        self._provider_name = provider_name
        self._model = model

    async def run(self, request: AgentRequest, context: RunContext) -> AgentResponse:
        response = await context.complete_llm(
            self._provider_name,
            LLMRequest(
                model=self._model,
                messages=[
                    *request.history,
                    LLMMessage(role="user", content=request.message),
                ],
                metadata={"prompt_version": self.prompt_version},
            ),
        )
        return AgentResponse(message=response.content, metadata={"model": response.model})
