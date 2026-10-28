"""Validate an observed AssembledJointMass_1 payload. Pure: no I/O or ETABS.

A validated payload is not proof that native execution occurred. The caller must
supply and establish capture identity, provenance, units and API-read evidence.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import math

COMPONENTS = ("U1", "U2", "U3", "R1", "R2", "R3")
NAME_FIELDS = ("point_elements", "mass_sources")
ARRAY_FIELDS = NAME_FIELDS + COMPONENTS


class MassValidationError(ValueError):
    """A stable diagnostic code and a human-readable explanation."""
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


def _fail(code, message):
    raise MassValidationError(code, message)


def _number(value, label, *, nonnegative=False):
    # bool is not a numeric measurement; strict JSON-compatible scalar types.
    if type(value) not in (int, float):
        _fail("NUMBER_TYPE", f"{label} must be int/float, excluding bool")
    try:
        number = float(value)
    except (OverflowError, ValueError):
        _fail("NONFINITE", f"{label} cannot be represented as a finite float")
    if not math.isfinite(number):
        _fail("NONFINITE", f"{label} is not finite")
    if nonnegative and number < 0:
        _fail("NEGATIVE_MASS", f"{label} must be nonnegative; no clamping")
    return number


def _name(value, label):
    if type(value) is not str or not value or value != value.strip():
        _fail("IDENTITY", f"{label} must be a nonempty, unpadded string")
    return value


def _mapping(value, label):
    if not isinstance(value, Mapping):
        _fail("STRUCTURE", f"{label} must be a mapping")
    return value


def _field(mapping, key, label):
    if key not in mapping:
        _fail("MISSING_FIELD", f"{label}.{key} is required")
    return mapping[key]


def _triple(value, label):
    if type(value) not in (list, tuple) or len(value) != 3:
        _fail("VECTOR_LENGTH", f"{label} must contain exactly three numbers")
    return tuple(_number(v, f"{label}[{i}]") for i, v in enumerate(value))


def _sum(values, label):
    try:
        value = math.fsum(values)
    except (OverflowError, ValueError):
        _fail("NONFINITE_TOTAL", f"{label} overflowed")
    if not math.isfinite(value):
        _fail("NONFINITE_TOTAL", f"{label} is not finite")
    return value


@dataclass(frozen=True)
class MassRow:
    point_element: str
    mass_source: str
    global_xyz: tuple[float, float, float]
    point_axes_deg: tuple[float, float, float]
    components: tuple[float, float, float, float, float, float]


@dataclass(frozen=True)
class MassSummary:
    capture_id: str
    units: str
    source: str
    number_results: int
    rows: tuple[MassRow, ...]
    padded_fields: tuple[str, ...]
    totals_U1_U2_U3: tuple[float, float, float]
    centroid_U1: tuple[float, float, float] | None
    centroid_U2: tuple[float, float, float] | None
    declared_expected_mass: float
    absolute_mass_tolerance: float
    scope: str = field(default="observed_payload_consistency_only_not_native_execution_or_EDB_verification", init=False)
    native_execution_verified: bool = field(default=False, init=False)


def validate_assembled_joint_mass(
    raw: Mapping,
    observations: Mapping,
    *,
    units: str,
    expected_source: str,
    expected_mass: float,
    absolute_mass_tolerance: float,
    axes_tolerance_deg: float,
) -> MassSummary:
    """Validate arrays, bind coordinates by (source, point), and check XY totals.

    raw requires capture_id, units, return_code=0, number_results>0 and eight arrays.
    Explicit units must be kN_m_C in the call and BOTH linked payloads.
    Each array may have N entries or N+1 with ONE neutral trailing entry:
    identifier tail None/""; numeric tail finite numeric zero, never bool/None.
    No truncation, reordering, merging, invented rows or ignored extra captures.

    observations requires the SAME capture_id and N coordinate rows. Each row
    repeats source/point and all SIX raw components to prevent joining another
    mass read to a coordinate list silently. Row order itself is immaterial.

    Axes must be canonical global angles near zero. Caller supplies an explicit
    small angular tolerance (0..1e-6 degrees). expected_source must match the
    actual source name exactly; uniqueness alone is not source identity.
    Expected mass is the COMPLETE selected-source total, not an isolated water
    quantity if that source also includes other patterns. Expected mass and absolute mass
    tolerance are explicit, finite, nonnegative, in the SAME units as raw data.
    U1/U2 are compared separately; their observable centroids remain separate.
    """
    raw = _mapping(raw, "raw")
    observations = _mapping(observations, "observations")
    if units != "kN_m_C" or type(units) is not str:
        _fail("UNITS", "explicit units must be kN_m_C; no implicit conversion")
    if _field(raw, "units", "raw") != units or _field(observations, "units", "observations") != units:
        _fail("UNITS", "raw masses and coordinate observations must explicitly share kN_m_C")
    source_expected = _name(expected_source, "expected_source")
    expected = _number(expected_mass, "expected_mass", nonnegative=True)
    mass_tol = _number(absolute_mass_tolerance, "absolute_mass_tolerance", nonnegative=True)
    axes_tol = _number(axes_tolerance_deg, "axes_tolerance_deg", nonnegative=True)
    if axes_tol > 1e-6:
        _fail("AXES_TOLERANCE", "global-axis tolerance must be <=1e-6 degrees")
    capture_id = _name(_field(raw, "capture_id", "raw"), "raw.capture_id")
    observed_capture = _name(_field(observations, "capture_id", "observations"), "observations.capture_id")
    if capture_id != observed_capture:
        _fail("CAPTURE_MISMATCH", "raw and coordinate observations belong to different captures")
    rc = _field(raw, "return_code", "raw")
    if type(rc) is not int or rc != 0:
        _fail("API_RETURN", "native read return_code must be integer zero, not bool")
    n = _field(raw, "number_results", "raw")
    if type(n) is not int or n < 0:
        _fail("RESULT_COUNT", "number_results must be a nonnegative integer, excluding bool")
    if n == 0:
        _fail("EMPTY_RESULT", "diagnostic empty result; not validated even if expected_mass=0; execution evidence belongs outside this API")

    arrays = {}
    padded = []
    for field in ARRAY_FIELDS:
        values = _field(raw, field, "raw")
        if type(values) not in (list, tuple):
            _fail("ARRAY_TYPE", f"raw.{field} must be a list/tuple")
        if len(values) not in (n, n + 1):
            _fail("ARRAY_LENGTH", f"raw.{field} has {len(values)} entries; expected N or N+1")
        if len(values) == n + 1:
            tail = values[n]
            if field in NAME_FIELDS:
                if tail is not None and not (type(tail) is str and tail == ""):
                    _fail("NONNEUTRAL_PADDING", f"raw.{field} has a nonneutral identifier tail")
            elif _number(tail, f"raw.{field} padding") != 0:
                _fail("NONNEUTRAL_PADDING", f"raw.{field} has a nonzero numeric tail")
            padded.append(field)
        # Copy only after length and tail have been checked; inputs stay intact.
        arrays[field] = tuple(values[:n])

    keyed = {}
    source_names = set()
    order = []
    for i in range(n):
        point = _name(arrays["point_elements"][i], f"point_elements[{i}]")
        source = _name(arrays["mass_sources"][i], f"mass_sources[{i}]")
        key = (source, point)
        if key in keyed:
            _fail("DUPLICATE_RAW_ROW", f"duplicate source/point {key!r}")
        components = tuple(_number(arrays[f][i], f"{f}[{i}]", nonnegative=True) for f in COMPONENTS)
        keyed[key] = components
        order.append(key)
        source_names.add(source)
    if len(source_names) != 1:
        _fail("MULTIPLE_SOURCES", "do not combine multiple mass sources")

    if next(iter(source_names)) != source_expected:
        _fail("SOURCE_MISMATCH", "observed unique source does not match explicit expected_source")

    observed_rows = _field(observations, "rows", "observations")
    if type(observed_rows) not in (list, tuple) or len(observed_rows) != n:
        _fail("OBSERVATION_COUNT", "coordinate row count must equal positive N exactly")
    linked = {}
    for i, row in enumerate(observed_rows):
        row = _mapping(row, f"observations.rows[{i}]")
        point = _name(_field(row, "point_element", "row"), "row.point_element")
        source = _name(_field(row, "mass_source", "row"), "row.mass_source")
        key = (source, point)
        if key in linked:
            _fail("DUPLICATE_OBSERVATION", f"duplicate coordinate source/point {key!r}")
        if key not in keyed:
            _fail("UNLINKED_OBSERVATION", f"coordinates do not belong to raw source/point {key!r}")
        repeated = tuple(_number(_field(row, f, "row"), f"row.{f}", nonnegative=True) for f in COMPONENTS)
        if repeated != keyed[key]:
            _fail("MASS_OBSERVATION_MISMATCH", f"coordinate row repeats different mass values for {key!r}")
        xyz = _triple(_field(row, "global_xyz", "row"), "row.global_xyz")
        axes = _triple(_field(row, "point_axes_deg", "row"), "row.point_axes_deg")
        if any(abs(a) > axes_tol for a in axes):
            _fail("ROTATED_AXES", "U1/U2 cannot be interpreted as global XY with rotated point axes")
        linked[key] = MassRow(point, source, xyz, axes, repeated)
    if set(linked) != set(keyed):
        _fail("MISSING_OBSERVATION", "every raw row must have exactly one identity-linked coordinate observation")
    rows = tuple(linked[key] for key in order)
    totals = tuple(_sum((r.components[k] for r in rows), f"total_U{k+1}") for k in range(3))
    for component in (0, 1):
        if abs(totals[component] - expected) > mass_tol:
            _fail("MASS_TOTAL", f"U{component+1} total {totals[component]} differs from expected {expected} beyond {mass_tol}")

    def centroid(component):
        total = totals[component]
        if total == 0:
            return None
        # Ratios first avoid unnecessary mass*coordinate overflow.
        return tuple(_sum((r.global_xyz[k] * (r.components[component] / total) for r in rows),
                          f"centroid_U{component+1}_{k}") for k in range(3))

    return MassSummary(capture_id, units, next(iter(source_names)), n, rows, tuple(padded), totals,
                       centroid(0), centroid(1), expected, mass_tol)
