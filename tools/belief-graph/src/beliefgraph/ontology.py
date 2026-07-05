"""Seed ontology of topics a software-project vision usually must decide.

Coverage gaps are computed against this list: a topic with little or no belief
coverage is something worth asking about. Callers can supply their own ontology;
this is a sensible default for scoping a software product.
"""

from __future__ import annotations

from .schema import Topic

PROJECT_VISION_ONTOLOGY: list[Topic] = [
    Topic(
        id="problem",
        name="Problem & Vision",
        description="What problem is being solved and for whom; the core thesis.",
        keywords=["problem", "vision", "goal", "why", "user", "audience", "pain"],
        importance=1.4,
    ),
    Topic(
        id="distribution",
        name="Distribution & Runtime",
        description="How the software is delivered and runs (desktop, web, CLI, service).",
        keywords=["electron", "desktop", "web", "runtime", "cli", "browser", "daemon", "process"],
    ),
    Topic(
        id="llm_providers",
        name="LLM Providers",
        description="Which model providers, abstraction, and defaults.",
        keywords=["llm", "model", "provider", "gemini", "openai", "anthropic", "ollama", "embedding"],
    ),
    Topic(
        id="data_storage",
        name="Data Storage",
        description="Persistence: databases, ORMs, file vs server storage.",
        keywords=["database", "storage", "sqlalchemy", "sqlite", "postgres", "orm", "persist", "schema"],
    ),
    Topic(
        id="vectors",
        name="Vector / Retrieval",
        description="Vector store and retrieval strategy for RAG.",
        keywords=["vector", "rag", "retrieval", "embedding", "pgvector", "index", "graphrag"],
    ),
    Topic(
        id="tools",
        name="Tools & Extensibility",
        description="Built-in tools, custom tools, execution sandbox.",
        keywords=["tool", "function", "sandbox", "subprocess", "venv", "plugin", "extend"],
    ),
    Topic(
        id="security",
        name="Security & Trust",
        description="Sandboxing, secrets, permissions, human-in-the-loop, autonomy.",
        keywords=["security", "secret", "permission", "sandbox", "trust", "autonomy", "approve", "credential"],
    ),
    Topic(
        id="ui_navigation",
        name="UI & Navigation",
        description="Layout, navigation model, surfaces, interaction.",
        keywords=["ui", "layout", "navigation", "surface", "panel", "gesture", "screen", "interaction"],
    ),
    Topic(
        id="design_language",
        name="Design Language",
        description="Visual style, design system, components.",
        keywords=["design", "style", "neumorphic", "theme", "component", "visual", "color"],
    ),
    Topic(
        id="agent_model",
        name="Agent / Flow Model",
        description="How agents are defined, communicate, loop, and are orchestrated.",
        keywords=["agent", "flow", "node", "orchestrator", "state", "graph", "loop", "async"],
    ),
    Topic(
        id="testing",
        name="Testing & Quality",
        description="Test strategy, CI, quality gates.",
        keywords=["test", "ci", "quality", "lint", "coverage", "pytest", "vitest"],
    ),
    Topic(
        id="deployment",
        name="Packaging & Deployment",
        description="How it is built, packaged, released, updated.",
        keywords=["deploy", "package", "build", "release", "installer", "update", "bundle"],
    ),
    Topic(
        id="observability",
        name="Observability",
        description="Logging, tracing, metrics, debugging agent runs.",
        keywords=["log", "trace", "metric", "observability", "debug", "monitor"],
    ),
    Topic(
        id="collaboration",
        name="Collaboration & Multi-user",
        description="Sharing, multi-user, sync, marketplace.",
        keywords=["collaboration", "multi-user", "share", "sync", "team", "marketplace"],
    ),
]


def default_ontology() -> list[Topic]:
    return list(PROJECT_VISION_ONTOLOGY)
