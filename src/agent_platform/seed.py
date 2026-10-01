import asyncio

from sqlalchemy import select

from agent_platform.db import session_factory
from agent_platform.models import EvaluationCase, EvaluationDataset


async def seed() -> None:
    async with session_factory()() as session:
        dataset = await session.scalar(
            select(EvaluationDataset).where(
                EvaluationDataset.name == "platform-smoke",
                EvaluationDataset.version == "1",
            )
        )
        if dataset is None:
            dataset = EvaluationDataset(
                name="platform-smoke",
                version="1",
                description="Minimal deterministic platform smoke evaluation.",
            )
            session.add(dataset)
            await session.flush()
            session.add(
                EvaluationCase(
                    dataset_id=dataset.id,
                    input={"message": "hello"},
                    expected_output={"message": "hello"},
                    metadata_json={"kind": "exact-match-smoke"},
                )
            )
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
