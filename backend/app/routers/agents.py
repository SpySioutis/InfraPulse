"""Agent lifecycle (user-facing): registration tokens, status, revocation.

Token plaintext is returned exactly once at issuance and never stored.
Rotation = revoke + issue a fresh token.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import auth, security
from app.database import get_db
from app.models import Agent, RegistrationToken, Server, User
from app.schemas import AgentOut, RegistrationOut

router = APIRouter(tags=["agents"])

REGISTRATION_TTL_HOURS = 24


def _agent_out(agent: Agent, db: Session) -> AgentOut:
    payload = AgentOut.model_validate(agent)
    server = db.get(Server, agent.server_id)
    payload.server_name = server.name if server else None
    return payload


@router.get("/agents", response_model=list[AgentOut])
def list_agents(user: User = Depends(auth.get_current_user), db: Session = Depends(get_db)) -> list[AgentOut]:
    return [_agent_out(a, db) for a in db.query(Agent).order_by(Agent.created_at.desc()).all()]


@router.get("/agents/{agent_id}", response_model=AgentOut)
def get_agent(
    agent_id: str, user: User = Depends(auth.get_current_user), db: Session = Depends(get_db)
) -> AgentOut:
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found.")
    return _agent_out(agent, db)


@router.post("/servers/{server_id}/registration-token", response_model=RegistrationOut, status_code=201)
def issue_registration_token(
    server_id: str, user: User = Depends(auth.get_current_user), db: Session = Depends(get_db)
) -> RegistrationOut:
    server = db.get(Server, server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="Server not found.")
    plaintext, digest = security.generate_agent_token()
    record = RegistrationToken(
        server_id=server.id,
        token_hash=digest,
        token_prefix=plaintext[:8],
        expires_at=datetime.now(timezone.utc) + timedelta(hours=REGISTRATION_TTL_HOURS),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    auth.audit(db, user, "agent.registration_issue", "server", server.id, server.name)
    return RegistrationOut(
        server_id=server.id,
        registration_token=plaintext,
        expires_at=record.expires_at,
    )


@router.delete("/agents/{agent_id}", status_code=204)
def revoke_agent(
    agent_id: str, user: User = Depends(auth.require_admin), db: Session = Depends(get_db)
) -> None:
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found.")
    agent.status = "revoked"
    db.commit()
    auth.audit(db, user, "agent.revoke", "agent", agent_id, agent.server_id)
