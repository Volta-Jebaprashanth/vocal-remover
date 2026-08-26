from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from common import FRIENDLY_STEM_NAMES, MP3_BITRATES, OUTPUT_FORMATS, STEM_ICONS, STEM_MODE_LABELS, STEM_NAMES

# (label, fast, mwf)
QUALITY_PRESETS = [
    ("⚡ Fast preview (lower quality)", True, False),
    ("⚖ Standard (recommended)", False, False),
    ("✨ Best quality (slower)", False, True),
]


class AdvancedPanel(QWidget):
    """Collapsed by default so a casual user never has to look at it. Everything in
    here has a sensible default that reproduces plain "give me the instrumental"
    behavior out of the box."""

    settings_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stem_checkboxes: dict[str, QCheckBox] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        self.toggle_button = QPushButton("▸  Advanced options")
        self.toggle_button.setObjectName("advancedToggle")
        self.toggle_button.setCursor(Qt.PointingHandCursor)
        self.toggle_button.setCheckable(True)
        self.toggle_button.clicked.connect(self._on_toggle)
        outer.addWidget(self.toggle_button)

        self.content = QFrame()
        self.content.setObjectName("advancedContent")
        self.content.setVisible(False)
        content_layout = QVBoxLayout(self.content)
        content_layout.setSpacing(12)

        content_layout.addWidget(self._row("Separation mode", self._build_mode_combo()))

        self.memory_warning = QLabel(
            "⚠ Uses significantly more memory than Vocals + Instrumental, and can crash "
            "on longer songs if your PC is low on RAM."
        )
        self.memory_warning.setObjectName("memoryWarning")
        self.memory_warning.setWordWrap(True)
        self.memory_warning.setVisible(False)
        content_layout.addWidget(self.memory_warning)

        content_layout.addWidget(self._row("Quality", self._build_quality_combo()))
        content_layout.addWidget(self._row("Output format", self._build_format_row()))

        self.stems_label = QLabel("TRACKS TO SAVE")
        self.stems_label.setObjectName("sectionLabel")
        content_layout.addWidget(self.stems_label)
        self.stems_row = QHBoxLayout()
        self.stems_row.setSpacing(14)
        content_layout.addLayout(self.stems_row)

        outer.addWidget(self.content)

        self._rebuild_stem_checkboxes()

    def _row(self, label_text: str, field_widget: QWidget) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        label.setFixedWidth(120)
        layout.addWidget(label)
        layout.addWidget(field_widget, stretch=1)
        return row

    def _build_mode_combo(self) -> QComboBox:
        self.mode_combo = QComboBox()
        for mode in ("2stems", "4stems", "5stems"):
            self.mode_combo.addItem(STEM_MODE_LABELS[mode], mode)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        return self.mode_combo

    def _build_quality_combo(self) -> QComboBox:
        self.quality_combo = QComboBox()
        for label, _fast, _mwf in QUALITY_PRESETS:
            self.quality_combo.addItem(label)
        self.quality_combo.setCurrentIndex(1)  # Standard
        self.quality_combo.currentIndexChanged.connect(lambda _: self.settings_changed.emit())
        return self.quality_combo

    def _build_format_row(self) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.format_combo = QComboBox()
        for fmt in OUTPUT_FORMATS:
            self.format_combo.addItem(fmt.upper(), fmt)
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)

        self.bitrate_combo = QComboBox()
        for rate in MP3_BITRATES:
            self.bitrate_combo.addItem(rate, rate)
        self.bitrate_combo.setCurrentIndex(1)  # 192k
        self.bitrate_combo.setVisible(False)
        self.bitrate_combo.currentIndexChanged.connect(lambda _: self.settings_changed.emit())

        layout.addWidget(self.format_combo)
        layout.addWidget(self.bitrate_combo)
        layout.addStretch()
        return row

    def _on_toggle(self, checked: bool) -> None:
        self.content.setVisible(checked)
        self.toggle_button.setText(("▾" if checked else "▸") + "  Advanced options")

    def _on_mode_changed(self, _index: int) -> None:
        self._rebuild_stem_checkboxes()
        self.memory_warning.setVisible(self.mode_combo.currentData() != "2stems")
        self.settings_changed.emit()

    def _on_format_changed(self, _index: int) -> None:
        self.bitrate_combo.setVisible(self.format_combo.currentData() == "mp3")
        self.settings_changed.emit()

    def _rebuild_stem_checkboxes(self) -> None:
        while self.stems_row.count():
            item = self.stems_row.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._stem_checkboxes.clear()

        mode = self.mode_combo.currentData()
        for stem in STEM_NAMES[mode]:
            label = f"{STEM_ICONS.get(stem, '')} {FRIENDLY_STEM_NAMES.get(stem, stem)}"
            checkbox = QCheckBox(label)
            checkbox.setChecked(stem != "vocals")
            checkbox.stateChanged.connect(self._on_stem_toggled)
            self._stem_checkboxes[stem] = checkbox
            self.stems_row.addWidget(checkbox)
        self.stems_row.addStretch()

    def _on_stem_toggled(self, _state: int) -> None:
        # Never allow zero stems selected -- re-check the last one that would leave none.
        checked = [s for s, cb in self._stem_checkboxes.items() if cb.isChecked()]
        if not checked:
            sender = self.sender()
            sender.blockSignals(True)
            sender.setChecked(True)
            sender.blockSignals(False)
        self.settings_changed.emit()

    def get_settings(self) -> dict:
        _label, fast, mwf = QUALITY_PRESETS[self.quality_combo.currentIndex()]
        output_format = self.format_combo.currentData()
        stems_to_keep = [s for s, cb in self._stem_checkboxes.items() if cb.isChecked()]
        return {
            "stem_mode": self.mode_combo.currentData(),
            "fast": fast,
            "mwf": mwf,
            "output_format": output_format,
            "bitrate": self.bitrate_combo.currentData() if output_format == "mp3" else None,
            "stems_to_keep": stems_to_keep,
        }
