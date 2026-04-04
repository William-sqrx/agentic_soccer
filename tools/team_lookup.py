"""Team stats lookup tool.

Reads ``data/processed/team_stats.csv`` and returns a :class:`Team` instance
for the requested team.  This tool is called by the LangGraph agent at
query time — the CSV is precomputed offline by ``scripts/extract_team_stats.py``.
"""

from __future__ import annotations

import csv
from pathlib import Path

from model.team import Team

# CSV lives at <project_root>/data/processed/team_stats.csv
_CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "team_stats.csv"


def team_lookup(team_name: str) -> Team:
    """Look up a team's stats from the precomputed CSV and return a Team.

    The search is **case-insensitive** so that ``"barcelona"`` matches
    ``"Barcelona"`` in the CSV.

    Args:
        team_name: Display name of the team (e.g. ``"Barcelona"``).

    Returns:
        A :class:`Team` instance populated with all seven CSV metrics.

    Raises:
        FileNotFoundError: If the CSV file does not exist.
        ValueError: If no row in the CSV matches *team_name*.
    """
    if not _CSV_PATH.exists():
        raise FileNotFoundError(
            f"Team stats CSV not found at {_CSV_PATH}.  "
            "Run scripts/extract_team_stats.py first."
        )

    target = team_name.strip().lower()

    with _CSV_PATH.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["team"].strip().lower() == target:
                return Team(
                    pass_reliability=int(row["pass_reliability"]),
                    pass_under_pressure=int(row["pass_under_pressure"]),
                    shot_conversion=int(row["shot_conversion"]),
                    xg_per_shot=int(row["xg_per_shot"]),
                    ball_retention=int(row["ball_retention"]),
                    pressure_success=int(row["pressure_success"]),
                    pressure_aggression=int(row["pressure_aggression"]),
                )

    raise ValueError(
        f"Team '{team_name}' not found in {_CSV_PATH.name}.  "
        "Check spelling or run the extraction script with updated data."
    )
