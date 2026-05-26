import uuid

from pydantic import BaseModel, ConfigDict


class AccountNameRead(BaseModel):
    """Shape liviano para GET /user/accounts_names — solo id + nombre."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class AccountNameRename(BaseModel):
    """Item del body para PUT /user/accounts_names — renombrar 1 cuenta."""

    id: uuid.UUID
    name: str
