"""FastAPI dependencies shared across routers.

`SessionDep` is the one every endpoint uses -- an `Annotated` alias keeps
router signatures short and gives tests a single key (`get_session`) to
override via `app.dependency_overrides`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from fleetwise.data.db import get_session

SessionDep = Annotated[AsyncSession, Depends(get_session)]
