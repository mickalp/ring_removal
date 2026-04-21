# -*- coding: utf-8 -*-
"""
Created on Wed Mar 18 10:46:11 2026

@author: michal.kalapus
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QCheckBox,
    QComboBox,
    QPlainTextEdit,
    QProgressBar,
    QSpinBox,
    QDoubleSpinBox,
    QFormLayout,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.gui.workers import ProjectionJobWorker
from app.services.workflows import ProjectionJob
from ringremoval.engine import Params


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Micro-CT Ring Removal & Reconstruction")
        self.resize(1100, 850)

        self.thread_pool = QThreadPool.globalInstance()
        self.pending_jobs = 0

        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)

        root.addWidget(self._build_input_group())
        root.addWidget(self._build_pipeline_group())
        self.output_group = self._build_output_group()
        root.addWidget(self.output_group)

        self.algorithm_group = self._build_algorithm_group()
        root.addWidget(self.algorithm_group)

        self.reconstruction_group = self._build_reconstruction_group()
        root.addWidget(self.reconstruction_group)

        root.addWidget(self._build_run_group())
        root.addWidget(self._build_log_group())

        self._update_pipeline_state()

    def _make_int_spin(self, value: int, minimum: int = 1, maximum: int = 100000) -> QSpinBox:
        w = QSpinBox()
        w.setRange(minimum, maximum)
        w.setValue(value)
        return w

    def _make_float_spin(
        self,
        value: float,
        minimum: float = 0.0,
        maximum: float = 1_000_000.0,
        decimals: int = 3,
    ) -> QDoubleSpinBox:
        w = QDoubleSpinBox()
        w.setRange(minimum, maximum)
        w.setDecimals(decimals)
        w.setValue(value)
        return w

    def _add_correction_page(
        self,
        name: str,
        rows: list[tuple[str, QWidget]] | None = None,
        note: str | None = None,
    ) -> None:
        page = QWidget()
        form = QFormLayout(page)

        if note:
            lbl = QLabel(note)
            lbl.setWordWrap(True)
            form.addRow(lbl)

        for label_text, widget in (rows or []):
            form.addRow(label_text, widget)

        self.correction_pages[name] = page
        self.correction_stack.addWidget(page)

    def _update_correction_page(self, method: str) -> None:
        page = self.correction_pages.get(method)
        if page is not None:
            self.correction_stack.setCurrentWidget(page)

    def _build_input_group(self) -> QGroupBox:
        box = QGroupBox("Input projection folders")
        layout = QVBoxLayout(box)

        self.folder_list = QListWidget()

        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add folder(s)")
        remove_btn = QPushButton("Remove selected")
        clear_btn = QPushButton("Clear")

        add_btn.clicked.connect(self.add_folders)
        remove_btn.clicked.connect(self.remove_selected_folder)
        clear_btn.clicked.connect(self.folder_list.clear)

        btn_row.addWidget(add_btn)
        btn_row.addWidget(remove_btn)
        btn_row.addWidget(clear_btn)

        pattern_row = QHBoxLayout()
        pattern_row.addWidget(QLabel("Glob pattern:"))
        self.glob_edit = QLineEdit("tomo_*.tif")
        self.recursive_check = QCheckBox("Recursive")
        pattern_row.addWidget(self.glob_edit)
        pattern_row.addWidget(self.recursive_check)

        layout.addLayout(btn_row)
        layout.addLayout(pattern_row)
        layout.addWidget(self.folder_list)
        return box

    def _build_pipeline_group(self) -> QGroupBox:
        box = QGroupBox("Processing pipeline")
        layout = QGridLayout(box)

        self.pipeline_combo = QComboBox()
        self.pipeline_combo.addItem("Ring removal only", "ring_removal_only")
        self.pipeline_combo.addItem("Reconstruction only", "reconstruction_only")
        self.pipeline_combo.addItem("Ring removal + reconstruction", "ring_removal_and_reconstruction")
        self.pipeline_combo.setCurrentIndex(0)
        self.pipeline_combo.currentIndexChanged.connect(self._update_pipeline_state)

        note = QLabel(
            "Reconstruction is executed through an external CERA Python environment. "
            "For reconstruction jobs, select the Python executable from that environment "
            "and a CERA config template file."
        )
        note.setWordWrap(True)

        layout.addWidget(QLabel("Pipeline:"), 0, 0)
        layout.addWidget(self.pipeline_combo, 0, 1)
        layout.addWidget(note, 1, 0, 1, 2)

        return box

    def _build_output_group(self) -> QGroupBox:
        box = QGroupBox("Output")
        layout = QGridLayout(box)

        self.output_mode_combo = QComboBox()
        self.output_mode_combo.addItem("Inside input folder", "inside")
        self.output_mode_combo.addItem("One level above input folder", "up")
        self.output_mode_combo.addItem("One level below / child folder", "down")
        self.output_mode_combo.addItem("Custom folder", "custom")

        self.folder_name_edit = QLineEdit("ring_corrected")
        self.custom_output_edit = QLineEdit()
        self.custom_output_btn = QPushButton("Browse...")
        self.overwrite_check = QCheckBox("Overwrite output files")
        self.keep_temp_check = QCheckBox("Keep temporary sinogram files")

        self.custom_output_btn.clicked.connect(self.pick_custom_output_dir)
        self.output_mode_combo.currentIndexChanged.connect(self._update_output_mode_state)

        layout.addWidget(QLabel("Save mode:"), 0, 0)
        layout.addWidget(self.output_mode_combo, 0, 1, 1, 2)

        layout.addWidget(QLabel("Created folder name:"), 1, 0)
        layout.addWidget(self.folder_name_edit, 1, 1, 1, 2)

        layout.addWidget(QLabel("Custom output:"), 2, 0)
        layout.addWidget(self.custom_output_edit, 2, 1)
        layout.addWidget(self.custom_output_btn, 2, 2)

        layout.addWidget(self.overwrite_check, 3, 0, 1, 2)
        layout.addWidget(self.keep_temp_check, 4, 0, 1, 2)

        self._update_output_mode_state()
        return box

    def _build_algorithm_group(self) -> QGroupBox:
        box = QGroupBox("Ring-removal algorithm")
        layout = QGridLayout(box)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["auto", "intensity", "log"])

        self.correction_combo = QComboBox()
        self.correction_combo.addItems([
            "auto",
            "algotom",
            "repair",
            "filtering",
            "sorting",
            "wavelet_fft",
            "dead",
            "large",
        ])
        self.correction_combo.setCurrentText("algotom")

        # algotom
        self.snr_spin = self._make_float_spin(3.0)
        self.la_size_spin = self._make_int_spin(51)
        self.sm_size_spin = self._make_int_spin(21)
        self.dim_spin = self._make_int_spin(1, 1, 8)

        # repair
        self.repair_thresh_spin = self._make_float_spin(3.0)
        self.repair_max_cols_spin = self._make_int_spin(1000, 1, 1000000)

        # filtering
        self.filt_sigma_spin = self._make_int_spin(3)
        self.filt_size_spin = self._make_int_spin(21)
        self.filt_dim_spin = self._make_int_spin(1, 1, 8)
        self.filt_sort_check = QCheckBox()
        self.filt_sort_check.setChecked(True)

        # sorting
        self.sort_size_spin = self._make_int_spin(21)
        self.sort_dim_spin = self._make_int_spin(1, 1, 8)

        # wavelet_fft
        self.wfft_level_spin = self._make_int_spin(5, 1, 100)
        self.wfft_size_spin = self._make_int_spin(1, 1, 100000)
        self.wfft_wavelet_name_edit = QLineEdit("db9")
        self.wfft_window_name_combo = QComboBox()
        self.wfft_window_name_combo.addItems(["gaussian", "butter"])
        self.wfft_window_name_combo.setCurrentText("gaussian")
        self.wfft_sort_check = QCheckBox()
        self.wfft_sort_check.setChecked(False)

        # dead
        self.dead_snr_spin = self._make_float_spin(3.0)
        self.dead_size_spin = self._make_int_spin(51)
        self.dead_residual_check = QCheckBox()
        self.dead_residual_check.setChecked(True)

        # large
        self.large_snr_spin = self._make_float_spin(3.0)
        self.large_size_spin = self._make_int_spin(51)
        self.large_drop_ratio_spin = self._make_float_spin(0.1, 0.0, 1.0, 3)
        self.large_norm_check = QCheckBox()
        self.large_norm_check.setChecked(True)

        self.workers_spin = QSpinBox()
        self.workers_spin.setRange(0, 128)
        self.workers_spin.setValue(12)
        self.workers_spin.setToolTip("0 = automatic")

        self.correction_stack = QStackedWidget()
        self.correction_pages: dict[str, QWidget] = {}

        self._add_correction_page(
            "auto",
            note="Auto uses algotom for intensity sinograms and repair for log sinograms.",
        )
        self._add_correction_page("algotom", [
            ("SNR:", self.snr_spin),
            ("la_size:", self.la_size_spin),
            ("sm_size:", self.sm_size_spin),
            ("dim:", self.dim_spin),
        ])
        self._add_correction_page("repair", [
            ("repair_thresh:", self.repair_thresh_spin),
            ("repair_max_cols:", self.repair_max_cols_spin),
        ])
        self._add_correction_page("filtering", [
            ("filt_sigma:", self.filt_sigma_spin),
            ("filt_size:", self.filt_size_spin),
            ("filt_dim:", self.filt_dim_spin),
            ("filt_sort:", self.filt_sort_check),
        ])
        self._add_correction_page("sorting", [
            ("sort_size:", self.sort_size_spin),
            ("sort_dim:", self.sort_dim_spin),
        ])
        self._add_correction_page("wavelet_fft", [
            ("wfft_level:", self.wfft_level_spin),
            ("wfft_size:", self.wfft_size_spin),
            ("wfft_wavelet_name:", self.wfft_wavelet_name_edit),
            ("wfft_window_name:", self.wfft_window_name_combo),
            ("wfft_sort:", self.wfft_sort_check),
        ])
        self._add_correction_page("dead", [
            ("dead_snr:", self.dead_snr_spin),
            ("dead_size:", self.dead_size_spin),
            ("dead_residual:", self.dead_residual_check),
        ])
        self._add_correction_page("large", [
            ("large_snr:", self.large_snr_spin),
            ("large_size:", self.large_size_spin),
            ("large_drop_ratio:", self.large_drop_ratio_spin),
            ("large_norm:", self.large_norm_check),
        ])

        self.correction_combo.currentTextChanged.connect(self._update_correction_page)

        layout.addWidget(QLabel("Mode:"), 0, 0)
        layout.addWidget(self.mode_combo, 0, 1)

        layout.addWidget(QLabel("Correction:"), 1, 0)
        layout.addWidget(self.correction_combo, 1, 1)

        layout.addWidget(QLabel("Parameters:"), 2, 0)
        layout.addWidget(self.correction_stack, 2, 1)

        layout.addWidget(QLabel("Workers:"), 3, 0)
        layout.addWidget(self.workers_spin, 3, 1)

        layout.setColumnStretch(1, 1)

        self._update_correction_page(self.correction_combo.currentText())
        return box

    def _build_reconstruction_group(self) -> QGroupBox:
        box = QGroupBox("Reconstruction (CERA)")
        layout = QGridLayout(box)

        self.cera_python_edit = QLineEdit()
        self.cera_python_btn = QPushButton("Browse...")
        self.cera_python_btn.clicked.connect(self.pick_cera_python_exe)

        self.cera_config_edit = QLineEdit()
        self.cera_config_btn = QPushButton("Browse...")
        self.cera_config_btn.clicked.connect(self.pick_cera_config_template)

        self.reconstruction_name_edit = QLineEdit()
        self.reconstruction_name_edit.setPlaceholderText("Leave empty to use input folder name")

        placeholder_note = QLabel(
            "Your CERA config template may contain placeholders:\n"
            "{{PROJECTIONS_DIR}}, {{PROJECTIONS_DIR_POSIX}}, {{OUTPUT_DIR}}, "
            "{{OUTPUT_DIR_POSIX}}, {{OUTPUT_NAME}}, {{INPUT_FOLDER_NAME}}"
        )
        placeholder_note.setWordWrap(True)

        layout.addWidget(QLabel("CERA Python executable:"), 0, 0)
        layout.addWidget(self.cera_python_edit, 0, 1)
        layout.addWidget(self.cera_python_btn, 0, 2)

        layout.addWidget(QLabel("CERA config template:"), 1, 0)
        layout.addWidget(self.cera_config_edit, 1, 1)
        layout.addWidget(self.cera_config_btn, 1, 2)

        layout.addWidget(QLabel("Reconstruction name:"), 2, 0)
        layout.addWidget(self.reconstruction_name_edit, 2, 1, 1, 2)

        layout.addWidget(placeholder_note, 3, 0, 1, 3)
        layout.setColumnStretch(1, 1)

        return box

    def _build_run_group(self) -> QGroupBox:
        box = QGroupBox("Run")
        layout = QHBoxLayout(box)

        self.run_btn = QPushButton("Run selected jobs")
        self.run_btn.clicked.connect(self.run_jobs)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(1)
        self.progress_bar.setValue(0)

        layout.addWidget(self.run_btn)
        layout.addWidget(self.progress_bar)
        return box

    def _build_log_group(self) -> QGroupBox:
        box = QGroupBox("Log")
        layout = QVBoxLayout(box)

        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)

        layout.addWidget(self.log_edit)
        return box

    def add_folders(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select projection folder")
        if not folder:
            return

        existing = {self.folder_list.item(i).text() for i in range(self.folder_list.count())}
        if folder not in existing:
            self.folder_list.addItem(folder)

    def remove_selected_folder(self) -> None:
        row = self.folder_list.currentRow()
        if row >= 0:
            self.folder_list.takeItem(row)

    def pick_custom_output_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select custom output folder")
        if folder:
            self.custom_output_edit.setText(folder)

    def pick_cera_python_exe(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select CERA Python executable",
            str(Path.home()),
            "Executables (*.exe);;All files (*)",
        )
        if path:
            self.cera_python_edit.setText(path)

    def pick_cera_config_template(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select CERA config template",
            str(Path.home()),
            "Config files (*.config *.cfg *.txt);;All files (*)",
        )
        if path:
            self.cera_config_edit.setText(path)

    def _update_output_mode_state(self, *_args) -> None:
        mode = self.output_mode_combo.currentData()
        is_custom = mode == "custom"
        self.custom_output_edit.setEnabled(is_custom)
        self.custom_output_btn.setEnabled(is_custom)

    def _update_pipeline_state(self, *_args) -> None:
        mode = self.pipeline_combo.currentData()
        run_ring = mode in ("ring_removal_only", "ring_removal_and_reconstruction")
        run_recon = mode in ("reconstruction_only", "ring_removal_and_reconstruction")

        if hasattr(self, "algorithm_group"):
            self.algorithm_group.setEnabled(run_ring)
        if hasattr(self, "reconstruction_group"):
            self.reconstruction_group.setEnabled(run_recon)
        if hasattr(self, "output_group"):
            self.output_group.setEnabled(mode != "reconstruction_only")

    def append_log(self, text: str) -> None:
        self.log_edit.appendPlainText(text)

    def update_progress(self, done: int, total: int) -> None:
        self.progress_bar.setMaximum(max(1, total))
        self.progress_bar.setValue(done)

    def build_params(self) -> Params:
        return Params(
            mode=self.mode_combo.currentText(),
            correction=self.correction_combo.currentText(),
            snr=self.snr_spin.value(),
            la_size=self.la_size_spin.value(),
            sm_size=self.sm_size_spin.value(),
            dim=self.dim_spin.value(),
            repair_thresh=self.repair_thresh_spin.value(),
            repair_max_cols=self.repair_max_cols_spin.value(),
            filt_sigma=self.filt_sigma_spin.value(),
            filt_size=self.filt_size_spin.value(),
            filt_dim=self.filt_dim_spin.value(),
            filt_sort=self.filt_sort_check.isChecked(),
            sort_size=self.sort_size_spin.value(),
            sort_dim=self.sort_dim_spin.value(),
            wfft_level=self.wfft_level_spin.value(),
            wfft_size=self.wfft_size_spin.value(),
            wfft_wavelet_name=self.wfft_wavelet_name_edit.text().strip() or "db9",
            wfft_window_name=self.wfft_window_name_combo.currentText(),
            wfft_sort=self.wfft_sort_check.isChecked(),
            dead_snr=self.dead_snr_spin.value(),
            dead_size=self.dead_size_spin.value(),
            dead_residual=self.dead_residual_check.isChecked(),
            large_snr=self.large_snr_spin.value(),
            large_size=self.large_size_spin.value(),
            large_drop_ratio=self.large_drop_ratio_spin.value(),
            large_norm=self.large_norm_check.isChecked(),
        )

    def build_jobs(self) -> list[ProjectionJob]:
        jobs: list[ProjectionJob] = []

        pipeline_mode = self.pipeline_combo.currentData()
        cera_python = self.cera_python_edit.text().strip() or None
        cera_config = self.cera_config_edit.text().strip() or None
        reconstruction_name = self.reconstruction_name_edit.text().strip() or None

        for i in range(self.folder_list.count()):
            jobs.append(
                ProjectionJob(
                    input_dir=self.folder_list.item(i).text(),
                    output_mode=self.output_mode_combo.currentData(),
                    folder_name=self.folder_name_edit.text().strip() or "ring_corrected",
                    custom_output_dir=self.custom_output_edit.text().strip() or None,
                    glob_pattern=self.glob_edit.text().strip() or "tomo_*.tif",
                    recursive=self.recursive_check.isChecked(),
                    overwrite=self.overwrite_check.isChecked(),
                    keep_temp=self.keep_temp_check.isChecked(),
                    workers=self.workers_spin.value(),
                    pipeline_mode=pipeline_mode,
                    cera_python_exe=cera_python,
                    cera_config_template=cera_config,
                    reconstruction_name=reconstruction_name,
                )
            )
        return jobs

    def _validate_before_run(self) -> bool:
        pipeline_mode = self.pipeline_combo.currentData()
        if pipeline_mode in ("reconstruction_only", "ring_removal_and_reconstruction"):
            cera_python = self.cera_python_edit.text().strip()
            cera_config = self.cera_config_edit.text().strip()

            if not cera_python:
                QMessageBox.warning(self, "Missing CERA Python", "Please select the Python executable from your CERA environment.")
                return False
            if not Path(cera_python).exists():
                QMessageBox.warning(self, "Invalid CERA Python", f"File not found:\n{cera_python}")
                return False

            if not cera_config:
                QMessageBox.warning(self, "Missing CERA config", "Please select a CERA config template file.")
                return False
            if not Path(cera_config).exists():
                QMessageBox.warning(self, "Invalid CERA config", f"File not found:\n{cera_config}")
                return False

        return True

    def run_jobs(self) -> None:
        jobs = self.build_jobs()
        if not jobs:
            QMessageBox.warning(self, "No input", "Please add at least one projection folder.")
            return

        if not self._validate_before_run():
            return

        self.run_btn.setEnabled(False)
        self.progress_bar.setMaximum(1)
        self.progress_bar.setValue(0)
        self.log_edit.clear()
        self.pending_jobs = len(jobs)

        params = self.build_params()

        for job in jobs:
            self.append_log(f"Queued: {job.input_dir} [{job.pipeline_mode}]")
            worker = ProjectionJobWorker(job=job, params=params)
            worker.signals.log.connect(self.append_log)
            worker.signals.progress.connect(self.update_progress)
            worker.signals.finished.connect(self.on_job_finished)
            worker.signals.error.connect(self.on_job_error)
            self.thread_pool.start(worker)

    def on_job_finished(self, result: dict) -> None:
        out_dir = result.get("output_dir", "")
        log_path = result.get("log_path", "")
        summary_path = result.get("summary_path", "")
        recon_meta = result.get("reconstruction")

        self.append_log(f"Finished successfully: {out_dir}")
        if recon_meta:
            self.append_log(f"Reconstruction output: {recon_meta.get('output_dir', '')}")
            self.append_log(f"Rendered CERA config: {recon_meta.get('rendered_config_path', '')}")
        if log_path:
            self.append_log(f"Saved text log: {log_path}")
        if summary_path:
            self.append_log(f"Saved JSON summary: {summary_path}")

        self._job_done()

    def on_job_error(self, error_text: str) -> None:
        self.append_log("ERROR:")
        self.append_log(error_text)
        self._job_done()

    def _job_done(self) -> None:
        self.pending_jobs -= 1
        if self.pending_jobs <= 0:
            self.run_btn.setEnabled(True)
            QMessageBox.information(self, "Done", "All jobs finished.")
