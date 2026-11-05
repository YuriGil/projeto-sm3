#!/usr/bin/env python3
"""Safely remove regenerable Python caches and prepare this repository for GitHub."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR_NAMES = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
CACHE_FILE_SUFFIXES = {".pyc", ".pyo"}
SCAN_ROOTS = (
    "approval",
    "agents",
    "config",
    "contracts",
    "deployment",
    "diagnostics",
    "docs",
    "ingestion",
    "metrics",
    "ops_console",
    "orchestrator",
    "prompts",
    "publisher",
    "r21_orchestrator",
    "r25_relay",
    "r26_acquisition",
    "r29_audience",
    "r29_drift",
    "r29_feedback",
    "r29_observer",
    "r30_1_injection",
    "r30_2_capture",
    "r30_preedit",
    "renderer",
    "schemas",
    "scripts",
    "tests",
    "vision",
    "worker",
    "workflows",
)
GITIGNORE_START = "# BEGIN prepare_github.py"
GITIGNORE_END = "# END prepare_github.py"
GITIGNORE_RULES = """\
.venv/
venv/
__pycache__/
*.pyc
*.pyo
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
coverage.xml
.env
.env.*
!.env.example
**/config/bindings.json
**/config/google_drive_real_binding.json
trash/
.trash/
/state/
/runtime/
/sm3_backups/
/sm3_receipts/
/reports/
/authorized_external_sources/
/A11_A14_CANDIDATES/
/A11_A15_MEDIA/
/expanded_scene_clips/
/portable_clips/
/SM3_ART_DIRECTION_VARIANTS/
/SM3_PREVIEWS/
/SM3_PUBLICATION_CANDIDATES/
/SM3_R32_1_2_HUMAN_REVIEW_*/
/mpp_-win-g3010-1_04-ea34_2/
/provenance_fix_candidate_2_33_2/
/provenance_fix_successor_2_33_2/
/recovered_canonical_2_33_2/
*.mp4
*.jpg
*.jpeg
*.png
*.pdf
*.cab
*.zip
*.sqlite
*.sqlite3
*.db
*.log
*.bak
# Historical files with embedded session credentials; local copies are retained.
/archive/releases/PROJETO_SM3_07F_PREFLIGHT.ps1
/archive/releases/PROJETO_SM3_07F_VERIFY_PREVIEWS.ps1
/archive/releases/SM3_07F_PREPARAR_REVISAO_3.ps1
/archive/releases/SM3_07F_VERIFICAR_E_BAIXAR_PREVIEW_V2.ps1
/archive/releases/SM3_07F_VERIFICAR_E_BAIXAR_PREVIEW_V3.ps1
/archive/releases/SM3_07F_VERIFICAR_E_BAIXAR_PREVIEW_V5.ps1
/archive/releases/SM3_08A_REGISTRAR_REV4_FEEDBACK_NEGATIVO.ps1
/archive/releases/SM3_08B_BIND_DIRECTION_PROFILE.ps1
/archive/releases/SM3_08B_INSTALL_WORKER_2_10_0.ps1
/archive/releases/SM3_08B_VERIFICAR_PERFIS_E_APRENDIZADO.ps1
/archive/releases/SM3_08C_INSTALL_WORKER_2_11_0.ps1
/archive/releases/SM3_08C_VERIFICAR_GEOMETRIA.ps1
/archive/releases/SM3_08D_INSTALL_WORKER_2_12_0.ps1
/archive/releases/SM3_08E_INSTALL_WORKER_2_13_0.ps1
/archive/releases/SM3_08E_INSTALL_WORKER_2_13_0_R2.ps1
/archive/releases/SM3_08E_INSTALL_WORKER_2_13_1_R3.ps1
/archive/releases/SM3_08F_DIAGNOSTICAR_RENDER.ps1
/archive/releases/SM3_08F_INSTALL_WORKER_2_14_0.ps1
/archive/releases/SM3_08F_INSTALL_WORKER_2_14_1_R2.ps1
/archive/releases/SM3_08F_INSTALL_WORKER_2_14_1_R3.ps1
/archive/releases/SM3_08F_VERIFICAR_E_BAIXAR_VARIANTES.ps1
/archive/releases/SM3_08F_VERIFICAR_FEEDBACK_08E.ps1
/archive/releases/SM3_09A1_INSTALL_WORKER_2_15_1.ps1
/archive/releases/SM3_09A3_INSTALL_WORKER_2_16_1.ps1
/archive/releases/SM3_09A3_INSTALL_WORKER_2_16_1_R2.ps1
/archive/releases/SM3_09A4_INSTALL_WORKER_2_16_2.ps1
/archive/releases/SM3_09A_INSTALL_WORKER_2_15_0.ps1
/archive/releases/SM3_09B_INSTALL_WORKER_2_16_0.ps1
/archive/releases/SM3_09C_INSTALL_WORKER_2_17_0.ps1
/diagnostics/verify_workflow.py
/workflows/part4/PROJETO_SM3_07F_VERIFY_PREVIEWS.ps1
/workflows/part4/PROJETO_SM3_08C_SEMANTIC_GEOMETRY_v1_CURRENT_FIXTURE.json
"""


def run_git(*args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def repository_root() -> Path | None:
    result = run_git("rev-parse", "--show-toplevel")
    if result.returncode:
        return None
    return Path(result.stdout.strip()).resolve()


def cache_candidates() -> list[Path]:
    candidates: list[Path] = []

    root_cache = ROOT / "__pycache__"
    if root_cache.is_dir() and not root_cache.is_symlink():
        candidates.append(root_cache)

    for root_name in SCAN_ROOTS:
        scan_root = ROOT / root_name
        if not scan_root.is_dir():
            continue
        for current, dirs, files in os.walk(scan_root, followlinks=False):
            dirs[:] = [name for name in dirs if name != ".git"]
            current_path = Path(current)
            for name in list(dirs):
                if name in CACHE_DIR_NAMES:
                    cache_path = current_path / name
                    if not cache_path.is_symlink():
                        candidates.append(cache_path)
                    dirs.remove(name)
            for name in files:
                path = current_path / name
                if (
                    path.suffix.casefold() in CACHE_FILE_SUFFIXES
                    and not path.is_symlink()
                ):
                    candidates.append(path)

    return candidates


def update_gitignore() -> None:
    path = ROOT / ".gitignore"
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    start = content.find(GITIGNORE_START)
    end = content.find(GITIGNORE_END)

    if (start == -1) != (end == -1):
        raise RuntimeError(f"Marcadores incompletos em {path}")
    if start != -1 and end < start:
        raise RuntimeError(f"Marcadores fora de ordem em {path}")

    managed = f"{GITIGNORE_START}\n{GITIGNORE_RULES}{GITIGNORE_END}"
    if start != -1:
        end += len(GITIGNORE_END)
        updated = content[:start] + managed + content[end:]
    else:
        separator = "" if not content or content.endswith("\n") else "\n"
        updated = f"{content}{separator}{managed}\n"

    if updated != content:
        path.write_text(updated, encoding="utf-8", newline="\n")


def describe_git_state() -> None:
    root = repository_root()
    if root is None:
        print("Git: este diretório ainda não é um repositório.")
        return
    if root != ROOT:
        raise RuntimeError(
            f"O script está em {ROOT}, mas o Git raiz é {root}; "
            "não farei alterações fora da raiz do projeto."
        )

    branch = run_git("branch", "--show-current").stdout.strip() or "(sem branch)"
    remote = run_git("remote", "get-url", "origin")
    print(f"Git: já inicializado na branch {branch}.")
    print(
        f"origin: {remote.stdout.strip()}"
        if remote.returncode == 0
        else "origin: não configurado."
    )
    status = run_git("status", "--short", "--untracked-files=normal")
    if status.returncode:
        raise RuntimeError(status.stderr.strip() or "Não foi possível consultar o Git.")
    changed = [line for line in status.stdout.splitlines() if line.strip()]
    print(f"Alterações já existentes no worktree: {len(changed)}.")
    if changed:
        print("Elas serão preservadas e não serão adicionadas ao stage.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Relata caches Python descartáveis e prepara .gitignore. "
            "Sem --apply, não altera nem apaga arquivos."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="aplica a limpeza e atualiza .gitignore após confirmação",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="confirma a aplicação sem prompt (requer --apply)",
    )
    args = parser.parse_args()

    if args.yes and not args.apply:
        parser.error("--yes só pode ser usado junto com --apply")

    try:
        describe_git_state()
        candidates = cache_candidates()

        print("\nCaches Python descartáveis encontrados:")
        if candidates:
            for path in candidates:
                print(f"  {path.relative_to(ROOT)}")
        else:
            print("  nenhum")

        if not args.apply:
            print("\nPrévia concluída. Use --apply para confirmar as alterações.")
            return 0

        if not args.yes:
            answer = input(
                "\nApagar somente os caches listados e atualizar .gitignore? [s/N] "
            )
            if answer.strip().casefold() not in {"s", "sim"}:
                print("Cancelado; nenhum arquivo foi alterado.")
                return 0

        if repository_root() is None:
            run_git("init", "--initial-branch=main", check=True)
            print("Repositório Git inicializado na branch main.")

        update_gitignore()
        removed = 0
        for path in candidates:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            removed += 1

        print(f"\nConcluído: {removed} caches removidos e .gitignore atualizado.")
        print("Nenhum arquivo foi staged, commitado ou enviado ao GitHub.")
        return 0
    except FileNotFoundError as error:
        print(
            f"Erro: Git não está disponível no PATH ({error}).",
            file=sys.stderr,
        )
        return 1
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
