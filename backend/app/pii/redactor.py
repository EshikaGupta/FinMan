from .detector import detect_pii
from .models import RedactionResult


class Redactor:

    def __init__(self):

        self.replacements = {}
        self.counters = {}

    def _get_replacement(
        self,
        entity_type,
        original,
    ):

        key = (
            entity_type,
            original.strip().lower(),
        )

        if key in self.replacements:
            return self.replacements[key]

        count = (
            self.counters.get(
                entity_type,
                0,
            )
            + 1
        )

        self.counters[
            entity_type
        ] = count

        replacement = (
            f"<PII:{entity_type}>"
            f"{entity_type}_{count}"
            f"</PII:{entity_type}>"
        )

        self.replacements[key] = replacement

        return replacement

    def replacement_for(
        self,
        entity_type,
        original,
    ):

        return self._get_replacement(
            entity_type,
            original,
        )

    def redact(
        self,
        text,
    ):

        matches = detect_pii(text)

        if not matches:

            return RedactionResult(
                text=text,
                matches=[],
            )

        output = []
        last_position = 0

        for match in matches:

            output.append(
                text[
                    last_position:
                    match.start
                ]
            )

            replacement = (
                self._get_replacement(
                    match.entity_type,
                    match.value,
                )
            )

            output.append(
                replacement
            )

            last_position = match.end

        output.append(
            text[last_position:]
        )

        return RedactionResult(
            text="".join(output),
            matches=matches,
        )