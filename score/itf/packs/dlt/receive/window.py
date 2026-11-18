"""Original DLT window API; process lifecycle and record searching are shared."""

import logging
import os
import sys
import tempfile
import time

from .process import DltReceive, Protocol

logger = logging.getLogger(__name__)


class Bunch:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __repr__(self):
        return str(self.__dict__)

    __str__ = __repr__

    def get(self, *args, **kwargs):
        return self.__dict__.get(*args, **kwargs)

    def update(self, **kwargs):
        self.__dict__.update(kwargs)


def _normalize_timestamp_precision(epoch_time):
    try:
        seconds, microseconds = str(epoch_time).split(".")
        if len(microseconds) < 6:
            microseconds = microseconds.rjust(6, "0")
    except Exception as error:
        logger.error(f"Error normalizing timestamp precision: {error}")
    return f"{seconds}.{microseconds}"


class DltLogRecord:
    _clock = staticmethod(lambda: time.time())

    def __init__(self, file_name: str, filters=None):
        import dlt.dlt as python_dlt

        self._file_name = file_name
        self._content = python_dlt.load(file_name, filters=filters)
        self._queried = 0

    @staticmethod
    def _convert(msg):
        payload = msg.payload_decoded
        if isinstance(payload, bytes):
            payload = payload.decode(errors="ignore")
        return Bunch(
            time_stamp=msg.tmsp,
            apid=msg.apid,
            ctid=msg.ctid,
            payload=payload,
            raw_msg=msg,
            epoch_time=_normalize_timestamp_precision(msg.storage_timestamp),
        )

    def find(
        self,
        query: dict | None = None,
        include_ext: bool = True,
        include_non_ext: bool = False,
        full_match: bool = True,
        timeout: float | None = None,
    ) -> list[Bunch]:
        if not include_ext and not include_non_ext:
            logger.warning("Both 'include_ext' and 'include_non_ext' flags are set to False: empty search space!")
            return []
        self._queried, result, started = 0, [], self._clock()
        try:
            if os.path.getsize(self._file_name) == 0:
                return result
        except FileNotFoundError:
            pass
        for raw in self._content:
            if raw.use_extended_header and not include_ext or not raw.use_extended_header and not include_non_ext:
                continue
            self._queried += 1
            if not query or raw.compare(query):
                result.append(self._convert(raw))
                if not full_match:
                    break
            if timeout is not None and self._clock() - started >= timeout:
                logger.debug("[DLT Window]: find function exceeded timeout set!")
                break
        return result

    def total_count(self) -> int:
        return self._content.counter_total

    def filtered_count(self) -> int:
        return self._content.counter

    def queried_count(self) -> int:
        return self._queried


class DltWindow(DltReceive):
    def __init__(
        self,
        protocol: Protocol = Protocol.UDP,
        host_ip: str = None,
        multicast_ips: list[str] = None,
        target_ip: str = None,
        file_name: str = None,
        print_to_stdout: bool = False,
        logger_name: str = None,
        dlt_filter: str = None,
        binary_path: str = None,
    ):
        self._protocol = protocol
        self._multicast_ips = tuple(multicast_ips or ())
        if not file_name:
            handle, file_name = tempfile.mkstemp()
            os.close(handle)
        super().__init__(
            protocol,
            host_ip,
            multicast_ips,
            target_ip,
            file_name,
            False,
            print_to_stdout,
            logger_name or "dlt_receive_window",
            binary_path,
        )
        self._file_name = file_name
        self._args = ["-o", file_name, *self._args]
        if print_to_stdout:
            self._args.append("--stdout-flush")
        self._filter_file = None
        if dlt_filter:
            handle, self._filter_file = tempfile.mkstemp()
            with os.fdopen(handle, "w") as filter_file:
                filter_file.write(f"{dlt_filter}\n\n")
            self._args += ["-f", self._filter_file]
        self._captured_logs = []
        self._initialize_log_capture(self._logger_name)

    def _initialize_log_capture(self, logger_name):
        self._logger = logging.getLogger(logger_name)
        self._log_handler = logging.Handler()
        self._log_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        self._log_handler.emit = lambda record: self._captured_logs.append(self._log_handler.format(record))
        self._logger.addHandler(self._log_handler)
        self._logger.setLevel(logging.DEBUG)

    def start(self):
        self._start()

    def stop(self):
        self._stop(None, None, None)

    def _start(self):
        try:
            super().__enter__()
        except BaseException:
            exception_info = sys.exc_info()
            try:
                if self.process is not None:
                    super().__exit__(*exception_info)
            except BaseException:
                logger.exception("Failed to stop dlt-receive after startup failure")
            try:
                self._cleanup()
            except BaseException:
                logger.exception("Failed to clean up DLT window after startup failure")
            raise

    def __enter__(self):
        self._start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._stop(exc_type, exc_val, exc_tb)

    def _stop(self, exc_type, exc_val, exc_tb):
        try:
            super().__exit__(exc_type, exc_val, exc_tb)
        finally:
            self._cleanup()

    def _cleanup(self):
        try:
            if self._filter_file and os.path.exists(self._filter_file):
                os.remove(self._filter_file)
        finally:
            self._logger.removeHandler(self._log_handler)
            self._captured_logs.clear()

    def record(self, filters=None):
        return DltLogRecord(self._file_name, filters)

    def get_logged_output(self, clear_after_read=False):
        logs = "\n".join(self._captured_logs)
        if clear_after_read:
            self._captured_logs.clear()
        return logs

    def get_captured_logs(self):
        return self._captured_logs
