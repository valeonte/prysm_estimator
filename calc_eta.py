import datetime
import sys
import re

from pathlib import Path
from dataclasses import dataclass
from typing import Optional


MATCHER = re.compile(r'^time="([\d\-\:\s]+)" level.*latestProcessedSlot\/currentSlot="(\d+)\/(\d+)".*$')
GENESIS_TIME = datetime.datetime(2020, 12, 1, 12, 0, 23, tzinfo=datetime.UTC)


@dataclass
class SlotAtTime:

    slot_time: datetime.datetime
    slot: int
    current_slot: int

    @staticmethod
    def from_log_line(log_line: str) -> Optional["SlotAtTime"]:
        match = MATCHER.match(log_line)
        if match is None:
            return None

        log_time = datetime.datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.UTC)
        last_slot = int(match.group(2))
        cur_slot = int(match.group(3))

        return SlotAtTime(log_time, last_slot, cur_slot)


def print_eta(start: SlotAtTime, end: SlotAtTime) -> datetime.timedelta:
    now = datetime.datetime.now(datetime.UTC)
    slots_processed = end.slot - start.slot
    seconds_processed = (end.slot_time - start.slot_time).total_seconds()

    processed_speed = slots_processed / seconds_processed
    new_slots_speed = 1/12  # By design, 1 slot every 12 seconds

    # The actual speed is the difference between the calculating speed
    # and the speed of new slots being created.
    cover_speed = processed_speed - new_slots_speed
    estimate_seconds = (end.current_slot - end.slot)/cover_speed

    print(f"{slots_processed} slots ({100*slots_processed/end.current_slot:.2f}%) "
          f"processed in {datetime.timedelta(seconds=seconds_processed)}, "
          f"aka {processed_speed:.1f} slots/second, "
          f"estimated finish at {now + datetime.timedelta(seconds=estimate_seconds):%Y-%m-%d %H:%M}")
    return datetime.timedelta(seconds=estimate_seconds)


def print_etas(logs_folder: str | Path) -> None:
    now = datetime.datetime.now(datetime.UTC)
    start_of_day = now - datetime.timedelta(days=1)
    start_of_hour = now - datetime.timedelta(hours=1)

    all_time_start: SlotAtTime | None = None
    one_day_start: SlotAtTime | None = None
    one_hour_start: SlotAtTime | None = None
    all_end: SlotAtTime | None = None
    for log_file in Path(logs_folder).iterdir():
        if not log_file.suffix.lower().startswith(".log"):
            continue
        
        print("Parsing", log_file)
        for log_line in log_file.read_text("utf8").splitlines():
            
            slot = SlotAtTime.from_log_line(log_line)
            if slot is None:
                continue

            if all_time_start is None or slot.slot < all_time_start.slot:
                all_time_start = slot
            if all_end is None or slot.slot_time > all_end.slot_time:
                all_end = slot

            if  slot.slot_time >= start_of_day:
                if one_day_start is None or slot.slot < one_day_start.slot:
                    one_day_start = slot
            if slot.slot_time >= start_of_hour:
                if one_hour_start is None or slot.slot_time < one_hour_start.slot_time:
                    one_hour_start = slot

    print()
    time_format = "%Y-%m-%d %H:%M"
    assert all_end is not None
    print("Last log (UTC):", all_end.slot_time.strftime(time_format))
    print("Last processed slot:", all_end.slot, "/", GENESIS_TIME + datetime.timedelta(seconds=all_end.slot*12))
    print()

    assert all_time_start is not None
    print("Sync Start start (UTC):", all_time_start.slot_time.strftime(time_format))
    print_eta(all_time_start, all_end)
    print()

    assert one_day_start is not None
    print("Last Day Start (UTC):", one_day_start.slot_time.strftime(time_format))
    print_eta(one_day_start, all_end)
    print()

    assert one_hour_start is not None
    print("Last Hour start (UTC):", one_hour_start.slot_time.strftime(time_format))
    print_eta(one_hour_start, all_end)


if __name__ == "__main__":

    logs_folder = Path.home() /"logs" / "prysm_logs"

    print_etas(logs_folder)
