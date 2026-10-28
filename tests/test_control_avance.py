"""Pruebas de vigencia de evidencia, regresiones y lectura aislada del control."""
import copy
from email.message import Message
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from urllib.error import URLError

from seguimiento.control import Controller, ROOT, blob, diff, evaluate, handler, public_path, remote_snapshot, save, scan


def catalog():
    return {'milestones': [{'id': 'O1', 'title': 'Prueba', 'criteria': [
        {'id': 'O1.1', 'title': 'Código', 'files': ['mod.py', 'tests/test_mod.py'],
         'tests': ['test_mod.py'], 'check_files': ['mod.py', 'tests/test_mod.py', 'dependency.py']},
        {'id': 'O1.2', 'title': 'Ingeniería', 'files': [], 'tests': [], 'pending': 'Falta revisión real.'}]}]}


def files():
    return {'mod.py': 'a', 'tests/test_mod.py': 'b', 'dependency.py': 'c'}


def proof():
    return {'files': files(), 'modules': {'test_mod.py': {'passed': True, 'count': 2}}, 'finished': '2026-10-15T00:00:00Z'}


def criterion(result):
    return result['milestones'][0]['criteria'][0]


class ControlAvanceTests(unittest.TestCase):
    def test_existence_does_not_verify(self):
        self.assertEqual(criterion(evaluate(catalog(), files()))['state'], 'implementado')
        self.assertEqual(evaluate(catalog(), files())['percent'], 0)

    def test_tests_on_exact_files_verify(self):
        result = evaluate(catalog(), files(), proof())
        self.assertEqual(result['done'], 1)
        self.assertEqual(result['percent'], 50)
        self.assertEqual(result['milestones'][0]['criteria'][1]['state'], 'pendiente')

    def test_dependency_change_invalidates_proof(self):
        changed = files()
        changed['dependency.py'] = 'new'
        self.assertEqual(criterion(evaluate(catalog(), changed, proof()))['state'], 'implementado')

    def test_delete_file_removes_verification(self):
        changed = files()
        del changed['mod.py']
        self.assertEqual(evaluate(catalog(), changed, proof())['done'], 0)

    def test_failed_and_zero_tests_not_verified(self):
        for passed, count in ((False, 2), (True, 0)):
            p = proof()
            p['modules']['test_mod.py'] = {'passed': passed, 'count': count}
            self.assertEqual(evaluate(catalog(), files(), p)['done'], 0)

    def test_remote_matching_is_not_local_status_copy(self):
        remote = files()
        remote['mod.py'] = 'older version'
        self.assertEqual(evaluate(catalog(), files(), proof())['done'], 1)
        self.assertEqual(evaluate(catalog(), remote, proof())['done'], 0)

    def test_reviews_require_current_complete_evidence(self):
        review = {'criterion': 'O1.1', 'reviewer': 'Prueba declarada', 'date': '2026-10-15', 'note': 'Revisado', 'files': files()}
        self.assertEqual(evaluate(catalog(), files(), reviews=[review])['done'], 1)
        review['files']['mod.py'] = 'stale'
        self.assertEqual(evaluate(catalog(), files(), reviews=[review])['done'], 0)

    def test_invalid_review_cannot_complete_engineering(self):
        review = {'criterion': 'O1.2', 'reviewer': 'r', 'date': '2026-10-15', 'note': 'n', 'files': {}}
        self.assertEqual(evaluate(catalog(), files(), reviews=[review])['done'], 0)

    def test_metadata_probe_requires_true(self):
        cat = catalog()
        cat['milestones'][0]['criteria'][0]['probe'] = 'private'
        self.assertEqual(evaluate(cat, {}, meta={'private': 'true'})['done'], 0)
        self.assertEqual(evaluate(cat, {}, meta={'private': True})['done'], 1)

    def test_scan_detects_add_modify_delete_and_excludes_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'mod.py').write_text('a', encoding='utf-8')
            (root / '.env').write_text('secret')
            (root / '.venv').mkdir()
            (root / '.venv/x.py').write_text('secret')
            first, cache, errors = scan(root)
            self.assertFalse(errors)
            self.assertEqual(list(first), ['mod.py'])
            (root / 'mod.py').write_text('b', encoding='utf-8')
            (root / 'new.md').write_text('n', encoding='utf-8')
            second, _, _ = scan(root, cache)
            self.assertEqual({x['kind'] for x in diff(first, second)}, {'nuevo', 'modificado'})
            (root / 'mod.py').unlink()
            third, _, _ = scan(root)
            self.assertIn({'path': 'mod.py', 'kind': 'eliminado'}, diff(second, third))

    def test_private_observation_stays_out_of_published_comparison(self):
        for p in ('planos_muestra/a.pdf', 'data/private/a.json', 'models/generated/a.edb', '.env', 'tmp/a.json'):
            self.assertFalse(public_path(p), p)
        self.assertTrue(public_path('draft2model/ingreso.py'))

    def test_blob_hash_and_atomic_save(self):
        self.assertEqual(blob(b'hello\n'), 'ce013625030ba8dba906f756967f9e9ca394464a')
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'x.json'
            save(p, {'value': 1})
            with self.assertRaises(ValueError):
                save(p, {'value': float('nan')})
            self.assertEqual(json.loads(p.read_text())['value'], 1)
            self.assertEqual(list(Path(tmp).glob('*.tmp')), [])

    def test_evaluation_does_not_mutate_inputs(self):
        cat, f, p = catalog(), files(), proof()
        original = copy.deepcopy((cat, f, p))
        evaluate(cat, f, p)
        self.assertEqual((cat, f, p), original)

    def test_live_test_runner_records_modules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'tests').mkdir()
            (root / 'tests/test_sample.py').write_text('import unittest\nclass T(unittest.TestCase):\n def test_sum(self): self.assertEqual(2+2,4)\n', encoding='utf-8')
            (root / 'seguimiento').mkdir()
            save(root / 'seguimiento/hitos.json', {'milestones': []})
            c = Controller(root, root / 'tmp')
            c.scan_once()
            c.run_tests()
            self.assertTrue(c.proof['passed'], c.proof)
            self.assertEqual(c.proof['modules']['test_sample.py'], {'count': 1, 'passed': True})

    def test_skipped_tests_are_visible_and_not_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'tests').mkdir();(root/'seguimiento').mkdir()
            (root/'tests/test_skip.py').write_text('import unittest\nclass T(unittest.TestCase):\n @unittest.skip("sin capacidad en este entorno")\n def test_optional(self): pass\n',encoding='utf-8')
            save(root/'seguimiento/hitos.json',{'milestones':[]})
            c=Controller(root,root/'tmp');c.scan_once();c.run_tests()
            self.assertTrue(c.proof['passed'])
            self.assertFalse(c.proof['modules']['test_skip.py']['passed'])
            self.assertEqual(len(c.proof['skipped']),1)
            self.assertEqual(c.proof['skipped'][0]['module'],'test_skip.py')

    def test_github_failure_preserves_last_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = Controller(Path(tmp), Path(tmp) / 'state')
            c.remote = {'sha': 'previous', 'checked_at': 'original-date'}
            c.token = 'test-only'
            with patch('seguimiento.control.remote_snapshot', side_effect=URLError('offline')):
                c.sync_github()
            self.assertEqual(c.remote['sha'], 'previous')
            self.assertEqual(c.remote['checked_at'], 'original-date')
            self.assertEqual(c.remote_mode, 'sin_conexion')

    def test_truncated_remote_tree_not_accepted(self):
        responses = [{'default_branch': 'main'}, {'commit': {'sha': 'c', 'commit': {'tree': {'sha': 't'}}}}, {'truncated': True}]
        with patch('seguimiento.control.api', side_effect=responses):
            with self.assertRaises(ValueError):
                remote_snapshot('test-only')

    def test_regression_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'seguimiento').mkdir()
            save(root / 'seguimiento/hitos.json', catalog())
            c = Controller(root, root / 'tmp')
            c.files, c.proof = files(), proof()
            c.record_progress()
            c.files['mod.py'] = 'changed'
            c.record_progress()
            self.assertEqual(c.events[0]['kind'], 'criterio')
            self.assertIn('invalidada', c.events[0]['interpretation'])

    def test_http_actions_require_local_session_and_origin(self):
        c = SimpleNamespace(secret='test-session', start_tests=lambda: None)
        H = handler(c)
        def request(origin, session):
            h = object.__new__(H)
            h.server = SimpleNamespace(server_port=8765)
            h.path = '/api/tests'
            h.headers = Message()
            for key, value in {'Host':'127.0.0.1:8765','Origin':origin,'X-Control-Session':session,'Content-Length':'2'}.items():
                h.headers[key] = value
            h.rfile = BytesIO(b'{}')
            response=[]
            h.send=lambda *args: response.append(args)
            h.do_POST()
            return response[0][0]
        self.assertEqual(request('http://evil.invalid','test-session'),403)
        self.assertEqual(request('http://127.0.0.1:8765','wrong'),403)
        self.assertEqual(request('http://127.0.0.1:8765','test-session'),202)

    def test_http_only_serves_explicit_assets(self):
        H = handler(SimpleNamespace(root=ROOT))
        h = object.__new__(H)
        h.server = SimpleNamespace(server_port=8765)
        h.headers = Message()
        h.headers['Host']='127.0.0.1:8765'
        response=[]
        h.send=lambda *args: response.append(args)
        h.path='/../data/private/expediente.json'
        h.do_GET()
        self.assertEqual(response[-1][0],404)
        h.path='/'
        h.do_GET()
        self.assertEqual(response[-1][0],200)
        self.assertIn(b'Control de avance',response[-1][1])

    def test_frontend_referenced_ids_exist(self):
        import re
        html=(ROOT/'seguimiento/web/index.html').read_text(encoding='utf-8')
        script=(ROOT/'seguimiento/web/app.js').read_text(encoding='utf-8')
        references=set(re.findall(r"\$\('([^']+)'\)",script))
        ids=set(re.findall(r'id="([^"]+)"',html))
        self.assertFalse(references-ids,references-ids)

    def test_catalog_has_unique_criteria_and_existing_test_dependencies(self):
        cat=json.loads((ROOT/'seguimiento/hitos.json').read_text(encoding='utf-8'))
        ids=[c['id'] for m in cat['milestones'] for c in m['criteria']]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual(len(cat['milestones']),7)
        for m in cat['milestones']:
            for c in m['criteria']:
                for p in c.get('check_files',[]):
                    self.assertNotIn('..',Path(p).parts)
                if c.get('tests') and all((ROOT/p).is_file() for p in c['files']):
                    self.assertTrue(all((ROOT/p).is_file() for p in c['check_files']),c['id'])

    def test_linked_html_uses_local_assets_and_same_dashboard_ids(self):
        import re
        html = (ROOT/'Control de avance.html').read_text(encoding='utf-8')
        source = (ROOT/'seguimiento/web/index.html').read_text(encoding='utf-8')
        self.assertEqual(set(re.findall(r'id="([^"]+)"',html)), set(re.findall(r'id="([^"]+)"',source)))
        self.assertIn('href="seguimiento/web/style.css"', html)
        self.assertIn('src="seguimiento/web/app.js"', html)
        self.assertNotIn('http://127.0.0.1', html)

    def test_exported_data_changes_with_snapshot_and_excludes_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            c=Controller(root,root/'tmp')
            c.secret='NEVER_EXPORT_THIS_SESSION'
            first={'local':{'done':1},'session':c.secret,'activity':[{'message':'<script>input</script>'}]}
            with patch.object(c,'snapshot',return_value=first.copy()):
                target=c.export_snapshot()
            text=target.read_text(encoding='utf-8')
            self.assertTrue(text.startswith('window.recibirControlAvance('))
            self.assertNotIn(c.secret,text)
            self.assertNotIn('<script>',text)
            payload=json.loads(text[len('window.recibirControlAvance('):-3])
            self.assertEqual(payload['local']['done'],1)
            self.assertEqual(payload,json.loads((c.state_dir/'resumen.json').read_text(encoding='utf-8')))
            with patch.object(c,'snapshot',return_value={'local':{'done':2},'session':c.secret}):
                c.export_snapshot()
            updated=target.read_text(encoding='utf-8')
            self.assertNotEqual(text,updated)
            self.assertEqual(json.loads(updated[len('window.recibirControlAvance('):-3])['local']['done'],2)
            self.assertFalse(list(c.state_dir.glob('estado.*.tmp')))

    def test_failed_data_export_keeps_previous_complete_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);c=Controller(root,root/'tmp')
            with patch.object(c,'snapshot',return_value={'session':'secret','value':1}):
                target=c.export_snapshot()
            original=target.read_bytes()
            # La escritura de resumen.json sí pasa; el fallo se limita a publicar el JS.
            import os
            replace=os.replace
            def fail_js(source,destination):
                if Path(destination).name=='estado.js':
                    raise OSError('Fallo simulado')
                return replace(source,destination)
            with patch.object(c,'snapshot',return_value={'session':'secret','value':2}), patch('seguimiento.control.os.replace',side_effect=fail_js):
                with self.assertRaises(OSError):c.export_snapshot()
            self.assertEqual(target.read_bytes(),original)
            self.assertFalse(list(c.state_dir.glob('estado.*.tmp')))

    def test_damaged_generated_caches_are_preserved_without_fake_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);state=root/'tmp';state.mkdir()
            (state/'criteria.json').write_bytes(b'\x00\x00')
            (state/'tests.json').write_bytes(b'not JSON')
            c=Controller(root,state)
            self.assertEqual(c.last_result,{})
            self.assertEqual(c.proof,{})
            self.assertEqual(next(state.glob('criteria.json.invalid-*')).read_bytes(),b'\x00\x00')
            self.assertEqual(next(state.glob('tests.json.invalid-*')).read_bytes(),b'not JSON')
            self.assertTrue(any(e['kind']=='recuperacion' for e in c.events))


if __name__ == '__main__':
    unittest.main()
