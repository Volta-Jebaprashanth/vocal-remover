STYLESHEET = """
QWidget {
    background-color: #14151f;
    color: #e6e6f0;
    font-family: 'Segoe UI', sans-serif;
    font-size: 13px;
}

QLabel {
    background-color: transparent;
}

QLabel#headerSubtitle {
    font-size: 12px;
    color: #8b8ea3;
}

QFrame#dropZone {
    background-color: #1c1e2b;
    border: 2px dashed #3d4160;
    border-radius: 14px;
}

QFrame#dropZone[dragActive="true"] {
    background-color: #23263a;
    border: 2px dashed #7c5cff;
}

QLabel#dropIcon {
    font-size: 34px;
}

QLabel#dropTitle {
    font-size: 15px;
    font-weight: 600;
    color: #ffffff;
}

QLabel#dropSubtitle {
    font-size: 11px;
    color: #8b8ea3;
}

QLabel#sectionLabel {
    font-size: 12px;
    font-weight: 600;
    color: #b7b9cc;
    text-transform: uppercase;
}

QLineEdit {
    background-color: #1c1e2b;
    border: 1px solid #33364d;
    border-radius: 8px;
    padding: 8px 10px;
    color: #e6e6f0;
}

QLineEdit:focus {
    border: 1px solid #7c5cff;
}

QPushButton {
    background-color: #262a3d;
    border: 1px solid #3d4160;
    border-radius: 8px;
    padding: 8px 16px;
    color: #e6e6f0;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #313550;
    border: 1px solid #7c5cff;
}

QPushButton:pressed {
    background-color: #23263a;
}

QPushButton:disabled {
    background-color: #1c1e2b;
    border: 1px solid #2a2c3d;
    color: #55586e;
}

QPushButton#runButton {
    background-color: #7c5cff;
    border: none;
    color: #ffffff;
    font-size: 14px;
    font-weight: 700;
    padding: 12px 20px;
    border-radius: 10px;
}

QPushButton#runButton:hover {
    background-color: #8e70ff;
}

QPushButton#runButton:pressed {
    background-color: #6a4be0;
}

QPushButton#runButton:disabled {
    background-color: #3a3a4a;
    color: #77778a;
}

QProgressBar {
    background-color: #1c1e2b;
    border: 1px solid #33364d;
    border-radius: 8px;
    height: 10px;
    text-align: center;
    color: transparent;
}

QProgressBar::chunk {
    background-color: #7c5cff;
    border-radius: 8px;
}

QLabel#statusLabel {
    color: #8b8ea3;
    font-size: 12px;
}

QLabel#statusLabel[state="error"] {
    color: #ff6b6b;
}

QLabel#statusLabel[state="success"] {
    color: #4ade80;
}

QLabel#statusLabel[state="downloading"] {
    color: #5cb8ff;
    font-weight: 600;
}

QPushButton#linkButton {
    background: transparent;
    border: none;
    color: #9d8cff;
    font-weight: 600;
    padding: 2px 4px;
}

QPushButton#linkButton:hover {
    color: #b7a8ff;
    background: transparent;
    border: none;
}

QListWidget#fileQueueList {
    background-color: #1c1e2b;
    border: 1px solid #2a2c3d;
    border-radius: 10px;
    padding: 2px;
}

QListWidget#fileQueueList::item {
    border-bottom: 1px solid #23263a;
}

QListWidget#fileQueueList::item:last {
    border-bottom: none;
}

QLabel#queueItemName {
    color: #e6e6f0;
}

QPushButton#queueRemoveButton {
    background: transparent;
    border: none;
    color: #6f7290;
    font-weight: 700;
    padding: 0;
    border-radius: 11px;
}

QPushButton#queueRemoveButton:hover {
    background-color: #3a2a3a;
    color: #ff6b6b;
    border: none;
}

QPushButton#advancedToggle {
    background: transparent;
    border: none;
    color: #b7b9cc;
    font-weight: 600;
    text-align: left;
    padding: 4px 2px;
}

QPushButton#advancedToggle:hover {
    background: transparent;
    border: none;
    color: #ffffff;
}

QFrame#advancedContent {
    background-color: #191b28;
    border: 1px solid #262a3d;
    border-radius: 12px;
    padding: 14px;
}

QLabel#fieldLabel {
    color: #b7b9cc;
    font-weight: 500;
}

QComboBox {
    background-color: #1c1e2b;
    border: 1px solid #33364d;
    border-radius: 8px;
    padding: 6px 10px;
    color: #e6e6f0;
}

QComboBox:hover {
    border: 1px solid #7c5cff;
}

QComboBox::drop-down {
    border: none;
    width: 22px;
}

QComboBox QAbstractItemView {
    background-color: #1c1e2b;
    border: 1px solid #3d4160;
    selection-background-color: #7c5cff;
    color: #e6e6f0;
    outline: none;
}

QCheckBox {
    color: #e6e6f0;
    spacing: 6px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid #3d4160;
    background-color: #1c1e2b;
}

QCheckBox::indicator:checked {
    background-color: #7c5cff;
    border: 1px solid #7c5cff;
}

QFrame#resultRow {
    background-color: #1c1e2b;
    border-radius: 8px;
}

QLabel#resultOk {
    color: #4ade80;
}

QLabel#resultError {
    color: #ff6b6b;
}

QLabel#resultDetail {
    color: #8b8ea3;
    font-size: 11px;
}

QLabel#memoryWarning {
    color: #f5a742;
    font-size: 11px;
    background-color: #2a2415;
    border: 1px solid #4a3d1f;
    border-radius: 8px;
    padding: 8px 10px;
}
"""
