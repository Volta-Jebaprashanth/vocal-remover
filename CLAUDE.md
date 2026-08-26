# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

A Windows desktop app (PyQt5 UI) that separates a song into stems using Spleeter (Deezer's source-separation library) — from simple vocal removal (keep the instrumental) up to full 5-stem separation (vocals/drums/bass/piano/other), with batch processing, quality presets, and format choice. Target deliverable is a single-file, offline-capable `.exe` built with PyInstaller — end users should need nothing installed (no Python, no ffmpeg, no internet for the model).

**Current status:** the app runs correctly from source (`app/main.py`). PyInstaller packaging into the final onefile `.exe` has **not** been done yet — no `.spec` file exists and `pyinstaller` is not yet installed in `venv`. That's the next milestone.

## Critical environment constraint

This machine's default Python is 3.14, which **cannot run this project** — Spleeter pins to old TensorFlow (2.9.3 here), which does not support Python past ~3.10 and breaks under numpy 2.x. The project venv **must** use Python 3.10:

```
py -3.10 -m venv venv
```

Do not `pip install --upgrade` inside this venv without checking compatibility — `numpy` in particular must stay `<2` (pinned in `requirements.txt`) or TensorFlow import fails with `AttributeError: _ARRAY_API not found`.

## Commands

All commands run from the repo root, using the project venv (not system Python):

```
# install/update deps
./venv/Scripts/python.exe -m pip install -r requirements.txt

# run the app
cd app && "../venv/Scripts/python.exe" main.py
# or windowed, no console:
cd app && "../venv/Scripts/pythonw.exe" main.py
```

There is no test suite and no linter configured yet. Ad-hoc verification during development has been done by driving `core.separation_controller.SeparationController` directly from a throwaway script (construct it, connect signals, call `.start(job)`, run a `QEventLoop`) rather than clicking through the UI — see git history / session logs for examples.

## Architecture

### One `Separator` per process, and one *file* per process — this drives everything

**Spleeter's `Separator` can only be instantiated once per OS process.** A second instance in the same process — even with identical settings — corrupts TensorFlow's global graph/eager-execution state and crashes with `AssertionError: Nesting violated for default stack...` followed by `ValueError: When eager execution is enabled, use_resource cannot be set to false`. (Reusing *one* `Separator` across many files via `separate_to_file` in a loop is fine and is spleeter's own supported pattern — it's a *second construction* that's fatal.)

Consequently, **the GUI process never imports spleeter/tensorflow at all.** `app/worker_main.py` is re-invoked as a child process (same exe/script, `--worker-job <job.json>` flag) to do the actual work. This is why the architecture has a controller/subprocess split instead of the more obvious `QThread`.

**On top of that, each child process handles exactly one file, not the whole batch.** This was *not* the original design — the first version shared one `Separator`/process across an entire batch for speed, and it worked fine in every synthetic test. It failed in real use: a real user hit a genuine crash running 5-stems + batch of 3 real songs, confirmed via Windows Event Viewer (`Get-WinEvent -FilterHashtable @{LogName='Application'}`) as `Faulting application: pythonw.exe, Faulting module: ucrtbase.dll, Exception code: 0xc0000409` — a native C-runtime `abort()`, not a catchable Python exception. Spleeter loads a song's *entire* spectrogram into memory at once (no chunking/streaming), and 5-stems on a real multi-minute song on an 8GB-RAM machine exhausted memory badly enough that some C++ allocator (TensorFlow/Eigen) called `std::terminate()` directly instead of throwing a catchable `std::bad_alloc`. That kind of crash bypasses every `try/except` in `worker_main.py` and kills the whole process — which, under the original one-process-per-batch design, silently took the rest of the queued files down with it.

The fix: `SeparationController` now pops one file off the queue at a time and spawns a **fresh subprocess per file**, waiting for it to finish (or crash) before starting the next. A crash while processing file 2 of 5 now surfaces as a `file_failed` for file 2 with an actionable message (`CRASH_MESSAGE` in `separation_controller.py` — suggests Fast preview quality, fewer stems, or fewer concurrent songs), and files 3–5 still run. The cost is a reloaded model (and TF startup overhead, several seconds) per file instead of once per batch — an accepted tradeoff for not losing an entire batch to one bad file. **Don't revert to one-process-per-batch** without solving the crash-isolation problem some other way.

- `app/main.py` — dispatches: no `--worker-job` arg → launch the Qt GUI (`run_gui()`); `--worker-job` present → delegate straight to `worker_main.run_job()` and never touch Qt.
- `app/worker_main.py` — the actual separation logic for **one file** (job JSON has a single `input_path`, not a list). Builds one `Separator(descriptor, MWF=..., multiprocess=False)`, calls `separate_to_file` once, copies only the requested stems to the output location, and reports progress as one-JSON-object-per-line on **stdout**, each line prefixed with `JOBEVENT ` (event types: `status`, `file_done`, `file_failed`).
- `app/core/separation_controller.py` — `SeparationController(QObject)`, lives in the GUI process. Holds the file queue and per-batch settings; `_start_next()` pops one path, writes just that file's job to a temp JSON, and launches a worker subprocess (`sys.executable` + the right args depending on `sys.frozen`). Parses `JOBEVENT ` lines off stdout and re-emits them as Qt signals (`status_changed`, `file_started`, `file_done`, `file_failed`, `all_done`, `fatal_error`) that `MainWindow` connects to — this external signal API is batch-shaped even though the internals are per-file, so `MainWindow` needed no changes when this was refactored. If a process's `finished` fires without a `file_done`/`file_failed` having been seen for the file it was working on, that's treated as a crash: `_on_process_finished` checks stderr for an actual Python traceback (rare — most native crashes leave only TF's routine deprecation-warning noise) and falls back to the friendly `CRASH_MESSAGE` otherwise, then continues to the next file regardless. `errorOccurred` is also handled (`QProcess.FailedToStart` → `fatal_error`) so a broken install doesn't hang the UI silently.
- `app/common.py` — shared between the GUI and worker processes: `resource_path()` (see below), `configure_environment()` (env vars + the stdout/stderr `None` patch, must run first thing in *every* process), and the stem-name/label/icon tables (`STEM_NAMES`, `STEM_MODE_LABELS`, `FRIENDLY_STEM_NAMES`, `STEM_ICONS`, `OUTPUT_FORMATS`, `MP3_BITRATES`).

If you ever need to add a second concurrent separation (e.g. a "cancel and start something else" feature), it must still be one `Separator` per process — don't be tempted to reuse a process for a second job; always spawn a new one.

### Memory is the real constraint, not CPU time

4/5-stem modes need noticeably more RAM than 2-stems (more simultaneous output masks over the same full-song spectrogram), and Spleeter has no chunking — the whole song is processed in memory at once. On an 8GB-RAM dev machine, a single 5-stems file at fast (16kHz) quality peaked around 3.7GB resident just for the worker process. `AdvancedPanel` shows a static warning (`memory_warning` label) whenever a non-2stems mode is selected. If you're tempted to "fix" the crash risk more thoroughly, the per-file subprocess isolation (above) is the containment strategy that's actually in place today — there's no chunked/streaming separation implemented, and adding one would be a substantial spleeter-internals change, not a quick fix.

### Entry point ordering matters

`configure_environment()` (in `common.py`) must run **before** any PyQt/spleeter/tensorflow import, in both the GUI process and the worker subprocess — spleeter reads `MODEL_PATH` and locates `ffmpeg`/`ffprobe` on `PATH` at import/construction time, and the `sys.stdout is None` patch must land before anything tries to log. `main.py` calls it immediately in `__main__`, before deciding whether to run the GUI or the worker.

`resource_path()` resolves bundled files (ffmpeg binaries, pretrained models) relative to `sys._MEIPASS` when frozen by PyInstaller, or relative to `app/` when run from source. Any new bundled asset must be looked up through this helper, not a hardcoded relative path.

### Bundled, offline-capable dependencies

- `app/ffmpeg/ffmpeg.exe` + `app/ffmpeg/ffprobe.exe` — spleeter's `FFMPEGProcessAudioAdapter` shells out to both binaries (not just `ffmpeg`); missing either raises `SpleeterError: ... binary not found`. Sourced from the gyan.dev "essentials" static build. Confirmed working for `wav`, `mp3` (libmp3lame), and implicitly `flac` (native ffmpeg encoder, untested but standard).
- `app/pretrained_models/` — **all six** spleeter model variants are pre-downloaded here so the packaged exe works fully offline and every UI option actually works: `2stems`, `2stems-16kHz`, `4stems`, `4stems-16kHz`, `5stems`, `5stems-16kHz`. Each populates itself the first time it's used with `MODEL_PATH` pointed at this folder (spleeter downloads lazily from `github.com/deezer/spleeter` releases on first use of a given descriptor, then reuses it) — **but each descriptor must be triggered in its own separate process** the first time, per the one-`Separator`-per-process constraint above; don't loop over descriptors in one Python session to populate this folder.

Both `app/ffmpeg/` and `app/pretrained_models/` are gitignored (large binaries) — a fresh clone needs to re-download/re-populate them before the app or a PyInstaller build will work.

### UI structure

Progressive disclosure is the deliberate design: a casual user drops a song, picks a folder, and clicks Run without ever seeing a setting. Everything added for multi-stem/batch/quality/format lives behind a collapsed-by-default panel.

- `ui/main_window.py` (`MainWindow`) — top-level layout and the signal-driven state machine for one job (wires `FileQueue`, `AdvancedPanel`, and `SeparationController` together; builds a scrolling per-file results list of ✅/❌ rows as the job progresses).
- `ui/drop_zone.py` (`DropZone`) — drag-and-drop target + click-to-browse, filters by `AUDIO_EXTENSIONS`, emits `files_selected(list)` (plural — accepts multiple files at once for batch mode). It's stateless about the queue; `main_window` forwards new paths into...
- `ui/file_queue.py` (`FileQueue`) — the actual list of queued songs, one row per file with a remove (✕) button and a "Clear all" action, deduplicates by path, emits `changed` whenever the queue is mutated.
- `ui/advanced_panel.py` (`AdvancedPanel`) — the collapsible settings panel: separation mode (2/4/5 stems, human-labeled), a single "Quality" preset combo that collapses spleeter's two independent knobs (`fast`/16kHz and `MWF`) into three intuitive choices (Fast preview / Standard / Best quality) rather than exposing them as separate checkboxes, output format + bitrate (bitrate only shown for MP3), and a row of per-stem checkboxes that rebuilds whenever the stem mode changes (defaults: everything checked except vocals, at least one stem is always forced to stay checked). `get_settings()` returns the dict that becomes most of the job JSON sent to the worker.
- `ui/styles.py` — single `STYLESHEET` string (dark theme, purple accent) applied once at the `MainWindow` level; widgets are styled via `objectName` selectors, not inline styles.

### Windows-specific gotchas already worked around

- **One `Separator` per process** — see above; this is the big one and the reason for the subprocess architecture at all.
- **`Separator(..., multiprocess=False)`** is still used in the worker even though it's now an isolated subprocess — spleeter's default `multiprocess=True` spins up a `multiprocessing.Pool`, which under a frozen/windowed Windows exe can spawn runaway child processes (observed directly: a single test run left ~10 stray `pythonw.exe` processes behind). Don't remove this without re-testing under `pythonw`/a frozen build.
- **`sys.stdout`/`sys.stderr` are `None`** under `pythonw.exe` or a windowed PyInstaller build (no console attached). Spleeter/TensorFlow logging calls `.write()` on them and crashes with `'NoneType' object has no attribute 'write'` if not patched — handled in `configure_environment()`. Must run before any other import, in every process.
- `multiprocessing.freeze_support()` is called in `main.py`'s `__main__` guard as a safety net for the frozen build.
- The worker's stdout is a structured IPC channel (`JOBEVENT `-prefixed JSON lines) — any stray `print()` added to `worker_main.py` or its imports that writes plain text to stdout risks being misread as a progress event line (it won't match the prefix so it's just ignored, but keep this in mind before adding logging there).
