from pydantic import BaseModel, Field


class BrandingUpdateRequest(BaseModel):
    """单位名称最长 255（与 organizations.name 一致）；Logo 可留空。"""

    name: str = Field(..., min_length=1, max_length=255)
    # 支持 https 链接或 data:image/...;base64,...（前端粘贴/上传图片）
    logo_url: str = Field(default="", max_length=2_500_000)
