"""LangGraph / LangChain integration layer.

- `prompts.py` — system prompt constants (verbatim from .NET).
- `providers.py` — chat-model factory keyed on `settings.ai_provider`.
- `tools/` — `@tool`-decorated async functions; one module per .NET plugin.
- `agent.py` — prebuilt ReAct agent + `AsyncSqliteSaver` checkpointer.
"""
