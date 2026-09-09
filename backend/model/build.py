"""Render the Modelfile for whoever this desk belongs to.

The Modelfile used to name one adviser and one FSP number in its SYSTEM block.
That is identity compiled into a build artefact — the same leak as an FSP
number in a prompt, with the extra problem that a model built from it carries
the identity inside its own weights' system message wherever the model goes.

So the file in the repository is a template with one placeholder, and the
identity is filled in at build time from the desk's own configuration. An
unconfigured desk builds a model belonging to "a South African financial
adviser", which is true, rather than to somebody who does not use it.

    python model/build.py                 # write model/Modelfile.built
    ollama create fortitudo -f model/Modelfile.built
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "Modelfile"
BUILT = HERE / "Modelfile.built"
PLACEHOLDER = "{{DESK_OWNER}}"


def owner_line() -> str:
    sys.path.insert(0, str(HERE.parent))
    from identity import load

    return load().licence_line or "a South African financial adviser"


def render() -> str:
    text = TEMPLATE.read_text(encoding="utf-8")
    if PLACEHOLDER not in text:
        raise SystemExit(f"{TEMPLATE} has no {PLACEHOLDER} to fill in")
    return text.replace(PLACEHOLDER, owner_line())


def main() -> None:
    BUILT.write_text(render(), encoding="utf-8")
    print(f"wrote {BUILT}")
    print(f"  desk owner: {owner_line()}")
    print(f"\n  ollama create fortitudo -f {BUILT}\n")


if __name__ == "__main__":
    main()
