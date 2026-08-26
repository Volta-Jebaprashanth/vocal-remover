import json
import os
import shutil
import sys
import tempfile

from common import FRIENDLY_STEM_NAMES

EVENT_PREFIX = "JOBEVENT "


def emit(event: str, **kwargs) -> None:
    print(EVENT_PREFIX + json.dumps({"event": event, **kwargs}), flush=True)


def _unique_path(path: str) -> str:
    root, ext = os.path.splitext(path)
    counter = 1
    candidate = path
    while os.path.exists(candidate):
        candidate = f"{root}_{counter}{ext}"
        counter += 1
    return candidate


def run_job(job_path: str) -> None:
    """Handles exactly one input file. One process handles exactly one file (see
    core/separation_controller.py) so that a crash on a problematic file (typically
    an out-of-memory abort on a large stem count / long song) only fails that file
    instead of taking down an entire batch."""
    with open(job_path, "r", encoding="utf-8") as f:
        job = json.load(f)

    input_path = job["input_path"]
    output_dir = job["output_dir"]
    stem_mode = job["stem_mode"]
    fast = job["fast"]
    mwf = job["mwf"]
    output_format = job["output_format"]
    bitrate = job.get("bitrate")
    stems_to_keep = job["stems_to_keep"]
    filename = os.path.basename(input_path)

    try:
        from spleeter.separator import Separator

        descriptor = f"spleeter:{stem_mode}{'-16kHz' if fast else ''}"
        emit("status", text=f"Loading {stem_mode} model...")
        # multiprocess=False: avoids spawning extra child processes inside a
        # frozen/windowed exe (spleeter's own Pool-based path is fragile there).
        separator = Separator(descriptor, MWF=mwf, multiprocess=False)

        base_name = os.path.splitext(filename)[0]
        with tempfile.TemporaryDirectory(prefix="vocal_remover_") as tmp_dir:
            emit("status", text=f"Separating {filename}...")
            save_kwargs = {"codec": output_format}
            if output_format == "mp3" and bitrate:
                save_kwargs["bitrate"] = bitrate
            separator.separate_to_file(input_path, tmp_dir, **save_kwargs)

            stem_dir = os.path.join(tmp_dir, base_name)
            multi_stem = len(stems_to_keep) > 1
            dest_dir = os.path.join(output_dir, base_name) if multi_stem else output_dir
            os.makedirs(dest_dir, exist_ok=True)

            saved_paths = []
            for stem in stems_to_keep:
                src = os.path.join(stem_dir, f"{stem}.{output_format}")
                if not os.path.exists(src):
                    raise FileNotFoundError(f"Missing expected stem output: {stem}")
                friendly = FRIENDLY_STEM_NAMES.get(stem, stem).lower()
                dest_name = (
                    f"{friendly}.{output_format}"
                    if multi_stem
                    else f"{base_name}_{friendly}.{output_format}"
                )
                dest_path = _unique_path(os.path.join(dest_dir, dest_name))
                shutil.copyfile(src, dest_path)
                saved_paths.append(dest_path)

        emit("file_done", outputs=saved_paths)
    except Exception as exc:
        emit("file_failed", error=str(exc))


if __name__ == "__main__":
    from common import configure_environment

    configure_environment()
    if "--worker-job" not in sys.argv:
        emit("file_failed", error="worker_main invoked without --worker-job")
        sys.exit(1)
    job_index = sys.argv.index("--worker-job")
    run_job(sys.argv[job_index + 1])
