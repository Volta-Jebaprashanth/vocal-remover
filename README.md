# Vocal Remover

A Windows desktop app that removes vocals from a song, leaving the instrumental/background track. Built with PyQt5 and [Spleeter](https://github.com/deezer/spleeter) (Deezer's source-separation library).

- Drag & drop a song (or click to browse) — MP3, WAV, FLAC, M4A, AAC, OGG
- Pick an output folder
- Click **Remove Vocals** — the background track is saved as `<song>_background.wav`

## Requirements

Spleeter depends on an old TensorFlow build that only supports **Python 3.9/3.10** (not whatever newer Python you may have as your system default). It also shells out to `ffmpeg`/`ffprobe`.

## Setup (development)

```powershell
# Install Python 3.10 if you don't have it
winget install --id Python.Python.3.10 -e

# Create the project venv with 3.10 specifically
py -3.10 -m venv venv

# Install dependencies
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Bundled binaries (not in git)

The app expects these to exist locally (both gitignored — regenerate them, don't commit them):

- `app/ffmpeg/ffmpeg.exe` and `app/ffmpeg/ffprobe.exe` — grab a static Windows build, e.g. the "essentials" build from `gyan.dev/ffmpeg/builds`, and copy both `.exe` files from its `bin/` folder into `app/ffmpeg/`.
- `app/pretrained_models/2stems/` — Spleeter's 2stems model. It downloads itself automatically the first time you run a real separation, as long as `MODEL_PATH` points at `app/pretrained_models` (already wired up in `app/main.py`). Just run the app once with an internet connection and a real audio file.

## Running

```powershell
cd app
..\venv\Scripts\python.exe main.py
```

## Building the distributable `.exe`

Not yet done in this repo (no `.spec` file, `pyinstaller` not yet installed). The plan: `pyinstaller --onefile --windowed` bundling `app/ffmpeg/`, `app/pretrained_models/`, and spleeter's `resources/*.json` as data files, with `app/main.py` as the entry point. See `CLAUDE.md` for the architecture notes a build needs to account for (env var ordering, the `pythonw` stdout fix, `multiprocess=False`).

## Notes

- Only the instrumental/background track is kept; the isolated vocals stem is discarded after separation.
- First run needs internet access (to fetch the model, if not already bundled) — after that, works fully offline.
