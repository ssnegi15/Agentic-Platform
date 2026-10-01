from typing import Any, Protocol


class Tool(Protocol):
    name: str

    async def execute(self, arguments: dict[str, Any]) -> Any: ...
