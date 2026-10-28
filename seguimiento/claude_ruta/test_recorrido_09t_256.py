"""Offline candidate route tests: no product import, ETABS or private approval."""
import ast
from copy import deepcopy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from contextlib import redirect_stdout

from validacion_etapas_255 import (validate_stage_outcome, validar_revision_controles,
    StageOutcomeError, CONTROLES_ESPERADOS)

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("candidato255", HERE / "recorrido_etabs_09t.py")
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)  # Only standard library and pure local gates load.
H = "a" * 64


def good_report(stage="relectura"):
    return {"sha256_plantilla_esperada": H, "sha256_plantilla_anterior": H,
            "sha256_plantilla_posterior": H,
            "fases": {"construccion": {"estado": "ok", "cierre_confirmado": True, "registro_modelo": "model255"},
                      "relectura": {"estado": "verificado", "discrepancias": 0, "incompletos": 0}}}


def review(reference="evidence.txt", evidence_sha=H):
    return {"modelo_id": "model255", "huella_modelo": H, "revisor": "Revisor de prueba offline",
            "fecha": "2026-10-22", "alcance": "Solo revisión del transporte en prueba offline",
            "controles": dict.fromkeys(CONTROLES_ESPERADOS, True),
            "evidencias": {k: {"referencia": reference, "sha256": evidence_sha, "alcance": "Comprobación explícita de " + k}
                           for k in CONTROLES_ESPERADOS}}


def original_exit_from_pure_predicate(report):
    # Execute ONLY the frozen original's pure fallo expression, never its imports/main.
    tree = ast.parse((HERE / "fixtures_recorrido_256/original/recorrido_etabs_09t.py").read_text(encoding="utf-8-sig"))
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    expr = next(n.value for n in main.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "fallo" for t in n.targets))
    return 1 if eval(compile(ast.Expression(expr), "frozen_pure_predicate", "eval"), {"rep": report}) else 0


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory(dir=HERE)
        self.root = Path(self.tmp.name)
        (self.root / "tmp").mkdir()
        (self.root / "data").mkdir()
        self.save = lambda p, d: p.write_text(json.dumps(d), encoding="utf-8")
        self.epl = SimpleNamespace(guardar=self.save,
            sha=lambda p: H if Path(p) == candidate.PLANTILLA else hashlib.sha256(Path(p).read_bytes()).hexdigest())
        self.patches = [patch.object(candidate, "RAIZ", self.root),
                        patch.object(candidate, "LOCK", self.root / "tmp/motor.lock"),
                        patch.object(candidate, "cargar_dependencias", Mock()),
                        patch.object(candidate, "epl", self.epl, create=True)]
        for p in self.patches: p.start()

    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        self.tmp.cleanup()

    def run_main(self, stage, report):
        work = self.root / "tmp/run"
        if stage != "construccion":
            work.mkdir(exist_ok=True)
            self.save(work / "registro.json", good_report())
        def outcome(work, rep, **kwargs):
            rep.clear(); rep.update(deepcopy(report))
        with patch.object(candidate, "etapa_" + stage, side_effect=outcome), redirect_stdout(io.StringIO()):
            result = candidate.main(["--trabajo", str(work), "--etapa", stage])
        return result, json.loads((work / "registro.json").read_text())

    def test_main_construction_closure_and_hash_regressions(self):
        bads = []
        r = good_report(); r["fases"]["construccion"]["cierre_confirmado"] = False; bads.append(r)
        r = good_report(); r["fases"]["construccion"]["error_cierre"] = "close failed"; bads.append(r)
        r = good_report(); r["sha256_plantilla_posterior"] = "b" * 64; bads.append(r)
        r = good_report(); del r["sha256_plantilla_anterior"]; bads.append(r)
        for i, r in enumerate(bads):
            with self.subTest(i=i):
                # Same candidate main route, separate new work folder for every iteration.
                with patch.object(candidate, "RAIZ", self.root / str(i)):
                    (candidate.RAIZ / "tmp").mkdir(parents=True)
                    old_root = self.root; self.root = candidate.RAIZ
                    try:
                        self.assertEqual(original_exit_from_pure_predicate(r), 0)
                        if i == 2:
                            self.epl.sha = lambda p: "b" * 64
                        else:
                            self.epl.sha = lambda p: H
                        rc, saved = self.run_main("construccion", r)
                        self.assertEqual(rc, 1)
                        self.assertIn("construccion_error", saved["fases"])
                    finally: self.root = old_root

    def test_main_construction_positive(self):
        rc, _ = self.run_main("construccion", good_report())
        self.assertEqual(rc, 0)

    def test_main_reread_rejects_discrepancies_incomplete_and_bad_counts(self):
        cases = [("discrepancias", 1, 0), ("incompleto", 0, 1), ("verificado", 1, 0), ("verificado", 0, False)]
        for i, (state, disc, inc) in enumerate(cases):
            r = good_report(); r["fases"]["relectura"].update(estado=state, discrepancias=disc, incompletos=inc)
            self.assertEqual(original_exit_from_pure_predicate(r), 0)
            rc, saved = self.run_main("relectura", r)
            self.assertEqual(rc, 1)
            self.assertIn("relectura_error", saved["fases"])

    def test_main_reread_positive(self):
        self.assertEqual(self.run_main("relectura", good_report())[0], 0)

    def test_main_resolves_absolute_and_relative_escape_before_loader(self):
        for path in (str(self.root / "tmp/../data/escape"), "tmp/../data/escape", str(self.root / "tmp")):
            with self.assertRaises(ValueError):
                candidate.main(["--trabajo", path, "--etapa", "construccion"])
        candidate.cargar_dependencias.assert_not_called()
        self.assertFalse((self.root / "data/escape").exists())

    def test_new_construction_directory_preserves_previous_outputs(self):
        work = self.root / "tmp/existing"; work.mkdir(); (work / "old.txt").write_text("keep")
        with self.assertRaises(FileExistsError):
            candidate.main(["--trabajo", str(work), "--etapa", "construccion"])
        self.assertEqual((work / "old.txt").read_text(), "keep")

    def test_analysis_without_explicit_review_does_not_approve(self):
        fake_rm = SimpleNamespace(aprobar=Mock(), consultar=Mock(), CONTROLES=CONTROLES_ESPERADOS)
        with patch.object(candidate, "rm", fake_rm, create=True):
            with self.assertRaises(ValueError): candidate.etapa_analisis(self.root, good_report())
        fake_rm.aprobar.assert_not_called()

    def test_analysis_bad_prerequisite_does_not_approve(self):
        r = good_report(); r["fases"]["relectura"]["incompletos"] = 1
        fake_rm = SimpleNamespace(aprobar=Mock())
        with patch.object(candidate, "rm", fake_rm, create=True):
            with self.assertRaises(ValueError): candidate.etapa_analisis(self.root, r)
        fake_rm.aprobar.assert_not_called()

    def test_review_validator_rejects_unobserved_or_stale_controls(self):
        edits = [lambda r: r["controles"].update(cargas_masa=False),
                 lambda r: r["controles"].update(cargas_masa=1),
                 lambda r: r["evidencias"].pop("cargas_masa"),
                 lambda r: r["evidencias"]["cargas_masa"].update(alcance=""),
                 lambda r: r.update(modelo_id="other"),
                 lambda r: r.update(huella_modelo="b" * 64),
                 lambda r: r.update(revisor=""), lambda r: r.update(fecha="invalid")]
        for edit in edits:
            r = review(); edit(r)
            with self.assertRaises(ValueError): validar_revision_controles(r, CONTROLES_ESPERADOS, "model255", H)

    def test_actual_analysis_route_forwards_only_explicit_actor_and_controls(self):
        evidence = self.root / "evidence.txt"; evidence.write_text("offline synthetic review evidence")
        h = hashlib.sha256(evidence.read_bytes()).hexdigest()
        r = review(evidence_sha=h); path = self.root / "review.json"; self.save(path, r)
        stop = RuntimeError("STOP AFTER MOCK APPROVAL - no native calls")
        fake_rm = SimpleNamespace(consultar=Mock(return_value={"huella_modelo": H}),
            aprobar=Mock(side_effect=stop), CONTROLES=CONTROLES_ESPERADOS)
        with patch.object(candidate, "rm", fake_rm, create=True):
            with self.assertRaisesRegex(RuntimeError, "STOP AFTER MOCK"):
                candidate.etapa_analisis(self.root, good_report(), path)
        kwargs = fake_rm.aprobar.call_args.kwargs
        self.assertEqual(kwargs["revisor"], r["revisor"])
        self.assertNotEqual(kwargs["revisor"], candidate.REVISOR)
        self.assertEqual(kwargs["controles"], r["controles"])
        self.assertEqual(kwargs["alcance"], candidate.ALCANCE)

    def test_modified_evidence_file_blocks_actual_analysis_approval(self):
        evidence = self.root / "evidence.txt"; evidence.write_text("changed")
        path = self.root / "review.json"; self.save(path, review())
        fake_rm = SimpleNamespace(consultar=Mock(return_value={"huella_modelo": H}), aprobar=Mock(), CONTROLES=CONTROLES_ESPERADOS)
        with patch.object(candidate, "rm", fake_rm, create=True):
            with self.assertRaises(ValueError): candidate.etapa_analisis(self.root, good_report(), path)
        fake_rm.aprobar.assert_not_called()

    def test_review_changed_after_read_blocks_approval(self):
        evidence = self.root / "evidence.txt"
        evidence.write_text("offline evidence")
        h = hashlib.sha256(evidence.read_bytes()).hexdigest()
        path = self.root / "review.json"
        self.save(path, review(evidence_sha=h))
        def modify_review(*args):
            changed = review(evidence_sha=h)
            changed["revisor"] = "Actor posterior distinto"
            self.save(path, changed)
            return {"huella_modelo": H}
        fake_rm = SimpleNamespace(consultar=Mock(side_effect=modify_review),
            aprobar=Mock(), CONTROLES=CONTROLES_ESPERADOS)
        with patch.object(candidate, "rm", fake_rm, create=True):
            with self.assertRaisesRegex(ValueError, "cambió durante"):
                candidate.etapa_analisis(self.root, good_report(), path)
        fake_rm.aprobar.assert_not_called()

    def test_pure_analysis_gate_rejects_just_reread(self):
        with self.assertRaises(ValueError): validate_stage_outcome("analisis", good_report())


    def test_analysis_main_requires_documented_controls_even_after_verified_read(self):
        r = good_report(); doc = review()
        r["fases"]["revision_controles_transporte"] = {
            "estado": "documentada", "sha256": H, "modelo_id": doc["modelo_id"], "huella_modelo": H,
            "revisor_declarado": doc["revisor"], "fecha": doc["fecha"], "alcance_revision": doc["alcance"],
            "controles": doc["controles"], "evidencias": doc["evidencias"],
            "alcance_autorizacion_software": candidate.ALCANCE, "aprueba_ingenieria": False}
        r["fases"]["aprobacion_modelo_transporte"] = {"estado": "ok"}
        r["fases"]["analisis"] = {"estado": "ok"}
        r["fases"]["lecturas"] = {name: {"estado": "ok"} for name in ("reacciones", "modal", "derivas")}
        self.assertEqual(self.run_main("analisis", r)[0], 0)
        r["fases"]["revision_controles_transporte"]["controles"]["cargas_masa"] = False
        self.assertEqual(self.run_main("analisis", r)[0], 1)

    def test_template_drift_blocks_reread_before_handler(self):
        work = self.root / "tmp/run"; work.mkdir(); self.save(work / "registro.json", good_report())
        self.epl.sha = lambda p: "b" * 64
        with patch.object(candidate, "etapa_relectura") as handler, redirect_stdout(io.StringIO()):
            result = candidate.main(["--trabajo", str(work), "--etapa", "relectura"])
        self.assertEqual(result, 1); handler.assert_not_called()

    def test_real_control_contract_frozen_without_importing_product(self):
        frozen = json.loads((HERE / "fixtures_recorrido_256" / "congelado.json").read_text())
        self.assertEqual(tuple(frozen["CONTROLES"]), CONTROLES_ESPERADOS)
        self.assertEqual(hashlib.sha256((HERE / "fixtures_recorrido_256/original/recorrido_etabs_09t.py").read_bytes()).hexdigest(), frozen["sha256"])


if __name__ == "__main__":
    unittest.main()
