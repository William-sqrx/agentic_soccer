"""PAT wrapper: macro substitution + CLI execution + output retrieval.

Reads the PCSP# template, substitutes #define macros with concrete
integer values from Team objects, invokes PAT via CLI, and returns
the raw verification output.
"""

import os
import re
import subprocess
import tempfile
from pathlib import Path

from model.team import Team

# Resolve paths relative to the project root (one level above tools/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_TEMPLATE_PATH = _PROJECT_ROOT / "pcsp_model" / "football_pressure.pcsp"
_OUTPUT_LOG = _PROJECT_ROOT / "pcsp_model" / "output.log"


def _clamp(value: int, minimum: int = 1, maximum: int = 100) -> int:
    """Clamp an integer to [minimum, maximum].

    All pcase weights in the PCSP model must be positive integers.
    Clamping inputs to at least 1 prevents zero or negative weights
    at extreme parameter values.  XG_PER_SHOT in particular must be
    >= 1 because it appears as a divisor in the shot-conversion formula.
    """
    return max(minimum, min(maximum, value))


def _build_macro_map(team_a: Team, team_b: Team) -> dict[str, int]:
    """Build a mapping from #define macro names to clamped integer values."""
    return {
        # --- Team A ---
        "PASS_RELIABILITY_A": _clamp(team_a.pass_reliability),
        "PASS_UNDER_PRESSURE_A": _clamp(team_a.pass_under_pressure),
        "SHOT_CONVERSION_A": _clamp(team_a.shot_conversion),
        "XG_PER_SHOT_A": _clamp(team_a.xg_per_shot),
        "BALL_RETENTION_A": _clamp(team_a.ball_retention),
        "PRESSURE_SUCCESS_A": _clamp(team_a.pressure_success),
        "PRESSURE_AGGRESSION_A": _clamp(team_a.pressure_aggression),
        # --- Team B ---
        "PASS_RELIABILITY_B": _clamp(team_b.pass_reliability),
        "PASS_UNDER_PRESSURE_B": _clamp(team_b.pass_under_pressure),
        "SHOT_CONVERSION_B": _clamp(team_b.shot_conversion),
        "XG_PER_SHOT_B": _clamp(team_b.xg_per_shot),
        "BALL_RETENTION_B": _clamp(team_b.ball_retention),
        "PRESSURE_SUCCESS_B": _clamp(team_b.pressure_success),
        "PRESSURE_AGGRESSION_B": _clamp(team_b.pressure_aggression),
    }


def _substitute_macros(template: str, team_a: Team, team_b: Team) -> str:
    """Replace #define macros in the PCSP template with concrete integers.

    Uses regex to match lines of the form ``#define MACRO_NAME <value>;``
    and overwrites <value> with the corresponding team parameter.
    Only the 14 injectable team macros are touched; all other #define
    lines (derived weights, propositions, etc.) are left unchanged.
    """
    macros = _build_macro_map(team_a, team_b)
    result = template
    for macro_name, value in macros.items():
        # Pattern: #define MACRO_NAME <anything>;
        pattern = rf"(#define\s+{macro_name}\s+)[^;]*(;)"
        result = re.sub(pattern, rf"\g<1>{value}\2", result)
    return result


def pat_runner(team_a: Team, team_b: Team) -> str:
    """Run PAT model checking with the given team parameters.

    Steps:
        1. Read the PCSP template from ``pcsp_model/football_pressure.pcsp``.
        2. Substitute ``#define`` macros with clamped team parameter values.
        3. Write the substituted model to a temporary ``.pcsp`` file.
        4. Invoke ``pat -pcsp <tmp_file> <output_log>`` via subprocess.
        5. Read and return the verification output from the log file.

    Args:
        team_a: The team whose pressure aggression is being analysed.
        team_b: The opponent team.

    Returns:
        The raw PAT verification output as a string.

    Raises:
        FileNotFoundError: If the PCSP template does not exist.
        subprocess.CalledProcessError: If PAT exits with a non-zero code.
        RuntimeError: If the output log file is not created by PAT.
    """
    # 1. Read the template
    if not _TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"PCSP template not found: {_TEMPLATE_PATH}")
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")

    # 2. Substitute parameters
    substituted = _substitute_macros(template, team_a, team_b)

    # 3. Write to a temporary PCSP file
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".pcsp")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as tmp_file:
            tmp_file.write(substituted)

        # 4. Run PAT
        output_log = str(_OUTPUT_LOG)
        subprocess.run(
            ["pat", "-pcsp", tmp_path, output_log],
            check=True,
            capture_output=True,
            text=True,
        )

        # 5. Retrieve the output from the log file
        if not _OUTPUT_LOG.exists():
            raise RuntimeError(
                f"PAT did not produce an output log at {_OUTPUT_LOG}"
            )
        return _OUTPUT_LOG.read_text(encoding="utf-8")

    finally:
        # Clean up the temporary PCSP file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
