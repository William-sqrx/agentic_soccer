"""Evaluate the PAT model against historical StatsBomb matches.

For each match where both teams appear in ``data/processed/team_stats.csv``:

  1. Look up both teams' parameters from the CSV.
  2. Run PAT with home team = A, away team = B.
  3. Parse predicted (p_home_win, p_draw, p_home_loss) from PAT output.
  4. Build one-hot (w, d, l) from the actual scoreline (home team's POV).
  5. Accumulate argmax accuracy and Brier score.

Usage (PowerShell)::

    $env:PAT_PATH = 'C:\\...\\PAT3.Console.exe'
    python scripts/evaluate_model.py --limit 20    # quick smoke test
    python scripts/evaluate_model.py               # all eligible matches
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from tools import pat_runner as pr  # noqa: E402
from tools import team_lookup as tl  # noqa: E402
from tools.team_lookup import team_lookup  # noqa: E402

# Both modules resolve their project root to backend/, so default paths are
# wrong when invoked from this script. Redirect them to the actual repo paths.
pr._TEMPLATE_PATH = ROOT / "pcsp_model" / "football_pressure.pcsp"
pr._OUTPUT_LOG = ROOT / "pcsp_model" / "output.log"
tl._CSV_PATH = ROOT / "data" / "processed" / "team_stats.csv"

# Silence the per-call "Running: ..." line that pat_runner emits — it makes
# the eval log unreadable across thousands of matches.
pr.print = lambda *args, **kwargs: None

MATCHES_DIR = ROOT / "data" / "open-data" / "data" / "matches"
TEAMS_CSV = ROOT / "data" / "processed" / "team_stats.csv"
PREDICTIONS_CSV = ROOT / "scripts" / "eval_predictions.csv"

# Captures one PAT assertion block: assertion name + the [pmin, pmax] interval
# from its Verification Result. Non-greedy .*? with DOTALL hops over the
# intervening "Verification Result" header and settings.
_RESULT_RE = re.compile(
    r"Assertion: Match\(\) reaches (TeamAWins|TeamBWins|Draw) with prob"
    r".*?Probability \[([\d.]+),\s*([\d.]+)\]",
    re.DOTALL,
)


def parse_pat_output(output: str) -> dict[str, float]:
    """Extract {p_a_win, p_b_win, p_draw} from PAT verification output."""
    probs: dict[str, float] = {}
    for m in _RESULT_RE.finditer(output):
        name, low, _high = m.group(1), float(m.group(2)), float(m.group(3))
        probs[name] = low
    missing = {"TeamAWins", "TeamBWins", "Draw"} - probs.keys()
    if missing:
        raise ValueError(f"Missing PAT assertions in output: {sorted(missing)}")
    return {
        "p_a_win": probs["TeamAWins"],
        "p_b_win": probs["TeamBWins"],
        "p_draw": probs["Draw"],
    }


def load_known_teams() -> set[str]:
    """Lowercased team names that exist in team_stats.csv."""
    with TEAMS_CSV.open("r", encoding="utf-8") as f:
        return {row["team"].strip().lower() for row in csv.DictReader(f)}


def list_all_matches() -> list[dict]:
    """Flatten every season file under data/open-data/data/matches/ into one list."""
    matches: list[dict] = []
    for season_file in MATCHES_DIR.rglob("*.json"):
        with season_file.open("r", encoding="utf-8") as f:
            matches.extend(json.load(f))
    return matches


def actual_outcome(home_score: int, away_score: int) -> tuple[int, int, int]:
    """One-hot (w, d, l) from the home team's perspective."""
    if home_score > away_score:
        return (1, 0, 0)
    if home_score == away_score:
        return (0, 1, 0)
    return (0, 0, 1)


def brier_score(
    p_win: float, p_draw: float, p_loss: float, w: int, d: int, l: int
) -> float:
    return (p_win - w) ** 2 + (p_draw - d) ** 2 + (p_loss - l) ** 2


def argmax_correct(
    p_win: float, p_draw: float, p_loss: float, w: int, d: int, l: int
) -> bool:
    pred_idx = max(range(3), key=lambda i: (p_win, p_draw, p_loss)[i])
    actual_idx = (w, d, l).index(1)
    return pred_idx == actual_idx


def evaluate(limit: int | None) -> None:
    known = load_known_teams()
    all_matches = list_all_matches()
    eligible = [
        m for m in all_matches
        if m["home_team"]["home_team_name"].strip().lower() in known
        and m["away_team"]["away_team_name"].strip().lower() in known
    ]
    print(
        f"open-data: {len(all_matches)} matches | "
        f"both teams in CSV: {len(eligible)} | "
        f"teams in CSV: {len(known)}"
    )

    if limit is not None:
        eligible = eligible[:limit]
        print(f"--limit {limit}: evaluating first {len(eligible)} eligible matches")

    rows: list[dict] = []
    sum_brier = 0.0
    n_correct = 0
    n_evaluated = 0
    started = time.time()

    for i, match in enumerate(eligible, 1):
        home = match["home_team"]["home_team_name"]
        away = match["away_team"]["away_team_name"]
        try:
            team_a = team_lookup(home)
            team_b = team_lookup(away)
            output = pr.pat_runner(team_a, team_b)
            probs = parse_pat_output(output)
        except Exception as exc:
            print(f"  [{i}/{len(eligible)}] SKIP {home} vs {away}: {exc}")
            continue

        p_win = probs["p_a_win"]
        p_draw = probs["p_draw"]
        p_loss = probs["p_b_win"]
        w, d, l = actual_outcome(match["home_score"], match["away_score"])

        bs = brier_score(p_win, p_draw, p_loss, w, d, l)
        correct = argmax_correct(p_win, p_draw, p_loss, w, d, l)

        sum_brier += bs
        n_correct += int(correct)
        n_evaluated += 1

        rows.append({
            "match_id": match["match_id"],
            "home_team": home,
            "away_team": away,
            "home_score": match["home_score"],
            "away_score": match["away_score"],
            "p_home_win": round(p_win, 5),
            "p_draw": round(p_draw, 5),
            "p_home_loss": round(p_loss, 5),
            "actual_w": w,
            "actual_d": d,
            "actual_l": l,
            "brier": round(bs, 5),
            "correct": int(correct),
        })

        if i % 10 == 0 or i == len(eligible):
            elapsed = time.time() - started
            running_acc = n_correct / n_evaluated
            running_brier = sum_brier / n_evaluated
            print(
                f"  [{i}/{len(eligible)}] "
                f"acc={running_acc:.3f}  brier={running_brier:.3f}  "
                f"({elapsed:.0f}s, {elapsed / max(i, 1):.1f}s/match)"
            )

    if not n_evaluated:
        print("No matches evaluated — check that PAT_PATH is set and PAT runs.")
        return

    PREDICTIONS_CSV.parent.mkdir(parents=True, exist_ok=True)
    with PREDICTIONS_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print()
    print("=" * 60)
    print(f"Matches evaluated:  {n_evaluated}")
    print(f"Argmax accuracy:    {n_correct / n_evaluated:.4f}  "
          f"({n_correct}/{n_evaluated})")
    print(f"Mean Brier score:   {sum_brier / n_evaluated:.4f}  "
          "(0 = perfect, ~0.67 = uniform 1/3 each, 2 = worst)")
    print(f"Predictions saved:  {PREDICTIONS_CSV}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate PAT model accuracy.")
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Cap matches evaluated (for quick smoke testing).",
    )
    args = parser.parse_args()
    evaluate(limit=args.limit)


if __name__ == "__main__":
    main()
