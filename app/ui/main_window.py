import os

from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.separation_controller import SeparationController
from ui.advanced_panel import AdvancedPanel
from ui.drop_zone import AUDIO_EXTENSIONS, DropZone
from ui.file_queue import FileQueue
from ui.styles import STYLESHEET

AUDIO_FILE_FILTER = "Audio files (*.mp3 *.wav *.flac *.m4a *.aac *.ogg *.wma)"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = None

        self.setWindowTitle("Vocal Remover — Background Track Extractor")
        self.setMinimumSize(600, 640)
        self.resize(600, 760)
        self.setStyleSheet(STYLESHEET)

        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)

        root = QVBoxLayout(content)
        root.setContentsMargins(28, 28, 28, 28)
        root.setSpacing(16)

        title = QLabel("Vocal Remover")
        title.setObjectName("headerTitle")
        subtitle = QLabel("Strip the vocals out of any song and keep the instrumental.")
        subtitle.setObjectName("headerSubtitle")
        root.addWidget(title)
        root.addWidget(subtitle)

        self.drop_zone = DropZone()
        self.drop_zone.files_selected.connect(self._on_files_added)
        self.drop_zone.clicked.connect(self._browse_input_files)
        root.addWidget(self.drop_zone)

        self.file_queue = FileQueue()
        self.file_queue.changed.connect(self._update_run_button_state)
        root.addWidget(self.file_queue)

        self.advanced_panel = AdvancedPanel()
        root.addWidget(self.advanced_panel)

        output_label = QLabel("OUTPUT FOLDER")
        output_label.setObjectName("sectionLabel")
        root.addWidget(output_label)

        output_row = QHBoxLayout()
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Choose where to save the results...")
        self.output_edit.setReadOnly(True)
        browse_output_btn = QPushButton("Browse")
        browse_output_btn.clicked.connect(self._browse_output_dir)
        output_row.addWidget(self.output_edit)
        output_row.addWidget(browse_output_btn)
        root.addLayout(output_row)

        default_output = os.path.join(os.path.expanduser("~"), "Music", "Vocal Remover Output")
        self.output_edit.setText(default_output)

        self.run_button = QPushButton("Remove Vocals")
        self.run_button.setObjectName("runButton")
        self.run_button.setEnabled(False)
        self.run_button.clicked.connect(self._run_separation)
        root.addWidget(self.run_button)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        root.addWidget(self.progress_bar)

        self.batch_label = QLabel("")
        self.batch_label.setObjectName("statusLabel")
        self.batch_label.setVisible(False)
        root.addWidget(self.batch_label)

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self.results_layout = QVBoxLayout()
        self.results_layout.setSpacing(6)
        root.addLayout(self.results_layout)

        self.open_folder_button = QPushButton("Open Output Folder")
        self.open_folder_button.setVisible(False)
        self.open_folder_button.clicked.connect(self._open_output_folder)
        root.addWidget(self.open_folder_button)

        root.addStretch()

    # -- input handling -----------------------------------------------------

    def _browse_input_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Select song(s)", "", AUDIO_FILE_FILTER)
        if paths:
            self._on_files_added(paths)

    def _on_files_added(self, paths: list) -> None:
        valid = [p for p in paths if os.path.splitext(p)[1].lower() in AUDIO_EXTENSIONS]
        if valid:
            self.file_queue.add_paths(valid)
            self._clear_results()
            self._set_status("")
            self.open_folder_button.setVisible(False)

    def _browse_output_dir(self) -> None:
        start_dir = self.output_edit.text() or os.path.expanduser("~")
        directory = QFileDialog.getExistingDirectory(self, "Select output folder", start_dir)
        if directory:
            self.output_edit.setText(directory)
            self._update_run_button_state()

    def _update_run_button_state(self) -> None:
        has_input = len(self.file_queue.paths()) > 0
        has_output = bool(self.output_edit.text().strip())
        self.run_button.setEnabled(has_input and has_output)
        count = len(self.file_queue.paths())
        if count > 1:
            self.run_button.setText(f"Process {count} Songs")
        else:
            self.run_button.setText("Remove Vocals")

    def _set_status(self, message: str, state: str = "normal") -> None:
        self.status_label.setText(message)
        self.status_label.setProperty("state", state)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _clear_results(self) -> None:
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _add_result_row(self, ok: bool, filename: str, detail: str) -> None:
        row = QFrame()
        row.setObjectName("resultRow")
        layout = QVBoxLayout(row)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        title = QLabel(("✅ " if ok else "❌ ") + filename)
        title.setObjectName("resultOk" if ok else "resultError")
        layout.addWidget(title)

        if detail:
            detail_label = QLabel(detail)
            detail_label.setObjectName("resultDetail")
            detail_label.setWordWrap(True)
            layout.addWidget(detail_label)

        self.results_layout.addWidget(row)

    # -- running --------------------------------------------------------

    def _run_separation(self) -> None:
        input_paths = self.file_queue.paths()
        if not input_paths:
            return

        output_dir = self.output_edit.text().strip()
        settings = self.advanced_panel.get_settings()

        self.run_button.setEnabled(False)
        self.drop_zone.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.open_folder_button.setVisible(False)
        self._clear_results()
        self._set_status("Starting up...")

        self.batch_label.setVisible(len(input_paths) > 1)
        self.batch_label.setText("")

        job = {
            "input_paths": input_paths,
            "output_dir": output_dir,
            **settings,
        }

        self.controller = SeparationController(self)
        self.controller.status_changed.connect(
            lambda msg, downloading: self._set_status(msg, state="downloading" if downloading else "normal")
        )
        self.controller.file_started.connect(self._on_file_started)
        self.controller.file_done.connect(self._on_file_done)
        self.controller.file_failed.connect(self._on_file_failed)
        self.controller.all_done.connect(self._on_all_done)
        self.controller.fatal_error.connect(self._on_fatal_error)
        self.controller.start(job)

    def _on_file_started(self, filename: str, index: int, total: int) -> None:
        if total > 1:
            self.batch_label.setText(f"Song {index} of {total}: {filename}")

    def _on_file_done(self, filename: str, outputs: list) -> None:
        if len(outputs) == 1:
            detail = outputs[0]
        else:
            detail = f"{len(outputs)} tracks saved"
        self._add_result_row(True, filename, detail)

    def _on_file_failed(self, filename: str, error: str) -> None:
        self._add_result_row(False, filename, error)

    def _on_all_done(self) -> None:
        self.progress_bar.setVisible(False)
        self.drop_zone.setEnabled(True)
        self.run_button.setEnabled(True)
        self._set_status("Done!", state="success")
        self.open_folder_button.setVisible(True)

    def _on_fatal_error(self, message: str) -> None:
        self.progress_bar.setVisible(False)
        self.drop_zone.setEnabled(True)
        self.run_button.setEnabled(True)
        self._set_status(f"Something went wrong: {message}", state="error")

    def _open_output_folder(self) -> None:
        folder = self.output_edit.text().strip()
        if folder and os.path.isdir(folder):
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
