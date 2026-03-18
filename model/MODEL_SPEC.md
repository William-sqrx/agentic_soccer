# Model Spec

## 3. Relevant Variables and Their Football Meaning

The model captures six key metrics per team, plus one **control variable** (pressure aggression) that the agent varies during sensitivity analysis.

| #     | Variable                | PCSP Macro Name         | Range | Football Meaning                                                                                                                    |
| ----- | ----------------------- | ----------------------- | ----- | ----------------------------------------------------------------------------------------------------------------------------------- |
| 1     | Pass Reliability        | `PASS_RELIABILITY_X`    | 0–100 | Percentage of attempted passes completed successfully.                                                                              |
| 2     | Pass Under Pressure     | `PASS_UNDER_PRESSURE_X` | 0–100 | Percentage of passes completed when the passer was flagged as `under_pressure`. Captures how well a team copes when pressed.        |
| 3     | Pressure Success Rate   | `PRESSURE_SUCCESS_X`    | 0–100 | Ratio of (interceptions + ball recoveries) to total pressure events applied. Approximates how often pressing wins the ball back.    |
| 4     | Shot Conversion         | `SHOT_CONVERSION_X`     | 0–100 | Goals scored from open play divided by total shots.                                                                                 |
| 5     | xG per Shot             | `XG_PER_SHOT_X`         | 0–100 | Average StatsBomb expected goals per shot, multiplied by 100 (e.g., 0.11 → 11). Measures quality of chances created.                |
| 6     | Ball Retention          | `BALL_RETENTION_X`      | 0–100 | 1 minus the loss rate, where losses = dispossessions + miscontrols. A high value means the team rarely gives the ball away cheaply. |
| **C** | **Pressure Aggression** | `PRESSURE_AGGRESSION_X` | 0–100 | **The control knob.** How aggressively Team X presses when the opponent has the ball. The AI Agent varies this to find the optimum. |

> `X` is replaced by `A` or `B` for each team.

---

## 4. How Each Variable Is Computed from StatsBomb JSON

StatsBomb open-data stores events in `data/events/{match_id}.json`. Each event is a JSON object with fields including `type.name`, `team.name`, `under_pressure`, and type-specific sub-objects (`pass`, `shot`, `dribble`, `duel`, etc.).

### 4.1 Pass Reliability

```
Source events:   type.name == "Pass"
Success:         pass.outcome is null/absent  (StatsBomb convention: no outcome = complete)
Failure:         pass.outcome.name is present (e.g., "Incomplete", "Out")
Formula:         pass_reliability = complete_passes / total_passes × 100
```

### 4.2 Pass Under Pressure

```
Source events:   type.name == "Pass"  AND  under_pressure == true
Success:         pass.outcome is null/absent
Formula:         pass_under_pressure = complete_under_pressure / total_under_pressure × 100
```

### 4.3 Pressure Success Rate

```
Numerator:       count(type.name == "Interception") + count(type.name == "Ball Recovery")
                 where team == pressing team
Denominator:     count(type.name == "Pressure") where team == pressing team
Formula:         pressure_success_rate = numerator / denominator × 100
```

### 4.4 Shot Conversion

```
Source events:   type.name == "Shot"
Goals:           shot.outcome.name == "Goal"
Formula:         shot_conversion = goals / total_shots × 100
```

### 4.5 xG per Shot

```
Source events:   type.name == "Shot"
Value:           shot.statsbomb_xg   (float, e.g. 0.12)
Formula:         xg_per_shot = mean(statsbomb_xg) × 100   (integer)
```

### 4.6 Ball Retention

```
Losses:          count(type.name == "Dispossessed") + count(type.name == "Miscontrol")
Touches proxy:   count(type.name == "Ball Receipt*") + count(type.name == "Pass")
Formula:         ball_retention = (1 - losses / touches_proxy) × 100
```

---

## 5. PCSP# Model Design

### 5.1 Model Structure

The match is abstracted into **possession phases**. `TOTAL_PHASES` controls how many phases are simulated (default 20, balancing realism against state-space size).

Each phase follows this flow:

```
 ┌──────────────────────────────────┐
 │       Team X Has the Ball        │
 └──────────┬───────────────────────┘
            │
     ┌──────▼──────┐
     │  Opponent    │
     │  Presses?    │
     └──┬───────┬───┘
   wins │       │ fails
   ball │       │
     ┌──▼──┐ ┌──▼──────────┐
     │Turn-│ │Team X       │
     │over │ │Advances     │
     └─────┘ └──┬──────┬───┘
           pass │      │ pass
           ok   │      │ fails
          ┌─────▼─┐  ┌─▼──────┐
          │Shoot- │  │Turnover│
          │ing    │  └────────┘
          │Chance │
          └──┬──┬─┘
        goal │  │ no goal
          ┌──▼┐ ┌▼──────────┐
          │+1 │ │Next Phase │
          └───┘ └───────────┘
```

### 5.2 Key Probabilistic Choices (all using weighted `pcase`)

**Press outcome:**

```
TeamAHasBall() = pcase {
    PRESS_B_WINS  : turnover_b -> TeamBHasBall()
    PRESS_B_FAILS : TeamAAdvances()
};
```

Where `PRESS_B_WINS = AGGRESSION_B × PRESS_SUCCESS_B × (100 − RETENTION_A) / 100`.

**Passing under pressure:**
Effective pass rate is a weighted blend of `PASS_RELIABILITY` (no pressure) and `PASS_UNDER_PRESSURE` (full pressure), with blending weight = `PRESSURE_AGGRESSION`.

**Shot conversion with high-press bonus:**
When the opponent presses high and the press is beaten, the attacking team gets space behind the defensive line. The model adds a bonus: `(AGGRESSION − 50) × XG / 200`. Over-pressing (>50) gives the opponent better chances when they beat the press.

### 5.3 Variable Updates

All variable mutations occur inside event prefixes:

```
goal_a{goalsA++;} -> Match()
next_phase{phase++;} -> TeamAHasBall()
```

### 5.4 Assertions

```
#define TeamAWins  goalsA > goalsB && phase >= TOTAL_PHASES;
#define TeamBWins  goalsB > goalsA && phase >= TOTAL_PHASES;
#define Draw       goalsA == goalsB && phase >= TOTAL_PHASES;

#assert Match() reaches TeamAWins with prob;
#assert Match() reaches TeamBWins with prob;
#assert Match() reaches Draw with prob;
```

---

## 6. AI Agent Workflow

### 6.1 User Query

> "Should Barcelona press Liverpool more aggressively to increase their chance of winning?"

### 6.2 Agent Steps

1. **Look up** `team_stats.csv` for rows where `team == "Barcelona"` and `team == "Liverpool"`.

2. **Prepare** the PCSP template — for each aggression level (e.g., 20, 30, 40, 50, 60, 70, 80, 90):
   - Replace all `#define` macros for Team A (Barcelona) and Team B (Liverpool).
   - Set `PRESSURE_AGGRESSION_A` to the current test value.
   - Keep `PRESSURE_AGGRESSION_B` at Liverpool's natural aggression (from data, or sweep it too).

3. **Execute** PAT for each file:

   ```
   PAT3.Console.exe -pcsp football_pressure.pcsp
   ```

4. **Parse** PAT output — extract the probability from lines like:

   ```
   The Assertion (Match() reaches TeamAWins with prob) is Valid.
   Min probability = 0.312; Max probability = 0.428
   ```

5. **Synthesise** results into a table and recommendation.

### 6.3 Macro Editing (Pseudocode for the Agent)

```python
import re, subprocess

def run_analysis(team_a_stats, team_b_stats, aggression_level, pcsp_template_path):
    with open(pcsp_template_path, 'r') as f:
        code = f.read()

    replacements = {
        'PASS_RELIABILITY_A':     team_a_stats['pass_reliability'],
        'PASS_UNDER_PRESSURE_A':  team_a_stats['pass_under_pressure'],
        'SHOT_CONVERSION_A':      team_a_stats['shot_conversion'],
        'XG_PER_SHOT_A':          team_a_stats['xg_per_shot'],
        'BALL_RETENTION_A':       team_a_stats['ball_retention'],
        'PRESSURE_SUCCESS_A':     team_a_stats['pressure_success_rate'],
        'PASS_RELIABILITY_B':     team_b_stats['pass_reliability'],
        'PASS_UNDER_PRESSURE_B':  team_b_stats['pass_under_pressure'],
        'SHOT_CONVERSION_B':      team_b_stats['shot_conversion'],
        'XG_PER_SHOT_B':          team_b_stats['xg_per_shot'],
        'BALL_RETENTION_B':       team_b_stats['ball_retention'],
        'PRESSURE_SUCCESS_B':     team_b_stats['pressure_success_rate'],
        'PRESSURE_AGGRESSION_A':  aggression_level,
        'PRESSURE_AGGRESSION_B':  team_b_stats.get('default_aggression', 50),
    }

    for macro, value in replacements.items():
        pattern = rf'(#define\s+{macro}\s+)\d+;'
        code = re.sub(pattern, rf'\g<1>{value};', code)

    out_path = 'matchup.pcsp'
    with open(out_path, 'w') as f:
        f.write(code)

    result = subprocess.run(
        ['PAT3.Console.exe', '-pcsp', out_path],
        capture_output=True, text=True
    )
    return parse_pat_output(result.stdout)
```

---

## 8. Notes on State-Space Management

To keep PAT verification tractable, `TOTAL_PHASES` defaults to 20. Each "phase" represents roughly a 4–5 minute block of play. The model can be made finer-grained (e.g., `TOTAL_PHASES = 40`) at the cost of longer verification time.

All `pcase` weights are precomputed as `#define` integer constants. The formulas are designed so that weights remain positive across the full 0–100 aggression range. If extreme parameter combinations produce a zero or negative weight, add a floor of 1 to the relevant `#define`.
