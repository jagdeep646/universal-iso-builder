import threading
from typing import Any, Optional


class BuildCancelled(RuntimeError):
    """Raised inside the build worker after cancellation is requested."""


class BuildCancellation:
    """Thread-safe cancellation signal and active backend-process owner."""

    def __init__(self) -> None:
        self._event = threading.Event()
        self._lock = threading.Lock()
        self._process: Optional[Any] = None

    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled():
            raise BuildCancelled("Build cancelled by user.")

    def register_process(self, process: Any) -> None:
        with self._lock:
            self._process = process
            cancel_now = self._event.is_set()
        if cancel_now:
            self._stop_process(process, force=False)

    def clear_process(self, process: Any) -> None:
        with self._lock:
            if self._process is process:
                self._process = None

    def cancel(self, *, force: bool = False) -> None:
        self._event.set()
        with self._lock:
            process = self._process
        if process is not None:
            self._stop_process(process, force=force)

    @staticmethod
    def _stop_process(process: Any, *, force: bool) -> None:
        try:
            if process.poll() is not None:
                return
            if force:
                process.kill()
            else:
                process.terminate()
        except (OSError, ProcessLookupError):
            # The worker will re-check the cancellation event and will not
            # publish a final ISO even if the process exited concurrently.
            pass
