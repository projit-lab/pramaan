"""GET /v1/mandates/{mandateId} (contracts/openapi.yaml, getMandate).

Public on purpose: an auditor or payee must be able to check a mandate they were
handed, with no sign-in. It serves exactly what Prajit's mandate service stored;
the countersignature is checked by the reader against GET /keys/countersign."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path

from app.db.engine import unit_of_work
from app.db.models import Mandate
from app.errors import ProblemException
from app.runtime import Runtime, get_runtime

router = APIRouter(tags=["mandates"])


@router.get("/mandates/{mandateId}", operation_id="getMandate")
def get_mandate(
    mandate_id: Annotated[str, Path(alias="mandateId", pattern=r"^pm_[A-Za-z0-9]+$")],
    rt: Runtime = Depends(get_runtime),
):
    with unit_of_work(rt.sessions) as s:
        m = s.get(Mandate, mandate_id)
        if m is None:
            raise ProblemException(404, "Mandate not found", "No mandate with this id.")
        return m.document
