"""Display state is independent from scientific analysis configuration."""

from dataclasses import asdict, dataclass, field
import math
from .types import ValidationError


@dataclass
class ViewConfig:
    """Validated display settings, separate from numerical analysis.

    style: ballstick/envelope/parcels (legacy skeleton maps to ballstick).
    theme: paper/midnight. layer: graph/hypergraph/both. opacity is in [0,1].
    labels and only_selected are booleans. selection is None or a dictionary
    with kind node/edge/hyperedge and a stable string id. camera holds optional
    position/target/up 3-vectors. schema_version must be 1. Invalid settings
    raise ValidationError; defaults are listed in the generated signature.
    """
    style: str = "ballstick"
    theme: str = "paper"
    layer: str = "graph"
    opacity: float = 0.2
    labels: bool = False
    only_selected: bool = False
    selection: dict | None = None
    camera: dict = field(default_factory=dict)
    schema_version: int = 1

    def __post_init__(self):
        # Legacy views keep their camera, selection and data while using the unified style.
        if self.style == "skeleton":
            self.style = "ballstick"
        if self.style not in {"ballstick", "envelope", "parcels"}:
            raise ValidationError("Unknown visualization style.")
        if self.theme not in {"midnight", "paper"} or self.layer not in {"graph", "hypergraph", "both"}:
            raise ValidationError("Unknown theme or structural layer.")
        if (
            isinstance(self.opacity, bool)
            or not isinstance(self.opacity, (float, int))
            or not 0 <= self.opacity <= 1
        ):
            raise ValidationError("Brain opacity must be in [0, 1].")
        if not isinstance(self.labels, bool) or not isinstance(self.only_selected, bool):
            raise ValidationError("Display toggles must be boolean.")
        if self.schema_version != 1:
            raise ValidationError("Unsupported view schema.")
        if self.selection is not None:
            if (
                not isinstance(self.selection, dict)
                or self.selection.get("kind") not in {"node", "edge", "hyperedge"}
                or not isinstance(self.selection.get("id"), str)
            ):
                raise ValidationError("Selection requires kind and a stable string ID.")
        if not isinstance(self.camera, dict) or set(self.camera) - {"position", "target", "up"}:
            raise ValidationError("Invalid camera state.")
        for vector in self.camera.values():
            if (
                not isinstance(vector, list)
                or len(vector) != 3
                or any(
                    isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x)
                    for x in vector
                )
            ):
                raise ValidationError("Camera vectors must contain three finite numbers.")
        if self.camera.get("up") == [0, 0, 0]:
            raise ValidationError("Camera up vector cannot be zero.")
        if (
            "position" in self.camera
            and "target" in self.camera
            and self.camera["position"] == self.camera["target"]
        ):
            raise ValidationError("Camera position and target must differ.")

    def to_dict(self):
        """Return a new serializable display-state dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        """Construct validated display state; unknown fields/settings raise ValidationError."""
        try:
            return cls(**value)
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"Invalid view settings: {exc}") from exc
