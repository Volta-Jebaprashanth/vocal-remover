import os

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class _RowWidget(QWidget):
    remove_clicked = pyqtSignal(str)

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self.path = path

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 6, 4)
        layout.setSpacing(8)

        icon = QLabel("🎧")
        name = QLabel(os.path.basename(path))
        name.setObjectName("queueItemName")
        name.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        remove_btn = QPushButton("✕")
        remove_btn.setObjectName("queueRemoveButton")
        remove_btn.setFixedSize(22, 22)
        remove_btn.setCursor(Qt.PointingHandCursor)
        remove_btn.clicked.connect(lambda: self.remove_clicked.emit(self.path))

        layout.addWidget(icon)
        layout.addWidget(name)
        layout.addWidget(remove_btn)


class FileQueue(QWidget):
    """Shows the queued songs to process, with per-row removal and a clear-all action."""

    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._paths: list[str] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header = QHBoxLayout()
        self.count_label = QLabel("No songs added yet")
        self.count_label.setObjectName("sectionLabel")
        self.clear_button = QPushButton("Clear all")
        self.clear_button.setObjectName("linkButton")
        self.clear_button.setCursor(Qt.PointingHandCursor)
        self.clear_button.clicked.connect(self.clear)
        self.clear_button.setVisible(False)
        header.addWidget(self.count_label)
        header.addStretch()
        header.addWidget(self.clear_button)
        layout.addLayout(header)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("fileQueueList")
        self.list_widget.setVisible(False)
        self.list_widget.setMaximumHeight(140)
        self.list_widget.setFocusPolicy(Qt.NoFocus)
        layout.addWidget(self.list_widget)

    def add_paths(self, paths: list) -> None:
        added = False
        for path in paths:
            if path not in self._paths:
                self._paths.append(path)
                self._add_row(path)
                added = True
        if added:
            self._refresh_header()
            self.changed.emit()

    def _add_row(self, path: str) -> None:
        item = QListWidgetItem(self.list_widget)
        item.setSizeHint(_RowWidget(path).sizeHint())
        row = _RowWidget(path)
        row.remove_clicked.connect(self._remove_path)
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, row)

    def remove_paths(self, paths) -> None:
        for path in paths:
            self._remove_path(path)

    def _remove_path(self, path: str) -> None:
        if path in self._paths:
            self._paths.remove(path)
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            widget = self.list_widget.itemWidget(item)
            if widget is not None and widget.path == path:
                self.list_widget.takeItem(i)
                break
        self._refresh_header()
        self.changed.emit()

    def clear(self) -> None:
        self._paths = []
        self.list_widget.clear()
        self._refresh_header()
        self.changed.emit()

    def _refresh_header(self) -> None:
        count = len(self._paths)
        has_items = count > 0
        self.list_widget.setVisible(has_items)
        self.clear_button.setVisible(has_items)
        if count == 0:
            self.count_label.setText("No songs added yet")
        elif count == 1:
            self.count_label.setText("1 song added")
        else:
            self.count_label.setText(f"{count} songs added")

    def paths(self) -> list:
        return list(self._paths)
