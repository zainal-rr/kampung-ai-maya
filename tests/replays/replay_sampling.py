from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Iterable
from typing import TypeVar

T = TypeVar("T")


def stratified_limit(items: Iterable[T], limit: int | None, key: Callable[[T], str]) -> list[T]:
    all_items = list(items)
    if limit is None or limit >= len(all_items):
        return all_items
    if limit <= 0:
        return []
    groups: OrderedDict[str, list[tuple[int, T]]] = OrderedDict()
    for index, item in enumerate(all_items):
        groups.setdefault(key(item), []).append((index, item))
    selected: list[tuple[int, T]] = []
    offset = 0
    while len(selected) < limit:
        added = False
        for group_name in sorted(groups):
            bucket = groups[group_name]
            if offset < len(bucket):
                selected.append(bucket[offset])
                added = True
                if len(selected) >= limit:
                    break
        if not added:
            break
        offset += 1
    return [item for _index, item in sorted(selected, key=lambda pair: pair[0])]


def coverage_text(items: Iterable[T], key: Callable[[T], str]) -> str:
    counts: dict[str, int] = {}
    for item in items:
        group = key(item)
        counts[group] = counts.get(group, 0) + 1
    return ", ".join(f"{name}={counts[name]}" for name in sorted(counts))
