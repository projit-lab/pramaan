from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.adapters.signer import get_mandate_signer
from app.config import Settings, get_settings
from app.domain.protocols import MandateSigner

router = APIRouter(tags=["mandates"])


class CountersignKeyResponse(BaseModel):
    pem: str
    algorithm: str = "EC_SIGN_P256_SHA256"
    key_version: str


@router.get("/keys/countersign", response_model=CountersignKeyResponse)
async def get_countersign_key(settings: Settings = Depends(get_settings)):
    """Returns the KMS public key so clients and verifiers can verify countersignatures."""
    signer: MandateSigner = get_mandate_signer(settings)
    pem, key_version = signer.get_public_key_pem()
    return CountersignKeyResponse(
        pem=pem,
        algorithm="EC_SIGN_P256_SHA256",
        key_version=key_version,
    )
