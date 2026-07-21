"""공유 테스트 픽스처 — schema/*.json 검증용 로더(design/20 Phase 0·2가 여러 스키마 파일을 참조)."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from referencing import Registry, Resource

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schema"


def load_schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def schema_registry() -> Registry:
    names = ["envelope.schema.json", "market.schema.json", "ta_preview.schema.json"]
    resources = [(s["$id"], Resource.from_contents(s)) for s in (load_schema(n) for n in names)]
    return Registry().with_resources(resources)


def validator_for(schema_name: str, registry: Registry) -> jsonschema.Draft202012Validator:
    return jsonschema.Draft202012Validator(load_schema(schema_name), registry=registry)
