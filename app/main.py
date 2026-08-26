import multiprocessing
import sys

from common import configure_environment


def run_gui() -> None:
    from PyQt5.QtWidgets import QApplication

    from ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("Vocal Remover")
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    multiprocessing.freeze_support()
    configure_environment()

    if "--worker-job" in sys.argv:
        # Re-invocation as a one-shot separation worker (see core/separation_controller.py):
        # each "Process" click runs in its own fresh process, because spleeter's Separator
        # can only be instantiated once per process (see CLAUDE.md).
        import worker_main

        job_index = sys.argv.index("--worker-job")
        worker_main.run_job(sys.argv[job_index + 1])
    else:
        run_gui()
