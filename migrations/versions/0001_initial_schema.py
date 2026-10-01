"""Create the initial PostgreSQL application, telemetry and evaluation schema.

Revision ID: 0001_initial
Revises:
"""

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        CREATE TABLE conversations (
            id UUID PRIMARY KEY,
            user_id VARCHAR(255) NOT NULL,
            title VARCHAR(500),
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX ix_conversations_user_id ON conversations (user_id)")
    op.execute(
        """
        CREATE TABLE messages (
            id UUID PRIMARY KEY,
            conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            role VARCHAR(32) NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX ix_messages_conversation_id ON messages (conversation_id)")
    op.execute(
        """
        CREATE TABLE documents (
            id UUID PRIMARY KEY,
            owner_id VARCHAR(255),
            source TEXT,
            title VARCHAR(500) NOT NULL,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX ix_documents_owner_id ON documents (owner_id)")
    op.execute(
        """
        CREATE TABLE document_chunks (
            id UUID PRIMARY KEY,
            document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            embedding VECTOR(1536),
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
        )
        """
    )
    op.execute("CREATE INDEX ix_document_chunks_document_id ON document_chunks (document_id)")
    op.execute(
        """
        CREATE TABLE traces (
            trace_id VARCHAR(64) PRIMARY KEY,
            user_id VARCHAR(255),
            session_id VARCHAR(255),
            agent VARCHAR(255) NOT NULL,
            workflow VARCHAR(255),
            environment VARCHAR(64) NOT NULL,
            application_version VARCHAR(64) NOT NULL,
            started_at TIMESTAMPTZ NOT NULL,
            ended_at TIMESTAMPTZ,
            duration_ms DOUBLE PRECISION,
            status VARCHAR(32) NOT NULL,
            error TEXT
        )
        """
    )
    for column in ("user_id", "session_id", "agent", "environment", "started_at", "status"):
        op.create_index(f"ix_traces_{column}", "traces", [column])
    op.execute(
        """
        CREATE TABLE spans (
            span_id VARCHAR(64) PRIMARY KEY,
            trace_id VARCHAR(64) NOT NULL REFERENCES traces(trace_id) ON DELETE CASCADE,
            parent_span_id VARCHAR(64),
            span_type VARCHAR(64) NOT NULL,
            name VARCHAR(255) NOT NULL,
            started_at TIMESTAMPTZ NOT NULL,
            ended_at TIMESTAMPTZ,
            duration_ms DOUBLE PRECISION,
            status VARCHAR(32) NOT NULL,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
        )
        """
    )
    op.create_index("ix_spans_trace_id", "spans", ["trace_id"])
    op.create_index("ix_spans_span_type", "spans", ["span_type"])
    op.create_index("ix_spans_status", "spans", ["status"])
    op.execute(
        """
        CREATE TABLE llm_calls (
            id UUID PRIMARY KEY,
            trace_id VARCHAR(64) NOT NULL REFERENCES traces(trace_id) ON DELETE CASCADE,
            span_id VARCHAR(64),
            provider VARCHAR(128) NOT NULL,
            model VARCHAR(255) NOT NULL,
            input_tokens INTEGER,
            output_tokens INTEGER,
            total_tokens INTEGER,
            input_cost_estimated DOUBLE PRECISION,
            output_cost_estimated DOUBLE PRECISION,
            total_cost_estimated DOUBLE PRECISION,
            cost_is_estimated BOOLEAN NOT NULL DEFAULT TRUE,
            latency_ms DOUBLE PRECISION NOT NULL,
            prompt_version VARCHAR(128),
            request_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            error TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    for column in ("trace_id", "provider", "model", "created_at"):
        op.create_index(f"ix_llm_calls_{column}", "llm_calls", [column])
    op.execute(
        """
        CREATE TABLE tool_calls (
            id UUID PRIMARY KEY,
            trace_id VARCHAR(64) NOT NULL REFERENCES traces(trace_id) ON DELETE CASCADE,
            span_id VARCHAR(64),
            tool_name VARCHAR(255) NOT NULL,
            safe_input JSONB,
            safe_output JSONB,
            latency_ms DOUBLE PRECISION NOT NULL,
            status VARCHAR(32) NOT NULL,
            error TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    for column in ("trace_id", "tool_name", "status", "created_at"):
        op.create_index(f"ix_tool_calls_{column}", "tool_calls", [column])
    op.execute(
        """
        CREATE TABLE evaluation_datasets (
            id UUID PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            version VARCHAR(64) NOT NULL,
            description TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_evaluation_datasets_name_version UNIQUE (name, version)
        )
        """
    )
    op.create_index("ix_evaluation_datasets_name", "evaluation_datasets", ["name"])
    op.execute(
        """
        CREATE TABLE evaluation_cases (
            id UUID PRIMARY KEY,
            dataset_id UUID NOT NULL REFERENCES evaluation_datasets(id) ON DELETE CASCADE,
            input JSONB NOT NULL,
            expected_output JSONB,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
        )
        """
    )
    op.create_index("ix_evaluation_cases_dataset_id", "evaluation_cases", ["dataset_id"])
    op.execute(
        """
        CREATE TABLE evaluation_runs (
            id UUID PRIMARY KEY,
            dataset_id UUID NOT NULL REFERENCES evaluation_datasets(id),
            agent_version VARCHAR(128) NOT NULL,
            baseline_run_id UUID REFERENCES evaluation_runs(id),
            started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            finished_at TIMESTAMPTZ,
            total_cases INTEGER NOT NULL DEFAULT 0,
            passed_cases INTEGER NOT NULL DEFAULT 0,
            failed_cases INTEGER NOT NULL DEFAULT 0,
            overall_score DOUBLE PRECISION
        )
        """
    )
    op.create_index("ix_evaluation_runs_dataset_id", "evaluation_runs", ["dataset_id"])
    op.execute(
        """
        CREATE TABLE evaluation_scores (
            id UUID PRIMARY KEY,
            evaluation_run_id UUID NOT NULL REFERENCES evaluation_runs(id) ON DELETE CASCADE,
            case_id UUID NOT NULL REFERENCES evaluation_cases(id),
            evaluator VARCHAR(255) NOT NULL,
            score DOUBLE PRECISION NOT NULL,
            passed BOOLEAN NOT NULL,
            reason TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.create_index(
        "ix_evaluation_scores_evaluation_run_id",
        "evaluation_scores",
        ["evaluation_run_id"],
    )
    op.create_index("ix_evaluation_scores_case_id", "evaluation_scores", ["case_id"])
    op.execute(
        """
        CREATE TABLE model_pricing (
            id UUID PRIMARY KEY,
            provider VARCHAR(128) NOT NULL,
            model VARCHAR(255) NOT NULL,
            input_cost_per_million DOUBLE PRECISION NOT NULL,
            output_cost_per_million DOUBLE PRECISION NOT NULL,
            effective_from TIMESTAMPTZ NOT NULL,
            effective_until TIMESTAMPTZ,
            CONSTRAINT uq_model_pricing_provider_model_effective
                UNIQUE (provider, model, effective_from)
        )
        """
    )
    op.create_index("ix_model_pricing_provider", "model_pricing", ["provider"])
    op.create_index("ix_model_pricing_model", "model_pricing", ["model"])
    op.create_index("ix_model_pricing_effective_from", "model_pricing", ["effective_from"])


def downgrade() -> None:
    for table in (
        "model_pricing",
        "evaluation_scores",
        "evaluation_runs",
        "evaluation_cases",
        "evaluation_datasets",
        "tool_calls",
        "llm_calls",
        "spans",
        "traces",
        "document_chunks",
        "documents",
        "messages",
        "conversations",
    ):
        op.drop_table(table)
