"""Bug class guidance shown to models in the detect prompt.

Each chain defines its own classes, but every chain labels by the same
principle, so labels mean the same thing across benchmarks. A chain writes a
one-line definition per class (with any "even if ..." tie-break built in) and
renders them with class_guide() inside its detect answer format.
"""

from __future__ import annotations

LABEL_PRINCIPLE = (
    "Label the cause, not the consequence: name the class of the check that is missing or "
    "wrong, not the harm it allows (stolen funds, someone gaining control). When two classes "
    "seem to fit, the definitions below say which one applies."
)


def class_guide(definitions: dict[str, str]) -> str:
    """Markdown block: the labeling principle, then one line per class."""
    lines = [f"- `{key}`: {text}" for key, text in definitions.items()]
    return LABEL_PRINCIPLE + "\n\n" + "\n".join(lines)
