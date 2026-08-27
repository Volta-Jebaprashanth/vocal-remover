import json
import os
import re
import subprocess
import sys

from PyQt5.QtCore import QObject, QProcess, QThread, pyqtSignal

from common import resource_path
from core.ytdlp_manager import ensure_ytdlp

PROGRESS_RE = re.compile(r"\[download\]\s+([\d.]+)%")

# Extensions/suffixes that mean "not actually finished yet" -- a crash mid-download
# can leave these behind, and they should never be mistaken for the real output.
_INCOMPLETE_SUFFIXES = (".part", ".ytdl", ".temp")

_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


class _YtDlpFetchThread(QThread):
    """Ensures yt-dlp.exe is present/fresh without blocking the UI thread -- a
    first-run fetch (or periodic refresh) hits the network and can take a few
    seconds."""

    progress = pyqtSignal(int)
    ready = pyqtSignal(str)
    failed = pyqtSignal(str)

    def run(self) -> None:
        try:
            path = ensure_ytdlp(progress_cb=self.progress.emit)
            self.ready.emit(path)
        except Exception as exc:
            self.failed.emit(str(exc))


class _ResolveThread(QThread):
    """Looks up what a link points to (single video vs. playlist) without
    downloading anything, so the controller knows the full item count up front and
    can report "video 2 of 15" style progress."""

    resolved = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, ytdlp_path: str, url: str, is_playlist: bool, parent=None):
        super().__init__(parent)
        self._ytdlp_path = ytdlp_path
        self._url = url
        self._is_playlist = is_playlist

    def run(self) -> None:
        args = [self._ytdlp_path, "--dump-single-json", "--no-warnings"]
        if self._is_playlist:
            # --flat-playlist skips fetching full metadata for every entry up front,
            # which matters a lot for long playlists -- we only need id/title/url
            # here, the rest is resolved per-entry when it's actually downloaded.
            args += ["--flat-playlist", "--yes-playlist"]
        else:
            args += ["--no-playlist"]
        args.append(self._url)

        try:
            result = subprocess.run(
                args, capture_output=True, text=True, timeout=60, creationflags=_NO_WINDOW
            )
        except Exception as exc:
            self.failed.emit(f"Could not look up that link: {exc}")
            return

        if result.returncode != 0:
            message = result.stderr.strip()[-400:] or "Could not look up that link."
            self.failed.emit(message)
            return

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            self.failed.emit("Unexpected response while looking up that link.")
            return

        entries = []
        if data.get("_type") == "playlist" and "entries" in data:
            for entry in data["entries"]:
                if not entry:
                    continue
                video_id = entry.get("id")
                video_url = entry.get("url") or (
                    f"https://www.youtube.com/watch?v={video_id}" if video_id else None
                )
                if not video_url:
                    continue
                entries.append({"title": entry.get("title") or video_id or "video", "url": video_url})
        else:
            entries.append({"title": data.get("title") or "video", "url": self._url})

        self.resolved.emit(entries)


class YouTubeController(QObject):
    """Resolves a video/playlist link, then downloads each entry in its own fresh
    yt-dlp.exe subprocess, one at a time -- deliberately the same shape as
    SeparationController's one-subprocess-per-file design (see CLAUDE.md): a broken
    video partway through a playlist should only fail that entry, not the rest of
    the batch, and each process only ever has one download's worth of state."""

    status_changed = pyqtSignal(str)
    item_started = pyqtSignal(str, int, int)  # title, index, total
    item_done = pyqtSignal(str, str)  # title, filepath
    item_failed = pyqtSignal(str, str)  # title, error
    all_done = pyqtSignal()
    fatal_error = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._process = QProcess(self)
        self._process.readyReadStandardOutput.connect(self._read_stdout)
        self._process.readyReadStandardError.connect(self._read_stderr)
        self._process.finished.connect(self._on_process_finished)
        self._process.errorOccurred.connect(self._on_error_occurred)

        self._ytdlp_path = None
        self._output_dir = None
        self._extra_args = []
        self._entries = []
        self._total = 0
        self._index = 0
        self._current_title = ""
        self._mtimes_before = {}
        self._buffer = ""
        self._stderr_buffer = ""
        self._stopped = False

    def start(self, url: str, is_playlist: bool, output_dir: str, extra_args: list) -> None:
        self._output_dir = output_dir
        self._extra_args = extra_args

        self.status_changed.emit("Preparing YouTube downloader...")
        self._fetch_thread = _YtDlpFetchThread(self)
        self._fetch_thread.progress.connect(
            lambda p: self.status_changed.emit(f"Preparing YouTube downloader... {p}%")
        )
        self._fetch_thread.ready.connect(lambda path: self._on_ytdlp_ready(path, url, is_playlist))
        self._fetch_thread.failed.connect(
            lambda err: self.fatal_error.emit(f"Could not prepare the YouTube downloader: {err}")
        )
        self._fetch_thread.start()

    def _on_ytdlp_ready(self, path: str, url: str, is_playlist: bool) -> None:
        if self._stopped:
            return
        self._ytdlp_path = path
        self.status_changed.emit("Looking up video information...")
        self._resolve_thread = _ResolveThread(path, url, is_playlist, self)
        self._resolve_thread.resolved.connect(self._on_resolved)
        self._resolve_thread.failed.connect(self.fatal_error.emit)
        self._resolve_thread.start()

    def _on_resolved(self, entries: list) -> None:
        if self._stopped:
            return
        if not entries:
            self.fatal_error.emit("No videos found at that link.")
            return
        self._entries = entries
        self._total = len(entries)
        self._index = 0
        self._start_next()

    def stop(self) -> None:
        """Cancels whatever stage is in flight (preparing yt-dlp, looking up the
        link, or an active download) -- the fetch/resolve threads are left to run
        to completion since QThread.terminate() is unsafe, but the _stopped flag
        makes their callbacks (and any further queued entries) into no-ops."""
        if self._stopped:
            return
        self._stopped = True
        self._entries = []
        if self._process.state() != QProcess.NotRunning:
            self._process.kill()
        self.cancelled.emit()

    def _start_next(self) -> None:
        if self._stopped:
            return
        if not self._entries:
            self.all_done.emit()
            return

        entry = self._entries.pop(0)
        self._index += 1
        self._current_title = entry.get("title") or "video"
        self._buffer = ""
        self._stderr_buffer = ""
        self.item_started.emit(self._current_title, self._index, self._total)

        os.makedirs(self._output_dir, exist_ok=True)
        # yt-dlp's own --print "after_move:%(filepath)s" turned out unreliable for
        # titles with Windows-illegal characters (e.g. "|"): the string it prints
        # for that field doesn't always match the actual sanitized filename it
        # writes to disk (confirmed by comparing raw bytes against the real file),
        # so trusting the printed path silently reports a successful download as
        # failed. Recording each existing file's mtime and comparing after the run
        # is immune to whatever yt-dlp's sanitizer does internally -- and unlike a
        # plain "is this filename new" set-diff, it still recognizes a re-download
        # of the same video (same resulting filename) as long as --force-overwrites
        # below guarantees the file actually gets rewritten rather than skipped.
        self._mtimes_before = {}
        for name in os.listdir(self._output_dir):
            try:
                self._mtimes_before[name] = os.path.getmtime(os.path.join(self._output_dir, name))
            except OSError:
                pass

        # Truncate the title component so a long video title can't push the path
        # past Windows' MAX_PATH; the video id keeps the name unique regardless.
        output_template = os.path.join(self._output_dir, "%(title).150B [%(id)s].%(ext)s")
        args = [
            "--newline",
            "--no-playlist",
            "--force-overwrites",
            "--ffmpeg-location", resource_path("ffmpeg"),
            "-o", output_template,
            *self._extra_args,
            entry["url"],
        ]
        self._process.start(self._ytdlp_path, args)

    def _find_new_output_file(self):
        try:
            names_after = os.listdir(self._output_dir)
        except OSError:
            return None

        candidates = []
        for name in names_after:
            if name.endswith(_INCOMPLETE_SUFFIXES):
                continue
            path = os.path.join(self._output_dir, name)
            try:
                mtime = os.path.getmtime(path)
            except OSError:
                continue
            before_mtime = self._mtimes_before.get(name)
            if before_mtime is None or mtime > before_mtime:
                candidates.append((mtime, path))

        if not candidates:
            return None
        # Normally there's exactly one. If more than one somehow shows up, the
        # most recently modified is the finished output, not a stray sidecar.
        candidates.sort(reverse=True)
        return candidates[0][1]

    def _read_stdout(self) -> None:
        data = bytes(self._process.readAllStandardOutput()).decode("utf-8", errors="replace")
        self._buffer += data
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            match = PROGRESS_RE.search(line)
            if match:
                self.status_changed.emit(f"Downloading {self._current_title}... {match.group(1)}%")

    def _read_stderr(self) -> None:
        data = bytes(self._process.readAllStandardError()).decode("utf-8", errors="replace")
        self._stderr_buffer += data

    def _on_error_occurred(self, error) -> None:
        if self._stopped:
            return
        if error == QProcess.FailedToStart:
            self.fatal_error.emit("Could not start the YouTube downloader.")

    def _on_process_finished(self, exit_code: int, _exit_status) -> None:
        if self._stopped:
            return
        result_path = self._find_new_output_file() if exit_code == 0 else None
        if result_path:
            self.item_done.emit(self._current_title, result_path)
        else:
            detail = self._stderr_buffer.strip()[-400:] or "Download failed."
            self.item_failed.emit(self._current_title, detail)
        self._start_next()
