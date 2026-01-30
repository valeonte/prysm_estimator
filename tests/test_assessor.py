import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from assessor import (
    get_erigon_sync_status,
    get_prysm_sync_status,
    scan_logs,
    assess,
)


class TestGetErigonSyncStatus:

    @patch("assessor.requests.post")
    def test_fully_synced(self, mock_post: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": False}
        mock_post.return_value = mock_response

        result = get_erigon_sync_status()
        assert result == {"synced": True, "details": "Erigon fully synced"}
        mock_post.assert_called_once_with(
            "http://localhost:8545",
            json={
                "jsonrpc": "2.0",
                "method": "eth_syncing",
                "params": [],
                "id": 1,
            },
            timeout=10,
        )

    @patch("assessor.requests.post")
    def test_still_syncing(self, mock_post: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "currentBlock": "0x100",
                "highestBlock": "0x200",
                "stages": ["stage1", "stage2"],
            }
        }
        mock_post.return_value = mock_response

        result = get_erigon_sync_status()
        assert result == {
            "synced": False,
            "result": {
                "currentBlock": "0x100",
                "highestBlock": "0x200",
            },
        }

    @patch("assessor.requests.post")
    def test_connection_error(self, mock_post: MagicMock) -> None:
        mock_post.side_effect = ConnectionError("Connection refused")

        result = get_erigon_sync_status()
        assert result == {"error": "Connection refused"}

    @patch("assessor.requests.post")
    def test_result_none(self, mock_post: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": None}
        mock_post.return_value = mock_response

        result = get_erigon_sync_status()
        assert result == {"synced": True, "details": "Erigon fully synced"}


class TestGetPrysmSyncStatus:

    @patch("assessor.requests.get")
    def test_success(self, mock_get: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": {"head_slot": "123", "sync_distance": "456", "is_syncing": True}
        }
        mock_get.return_value = mock_response

        result = get_prysm_sync_status()
        assert result == {
            "head_slot": "123",
            "sync_distance": "456",
            "is_syncing": True,
        }
        mock_get.assert_called_once_with(
            "http://localhost:3500/eth/v1/node/syncing", timeout=120
        )

    @patch("assessor.requests.get")
    def test_connection_error(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = ConnectionError("Connection refused")

        result = get_prysm_sync_status()
        assert result == {"error": "Connection refused"}


class TestScanLogs:

    def test_missing_file(self, tmp_path: Path) -> None:
        result = scan_logs(tmp_path / "nonexistent.log", "WARN", "ERROR")
        assert result == {"missing": True}

    def test_counts_errors_and_warnings(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        # Note: split("\n") on trailing newline produces an extra empty element
        log_file.write_text(
            "INFO normal line\n"
            "level=error something broke\n"
            "INFO another normal line\n"
            "level=warning something suspicious\n"
            "level=warning another warning\n"
            "INFO all good\n",
            encoding="utf8",
        )

        result = scan_logs(log_file, "level=warning", "level=error")
        assert result["error_count"] == 1
        assert result["warning_count"] == 2
        assert result["total_count"] == 7  # 6 lines + 1 trailing empty from split
        assert result["error_rate"] == "14.29 %"
        assert result["warning_rate"] == "28.57 %"

    def test_no_errors_or_warnings(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        log_file.write_text("INFO all good\nINFO still good\n", encoding="utf8")

        result = scan_logs(log_file, "WARN", "ERROR")
        assert result["error_count"] == 0
        assert result["warning_count"] == 0
        assert result["total_count"] == 3  # 2 lines + 1 trailing empty from split
        assert result["error_rate"] == "0.00 %"
        assert result["warning_rate"] == "0.00 %"

    def test_erigon_keywords(self, tmp_path: Path) -> None:
        log_file = tmp_path / "erigon.log"
        log_file.write_text(
            "[INFO] normal\n[WARN] disk space\n[ERROR] crash\n[INFO] ok\n",
            encoding="utf8",
        )

        result = scan_logs(log_file, "[WARN]", "[ERROR]")
        assert result["error_count"] == 1
        assert result["warning_count"] == 1
        assert result["total_count"] == 5  # 4 lines + 1 trailing empty from split


class TestAssess:

    @patch("assessor.get_prysm_sync_status")
    @patch("assessor.get_erigon_sync_status")
    def test_assess_prints_output(
        self,
        mock_erigon: MagicMock,
        mock_prysm: MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_erigon.return_value = {"synced": True, "details": "Erigon fully synced"}
        mock_prysm.return_value = {"head_slot": "123", "is_syncing": False}

        prysm_log = tmp_path / "prysm.log"
        prysm_log.write_text(
            "level=error bad\nlevel=warning meh\nINFO ok\n", encoding="utf8"
        )
        erigon_log = tmp_path / "erigon.log"
        erigon_log.write_text("[ERROR] bad\n[WARN] meh\nINFO ok\n", encoding="utf8")

        assess(erigon_log, prysm_log)

        captured = capsys.readouterr()
        assert "Checking Erigon sync status" in captured.out
        assert "Checking Prysm sync status" in captured.out
        assert "Scanning Prysm logs" in captured.out
        assert "Scanning Erigon logs" in captured.out
        assert "Erigon fully synced" in captured.out
        assert '"error_count": 1' in captured.out

    @patch("assessor.get_prysm_sync_status")
    @patch("assessor.get_erigon_sync_status")
    def test_assess_with_missing_logs(
        self,
        mock_erigon: MagicMock,
        mock_prysm: MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_erigon.return_value = {"synced": True, "details": "Erigon fully synced"}
        mock_prysm.return_value = {"head_slot": "123", "is_syncing": False}

        assess(tmp_path / "erigon.log", tmp_path / "prysm.log")

        captured = capsys.readouterr()
        assert '"missing": true' in captured.out
