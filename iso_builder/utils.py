from typing import Sequence


def human_size(num: int) -> str:
    value = float(num)
    for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
        if value < 1024 or unit == "PB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{num} B"


def quote_cmd(parts: Sequence[str]) -> str:
    def q(item: str) -> str:
        item = str(item)
        if not item:
            return '""'
        if any(ch.isspace() for ch in item) or any(ch in item for ch in ['"', "'", "&", "(", ")"]):
            return '"' + item.replace('"', '\\"') + '"'
        return item

    return " ".join(q(p) for p in parts)
