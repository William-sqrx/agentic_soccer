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

# PAT prints "is NOT valid" (without a Probability line) when reachability
# probability is exactly 0 — we treat that as p=0.0. We split the output into
# per-assertion blocks so the prob regex cannot cross assertion boundaries.
_ASSERTION_HEADER_RE = re.compile(
    r"Assertion: Match\(\) reaches (TeamAWins|TeamBWins|Draw) with prob"
)
_PROB_RE = re.compile(r"Probability \[([\d.]+),\s*([\d.]+)\]")
_NOT_VALID_RE = re.compile(r"is NOT valid")


def parse_pat_output(output: str) -> dict[str, float]:
    """Extract {p_a_win, p_b_win, p_draw} from PAT verification output."""
    headers = [
        (m.group(1), m.start()) for m in _ASSERTION_HEADER_RE.finditer(output)
    ]
    if len(headers) != 3:
        raise ValueError(
            f"Expected 3 PAT assertions, found {len(headers)}: "
            f"{[h for h, _ in headers]}"
        )
    probs: dict[str, float] = {}
    for i, (name, start) in enumerate(headers):
        end = headers[i + 1][1] if i + 1 < len(headers) else len(output)
        block = output[start:end]
        m_prob = _PROB_RE.search(block)
        if m_prob:
            probs[name] = float(m_prob.group(1))
        elif _NOT_VALID_RE.search(block):
            probs[name] = 0.0
        else:
            raise ValueError(f"Cannot parse {name} block: {block[:200]!r}")
    return {
        "p_a_win": probs["TeamAWins"],
        "p_b_win": probs["TeamBWins"],
        "p_draw": probs["Draw"],
    }


def load_existing_predictions() -> tuple[list[dict], set[int]]:
    """Load already-evaluated rows from PREDICTIONS_CSV (empty if file missing)."""
    if not PREDICTIONS_CSV.exists():
        return [], set()
    with PREDICTIONS_CSV.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return rows, {int(r["match_id"]) for r in rows}


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


def evaluate(limit: int | None, resume: bool) -> None:
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

    existing_rows: list[dict] = []
    done_ids: set[int] = set()
    if resume:
        existing_rows, done_ids = load_existing_predictions()
        eligible = [m for m in eligible if m["match_id"] not in done_ids]
        print(f"--resume: {len(done_ids)} matches already in CSV; "
              f"{len(eligible)} new to evaluate")

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

    combined = existing_rows + rows
    if not combined:
        print("No matches evaluated — check that PAT_PATH is set and PAT runs.")
        return

    PREDICTIONS_CSV.parent.mkdir(parents=True, exist_ok=True)
    with PREDICTIONS_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=combined[0].keys())
        writer.writeheader()
        writer.writerows(combined)

    # Recompute summary across the full combined CSV (existing + newly added)
    total_correct = sum(int(r["correct"]) for r in combined)
    total_brier = sum(float(r["brier"]) for r in combined)
    total = len(combined)

    print()
    print("=" * 60)
    if existing_rows:
        print(f"Newly evaluated:    {n_evaluated}  "
              f"(existing rows reused: {len(existing_rows)})")
    print(f"Matches in CSV:     {total}")
    print(f"Argmax accuracy:    {total_correct / total:.4f}  "
          f"({total_correct}/{total})")
    print(f"Mean Brier score:   {total_brier / total:.4f}  "
          "(0 = perfect, ~0.67 = uniform 1/3 each, 2 = worst)")
    print(f"Predictions saved:  {PREDICTIONS_CSV}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate PAT model accuracy.")
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Cap matches evaluated (for quick smoke testing).",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Skip matches already in eval_predictions.csv and append new ones.",
    )
    args = parser.parse_args()
    evaluate(limit=args.limit, resume=args.resume)


if __name__ == "__main__":
    main()
