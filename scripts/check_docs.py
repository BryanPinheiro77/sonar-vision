"""Verificações determinísticas de documentação (#29): `python scripts/check_docs.py`.

Só usa a biblioteca padrão, não acessa a rede e não lê segredos. Confere:

- links relativos de Markdown (arquivo e âncora) e imagens locais;
- arquivos JSON em `docs/` (sintaxe válida e chaves não duplicadas);
- ADRs: número único, índice em `docs/decisions/README.md` completo e sem
  entradas órfãs;
- índice `docs/README.md` cobrindo todo `docs/*.md`.

Links externos (http/https) não são consultados: dependeriam da rede e
tornariam o resultado não reproduzível.
"""

import argparse
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", ".local", "models", "results", "runs",
             "__pycache__", ".pytest_cache", ".ruff_cache"}
FENCE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE = re.compile(r"`[^`\n]*`")
LINK = re.compile(r"!?\[(?:[^\[\]]|\[[^\]]*\])*\]\(\s*(<[^>]*>|[^)\s]*)(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
EXTERNAL = re.compile(r"^(?:[a-zA-Z][a-zA-Z0-9+.-]*:|//)")
ADR_FILE = re.compile(r"^(\d{4})-.+\.md$")


def markdown_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.md")
                  if not SKIP_DIRS.intersection(path.relative_to(root).parts))


def strip_code(text: str, keep_inline: bool = False) -> list[tuple[int, str]]:
    """Linhas fora de blocos de código, com o número da linha.

    Trechos em crase são removidos, salvo com `keep_inline`: títulos precisam
    do texto do código para calcular a âncora (`slug` tira só as crases).
    """
    lines, fenced = [], False
    for number, line in enumerate(text.splitlines(), 1):
        if FENCE.match(line):
            fenced = not fenced
            continue
        if not fenced:
            lines.append((number, line if keep_inline else INLINE_CODE.sub("", line)))
    return lines


def slug(heading: str) -> str:
    """Âncora no estilo do GitHub: minúsculas, sem pontuação, espaços viram hífen."""
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", heading)
    text = INLINE_CODE.sub(lambda match: match.group(0).strip("`"), text).strip().lower()
    text = re.sub(r"[^\w\- ]", "", text, flags=re.UNICODE)
    return text.replace(" ", "-")


def anchors(path: Path, cache: dict) -> set[str]:
    if path not in cache:
        found, seen = set(), {}
        for _, line in strip_code(path.read_text(encoding="utf-8"), keep_inline=True):
            match = HEADING.match(line)
            if match:
                base = slug(match.group(2))
                count = seen.get(base, 0)
                seen[base] = count + 1
                found.add(base if count == 0 else f"{base}-{count}")
        cache[path] = found
    return cache[path]


def check_links(root: Path, files: list[Path]) -> list[str]:
    problems, cache = [], {}
    for path in files:
        for number, line in strip_code(path.read_text(encoding="utf-8")):
            for match in LINK.finditer(line):
                target = match.group(1).strip("<>")
                if not target or EXTERNAL.match(target):
                    continue
                where = f"{path.relative_to(root).as_posix()}:{number}"
                file_part, _, fragment = target.partition("#")
                resolved = path if not file_part else (path.parent / unquote(file_part)).resolve()
                try:
                    resolved.relative_to(root.resolve())
                except ValueError:
                    problems.append(f"{where}: link sai do repositório: {target}")
                    continue
                if not resolved.exists():
                    problems.append(f"{where}: alvo inexistente: {target}")
                elif fragment and resolved.suffix == ".md" and resolved.is_file():
                    if unquote(fragment).lower() not in anchors(resolved, cache):
                        problems.append(f"{where}: âncora inexistente: {target}")
    return problems


def _no_duplicates(pairs):
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("chave duplicada")
    return dict(pairs)


def check_json(root: Path) -> list[str]:
    problems = []
    docs = root / "docs"
    for path in sorted(docs.rglob("*.json")) if docs.is_dir() else []:
        try:
            json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_no_duplicates,
                       parse_constant=lambda name: (_ for _ in ()).throw(ValueError("NaN/Infinity")))
        except (ValueError, OSError) as error:
            problems.append(f"{path.relative_to(root).as_posix()}: JSON inválido: {error}")
    return problems


def check_adrs(root: Path) -> list[str]:
    folder = root / "docs" / "decisions"
    if not folder.is_dir():
        return []
    problems, numbers, files = [], {}, []
    for path in sorted(folder.glob("*.md")):
        match = ADR_FILE.match(path.name)
        if match:
            files.append(path.name)
            numbers.setdefault(match.group(1), []).append(path.name)
    for number, names in numbers.items():
        if len(names) > 1:
            problems.append(f"docs/decisions: número {number} repetido: {', '.join(names)}")
    index = folder / "README.md"
    listed = set()
    if index.is_file():
        for _, line in strip_code(index.read_text(encoding="utf-8")):
            for match in LINK.finditer(line):
                listed.add(unquote(match.group(1).partition("#")[0]))
    else:
        problems.append("docs/decisions/README.md ausente")
    for name in files:
        if name not in listed:
            problems.append(f"docs/decisions/README.md: ADR fora do índice: {name}")
    for name in sorted(listed):
        if ADR_FILE.match(name) and name not in files:
            problems.append(f"docs/decisions/README.md: entrada sem arquivo: {name}")
    return problems


def check_docs_index(root: Path) -> list[str]:
    docs = root / "docs"
    index = docs / "README.md"
    if not index.is_file():
        return []
    listed = set()
    for _, line in strip_code(index.read_text(encoding="utf-8")):
        for match in LINK.finditer(line):
            listed.add(unquote(match.group(1).partition("#")[0]))
    return [f"docs/README.md: documento fora do índice: {path.name}"
            for path in sorted(docs.glob("*.md"))
            if path.name != "README.md" and path.name not in listed]


def run(root: Path) -> list[str]:
    files = markdown_files(root)
    return check_links(root, files) + check_json(root) + check_adrs(root) + check_docs_index(root)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    problems = run(args.root.resolve())
    for problem in problems:
        print(f"ERRO {problem}", file=sys.stderr)
    count = len(markdown_files(args.root.resolve()))
    print(f"check_docs: {count} arquivos Markdown, {len(problems)} problema(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
