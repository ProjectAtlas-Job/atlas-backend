from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.types import UserDefinedType


class Vector(UserDefinedType):
    cache_ok = True

    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions

    def get_col_spec(self, **_: object) -> str:
        return f"VECTOR({self.dimensions})"

    def bind_processor(self, dialect: object) -> object:
        del dialect

        def process(value: Sequence[float] | None) -> str | None:
            if value is None:
                return None
            if len(value) != self.dimensions:
                raise ValueError(f"Expected {self.dimensions} dimensions, got {len(value)}.")
            return "[" + ",".join(format(float(component), ".17g") for component in value) + "]"

        return process

    def result_processor(self, dialect: object, coltype: object) -> object:
        del dialect, coltype

        def process(value: str | None) -> list[float] | None:
            if value is None:
                return None
            stripped = value.strip()
            if not stripped:
                return []
            if stripped[0] == "[" and stripped[-1] == "]":
                stripped = stripped[1:-1]
            if not stripped:
                return []
            return [float(component) for component in stripped.split(",")]

        return process
