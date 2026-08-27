from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QCheckBox, QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout, QWidget


class YouTubeInputRow(QWidget):
    """Paste a YouTube video or playlist link here to pull its audio straight into
    the processing queue, alongside (or instead of) dropped local files."""

    download_requested = pyqtSignal(str, bool)  # url, is_playlist

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        row = QHBoxLayout()
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("...or paste a YouTube video or playlist link")
        self.url_edit.returnPressed.connect(self._emit)
        self.add_button = QPushButton("Add")
        self.add_button.clicked.connect(self._emit)
        row.addWidget(self.url_edit, 1)
        row.addWidget(self.add_button)
        layout.addLayout(row)

        self.playlist_checkbox = QCheckBox("This is a playlist — add every video")
        layout.addWidget(self.playlist_checkbox)

    def _emit(self) -> None:
        url = self.url_edit.text().strip()
        if not url:
            return
        self.download_requested.emit(url, self.playlist_checkbox.isChecked())
        self.url_edit.clear()

    def set_busy(self, busy: bool) -> None:
        self.add_button.setEnabled(not busy)
        self.url_edit.setEnabled(not busy)
