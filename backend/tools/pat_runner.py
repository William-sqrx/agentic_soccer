"""PAT wrapper: macro substitution + CLI execution + output retrieval.

Reads the PCSP# template, substitutes #define macros with concrete
integer values from Team objects, invokes PAT via CLI, and returns
the raw verification output.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Ensure the project root is on sys.path so `model` is importable regardless
# of how this script is invoked (e.g. `python tools/pat_runner.py`).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from model.team import Team

# Resolve paths relative to the project root (one level above tools/)
_TEMPLATE_PATH = _PROJECT_ROOT / "pcsp_model" / "football_pressure.pcsp"
_OUTPUT_LOG = _PROJECT_ROOT / "pcsp_model" / "output.log"

# Default executable name for PAT.  Override with the PAT_PATH environment
# variable if PAT3.Console.exe is not on your system PATH.
_PAT_DEFAULT_EXE = "PAT3.Console.exe"


def _use_wine() -> bool:
    """Return True if PAT must be invoked through Wine.

    Controlled by the ``PAT_USE_WINE`` environment variable.
    Set ``PAT_USE_WINE=1`` inside the Docker container where
    Wine is available and PAT3.Console.exe cannot run natively.
    """
    return os.environ.get("PAT_USE_WINE", "").strip() == "1"


def _resolve_pat_executable() -> str:
    """Return the path to the PAT executable.

    Resolution order:
        1. ``PAT_PATH`` environment variable (full path to the executable).
        2. ``PAT3.Console.exe`` found on the system PATH via ``shutil.which``.

    Raises:
        FileNotFoundError: If the executable cannot be located.
    """
    # 1. Explicit environment variable
    env_path = os.environ.get("PAT_PATH")
    if env_path:
        if os.path.isfile(env_path):
            return env_path
        raise FileNotFoundError(
            f"PAT_PATH is set to '{env_path}' but the file does not exist."
        )

    # 2. Look for PAT3.Console.exe on the system PATH
    found = shutil.which(_PAT_DEFAULT_EXE)
    if found:
        return found

    raise FileNotFoundError(
        f"Could not find '{_PAT_DEFAULT_EXE}' on the system PATH.  "
        "Either add its directory to PATH or set the PAT_PATH environment "
        "variable to the full path of the executable "
        "(e.g. PAT_PATH=C:\\Program Files\\PAT\\PAT3.Console.exe)."
    )


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


def _build_command(pat_exe: str, pcsp_path: str, output_log: str) -> list[str]:
    """Build the subprocess command list for invoking PAT.

    When ``PAT_USE_WINE=1`` the command is prefixed with ``wine`` so
    the Windows executable runs under the Wine compatibility layer
    inside the Docker container.
    """
    cmd = [pat_exe, "-pcsp", pcsp_path, output_log]
    if _use_wine():
        cmd = ["wine"] + cmd
    return cmd


def pat_runner(team_a: Team, team_b: Team) -> str:
    """Run PAT model checking with the given team parameters.

    Steps:
        1. Read the PCSP template from ``pcsp_model/football_pressure.pcsp``.
        2. Substitute ``#define`` macros with clamped team parameter values.
        3. Write the substituted model to a temporary ``.pcsp`` file.
        4. Invoke ``PAT3.Console.exe -pcsp <tmp_file> <output_log>`` via subprocess.
           When running inside Docker (``PAT_USE_WINE=1``), the command is
           prefixed with ``wine``.
        5. Read and return the verification output from the log file.

    Args:
        team_a: The team whose pressure aggression is being analysed.
        team_b: The opponent team.

    Returns:
        The raw PAT verification output as a string.

    Raises:
        FileNotFoundError: If the PCSP template or PAT executable cannot be found.
        subprocess.CalledProcessError: If PAT exits with a non-zero code.
        RuntimeError: If the output log file is not created by PAT.
    """
    # 0. Resolve the PAT executable (fail fast with a clear message)
    pat_exe = _resolve_pat_executable()

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

        # 4. Run PAT (via Wine inside Docker, natively on Windows)
        output_log = str(_OUTPUT_LOG)
        cmd = _build_command(pat_exe, tmp_path, output_log)
        print(f"Running: {' '.join(cmd)}")
        subprocess.run(
            cmd,
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


if __name__ == "__main__":
    # Example usage with dummy teams
    team_a = Team(50, 50, 50, 50, 50, 50, 50)
    team_b = Team(50, 50, 50, 50, 50, 50, 50)
    output = pat_runner(team_a, team_b)
    print(output)
