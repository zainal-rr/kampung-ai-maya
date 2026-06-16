from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ArtisanMakerTemplatePlan:
    template_id: str
    title: str
    reason: str
    parameters: dict[str, float | str]

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ArtisanMakerResult:
    passed: bool
    summary: str
    issues: list[str]
    warnings: list[str]
    checks: list[str]
    source_scripts: list[str]
    blend_files: list[str]
    mesh_files: list[str]
    readme_files: list[str]
    preview_files: list[str]
    dimensions_mm: dict[str, list[float]]

    def as_dict(self) -> dict:
        return asdict(self)
