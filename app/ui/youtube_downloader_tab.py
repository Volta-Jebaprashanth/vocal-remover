import os

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from core.youtube_controller import YouTubeController

AUDIO_FORMATS = ["mp3", "wav", "flac", "m4a"]

# (label, max height or None for uncapped) -- exact resolutions a video actually
# offers vary per video, so rather than probing formats up front (a network round
# trip before the user can even hit Download), these map to yt-dlp's own
# height-capped selector syntax and it picks whatever's actually available at or
# below the cap. "High" intentionally has no cap, matching the previous behavior.
VIDEO_QUALITIES = [
    ("High (best available, slower)", None),
    ("Medium (720p)", 720),
    ("Low (480p)", 480),
]


class YouTubeDownloaderTab(QWidget):
    """Plain YouTube downloader -- no separation involved, just saves the video or
    its audio to a folder the user picks. A separate flow from the "paste a link to
    process" row on the main tab, for people who just want the file itself."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.controller = None
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 28, 28, 28)
        root.setSpacing(16)

        subtitle = QLabel("Download any YouTube video or playlist as a video or audio file.")
        subtitle.setObjectName("headerSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        url_label = QLabel("YOUTUBE LINK")
        url_label.setObjectName("sectionLabel")
        root.addWidget(url_label)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("Paste a YouTube video or playlist link...")
        root.addWidget(self.url_edit)

        self.playlist_checkbox = QCheckBox("This is a playlist — download every video")
        root.addWidget(self.playlist_checkbox)

        type_row = QHBoxLayout()
        type_label = QLabel("Download as")
        type_label.setObjectName("fieldLabel")
        type_label.setFixedWidth(120)
        self.video_radio = QRadioButton("Video")
        self.audio_radio = QRadioButton("Audio only")
        self.audio_radio.setChecked(True)
        self.video_radio.toggled.connect(self._on_type_changed)
        type_row.addWidget(type_label)
        type_row.addWidget(self.video_radio)
        type_row.addWidget(self.audio_radio)
        type_row.addStretch()
        root.addLayout(type_row)

        self.format_row_widget = QWidget()
        format_row = QHBoxLayout(self.format_row_widget)
        format_row.setContentsMargins(0, 0, 0, 0)
        format_label = QLabel("Audio format")
        format_label.setObjectName("fieldLabel")
        format_label.setFixedWidth(120)
        self.format_combo = QComboBox()
        for fmt in AUDIO_FORMATS:
            self.format_combo.addItem(fmt.upper(), fmt)
        format_row.addWidget(format_label)
        format_row.addWidget(self.format_combo, 1)
        root.addWidget(self.format_row_widget)

        self.quality_row_widget = QWidget()
        quality_row = QHBoxLayout(self.quality_row_widget)
        quality_row.setContentsMargins(0, 0, 0, 0)
        quality_label = QLabel("Video quality")
        quality_label.setObjectName("fieldLabel")
        quality_label.setFixedWidth(120)
        self.quality_combo = QComboBox()
        for label, _max_height in VIDEO_QUALITIES:
            self.quality_combo.addItem(label)
        quality_row.addWidget(quality_label)
        quality_row.addWidget(self.quality_combo, 1)
        root.addWidget(self.quality_row_widget)
        self.quality_row_widget.setVisible(False)

        output_label = QLabel("SAVE TO")
        output_label.setObjectName("sectionLabel")
        root.addWidget(output_label)

        output_row = QHBoxLayout()
        self.output_edit = QLineEdit()
        self.output_edit.setReadOnly(True)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse_output_dir)
        output_row.addWidget(self.output_edit)
        output_row.addWidget(browse_btn)
        root.addLayout(output_row)

        default_output = os.path.join(os.path.expanduser("~"), "Downloads", "YouTube Downloads")
        self.output_edit.setText(default_output)

        self.download_button = QPushButton("Download")
        self.download_button.setObjectName("runButton")
        self.download_button.clicked.connect(self._start_download)
        root.addWidget(self.download_button)

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
        self.stop_button = QPushButton("✕")
        self.stop_button.setObjectName("stopButton")
        self.stop_button.setFixedSize(22, 22)
        self.stop_button.setCursor(Qt.PointingHandCursor)
        self.stop_button.setVisible(False)
        self.stop_button.clicked.connect(self._stop_download)
        status_row.addWidget(self.status_label, 1)
        status_row.addWidget(self.stop_button)
        root.addLayout(status_row)

        self.results_layout = QVBoxLayout()
        self.results_layout.setSpacing(6)
        root.addLayout(self.results_layout)

        self.open_folder_button = QPushButton("Open Download Folder")
        self.open_folder_button.setVisible(False)
        self.open_folder_button.clicked.connect(self._open_output_folder)
        root.addWidget(self.open_folder_button)

        root.addStretch()

    def _on_type_changed(self, _checked: bool) -> None:
        is_audio = self.audio_radio.isChecked()
        self.format_row_widget.setVisible(is_audio)
        self.quality_row_widget.setVisible(not is_audio)

    def _browse_output_dir(self) -> None:
        start_dir = self.output_edit.text() or os.path.expanduser("~")
        directory = QFileDialog.getExistingDirectory(self, "Select download folder", start_dir)
        if directory:
            self.output_edit.setText(directory)

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

    def _add_result_row(self, ok: bool, title: str, detail: str) -> None:
        row = QFrame()
        row.setObjectName("resultRow")
        layout = QVBoxLayout(row)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        title_label = QLabel(("✅ " if ok else "❌ ") + title)
        title_label.setObjectName("resultOk" if ok else "resultError")
        layout.addWidget(title_label)

        if detail:
            detail_label = QLabel(detail)
            detail_label.setObjectName("resultDetail")
            detail_label.setWordWrap(True)
            layout.addWidget(detail_label)

        self.results_layout.addWidget(row)

    def _start_download(self) -> None:
        url = self.url_edit.text().strip()
        output_dir = self.output_edit.text().strip()
        if not url or not output_dir:
            return

        if self.video_radio.isChecked():
            _label, max_height = VIDEO_QUALITIES[self.quality_combo.currentIndex()]
            if max_height is None:
                video_format = "bv*+ba/b"
            else:
                video_format = f"bv*[height<={max_height}]+ba/b[height<={max_height}]"
            extra_args = ["-f", video_format, "--merge-output-format", "mp4"]
        else:
            fmt = self.format_combo.currentData()
            extra_args = ["-f", "bestaudio/best", "-x", "--audio-format", fmt]

        self.download_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.stop_button.setVisible(True)
        self.open_folder_button.setVisible(False)
        self._clear_results()
        self._set_status("Starting up...")
        self.batch_label.setText("")

        self.controller = YouTubeController(self)
        self.controller.status_changed.connect(lambda msg: self._set_status(msg, state="downloading"))
        self.controller.item_started.connect(self._on_item_started)
        self.controller.item_done.connect(self._on_item_done)
        self.controller.item_failed.connect(self._on_item_failed)
        self.controller.all_done.connect(self._on_all_done)
        self.controller.fatal_error.connect(self._on_fatal_error)
        self.controller.cancelled.connect(self._on_cancelled)
        self.controller.start(url, self.playlist_checkbox.isChecked(), output_dir, extra_args)

    def _stop_download(self) -> None:
        if self.controller:
            self.controller.stop()

    def _on_cancelled(self) -> None:
        self.progress_bar.setVisible(False)
        self.stop_button.setVisible(False)
        self.download_button.setEnabled(True)
        self._set_status("Cancelled.")

    def _on_item_started(self, title: str, index: int, total: int) -> None:
        if total > 1:
            self.batch_label.setVisible(True)
            self.batch_label.setText(f"Video {index} of {total}: {title}")

    def _on_item_done(self, title: str, filepath: str) -> None:
        self._add_result_row(True, title, os.path.basename(filepath))

    def _on_item_failed(self, title: str, error: str) -> None:
        self._add_result_row(False, title, error)

    def _on_all_done(self) -> None:
        self.progress_bar.setVisible(False)
        self.stop_button.setVisible(False)
        self.download_button.setEnabled(True)
        self._set_status("Done!", state="success")
        self.open_folder_button.setVisible(True)

    def _on_fatal_error(self, message: str) -> None:
        self.progress_bar.setVisible(False)
        self.stop_button.setVisible(False)
        self.download_button.setEnabled(True)
        self._set_status(f"Something went wrong: {message}", state="error")

    def _open_output_folder(self) -> None:
        folder = self.output_edit.text().strip()
        if folder and os.path.isdir(folder):
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
