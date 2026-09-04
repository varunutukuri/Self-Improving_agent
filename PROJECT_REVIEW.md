# Self-Improving Code Agent (AIDEN) — Full Review

> **Update — post-review fixes applied.** Weaknesses 3, 6, 7, 8, 9 below have since been
> fixed and are struck through. The suite is now **25 tests at 91% coverage**, enforced in
> CI, and the memory layer was verified end-to-end against a live MySQL instance. Sections
> 4–5 reflect the current numbers.

**Verdict up front:** this is a genuinely strong project and the most conceptually ambitious thing on your resume. The architecture is clean, the memory layer is a real idea rather than a wrapper around an API, and the code is documented to a standard most student projects never reach. All 25 tests pass, 91% coverage on the agent and db packages.

Unlike the RAG project, there are **no inflated claims to correct** — because you haven't written resume bullets for it yet. Section 4 is instead about which claims you *can* safely make, and the two words to avoid.

The one real risk is the security posture of the code executor. Section 3 covers it, and Section 6 tells you exactly how to answer when an interviewer asks — because they will.

---

## 1. What it is

An agent that takes a natural-language coding task, writes Python plus its own pytest tests, runs them in a subprocess, and — on failure — diagnoses the root cause and rewrites the code. Every failure is embedded and stored, so recurring error patterns are recognised on future runs.

```
Task ──▶ GENERATOR (gpt-4o, streaming) ──▶ ## CODE / ## TESTS parsed
                  ▲                                  │
                  │                                  ▼
                  │                    run_tests() — pytest in tempdir
                  │                          (timeout=30s)
                  │                                  │
                  │                    ┌─────────────┴─────────────┐
                  │                 passed                       failed
                  │                    │                           │
                  │              emit "complete"                   ▼
                  │                                SentenceTransformer.encode(error)
                  │                                          │
                  │                                          ▼
                  │                        get_relevant_memories(top_k=3, cos ≥ 0.6)
                  │                                          │
                  │                                          ▼
                  │                        ANALYZER (gpt-4o-mini) → strict JSON
                  │                        {error_class, root_cause, fix_hint}
                  │                                          │
                  │                                          ▼
                  │                        save_memory(dedup at cos ≥ 0.85)
                  │                                          │
                  └────── PATCHER (gpt-4o) ◀─────────────────┘
                          prompt = code + root cause + history + memories

        every stage yields an event ──▶ WebSocket ──▶ React (Monaco + cards + memory table)
```

**Stack:** FastAPI, OpenAI (gpt-4o generator/patcher + gpt-4o-mini analyzer), sentence-transformers `all-MiniLM-L6-v2` (384-dim), scikit-learn cosine similarity, MySQL 9.0 via aiomysql, React 18 + Vite + Tailwind + Monaco, Docker Compose. Python 3.11.

**Structure** — 235 statements across the agent and db packages, 1,256 lines of backend Python, 915 lines of frontend:

```
backend/
├── api.py              lifespan-managed model + pool, /health, /memories, WS /ws/run
├── agent/
│   ├── agent_loop.py       the generate→test→analyse→patch orchestrator
│   ├── agent_context.py    per-session state + three prompt builders + parser
│   ├── llm_client.py       async OpenAI wrapper (streaming + non-streaming)
│   ├── memory_store.py     embedding storage, cosine retrieval, dedup
│   └── test_executor.py    subprocess pytest runner + output parsing
├── db/
│   ├── connection.py       aiomysql pool (minsize=5, maxsize=20)
│   └── schema.sql          memories / fix_attempts / runs
└── tests/                  25 tests
frontend/src/               8 components + useAgentSocket hook
```

---

## 2. What's genuinely well done

**The three LLM roles have genuinely separate context windows.** This is the architectural decision worth talking about. The generator sees only the task plus a one-line summary of the last failure. The analyzer sees code + error + retrieved memories. The patcher sees code + root cause + full iteration history + memories. Nobody passes a growing conversation transcript, so token cost stays roughly flat as iterations accumulate instead of growing quadratically. `AgentContext.iteration_history` stores a compressed `IterationSummary` per iteration — error type, 150 chars of attempted fix, result — rather than raw transcripts.

**Structured JSON critique instead of prose.** The analyzer's system prompt pins an exact schema (`error_class`, `root_cause`, `fix_hint`) and the loop parses it with a graceful fallback:

```python
try:
    analysis_data = json.loads(analysis_raw)
    ...
except (json.JSONDecodeError, AttributeError):
    error_class = test_result.error_type   # falls back to regex-extracted type
    root_cause  = analysis_raw[:200]
```

The failure path degrades to the deterministic regex-extracted error type rather than crashing the run. That's the right instinct — treating LLM output as untrusted input.

**Semantic dedup, not just semantic retrieval.** Two thresholds doing two different jobs: retrieval at cosine ≥ 0.6 (loose, "show me anything related"), dedup at ≥ 0.85 (tight, "this is the same mistake"). On a dedup hit it appends to `fix_attempts` and increments `success_count` rather than inserting a near-identical row. Without this the memory table would fill with 40 variants of the same `AssertionError` and retrieval quality would collapse. Most people implement retrieval and forget dedup entirely.

**The UI streams two independent event types per iteration.** `iteration_failed` fires immediately so the card appears with test results; `iteration_analysis` arrives later and *patches* the same card with critic rows, with a shimmer placeholder in between. The frontend matches on `it.iteration === event.iteration`. This is a deliberate perceived-latency decision — the user sees test results while the analyzer LLM call is still in flight, instead of staring at nothing for two seconds.

**Robust LLM output parsing.** `parse_llm_response` normalises heading levels (`### CODE`, `## CODE`, `#CODE`) with regex before splitting, then strips markdown fences three different ways — opening fence with optional language tag, closing fence, and orphaned fence lines. This is exactly the kind of defensive parsing that separates a demo from something that runs unattended, and it's clearly the product of watching real model output break the naive version.

**Per-test-case granularity.** `_parse_test_cases` regexes pytest's `-v` output into `[{name, passed}]`, so the UI shows "3 / 5 tests failed" with individual pills rather than a binary pass/fail. Small feature, meaningfully better signal.

**Socket lifecycle handled correctly.** `useAgentSocket` nulls `onmessage` and `onclose` on the previous socket *before* opening a new one, so stale callbacks from an abandoned run can't write into the new run's state. The `stop()` path nulls `onclose` before closing so the close handler doesn't fight the explicit status set. This is a real class of React bug that most people ship.

**Genuine debugging recorded in git history.** All 15 commits landed on 2026-06-05 between 12:54 and 15:13 IST — the whole system was built in a single ~2.5-hour hackathon session, which makes the scope delivered more impressive rather than less. Five of those fifteen commits are fixes with specific causes: CPU-only PyTorch wheel to stop a 1GB+ download hanging the Docker build, `MYSQL_HOST` override for the container network, removing a `dotenv` override that was shadowing Docker env vars, and — the best one — *"correctly stream and apply patched code in subsequent iterations."* That last one is the interesting bug: the loop originally generated a patch but the next iteration re-ran the generator prompt instead of streaming the patcher's output, so fixes were silently discarded. The current code routes iteration ≥ 2 through `build_patcher_prompt` in the streaming path. Worth being able to tell that story.

**Secrets hygiene.** `.env` untracked and never committed at any point in history (verified with `git log --all --full-history`), `.env.example` provided, `.dockerignore` explicitly excludes `.env` so it can't be baked into an image. Only 44 tracked files.

**Test design.** `conftest.py` stubs the `openai` module via `sys.modules` so the suite imports and runs without the package installed or any API key present. Mock aiomysql pools are hand-built with correct `__aenter__`/`__aexit__` semantics. The memory tests construct actual normalised numpy vectors and assert real cosine behaviour above and below threshold rather than mocking the similarity function — that's testing the logic, not the mock.

---

## 3. Weaknesses

Ordered by what an interviewer would probe first.

**1. The "sandbox" is a temp directory, not a sandbox.** This is the big one. `run_tests()` writes LLM-generated code to a tempdir and runs it with `subprocess.run(["python", "-m", "pytest", ...])` on the host interpreter. There is no container, no seccomp, no user namespace, no network isolation, no memory or CPU limit. Generated code can read your filesystem, make network calls, or read `.env`. The only guards are `timeout=30` and automatic tempdir cleanup.

To your credit, the module docstring says this explicitly:

> The generated code is executed inside a temporary directory with no extra sandboxing beyond what the OS provides. Do **not** run this in a shared multi-tenant environment without additional isolation (e.g. Docker with `--network=none` and resource limits).

Documenting a known limitation honestly is much better than pretending. But **do not use the word "sandboxed" on your resume** — it invites exactly one follow-up question and the honest answer contradicts the bullet. "Isolated subprocess with a timeout" is accurate and still sounds competent. See §6 for how to answer the question.

**2. Full-table scan on every memory retrieval.** `get_relevant_memories` runs `SELECT id, error_text, embedding, success_count FROM memories` with no `LIMIT` and no `WHERE`, parses every embedding out of JSON, and builds an N×384 numpy array — per iteration, per run, per user. Then `save_memory` calls it *again* for the dedup check, so it's two full scans per failed iteration. The module docstring correctly flags this as fine below ~10k rows, but this is the scaling question you'll be asked.

**3. The concurrency story doesn't survive contact with `--workers 4`.** *Partially fixed.* The blocking `subprocess.run` inside the async generator — which stalled a worker's entire event loop for up to 30 seconds and froze every other WebSocket connection on it — is now wrapped in `asyncio.to_thread`. ✅

What remains unaddressed: each of the 4 uvicorn workers is a separate process, so each loads its own ~90MB copy of the embedding model and its own pool of up to 20 MySQL connections — a potential 80 connections against a default `max_connections` of 151. And none of it has been load-tested. **Still don't claim a concurrency number you haven't measured.**

**4. Nothing writes to the `runs` table.** It's defined in `schema.sql` with a `session_id` index, and `session_id` is generated per WebSocket connection and threaded through `AgentContext` — but no `INSERT` ever happens. Run history is not persisted; only the memory rows are. Either wire it up or drop the table.

**5. The agent grades its own homework.** The generator writes both the implementation *and* the tests, so "all tests passed" means the code satisfies tests the same model invented. If the model misunderstands the task, it will write tests that encode the misunderstanding and then pass them. Inherent to the design rather than a bug, but it's the sharpest question available about the project.

**This is no longer hypothetical — it was observed in a live run.** On the duration-parsing task, iteration 1 failed and the analyser returned:

> root cause: *"The test is incorrectly asserting that an empty string should not raise a ValueError."*
> fix hint: *"Change the test to expect a ValueError when passing an empty string."*

The agent resolved the failure by **rewriting its own test to match its implementation**, not by changing the code. Here that was arguably the right call — the implementation matched the spec and the test didn't — but it demonstrates the failure mode exactly: nothing in the loop prevents turning a red test green by weakening the test.

Mitigation is a fixed held-out test set per task, or generating tests and implementation in separate calls that can't see each other. Volunteering this run in an interview is far stronger than being asked about it.

**~~6. Memory is written on failure but success is never recorded.~~** ✅ **FIXED.** `save_memory` was only ever called with `result="failed"`, so `success_count` stayed 0 for every row and the store recorded approaches that did *not* work. The preceding failure is now carried forward and re-saved with `result="passed"` when a later iteration succeeds. Verified against a live database: one memories row, `success_count = 1`, two fix_attempts (`failed`, `passed`). Covered by two regression tests.

**~~7. `last_similarity` is a global field, not a per-query one.~~** ✅ **FIXED.** It was written on every dedup hit, where the score is ~1.0 by construction, so the UI column read 100% for every row regardless of usefulness. Dedup no longer touches it; `update_last_similarity()` now records the score at *retrieval* time, so the column means "how closely this memory matched a genuinely new error." Two tests pin the behaviour.

**~~8. No CI.~~** ✅ **FIXED.** `.github/workflows/ci.yml` runs ruff plus pytest with an 85% coverage gate (currently 91%) and a frontend build, verified green on a clean Linux runner. `ruff.toml` pins the rule set explicitly so a ruff release can't break the build on an unrelated commit.

**9. Hardcoded `localhost:8000` in the frontend.** *Partially fixed.* `MemoryLog.jsx` — dead code superseded by `MemoryTable.jsx`, but still duplicating the fetch logic — has been deleted. ✅ The two live call sites in `useAgentSocket.js` and `App.jsx` still hardcode the backend URL, so the Docker Compose frontend only works when accessed from the host machine. Should be `import.meta.env.VITE_API_URL`.

**9b. The UI refetched `/memories` before the write landed.** ✅ **FIXED** (found by running the app, not by reading it). The frontend refetched on `iteration_failed`, which the loop emits *before* `save_memory()` runs — so the memory table rendered one step behind and showed "0 entries" immediately after a failure had been persisted. The backend now emits a `memory_saved` event once the row is committed, and the frontend refetches on that. A good example of a bug that only surfaces end-to-end: every unit test passed throughout.

**10. WebSocket errors leak raw exception strings to the client.** `except Exception as e: send_json({"type": "error", "message": str(e)})` will happily forward a MySQL error containing connection details or a stack-trace fragment to the browser. Log server-side, send a generic message.

**11. No auth or rate limiting on `/ws/run`.** Every run costs real OpenAI money across up to 10 iterations × 3 calls. An open WebSocket endpoint that spends money per connection is a billing incident waiting to happen if it's ever exposed publicly.

**12. `llm_client.py` at 50% coverage and `db/connection.py` at 0%.** The two modules that touch the network are the two least covered. Understandable — they're thin wrappers over external services — but worth knowing before someone points at the coverage report.

---

## 4. Resume claims — what's safe to say

You have no existing bullets for this project, so nothing needs correcting. This is what the repository will support under scrutiny:

### Safe — directly verifiable from the code

| Claim | Evidence |
|---|---|
| Three separated LLM roles with independent context windows | `build_generator_prompt`, `build_analyzer_prompt`, `build_patcher_prompt` |
| gpt-4o for generation/patching, gpt-4o-mini for analysis | `agent_loop.py` model arguments |
| Semantic memory: 384-dim embeddings, cosine retrieval at 0.6, dedup at 0.85 | `memory_store.py` defaults |
| Token-by-token streaming over WebSocket to Monaco | `call_llm_stream` → `token` events → `useAgentSocket` |
| Structured JSON critique with graceful fallback | `build_analyzer_prompt` schema + `try/except` in the loop |
| Per-test-case pass/fail parsing | `_parse_test_cases` |
| 25 tests, 91% coverage on agent + db, ~3s runtime, zero API cost, CI-enforced at 85% | ran it; `conftest.py` stubs openai |
| 235 statements, 1,256 lines backend, 915 lines frontend | coverage report + `wc -l` |
| Containerized: MySQL 9.0 + backend + frontend, healthcheck-gated startup | `docker-compose.yml` |
| aiomysql pool, 5–20 connections, lifespan-managed | `connection.py`, `api.py` |
| Embedding model loaded once per worker at startup | `api.py` lifespan |
| Iteration cap configurable 1–10, clamped server-side | `api.py` |

### Avoid these

| Don't say | Why |
|---|---|
| **"sandboxed"** execution | It's a tempdir + 30s timeout on the host interpreter. Your own docstring says so. Use "isolated subprocess with timeout enforcement." |
| **"supports 50 concurrent users"** | Never load-tested, and `subprocess.run` blocks the worker's event loop for up to 30s. The number came from the plan document, not a measurement. |
| **"learns across sessions"** without qualification | True in the narrow sense that memory persists in MySQL — but since only *failures* are saved (§3.6), what persists is a record of failed approaches. Fix that first, then the claim gets much stronger. |
| Any accuracy or success-rate figure | Nothing in the repo measures how often the agent actually solves a task. |

### The one number worth earning

You have no metric for the thing the project is actually about: **does the memory help?** That's a weekend's work and it would become the strongest line on your resume:

Run 30 tasks with `threshold=0.6` (memory on) and 30 with the retrieval call stubbed to return `[]` (memory off). Record mean iterations-to-pass and solve rate for each. If memory helps, you get to write "reduced mean iterations-to-solution from X to Y across N tasks (Z% fewer LLM calls)" — a measured claim about your own novel component. If it doesn't help, that's a more interesting interview answer than most people have, and it tells you to fix §3.6 first.

Fix the success-path memory write before running this, or you'll be measuring the wrong thing.

---

## 5. Numbers you can cite safely

| Metric | Value | Verified how |
|---|---|---|
| Test suite | 25 tests, 100% passing | ran it |
| Coverage (agent + db) | 91%, CI gate at 85% | `pytest --cov` |
| Per-module coverage | agent_context 100%, memory_store 100%, test_executor 98%, agent_loop 97% | coverage report |
| Test runtime | ~3s, zero API cost | ran it; openai stubbed in `conftest.py` |
| Application size | 247 statements; ~1,300 lines backend Python, ~900 lines frontend | coverage + `wc -l` |
| API surface | 2 HTTP endpoints + 1 WebSocket | `api.py` |
| Event types streamed | 8 (`token`, `status`, `iteration_failed`, `iteration_analysis`, `memory_saved`, `complete`, `max_iterations_reached`, `error`) | `agent_loop.py` + hook |
| CI | ruff + pytest + coverage gate + frontend build, green on Linux | GitHub Actions run |
| Live memory retrieval | stored mistake matched a different task at **68.1%** and was applied | observed end-to-end run |
| Embeddings | all-MiniLM-L6-v2, 384-dim | `api.py`, tests |
| Retrieval | top_k = 3, cosine ≥ 0.6 | `memory_store.py` |
| Dedup | cosine ≥ 0.85 | `memory_store.py` |
| Models | gpt-4o (generate/patch), gpt-4o-mini (analyse), temp 0.2 | `agent_loop.py`, `llm_client.py` |
| Test timeout | 30s per subprocess run | `test_executor.py` |
| Iteration cap | default 5, clamped 1–10 | `api.py` |
| DB pool | aiomysql, minsize 5 / maxsize 20, autocommit | `connection.py` |
| Frontend | 8 components + 1 hook, React 18 + Vite + Tailwind + Monaco | `frontend/src` |
| Repo | 44 tracked files, 15 commits, no secrets in history | `git ls-files`, `git log --all` |
| Build window | all commits 2026-06-05, 12:54–15:13 IST (~2.5 hours) | `git log --date=iso` |

---

## 6. Interview preparation

**"Walk me through the architecture."** — Task comes in over a WebSocket. Generator (gpt-4o) streams code and tests token-by-token to the browser. Tests run in a subprocess; if they pass, done. If not, the error text is embedded with MiniLM and used to query a MySQL-backed memory of past failures by cosine similarity. Retrieved matches are injected into an analyzer prompt (gpt-4o-mini) that returns structured JSON — error class, root cause, fix hint — and then into a patcher prompt (gpt-4o) that rewrites the code. Loop repeats up to N times. The key design point is that the three roles have separate, purpose-built context windows rather than a shared growing transcript, so token cost per call stays roughly flat across iterations.

**"Is executing LLM-generated code safe?"** — *The question you will definitely get. Answer it before they push.* No, and I documented that in the module. It runs pytest in a temp directory on the host interpreter with a 30-second timeout — that stops infinite loops, and cleanup is guaranteed by the context manager, but it does not stop filesystem or network access. It's acceptable for a single-user local tool and not acceptable for anything multi-tenant. The fix is running each execution in a throwaway container with `--network=none`, a read-only root filesystem, a memory cap, and a non-root user — or gVisor/Firecracker if I wanted real kernel isolation. I chose not to build that because the project was about the learning loop, not the isolation layer, and I'd rather state the limitation than imply I'd solved it. **Volunteering this is worth more than being caught by it.**

**"How does the memory actually work, and does it help?"** — Error text is embedded to 384 dimensions with all-MiniLM-L6-v2, stored in MySQL as JSON. Retrieval is cosine similarity in Python at a 0.6 threshold, top 3. There's a second, tighter threshold at 0.85 for dedup, so semantically identical errors append a fix attempt to the existing row instead of creating a new one. Then be honest: I haven't yet A/B'd memory-on versus memory-off, so I can't give you a number for how much it helps — that's the next thing I'd measure, and I'd measure it as mean iterations-to-solution across a fixed task set.

**"The agent writes its own tests — isn't that circular?"** — Yes, and it's the real limitation of the design. Passing means the code satisfies tests the same model wrote, so a misunderstood requirement produces tests that encode the misunderstanding. It validates internal consistency, not correctness against intent. The fix is a held-out test set per task that the generator never sees, or at minimum generating tests in a separate call with no visibility into the implementation. *Say this before they say it.*

**"How would you scale the memory search?"** — Right now every retrieval pulls the whole table and computes cosine similarity in numpy — two full scans per failed iteration, since dedup calls the same function. Fine at hundreds of rows, wrong at a hundred thousand. I'd move to pgvector or Qdrant with an ANN index, or MySQL 9's native `VECTOR` type, and add an approximate index so it's sublinear. I'd also scope retrieval by task type so a Fibonacci off-by-one doesn't get matched against an unrelated parsing bug.

**"You said it handles concurrent users — how do you know?"** — *Don't claim this.* If asked about concurrency: the design is session-isolated (one `AgentContext` per socket, no shared mutable state) and the DB pool is sized 5–20, but I haven't load-tested it, and there's a known blocker — the pytest subprocess call is synchronous inside an async generator, so it stalls that worker's event loop for up to 30 seconds. I'd move it to `asyncio.to_thread` before making any concurrency claim.

**"What was the hardest bug?"** — Patched code was being generated and then silently discarded. The loop streamed from the generator prompt on every iteration, so the patcher's output — the actual fix, informed by the root-cause analysis and retrieved memories — never made it into the next test run. The agent looked like it was iterating but was really just resampling the generator. Fix was routing iterations ≥ 2 through the patcher prompt in the streaming path, which is why the git history has a commit named exactly that.

---

## 7. Highest-value next steps

✅ **Done:** successful fixes now saved to memory; `run_tests` moved off the event loop; GitHub Actions with a coverage gate; `last_similarity` made meaningful; memory-table refetch race fixed; dead `MemoryLog.jsx` removed.

Remaining, in order of return on effort:

1. **Measure memory-on vs memory-off** (~a weekend). The one metric the project is missing, and the strongest bullet available to you. Now unblocked — the store finally contains fixes that worked, so the benchmark measures the right thing.
2. **Containerize the executor** with `--network=none` and resource limits. Turns your biggest weakness into your best answer.
3. **Use a held-out test set per task.** Addresses the self-grading circularity in §3.5 — the sharpest question anyone can ask about this design, and one you've now seen fire in a real run.
4. **Wire up the `runs` table or delete it.** Dead schema invites questions with no good answer.
5. **Parameterise the frontend API URL** with `VITE_API_URL` so the containerized frontend works off-host.
