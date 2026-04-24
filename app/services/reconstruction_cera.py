# -*- coding: utf-8 -*-
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable, Optional


def _emit(cb: Optional[Callable[[str], None]], message: str) -> None:
    if cb:
        cb(message)


def render_cera_config(
    template_path: str | Path,
    rendered_path: str | Path,
    *,
    projections_dir: str | Path,
    output_dir: str | Path,
    output_name: str,
    input_folder_name: str,
) -> Path:
    """
    Render a CERA config template by replacing a few simple placeholders.

    Supported placeholders:
      {{PROJECTIONS_DIR}}
      {{PROJECTIONS_DIR_POSIX}}
      {{OUTPUT_DIR}}
      {{OUTPUT_DIR_POSIX}}
      {{OUTPUT_NAME}}
      {{INPUT_FOLDER_NAME}}
    """
    template_path = Path(template_path).resolve()
    rendered_path = Path(rendered_path).resolve()
    projections_dir = Path(projections_dir).resolve()
    output_dir = Path(output_dir).resolve()

    if not template_path.exists():
        raise FileNotFoundError(f"CERA config template not found: {template_path}")

    text = template_path.read_text(encoding="utf-8")

    replacements = {
        "{{PROJECTIONS_DIR}}": str(projections_dir),
        "{{PROJECTIONS_DIR_POSIX}}": projections_dir.as_posix(),
        "{{OUTPUT_DIR}}": str(output_dir),
        "{{OUTPUT_DIR_POSIX}}": output_dir.as_posix(),
        "{{OUTPUT_NAME}}": output_name,
        "{{INPUT_FOLDER_NAME}}": input_folder_name,
    }

    for key, value in replacements.items():
        text = text.replace(key, value)

    rendered_path.parent.mkdir(parents=True, exist_ok=True)
    rendered_path.write_text(text, encoding="utf-8")
    return rendered_path


def run_cera_reconstruction(
    *,
    python_exe: str,
    template_config_path: str,
    projections_dir: str,
    output_dir: str,
    output_name: str,
    input_folder_name: str,
    log: Optional[Callable[[str], None]] = None,
    render_config: bool = True,
) -> dict:
    """
    Launch the standalone CERA helper script in a separate Python environment.

    This keeps the main GUI environment independent from the Python version
    required by the cerapy wheel.
    """
    python_path = Path(python_exe).resolve()
    template_path = Path(template_config_path).resolve()
    projections_path = Path(projections_dir).resolve()
    output_path = Path(output_dir).resolve()

    if not python_path.exists():
        raise FileNotFoundError(f"CERA Python executable not found: {python_path}")
    if not template_path.exists():
        raise FileNotFoundError(f"CERA config template not found: {template_path}")
    if not projections_path.exists() or not projections_path.is_dir():
        raise FileNotFoundError(f"Projection directory for reconstruction not found: {projections_path}")

    output_path.mkdir(parents=True, exist_ok=True)

    helper_script = Path(__file__).resolve().parents[2] / "tools" / "run_cera_reconstruction.py"
    if not helper_script.exists():
        raise FileNotFoundError(f"CERA helper script not found: {helper_script}")

    safe_output_name = (output_name or input_folder_name or projections_path.name).strip()

    if render_config:
        config_to_use = output_path / f"{safe_output_name}_cera_rendered.config"

        render_cera_config(
            template_path,
            config_to_use,
            projections_dir=projections_path,
            output_dir=output_path,
            output_name=safe_output_name,
            input_folder_name=input_folder_name,
        )
    else:
        config_to_use = template_path
        _emit(log, f"Using existing CERA config without rendering: {config_to_use}")

    cmd = [str(python_path), "-u", str(helper_script), "--config", str(config_to_use)]
    _emit(log, f"Starting CERA reconstruction with: {subprocess.list2cmdline(cmd)}")

    output_lines: list[str] = []
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip()
        if not line:
            continue
        output_lines.append(line)
        _emit(log, f"[CERA] {line}")

    return_code = proc.wait()
    if return_code != 0:
        raise RuntimeError(f"CERA reconstruction failed with exit code {return_code}")

    return {
        "python_exe": str(python_path),
        "template_config_path": str(template_path),
        "config_path_used": str(config_to_use),
        "rendered_config_path": str(config_to_use) if render_config else None,
        "projections_dir": str(projections_path),
        "output_dir": str(output_path),
        "output_name": safe_output_name,
        "command": cmd,
        "output_lines": output_lines,
    }
