# FleetWise AI — .NET → Python migration guide

## Context

The .NET edition is shipped, deployed, and used for the AssetWorks application. The README already announces a Python parallel rewrite using FastAPI + LangGraph + Anthropic Claude as a separate repository; this is the detailed migration plan for that rewrite.

**Why a Python edition at all:**

1. **Portfolio breadth.** The AssetWorks stack is C#/Angular. Shipping the same product twice in two stacks — once in .NET + SK, once in Python + LangGraph + Anthropic — demonstrates that the interesting work (domain modeling, tool design, RAG, streaming UX, deployment) was deliberate, not accidentally tied to one stack.
2. **LangGraph fluency.** LangGraph is visible on a lot of job listings right now. A working LangGraph agent with four tools, persistent checkpointed conversations, and RAG is a more recruiter-legible signal than a generic chatbot.
3. **Anthropic-native.** The .NET version talks to OpenAI / Ollama / Groq. A Claude-backed version is a useful contrast: Claude's tool-use trace is different from OpenAI's function-calling, and that divergence is worth showing on paper.
4. **Fix three things we'd fix if we could.** The .NET version has three rough edges we can design around cleanly on the Python side:
   - Conversation history is a process-local `ConcurrentDictionary` — lost on restart. LangGraph's checkpointers solve this for free.
   - RAG re-ingests every boot. A persistent vector store (Chroma on a volume) means ingestion runs once.
   - The SSE format emits raw `data: {text}\n\n` without newline escaping; any chunk containing `\n` breaks the client's line-split parser. A better-shaped event stream is a one-line fix in Python.

**Intended outcome.** A Python API with the same HTTP contract the existing Angular frontend already speaks *plus* a new React + TypeScript frontend that consumes the same API — so a recruiter (Chatham in particular) sees a Python/FastAPI/React/LLM full-stack shipped end-to-end, while the existing Angular UI still works against the Python backend as a bonus. A live LangGraph agent with the same four tool areas, working RAG against the same five SOP documents, and parity-level tests in pytest. Deployed to Render (and documented for AWS), verifiable end-to-end in a browser.

---

## Chatham Financial alignment

This plan was tuned to the Chatham Financial Full Stack Engineer job description. Line-by-line alignment:

| Chatham requirement | Where in this plan |
|---|---|
| "Production Python using modern frameworks (FastAPI, etc.)" | Phases 0–4: FastAPI async routes, Pydantic v2, SQLAlchemy 2.x async. |
| "Clean architecture, solid design patterns, well-structured code" | Repo layout separates `domain / data / api / ai`, repositories with typed interfaces, Pydantic DTOs at the wire boundary. Design principles section locks this in before work starts. |
| "React or similar-based frontends that are clean, functional, and user-friendly" | **Phase 9** — new React + TypeScript + Vite frontend consuming the same API. This is the primary portfolio-visible frontend for the Python edition. |
| "Design and build APIs, services, and integrations" | Phase 2 (REST parity) + Phase 3 (LangGraph tool integrations against the data layer). |
| "SQL databases to design schemas, write queries, and manage data" | Phase 1: SQLAlchemy models, unique indexes, cascade rules, seed data, hybrid properties. |
| "LLM-powered applications: agent orchestration, extraction engines, tool-use patterns, AI-integrated workflows" | Phase 3 (prebuilt ReAct agent) + Phase 4 (hand-rolled StateGraph) + 13 tool-use functions + Phase 10 (optional extraction pipeline). |
| "RAG systems, prompt engineering" | Phase 5: Chroma persistent store, heading-based chunker, same-provider / fallback embedding strategy, prompt-conditional documentation stanza. |
| "Understanding of LLM strengths, limitations, and how to build reliable systems around them" | Phase 4's SSE framing fix, error-resilient streaming wrapper, conditional tool advertisement (the PR #14 lesson), `AsyncSqliteSaver` for persistent conversations. |
| "Active daily use of Claude Code / Codex / similar" | The README will include a "Built with Claude Code" section describing the agent-driven workflow used for this project, with commit message conventions and PR descriptions reflecting the collaboration. |
| "Cloud platforms (AWS, Azure, or GCP)" — preferred | Phase 6 includes a Render blueprint (primary) **and** an AWS deployment appendix (ECS Fargate + RDS + S3 for Chroma persistence), so the repo demonstrates cloud fluency without doubling deploy-maintenance effort. |
| "Data pipelines, ETL, working with unstructured data" — preferred | **Phase 10** (optional) adds a small ETL pipeline that ingests vehicle inspection CSVs, normalizes them, and loads them into the fleet database — unstructured-ish tabular data, with a Pydantic-driven extraction layer demonstrating the pattern. |
| "Own features end-to-end: architecture, implementation, testing, deployment" | Every phase is scoped as a complete deliverable with its own tests, its own commit, and its own verification step. Phase 0 ships to production before any feature code lands, so deploy is owned from day one. |
| "5+ years professional experience" | Met. |
| Financial-services domain | Not directly — FleetWise is a municipal-fleet app. But the architecture is directly transferable: a private-equity asset tracker with the same RAG-over-policy-docs + tool-use-over-structured-data pattern would be a rename, not a rewrite. Worth noting in the cover letter. |

---

## Assumptions to confirm in the morning

These are the decisions that would materially change the plan. I've picked defaults so the plan is complete; flag any to revisit before work starts.

| # | Assumption | Why it matters |
|---|---|---|
| 1 | **A new empty repo** (`fleetwise-ai-py` or similar) under your GitHub. Not merged into the .NET repo. | README says "separate repository"; the two deploys should be independently buildable. |
| 2 | **Python 3.12** as the floor. | 3.12 is stable + fast, 3.13 is fine but some ML packages lag. If you want 3.13, only the pyproject / CI image change. |
| 3 | **`uv`** as the package manager (not Poetry, not raw pip). | `uv` is ~10× faster on cold installs and the de-facto 2026 default. Docker layer cache also works cleanly with `uv sync --frozen`. |
| 4 | **New React + TypeScript + Vite frontend** is the primary UI for the Python edition. The existing Angular frontend is retained (points at either backend via env var) as a secondary/reference implementation, but the portfolio-visible client for the Python edition is React — matching Chatham's stack and giving the repo its own complete full-stack story. | React is an explicit Chatham requirement; shipping a React frontend is higher-signal than reusing Angular. Both frontends consuming the same FastAPI contract also demonstrates clean API boundaries. |
| 5 | **Claude Sonnet 4.5** for hosted demo, **Claude Haiku 4.5** for dev/cheap. | Sonnet has solid tool-use ergonomics and the latency is fine for chat. Haiku is the cost floor. Both support Anthropic-native tool use through `langchain-anthropic`. |
| 6 | **Provider swap retained:** Anthropic (hosted demo default), OpenAI, Ollama. Groq dropped — doesn't support Anthropic-shaped tool use and the .NET version was the place that demo lived. | Keeps local-first story intact (Ollama) and gives a credit-card-free fallback (OpenAI). |
| 7 | **Chroma persistent** for the vector store (on-disk, on a Render volume). | Simplest production-ready vector DB in Python, no external service, survives restarts. |

If any of these is wrong, say so in the morning and I'll redline the affected sections only.

---

## Target stack

| Layer | .NET edition | Python edition |
|---|---|---|
| HTTP | ASP.NET Core 9 controllers | FastAPI 0.115+ with async routes |
| Data | EF Core 9 + SQLite | SQLAlchemy 2.x async + aiosqlite |
| DTOs / validation | C# records + `JsonStringEnumConverter` | Pydantic v2 models with `use_enum_values` |
| AI orchestration | Semantic Kernel 1.74 | LangGraph 0.2+ prebuilt `create_react_agent`, upgrading to a hand-rolled `StateGraph` in phase 2 |
| LLM | OpenAI / Ollama / Groq via OpenAI connector | Claude via `langchain-anthropic`, plus `langchain-openai` + `langchain-ollama` shims |
| Tool calling | `[KernelFunction]` + `[Description]` attributes | `@tool` decorator (LangChain core) with typed pydantic arg schemas |
| Embeddings | `nomic-embed-text` (Ollama) / `text-embedding-3-small` (OpenAI) | `voyage-3` or `text-embedding-3-small` (Anthropic has no native embeddings endpoint — same constraint as Groq had, just named differently) |
| Vector store | `InMemoryVectorStore` (SK) | Chroma persistent (`chromadb` package), collection on a volume |
| Chat history | `ConcurrentDictionary<string, ChatHistory>` | LangGraph `SqliteSaver` checkpointer (or `AsyncSqliteSaver` for async) |
| Tests | xUnit + Moq + FluentAssertions | pytest + pytest-asyncio + httpx `AsyncClient` + pytest-mock |
| Coverage | coverlet + Cobertura | `coverage.py` + Codecov or artifact upload |
| Lint / format | `dotnet format` (implicit) | `ruff check` + `ruff format` + `mypy --strict` |
| CI | GitHub Actions, 2 jobs | GitHub Actions, 2 jobs (backend + React frontend) |
| Container | `mcr.microsoft.com/dotnet/aspnet:9.0` | `python:3.12-slim` multi-stage with `uv` |
| Deploy | Render Blueprint (OpenAI) | Render Blueprint primary (Anthropic) + AWS appendix (ECS Fargate + RDS + S3) |
| **Frontend (primary)** | Angular 21 | **React 18 + TypeScript + Vite + TanStack Query + Tailwind** — new, lives in `frontend/` of this repo |
| **Frontend (secondary)** | — | Existing Angular client can also point at this API (env-var swap); retained for comparison |

---

## Design principles (choose ahead of time, stop revisiting)

1. **API contract is stable.** The Python API is the source of truth. Both the new React frontend and the existing Angular frontend consume it via the same shapes. Internal Python code uses snake_case; the wire keeps PascalCase via Pydantic aliases so the Angular frontend works unchanged.
2. **Prebuilt first, hand-rolled second.** Phase 3 uses LangGraph's `create_react_agent` to get the tool-calling loop working in an hour. Phase 4 swaps to a custom `StateGraph` that adds one piece of custom routing (system-prompt conditional). That two-step is the recruiter-legible progression.
3. **Idiomatic Python at every layer.** Snake_case everywhere except at the wire boundary. Type hints everywhere. Async-first (`async def` routes, SQLAlchemy async session). No sync DB calls inside async routes.
4. **Integration tests for the two surfaces that always bite:** (a) SQLAlchemy → SQLite aggregation queries, (b) the SSE adapter's framing. Everything else is a fast unit test against a mocked LLM.
5. **One configuration source of truth:** environment variables via Pydantic Settings. No double layer of YAML + env vars like .NET's `appsettings.json` → env overrides. A `.env.example` at the repo root lists every knob.
6. **Deploy on day one.** A "hello world" FastAPI deploys to Render at the end of Phase 0 before any domain code is written. Deployment never becomes a big-bang cliff at the end.

---

## Repo layout (`fleetwise-ai-py/`)

```
fleetwise-ai-py/
├── README.md
├── pyproject.toml                 # uv-managed, project metadata, deps, tool config
├── uv.lock
├── .python-version                # "3.12"
├── .env.example                   # every env var documented
├── .github/workflows/ci.yml
├── Dockerfile
├── render.yaml
├── docker-compose.yml             # local stack (api + ollama)
├── data/
│   └── documents/                 # same 5 SOP markdown files, symlinked or copied from .NET repo
├── src/fleetwise/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app factory, CORS, startup hooks
│   ├── settings.py                # Pydantic Settings singleton
│   ├── domain/
│   │   ├── entities.py            # SQLAlchemy models
│   │   ├── enums.py               # FuelType, VehicleStatus, etc.
│   │   └── dto.py                 # Pydantic response models (FleetSummary, VehicleMaintenanceCost, …)
│   ├── data/
│   │   ├── db.py                  # engine, sessionmaker, get_session dependency
│   │   ├── seed.py                # 35-vehicle fleet seed logic
│   │   └── repositories/
│   │       ├── vehicle.py
│   │       ├── maintenance.py
│   │       ├── work_order.py
│   │       └── part.py
│   ├── api/
│   │   ├── deps.py                # FastAPI dependencies (session, agent)
│   │   ├── vehicles.py
│   │   ├── maintenance.py
│   │   ├── work_orders.py
│   │   └── chat.py                # sync + SSE stream endpoints
│   ├── ai/
│   │   ├── agent.py               # LangGraph StateGraph builder
│   │   ├── tools/
│   │   │   ├── fleet_query.py
│   │   │   ├── maintenance.py
│   │   │   ├── work_order.py
│   │   │   └── document_search.py
│   │   ├── providers.py           # Anthropic / OpenAI / Ollama chat model factory
│   │   ├── embeddings.py          # embedding provider factory
│   │   ├── rag/
│   │   │   ├── chunker.py         # heading-based chunking, parity with DocumentChunker.cs
│   │   │   ├── ingestion.py       # startup ingest into Chroma
│   │   │   └── vector_store.py    # Chroma persistent client factory
│   │   ├── prompts.py             # BASE_SYSTEM_PROMPT + DOCUMENTATION_STANZA constants
│   │   └── sse.py                 # async generator → SSE frame adapter
│   └── logging_config.py
└── tests/
    ├── conftest.py                # shared fixtures (app, client, db, fake_llm)
    ├── unit/
    │   ├── test_domain_enums.py
    │   ├── test_dto_serialization.py
    │   ├── test_repositories/     # mirrors each repo
    │   ├── test_tools/            # each tool tested with mock repo
    │   ├── test_chunker.py
    │   ├── test_sse_framing.py
    │   └── test_agent_routing.py
    └── integration/
        ├── test_api_vehicles.py   # httpx AsyncClient against real FastAPI
        ├── test_api_maintenance.py
        ├── test_api_work_orders.py
        ├── test_chat_sync.py      # with FakeListChatModel
        ├── test_chat_stream.py    # full SSE round-trip
        ├── test_sqlite_decimal.py # mirrors MaintenanceCostSqliteTests.cs
        └── test_rag_roundtrip.py  # real Chroma, fake embeddings, end-to-end search
```

---

## Phase 0 — Repo scaffold + hello-world deploy (30–45 min)

**Goal.** A bare FastAPI "hello world" running locally AND deployed to Render, so deploy machinery is working before any domain code exists. Catches Render-specific surprises (volume mounts, port bindings, build-command gotchas) early instead of during a crunch.

**Deliverables.**
- `pyproject.toml` with `fastapi[standard]`, `uvicorn`, `pydantic-settings`, `ruff`, `mypy`, `pytest`, `pytest-asyncio`, `httpx`.
- `src/fleetwise/main.py` with `GET /api/health` → `{"status": "ok"}`.
- `Dockerfile` (multi-stage, `uv` for deps, final image from `python:3.12-slim`).
- `render.yaml` with one service pointing at the Dockerfile, `healthCheckPath: /api/health`.
- `.github/workflows/ci.yml` running `uv sync`, `ruff check`, `ruff format --check`, `mypy`, `pytest`.
- Push to GitHub, import as Render Blueprint, confirm the `/api/health` endpoint returns 200 publicly.

**Verification.** `curl https://fleetwise-py.onrender.com/api/health` returns `{"status":"ok"}`.

**Commit.** `(chore): scaffold FastAPI project with CI and Render deploy`

---

## Phase 1 — Domain model + data layer (1–2 days)

**Goal.** SQLAlchemy models that mirror the .NET entities exactly, async repositories that mirror the .NET repository interfaces method-for-method, and a seed module that replays the 35-vehicle fleet at startup.

### 1a. Enums & entities (`src/fleetwise/domain/`)

- `enums.py`: Python `StrEnum` subclasses for `FuelType`, `VehicleStatus`, `WorkOrderStatus`, `Priority`, `MaintenanceType`. Values must match the .NET string serialization (`"Active"`, `"Diesel"`, etc.) — the frontend parses these strings.
- `entities.py`: SQLAlchemy 2.x `DeclarativeBase` subclasses for `Vehicle`, `MaintenanceRecord`, `MaintenanceSchedule`, `WorkOrder`, `Part`. Column types:
  - `Numeric(18, 2)` for money fields (`acquisition_cost`, `cost`, `total_cost`, `unit_cost`) — matches .NET's `precision(18, 2)`.
  - `Numeric(8, 2)` for `labor_hours`.
  - `Mapped[FuelType] = mapped_column(SQLEnum(FuelType, native_enum=False))` — stored as strings, not SMALLINT, to match .NET's `.HasConversion<string>()`.
  - Unique indexes on `Vehicle.asset_number`, `Vehicle.vin`, `WorkOrder.work_order_number`, `Part.part_number`.
  - Cascade rules: `ondelete="CASCADE"` on `Vehicle → MaintenanceSchedule/MaintenanceRecord/WorkOrder`, `ondelete="SET NULL"` on `WorkOrder ← MaintenanceRecord`.
  - `is_overdue` as a Python `@hybrid_property` (computed, not persisted).

### 1b. Session management (`src/fleetwise/data/db.py`)

- One `async_sessionmaker` + an `async def get_session() -> AsyncIterator[AsyncSession]` FastAPI dependency.
- Engine URL from `settings.database_url`, default `sqlite+aiosqlite:///./fleetwise.db`.
- Startup hook in `main.py` calls `Base.metadata.create_all()` then `seed_if_empty(session)`.

### 1c. Seed data (`src/fleetwise/data/seed.py`)

Port the .NET `SeedData.Initialize` verbatim: 35 vehicles, 45 parts, 36 work orders, 163 maintenance records, 54 maintenance schedules, with the same 7 parts seeded below reorder threshold. Keep the same asset numbers (`V-2019-0042`, etc.) so screenshots and demo scripts remain meaningful across both editions.

**Practical tip:** the fastest way to port this is to run the .NET app once, dump the SQLite tables as JSON via a one-shot script, then have the Python seed read that JSON. Avoids translating 300 lines of C# data literals by hand and guarantees exact parity. Commit the dump alongside the seed module.

### 1d. Repositories (`src/fleetwise/data/repositories/`)

One module per aggregate, methods in snake_case matching the .NET interfaces. For `vehicle.py`:

```python
async def get_all(
    session: AsyncSession,
    status: VehicleStatus | None = None,
    department: str | None = None,
    fuel_type: FuelType | None = None,
) -> list[Vehicle]: ...

async def get_by_id(session: AsyncSession, id: int) -> Vehicle | None: ...
async def get_by_asset_number(session: AsyncSession, asset_number: str) -> Vehicle | None: ...
async def search(...) -> list[Vehicle]: ...
async def get_fleet_summary(session: AsyncSession) -> FleetSummary: ...
async def get_vehicles_by_maintenance_cost(session: AsyncSession, top_n: int = 10) -> list[VehicleMaintenanceCost]: ...
```

**The SQLite-decimal-ORDER-BY trap.** SQLAlchemy + aiosqlite actually translates `GROUP BY + SUM(Numeric) + ORDER BY` fine — the EF bug was EF-specific. But still port the in-memory aggregation implementation as an explicit choice and pin it with integration tests (see Phase 7). The dataset is small, the pattern is straightforward, and the test safety net is the actual point.

**Deliverables.** Full domain + data layer, seed-on-startup, dev DB (`fleetwise.db`) created automatically on first run.

**Verification.**
```bash
uv run python -c "import asyncio; from fleetwise.data.seed import count; print(asyncio.run(count()))"
# → 35 vehicles, 45 parts, 36 work orders, 163 maintenance records
```

**Commit.** `(feat): port domain entities, repositories, and seed data from .NET`

---

## Phase 2 — REST API parity (1 day)

**Goal.** All non-chat endpoints live, returning identical JSON shapes to the .NET version. Point the Angular frontend at the Python API and confirm every view still renders.

### 2a. Pydantic response DTOs (`src/fleetwise/domain/dto.py`)

Pydantic models with `ConfigDict(alias_generator=to_pascal, populate_by_name=True)` so the wire format is PascalCase (matches .NET) while Python code uses snake_case. One model per response shape:

- `VehicleResponse`, `VehicleListResponse`
- `MaintenanceRecordResponse`
- `WorkOrderResponse`
- `FleetSummaryResponse` (with `total_vehicles`, `by_status`, `by_fuel_type`, `by_department`)
- `VehicleMaintenanceCostResponse`
- `MaintenanceCostGroupResponse`
- `ChatRequest`, `ChatResponse`, `OverdueScheduleResponse`, `UpcomingScheduleResponse`

### 2b. Routers (`src/fleetwise/api/`)

One router per resource, mounted under `/api` in `main.py`:

| Router | Path | Endpoints |
|---|---|---|
| `vehicles.py` | `/api/vehicles` | `GET /` (filters: status, department, fuel_type), `GET /{id}`, `GET /{id}/maintenance`, `GET /{id}/work-orders`, `GET /summary` |
| `maintenance.py` | `/api/maintenance` | `GET /overdue`, `GET /upcoming?days=30&miles=5000` |
| `work_orders.py` | `/api/work-orders` | `GET /` (filter: status), `GET /{id}` |

Route ordering matters: `GET /vehicles/summary` must be declared before `GET /vehicles/{id:int}` so FastAPI's path matching takes the literal before the typed param (mirrors the .NET convention). 404 behavior via `raise HTTPException(status_code=404)`.

### 2c. CORS middleware

`fastapi.middleware.cors.CORSMiddleware` with `allow_origins=settings.cors_allowed_origins`, a list parsed from env like `CORS_ALLOWED_ORIGINS="https://fleetwise-frontend.onrender.com,http://localhost:4200"`.

### 2d. JSON encoder quirks

- `datetime` fields: use Pydantic's default `.isoformat()` — already produces the `2026-03-15T00:00:00` shape the Angular code parses.
- `Decimal` fields: the .NET JSON serializes decimals as JSON numbers. Pydantic v2 serializes `Decimal` as strings by default; override with a field serializer so the wire format matches (`Field(..., json_schema_extra={...})` + custom serializer).

**Verification.** Start the Python API on `:5100`. Edit the Angular `environment.ts` to point there. Walk dashboard, vehicle list, vehicle detail, work orders list, work order detail. Every screen renders identically to the .NET-backed version. (Chat endpoint not live yet — skip that view for now.)

**Commit.** `(feat): port REST API endpoints with pydantic DTOs and CORS`

---

## Phase 3 — LangGraph agent, prebuilt path (2 days)

**Goal.** Working `/api/chat` endpoint backed by LangGraph's prebuilt ReAct agent calling all four tool areas, with Claude Sonnet 4.5 as the default model.

### 3a. Tool definitions (`src/fleetwise/ai/tools/`)

Every .NET `[KernelFunction]` becomes an `@tool`-decorated async function with a typed pydantic args schema. Example:

```python
from pydantic import BaseModel, Field
from langchain_core.tools import tool

class SearchVehiclesArgs(BaseModel):
    make: str | None = Field(None, description="Filter by make (e.g., Ford, Chevrolet)")
    model: str | None = Field(None, description="Filter by model (e.g., F-150, Silverado)")
    department: str | None = Field(None, description="Filter by department (e.g., Public Works, Parks and Recreation)")
    status: VehicleStatus | None = Field(None, description="Filter by status: Active, InShop, OutOfService, Retired")
    fuel_type: FuelType | None = Field(None, description="Filter by fuel type: Gasoline, Diesel, Electric, Hybrid, CNG")

@tool("search_vehicles", args_schema=SearchVehiclesArgs)
async def search_vehicles(make=None, model=None, department=None, status=None, fuel_type=None) -> str:
    """Search vehicles by make, model, department, status, or fuel type. All filters optional."""
    async with SessionLocal() as session:
        results = await vehicle_repo.search(session, make, model, department, status, fuel_type)
    return _format_vehicle_list(results)  # returns the same prefatory-line + indented JSON the .NET does
```

**All 13 functions** are ported with the same names, same arg descriptions (lifted verbatim from the `[Description]` attributes — these are the LLM's only guidance), and the same "Found N results / JSON payload" return shape. Consistent return shape matters: Claude's tool-use loop is sensitive to how the tool result looks, and matching the .NET format gives us a known-good baseline to compare against.

**Tool grouping.** Tools are exported as four lists (`fleet_query_tools`, `maintenance_tools`, `work_order_tools`, `document_search_tools`) so the agent can be built with a subset — matters for the conditional RAG case in Phase 5.

### 3b. Provider factory (`src/fleetwise/ai/providers.py`)

```python
def build_chat_model(settings: Settings) -> BaseChatModel:
    match settings.ai_provider:
        case "anthropic":
            return ChatAnthropic(model=settings.anthropic_chat_model, api_key=settings.anthropic_api_key)
        case "openai":
            return ChatOpenAI(model=settings.openai_chat_model, api_key=settings.openai_api_key)
        case "ollama":
            return ChatOllama(model=settings.ollama_chat_model, base_url=settings.ollama_endpoint)
        case _:
            raise ValueError(f"Unknown ai_provider: {settings.ai_provider}")
```

### 3c. Agent (`src/fleetwise/ai/agent.py`)

Prebuilt ReAct agent with a SQLite checkpointer for persistent conversation history:

```python
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

async def build_agent(settings: Settings):
    model = build_chat_model(settings)
    tools = [*fleet_query_tools, *maintenance_tools, *work_order_tools]  # document_search added in Phase 5
    checkpointer = AsyncSqliteSaver.from_conn_string(settings.checkpoint_db_url)
    return create_react_agent(model, tools, checkpointer=checkpointer, prompt=BASE_SYSTEM_PROMPT)
```

`conversation_id` from the HTTP request maps to `config={"configurable": {"thread_id": conversation_id}}` — LangGraph's native conversation-persistence key. This is the improvement over the .NET `ConcurrentDictionary`: conversations survive restarts because the checkpointer writes to the same volume-mounted SQLite file.

### 3d. Chat router (`src/fleetwise/api/chat.py`)

`POST /api/chat` invokes the agent, extracts tool-call names from the message trace (LangGraph stores them in `ToolMessage.name`), returns `ChatResponse` with the final AI message content + `functions_used` (aliased to `functionsUsed` for wire parity).

**Verification.**
- Unit: tool functions called directly with mocked repo → return the expected formatted strings.
- Integration: `POST /api/chat` with a `FakeListChatModel` that scripts "call search_vehicles → return text" → response body has `response`, `conversationId`, `functionsUsed=["search_vehicles"]`.
- Live: deploy, hit from Angular chat view with Anthropic key in env, ask "Which vehicles are in the Public Works department?" — gets an answer grounded in the seeded fleet.

**Commit.** `(feat): LangGraph ReAct agent with three tool plugins and Anthropic Claude`

---

## Phase 4 — Custom StateGraph + streaming SSE (1.5 days)

**Goal.** Replace the prebuilt agent with a hand-rolled `StateGraph`, then add the SSE streaming endpoint that matches the Angular client's expectations exactly.

### 4a. Hand-rolled StateGraph (`src/fleetwise/ai/agent.py`)

Two nodes and one conditional edge — minimal, but fully explicit:

```
START → agent_node (LLM call with tools bound)
         ├─→ tool_node (executes any tool_calls in the last AIMessage)
         │      └─→ agent_node  (loop until LLM emits no more tool calls)
         └─→ END (when AIMessage has no tool_calls)
```

Why hand-roll it when prebuilt works: two reasons specific to this app.

1. **Conditional system prompt.** The .NET fix that earned PR #14 — only advertising `search_fleet_documentation` when the DocumentSearch plugin is actually wired up — is cleaner to express as a pre-agent node that selects the prompt based on `settings.rag_enabled`. With `create_react_agent` it's a bit of prompt-template gymnastics; with a custom graph it's one function.
2. **Recruiter legibility.** A 40-line `StateGraph` file reads like a diagram. A single `create_react_agent` call doesn't signal "I know how LangGraph works" the same way.

State schema is a TypedDict with `messages: Annotated[list[BaseMessage], add_messages]` and `functions_used: list[str]`, plus a reducer that appends tool names as `ToolMessage`s land.

### 4b. Streaming endpoint (`src/fleetwise/api/chat.py` + `src/fleetwise/ai/sse.py`)

LangGraph exposes `agent.astream_events(input, config, version="v2")` which yields `on_chat_model_stream` events containing `chunk.content`. Map those to SSE frames.

**SSE framing fix.** The .NET server emits `data: {chunk}\n\n` raw. If `chunk` contains `\n`, that newline terminates the SSE event mid-chunk and the Angular client's line-split parser produces garbage. In Python we fix this cleanly:

```python
async def to_sse_frames(events: AsyncIterator[StreamEvent]) -> AsyncIterator[str]:
    async for event in events:
        if event["event"] == "on_chat_model_stream":
            chunk = event["data"]["chunk"].content
            if not chunk:
                continue
            # Escape newlines so multi-line chunks don't break the client's event framing.
            # Each chunk is a single SSE `data:` line; the client unescapes before rendering.
            escaped = chunk.replace("\\", "\\\\").replace("\n", "\\n")
            yield f"data: {escaped}\n\n"
    yield "data: [DONE]\n\n"
```

Matching frontend change: in `chat.service.ts`, unescape `\\n` → `\n` and `\\\\` → `\\` before `subscriber.next(data)`. That's a 2-line edit on the Angular side, safe to apply to both backends at once. Note this as a trivial sibling PR in the .NET repo rather than a Python-only concern.

### 4c. Error-resilient streaming

Port the `SafeStreamChunksAsync` wrapper's intent — catch exceptions mid-stream, emit `data: *An error occurred: {msg}*\n\n` instead of tearing down the response. In Python this is an async generator with a `try/except` around the inner `async for`. Specifically catch `asyncio.CancelledError` and re-raise (client disconnect is not an error).

**Verification.**
- Unit: feed synthetic `on_chat_model_stream` events into `to_sse_frames`, assert frame output is well-formed.
- Unit: feed an event generator that raises mid-stream, assert error frame emitted and stream closes cleanly.
- Integration: POST to `/api/chat/stream` with `FakeListChatModel` that yields chunks containing `\n`. Read raw response bytes, assert `\\n` appears in the wire but not raw `\n` inside a `data:` line.
- Live: Angular chat view receives streamed tokens the same way it does from the .NET backend.

**Commit.** `(feat): custom LangGraph StateGraph with streaming SSE endpoint`

---

## Phase 5 — RAG pipeline (1 day)

**Goal.** DocumentSearch tool live, Chroma persistent on a volume, ingestion runs once at startup and is skipped on subsequent boots when the collection is already populated.

### 5a. Chunker (`src/fleetwise/ai/rag/chunker.py`)

Port `DocumentChunker.ChunkByHeadings` literally: split on `## `, keep sections ≤ 500 chars as-is, sub-split larger sections by `\n\n`, re-prefix `## ` on subsequent sections. Heading-based chunking preserves SOP section boundaries in the retrieval output (the .NET version's citations look clean because of this; we want identical behavior).

Alternative considered + rejected: `RecursiveCharacterTextSplitter` from LangChain. Generic, produces smaller but less semantically coherent chunks. Portfolio project benefits more from a hand-rolled chunker that mirrors the domain shape.

### 5b. Embedding provider (`src/fleetwise/ai/embeddings.py`)

```python
def build_embeddings(settings) -> Embeddings | None:
    match settings.ai_provider:
        case "anthropic":
            # Anthropic doesn't offer embeddings; default to Voyage or fall back to OpenAI's small model
            # if VOYAGE_API_KEY is absent.
            if settings.voyage_api_key:
                return VoyageEmbeddings(model="voyage-3", api_key=settings.voyage_api_key)
            return OpenAIEmbeddings(model="text-embedding-3-small", api_key=settings.openai_api_key)
        case "openai":
            return OpenAIEmbeddings(...)
        case "ollama":
            return OllamaEmbeddings(model=settings.ollama_embedding_model, base_url=settings.ollama_endpoint)
```

Return `None` only if neither a same-provider nor fallback embedding source is available — in which case RAG is cleanly disabled and the system prompt adapts (the Phase 4 graph already branches on `settings.rag_enabled`).

### 5c. Vector store (`src/fleetwise/ai/rag/vector_store.py`)

```python
def build_vector_store(embeddings, settings) -> Chroma:
    return Chroma(
        collection_name="fleet-documents",
        embedding_function=embeddings,
        persist_directory=settings.chroma_persist_dir,  # /app/data/chroma on Render
    )
```

### 5d. Ingestion (`src/fleetwise/ai/rag/ingestion.py`)

Called from `main.py` startup hook. Walks `data/documents/*.md`, chunks each, embeds, upserts to Chroma with ID `{filename}_{i}`. Skip if `vector_store._collection.count() > 0` — on Render the collection survives restarts and doesn't need re-embedding.

### 5e. DocumentSearch tool (`src/fleetwise/ai/tools/document_search.py`)

```python
@tool("search_fleet_documentation", args_schema=DocSearchArgs)
async def search_fleet_documentation(query: str, top_k: int = 3) -> str:
    results = await vector_store.asimilarity_search_with_score(query, k=top_k)
    return _format_doc_results(results)  # same "--- Source: X (relevance: Y) ---" shape as .NET
```

Description string lifted verbatim from the .NET version, including the `Do NOT use this for...` anti-patterns block. These directives are doing real work in the tool-choice loop — don't paraphrase.

**Verification.**
- Unit: chunker tests mirror `DocumentChunkerTests.cs` (28 tests).
- Integration: ingest into Chroma in-memory, search "anti-idling policy", assert top hit is `fuel-management-policy.md` with score > 0.4.
- Live: deploy, chat "What's the anti-idling policy?" — response cites the relevant SOP section, matching the .NET live-demo behavior.

**Commit.** `(feat): RAG pipeline with Chroma persistent store and DocumentSearch tool`

---

## Phase 6 — Provider swap + Render deploy finalization (half day)

**Goal.** Clean `AiProvider` env-var swap, `render.yaml` updated, dashboard-prompted Anthropic key wired, live demo URL added to README.

### 6a. `render.yaml`

```yaml
services:
  - type: web
    name: fleetwise-py-api
    runtime: docker
    plan: free
    dockerfilePath: ./Dockerfile
    healthCheckPath: /api/health
    disk:
      name: fleetwise-data
      mountPath: /app/data
      sizeGB: 1
    envVars:
      - key: AI_PROVIDER
        value: anthropic
      - key: ANTHROPIC_CHAT_MODEL
        value: claude-sonnet-4-5
      - key: ANTHROPIC_API_KEY
        sync: false
      - key: OPENAI_EMBEDDING_MODEL
        value: text-embedding-3-small
      - key: OPENAI_API_KEY
        sync: false  # needed for embeddings even when chat is Anthropic
      - key: DATABASE_URL
        value: sqlite+aiosqlite:///app/data/fleetwise.db
      - key: CHROMA_PERSIST_DIR
        value: /app/data/chroma
      - key: CHECKPOINT_DB_URL
        value: /app/data/checkpoints.db
      - key: CORS_ALLOWED_ORIGINS
        value: https://fleetwise-frontend.onrender.com,http://localhost:4200
```

One disk mount at `/app/data` covers three things: fleet DB, Chroma collection, LangGraph checkpointer. All three persist across restarts — every "idle → wake" on Render's free tier is now instant to first useful response (no re-ingestion).

### 6b. Angular frontend switch

Add `environment.py.ts` variant pointing at `https://fleetwise-py-api.onrender.com`. Don't overwrite the .NET-backed env — keep both so you can demo both with an env swap at build time. Consider wiring a prominent "backend: .NET | Python" toggle in the UI if time permits (big recruiter signal).

**Verification.** Paste keys into Render dashboard, redeploy, confirm health check passes, walk every screen, run the same Q1–Q5 transcript you used to verify PR #15.

**Commit.** `(chore): Render blueprint + disk-backed persistent storage`

---

## Phase 7 — Tests + CI to parity (1.5–2 days)

**Goal.** Match the .NET test posture: unit tests around 100% on tools / services / repositories, integration tests covering the API surface and the specific SQLite bug class that bit us on .NET.

### 7a. Fixtures (`tests/conftest.py`)

- `event_loop` (function-scoped, per pytest-asyncio best practice).
- `test_db` → in-memory aiosqlite engine + `create_all` + seeded fixture data; yields `AsyncSession`.
- `app` → FastAPI instance with `get_session` dependency-overridden to `test_db`.
- `client` → `httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")`.
- `fake_llm` → `FakeListChatModel` or custom `BaseChatModel` stub that returns scripted messages including scripted `tool_calls`.
- `fake_embeddings` → deterministic embeddings (hash-based) so RAG tests are reproducible without a live embedding API.

### 7b. Unit tests (pytest)

One test module per module under `src/fleetwise/`. Target parity with the .NET breakdown:

- **Tools (four modules, ~80 tests).** Each tool called directly with mocked repo, asserts the returned string has the expected "Found N results" preamble + JSON payload. Edge cases: empty result sets, invalid asset numbers, top_n = 0.
- **Repositories (four modules, ~60 tests).** Against the in-memory SQLite fixture. Each method × each filter combination.
- **Agent routing (~10 tests).** Build the graph with `fake_llm`, feed scripted responses, assert the tool_node/agent_node transitions land as expected.
- **Chunker (~28 tests).** Direct port of `DocumentChunkerTests.cs`.
- **SSE framing (~15 tests).** Synthetic event streams in → frame strings out. Escape-handling, `[DONE]` emission, error-frame handling on exception.

### 7c. Integration tests (pytest + httpx)

- **API routes.** Every endpoint, happy path + 404 path. Body shapes asserted with `response.json()` compared against exact expected dicts — wire-format regressions caught immediately.
- **Chat sync.** `POST /api/chat` with `fake_llm` scripted to call `get_fleet_summary`; assert `functionsUsed == ["get_fleet_summary"]`.
- **Chat stream.** `POST /api/chat/stream`, read raw bytes, verify `data: ...\n\n` framing, `[DONE]` terminator, no unescaped `\n` inside a chunk.
- **SQLite-decimal regression.** The equivalent of `MaintenanceCostSqliteTests.cs` — exercise every query that does `GROUP BY + SUM(Numeric) + ORDER BY` against real SQLite, pin the ordering. This is the test pyramid fix we learned from on the .NET side; not skipping it here.
- **RAG round-trip.** Real Chroma in-memory, fake embeddings, ingest one doc, search for a term, assert the chunk comes back.

### 7d. CI (`.github/workflows/ci.yml`)

```yaml
- uses: astral-sh/setup-uv@v4
- run: uv sync --frozen
- run: uv run ruff check .
- run: uv run ruff format --check .
- run: uv run mypy src/
- run: uv run pytest --cov=fleetwise --cov-report=xml --cov-fail-under=90
- uses: actions/upload-artifact@v4
  with: { name: python-coverage, path: coverage.xml }
```

One job — no frontend to run separately. Coverage floor set to 90% so it's an enforced ratchet without being brittle about the 3% of boilerplate that isn't worth testing.

**Verification.** Green CI, pytest shows the expected test counts split by unit/integration.

**Commit.** `(test): pytest + httpx integration suite with SQLite regression coverage`

---

## Phase 8 — README + portfolio polish (half day)

- Python-repo README with architecture Mermaid, live demo URL, tech stack table paralleling the .NET one, "Running Locally" section with `uv sync && uv run uvicorn fleetwise.main:app --reload`.
- Link both repos from each other (".NET edition" / "Python edition" callouts at the top).
- In the .NET repo's "Coming Next" section, replace the generic "Python edition" line with a specific link and a one-sentence summary of what's different ("LangGraph agent with persistent conversation history and Chroma-backed RAG").

**Commit.** `(docs): Python-edition README with live demo + cross-repo links`

---

## Phase 9 — React frontend (2–3 days)

**Goal.** A new React + TypeScript frontend living in `frontend/` of this repo, consuming the same FastAPI backend, with the same views the Angular app has today. This is the primary portfolio-facing UI for the Python edition and the specific Chatham-stack signal (React, TypeScript, API integration).

### 9a. Scaffold

- `npm create vite@latest frontend -- --template react-ts`
- Add: `@tanstack/react-query` (server state), `react-router-dom` v7 (routing), `tailwindcss` v4 (styling), `lucide-react` (icons), `clsx` + `tailwind-merge` (class composition), `zod` (runtime response validation at the API boundary).
- ESLint + Prettier + Vitest + React Testing Library for parity with the Python `ruff` + `pytest` story.

### 9b. Layout

Six routes mirroring the Angular app:

| Route | View |
|---|---|
| `/` | Dashboard: fleet summary cards, overdue maintenance list, upcoming maintenance list |
| `/vehicles` | Vehicle list with filters (status / department / fuel type) |
| `/vehicles/:assetNumber` | Vehicle detail with maintenance history and work-order tabs |
| `/work-orders` | Work order list with status filter |
| `/work-orders/:id` | Work order detail |
| `/chat` | Streaming chat UI with conversation sidebar |

Persistent app shell with a sidenav, mobile-responsive via Tailwind breakpoints. Same visual parity targets as the Angular app — no design novelty, just clean, idiomatic React.

### 9c. API client (`frontend/src/api/`)

A small typed client built around `fetch` + `zod`:

```ts
const VehicleSchema = z.object({
  id: z.number(),
  assetNumber: z.string(),
  // ...
});
export type Vehicle = z.infer<typeof VehicleSchema>;

export async function getVehicles(filters?: VehicleFilters): Promise<Vehicle[]> {
  const res = await fetch(`${API_BASE}/vehicles?${qs(filters)}`);
  return z.array(VehicleSchema).parse(await res.json());
}
```

Wrapped in TanStack Query hooks (`useVehicles`, `useVehicle`, etc.) for caching, stale-while-revalidate, and loading/error states.

### 9d. Chat view

- `useConversation(conversationId)` manages message history in React state.
- `streamMessage` uses `fetch` + `ReadableStream` + a `TextDecoderStream` to parse SSE frames exactly as the Angular service does, including the newline-escape reversal from Phase 4.
- Tool-call indicator renders a collapsible "Called functions: [search_vehicles, …]" badge under the assistant message — higher-fidelity UX than the Angular app currently has.

### 9e. Tests

- Unit: zod schemas reject malformed responses (wire-format regression gate).
- Component: each view renders happy path + loading + error, TanStack Query mocked via MSW (Mock Service Worker).
- Integration: end-to-end happy path with MSW serving canned API responses — no real backend.
- Coverage floor: 85%.

### 9f. Build + deploy

- Vite production build outputs to `frontend/dist/`.
- Render static site pointing at this directory, or served by FastAPI via `StaticFiles` mount (simpler for demo, single Render service, same origin so no CORS in prod).
- Decision: **serve via FastAPI** for the Python edition — one service is cheaper on free tier and removes a CORS surface area. Document both options in the README.

**Verification.**
- `npm run build` succeeds.
- `npm run test` green, coverage ≥ 85%.
- `npm run dev` + backend running locally — walk every route, each view renders against live seeded data.
- Chat view streams tokens end-to-end from the Python backend.

**Commit.** `(feat): React + TypeScript + Vite frontend with TanStack Query and SSE chat`

---

## Phase 10 — Optional: ETL pipeline for inspection CSVs (1–1.5 days)

**Goal.** A small unstructured-data ingestion path that demonstrates the exact thing Chatham's "data pipelines, ETL, working with unstructured data" bullet asks for. Lifts FleetWise from "AI chat over a canned dataset" to "pipeline that accepts messy external inputs and normalizes them."

### 10a. Synthetic input

Generate 10–20 "vehicle inspection CSV" files in `data/inspections/` — real-world-messy: inconsistent column names (`Vehicle ID` vs `asset_number` vs `unit_no`), mixed date formats, free-text condition notes. This is the "unstructured-ish" input the pipeline normalizes.

### 10b. Pipeline (`src/fleetwise/etl/`)

```
src/fleetwise/etl/
├── __init__.py
├── schema.py           # pydantic model: NormalizedInspection
├── extractors/
│   ├── csv_loader.py   # pandas or polars read + basic type coercion
│   └── llm_mapper.py   # Claude-powered column-mapping for unknown headers
├── transform.py        # dedup, validate VIN against fleet DB, flag orphans
├── load.py             # upsert into new VehicleInspection table
└── pipeline.py         # orchestrator with structured logging + metrics
```

The `llm_mapper` is the interesting piece: when column headers don't match the known vocabulary, call Claude with a structured output schema to propose a mapping (e.g., "unit_no" → "asset_number"), cached so each unknown header is resolved once. That's the "LLM-powered extraction engine" pattern Chatham's JD calls out by name.

### 10c. CLI entrypoint

```bash
uv run fleetwise-etl ingest data/inspections/*.csv
```

Reports per-file: rows loaded, rows rejected with reasons, unknown-header mappings applied, orphan asset numbers flagged.

### 10d. Tests

- Fixtures of representative messy CSVs.
- Unit tests per extractor / transform stage.
- Integration test: end-to-end pipeline against a seeded DB, assert idempotency (re-running same file produces no new rows).

### 10e. Wire into chat

Add a `get_recent_inspections(asset_number)` tool so the LangGraph agent can answer "Show me the latest inspection findings for V-2020-0015" using the freshly ETL'd data. Closes the loop between the pipeline and the LLM.

**Verification.** End-to-end: drop a new CSV in `data/inspections/`, run the CLI, ask the chat agent about an inspection from that file, get a grounded answer referencing the new record.

**Commit.** `(feat): ETL pipeline for vehicle inspection CSVs with LLM-powered header mapping`

---

## Appendix: AWS deployment variant

Primary deployment is Render (Phase 6) because it's zero-cost and fast to iterate. The repo also documents an AWS variant for the Chatham "cloud platforms" preferred bullet. Not planned as a separate deploy — just a `docs/deploy-aws.md` walk-through so the story is written down.

**Proposed shape (documented, not built):**

| Component | AWS service |
|---|---|
| API container | ECS Fargate, behind an ALB |
| Fleet SQL database | RDS (PostgreSQL t4g.micro) — demonstrates the code works with Postgres too; SQLAlchemy already makes this a URL swap |
| Chroma persistence | S3-backed persistent directory, or switch to `opensearch` + `opensearch-py` for a pure-AWS vector story |
| LangGraph checkpoints | Same RDS instance with the LangGraph Postgres checkpointer |
| LLM | Anthropic direct, or Bedrock (`langchain-aws`'s `ChatBedrock`) to round out the AWS story |
| Frontend | CloudFront + S3 static hosting |
| Secrets | AWS Secrets Manager, read at container start |
| CI/CD | GitHub Actions → ECR push → ECS deploy with `aws-actions/amazon-ecs-deploy-task-definition` |

Document this in `docs/deploy-aws.md` with the Terraform or CDK stanzas that would provision it, plus a one-paragraph rationale for when you'd reach for AWS vs Render. Actual deploy is deferred to post-hire.

---

## Parity checklist (every behavior from .NET that must be preserved)

| Area | Behavior | Python equivalent | Phase |
|---|---|---|---|
| Domain | 5 entities with exact field names & types | SQLAlchemy models | 1 |
| Domain | Enums stored as strings, serialized as strings | `StrEnum` + Pydantic `use_enum_values` | 1 |
| Domain | `MaintenanceSchedule.is_overdue` computed | `@hybrid_property` | 1 |
| Data | 35 vehicles, 45 parts, 36 WOs, 163 MRs, 54 MSs | Direct port of seed | 1 |
| Data | Cascade delete Vehicle → children; SET NULL WO ← MR | `ondelete=` clauses | 1 |
| Data | Unique indexes on asset_number / vin / wo_number / part_number | `__table_args__` | 1 |
| API | Every route, verb, status code, response shape (PascalCase JSON) | FastAPI + Pydantic aliases | 2 |
| API | CORS allowing frontend origins + localhost | `CORSMiddleware` | 2 |
| API | `/api/vehicles/summary` before `/{id}` route ordering | Declare first | 2 |
| Chat | Sync endpoint returns `{Response, ConversationId, FunctionsUsed}` | Same DTO via aliases | 3 |
| Chat | Streaming endpoint emits `data: ...\n\n` + `data: [DONE]\n\n` | SSE adapter | 4 |
| Chat | Mid-stream errors yield `*An error occurred: ...*` instead of 500 | try/except in generator | 4 |
| Chat | Conversation history persists across a session | LangGraph `AsyncSqliteSaver` (improves on .NET: survives restart too) | 3 |
| Chat | System prompt adds documentation stanza only when RAG is wired | StateGraph prompt-select node | 4 |
| Tools | 13 tools across 4 functional areas, exact same names + descriptions | `@tool` with pydantic arg schemas | 3, 5 |
| Tools | Return-value format: prefatory line + indented JSON (or `--- Source: X ---` for docs) | Formatter helpers | 3, 5 |
| RAG | 5 SOP markdown files chunked, embedded, searchable | Same files, Chroma + same chunker | 5 |
| RAG | Chunks by `## ` headings, 500-char ceiling with paragraph sub-split | Direct port of chunker | 5 |
| RAG | Similarity search returns top-k with score | `asimilarity_search_with_score` | 5 |
| Provider | `AiProvider` env var flips chat + embedding stacks | `match settings.ai_provider` | 3, 5, 6 |
| Tests | Integration tests against real SQLite for aggregation queries | pytest against aiosqlite | 7 |
| Tests | Test-bed factory pattern, no direct CUT instantiation | pytest fixtures | 7 |
| CI | Green on PR before merge | GitHub Actions | 0, 7 |
| Deploy | Render free tier, Docker, health check, dashboard-prompted secret | `render.yaml` | 0, 6 |

---

## Deliberate deviations (what the Python edition does differently, on purpose)

| Deviation | Rationale |
|---|---|
| Conversation history persists across restarts | LangGraph checkpointer costs nothing; fixes a known .NET pain point. Free upgrade. |
| RAG collection persists across restarts | Chroma on disk; ingestion is idempotent and skipped when collection is populated. No reason to re-embed on every boot. |
| SSE chunks are newline-escaped | Fixes a latent framing bug in .NET. Requires a 2-line Angular-side change that applies to both backends. |
| Snake_case internally with alias-layer | Python idiom; aliases keep the wire format identical. |
| LangGraph StateGraph hand-rolled (phase 4) | Recruiter-visible demonstration of LangGraph mechanics. Prebuilt `create_react_agent` is used transitionally in phase 3 to de-risk the order. |
| Groq provider dropped | Not interesting as an Anthropic-centered portfolio. Ollama covers the free/no-credit-card story, OpenAI covers the hosted demo fallback. |
| No Aspire equivalent | .NET's Aspire observability is stack-specific. If the Python demo needs tracing, `opentelemetry-instrumentation-fastapi` + `logfire` is the equivalent — optional, defer until there's a reason. |

---

## Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Anthropic tool-call trace shape differs enough from OpenAI that tool descriptions need rewriting | Medium | Start with Haiku 4.5 locally (cheap) and iterate on tool descriptions early. If descriptions need domain rewrites, the .NET repo's descriptions are still good source material. |
| Pydantic `Decimal` serialization diverges from .NET `JsonSerializer` output | Medium | Phase 2 has an explicit "decimal serialization" subsection. Lock it down with a wire-format test early — one failing test here prevents a debug spiral later. |
| Chroma on a Render free-tier disk hits quota | Low | 5 SOPs × ~10 chunks × 1536 dims × 4 bytes ≈ 300 KB. 1 GB disk covers it 3000×. |
| LangGraph `astream_events` v2 schema changes | Low | LangGraph is pre-1.0. Pin `langgraph==X.Y.Z` in pyproject and only bump deliberately. |
| Angular frontend broken by wire-format drift | Medium | Phase 2 verification step is a full manual walk of every view against the Python API. Catches this before chat gets added. |
| Live demo cost creeps on Anthropic | Low | Haiku 4.5 for dev, Sonnet for hosted demo, per-account cap set at Anthropic dashboard. Usage for a portfolio demo is negligible. |

---

## Verification — end-to-end

At the end of each phase, the local equivalent of:

```bash
# Lint, type-check, tests
uv run ruff check .
uv run ruff format --check .
uv run mypy src/
uv run pytest --cov=fleetwise --cov-report=term-missing

# Smoke test the API
uv run uvicorn fleetwise.main:app --reload --port 5100
curl http://localhost:5100/api/vehicles/summary     # phases 2+
curl -X POST http://localhost:5100/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Which vehicles are overdue for oil changes?"}'  # phases 3+

# Streaming smoke test
curl -N -X POST http://localhost:5100/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "Summarize the fleet."}'  # phases 4+

# Angular frontend against Python backend
# Edit environment.ts → apiUrl='http://localhost:5100/api', run `npx ng serve`, walk every route
```

At the end of the whole migration, the live demo transcript from the .NET verification run replays verbatim against the Python deploy and produces comparable (not identical — different LLM) grounded answers, with RAG citations appearing on doc-flavored questions.

---

## Estimated effort

| Phase | Scope | Estimate |
|---|---|---|
| 0 | Scaffold + hello-world Render deploy | 30–45 min |
| 1 | Domain + data + seed | 1–2 days |
| 2 | REST API parity | 1 day |
| 3 | LangGraph prebuilt agent + 3 tool areas | 2 days |
| 4 | Custom StateGraph + SSE streaming | 1.5 days |
| 5 | RAG pipeline (Chroma + chunker + DocumentSearch) | 1 day |
| 6 | Provider swap + Render finalization | 0.5 day |
| 7 | Tests + CI parity | 1.5–2 days |
| 8 | README + cross-repo links | 0.5 day |
| 9 | React frontend (Vite + TanStack Query + Tailwind) | 2–3 days |
| 10 | *(optional)* ETL pipeline for inspection CSVs | 1–1.5 days |
| **Total** | | **~12–15 days of focused work (core) + 1–1.5 days optional ETL** |

That's wall-clock for someone who knows the codebase. Realistic calendar with the job search in parallel is ~2–3 weeks. Phases 0–2 (scaffold + data + REST) can land in the first week as a visible "look, same app, Python" milestone, with the LangGraph agent landing in week two.

---

## Files I expect to touch most often

| File / area | Why |
|---|---|
| `src/fleetwise/ai/agent.py` | Graph evolves from prebuilt → custom → streaming over phases 3/4 |
| `src/fleetwise/ai/tools/*.py` | 13 tools ported; descriptions iterated against real Claude calls |
| `src/fleetwise/ai/sse.py` | Framing fix is non-obvious; testing is where this earns its keep |
| `src/fleetwise/domain/dto.py` | PascalCase aliasing + Decimal serialization — wire-format gravity well |
| `src/fleetwise/data/seed.py` | Big one-time port; JSON-dump trick keeps it mechanical |
| `tests/conftest.py` | Fixtures are the whole game — good fixtures make the 200 tests trivial |
| `render.yaml` | Iterated as env vars and disk mounts firm up |
| Angular `chat.service.ts` | 2-line unescape fix, shared across both backends |

---

## What I'd want to know in the morning before starting work

In priority order:

1. **Does a Python repo already exist?** If yes, paste the URL — Phase 0 becomes "audit and align" rather than "scaffold fresh."
2. **Is the frontend-backend swap going to be a build-time env change or a runtime toggle in the UI?** The runtime toggle is ~2 hours of Angular work with a recruiter-visible payoff; worth doing if the schedule allows.
3. **Claude model preference for the hosted demo — Sonnet 4.5, or save the cost and use Haiku 4.5?** I'd default to Sonnet for the portfolio version.
4. **Groq drop — OK, or do you want me to keep it for parity?** My recommendation is drop (stated above), but it's cheap to keep.

The answers affect specific sections of this plan — flag anything that feels off and I'll redline just that section before we start executing.
