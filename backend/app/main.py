import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.sdk import router as sdk_router
from app.api.prices import router as prices_router
from app.api.account import router as account_router
from app.api.spot import router as spot_router
from app.api.futures import router as futures_router
from app.api.amm import router as amm_router
from app.services.price_engine import price_update_loop
from app.websocket.broadcaster import manager

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(price_update_loop())
    yield
    task.cancel()


app = FastAPI(title="Agent Metaverse Virtual Exchange", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(sdk_router)
app.include_router(prices_router)
app.include_router(account_router)
app.include_router(spot_router)
app.include_router(futures_router)
app.include_router(amm_router)


@app.websocket("/ws/prices")
async def ws_prices(websocket: WebSocket):
    await manager.connect("prices", websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect("prices", websocket)


@app.get("/health")
async def health():
    return {"status": "ok"}
