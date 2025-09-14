import datetime
import sys
import re

from pathlib import Path
from dataclasses import dataclass
from typing import Optional


MATCHER = re.compile(r'^time="([\d\-\:\s]+)" level.*latestProcessedSlot\/currentSlot="(\d+)\/(\d+)".*$')


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
    current_progressed = end.current_slot - start.current_slot

    current_per_second = current_progressed / seconds_processed
    slots_per_second_processed = slots_processed / seconds_processed

    # We calculate the straight forward estimate first
    estimate_1_seconds = (end.current_slot - end.slot)/slots_per_second_processed

    # Then we estimate how much the slots will have progressed in the meantime
    current_progress_in_estimate = current_per_second * estimate_1_seconds

    # And calculate a more accurate estimate
    estimate_2_seconds = (end.current_slot + current_progress_in_estimate - end.slot)/slots_per_second_processed

    print(f"{slots_processed} slots processed in {datetime.timedelta(seconds=seconds_processed)}, "
          f"aka {slots_per_second_processed:.1f} slots/second, "
          f"estimated finish at {now + datetime.timedelta(seconds=estimate_2_seconds):%Y-%m-%d %H:%M}")
    return datetime.timedelta(seconds=estimate_2_seconds)


def print_etas(logs_folder: str) -> None:
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
    time_format = "%Y-%m-%d %H:%m"
    assert all_end is not None
    print("Last log (UTC):", all_end.slot_time.strftime(time_format))
    print()

    assert all_time_start is not None
    print("All time start (UTC):", all_time_start.slot_time.strftime(time_format))
    print_eta(all_time_start, all_end)
    print()

    assert one_day_start is not None
    print("One day start (UTC):", one_day_start.slot_time.strftime(time_format))
    print_eta(one_day_start, all_end)
    print()

    assert one_hour_start is not None
    print("One hour start (UTC):", one_hour_start.slot_time.strftime(time_format))
    print_eta(one_hour_start, all_end)


if __name__ == "__main__":

    logs_folder = sys.argv[1] if len(sys.argv) > 1 else r"D:\scratch"

    print_etas(logs_folder)
