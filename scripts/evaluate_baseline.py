"""Baseline evaluator: always predict home team wins.

Walks the same eligible matches as ``evaluate_model.py`` (both teams must
appear in ``team_stats.csv``) and writes a parallel predictions CSV with
the trivial prediction (p_home_win=1, p_draw=0, p_home_loss=0).

The output schema matches ``eval_predictions.csv`` so the two files are
directly comparable.

Usage::

    python scripts/evaluate_baseline.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from tools import team_lookup as tl  # noqa: E402

tl._CSV_PATH = ROOT / "data" / "processed" / "team_stats.csv"

MATCHES_DIR = ROOT / "data" / "open-data" / "data" / "matches"
TEAMS_CSV = ROOT / "data" / "processed" / "team_stats.csv"
BASELINE_CSV = ROOT / "scripts" / "baseline_predictions.csv"


def load_known_teams() -> set[str]:
    with TEAMS_CSV.open("r", encoding="utf-8") as f:
        return {row["team"].strip().lower() for row in csv.DictReader(f)}


def list_all_matches() -> list[dict]:
    matches: list[dict] = []
    for season_file in MATCHES_DIR.rglob("*.json"):
        with season_file.open("r", encoding="utf-8") as f:
            matches.extend(json.load(f))
    return matches


def actual_outcome(home_score: int, away_score: int) -> tuple[int, int, int]:
    if home_score > away_score:
        return (1, 0, 0)
    if home_score == away_score:
        return (0, 1, 0)
    return (0, 0, 1)


def main() -> None:
    known = load_known_teams()
    eligible = [
        m for m in list_all_matches()
        if m["home_team"]["home_team_name"].strip().lower() in known
        and m["away_team"]["away_team_name"].strip().lower() in known
    ]
    print(f"Eligible matches: {len(eligible)}")

    rows: list[dict] = []
    sum_brier = 0.0
    n_correct = 0

    # Trivial baseline: always (1, 0, 0)
    p_win, p_draw, p_loss = 1.0, 0.0, 0.0

    for match in eligible:
        w, d, l = actual_outcome(match["home_score"], match["away_score"])
        # Brier with this prediction reduces to (1-w)^2 + d^2 + l^2
        bs = (p_win - w) ** 2 + (p_draw - d) ** 2 + (p_loss - l) ** 2
        correct = (w == 1)

        sum_brier += bs
        n_correct += int(correct)

        rows.append({
            "match_id": match["match_id"],
            "home_team": match["home_team"]["home_team_name"],
            "away_team": match["away_team"]["away_team_name"],
            "home_score": match["home_score"],
            "away_score": match["away_score"],
            "p_home_win": p_win,
            "p_draw": p_draw,
            "p_home_loss": p_loss,
            "actual_w": w,
            "actual_d": d,
            "actual_l": l,
            "brier": round(bs, 5),
            "correct": int(correct),
        })

    BASELINE_CSV.parent.mkdir(parents=True, exist_ok=True)
    with BASELINE_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    n = len(rows)
    print()
    print("=" * 60)
    print(f"Matches evaluated:  {n}")
    print(f"Argmax accuracy:    {n_correct / n:.4f}  ({n_correct}/{n})")
    print(f"Mean Brier score:   {sum_brier / n:.4f}")
    print(f"Predictions saved:  {BASELINE_CSV}")


if __name__ == "__main__":
    main()
