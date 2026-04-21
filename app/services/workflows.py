# -*- coding: utf-8 -*-
"""
Created on Wed Mar 18 10:44:29 2026

@author: michal.kalapus
"""

from __future__ import annotations

import json
import tempfile
import traceback
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from ringremoval.engine import Params
from ringremoval.projections import (
    ProjectionsToSinogramsSpec,
    build_sinogram_stack_from_projection_dir,
    sinograms_to_projection_files,
)
from ringremoval.stack import correct_tiff_stack

from .path_rules import resolve_output_dir
from .reconstruction_cera import run_cera_reconstruction


@dataclass
class ProjectionJob:
    input_dir: str
    output_mode: str = "down"  # custom | inside | up | down
    folder_name: str = "ring_corrected"
    custom_output_dir: str | None = None
    glob_pattern: str = "tomo_*.tif"
    recursive: bool = False
    overwrite: bool = False
    keep_temp: bool = False
    temp_dir: str | None = None
    workers: int = 12

    pipeline_mode: str = "ring_removal_only"  # ring_removal_only | reconstruction_only | ring_removal_and_reconstruction
    cera_python_exe: str | None = None
    cera_config_template: str | None = None
    reconstruction_folder_name: str = "reconstruction"
    reconstruction_name: str | None = None


def _emit(cb: Optional[Callable[[str], None]], message: str) -> None:
    if cb:
        cb(message)


def _used_ring_params_dict(params: Params) -> dict:
    base = {
        "mode": params.mode,
        "correction": params.correction,
    }

    per_method = {
        "auto": {},
        "algotom": {
            "snr": params.snr,
            "la_size": params.la_size,
            "sm_size": params.sm_size,
            "dim": params.dim,
        },
        "repair": {
            "repair_thresh": params.repair_thresh,
            "repair_max_cols": params.repair_max_cols,
        },
        "filtering": {
            "filt_sigma": params.filt_sigma,
            "filt_size": params.filt_size,
            "filt_dim": params.filt_dim,
            "filt_sort": params.filt_sort,
        },
        "sorting": {
            "sort_size": params.sort_size,
            "sort_dim": params.sort_dim,
        },
        "wavelet_fft": {
            "wfft_level": params.wfft_level,
            "wfft_size": params.wfft_size,
            "wfft_wavelet_name": params.wfft_wavelet_name,
            "wfft_window_name": params.wfft_window_name,
            "wfft_sort": params.wfft_sort,
        },
        "dead": {
            "dead_snr": params.dead_snr,
            "dead_size": params.dead_size,
            "dead_residual": params.dead_residual,
        },
        "large": {
            "large_snr": params.large_snr,
            "large_size": params.large_size,
            "large_drop_ratio": params.large_drop_ratio,
            "large_norm": params.large_norm,
        },
    }

    base.update(per_method.get(params.correction, {}))
    return base


def _job_settings_dict(job: ProjectionJob) -> dict:
    return {
        "input_dir": job.input_dir,
        "pipeline_mode": job.pipeline_mode,
        "output_mode": job.output_mode,
        "folder_name": job.folder_name,
        "custom_output_dir": job.custom_output_dir,
        "glob_pattern": job.glob_pattern,
        "recursive": job.recursive,
        "overwrite": job.overwrite,
        "keep_temp": job.keep_temp,
        "temp_dir": job.temp_dir,
        "workers": job.workers,
    }


def _reconstruction_settings_dict(job: ProjectionJob) -> dict:
    return {
        "cera_python_exe": job.cera_python_exe,
        "cera_config_template": job.cera_config_template,
        "reconstruction_folder_name": job.reconstruction_folder_name,
        "reconstruction_name": job.reconstruction_name or "<input folder name>",
    }


def _log_line(
    lines: list[str],
    cb: Optional[Callable[[str], None]],
    message: str,
) -> None:
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    lines.append(line)
    _emit(cb, line)


def _write_run_log(
    log_path: Path,
    *,
    started_at: datetime,
    finished_at: datetime,
    status: str,
    input_dir: Path,
    output_dir: Path,
    job: ProjectionJob,
    params: Params,
    log_lines: list[str],
    summary_path: Path | None = None,
    error_text: str | None = None,
) -> None:
    job_dict = _job_settings_dict(job)
    ring_params_dict = _used_ring_params_dict(params)
    recon_dict = _reconstruction_settings_dict(job)

    lines: list[str] = []
    lines.append("Micro-CT Ring Removal / Reconstruction Run Log")
    lines.append("=" * 52)
    lines.append(f"Started: {started_at.isoformat(timespec='seconds')}")
    lines.append(f"Finished: {finished_at.isoformat(timespec='seconds')}")
    lines.append(f"Status: {status}")
    lines.append(f"Input directory: {input_dir}")
    lines.append(f"Output directory: {output_dir}")
    if summary_path is not None:
        lines.append(f"JSON summary: {summary_path}")
    lines.append("")

    lines.append("Job settings")
    lines.append("-" * 20)
    for key, value in job_dict.items():
        lines.append(f"{key}: {value}")
    lines.append("")

    lines.append("Ring-correction parameters used in this run")
    lines.append("-" * 41)
    if job.pipeline_mode == "reconstruction_only":
        lines.append("not_run: True")
    else:
        for key, value in ring_params_dict.items():
            lines.append(f"{key}: {value}")
    lines.append("")

    lines.append("Reconstruction settings used in this run")
    lines.append("-" * 39)
    if job.pipeline_mode == "ring_removal_only":
        lines.append("not_run: True")
    else:
        for key, value in recon_dict.items():
            lines.append(f"{key}: {value}")
    lines.append("")

    lines.append("Run messages")
    lines.append("-" * 12)
    lines.extend(log_lines)

    if error_text:
        lines.append("")
        lines.append("Error traceback")
        lines.append("-" * 15)
        lines.append(error_text.rstrip())

    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def process_projection_job(
    job: ProjectionJob,
    params: Params,
    log: Optional[Callable[[str], None]] = None,
    progress: Optional[Callable[[int, int], None]] = None,
) -> dict:
    """
    Supported pipelines:
      1) ring_removal_only
      2) reconstruction_only
      3) ring_removal_and_reconstruction
    """
    input_dir = Path(job.input_dir).resolve()
    if not input_dir.exists() or not input_dir.is_dir():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    out_dir = Path(
        resolve_output_dir(
            input_dir=str(input_dir),
            mode=job.output_mode,
            folder_name=job.folder_name,
            custom_dir=job.custom_output_dir,
        )
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    run_ring = job.pipeline_mode in ("ring_removal_only", "ring_removal_and_reconstruction")
    run_recon = job.pipeline_mode in ("reconstruction_only", "ring_removal_and_reconstruction")
    if not run_ring and not run_recon:
        raise ValueError(f"Unknown pipeline mode: {job.pipeline_mode!r}")

    total_steps = (3 if run_ring else 0) + (1 if run_recon else 0)
    completed_steps = 0

    def advance_progress() -> None:
        nonlocal completed_steps
        completed_steps += 1
        if progress:
            progress(completed_steps, total_steps)

    started_at = datetime.now()
    log_lines: list[str] = []
    status = "SUCCESS"
    error_text: str | None = None
    summary_path = out_dir / "ringremoval_job_summary.json"
    log_path = out_dir / f"ringremoval_run_{started_at:%Y%m%d_%H%M%S}.log"

    temp_root_ctx = None
    temp_root: Path | None = None

    def log_line(message: str) -> None:
        _log_line(log_lines, log, message)

    log_line(f"Input: {input_dir}")
    log_line(f"Output root: {out_dir}")
    log_line(f"Pipeline mode: {job.pipeline_mode}")

    if run_ring:
        log_line(f"Requested correction: {params.correction}")
        log_line(f"Workers: {job.workers}")

        if job.temp_dir:
            temp_base = Path(job.temp_dir).resolve()
        else:
            temp_base = input_dir / "_ringremoval_temp"

        temp_base.mkdir(parents=True, exist_ok=True)

        if job.keep_temp:
            temp_root = (temp_base / f"{input_dir.name}_work").resolve()
            temp_root.mkdir(parents=True, exist_ok=True)
        else:
            temp_root_ctx = tempfile.TemporaryDirectory(dir=str(temp_base))
            temp_root = Path(temp_root_ctx.name)

    sino_meta = None
    corr_meta = None
    proj_meta = None
    recon_meta = None

    try:
        projection_source_for_reconstruction = input_dir

        if run_ring:
            assert temp_root is not None
            sino_stack = temp_root / "sinograms_stack.tif"
            corrected_sino_stack = temp_root / "sinograms_corrected_stack.tif"

            log_line("Step 1: Building sinograms from projection folder...")
            sino_spec = ProjectionsToSinogramsSpec(
                projections_dir=str(input_dir),
                output_mode="stack",
                output_sinogram_stack_tiff=str(sino_stack),
                glob_pattern=job.glob_pattern,
                recursive=job.recursive,
                overwrite=True,
                temp_dir=str(temp_root),
            )
            sino_meta = build_sinogram_stack_from_projection_dir(sino_spec)
            advance_progress()

            log_line("Step 2: Correcting ring artefacts in sinograms...")

            def on_stack_progress(done: int, total: int, page_idx: int, meta: dict) -> None:
                if "error" in meta:
                    log_line(f"FAIL page={page_idx}: {meta['error']}")
                else:
                    log_line(f"OK page={page_idx + 1}/{total}")

            corr_meta = correct_tiff_stack(
                input_tiff=str(sino_stack),
                output_sino_tiff=str(corrected_sino_stack),
                params=params,
                overwrite=True,
                workers=job.workers,
                on_progress=on_stack_progress,
            )
            advance_progress()

            log_line("Step 3: Converting corrected sinograms back to projections...")
            proj_meta = sinograms_to_projection_files(
                input_mode="stack",
                input_path=str(corrected_sino_stack),
                output_dir=str(out_dir),
                projection_template="tomo_{index:04d}.tif",
                overwrite=job.overwrite,
                temp_dir=str(temp_root),
            )
            advance_progress()

            projection_source_for_reconstruction = out_dir
        else:
            log_line("Ring-removal phase skipped by selected pipeline.")

        if run_recon:
            if not job.cera_python_exe:
                raise ValueError("CERA Python executable is required for reconstruction.")
            if not job.cera_config_template:
                raise ValueError("CERA config template is required for reconstruction.")

            recon_output_dir = out_dir / (job.reconstruction_folder_name.strip() or "reconstruction")
            recon_output_dir.mkdir(parents=True, exist_ok=True)

            recon_name = (job.reconstruction_name or input_dir.name).strip() or input_dir.name

            if run_ring:
                log_line("Step 4: Running CERA reconstruction from corrected projections...")
            else:
                log_line("Step 1: Running CERA reconstruction directly from input projections...")

            recon_meta = run_cera_reconstruction(
                python_exe=job.cera_python_exe,
                template_config_path=job.cera_config_template,
                projections_dir=str(projection_source_for_reconstruction),
                output_dir=str(recon_output_dir),
                output_name=recon_name,
                input_folder_name=input_dir.name,
                log=log_line,
            )
            advance_progress()
        else:
            log_line("Reconstruction phase skipped by selected pipeline.")

        summary = {
            "input_dir": str(input_dir),
            "output_dir": str(out_dir),
            "pipeline_mode": job.pipeline_mode,
            "ring_params_used": None if job.pipeline_mode == "reconstruction_only" else _used_ring_params_dict(params),
            "reconstruction_settings": None if job.pipeline_mode == "ring_removal_only" else _reconstruction_settings_dict(job),
            "sinogram_build": sino_meta,
            "correction": corr_meta,
            "projection_export": proj_meta,
            "reconstruction": recon_meta,
            "log_path": str(log_path),
            "summary_path": str(summary_path),
        }
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

        log_line(f"Saved summary: {summary_path}")
        log_line(f"Saved text log: {log_path}")

        return summary

    except Exception:
        status = "FAILED"
        error_text = traceback.format_exc()
        log_line("Run failed.")
        log_line(error_text.rstrip())
        raise

    finally:
        if temp_root_ctx is not None:
            try:
                temp_root_ctx.cleanup()
            except PermissionError as e:
                log_line(f"Temp cleanup warning: {e}")

        finished_at = datetime.now()
        _write_run_log(
            log_path,
            started_at=started_at,
            finished_at=finished_at,
            status=status,
            input_dir=input_dir,
            output_dir=out_dir,
            job=job,
            params=params,
            log_lines=log_lines,
            summary_path=summary_path if summary_path.exists() else None,
            error_text=error_text,
        )
