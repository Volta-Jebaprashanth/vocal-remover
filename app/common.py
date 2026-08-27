import os
import sys


def resource_path(*parts: str) -> str:
    """Resolve a path both in dev (running from source) and when frozen by PyInstaller."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


def default_model_path() -> str:
    """Where spleeter should cache downloaded models.

    In a frozen build the exe typically lives under Program Files (or wherever the
    installer put it), which a standard, non-elevated user cannot write to -- and
    since models are no longer bundled into the build (see build.spec), this *must*
    be writable so spleeter's own download-on-first-use can succeed. Dev runs from
    source keep using the local app/pretrained_models folder that's already
    populated, so testing doesn't re-download anything."""
    if getattr(sys, "frozen", False):
        return os.path.join(os.environ["LOCALAPPDATA"], "VocalRemover", "pretrained_models")
    return resource_path("pretrained_models")


def ytdlp_cache_dir() -> str:
    """Where the standalone yt-dlp.exe used for the YouTube features is cached.

    Deliberately NOT bundled into the build, unlike ffmpeg -- YouTube changes its
    internals often enough to break yt-dlp's extractor, and the yt-dlp project ships
    fixed builds quickly (often within a day). Fetching it at runtime into a
    writable per-user location (same reasoning as default_model_path() above) means
    a breakage can self-heal on next launch by re-fetching, instead of requiring a
    full app rebuild + reinstall every time YouTube changes something."""
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "VocalRemover", "yt-dlp")


def configure_environment() -> None:
    """Must run before spleeter/tensorflow is imported anywhere, in every process
    (GUI process and worker subprocess alike)."""
    # pythonw.exe / a windowed PyInstaller build has no console, so sys.stdout and
    # sys.stderr can be None. Libraries that call .write() on them crash with
    # "'NoneType' object has no attribute 'write'".
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")

    # When stdout/stderr are redirected pipes rather than a real console (true for
    # every worker subprocess, since its output is piped back to the GUI process),
    # Python falls back to the OS's ANSI codepage (cp1252 here) instead of UTF-8.
    # A YouTube-sourced filename can contain non-ASCII characters (e.g. yt-dlp's own
    # "｜" substitution for a Windows-illegal "|" in a video title), and any print/
    # log call touching that path then crashes with
    # "UnicodeEncodeError: 'charmap' codec can't encode character ...". Forcing
    # UTF-8 here, in every process, avoids that regardless of what ends up printed.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")

    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
    os.environ.setdefault("MODEL_PATH", default_model_path())
    os.environ["PATH"] = resource_path("ffmpeg") + os.pathsep + os.environ.get("PATH", "")


# Stem keys as spleeter names them, in a sensible display order.
STEM_NAMES = {
    "2stems": ["vocals", "accompaniment"],
    "4stems": ["vocals", "drums", "bass", "other"],
    "5stems": ["vocals", "drums", "bass", "piano", "other"],
}

STEM_MODE_LABELS = {
    "2stems": "Vocals + Instrumental",
    "4stems": "Vocals + Drums + Bass + Other",
    "5stems": "Vocals + Drums + Bass + Piano + Other",
}

FRIENDLY_STEM_NAMES = {
    "vocals": "Vocals",
    "accompaniment": "Instrumental",
    "drums": "Drums",
    "bass": "Bass",
    "piano": "Piano",
    "other": "Other",
}

STEM_ICONS = {
    "vocals": "🎤",
    "accompaniment": "🎵",
    "drums": "🥁",
    "bass": "🎸",
    "piano": "🎹",
    "other": "🎻",
}

OUTPUT_FORMATS = ["wav", "mp3", "flac"]
MP3_BITRATES = ["128k", "192k", "256k", "320k"]
