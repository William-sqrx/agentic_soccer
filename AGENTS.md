CLAUDE.md — Agentic Soccer Coach (CS4211 Project 4)

## Role

You are a **senior software engineer** working on a CS4211 course project. Follow good software engineering practices: clean separation of concerns, meaningful naming, docstrings, type hints in Python, and defensive error handling. Write code that a team of 5 students can read, extend, and debug.

This project builds an **AI Sports Coach** that uses **Probabilistic Model Checking (PCSP# / PAT)** to answer questions like _"How aggressively should Barcelona press Liverpool?"_ with formally verified, quantified probabilities — not LLM guesses.

---

## Architecture

The system has four layers:

```
┌─────────────────────────────────────────────────────┐
│  Frontend  (React / frontend)                       │
│  User types: "Should Barça press Liverpool harder?" │
└──────────────────────┬──────────────────────────────┘
                       │  HTTP (REST / SSE)
┌──────────────────────▼──────────────────────────────┐
│  Flask Backend  (backend/app.py)                    │
│  Routes: /chat, /teams, /analysis                   │
│  Hosts the LangGraph agent loop                     │
└──────────────────────┬──────────────────────────────┘
                       │  tool calls
┌──────────────────────▼──────────────────────────────┐
│  AI Agent  (backend/graph.py, backend/state.py)     │
│  LangGraph graph with tool nodes                    │
│  Tools:                                             │
│    - lookup_team_stats(team_name) → dict             │
│    - run_pat_analysis(macros: dict) → PAT output     │
└──────────────────────┬──────────────────────────────┘
                       │  subprocess
┌──────────────────────▼──────────────────────────────┐
│  PAT Wrapper  (tools/pat_runner.py)                 │
│  1. Reads template PCSP file                        │
│  2. Substitutes #define macros with supplied values  │
│  3. Writes temporary .pcsp file                     │
│  4. Invokes: PAT3.Console.exe -pcsp <file>          │
│  5. Parses stdout for probability results            │
│  6. Returns structured dict to the agent             │
└─────────────────────────────────────────────────────┘
```

### Typical Use Case

1. User asks via GUI: _"What pressure level should Barcelona use against Liverpool?"_
2. Flask receives the message, passes it to the LangGraph agent.
3. Agent decides it needs team data → calls `lookup_team_stats("Barcelona")` and `lookup_team_stats("Liverpool")` which read from the precomputed CSV in `data/processed/team_stats.csv`.
4. Agent decides to run a sensitivity sweep → calls `run_pat_analysis(...)` multiple times (e.g., pressure aggression = 20, 40, 50, 60, 70, 80), each time passing the team parameters plus the pressure value as macro substitution arguments.
5. PAT wrapper substitutes the `#define` lines in `pcsp_model/football_pressure.pcsp`, runs `PAT3.Console.exe -pcsp`, parses the output probabilities.
6. Agent receives the results (e.g., `{aggression: 70, p_win: 0.42, p_draw: 0.22, p_loss: 0.36}`), compares across runs, and composes a natural-language answer with the optimal aggression level and the reasoning.
7. Flask streams the answer back to the frontend.

---

## File Structure

```
agentic-soccer/
│
├── CLAUDE.md                          # This file
├── README.md                          # Project overview and setup instructions
├── requirements.txt                   # Python dependencies
├── docs/                              # documentations
│   └── help.pdf                       # PAT 3.5 User Manual (CSP#/PCSP# reference)
├── backend/                           # Flask backend + LangGraph agent
│   ├── app.py                         # Flask application, routes (/chat, /teams, etc.)
│   ├── graph.py                       # LangGraph agent definition, tool bindings
│   ├── main.py                        # Entry point (python main.py to start server)
│   ├── state.py                       # LangGraph state schema
│   └── Dockerfile
│
├── frontend/                          # Frontend client (React → nginx)
│   ├── src/
│   ├── package.json
│   ├── nginx.conf
│   ├── Dockerfile
│   └── ...
│
├── redisserver/                       # Redis instance
│   ├── Dockerfile
│   └── entrypoint.sh
│
├── tools/                             # Python tool implementations called by the agent
│   ├── pat_runner.py                  # PAT wrapper: macro substitution + CLI execution + output parsing
│   └── team_lookup.py                 # Reads team_stats.csv to return a team's metrics as a dict
│
├── model/                             # Python domain models
│   └── team.py                        # Team class for abstraction over team stats
│
├── pcsp_model/                        # PCSP# model and its documentation
│   ├── football_pressure.pcsp         # Parametric PCSP# template (agent edits #define lines)
│   └── MODEL_SPEC.md                  # Documents every variable: what it means, which StatsBomb
│                                      #   event type and attributes it is derived from, the formula,
│                                      #   and how it maps to a #define macro in the PCSP file
│
├── scripts/                           # Offline data processing (run once, or periodically)
│   ├── extract_team_stats.py          # Reads StatsBomb JSON → computes metrics → writes CSV
│   └── validate_stats.py             # (Optional) sanity-checks the computed CSV values
│
└─── data/                              # All data assets
      ├── open-data/                     # Full clone of https://github.com/statsbomb/open-data
      │   ├── data/
      │   │   ├── competitions.json
      │   │   ├── matches/
      │   │   ├── events/
      │   │   ├── lineups/
      │   │   └── three-sixty/
      │   └── doc/                       # StatsBomb data specification (event schema docs)
      │       ├── Open Data Competitions v2.0.0.pdf
      │       ├── Open Data Events v4.0.0.pdf
      │       ├── Open Data Lineups v2.0.0.pdf
      │       └── Open Data Matches v3.0.0.pdf
      │
      └── processed/                     # Output of scripts/extract_team_stats.py
          └── team_stats.csv             # One row per team, columns = metrics (0-100 integers)

```

### Key points

- **`scripts/`** is for offline batch processing. Run `python scripts/extract_team_stats.py --repo_path data/open-data --output data/processed/team_stats.csv` once (or whenever new matches are added to open-data). The agent never runs these scripts at query time — it reads the precomputed CSV.
- **`tools/`** contains the agent-callable tools. These are thin wrappers: `pat_runner.py` does macro substitution and subprocess invocation; `team_lookup.py` does a CSV lookup.
- **`model/`** holds Python domain models. `team.py` contains the `Team` class for abstracting over team statistics.
- **`pcsp_model/`** holds the PCSP# template and its specification document. `MODEL_SPEC.md` is the authoritative reference for what each `#define` macro means, how it is calculated, and which StatsBomb event types feed into it. If you change the model, update `MODEL_SPEC.md` in the same commit.
- **`data/processed/`** stores the CSV output. The format is CSV with columns: `team, pass_reliability, pass_under_pressure, pressure_success_rate, shot_conversion, xg_per_shot, ball_retention, matches_analysed, total_passes, total_shots, total_pressures`. All metric columns are integers 0–100.

---

## Information Sources

### PAT 3.5 User Manual (`help.pdf` in `docs/`)

This is the **authoritative reference** for CSP# and PCSP# syntax. Key sections:

- **Section 3.1.1** — CSP# language reference (global definitions, event prefixing, data operations, conditional choices, parallel composition, etc.)
- **Section 3.3** — PCSP module (probabilistic extension of CSP#)
- **Section 3.3.1.1** — `pcase` syntax: weighted format (`weight : Process`) and explicit probability format (`[0.5] : Process`)
- **Section 3.3.1.2** — Assertions with probability: `#assert P() reaches cond with prob/pmin/pmax;`
- **Section 3.3.1.3** — PCSP grammar rules
- **Section 3.3.2** — PCSP tutorials (PZ86 mutual exclusion, Monty Hall)

**Critical syntax rules to remember:**

| Construct                             | Meaning                                                                                  | Use case                                                                    |
| ------------------------------------- | ---------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| `if (cond) { P } else { Q }`          | Conditional choice. Time may elapse before evaluation.                                   | General branching. **Use this by default.**                                 |
| `ifa (cond) { P } else { Q }`         | **Atomic** conditional. Eval + first step of P/Q happen atomically with no interleaving. | Only for CAS-like operations in concurrent models. **Not** "if-assignment". |
| `ifb (cond) { P }`                    | **Blocking** conditional (guard). Waits until cond is true. No else.                     | Guard a process on a condition.                                             |
| `event{stmts;} -> P`                  | Data operation. Statements execute atomically when event fires.                          | **The only correct way to update global variables.**                        |
| `pcase { w1 : P1  w2 : P2 }`          | Weighted probabilistic choice. P(P1) = w1/(w1+w2).                                       | Our main modelling construct.                                               |
| `pcase { [0.5] : P1  default : P2 }`  | Explicit probability format. Probabilities must sum to 1.                                | Alternative to weighted; less convenient with `#define` integers.           |
| `#define Name expr;`                  | Constant macro. Textual substitution.                                                    | Team parameters, derived weights, proposition names.                        |
| `var x = 0;`                          | Global variable declaration.                                                             | Match state (goals, phase counter).                                         |
| `#assert P() reaches Cond with prob;` | Reachability with probability. `Cond` must be a `#define`'d name.                        | Our main assertion type. Returns min and max probability.                   |

**Do NOT use `ifa` as "if-then-else with assignment".** That is wrong. `ifa` means atomic-if. Variable assignments go inside event prefixes: `event_name{var = expr;} -> Process`.

### StatsBomb Open Data Specification (`data/open-data/doc/`)

The `doc/` directory inside the cloned `open-data` repository contains PDF specifications for the JSON data format:

- **Open Data Events v4.0.0.pdf** — The primary reference. Documents every event type (`Pass`, `Shot`, `Pressure`, `Dribble`, `Ball Receipt*`, `Duel`, `Dispossessed`, `Miscontrol`, `Interception`, `Ball Recovery`, etc.), their attributes, and the meaning of each field.
- **Open Data Matches v3.0.0.pdf** — Match-level metadata (teams, scores, competition, season).
- **Open Data Competitions v2.0.0.pdf** — Competition and season identifiers.
- **Open Data Lineups v2.0.0.pdf** — Player lineup data per match.

Key StatsBomb conventions to know:

- Event locations use a **120 × 80 coordinate system** (standardised pitch).
- A **Pass** with no `pass.outcome` field means the pass was **complete** (successful). A present `pass.outcome.name` (e.g., `"Incomplete"`) means it failed.
- The **`under_pressure`** boolean flag on any event indicates the player was being pressed when performing that action.
- **`shot.statsbomb_xg`** is a float (e.g., 0.12) representing expected goals for that shot.
- **Duel** events have a sub-type (`duel.type.name`): use `"Tackle"` for tackle statistics. Outcome `"Won"` / `"Success In Play"` / `"Success Out"` counts as a successful tackle.

### Online PAT Reference (supplementary)

The online version of the PAT manual is at `https://formal-analysis.com/sem-eng/pat/help/htm/` but uses a JavaScript CHM viewer that may not render in all environments. Always prefer `help.pdf` in `docs/` as the primary reference.

---

## Development Guidelines

- **Before writing or modifying any PCSP# code**, re-read the relevant section of `help.pdf`. Do not rely on memory or assumptions about PAT syntax.
- **All `pcase` weights must be positive integers.** If a computed weight could be zero or negative at extreme parameter values, the Python wrapper (`tools/pat_runner.py`) must clamp values to a minimum of 1 before substitution. `#define` does not support function calls like `max()`, so clamping must happen in the wrapper.
- **Keep `TOTAL_PHASES` at 20** during development for fast iteration. Increase to 30–40 for final evaluation runs only.
- **Test the PCSP model in PAT GUI first** before automating with CLI. Load `football_pressure.pcsp` in PAT, click Verify, and confirm the assertions produce sensible probabilities.
- **The Python wrapper uses regex substitution** on `#define` lines. The pattern is `#define MACRO_NAME <value>;`. When the agent writes the file for execution, all macro values must be resolved to **concrete integers** — no expressions. The template file itself may contain expressions for human readability, but `pat_runner.py` overwrites them with integers before invoking PAT.
- **Commit `pcsp_model/MODEL_SPEC.md` alongside any PCSP model changes.** The spec doc is the single source of truth for what each macro means, which StatsBomb event type feeds it, and the exact formula.
