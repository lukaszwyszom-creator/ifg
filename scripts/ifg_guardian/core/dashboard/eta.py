from __future__ import annotations


def estimate_eta_seconds(*, elapsed_seconds: int, step: int, total: int) -> int | None:
    if elapsed_seconds <= 0 or step <= 0 or total <= 0 or step >= total:
        return None
    rate = elapsed_seconds / step
    remaining_steps = total - step
    return max(0, int(rate * remaining_steps))


def format_duration(seconds: int) -> str:
    total = max(0, int(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours:02d}h {minutes:02d}m {secs:02d}s"
    return f"{minutes:02d}m {secs:02d}s"
