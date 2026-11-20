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
    FIRESTORE_EMULATOR_HOST: str | None = None
    VERSION: str = get_git_short_sha()


@lru_cache
def get_settings() -> Settings:
    return Settings()
