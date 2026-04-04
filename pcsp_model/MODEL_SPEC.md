# Model Spec

## 3. Relevant Variables and Their Football Meaning

The model captures six key metrics per team, plus one **data-grounded variable** (pressure aggression) that also serves as the control variable during sensitivity analysis.

| #   | Variable              | PCSP Macro Name         | Range | Football Meaning                                                                                                                                                                                                                                                |
| --- | --------------------- | ----------------------- | ----- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Pass Reliability      | `PASS_RELIABILITY_X`    | 0–100 | Percentage of attempted passes completed successfully.                                                                                                                                                                                                          |
| 2   | Pass Under Pressure   | `PASS_UNDER_PRESSURE_X` | 0–100 | Percentage of passes completed when the passer was flagged as `under_pressure`. Captures how well a team copes when pressed.                                                                                                                                    |
| 3   | Pressure Success Rate | `PRESSURE_SUCCESS_X`    | 0–100 | Ratio of (interceptions + ball recoveries) to total pressure events applied. Approximates how often pressing wins the ball back.                                                                                                                                |
| 4   | Shot Conversion       | `SHOT_CONVERSION_X`     | 0–100 | Goals scored from open play divided by total shots.                                                                                                                                                                                                             |
| 5   | xG per Shot           | `XG_PER_SHOT_X`         | 0–100 | Average StatsBomb expected goals per shot, multiplied by 100 (e.g., 0.11 → 11). Measures quality of chances created.                                                                                                                                            |
| 6   | Ball Retention        | `BALL_RETENTION_X`      | 0–100 | 1 minus the loss rate, where losses = dispossessions + miscontrols. A high value means the team rarely gives the ball away cheaply.                                                                                                                             |
| 7   | Pressure Aggression   | `PRESSURE_AGGRESSION_X` | 0–100 | How aggressively the team presses when the opponent has the ball. Computed from data (see 4.7). Also serves as the **control variable** — the AI Agent uses each team's historical value as the default, and sweeps Team A's value during sensitivity analysis. |

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

### 4.7 Pressure Aggression

This variable captures how aggressively a team presses when the opponent has the ball. It is derived from two complementary signals:

**Signal 1 — Pressing frequency:** How often the team applies pressure relative to the opponent's time on the ball. Computed as `total_pressures / opponent_total_passes × 100`, capped at 100. A team that pressures on 40% of opponent passes is more aggressive than one at 20%.

**Signal 2 — Pressing height:** Where on the pitch the pressures occur. StatsBomb `Pressure` events have a `location` field where `location[0]` is the x-coordinate (0 = own goal line, 120 = opponent goal line). We compute `avg_pressure_x / 120 × 100` to normalise to 0–100. A team pressing at average x=80 (opponent's third) scores ~67; a team pressing at x=40 (own half) scores ~33.

**Combined formula:**

```
pressure_aggression = (pressing_frequency + pressing_height) / 2
```

Equal weight is given to both signals. A team that presses both frequently AND high up the pitch scores near 100. A team that presses rarely AND deep scores near 0.

```
Source events:       type.name == "Pressure" (for the pressing team)
                     type.name == "Pass" (for the opponent, to compute opponent_total_passes)
Location field:      location[0] on Pressure events (x-coordinate, 0–120)
Pressing frequency:  min(100, total_pressures / opponent_total_passes × 100)
Pressing height:     avg(location[0] across all Pressure events) / 120 × 100
Formula:             pressure_aggression = (pressing_frequency + pressing_height) / 2
```

**Why this matters for the model:**

- The agent uses each team's historical `pressure_aggression` as the **default** value for `PRESSURE_AGGRESSION_X` in the PCSP model.
- When the user asks "should Team A be more aggressive?", the agent keeps `PRESSURE_AGGRESSION_B` at Team B's historical value and sweeps `PRESSURE_AGGRESSION_A` across a range.
- The historical value also enables **validation**: we can run the model with both teams' historical aggression values and compare the predicted win probability against actual match outcomes.

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

**Shot conversion (Finishing Skill Multiplier model):**

Historically, the team faces chances of average quality `XG_PER_SHOT` and converts at rate `SHOT_CONVERSION`. These two values define a known data point. We can think of `SHOT_CONVERSION` as the output of a function that takes `XG_PER_SHOT` as input — it tells us "this team converts at this rate given this average chance quality."

The ratio `SHOT_CONVERSION / XG_PER_SHOT` is the team's **finishing skill multiplier**: >1 means clinical (converts better than xG predicts), <1 means wasteful. We model conversion as a linear function of chance quality: `f(xg) = (CONVERSION / XG) × xg`.

When the opponent's press is beaten, the effective quality of the chance changes because there is more or less space behind the defensive line:

```
XG_EFFECTIVE = XG_PER_SHOT + (opp_aggression − 50) × SPACE_BONUS_K / 100
```

We feed this adjusted quality into the finishing skill function to predict the conversion rate for this particular chance:

```
SHOT_GOAL = CONVERSION × XG_EFFECTIVE / XG_PER_SHOT
          = CONVERSION × (XG×100 + (agg−50)×K) / (XG×100)
```

Key properties of this formula:

| Condition                    | Effect                                  | Correct?                             |
| ---------------------------- | --------------------------------------- | ------------------------------------ |
| `SHOT_CONVERSION` increases  | `SHOT_GOAL` increases proportionally    | ✓ Clinical teams score more          |
| `XG_PER_SHOT` increases      | `SHOT_GOAL` increases (via numerator)   | ✓ Better chance creators score more  |
| Opponent aggression > 50     | `SHOT_GOAL` > `SHOT_CONVERSION`         | ✓ Beating a high press yields space  |
| Opponent aggression = 50     | `SHOT_GOAL` = `SHOT_CONVERSION` exactly | ✓ Base case preserved                |
| Opponent aggression < 50     | `SHOT_GOAL` < `SHOT_CONVERSION`         | ✓ Deep block harder to score against |
| Higher finishing skill ratio | Amplifies the bonus from beating press  | ✓ Clinical teams exploit space more  |

`SPACE_BONUS_K` (default 10) controls sensitivity. With K=10 and aggression=100, the bonus is +5 xG units. `XG_PER_SHOT` must be ≥ 1 (Python wrapper must clamp) to avoid division by zero.

Worked example (CONVERSION=12, XG=11, K=10):

| Opp Aggression | XG_EFFECTIVE | SHOT_GOAL | SHOT_MISS |
| -------------: | -----------: | --------: | --------: |
|             20 |            8 |         8 |        92 |
|             50 |           11 |        12 |        88 |
|             70 |           13 |        14 |        86 |
|             90 |           15 |        16 |        84 |

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
   - There will be multiple test values (the more the better)
   - Test value will include the team A's historical `pressure_aggression` from the CSV, and will have differing values around it
   - PAT will be run multiple times so that the AI finds the `pressure_aggression` that yields local maximum
   - Set `PRESSURE_AGGRESSION_B` to Liverpool's historical `pressure_aggression` from the CSV.

3. **Execute** PAT for each file via tool call provided by backend server

- the tool will execute

```
PAT3.Console.exe -pcsp football_pressure.pcsp output.log
```

- and extract the probability from lines like from `output.log`:
  - or deliver the entire log back to Agent (up to implementation)

```
The Assertion (Match() reaches TeamAWins with prob) is Valid.
Min probability = 0.312; Max probability = 0.428
```

1. **Synthesise** results into a table and recommendation.

---

## 8. Notes on State-Space Management

To keep PAT verification tractable, `TOTAL_PHASES` defaults to 20. Each "phase" represents roughly a 4–5 minute block of play. The model can be made finer-grained (e.g., `TOTAL_PHASES = 40`) at the cost of longer verification time.

All `pcase` weights are precomputed as `#define` integer constants. The formulas are designed so that weights remain positive across the full 0–100 aggression range. If extreme parameter combinations produce a zero or negative weight, add a floor of 1 to the relevant `#define`.
