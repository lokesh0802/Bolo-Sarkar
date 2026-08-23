import logging

import uvicorn
from fastapi import FastAPI

from bolo.actions.api import router as actions_router
from bolo.actions.cases import list_cases
from bolo.bridge.govscheme import is_ready, warm_up
from bolo.config import settings
from bolo.telephony.routes import router as telephony_router
from bolo.voice.llm_api import router as llm_router

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Bolo Sarkar — Voice AI for Government Schemes")

app.include_router(llm_router)
app.include_router(telephony_router)
app.include_router(actions_router)


@app.on_event("startup")
def startup_warm_up_govscheme() -> None:
    """Load/build the GovScheme Chroma index via the sibling repo's own
    function (see bolo/bridge/govscheme.py) so the first live call doesn't
    eat the index-build latency."""
    try:
        warm_up()
    except Exception:
        logging.getLogger(__name__).exception(
            "GovScheme warm-up failed — service still starts, but replies "
            "may say the scheme search isn't ready yet"
        )


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "govscheme_bridge_ready": is_ready()}


@app.get("/cases")
def cases() -> list[dict]:
    """Inspect created cases — handy for judges/demo, not a real admin API."""
    return list_cases()


if __name__ == "__main__":
    uvicorn.run("bolo.main:app", host=settings.host, port=settings.port, reload=True)
