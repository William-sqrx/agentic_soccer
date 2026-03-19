# Agentic Soccer

Agentic Soccer consists of a Flask backend and a frontend client.

## Structure

```
agentic-soccer/
│
├── CLAUDE.md                          # This file
├── README.md                          # Project overview and setup instructions
├── requirements.txt                   # Python dependencies
├── docs/                              # documentations
│   └── help.pdf                       # PAT 3.5 User Manual (CSP#/PCSP# reference)
├── graph/                             # Flask backend + LangGraph agent
│   ├── app.py                         # Flask application, routes (/chat, /teams, etc.)
│   ├── graph.py                       # LangGraph agent definition, tool bindings
│   ├── main.py                        # Entry point (python main.py to start server)
│   ├── state.py                       # LangGraph state schema
│   └── soccer-chat/                   # Frontend client (React)
│       ├── public/
│       ├── src/
│       ├── package.json
│       └── ...
│
├── tools/                             # Python tool implementations called by the agent
│   ├── pat_runner.py                  # PAT wrapper: macro substitution + CLI execution + output parsing
│   └── team_lookup.py                 # Reads team_stats.csv to return a team's metrics as a dict
│
├── model/                             # PCSP# model and its documentation
│   ├── football_pressure.pcsp         # Parametric PCSP# template (agent edits #define lines)
│   └── MODEL_SPEC.md                  # Documents every variable: what it means, which StatsBomb
│                                      #   event type and attributes it is derived from, the formula,
│                                      #   and how it maps to a #define macro in the PCSP file
│
├── scripts/                           # Offline data processing (run once, or periodically)
│   └── extract_team_stats.py          # Reads StatsBomb JSON → computes metrics → writes CSV
│
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

## How to Run

Put the required environment variables in .env

Start the backend

```bash
cd graph
python3 main.py
```

Start the frontend

```bash
cd graph/soccer-chat
npm run start
```
