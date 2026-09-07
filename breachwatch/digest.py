def render(events: list, header: str = '') -> str:
    if not events:
        return 'No new events.'
    groups = {}
    for e in events:
        groups.setdefault(e['source'], []).append(e)
    lines = [header or f'NEW EVENTS: {len(events)}']
    for src in sorted(groups):
        evs = groups[src]
        lines.append(f'-- {src} ({len(evs)})')
        for e in evs[:60]:
            rec = f' | {e["records"]:,} records' if e.get('records') else ''
            data = (', '.join(e['data_classes'][:5]) + ', ...') if len(e.get('data_classes') or []) > 5 else ', '.join(e.get('data_classes') or [])
            extra = f' | data: {data}' if data else ''
            lines.append(f'   [{e.get("region", "?")}] {e["title"][:120]}{rec}  ({e.get("date_published", "")})')
            lines.append(f'       {e["url"]}{extra}')
        if len(evs) > 60:
            lines.append(f'   ... +{len(evs) - 60} more')
    return '\n'.join(lines)
