import os

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QFrame, QLabel, QVBoxLayout

AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".wma"}


class DropZone(QFrame):
    """Drag-and-drop target for one or more audio files. Also clickable to browse.
    Stateless about *which* files are queued -- that lives in FileQueue; this widget
    only ever announces newly added paths."""

    files_selected = pyqtSignal(list)
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(150)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        self.icon_label = QLabel("🎵")
        self.icon_label.setObjectName("dropIcon")
        self.icon_label.setAlignment(Qt.AlignCenter)

        self.title_label = QLabel("Drag & drop songs here")
        self.title_label.setObjectName("dropTitle")
        self.title_label.setAlignment(Qt.AlignCenter)

        self.subtitle_label = QLabel("or click to browse (MP3, WAV, FLAC, M4A, AAC, OGG)")
        self.subtitle_label.setObjectName("dropSubtitle")
        self.subtitle_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.icon_label)
        layout.addWidget(self.title_label)
        layout.addWidget(self.subtitle_label)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def _extract_valid_paths(self, mime_data) -> list:
        if not mime_data.hasUrls():
            return []
        paths = []
        for url in mime_data.urls():
            if url.isLocalFile():
                path = url.toLocalFile()
                _, ext = os.path.splitext(path)
                if ext.lower() in AUDIO_EXTENSIONS:
                    paths.append(path)
        return paths

    def dragEnterEvent(self, event):
        if self._extract_valid_paths(event.mimeData()):
            self.setProperty("dragActive", True)
            self.style().unpolish(self)
            self.style().polish(self)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.setProperty("dragActive", False)
        self.style().unpolish(self)
        self.style().polish(self)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self.setProperty("dragActive", False)
        self.style().unpolish(self)
        self.style().polish(self)
        paths = self._extract_valid_paths(event.mimeData())
        if paths:
            self.files_selected.emit(paths)
            event.acceptProposedAction()
        else:
            event.ignore()
