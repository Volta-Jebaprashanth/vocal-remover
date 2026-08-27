import os
import shutil
import tempfile

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices, QIcon, QPixmap
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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from common import resource_path
from core.separation_controller import SeparationController
from core.youtube_controller import YouTubeController
from ui.advanced_panel import AdvancedPanel
from ui.drop_zone import AUDIO_EXTENSIONS, DropZone
from ui.file_queue import FileQueue
from ui.styles import STYLESHEET
from ui.youtube_downloader_tab import YouTubeDownloaderTab
from ui.youtube_input_row import YouTubeInputRow

# Header logo height. The old "Vocal Remover" QLabel#headerTitle text was 22px font,
# but that reads too small as an image -- sized up for visual presence in the header.
HEADER_LOGO_HEIGHT = 112

AUDIO_FILE_FILTER = "Audio files (*.mp3 *.wav *.flac *.m4a *.aac *.ogg *.wma)"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = None
        self.youtube_controller = None
        self._yt_temp_dirs = set()
        self._yt_temp_paths = set()

        self.setWindowTitle("Vocal Remover — Background Track Extractor")
        self.setWindowIcon(QIcon(resource_path("assets", "icon.ico")))
        self.setMinimumSize(600, 640)
        self.resize(600, 760)
        self.setStyleSheet(STYLESHEET)

        self._build_ui()

    def _build_ui(self) -> None:
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self.tabs.addTab(self._build_vocal_remover_tab(), "Vocal Remover")
        self.tabs.addTab(YouTubeDownloaderTab(), "YouTube Downloader")
        self._relayout_tabs()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._relayout_tabs()

    def _relayout_tabs(self) -> None:
        # Styling QTabBar::tab (see styles.py) makes Qt fall back to content-sized
        # tabs instead of its normal auto-stretch-to-fill behavior -- on a narrow
        # window that leaves the tab bar overflowing, which shows scroll arrows and
        # hides part of the second tab instead of showing it. Forcing each tab to
        # exactly half the bar's width on every resize keeps both fully visible and
        # evenly split regardless of window size.
        bar = self.tabs.tabBar()
        bar.setUsesScrollButtons(False)
        count = max(self.tabs.count(), 1)
        # QSS "width" sets the *content* box -- styles.py's QTabBar::tab padding
        # (18px) and border (1px) are added on top of it, per side. Not
        # subtracting them here would make the two rendered tabs a few pixels
        # wider than the bar itself, which is what was triggering the overflow
        # arrows and an auto-scroll-to-selected-tab jump on every switch.
        horizontal_chrome = 2 * (18 + 1)
        content_width = max(self.tabs.width() // count - horizontal_chrome, 1)
        bar.setStyleSheet(f"QTabBar::tab {{ width: {content_width}px; }}")

    def _build_vocal_remover_tab(self) -> QWidget:
        tab = QWidget()
        outer = QVBoxLayout(tab)
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

        logo = QLabel()
        logo_pixmap = QPixmap(resource_path("assets", "logo-light.png"))
        logo.setPixmap(
            logo_pixmap.scaledToHeight(HEADER_LOGO_HEIGHT, Qt.SmoothTransformation)
        )
        subtitle = QLabel("Strip the vocals out of any song and keep the instrumental.")
        subtitle.setObjectName("headerSubtitle")
        root.addWidget(logo)
        root.addWidget(subtitle)

        self.drop_zone = DropZone()
        self.drop_zone.files_selected.connect(self._on_files_added)
        self.drop_zone.clicked.connect(self._browse_input_files)
        root.addWidget(self.drop_zone)

        self.youtube_input_row = YouTubeInputRow()
        self.youtube_input_row.download_requested.connect(self._on_youtube_link_added)
        root.addWidget(self.youtube_input_row)

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

        status_row = QHBoxLayout()
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        # Only ever shown while a YouTube add (not a separation run, which isn't
        # cancelable) is in flight -- see _on_youtube_link_added / set_busy below.
        self.youtube_stop_button = QPushButton("✕")
        self.youtube_stop_button.setObjectName("stopButton")
        self.youtube_stop_button.setFixedSize(22, 22)
        self.youtube_stop_button.setCursor(Qt.PointingHandCursor)
        self.youtube_stop_button.setVisible(False)
        self.youtube_stop_button.clicked.connect(self._stop_youtube_download)
        status_row.addWidget(self.status_label, 1)
        status_row.addWidget(self.youtube_stop_button)
        root.addLayout(status_row)

        self.results_layout = QVBoxLayout()
        self.results_layout.setSpacing(6)
        root.addLayout(self.results_layout)

        self.open_folder_button = QPushButton("Open Output Folder")
        self.open_folder_button.setVisible(False)
        self.open_folder_button.clicked.connect(self._open_output_folder)
        root.addWidget(self.open_folder_button)

        root.addStretch()

        return tab

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

    def _on_youtube_link_added(self, url: str, is_playlist: bool) -> None:
        self.youtube_input_row.set_busy(True)
        self.youtube_stop_button.setVisible(True)
        self._set_status("Preparing YouTube downloader...", state="downloading")

        temp_dir = tempfile.mkdtemp(prefix="vocal_remover_yt_")
        self._yt_temp_dirs.add(temp_dir)

        self.youtube_controller = YouTubeController(self)
        self.youtube_controller.status_changed.connect(
            lambda msg: self._set_status(msg, state="downloading")
        )
        self.youtube_controller.item_started.connect(self._on_youtube_item_started)
        self.youtube_controller.item_done.connect(self._on_youtube_item_done)
        self.youtube_controller.item_failed.connect(self._on_youtube_item_failed)
        self.youtube_controller.all_done.connect(self._on_youtube_batch_done)
        self.youtube_controller.fatal_error.connect(self._on_youtube_fatal_error)
        self.youtube_controller.cancelled.connect(self._on_youtube_cancelled)
        # Audio-only, wav: the safest container/codec pairing for spleeter/ffmpeg to
        # read back in (see CLAUDE.md "Bundled dependencies" -- wav is confirmed
        # working), and downloaded straight into a scratch temp dir since this file
        # only needs to survive long enough to be fed into separation.
        self.youtube_controller.start(
            url, is_playlist, temp_dir, ["-f", "bestaudio/best", "-x", "--audio-format", "wav"]
        )

    def _stop_youtube_download(self) -> None:
        if self.youtube_controller:
            self.youtube_controller.stop()

    def _on_youtube_cancelled(self) -> None:
        self.youtube_input_row.set_busy(False)
        self.youtube_stop_button.setVisible(False)
        self._set_status("Cancelled.")

    def _on_youtube_item_started(self, title: str, index: int, total: int) -> None:
        message = f"Downloading {title}..." if total == 1 else f"Downloading video {index} of {total}: {title}..."
        self._set_status(message, state="downloading")

    def _on_youtube_item_done(self, _title: str, path: str) -> None:
        self.file_queue.add_paths([path])
        self._yt_temp_paths.add(path)
        self._clear_results()
        self.open_folder_button.setVisible(False)

    def _on_youtube_item_failed(self, title: str, error: str) -> None:
        self._add_result_row(False, title, error)

    def _on_youtube_batch_done(self) -> None:
        self.youtube_input_row.set_busy(False)
        self.youtube_stop_button.setVisible(False)
        self._set_status("Added from YouTube.", state="success")

    def _on_youtube_fatal_error(self, message: str) -> None:
        self.youtube_input_row.set_busy(False)
        self.youtube_stop_button.setVisible(False)
        self._set_status(f"YouTube download failed: {message}", state="error")

    def _cleanup_yt_temp_dirs(self) -> None:
        for temp_dir in self._yt_temp_dirs:
            shutil.rmtree(temp_dir, ignore_errors=True)
        self._yt_temp_dirs.clear()
        # Their backing files are gone now -- leaving these in the queue would let a
        # second "Remove Vocals" click silently try to re-read deleted files (this
        # is exactly what produced the "No such file or directory" ffprobe error).
        self.file_queue.remove_paths(self._yt_temp_paths)
        self._yt_temp_paths.clear()

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
        self._cleanup_yt_temp_dirs()

    def _on_fatal_error(self, message: str) -> None:
        self.progress_bar.setVisible(False)
        self.drop_zone.setEnabled(True)
        self.run_button.setEnabled(True)
        self._set_status(f"Something went wrong: {message}", state="error")
        self._cleanup_yt_temp_dirs()

    def _open_output_folder(self) -> None:
        folder = self.output_edit.text().strip()
        if folder and os.path.isdir(folder):
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
