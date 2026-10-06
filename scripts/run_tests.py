"""Executa a suíte e gera relatório (#29): `python scripts/run_tests.py --report-dir test-report`.

Roda `unittest discover -s tests` e grava `report.json` e `report.md` com
contagens, lista de testes ignorados (com o motivo) e falhas. O relatório traz
só identificadores de teste, motivos e a primeira linha de cada falha, truncada,
e nunca ambiente, caminhos de usuário ou conteúdo de arquivos.

`--fail-on-skip TEXTO` (repetível) falha quando algum teste ignorado tiver
TEXTO no motivo. Os jobs que dizem exercitar extras opcionais (API, ByteTrack)
usam isso para que "skipped" não seja confundido com validação real.
Sem hardware, câmera, rede externa ou segredos.
"""

import argparse
import json
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
MAX_MESSAGE = 300


def _first_line(text: str) -> str:
    lines = [line for line in str(text).strip().splitlines() if line.strip()]
    line = lines[-1].strip() if lines else ""
    return line if len(line) <= MAX_MESSAGE else line[:MAX_MESSAGE - 1] + "…"


class RecordingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.skipped_records: list[dict] = []
        self.problem_records: list[dict] = []

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.skipped_records.append({"test": test.id(), "reason": str(reason)})

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.problem_records.append({"test": test.id(), "kind": "failure",
                                     "message": _first_line(self._exc_info_to_string(err, test))})

    def addError(self, test, err):
        super().addError(test, err)
        self.problem_records.append({"test": test.id(), "kind": "error",
                                     "message": _first_line(self._exc_info_to_string(err, test))})

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.problem_records.append({"test": test.id(), "kind": "unexpected_success", "message": ""})


def run_suite(start_dir: Path, *, top_level: Path | None = None, verbosity: int = 1,
              stream=None) -> tuple[RecordingResult, float]:
    loader = unittest.TestLoader()
    suite = loader.discover(str(start_dir), top_level_dir=str(top_level or start_dir))
    runner = unittest.TextTestRunner(stream=stream or sys.stderr, verbosity=verbosity,
                                     resultclass=RecordingResult)
    started = time.monotonic()
    result = runner.run(suite)
    return result, time.monotonic() - started


def build_report(result: RecordingResult, seconds: float, fail_on_skip=()) -> dict:
    blocked = [record for record in result.skipped_records
               if any(text in record["reason"] for text in fail_on_skip)]
    counts = {"run": result.testsRun, "failures": len(result.failures),
              "errors": len(result.errors), "skipped": len(result.skipped),
              "unexpected_successes": len(result.unexpectedSuccesses)}
    passed = (result.wasSuccessful() and not blocked)
    return {"passed": passed, "counts": counts, "seconds": round(seconds, 2),
            "skipped": result.skipped_records, "problems": result.problem_records,
            "forbidden_skips": blocked, "fail_on_skip": list(fail_on_skip)}


def render_markdown(report: dict, title: str = "Resultado dos testes") -> str:
    counts = report["counts"]
    lines = [f"## {title}", "",
             f"**{'Aprovado' if report['passed'] else 'Reprovado'}** em {report['seconds']} s", "",
             "| Executados | Falhas | Erros | Ignorados |", "|---|---|---|---|",
             f"| {counts['run']} | {counts['failures']} | {counts['errors']} | {counts['skipped']} |", ""]
    if report["problems"]:
        lines += ["### Falhas e erros", ""]
        lines += [f"- `{item['test']}` ({item['kind']}): {item['message']}" for item in report["problems"]]
        lines.append("")
    if report["forbidden_skips"]:
        lines += ["### Testes ignorados que deveriam ter rodado", ""]
        lines += [f"- `{item['test']}`: {item['reason']}" for item in report["forbidden_skips"]]
        lines.append("")
    if report["skipped"]:
        lines += [f"<details><summary>Testes ignorados ({len(report['skipped'])}): "
                  "dependência opcional ausente não é validação</summary>", ""]
        lines += [f"- `{item['test']}`: {item['reason']}" for item in report["skipped"]]
        lines += ["", "</details>", ""]
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-dir", type=Path, default=ROOT / "tests")
    parser.add_argument("--report-dir", type=Path, help="pasta de saída de report.json e report.md")
    parser.add_argument("--title", default="Resultado dos testes")
    parser.add_argument("--fail-on-skip", action="append", default=[], metavar="TEXTO",
                        help="falha se um teste ignorado tiver TEXTO no motivo")
    args = parser.parse_args(argv)
    result, seconds = run_suite(args.start_dir.resolve(), verbosity=2)
    report = build_report(result, seconds, args.fail_on_skip)
    if args.report_dir:
        args.report_dir.mkdir(parents=True, exist_ok=True)
        (args.report_dir / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (args.report_dir / "report.md").write_text(render_markdown(report, args.title), encoding="utf-8")
    for item in report["forbidden_skips"]:
        print(f"ERRO teste ignorado indevidamente: {item['test']}: {item['reason']}", file=sys.stderr)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
