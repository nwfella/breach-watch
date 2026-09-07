import json
from pathlib import Path


class Store:
    """JSONL event archive + JSON state (per-source seen sets / cursors)."""

    def __init__(self, data_dir: Path):
        self.dir = Path(data_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.events_path = self.dir / 'events.jsonl'
        self.state_path = self.dir / 'state.json'
        self.state = self._load_state()

    def _load_state(self) -> dict:
        if self.state_path.exists():
            try:
                return json.loads(self.state_path.read_text(encoding='utf-8'))
            except Exception:
                pass
        return {}

    def save_state(self) -> None:
        self.state_path.write_text(json.dumps(self.state, indent=2), encoding='utf-8')

    def append_events(self, events: list) -> None:
        if not events:
            return
        lines = [json.dumps(e, ensure_ascii=False) for e in events]
        with open(self.events_path, 'a', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n')
