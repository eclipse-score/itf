import pytest

from score.itf.packs.pcap.capture import TcpdumpCapture


def test_failed_capture_start_can_be_torn_down_without_a_second_failure(tmp_path):
    capture = TcpdumpCapture(
        {
            "interface": "lo",
            "out_dir": str(tmp_path),
            "binary_path": str(tmp_path / "missing-tcpdump"),
        }
    )
    with pytest.raises(FileNotFoundError):
        capture.start()
    capture.stop()
    assert not capture.running()
