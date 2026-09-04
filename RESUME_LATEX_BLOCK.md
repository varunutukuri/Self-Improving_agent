# Self-Improving Code Agent — LaTeX block for master resume

Built only from claims verifiable in the repository. See `PROJECT_REVIEW.md` §4
for the two words to avoid ("sandboxed", "50 concurrent users") and §3 for why.

**Date check:** all 15 commits are dated **2026-06-05, between 12:54 and 15:13 IST** — the entire project was built in a single ~2.5-hour session (it was a hackathon build). Later file timestamps on disk are touches, not commits; the working tree is clean and matches those commits.

So the honest heading is `Jun 2026`, not a multi-month range. This is not a weakness — "built in one day at a hackathon" is a genuinely good answer to "how fast do you work?", and the scope delivered in that window is the point. But don't stretch it to `Jun 2026 -- Jul 2026`; the git history is one `git log` away for anyone who clones the repo.

---

## Master-resume version (5 bullets)

```latex
    \resumeProjectHeading{Self-Improving Code Generation Agent}{Jun 2026}
    \resumeItemListStart
        \resumeItem{Built an autonomous coding agent that generates Python solutions with pytest tests, executes them in an isolated subprocess with timeout enforcement, and iteratively rewrites failing code across a configurable 1--10 iteration loop until tests pass.}
        \resumeItem{Architected three specialised LLM roles with independent context windows --- generator and patcher on GPT-4o, analyser on GPT-4o-mini --- passing compressed per-iteration summaries rather than a growing transcript, keeping token cost per call flat as iterations accumulate.}
        \resumeItem{Engineered a semantic mistake memory using \texttt{sentence-transformers} (all-MiniLM-L6-v2, 384-dim) and scikit-learn cosine similarity over MySQL, with dual thresholds --- 0.6 for top-3 retrieval and 0.85 for deduplication --- so recurring errors append to an existing memory instead of flooding the store with near-identical rows.}
        \resumeItem{Constrained the analyser to a strict JSON schema (error class, root cause, fix hint) with a deterministic regex-based fallback on malformed output, and streamed seven distinct event types over WebSockets to a React + Monaco UI that renders test results immediately and patches in LLM critique as it arrives.}
        \resumeItem{Validated with a 21-test pytest suite at 87\% coverage across the agent and database packages, running in 2.1s at zero API cost with OpenAI stubbed at import; containerized the full stack (MySQL 9.0, FastAPI, React) with Docker Compose and healthcheck-gated startup ordering.}
    \resumeItemListEnd
```

---

## Trimmed version (3 bullets)

```latex
    \resumeProjectHeading{Self-Improving Code Generation Agent}{Jun 2026}
    \resumeItemListStart
        \resumeItem{Built an autonomous coding agent using FastAPI and GPT-4o that generates Python code with pytest tests, runs them in an isolated subprocess with timeout enforcement, and self-corrects failures via three specialised LLM roles (generator, analyser, patcher) with independent context windows.}
        \resumeItem{Engineered a semantic mistake memory with \texttt{sentence-transformers} embeddings and cosine similarity over MySQL, using separate retrieval (0.6) and deduplication (0.85) thresholds so the agent reuses fixes for recurring error patterns instead of storing near-duplicate failures.}
        \resumeItem{Streamed live iteration events (code tokens, per-test results, structured JSON critique) over WebSockets to a React + Monaco frontend; validated with a 21-test pytest suite at 87\% coverage running in 2.1s at zero API cost, containerized with Docker Compose.}
    \resumeItemListEnd
```

---

## Alternate bullets — swap in by role

**AI / LLM engineering roles:**

```latex
        \resumeItem{Designed a layered context-management strategy in which each LLM role receives only the fields it needs --- the generator a one-line failure summary, the analyser code plus retrieved memories, the patcher root cause plus full iteration history --- avoiding the quadratic token growth of transcript-passing agent loops.}
```

**Backend / distributed systems roles:**

```latex
        \resumeItem{Managed the embedding model and aiomysql connection pool (5--20 connections) as FastAPI lifespan singletons loaded once per worker, with per-connection session isolation, server-side input clamping, and graceful pool teardown on shutdown.}
```

**Roles emphasising evaluation or agent reliability:**

```latex
        \resumeItem{Hardened LLM output parsing against real-world model drift --- normalising heading levels, stripping three variants of markdown fences, and falling back to regex-extracted exception types when structured JSON parsing fails --- so malformed generations degrade the run instead of terminating it.}
```

**Frontend-leaning or full-stack roles:**

```latex
        \resumeItem{Built a real-time React interface consuming seven WebSocket event types, rendering test results the instant they arrive and patching in asynchronous LLM critique via iteration-keyed state updates, with socket handler teardown preventing stale callbacks from corrupting a new run's state.}
```

---

## Wording rules for this project

| Don't write | Write instead | Why |
|---|---|---|
| "sandboxed execution" | "isolated subprocess with timeout enforcement" | It's a tempdir on the host interpreter — no container, no network isolation, no resource caps. Your own module docstring says so. One follow-up question and the claim collapses. |
| "supports 50 concurrent users" | omit entirely, or "session-isolated architecture" | Never load-tested, and `subprocess.run` blocks the worker event loop for up to 30s. The number came from the planning doc, not a measurement. |
| "learns from experience across sessions" | "retrieves and reuses prior error patterns" | Memory persists, but only *failures* are currently written — `success_count` stays 0 for every row. Fix that (§7.1 of the review) and the stronger phrasing becomes honest. |
| "reduced iterations by X%" | nothing yet | No A/B measurement exists. See below — it's cheap to earn. |

---

## The one metric worth earning

The project's central claim is that semantic memory makes the agent better, and right now nothing measures that. It's a weekend of work:

1. Fix the success-path memory write first (§7.1 of `PROJECT_REVIEW.md`) — otherwise you're measuring a memory that only contains failed approaches.
2. Pick 30 tasks spanning a few error classes (off-by-one, indexing, type coercion, recursion depth).
3. Run each twice: once normally, once with `get_relevant_memories` stubbed to return `[]`.
4. Record mean iterations-to-pass, solve rate, and total LLM calls for each arm.

Then you can write, with every number checkable:

```latex
        \resumeItem{Measured the memory system's contribution via a controlled A/B across 30 tasks, reducing mean iterations-to-solution from X.X to Y.Y and total LLM calls by Z\% versus an identical agent with retrieval disabled.}
```

That single bullet would be stronger than the other four combined, because it's a measured result about a component you designed yourself rather than a description of architecture. It is currently the biggest gap between what this project is and how it reads.

---

## Skills section

Already on your list and reinforced by this project: Python, FastAPI, Docker, MySQL, React, Testing, Prompt Engineering, Text Embeddings, Vector Search, OpenAI.

Worth adding, since all appear in the bullets above:

- **WebSockets** — the clearest differentiator versus your other REST-only projects
- **sentence-transformers** — currently only HuggingFace is listed
- **aiomysql** / **asyncio** — async Python is not represented anywhere on the current resume
- **Docker Compose** — distinct from plain Docker; multi-service orchestration
- **Monaco Editor** — minor, but concrete frontend surface area
- **Tailwind CSS** — appears in the RAG project too but isn't in your skills list

Consider adding an **Agentic Systems** or **LLM Orchestration** line to the ML/AI row. Between this project and the RAG one you have a real claim to it, and it's the phrase AI/ML job descriptions increasingly screen for.
