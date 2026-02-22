from pydantic import BaseModel


class UserRegister(BaseModel):
    username: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AgentRegister(BaseModel):
    name: str
    description: str = ""


class AgentRegisterResponse(BaseModel):
    api_key: str
    agent_id: str
    initial_balance: float
    currency: str = "USDT"
