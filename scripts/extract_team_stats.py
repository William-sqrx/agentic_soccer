"""Extract per-team metrics from StatsBomb open-data events.

This script reads all event JSON files under:
    <repo_path>/data/events/*.json

It computes one output row per unique team with columns:
    - team
    - pass_reliability
    - pass_under_pressure
    - shot_conversion
    - xg_per_shot
    - ball_retention
    - pressure_success
    - pressure_aggression
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class TeamCounters:
    """Raw counters used to derive final team metrics."""

    total_passes: int = 0
    complete_passes: int = 0

    total_passes_under_pressure: int = 0
    complete_passes_under_pressure: int = 0

    total_shots: int = 0
    goals: int = 0
    xg_sum: float = 0.0
    shots_with_xg: int = 0

    losses: int = 0
    touches_proxy: int = 0

    total_pressures: int = 0
    pressure_regains_proxy: int = 0

    # For pressure aggression computation
    pressure_location_x_sum: float = 0.0
    pressure_location_count: int = 0

    # Opponent passes faced (used for pressing frequency calculation)
    opponent_passes: int = 0


def safe_percentage(numerator: float, denominator: float) -> int:
    """Return rounded percentage in [0, 100], or 0 if denominator is 0."""
    if denominator <= 0:
        return 0
    value = round((numerator / denominator) * 100)
    return max(0, min(100, int(value)))


def list_event_files(events_dir: Path) -> list[Path]:
    """List all StatsBomb event JSON files under events directory."""
    if not events_dir.exists() or not events_dir.is_dir():
        raise FileNotFoundError(f"Events directory not found: {events_dir}")
    return sorted(events_dir.glob("*.json"))


def load_json_file(file_path: Path) -> Any:
    """Load JSON content from a file with explicit UTF-8 decoding."""
    with file_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def is_successful_pass(event: dict[str, Any]) -> bool:
    """StatsBomb pass success convention: missing/null pass.outcome means complete."""
    pass_obj = event.get("pass")
    if not isinstance(pass_obj, dict):
        return False
    return pass_obj.get("outcome") is None


def get_teams_in_match(events: list[dict[str, Any]]) -> set[str]:
    """Extract the set of team names appearing in a match's events."""
    teams: set[str] = set()
    for event in events:
        team_obj = event.get("team")
        if isinstance(team_obj, dict):
            name = team_obj.get("name")
            if isinstance(name, str) and name.strip():
                teams.add(name)
    return teams


def process_match_events(
    counters_by_team: dict[str, TeamCounters],
    events: list[dict[str, Any]],
) -> None:
    """Process all events in a single match, updating counters."""
    # First pass: count total passes per team (needed for opponent_passes)
    match_teams = get_teams_in_match(events)
    passes_per_team: dict[str, int] = defaultdict(int)

    for event in events:
        team_obj = event.get("team")
        if not isinstance(team_obj, dict):
            continue
        team_name = team_obj.get("name")
        if not isinstance(team_name, str) or not team_name.strip():
            continue

        event_type = event.get("type", {})
        if not isinstance(event_type, dict):
            continue
        type_name = event_type.get("name")
        if not isinstance(type_name, str):
            continue

        if type_name == "Pass":
            passes_per_team[team_name] += 1

    # Accumulate opponent passes: for each team, sum the passes of all other teams
    for team in match_teams:
        opp_pass_count = sum(
            count for t, count in passes_per_team.items() if t != team
        )
        counters_by_team[team].opponent_passes += opp_pass_count

    # Second pass: update all counters
    for event in events:
        team_obj = event.get("team")
        if not isinstance(team_obj, dict):
            continue
        team_name = team_obj.get("name")
        if not isinstance(team_name, str) or not team_name.strip():
            continue

        event_type = event.get("type", {})
        if not isinstance(event_type, dict):
            continue
        type_name = event_type.get("name")
        if not isinstance(type_name, str):
            continue

        stats = counters_by_team[team_name]

        if type_name == "Pass":
            stats.total_passes += 1
            stats.touches_proxy += 1
            if is_successful_pass(event):
                stats.complete_passes += 1

            if event.get("under_pressure") is True:
                stats.total_passes_under_pressure += 1
                if is_successful_pass(event):
                    stats.complete_passes_under_pressure += 1

        elif type_name == "Shot":
            stats.total_shots += 1
            shot_obj = event.get("shot")
            if isinstance(shot_obj, dict):
                outcome_obj = shot_obj.get("outcome")
                if isinstance(outcome_obj, dict) and outcome_obj.get("name") == "Goal":
                    stats.goals += 1

                xg_value = shot_obj.get("statsbomb_xg")
                if xg_value is not None:
                    try:
                        stats.xg_sum += float(xg_value)
                        stats.shots_with_xg += 1
                    except (TypeError, ValueError):
                        pass

        elif type_name == "Ball Receipt*":
            stats.touches_proxy += 1

        elif type_name in {"Dispossessed", "Miscontrol"}:
            stats.losses += 1

        elif type_name == "Pressure":
            stats.total_pressures += 1
            # Track pressure location for pressing height
            location = event.get("location")
            if isinstance(location, list) and len(location) >= 1:
                try:
                    x = float(location[0])
                    stats.pressure_location_x_sum += x
                    stats.pressure_location_count += 1
                except (TypeError, ValueError):
                    pass

        elif type_name in {"Interception", "Ball Recovery"}:
            stats.pressure_regains_proxy += 1


def compute_team_row(
    team_name: str,
    counters: TeamCounters,
) -> dict[str, int | str]:
    """Compute final metric row for one team."""
    pass_reliability = safe_percentage(counters.complete_passes, counters.total_passes)
    pass_under_pressure = safe_percentage(
        counters.complete_passes_under_pressure,
        counters.total_passes_under_pressure,
    )
    shot_conversion = safe_percentage(counters.goals, counters.total_shots)
    xg_per_shot = safe_percentage(counters.xg_sum, counters.shots_with_xg)
    ball_retention = safe_percentage(
        counters.touches_proxy - counters.losses,
        counters.touches_proxy,
    )
    pressure_success = safe_percentage(
        counters.pressure_regains_proxy,
        counters.total_pressures,
    )

    # Pressure aggression = average of pressing frequency and pressing height
    # Pressing frequency: pressures / opponent_passes × 100, capped at 100
    pressing_frequency = safe_percentage(
        counters.total_pressures, counters.opponent_passes
    )
    pressing_frequency = min(100, pressing_frequency)

    # Pressing height: avg pressure x-coordinate / 120 × 100
    if counters.pressure_location_count > 0:
        avg_pressure_x = counters.pressure_location_x_sum / counters.pressure_location_count
        pressing_height = max(0, min(100, round(avg_pressure_x / 120 * 100)))
    else:
        pressing_height = 50  # default neutral if no data

    pressure_aggression = round((pressing_frequency + pressing_height) / 2)
    pressure_aggression = max(0, min(100, pressure_aggression))

    return {
        "team": team_name,
        "pass_reliability": pass_reliability,
        "pass_under_pressure": pass_under_pressure,
        "shot_conversion": shot_conversion,
        "xg_per_shot": xg_per_shot,
        "ball_retention": ball_retention,
        "pressure_success": pressure_success,
        "pressure_aggression": pressure_aggression,
    }


def write_output_csv(rows: list[dict[str, int | str]], output_path: Path) -> None:
    """Write computed rows to output CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "team",
        "pass_reliability",
        "pass_under_pressure",
        "shot_conversion",
        "xg_per_shot",
        "ball_retention",
        "pressure_success",
        "pressure_aggression",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Extract per-team stats from StatsBomb open-data events.",
    )
    parser.add_argument(
        "--repo_path",
        type=Path,
        required=True,
        help="Path to statsbomb open-data root (contains data/events).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output CSV path.",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point for script execution."""
    args = parse_args()
    events_dir = args.repo_path / "data" / "events"
    event_files = list_event_files(events_dir)

    if not event_files:
        raise RuntimeError(f"No event files found in {events_dir}")

    counters_by_team: dict[str, TeamCounters] = defaultdict(TeamCounters)

    for event_file in event_files:
        events = load_json_file(event_file)
        if not isinstance(events, list):
            continue
        process_match_events(counters_by_team, events)

    rows = [
        compute_team_row(team_name, counters)
        for team_name, counters in counters_by_team.items()
    ]
    rows.sort(key=lambda row: str(row["team"]).lower())

    write_output_csv(rows, args.output)
    print(f"Wrote {len(rows)} teams to {args.output}")


if __name__ == "__main__":
    main()
