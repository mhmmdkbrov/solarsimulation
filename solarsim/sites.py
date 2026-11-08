"""Location presets. Every value here is an input that the user can change; nothing is Baku-specific in the model."""
from dataclasses import dataclass, field, asdict


@dataclass
class Site:
    key: str
    name: str                     # display name (Azerbaijani)
    latitude: float               # ° N
    longitude: float              # ° E
    tz: str                       # IANA time zone, used only for display / local-time aggregation
    tilt_deg: float               # fixed-mount tilt
    azimuth_deg: float = 180.0    # 180 = south (northern hemisphere)
    albedo: float = 0.20          # ground reflectance (assumption unless measured)
    elevation_m: float | None = None          # filled from the PVGIS response
    horizon: list[tuple[float, float]] | None = None   # [(azimuth°, elevation°)], filled from PVGIS printhorizon
    notes: str = ""
    status: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


# Tilt: PVGIS 5.3 optimal fixed tilt for each point (PVcalc optimalangles=1), see data/sites.json after `fetch`.
# Albedo 0.20 is a generic assumption for all presets.
PRESETS = {
    "baku": Site("baku", "Bakı", 40.41, 49.87, "Asia/Baku", tilt_deg=35.0,
                 notes="Bakı mərkəzi (v1 baza nöqtəsi; v1-də maililik 35° götürülüb)"),
    "naxcivan": Site("naxcivan", "Naxçıvan", 39.2089, 45.4122, "Asia/Baku", tilt_deg=35.0,
                     notes="Naxçıvan şəhəri, ~886 m hündürlük"),
    "almeria": Site("almeria", "Almería", 36.8381, -2.4597, "Europe/Madrid", tilt_deg=32.0,
                    notes="Almería (İspaniya), Avropanın ən günəşli bölgələrindən biri"),
}
