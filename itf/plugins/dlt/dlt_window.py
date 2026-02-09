# *******************************************************************************
# Copyright (c) 2025 Contributors to the Eclipse Foundation
#
# See the NOTICE file(s) distributed with this work for additional
# information regarding copyright ownership.
#
# This program and the accompanying materials are made available under the
# terms of the Apache License Version 2.0 which is available at
# https://www.apache.org/licenses/LICENSE-2.0
#
# SPDX-License-Identifier: Apache-2.0
# *******************************************************************************
import logging
import os
import tempfile
import time
import dlt.dlt as python_dlt

from itf.core.utils.bunch import Bunch
from itf.core.utils.process.process_wrapper import ProcessWrapper
from itf.plugins.dlt.dlt_receive import DltReceive, Protocol, protocol_arguments


logger = logging.getLogger(__name__)


class DltWindow(ProcessWrapper):
    """
    Save, filter and query DLT logs on demand from the provided target
    Logs by default are saved in the "/tmp" folder and thus will not be uploaded
    "protocol" can be either Protocol.TCP or Protocol.UDP

    dlt_filter -> create './filter.txt' file and add flag -f filter.txt to dlt-receive.
    This enabled filtering dlt messages. Example of usages:
    dlt = DltWindow(dlt_filter='EPTP LTCE')
    Where:
    EPTP -> Application ID
    LTCE -> Contex ID
    """

    # pylint: disable=too-many-instance-attributes
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
        """Initialize DltWindow with target IP, protocol, and optional parameters.

        :param Protocol protocol: Protocol to use for receiving DLT logs (TCP or UDP).
        :param str host_ip: IP address to bind to in case of UDP.
        :param list[str] multicast_ips: Multicast IPs to join to in case of UDP.
        :param str target_ip: IP address to connect to in case of TCP.
        :param str file_name: Path to the DLT file. Defaults to '/tmp/dlt_window.dlt'.
        :param bool print_to_stdout: If True, prints DLT messages to stdout.
        :param str logger_name: Name of the logger to use.
        :param bool clear_dlt: If True, clears the DLT file at initialization.
        :param str filter: Filter string for DLT messages.
        :param str binary_path: Path to the dlt-receive binary.
        """

        self._file_name = file_name
        if not self._file_name:
            with tempfile.NamedTemporaryFile(delete=False, delete_on_close=False) as file:
                self._file_name = file.name
        self._captured_logs = []

        logger_name = logger_name if logger_name else "dlt_receive_window"
        self._initialize_log_capture(logger_name)

        dlt_receive_args = ["-o", self._file_name]
        dlt_receive_args += protocol_arguments(protocol, host_ip, target_ip, multicast_ips)
        dlt_receive_args += ["-a", "--stdout-flush"] if print_to_stdout else []

        self._filter_file = None
        if dlt_filter:
            with tempfile.NamedTemporaryFile(mode="w", delete=False, delete_on_close=False) as file:
                self._filter_file = file.name
                file.write(f"{dlt_filter}\n\n")
            dlt_receive_args += ["-f", self._filter_file]

        super().__init__(
            binary_path,
            dlt_receive_args,
            logger_name=logger_name,
        )

    def start(self):
        self._start()

    def stop(self):
        self._stop(None, None, None)

    def record(self, filters=None):
        return DltLogRecord(self._file_name, filters)

    def file_name(self):
        return self._file_name

    def get_logged_output(self, clear_after_read=False):
        """Returns captured DLT logs as a single string.

        :param clear_after_read: If True, clears logs after reading. Defaults to True.
        :return: String containing all log lines.
        """
        logs = "\n".join(self._captured_logs)
        if clear_after_read:
            self._captured_logs.clear()
        return logs

    def get_captured_logs(self):
        return self._captured_logs

    def _initialize_log_capture(self, logger_name):
        self._logger = logging.getLogger(logger_name)
        self._log_handler = None
        if self._logger:
            self._log_handler = logging.Handler()

            def emit(record):
                log_entry = self._log_handler.format(record)
                self._captured_logs.append(log_entry)

            self._log_handler.emit = emit
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            self._log_handler.setFormatter(formatter)
            self._logger.addHandler(self._log_handler)
            self._logger.setLevel(logging.DEBUG)

    def __enter__(self):
        self._start()
        return self

    def _start(self):
        super().__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._stop(exc_type, exc_val, exc_tb)

    def _stop(self, exc_type, exc_val, exc_tb):
        super().__exit__(exc_type, exc_val, exc_tb)
        if self._filter_file and os.path.exists(self._filter_file):
            os.remove(self._filter_file)
        if self._logger and self._log_handler:
            self._logger.removeHandler(self._log_handler)
        self._captured_logs.clear()


class DltLogRecord:
    def __init__(self, file_name, filters=None):
        """Load and filter DLT messages from the recorded file

        :param str file_name: File with DLT logs
        :param list filters: List of filters to apply [("APPID", "CTID"), ...]
            [("", "")] : loads everything, same as filters=None
            [("Fasi", "")] : loads all messages with APPID="Fasi" and non extended ones
            [("Fasi", "mata")] : loads messages with APPID="Fasi" and CTID="mata", also all non extended ones
        """

        self._dlt_content = python_dlt.load(file_name, filters=filters)
        self._queried_counter = 0

    def find(self, query=None, include_ext=True, include_non_ext=False, full_match=True, timeout=None):
        """Find DLT messages matching the input query

        :param dict query: Dictionary with selected keys to compare with
            dict(apid=re.compile(r"^A.*"), ctid=b'ACOM') : messages which apid starting with "A" and CTID="ACOM"
            dict(payload_decoded=re.compile(r".connected.*")) : messages which payload contains "connected"
        :param bool include_ext: Include extended DLT messages during search. Set False to exclude them
        :param bool include_non_ext: Include non extended DLT messages during search. Set False to exclude them
        :param bool full_match: Find all DLT messages matching the query. Set False to return immediatly after first match
        :param bool timeout: If set, the check will be stopped if timeout exceeded
        :returns list: List of DLT messages matching the query. Each message is a Bunch object:
                            time_stamp float
                            apid, ctid, payload string
                            raw_msg DLTMessage object
                            epoch_time float
        """
        if not include_ext and not include_non_ext:
            logger.warning("Both 'include_ext' and 'include_non_ext' flags are set to False: empty search space!")
            return []

        self._queried_counter = 0
        result = []
        start_time = time.time()

        for msg in self._dlt_content:
            if not include_ext and msg.use_extended_header:
                continue

            if not include_non_ext and not msg.use_extended_header:
                continue

            self._queried_counter += 1

            if not query or msg.compare(query):
                payload = msg.payload_decoded
                if isinstance(payload, bytes):
                    payload = payload.decode(errors="ignore")

                normalized_time = _normalize_timestamp_precision(msg.storage_timestamp)
                result.append(
                    Bunch(
                        time_stamp=msg.tmsp,
                        apid=msg.apid,
                        ctid=msg.ctid,
                        payload=payload,
                        raw_msg=msg,
                        epoch_time=normalized_time,
                    )
                )

                if not full_match:
                    break

            if timeout is not None and time.time() - start_time >= timeout:
                logger.debug("[DLT Window]: find function exceeded timeout set!")
                break

        return result

    def total_count(self):
        """
        Total number of DLT messages recorded
        """
        return self._dlt_content.counter_total

    def filtered_count(self):
        """
        Number of relevant DLT messages according to the filters provided
        Includes all the non extended DLT messages
        """
        return self._dlt_content.counter

    def queried_count(self):
        """
        Number of relevant DLT messages according to the filters provided
        and after (optionally) discarding non extended or extended DLT messages
        """
        return self._queried_counter


def _normalize_timestamp_precision(epoch_time):
    try:
        time_str = str(epoch_time)
        seconds, microseconds = time_str.split(".")

        if len(microseconds) < 6:
            microseconds = microseconds.rjust(6, "0")

    except Exception as error:
        logger.error(f"Error normalizing timestamp precision: {error}")
    return f"{seconds}.{microseconds}"
