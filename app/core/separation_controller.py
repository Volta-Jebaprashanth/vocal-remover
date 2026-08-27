import json
import os
import sys
import tempfile

from PyQt5.QtCore import QObject, QProcess, pyqtSignal

EVENT_PREFIX = "JOBEVENT "

CRASH_MESSAGE = (
    "The separation process crashed while working on this file. This almost always "
    "means it ran out of memory (5-stem separation on a long song can need several "
    "GB of RAM). Try: Fast preview quality, a smaller separation mode (Vocals + "
    "Instrumental), processing fewer songs at once, or closing other applications."
)


class SeparationController(QObject):
    """Processes a queue of files one at a time, each in its own fresh subprocess.

    Two reasons for one-process-per-file rather than one process for the whole batch:

    1. Spleeter's Separator corrupts TensorFlow's global graph state if a second
       instance is created in the same process, so the GUI process itself never
       imports spleeter, and no process may build more than one Separator (see
       CLAUDE.md).
    2. A single file (large stem count + long song) can exhaust memory badly enough
       to crash the process at the C/C++ level (an unhandled bad_alloc -> abort()),
       which bypasses Python's try/except entirely. Isolating each file in its own
       process means that crash only fails *that* file -- the rest of the queue
       still runs, instead of silently losing the whole batch.
    """

    status_changed = pyqtSignal(str, bool)  # text, is_downloading
    file_started = pyqtSignal(str, int, int)  # filename, index, total
    file_done = pyqtSignal(str, list)  # filename, output_paths
    file_failed = pyqtSignal(str, str)  # filename, error
    all_done = pyqtSignal()
    fatal_error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._process = QProcess(self)
        self._process.readyReadStandardOutput.connect(self._read_stdout)
        self._process.finished.connect(self._on_process_finished)
        self._process.errorOccurred.connect(self._on_error_occurred)
        self._job_path = None
        self._buffer = ""
        self._settings = {}
        self._queue = []
        self._total = 0
        self._index = 0
        self._current_filename = ""
        self._current_file_reported = False

    def start(self, job: dict) -> None:
        self._settings = {k: v for k, v in job.items() if k != "input_paths"}
        self._queue = list(job["input_paths"])
        self._total = len(self._queue)
        self._index = 0
        self._start_next()

    def _start_next(self) -> None:
        if not self._queue:
            self.all_done.emit()
            return

        input_path = self._queue.pop(0)
        self._index += 1
        self._current_filename = os.path.basename(input_path)
        self._current_file_reported = False
        self._buffer = ""
        self.file_started.emit(self._current_filename, self._index, self._total)

        file_job = dict(self._settings)
        file_job["input_path"] = input_path

        fd, self._job_path = tempfile.mkstemp(suffix=".json", prefix="vocal_remover_job_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(file_job, f)

        if getattr(sys, "frozen", False):
            program = sys.executable
            args = ["--worker-job", self._job_path]
        else:
            main_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "main.py")
            program = sys.executable
            args = [os.path.abspath(main_py), "--worker-job", self._job_path]

        self._process.start(program, args)

    def _on_error_occurred(self, error) -> None:
        if error == QProcess.FailedToStart:
            self.fatal_error.emit("Could not start the separation worker process.")

    def _read_stdout(self) -> None:
        data = bytes(self._process.readAllStandardOutput()).decode("utf-8", errors="replace")
        self._buffer += data
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            line = line.strip()
            if line.startswith(EVENT_PREFIX):
                self._handle_event(line[len(EVENT_PREFIX):])

    def _handle_event(self, raw: str) -> None:
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            return

        kind = event.get("event")
        if kind == "status":
            self.status_changed.emit(event.get("text", ""), event.get("downloading", False))
        elif kind == "file_done":
            self._current_file_reported = True
            self.file_done.emit(self._current_filename, event.get("outputs", []))
        elif kind == "file_failed":
            self._current_file_reported = True
            self.file_failed.emit(self._current_filename, event.get("error", "Unknown error"))

    def _on_process_finished(self, exit_code: int, _exit_status) -> None:
        if self._job_path and os.path.exists(self._job_path):
            try:
                os.remove(self._job_path)
            except OSError:
                pass

        if not self._current_file_reported:
            # The worker process ended without ever reporting file_done/file_failed for
            # the file it was working on -- it crashed (native abort, OOM, etc.) rather
            # than hitting a normal Python exception (those are caught in worker_main.py
            # and reported as file_failed already).
            stderr = bytes(self._process.readAllStandardError()).decode("utf-8", errors="replace")
            if "Traceback (most recent call last)" in stderr:
                # A real Python traceback did make it to stderr somehow -- show it.
                message = stderr.strip()[-800:]
            else:
                message = CRASH_MESSAGE
            self.file_failed.emit(self._current_filename or "(unknown file)", message)

        self._start_next()
