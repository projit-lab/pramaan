import os
import subprocess
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


def get_git_short_sha() -> str:
    env_sha = os.environ.get("GIT_SHA") or os.environ.get("K_REVISION")
    if env_sha:
        return env_sha[:7]
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        ).strip()
        if out:
            return out
    except Exception:
        pass
    return "dev"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENV: Literal["local", "dev", "demo", "prod"] = "local"
    GCP_PROJECT: str = "pramaan-dev-515306"
    REGION: str = "asia-south1"
    KMS_KEY: str = (
        "projects/pramaan-dev-515306/locations/asia-south1/"
        "keyRings/pramaan/cryptoKeys/mandate-signer"
    )
    DEMO_MODE: bool = False
    ALLOW_TEST_SIGNER: bool = False
    USE_REAL_KMS_IN_LOCAL: bool = False
    # Local demo: write the live read model (holds, devices, payouts) to the real
    # Firestore with ADC, so the console shows what the local API does.
    USE_FIRESTORE_IN_LOCAL: bool = False
    FIRESTORE_EMULATOR_HOST: str | None = None
    ATTEST_PATCH_WINDOW_MONTHS: int = 12
    # Check every certificate in an enrolment chain against Google's live attestation
    # status list (cached 24 h). Outside ENV=local, enrolment is refused while the list
    # cannot be fetched; locally it falls back to "nothing revoked" with a warning.
    ATTEST_REVOCATION_LIVE: bool = True
    ANDROID_SIGNING_SHA256: str = "3313d44bb45e66849411470eeffa85a49a66bc9d1a9718a2463b98898d93d968"
    VERSION: str = get_git_short_sha()

    # M2 (Danish). The system of record: AlloyDB (PostgreSQL) in the cloud, e.g.
    # postgresql+psycopg://user:pass@host/pramaan. When unset and ENV=local, a SQLite
    # file in the gitignored .local/ directory is used instead.
    DATABASE_URL: str | None = None
    # Single tenant for the buildathon; every intent belongs to this company.
    COMPANY_ID: str = "co_acme"
    # How long an approver has to decide before the approval expires.
    APPROVAL_TTL_HOURS: int = 24
    # M2+: the department a payment belongs to when the caller does not say, and
    # how long an approval waits before it escalates to someone more senior.
    DEFAULT_DEPARTMENT_ID: str = "org_acme_ap"
    ESCALATE_AFTER_HOURS: int = 4


@lru_cache
def get_settings() -> Settings:
    return Settings()
