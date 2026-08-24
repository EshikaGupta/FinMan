from typing import List

class PIIMatch:
    def __init__(
        self,
        entity_type: str,
        start: int,
        end: int,
        value: str,
        score: float = 1.0,
    ):
        self.entity_type = entity_type
        self.start = start
        self.end = end
        self.value = value
        self.score = score

    def __repr__(self):
        return (
            f"PIIMatch("
            f"type={self.entity_type!r}, "
            f"start={self.start}, "
            f"end={self.end}, "
            f"value={self.value}, "
            f"score={self.score}"
            f")"
        )

class RedactionResult:
    def __init__(
        self,
        text: str,
        matches: List[PIIMatch],
    ):
        self.text = text
        self.matches = matches