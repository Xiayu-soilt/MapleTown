from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.auth import User
from app.models.world import SimState
from app.schemas import SimControlIn, SimStateOut

router = APIRouter(prefix="/sim", tags=["simulation"])


def _get_state(db: Session) -> SimState:
    state = db.get(SimState, 1)
    if state is None:
        raise HTTPException(status_code=500, detail="模拟状态未初始化")
    return state


@router.get("/state", response_model=SimStateOut)
def get_state(db: Session = Depends(get_db)):
    state = _get_state(db)
    return SimStateOut(
        sim_time=state.sim_time,
        tick=state.tick,
        speed=state.speed,
        running=state.running,
        sim_day=state.current_sim_day,
    )


@router.post("/control")
def control(body: SimControlIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    state = _get_state(db)
    if body.action == "start":
        state.running = True
    elif body.action == "pause":
        state.running = False
    elif body.action == "speed":
        if body.value is None:
            raise HTTPException(status_code=422, detail="speed 需要提供 value")
        state.speed = body.value
    db.commit()
    return {"ok": True, "running": state.running, "speed": state.speed, "tick": state.tick}
