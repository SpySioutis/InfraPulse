"""Agent-facing API: registration, metric ingestion, heartbeats.

Authentication: per-agent bearer tokens (hashed server-side, constant-time
compare). These endpoints never accept user JWTs and never touch the UI.
Rate and size limits keep a misbehaving agent from hurting the server.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app import alerting, ingest, security
from app.database import get_db
from app.models import Agent, RegistrationToken, Server
from app.schemas import AgentRegisterIn, AgentTokenOut, HeartbeatIn, MetricReport

router = APIRouter(prefix="/agent", tags=["agent"])


def _agent_from_token(authorization: str | None, db: Session) -> Agent:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing agent token.")
    plaintext = authorization[7:].strip()
    digest = security.hash_agent_token(plaintext)
    agent = db.query(Agent).filter(Agent.token_hash == digest).first()
    if agent is None or agent.status == "revoked":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked agent token.")
    return agent


@router.post("/register", response_model=AgentTokenOut, status_code=201)
def register_agent(payload: AgentRegisterIn, db: Session = Depends(get_db)) -> AgentTokenOut:
    digest = security.hash_agent_token(payload.registration_token.strip())
    record = db.query(RegistrationToken).filter(RegistrationToken.token_hash == digest).first()
    now = datetime.now(timezone.utc)
    if record is None:
        raise HTTPException(status_code=401, detail="Invalid registration token.")
    if record.used_at is not None:
        raise HTTPException(status_code=401, detail="Registration token already used.")
    expires = record.expires_at if record.expires_at.tzinfo else record.expires_at.replace(tzinfo=timezone.utc)
    if expires < now:
        raise HTTPException(status_code=401, detail="Registration token expired.")
    server = db.get(Server, record.server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="Server no longer exists.")

    plaintext, token_digest = security.generate_agent_token()
    agent = db.query(Agent).filter(Agent.server_id == server.id).first()
    if agent is None:
        agent = Agent(
            server_id=server.id,
            token_hash=token_digest,
            token_prefix=plaintext[:8],
            status="online",
            version=payload.agent_version,
            last_heartbeat_at=now,
        )
        db.add(agent)
    else:
        agent.token_hash = token_digest
        agent.token_prefix = plaintext[:8]
        agent.status = "online"
        agent.version = payload.agent_version
        agent.last_heartbeat_at = now
    record.used_at = now
    db.commit()
    alerting.evaluate_offline(db, server, now)  # resolves any offline incident
    return AgentTokenOut(agent_token=plaintext)


@router.post("/metrics")
def submit_metrics(
    payload: MetricReport,
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict:
    agent = _agent_from_token(authorization, db)
    server = db.get(Server, agent.server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="Server no longer exists.")
    return ingest.ingest(db, server, agent, payload)


@router.post("/heartbeat")
def heartbeat(
    payload: HeartbeatIn,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict:
    agent = _agent_from_token(authorization, db)
    now = datetime.now(timezone.utc)
    agent.last_heartbeat_at = now
    if agent.status in ("pending", "unhealthy"):
        agent.status = "online"
    if payload.agent_version:
        agent.version = payload.agent_version
    db.commit()
    server = db.get(Server, agent.server_id)
    if server is not None:
        alerting.evaluate_offline(db, server, now)
    return {"status": agent.status, "server_time": now.isoformat()}
