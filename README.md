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
├── backend/                           # Flask backend + LangGraph agent
│   ├── app.py                         # Flask application, routes (/chat, /teams, etc.)
│   ├── graph.py                       # LangGraph agent definition, tool bindings
│   ├── main.py                        # Entry point (python main.py to start server)
│   ├── state.py                       # LangGraph state schema
│   ├── Dockerfile
│   ├── tools/                         # Python tool implementations called by the agent
│   │   ├── pat_runner.py              # PAT wrapper: macro substitution + CLI execution + output parsing
│   │   └── team_lookup.py             # Reads team_stats.csv to return a team's metrics as a dict
│   └── model/                         # Python domain models
│       └── team.py                    # Team class for abstraction over team stats
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
├── pcsp_model/                        # PCSP# model and its documentation
│   ├── football_pressure.pcsp         # Parametric PCSP# template (agent edits #define lines)
│   └── MODEL_SPEC.md                  # Documents every variable
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

## How to Run Locally

- If the `data/processed/team_stats.csv` is not present
  - in project root directory, run
  - `python .\scripts\extract_team_stats.py --repo_path .\data\open-data\ --output .\data\processed\[team_stat_v1].csv`
    - don't delete previous processed data via naming versions as in `team_stat_v1`

- Put the required environment variables in `backend/.env`
  - `.env.sample` as reference

- Start the backend (you might want to use venv for package installation)

```bash
cd backend
pip install -r requirements.txt
python3 main.py
```

Start the frontend

```bash
cd frontend
npm run start
```

## Notes on running pat locally in Windows

- In Powershell, run
  - assuming `pat` is alias for `PAT3.Console.exe`
  - PAT3 cli currently does not know how to handle relative path

```powershell
pat -pcsp "$(Join-Path $PWD './pcsp_model/football_pressure.pcsp')" "$(Join-Path $PWD './pcsp_model/output.log')"
```

## Development guide

### Local Development with Docker Compose

- To start services locally for development:

```bash
docker compose up
```

- To enable live updates to code (e.g., for the backend):

```bash
docker compose up -f docker-compose.override.yml
```

### Production Deployment

For deployment on EC2 or a similar environment:

1. Use `docker-compose.prod.yml` with the following command:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build
```

1. Ensure Traefik and HTTPS configurations are set correctly.

- to have a terminal on the backend container, run

```bash
docker compose exec backend bash
```
