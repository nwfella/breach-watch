from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class BreachEvent:
    source: str          # collector id: hibp_api | hibp_rss | opc_news | cai_news | ca_doj
    external_id: str     # unique id within source (HIBP Name, URL, or row hash)
    url: str
    title: str           # organization / short title
    date_published: str  # ISO date (YYYY-MM-DD) the event became known
    date_breach: str = ''        # when the actual breach occurred, if reported
    records: int = 0             # number of affected records, if known
    data_classes: list = field(default_factory=list)
    description: str = ''
    region: str = 'unknown'      # ca | qc | us | global | unknown (qc = Quebec-specific)
    raw: dict = field(default_factory=dict)
    ingested_at: str = ''

    def __post_init__(self):
        if not self.ingested_at:
            self.ingested_at = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

    def to_dict(self) -> dict:
        return asdict(self)
