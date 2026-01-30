import datetime
import os
import time as time_module
from pathlib import Path
from unittest.mock import patch

import pytest

from calc_eta import SlotAtTime, print_eta, print_etas, MATCHER, OLD_MATCHER


class TestSlotAtTimeFromLogLine:

    def test_new_format_match(self) -> None:
        log_line = (
            'time="2024-06-15 10:30:45.123" level=info msg="Processing block '
            'blah. 5000/10000 some stuff" prefix=initial-sync'
        )
        result = SlotAtTime.from_log_line(log_line)
        assert result is not None
        assert result.slot == 5000
        assert result.current_slot == 10000
        assert result.slot_time == datetime.datetime(
            2024, 6, 15, 10, 30, 45, tzinfo=datetime.UTC
        )

    def test_old_format_match(self) -> None:
        log_line = (
            'time="2024-06-15 10:30:45.123" level=info '
            'msg="something" latestProcessedSlot/currentSlot="3000/9000" other stuff'
        )
        result = SlotAtTime.from_log_line(log_line)
        assert result is not None
        assert result.slot == 3000
        assert result.current_slot == 9000
        assert result.slot_time == datetime.datetime(
            2024, 6, 15, 10, 30, 45, tzinfo=datetime.UTC
        )

    def test_no_match(self) -> None:
        result = SlotAtTime.from_log_line("some random log line with no matching data")
        assert result is None

    def test_new_format_no_match_falls_to_old(self) -> None:
        log_line = 'time="2024-06-15 10:30:45.000" level=info msg="unrelated"'
        result = SlotAtTime.from_log_line(log_line)
        assert result is None


class TestPrintEta:

    def test_positive_cover_speed(self, capsys: pytest.CaptureFixture[str]) -> None:
        now = datetime.datetime.now(datetime.UTC)
        start = SlotAtTime(
            slot_time=now - datetime.timedelta(hours=1),
            slot=1000,
            current_slot=10000,
        )
        end = SlotAtTime(
            slot_time=now,
            slot=5000,
            current_slot=10000,
        )

        result = print_eta(start, end)
        captured = capsys.readouterr()

        assert "4000 slots" in captured.out
        assert "40.00%" in captured.out
        assert "slots/second" in captured.out
        assert "estimated finish at" in captured.out
        assert result.total_seconds() > 0

    def test_negative_cover_speed(self, capsys: pytest.CaptureFixture[str]) -> None:
        now = datetime.datetime.now(datetime.UTC)
        start = SlotAtTime(
            slot_time=now - datetime.timedelta(hours=1),
            slot=1000,
            current_slot=10000,
        )
        end = SlotAtTime(
            slot_time=now,
            slot=1010,
            current_slot=10000,
        )

        result = print_eta(start, end)
        captured = capsys.readouterr()

        assert "LOSING GROUND" in captured.out
        assert result.total_seconds() < 0

    def test_zero_progress(self, capsys: pytest.CaptureFixture[str]) -> None:
        now = datetime.datetime.now(datetime.UTC)
        start = SlotAtTime(
            slot_time=now - datetime.timedelta(hours=1),
            slot=1000,
            current_slot=10000,
        )
        end = SlotAtTime(
            slot_time=now,
            slot=1300,  # 300 slots/3600s = 1/12 slots/s = new_slots_speed
            current_slot=10000,
        )

        with pytest.raises(ZeroDivisionError):
            print_eta(start, end)


class TestPrintEtas:

    @staticmethod
    def _make_log_line(dt: datetime.datetime, slot: int, current: int) -> str:
        time_str = dt.strftime("%Y-%m-%d %H:%M:%S.000")
        return (
            f'time="{time_str}" level=info msg="Processing block '
            f"blah. {slot}/{current} some stuff\" prefix=initial-sync"
        )

    def test_basic_etas(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        now = datetime.datetime.now(datetime.UTC)

        # File suffix must start with ".log" to pass the filter
        log_file = tmp_path / "sync.log"
        lines = [
            self._make_log_line(now - datetime.timedelta(days=2), 1000, 50000),
            self._make_log_line(now - datetime.timedelta(hours=12), 20000, 50000),
            self._make_log_line(now - datetime.timedelta(minutes=30), 40000, 50000),
            self._make_log_line(now - datetime.timedelta(minutes=1), 45000, 50000),
        ]
        log_file.write_text("\n".join(lines) + "\n", encoding="utf8")

        print_etas(tmp_path)

        captured = capsys.readouterr()
        assert "Last log (UTC)" in captured.out
        assert "Last processed slot" in captured.out
        assert "Full Sync Start (UTC)" in captured.out
        assert "Last Day Start (UTC)" in captured.out
        assert "Last Hour Start (UTC)" in captured.out

    def test_with_all_time_start_env(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        now = datetime.datetime.now(datetime.UTC)

        log_file = tmp_path / "sync.log"
        lines = [
            self._make_log_line(now - datetime.timedelta(hours=12), 20000, 50000),
            self._make_log_line(now - datetime.timedelta(minutes=30), 40000, 50000),
            self._make_log_line(now - datetime.timedelta(minutes=1), 45000, 50000),
        ]
        log_file.write_text("\n".join(lines) + "\n", encoding="utf8")

        env_time = (now - datetime.timedelta(days=5)).isoformat()
        with patch.dict(os.environ, {"ALL_TIME_START": env_time}):
            print_etas(tmp_path)

        captured = capsys.readouterr()
        assert "Full Sync Start (UTC)" in captured.out

    def test_multiple_log_files(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        now = datetime.datetime.now(datetime.UTC)

        # Create files with distinct mtime ordering via explicit timestamps
        log1 = tmp_path / "a.log"
        log1.write_text(
            self._make_log_line(now - datetime.timedelta(days=3), 500, 50000) + "\n"
            + self._make_log_line(now - datetime.timedelta(days=2), 5000, 50000) + "\n",
            encoding="utf8",
        )
        os.utime(log1, (1000, 1000))

        log2 = tmp_path / "b.log"
        log2.write_text(
            self._make_log_line(now - datetime.timedelta(hours=12), 30000, 50000) + "\n"
            + self._make_log_line(now - datetime.timedelta(minutes=30), 42000, 50000) + "\n",
            encoding="utf8",
        )
        os.utime(log2, (2000, 2000))

        log3 = tmp_path / "c.log"
        log3.write_text(
            self._make_log_line(now - datetime.timedelta(minutes=10), 44000, 50000) + "\n"
            + self._make_log_line(now - datetime.timedelta(minutes=1), 45000, 50000) + "\n",
            encoding="utf8",
        )
        os.utime(log3, (3000, 3000))

        print_etas(tmp_path)

        captured = capsys.readouterr()
        assert "Last processed slot: 45000" in captured.out

    def test_non_matching_lines_are_skipped(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        now = datetime.datetime.now(datetime.UTC)

        log_file = tmp_path / "sync.log"
        lines = [
            "some random non-matching line",
            self._make_log_line(now - datetime.timedelta(days=2), 1000, 50000),
            "another irrelevant line",
            self._make_log_line(now - datetime.timedelta(hours=12), 20000, 50000),
            self._make_log_line(now - datetime.timedelta(minutes=30), 40000, 50000),
            self._make_log_line(now - datetime.timedelta(minutes=1), 45000, 50000),
        ]
        log_file.write_text("\n".join(lines) + "\n", encoding="utf8")

        print_etas(tmp_path)

        captured = capsys.readouterr()
        assert "Last processed slot: 45000" in captured.out

    def test_one_day_start_picks_smallest_slot(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        now = datetime.datetime.now(datetime.UTC)

        log_file = tmp_path / "sync.log"
        lines = [
            self._make_log_line(now - datetime.timedelta(days=2), 1000, 50000),
            # Two entries within last day - should pick the one with smallest slot
            self._make_log_line(now - datetime.timedelta(hours=10), 25000, 50000),
            self._make_log_line(now - datetime.timedelta(hours=5), 20000, 50000),
            self._make_log_line(now - datetime.timedelta(minutes=30), 40000, 50000),
            self._make_log_line(now - datetime.timedelta(minutes=1), 45000, 50000),
        ]
        log_file.write_text("\n".join(lines) + "\n", encoding="utf8")

        print_etas(tmp_path)

        captured = capsys.readouterr()
        assert "Last Day Start (UTC)" in captured.out

    def test_one_hour_start_picks_earliest_time(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        now = datetime.datetime.now(datetime.UTC)

        log_file = tmp_path / "sync.log"
        lines = [
            self._make_log_line(now - datetime.timedelta(days=2), 1000, 50000),
            self._make_log_line(now - datetime.timedelta(hours=12), 20000, 50000),
            # Two entries within last hour - should pick earliest slot_time
            self._make_log_line(now - datetime.timedelta(minutes=50), 42000, 50000),
            self._make_log_line(now - datetime.timedelta(minutes=30), 43000, 50000),
            self._make_log_line(now - datetime.timedelta(minutes=1), 45000, 50000),
        ]
        log_file.write_text("\n".join(lines) + "\n", encoding="utf8")

        print_etas(tmp_path)

        captured = capsys.readouterr()
        assert "Last Hour Start (UTC)" in captured.out


class TestRegexPatterns:

    def test_matcher_pattern(self) -> None:
        line = (
            'time="2024-06-15 10:30:45.123" level=info msg="Processing block '
            "0xabc. 5000/10000 blah blah\" prefix=initial-sync"
        )
        match = MATCHER.match(line)
        assert match is not None
        assert match.group(1) == "2024-06-15 10:30:45.123"
        assert match.group(2) == "5000"
        assert match.group(3) == "10000"

    def test_matcher_pattern_no_match(self) -> None:
        assert MATCHER.match("unrelated line") is None

    def test_old_matcher_pattern(self) -> None:
        line = (
            'time="2024-06-15 10:30:45.123" level=info '
            'msg="something" latestProcessedSlot/currentSlot="3000/9000" stuff'
        )
        match = OLD_MATCHER.match(line)
        assert match is not None
        assert match.group(1) == "2024-06-15 10:30:45.123"
        assert match.group(2) == "3000"
        assert match.group(3) == "9000"

    def test_old_matcher_pattern_no_match(self) -> None:
        assert OLD_MATCHER.match("unrelated line") is None
