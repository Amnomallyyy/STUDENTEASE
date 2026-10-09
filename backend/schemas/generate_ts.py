"""Generate frontend/src/types/profile.ts from the Pydantic models, so the two sides cannot drift.

    python -m backend.schemas.generate_ts          write the file
    python -m backend.schemas.generate_ts --check  exit 1 if the file is out of date (for CI)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from backend import schemas

OUTPUT = Path(__file__).resolve().parents[2] / "frontend" / "src" / "types" / "profile.ts"
HEADER = (
    "// AUTO-GENERATED from backend/schemas by `python -m backend.schemas.generate_ts`.\n"
    "// Do not edit by hand: change the Pydantic models and regenerate.\n"
)


def ts_type(schema: dict[str, Any]) -> str:
    if "$ref" in schema:
        return schema["$ref"].rsplit("/", 1)[-1]
    if "const" in schema:
        return json.dumps(schema["const"])
    if "enum" in schema:
        return " | ".join(json.dumps(v) for v in schema["enum"])
    if "anyOf" in schema:
        return " | ".join(dict.fromkeys(ts_type(s) for s in schema["anyOf"]))
    kind = schema.get("type")
    if kind == "string":
        return "string"
    if kind in ("integer", "number"):
        return "number"
    if kind == "boolean":
        return "boolean"
    if kind == "null":
        return "null"
    if kind == "array":
        inner = ts_type(schema.get("items", {}))
        return f"({inner})[]" if " | " in inner else f"{inner}[]"
    if kind == "object":
        extra = schema.get("additionalProperties")
        return f"Record<string, {ts_type(extra)}>" if isinstance(extra, dict) else "Record<string, unknown>"
    return "unknown"


def render(name: str, schema: dict[str, Any], required: set[str] | None = None) -> str:
    """An enum becomes a union type; a model becomes an interface.

    `required=None` marks every property required: the API serialises all fields, defaults included.
    Pass a set to mark only those properties required (used for request bodies).
    """
    if "enum" in schema:
        return f"export type {name} = {ts_type(schema)};"
    lines = [f"export interface {name} {{"]
    for prop, spec in schema.get("properties", {}).items():
        optional = "" if required is None or prop in required else "?"
        lines.append(f"  {prop}{optional}: {ts_type(spec)};")
    lines.append("}")
    return "\n".join(lines)


# Request bodies the front end builds by hand: fields with defaults are optional there.
REQUEST_MODELS = {"ProfilePatch", "ChatRequest"}


def generate() -> str:
    """TypeScript for every Pydantic model exported by backend.schemas, plus the enums they use."""
    declarations: dict[str, str] = {}
    for name in schemas.__all__:
        obj = getattr(schemas, name)
        if not (isinstance(obj, type) and issubclass(obj, BaseModel)):
            continue
        schema = obj.model_json_schema(mode="serialization")
        for def_name, def_schema in schema.pop("$defs", {}).items():
            declarations[def_name] = render(def_name, def_schema)
        required = None
        if obj.__name__ in REQUEST_MODELS:
            required = set(obj.model_json_schema(mode="validation").get("required", []))
        declarations[obj.__name__] = render(obj.__name__, schema, required)
    return HEADER + "\n" + "\n\n".join(declarations[key] for key in sorted(declarations)) + "\n"


def main(argv: list[str]) -> int:
    content = generate()
    if "--check" in argv:
        if not OUTPUT.is_file() or OUTPUT.read_text(encoding="utf-8").replace("\r\n", "\n") != content:
            print(f"{OUTPUT} is out of date. Run: python -m backend.schemas.generate_ts")
            return 1
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(content, encoding="utf-8", newline="\n")
    print(f"Wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
