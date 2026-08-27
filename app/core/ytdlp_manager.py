import os
import shutil
import tempfile
import time
import urllib.request

from common import ytdlp_cache_dir

# GitHub's "latest" release alias -- always resolves (via redirect) to whatever the
# current stable yt-dlp.exe build is, so we never need to query the GitHub API for a
# version number first.
YT_DLP_DOWNLOAD_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"

# How often to check for a newer build once one is already cached. yt-dlp itself
# only needs updating when YouTube breaks something, which isn't hourly -- checking
# this often avoids a network round-trip on every single download while still
# self-healing well within a normal usage cadence.
UPDATE_CHECK_INTERVAL_SECONDS = 7 * 24 * 60 * 60


def ytdlp_exe_path() -> str:
    return os.path.join(ytdlp_cache_dir(), "yt-dlp.exe")


def _download(dest_path: str, progress_cb=None) -> None:
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(dest_path), suffix=".download")
    os.close(fd)
    try:
        def _reporthook(block_num, block_size, total_size):
            if progress_cb and total_size > 0:
                downloaded = block_num * block_size
                progress_cb(min(100, int(downloaded * 100 / total_size)))

        urllib.request.urlretrieve(YT_DLP_DOWNLOAD_URL, tmp_path, reporthook=_reporthook)
        # shutil.move falls back to copy+delete (overwriting the destination) when a
        # plain os.rename can't be used, which covers the "file already exists" case
        # on Windows that a raw os.rename would reject.
        shutil.move(tmp_path, dest_path)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def ensure_ytdlp(progress_cb=None, force: bool = False) -> str:
    """Returns a path to a usable yt-dlp.exe, fetching or refreshing it first if
    needed. If a cached copy already exists, a failed refresh attempt is swallowed
    and the stale copy is used instead -- better to download with a slightly old
    yt-dlp than to fail outright because of a transient network hiccup. Only raises
    when there is no usable cached copy at all yet."""
    exe_path = ytdlp_exe_path()
    exists = os.path.exists(exe_path)

    if not exists:
        _download(exe_path, progress_cb)
        return exe_path

    stale = force or (time.time() - os.path.getmtime(exe_path)) > UPDATE_CHECK_INTERVAL_SECONDS
    if stale:
        try:
            _download(exe_path, progress_cb)
        except Exception:
            pass  # keep using the existing cached copy

    return exe_path
