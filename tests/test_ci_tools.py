"""#29 verificações automáticas: ferramentas de CI e contrato do workflow.

Só biblioteca padrão. Cobrem `scripts/check_docs.py`, `scripts/run_tests.py` e
regras estáticas do workflow (permissões mínimas, actions fixadas, nomes de
checks documentados). Nada aqui usa rede, segredo, câmera ou hardware.
"""

import importlib.util
import io
import json
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(f"_ci_{name}", ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


check_docs = load_script("check_docs")
run_tests = load_script("run_tests")


def write(base: Path, name: str, text: str = "") -> Path:
    path = base / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text), encoding="utf-8")
    return path


class CheckDocsTests(unittest.TestCase):
    def setUp(self):
        self._directory = TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.root = Path(self._directory.name).resolve()

    def problems(self):
        return check_docs.run(self.root)

    def test_valid_links_anchors_and_images_pass(self):
        write(self.root, "README.md", """\
            # Projeto
            Veja [guia](docs/guia.md#seção-dois), [topo](#projeto) e ![fig](docs/fig.png).
            [externo](https://example.com/inexistente) e [e-mail](mailto:a@b.c).
            """)
        write(self.root, "docs/guia.md", "# Guia\n## Seção dois\n")
        (self.root / "docs" / "fig.png").write_bytes(b"\x89PNG")
        self.assertEqual(self.problems(), [])

    def test_missing_target_and_missing_anchor_are_reported(self):
        write(self.root, "README.md", "[a](docs/nao-existe.md) e [b](docs/guia.md#ausente)\n")
        write(self.root, "docs/guia.md", "# Guia\n")
        found = self.problems()
        self.assertEqual(len(found), 2)
        self.assertTrue(any("alvo inexistente" in item for item in found))
        self.assertTrue(any("âncora inexistente" in item for item in found))

    def test_link_escaping_the_repository_is_reported(self):
        write(self.root, "README.md", "[fora](../fora.md)\n")
        self.assertTrue(any("sai do repositório" in item for item in self.problems()))

    def test_code_blocks_and_inline_code_are_ignored(self):
        write(self.root, "README.md", """\
            ```md
            [quebrado](nada.md)
            ```
            Texto com `[inline](nada.md)` e [valido](#titulo).
            # Titulo
            """)
        self.assertEqual(self.problems(), [])

    def test_duplicate_headings_get_numbered_anchors(self):
        write(self.root, "README.md", "# A\n# A\n[x](#a-1) [y](#a)\n")
        self.assertEqual(self.problems(), [])

    def test_invalid_json_duplicate_keys_and_nan_are_reported(self):
        write(self.root, "docs/ok.json", '{"a": 1}')
        write(self.root, "docs/quebrado.json", '{"a": ')
        write(self.root, "docs/duplicado.json", '{"a": 1, "a": 2}')
        write(self.root, "docs/nan.json", '{"a": NaN}')
        found = [item for item in self.problems() if "JSON inválido" in item]
        self.assertEqual(sorted(item.split(":")[0] for item in found),
                         ["docs/duplicado.json", "docs/nan.json", "docs/quebrado.json"])

    def test_adr_index_numbers_and_orphans(self):
        write(self.root, "docs/decisions/0001-a.md", "# a\n")
        write(self.root, "docs/decisions/0002-b.md", "# b\n")
        write(self.root, "docs/decisions/0002-c.md", "# c\n")
        write(self.root, "docs/decisions/README.md",
              "- [a](0001-a.md)\n- [b](0002-b.md)\n- [fantasma](0003-x.md)\n")
        found = "\n".join(self.problems())
        self.assertIn("número 0002 repetido", found)
        self.assertIn("ADR fora do índice: 0002-c.md", found)
        self.assertIn("entrada sem arquivo: 0003-x.md", found)

    def test_docs_index_must_list_every_document(self):
        write(self.root, "docs/README.md", "- [a](a.md)\n")
        write(self.root, "docs/a.md", "# a\n")
        write(self.root, "docs/b.md", "# b\n")
        self.assertEqual(self.problems(), ["docs/README.md: documento fora do índice: b.md"])

    def test_cli_exit_codes(self):
        write(self.root, "README.md", "# ok\n")
        stdout, stderr = io.StringIO(), io.StringIO()
        original = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = stdout, stderr
        try:
            self.assertEqual(check_docs.main(["--root", str(self.root)]), 0)
            write(self.root, "README.md", "[x](nada.md)\n")
            self.assertEqual(check_docs.main(["--root", str(self.root)]), 1)
        finally:
            sys.stdout, sys.stderr = original
        self.assertIn("ERRO README.md:1", stderr.getvalue())

    def test_repository_documentation_is_consistent(self):
        self.assertEqual(check_docs.run(ROOT), [])


FIXTURE = '''\
import unittest


class Sample(unittest.TestCase):
    def test_ok(self):
        pass

    def test_fails(self):
        self.assertEqual(1, 2)

    def test_errors(self):
        raise RuntimeError("falha com detalhe " + "x" * 600)

    @unittest.skip("install .[api] to run this")
    def test_skipped_optional(self):
        pass

    @unittest.skip("outro motivo")
    def test_skipped_other(self):
        pass
'''


class RunTestsTests(unittest.TestCase):
    def setUp(self):
        self._directory = TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.root = Path(self._directory.name)
        self.addCleanup(self._forget_fixture_modules)

    def _forget_fixture_modules(self):
        for name in [name for name in sys.modules if name.startswith("test_fx_")]:
            del sys.modules[name]
        sys.path[:] = [entry for entry in sys.path if entry != str(self.root.resolve())]

    def fixture(self, name="test_fx_mixed", text=FIXTURE):
        write(self.root, f"{name}.py", text)
        return self.root

    def run_fixture(self, **options):
        result, seconds = run_tests.run_suite(self.root, stream=io.StringIO(), verbosity=0)
        return run_tests.build_report(result, seconds, **options)

    def test_counts_failures_errors_and_skips(self):
        self.fixture("test_fx_mixed")
        report = self.run_fixture()
        self.assertFalse(report["passed"])
        self.assertEqual(report["counts"], {"run": 5, "failures": 1, "errors": 1, "skipped": 2,
                                            "unexpected_successes": 0})
        kinds = {item["kind"] for item in report["problems"]}
        self.assertEqual(kinds, {"failure", "error"})
        self.assertTrue(all(len(item["message"]) <= run_tests.MAX_MESSAGE for item in report["problems"]))

    def test_clean_run_passes_and_skips_are_listed(self):
        self.fixture("test_fx_clean", FIXTURE.split("    def test_fails")[0]
                     + '    @unittest.skip("opcional")\n    def test_s(self):\n        pass\n')
        report = self.run_fixture()
        self.assertTrue(report["passed"])
        self.assertEqual(report["counts"]["skipped"], 1)
        self.assertEqual(report["skipped"][0]["reason"], "opcional")

    def test_forbidden_skip_fails_an_otherwise_green_run(self):
        self.fixture("test_fx_skips", '''\
import unittest


class Only(unittest.TestCase):
    @unittest.skip("install .[api] to run this")
    def test_needs_extra(self):
        pass

    @unittest.skip("hardware ausente")
    def test_other(self):
        pass
''')
        report = self.run_fixture(fail_on_skip=("install .[api",))
        self.assertFalse(report["passed"])
        self.assertEqual([item["reason"] for item in report["forbidden_skips"]],
                         ["install .[api] to run this"])
        self.assertTrue(self.run_fixture(fail_on_skip=("texto que ninguém usa",))["passed"])

    def test_markdown_report_is_useful_and_free_of_local_paths(self):
        self.fixture("test_fx_md")
        report = self.run_fixture()
        text = run_tests.render_markdown(report, "Título de teste")
        self.assertIn("## Título de teste", text)
        self.assertIn("Reprovado", text)
        self.assertIn("test_fails", text)
        self.assertIn("Testes ignorados (2)", text)
        self.assertNotIn(str(self.root), text)
        self.assertNotIn(str(Path.home()), text)

    def test_main_writes_reports_and_returns_exit_code(self):
        self.fixture("test_fx_main")
        out = self.root / "saida"
        original, sys.stderr = sys.stderr, io.StringIO()
        try:
            code = run_tests.main(["--start-dir", str(self.root), "--report-dir", str(out)])
        finally:
            sys.stderr = original
        self.assertEqual(code, 1)
        data = json.loads((out / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(data["counts"]["run"], 5)
        self.assertTrue((out / "report.md").read_text(encoding="utf-8").startswith("## "))


class WorkflowContractTests(unittest.TestCase):
    """Regras estáticas do CI: o que não pode regredir sem revisão."""

    @classmethod
    def setUpClass(cls):
        # Comentários podem citar termos proibidos para explicar a regra.
        cls.workflows = {path.name: re.sub(r"(?m)^\s*#.*$", "", path.read_text(encoding="utf-8"))
                         for path in (ROOT / ".github" / "workflows").glob("*.yml")}
        cls.ci = cls.workflows["ci.yml"]

    def test_no_untrusted_trigger_and_no_secrets(self):
        for name, text in self.workflows.items():
            with self.subTest(name):
                self.assertNotIn("pull_request_target", text)
                self.assertNotIn("secrets.", text)
                self.assertNotIn("workflow_run", text)

    def test_permissions_are_read_only_at_workflow_level(self):
        for name in ("ci.yml", "benchmark.yml"):
            with self.subTest(name):
                self.assertRegex(self.workflows[name], r"(?m)^permissions:\n  contents: read$")
                self.assertNotRegex(self.workflows[name], r"(?m)^\s+(contents|pull-requests|id-token): write")

    def test_every_action_is_pinned_to_a_commit(self):
        for name, text in self.workflows.items():
            for use in re.findall(r"(?m)^\s*-?\s*uses:\s*(\S+)", text):
                with self.subTest(workflow=name, action=use):
                    self.assertRegex(use, r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")

    def test_checkout_does_not_persist_credentials(self):
        for name in ("ci.yml", "benchmark.yml"):
            text = self.workflows[name]
            checkouts = text.count("actions/checkout@")
            self.assertGreater(checkouts, 0)
            self.assertEqual(text.count("persist-credentials: false"), checkouts, name)

    def test_every_ci_job_has_a_timeout_and_a_documented_name(self):
        documented = (ROOT / "docs" / "ci.md").read_text(encoding="utf-8")
        jobs = re.findall(r"(?ms)^  ([\w-]+):\n    name: ([^\n]+)\n(.*?)(?=^  [\w-]+:\n|\Z)", self.ci)
        self.assertGreaterEqual(len(jobs), 6)
        for key, name, body in jobs:
            with self.subTest(job=key):
                self.assertIn("timeout-minutes:", body)
                base = re.sub(r"\s*\(.*\)$", "", name.strip())
                self.assertIn(base, documented)

    def test_ci_cancels_superseded_runs_and_is_the_only_pr_workflow(self):
        self.assertIn("concurrency:", self.ci)
        self.assertIn("cancel-in-progress: true", self.ci)
        self.assertNotIn("pull_request", self.workflows["benchmark.yml"])
        self.assertIn("workflow_dispatch", self.workflows["benchmark.yml"])

    def test_gate_job_requires_every_other_job(self):
        jobs = re.findall(r"(?m)^  ([\w-]+):\n    name:", self.ci)
        self.assertIn("gate", jobs)
        needs = re.search(r"(?m)^  gate:\n(?:.*\n)*?    needs: \[([^\]]*)\]", self.ci)
        self.assertIsNotNone(needs)
        listed = {item.strip() for item in needs.group(1).split(",")}
        self.assertEqual(listed, set(jobs) - {"gate"})
        self.assertIn("if: always()", self.ci)

    def test_dependencies_are_installed_from_pinned_extras_with_cache(self):
        self.assertIn("cache: pip", self.ci)
        self.assertIn("cache-dependency-path: pyproject.toml", self.ci)
        self.assertIn("ruff==", self.ci)

    def test_reports_are_uploaded_without_secrets_and_with_short_retention(self):
        self.assertIn("upload-artifact@", self.ci)
        self.assertRegex(self.ci, r"retention-days: \d+")
        self.assertIn("GITHUB_STEP_SUMMARY", self.ci)


if __name__ == "__main__":
    unittest.main()
