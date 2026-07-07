def runs(sorted_ints: list[int]) -> list[tuple[int, int]]:
    """ソート済み整数列を連続ラン (start, end) のリストに分割する。"""
    if not sorted_ints:
        return []
    out: list[tuple[int, int]] = []
    start = prev = sorted_ints[0]
    for n in sorted_ints[1:]:
        if n == prev + 1:
            prev = n
            continue
        out.append((start, prev))
        start = prev = n
    out.append((start, prev))
    return out
