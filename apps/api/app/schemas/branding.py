from pydantic import BaseModel


class BrandingUpdateRequest(BaseModel):
    name: str
    logo_url: str = ""
