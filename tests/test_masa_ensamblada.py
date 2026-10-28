"""Offline tests only. Fixtures are existing synthetic observations, not new runs."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import unittest

from draft2model.masa_ensamblada import COMPONENTS, ARRAY_FIELDS, MassValidationError, validate_assembled_joint_mass

HERE = Path(__file__).resolve().parent / "fixtures/masa_ensamblada_253f"
FIXTURE_PATH = HERE / "extracto_sintetico_253f.json"
FIXTURE = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def sample(index=2):
    return deepcopy(FIXTURE["controls"][index])


def validate(c):
    return validate_assembled_joint_mass(c["raw"], c["observations"], units=c["units"], expected_source=c["expected_source"],
        expected_mass=c["expected_mass"], absolute_mass_tolerance=c["absolute_mass_tolerance"],
        axes_tolerance_deg=c["axes_tolerance_deg"])


class MassTests(unittest.TestCase):
    def rejected(self, c, code=None):
        with self.assertRaises(MassValidationError) as caught:
            validate(c)
        if code:
            self.assertEqual(caught.exception.code, code)

    def test_fixture_hash_and_synthetic_scope(self):
        manifest = json.loads((HERE / "manifest.json").read_text())
        self.assertEqual(hashlib.sha256(FIXTURE_PATH.read_bytes()).hexdigest(), manifest["sha256"])
        self.assertEqual(FIXTURE["provenance"]["source_receipt_sha256"], manifest["source_receipt_sha256"])
        self.assertIn("not_new_execution_not_pilot", FIXTURE["provenance"]["scope"])

    def test_observed_three_controls_and_no_execution_claim(self):
        expected = (0, 2.433552692738806, 9.734210770955224)
        for i in range(3):
            with self.subTest(control=i):
                c = sample(i); result = validate(c)
                self.assertAlmostEqual(result.totals_U1_U2_U3[0], expected[i], places=12)
                self.assertAlmostEqual(result.totals_U1_U2_U3[1], expected[i], places=12)
                self.assertEqual(result.number_results, 14)
                self.assertEqual(result.units, "kN_m_C")
                self.assertFalse(result.native_execution_verified)
                self.assertIn("not_native_execution_or_EDB", result.scope)
                self.assertEqual(result.declared_expected_mass, c["expected_mass"])
                if i == 0:
                    self.assertIsNone(result.centroid_U1)
                else:
                    for actual, target in zip(result.centroid_U1, (1, 1.075, 3)):
                        self.assertAlmostEqual(actual, target, places=12)

    def test_inputs_unchanged(self):
        c = sample(); before = deepcopy(c); validate(c)
        self.assertEqual(c, before)

    def test_exact_N_arrays_valid_and_padding_reported(self):
        c = sample(); self.assertTrue(validate(c).padded_fields)
        for field in ARRAY_FIELDS:
            c["raw"][field] = c["raw"][field][:14]
        self.assertEqual(validate(c).padded_fields, ())

    def test_mixed_N_and_Nplus1_lengths_valid(self):
        c = sample()
        for field in ("point_elements", "U1", "R2"):
            c["raw"][field] = c["raw"][field][:14]
        result = validate(c)
        self.assertNotIn("U1", result.padded_fields)
        self.assertIn("U2", result.padded_fields)

    def test_non_neutral_padding_identifier_and_numeric(self):
        for field, tail in (("point_elements", "15"), ("mass_sources", "Other"), ("U1", 0.01), ("R3", -1)):
            with self.subTest(field=field):
                c = sample(); c["raw"][field][-1] = tail
                self.rejected(c, "NONNEUTRAL_PADDING")

    def test_bad_padding_types_not_neutral(self):
        for field, tail in (("U1", False), ("U2", None), ("U3", "0"), ("R1", float("nan")), ("point_elements", False)):
            with self.subTest(field=field, tail=tail):
                c = sample(); c["raw"][field][-1] = tail; self.rejected(c)

    def test_only_one_extra_tail_per_array(self):
        for field in ARRAY_FIELDS:
            c = sample(); c["raw"][field].append(None if field in ("point_elements", "mass_sources") else 0)
            with self.subTest(field=field): self.rejected(c, "ARRAY_LENGTH")

    def test_array_short_long_and_not_array(self):
        for value in ([], [0] * 13, [0] * 16, "not an array", {"U1": 0}):
            c = sample(); c["raw"]["U1"] = value; self.rejected(c)

    def test_invalid_result_number_excludes_bool_float_string(self):
        for value in (False, True, -1, 14.0, "14", None):
            c = sample(); c["raw"]["number_results"] = value
            with self.subTest(value=value): self.rejected(c, "RESULT_COUNT")

    def test_zero_rows_diagnostic_even_expected_zero(self):
        c = sample(0); c["raw"]["number_results"] = 0
        for field in ARRAY_FIELDS: c["raw"][field] = []
        c["observations"]["rows"] = []
        self.rejected(c, "EMPTY_RESULT")

    def test_return_code_required_exact_integer_zero(self):
        for rc in (True, False, 1, -1, 0.0, "0"):
            c = sample(); c["raw"]["return_code"] = rc; self.rejected(c, "API_RETURN")
        c = sample(); del c["raw"]["return_code"]; self.rejected(c, "MISSING_FIELD")

    def test_multiple_sources_rejected_before_sum(self):
        c = sample(); c["raw"]["mass_sources"][0] = "AnotherSource"
        self.rejected(c, "MULTIPLE_SOURCES")


    def test_unique_source_still_requires_explicit_expected_identity(self):
        c = sample(); c["expected_source"] = "DifferentSource"
        self.rejected(c, "SOURCE_MISMATCH")
        c = sample(); c["raw"]["mass_sources"][:14] = ["Other"] * 14
        for row in c["observations"]["rows"]: row["mass_source"] = "Other"
        self.rejected(c, "SOURCE_MISMATCH")
        for bad in (None, False, "", " MsSrc1"):
            c = sample(); c["expected_source"] = bad; self.rejected(c, "IDENTITY")

    def test_duplicate_raw_identity_rejected(self):
        c = sample(); c["raw"]["point_elements"][1] = c["raw"]["point_elements"][0]
        self.rejected(c, "DUPLICATE_RAW_ROW")

    def test_duplicate_observation_rejected(self):
        c = sample(); c["observations"]["rows"][1] = deepcopy(c["observations"]["rows"][0])
        self.rejected(c, "DUPLICATE_OBSERVATION")

    def test_observation_identity_not_index_join(self):
        c = sample(); reference = validate(c)
        c["observations"]["rows"].reverse()
        self.assertEqual(validate(c), reference)
        c["observations"]["rows"][0]["point_element"] = "unknown point"
        self.rejected(c, "UNLINKED_OBSERVATION")

    def test_observation_count_and_source_mismatch(self):
        for mutation in ("missing", "extra", "source"):
            c = sample()
            if mutation == "missing": c["observations"]["rows"].pop()
            elif mutation == "extra": c["observations"]["rows"].append(deepcopy(c["observations"]["rows"][0]))
            else: c["observations"]["rows"][0]["mass_source"] = "Other"
            self.rejected(c)

    def test_capture_identity_required(self):
        c = sample(); c["observations"]["capture_id"] = "another read"
        self.rejected(c, "CAPTURE_MISMATCH")
        c = sample(); del c["raw"]["capture_id"]; self.rejected(c, "MISSING_FIELD")

    def test_raw_mass_and_coordinate_row_must_repeat_same_measurement(self):
        c = sample(); c["observations"]["rows"][0]["U1"] += 1
        self.rejected(c, "MASS_OBSERVATION_MISMATCH")
        c = sample(); c["observations"] = sample(1)["observations"]
        self.rejected(c, "CAPTURE_MISMATCH")

    def test_rotated_axes_and_invalid_axes_tolerance(self):
        for angle in (1, 45, 90, 360, -0.001):
            c = sample(); c["observations"]["rows"][0]["point_axes_deg"][2] = angle
            self.rejected(c, "ROTATED_AXES")
        c = sample(); c["axes_tolerance_deg"] = 90; self.rejected(c, "AXES_TOLERANCE")

    def test_nonfinite_bool_negative_raw_components(self):
        for field in COMPONENTS:
            for value in (float("nan"), float("inf"), -0.000000000001, True, "0"):
                c = sample(); c["raw"][field][0] = value
                with self.subTest(field=field, value=value): self.rejected(c)

    def test_invalid_coordinate_axis_or_mass_observations(self):
        for field, value in (("global_xyz", [True, 0, 0]), ("global_xyz", [0, float("nan"), 0]),
                             ("global_xyz", [0, 0]), ("point_axes_deg", [0, float("inf"), 0]),
                             ("point_axes_deg", [False, 0, 0]), ("point_axes_deg", [0, 0, 0, 0])):
            c = sample(); c["observations"]["rows"][0][field] = value; self.rejected(c)
        c = sample(); c["observations"]["rows"][0]["U1"] = False; self.rejected(c)

    def test_units_explicit_no_implicit_millimeter_conversion(self):
        for place in ("call", "raw", "observations"):
            c = sample()
            if place == "call": c["units"] = "N_mm_C"
            else: c[place]["units"] = "N_mm_C"
            self.rejected(c, "UNITS")
        c = sample(); del c["raw"]["units"]; self.rejected(c, "MISSING_FIELD")

    def test_expected_mass_and_tolerances_explicit_finite(self):
        for field in ("expected_mass", "absolute_mass_tolerance", "axes_tolerance_deg"):
            for value in (True, -1, float("nan"), float("inf"), "0"):
                c = sample(); c[field] = value; self.rejected(c)

    def test_partial_mass_X_or_Y_not_accepted(self):
        for field in ("U1", "U2"):
            c = sample()
            c["raw"][field][:14] = [v / 2 for v in c["raw"][field][:14]]
            for row in c["observations"]["rows"]: row[field] /= 2
            self.rejected(c, "MASS_TOTAL")

    def test_totals_and_centroids_are_separate_directional_observations(self):
        c = sample(); n = 14
        # Keep total mass but place X and Y directional masses at different known points.
        for field, index in (("U1", 0), ("U2", 1)):
            c["raw"][field][:n] = [0] * n
            c["raw"][field][index] = c["expected_mass"]
            for i, row in enumerate(c["observations"]["rows"]): row[field] = c["raw"][field][i]
        result = validate(c)
        self.assertEqual(result.centroid_U1, tuple(c["observations"]["rows"][0]["global_xyz"]))
        self.assertEqual(result.centroid_U2, tuple(c["observations"]["rows"][1]["global_xyz"]))
        self.assertNotEqual(result.centroid_U1, result.centroid_U2)

    def test_nonfinite_sum_is_diagnostic(self):
        c = sample(); c["expected_mass"] = 1e308
        c["raw"]["U1"][:14] = [1e308] * 14
        for row in c["observations"]["rows"]: row["U1"] = 1e308
        self.rejected(c, "NONFINITE_TOTAL")

    def test_missing_field_and_empty_identifier(self):
        c = sample(); del c["raw"]["U3"]; self.rejected(c, "MISSING_FIELD")
        for value in (None, "", "  ", " point"):
            c = sample(); c["raw"]["point_elements"][0] = value; self.rejected(c, "IDENTITY")


if __name__ == "__main__":
    unittest.main()
