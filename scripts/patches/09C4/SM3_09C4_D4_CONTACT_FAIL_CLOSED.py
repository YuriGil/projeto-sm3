from pathlib import Path
from datetime import datetime
import shutil

worker = Path(r"D:\MOLOTOV_SOCIAL_OS_RC7\worker\worker_service.py")
backup_dir = Path(r"D:\MOLOTOV_SOCIAL_OS_RC7\sm3_backups")

text = worker.read_text(encoding="utf-8-sig")

old = """    contact_path=str(rec.get('contact_sheet_path') or '').strip()
    contact_sha=str(rec.get('contact_sheet_sha256') or '').lower()
    if contact_path and contact_sha:
        cp=Path(contact_path)
        if cp.exists() and cp.is_file() and sha256_file(cp).lower()!=contact_sha:
            raise HTTPException(409,'REFERENCE_MECHANICAL_CONTACT_SHEET_HASH_MISMATCH')
    return rec
"""

new = """    contact_path=str(rec.get('contact_sheet_path') or '').strip()
    contact_sha=str(rec.get('contact_sheet_sha256') or '').lower()

    if not contact_path:
        raise HTTPException(
            409,
            'REFERENCE_MECHANICAL_CONTACT_SHEET_REF_MISSING'
        )

    if not re.fullmatch(r'[a-f0-9]{64}',contact_sha):
        raise HTTPException(
            409,
            'REFERENCE_MECHANICAL_CONTACT_SHEET_HASH_INVALID'
        )

    cp=_ensure_under(Path(contact_path),CONTACTS)

    if not cp.exists() or not cp.is_file():
        raise HTTPException(
            409,
            'REFERENCE_MECHANICAL_CONTACT_SHEET_MISSING'
        )

    if sha256_file(cp).lower()!=contact_sha:
        raise HTTPException(
            409,
            'REFERENCE_MECHANICAL_CONTACT_SHEET_HASH_MISMATCH'
        )

    return rec
"""

count = text.count(old)

print(f"CONTACT_VERIFIER_ANCHOR_COUNT={count}")

if count != 1:
    raise SystemExit(
        f"SM3_D4_CONTACT_VERIFIER_ANCHOR_INVALID:{count}"
    )

patched = text.replace(old,new,1)

# Garantir que continuamos na versão esperada.
if 'WORKER_VERSION = "2.20.0"' not in patched:
    raise SystemExit("SM3_D4_VERSION_2_20_0_NOT_FOUND")

# Fail-closed precisa conter os quatro estados.
required = (
    "REFERENCE_MECHANICAL_CONTACT_SHEET_REF_MISSING",
    "REFERENCE_MECHANICAL_CONTACT_SHEET_HASH_INVALID",
    "REFERENCE_MECHANICAL_CONTACT_SHEET_MISSING",
    "REFERENCE_MECHANICAL_CONTACT_SHEET_HASH_MISMATCH",
)

for marker in required:
    if marker not in patched:
        raise SystemExit(
            f"SM3_D4_REQUIRED_MARKER_MISSING:{marker}"
        )

# Validação sintática ANTES da escrita.
compile(patched,str(worker),"exec")

stamp=datetime.now().strftime("%Y%m%d_%H%M%S")
backup=backup_dir/f"worker_2_20_0_pre_contact_failclosed_{stamp}.py"

backup_dir.mkdir(parents=True,exist_ok=True)
shutil.copy2(worker,backup)

worker.write_text(
    patched,
    encoding="utf-8"
)

print(f"BACKUP={backup}")
print("CONTACT_REF_REQUIRED=True")
print("CONTACT_HASH_REQUIRED=True")
print("CONTACT_FILE_REQUIRED=True")
print("CONTACT_HASH_VERIFIED=True")
print()
print("SM3_09C4_D4_CONTACT_FAIL_CLOSED_PASS")
