from dataclasses import dataclass, field
from typing import Dict, Any
@dataclass
class BotState:
    last: Dict[str, Any] = field(default_factory=dict)
