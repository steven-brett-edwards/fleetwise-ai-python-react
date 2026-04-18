"""Async repositories -- one module per aggregate root.

These are plain modules of async functions, not classes. That's the
idiomatic Python equivalent of the .NET `I...Repository` / `...Repository`
pair -- the session is passed in as a parameter instead of constructor-
injected, which gives us clean testability (pytest fixture yields a
session) without a DI container.
"""
