"""LangGraph Agent State Definition with Multi-Tenant RBAC Support

参考开源项目:
- multi-tenant-rbac: https://github.com/donchi4all/multi-tenant-rbac
- multi-tenant-saas-toolkit: https://github.com/lanemc/multi-tenant-saas-toolkit

核心设计原则:
1. 严格的组织隔离 - 所有数据必须关联 organization_id
2. RBAC 权限控制 - 支持 owner/member/viewer 等角色
3. 母账号可跨子账号管理 - 支持 parent_user_id 层级
4. 审计追踪 - 记录操作者和组织上下文
"""

from typing import Annotated, List, Dict, Any, Optional, Literal
from typing_extensions import TypedDict
from datetime import datetime
from dataclasses import dataclass, field
import operator


# ============ RBAC 权限定义 ============

class Permission:
    """权限常量定义"""
    # 用户管理权限
    USER_CREATE = "user:create"
    USER_READ = "user:read"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"
    
    # 子账号管理权限（仅母账号/owner）
    CHILD_CREATE = "child:create"
    CHILD_MANAGE = "child:manage"
    
    # 知识库权限
    KB_READ = "kb:read"
    KB_WRITE = "kb:write"
    KB_DELETE = "kb:delete"
    KB_ADMIN = "kb:admin"  # 管理组织内所有知识库
    
    # 报告/对话权限
    JOB_CREATE = "job:create"
    JOB_READ = "job:read"
    JOB_READ_ALL = "job:read:all"  # 读取组织内所有任务
    JOB_UPDATE = "job:update"
    JOB_DELETE = "job:delete"
    
    # 系统权限
    ORG_MANAGE = "org:manage"
    BILLING_MANAGE = "billing:manage"
    SETTINGS_MANAGE = "settings:manage"


class Role:
    """角色定义与权限映射"""
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"
    
    # 角色权限映射
    PERMISSIONS = {
        OWNER: [
            Permission.USER_CREATE, Permission.USER_READ, Permission.USER_UPDATE, Permission.USER_DELETE,
            Permission.CHILD_CREATE, Permission.CHILD_MANAGE,
            Permission.KB_READ, Permission.KB_WRITE, Permission.KB_DELETE, Permission.KB_ADMIN,
            Permission.JOB_CREATE, Permission.JOB_READ, Permission.JOB_READ_ALL, Permission.JOB_UPDATE, Permission.JOB_DELETE,
            Permission.ORG_MANAGE, Permission.BILLING_MANAGE, Permission.SETTINGS_MANAGE,
        ],
        ADMIN: [
            Permission.USER_READ, Permission.USER_UPDATE,
            Permission.CHILD_CREATE, Permission.CHILD_MANAGE,
            Permission.KB_READ, Permission.KB_WRITE, Permission.KB_DELETE, Permission.KB_ADMIN,
            Permission.JOB_CREATE, Permission.JOB_READ, Permission.JOB_READ_ALL, Permission.JOB_UPDATE, Permission.JOB_DELETE,
            Permission.SETTINGS_MANAGE,
        ],
        MEMBER: [
            Permission.USER_READ,
            Permission.KB_READ, Permission.KB_WRITE,
            Permission.JOB_CREATE, Permission.JOB_READ, Permission.JOB_UPDATE,
        ],
        VIEWER: [
            Permission.USER_READ,
            Permission.KB_READ,
            Permission.JOB_READ,
        ],
    }
    
    @classmethod
    def has_permission(cls, role: str, permission: str) -> bool:
        """检查角色是否拥有指定权限"""
        return permission in cls.PERMISSIONS.get(role, [])
    
    @classmethod
    def can_create_child(cls, role: str) -> bool:
        """是否可以创建子账号"""
        return cls.has_permission(role, Permission.CHILD_CREATE)
    
    @classmethod
    def can_manage_all_jobs(cls, role: str) -> bool:
        """是否可以查看/管理组织内所有任务"""
        return cls.has_permission(role, Permission.JOB_READ_ALL)


# ============ 用户与组织上下文 ============

@dataclass
class UserContext:
    """用户上下文 - 包含RBAC所需的完整用户信息"""
    user_id: str
    organization_id: str
    role: str = Role.MEMBER
    parent_user_id: Optional[str] = None  # 母账号ID（如果是子账号）
    is_child_account: bool = False
    permissions: List[str] = field(default_factory=list)
    
    # 审计字段
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
    
    def has_permission(self, permission: str) -> bool:
        """检查用户是否拥有指定权限"""
        if permission in self.permissions:
            return True
        return Role.has_permission(self.role, permission)
    
    def can_access_organization(self, org_id: str) -> bool:
        """检查是否可以访问指定组织"""
        return self.organization_id == org_id
    
    def is_owner_or_admin(self) -> bool:
        """是否是组织所有者或管理员"""
        return self.role in [Role.OWNER, Role.ADMIN]


# ============ Agent 状态定义 ============

class ReportState(TypedDict):
    """LangGraph 报告生成状态 - 增强多租户支持"""
    
    # ============ 用户与组织上下文（RBAC核心） ============
    user_context: Optional[UserContext]  # 完整的用户上下文
    user_id: Optional[str]              # 用户ID（向后兼容）
    organization_id: Optional[str]      # 组织ID（租户隔离）
    parent_user_id: Optional[str]       # 母账号ID（子账号支持）
    role: Optional[str]                 # 用户角色
    
    # 审计追踪
    created_by: Optional[str]           # 创建者ID
    created_at: Optional[str]           # 创建时间ISO格式
    accessed_by: Annotated[List[str], operator.add]  # 访问记录
    
    # ============ 任务相关 ============
    query: str                          # 用户查询
    job_id: Optional[str]               # 任务ID
    job_type: Optional[Literal["report", "chat", "analysis"]]  # 任务类型
    
    # ============ Planner 产出 ============
    plan: Optional[Dict[str, Any]]      # 执行计划
    
    # ============ 检索与流水线 ============
    keywords: Optional[List[str]]       # 提取的关键词
    collected_docs: Annotated[List[Dict], operator.add]      # 原始检索文档
    cleaned_docs: Annotated[List[Dict], operator.add]        # 清洗后文档
    deduplicated_docs: Annotated[List[Dict], operator.add]   # 去重后文档
    classified_docs: Optional[Dict[str, List[Dict]]]         # 分类后文档
    
    # ============ 报告生成 ============
    sections: Optional[Dict[str, str]]           # 各章节内容
    citations: Optional[Dict[str, List[Dict]]]   # 引用信息
    charts: Optional[List[Dict]]                 # 图表数据
    markdown: Optional[str]                      # 完整Markdown
    final_report: Optional[str]                  # 最终报告
    
    # ============ 多轮对话支持 ============
    messages: Annotated[List[Dict], operator.add]            # 对话历史
    conversation_memory: Optional[str]                       # 对话记忆摘要
    
    # ============ 合规与校验 ============
    needs_human: bool                            # 是否需要人工审核
    grounded_score: Optional[float]              #  groundedness 分数
    consistency_score: Optional[float]           # 跨章节一致性分数
    has_contradiction: bool                      # 是否存在矛盾
    contradictions: Optional[List[Dict]]         # 矛盾详情列表
    repeated_content: Optional[List[str]]        # 重复内容列表
    consistency_suggestions: Optional[List[str]] # 一致性改进建议
    
    # ============ 错误与状态 ============
    error: Optional[str]                         # 错误信息
    current_step: Optional[str]                  # 当前执行步骤
    progress: Optional[float]                    # 进度百分比
    trajectory: Optional[List[Dict]]             # Agent 执行轨迹


def create_initial_state(
    query: str,
    user_context: UserContext,
    job_id: Optional[str] = None,
    job_type: Literal["report", "chat", "analysis"] = "report"
) -> ReportState:
    """创建初始状态 - 强制要求用户上下文
    
    Args:
        query: 用户查询
        user_context: 完整的用户上下文（包含RBAC信息）
        job_id: 可选的任务ID
        job_type: 任务类型
    
    Returns:
        初始化后的 ReportState
    """
    now = datetime.utcnow().isoformat()
    
    return ReportState(
        # 用户与组织上下文
        user_context=user_context,
        user_id=user_context.user_id,
        organization_id=user_context.organization_id,
        parent_user_id=user_context.parent_user_id,
        role=user_context.role,
        
        # 审计
        created_by=user_context.user_id,
        created_at=now,
        accessed_by=[user_context.user_id],
        
        # 任务
        query=query,
        job_id=job_id,
        job_type=job_type,
        
        # 其他初始值
        plan=None,
        keywords=None,
        collected_docs=[],
        cleaned_docs=[],
        deduplicated_docs=[],
        classified_docs=None,
        sections=None,
        citations=None,
        charts=None,
        markdown=None,
        final_report=None,
        messages=[],
        conversation_memory=None,
        needs_human=False,
        grounded_score=None,
        consistency_score=None,
        has_contradiction=False,
        contradictions=None,
        repeated_content=None,
        consistency_suggestions=None,
        error=None,
        current_step="initialized",
        progress=0.0,
        trajectory=[],
    )


# ============ 知识库访问控制 ============

@dataclass
class KBAccessControl:
    """知识库访问控制策略"""
    
    @staticmethod
    def can_read(user_context: UserContext, doc_organization_id: str) -> bool:
        """检查用户是否有权限读取知识库文档"""
        return user_context.organization_id == doc_organization_id
    
    @staticmethod
    def can_write(user_context: UserContext, doc_organization_id: Optional[str] = None) -> bool:
        """检查用户是否有权限写入知识库"""
        if not user_context.has_permission(Permission.KB_WRITE):
            return False
        # 如果是更新操作，检查文档所属组织
        if doc_organization_id:
            return user_context.organization_id == doc_organization_id
        return True
    
    @staticmethod
    def can_delete(user_context: UserContext, doc_organization_id: str) -> bool:
        """检查用户是否有权限删除知识库文档"""
        if not user_context.has_permission(Permission.KB_DELETE):
            return False
        return user_context.organization_id == doc_organization_id
    
    @staticmethod
    def can_admin(user_context: UserContext) -> bool:
        """检查用户是否有知识库管理权限（查看组织内所有文档）"""
        return user_context.has_permission(Permission.KB_ADMIN)


# ============ 任务访问控制 ============

@dataclass
class JobAccessControl:
    """任务/对话访问控制策略"""
    
    @staticmethod
    def can_read(
        user_context: UserContext,
        job_owner_id: str,
        job_organization_id: str
    ) -> bool:
        """检查用户是否有权限读取任务/对话
        
        规则:
        1. 必须属于同一组织
        2. 如果是子账号，只能看自己的；owner/admin 可以看组织内所有
        """
        # 组织隔离检查
        if user_context.organization_id != job_organization_id:
            return False
        
        # 自己创建的任务总是可以访问
        if user_context.user_id == job_owner_id:
            return True
        
        # owner/admin 可以访问组织内所有任务
        if Role.can_manage_all_jobs(user_context.role):
            return True
        
        # 子账号不能访问其他账号的任务
        return False
    
    @staticmethod
    def can_create(user_context: UserContext) -> bool:
        """检查用户是否有权限创建任务"""
        return user_context.has_permission(Permission.JOB_CREATE)
    
    @staticmethod
    def can_update(
        user_context: UserContext,
        job_owner_id: str,
        job_organization_id: str
    ) -> bool:
        """检查用户是否有权限更新任务"""
        if user_context.organization_id != job_organization_id:
            return False
        
        # 只能更新自己的任务，或拥有全局权限
        if user_context.user_id == job_owner_id:
            return user_context.has_permission(Permission.JOB_UPDATE)
        
        # owner/admin 可以更新组织内任务
        if Role.can_manage_all_jobs(user_context.role):
            return user_context.has_permission(Permission.JOB_UPDATE)
        
        return False
    
    @staticmethod
    def can_delete(
        user_context: UserContext,
        job_owner_id: str,
        job_organization_id: str
    ) -> bool:
        """检查用户是否有权限删除任务"""
        if user_context.organization_id != job_organization_id:
            return False
        
        # 只能删除自己的任务，或拥有全局权限
        if user_context.user_id == job_owner_id:
            return user_context.has_permission(Permission.JOB_DELETE)
        
        # owner/admin 可以删除组织内任务
        if Role.can_manage_all_jobs(user_context.role):
            return user_context.has_permission(Permission.JOB_DELETE)
        
        return False


# ============ 子账号管理 ============

@dataclass
class ChildAccountManager:
    """子账号管理工具"""
    
    @staticmethod
    def can_create_child(parent_context: UserContext) -> bool:
        """检查是否可以创建子账号"""
        return Role.can_create_child(parent_context.role)
    
    @staticmethod
    def can_manage_child(
        parent_context: UserContext,
        child_organization_id: str,
        child_parent_id: Optional[str]
    ) -> bool:
        """检查是否可以管理子账号
        
        规则:
        1. 必须属于同一组织
        2. 必须是被管理子账号的母账号
        3. 或拥有组织管理权限
        """
        if parent_context.organization_id != child_organization_id:
            return False
        
        # 是子账号的母账号
        if child_parent_id and parent_context.user_id == child_parent_id:
            return True
        
        # owner/admin 可以管理组织内所有子账号
        if parent_context.is_owner_or_admin():
            return True
        
        return False
    
    @staticmethod
    def get_child_permissions(parent_role: str) -> List[str]:
        """获取子账号的默认权限列表
        
        子账号默认权限比母账号低一级
        """
        if parent_role == Role.OWNER:
            # owner 创建的子账号可以是 admin/member/viewer
            return Role.PERMISSIONS[Role.ADMIN]
        elif parent_role == Role.ADMIN:
            # admin 创建的子账号最多是 member
            return Role.PERMISSIONS[Role.MEMBER]
        else:
            # member/viewer 不能创建子账号
            return []


# ============ 工具函数 ============

def filter_by_organization(
    items: List[Dict[str, Any]],
    organization_id: str,
    org_field: str = "organization_id"
) -> List[Dict[str, Any]]:
    """按组织ID过滤数据列表
    
    Args:
        items: 数据列表
        organization_id: 组织ID
        org_field: 组织ID字段名
    
    Returns:
        过滤后的列表
    """
    return [item for item in items if item.get(org_field) == organization_id]


def add_organization_filter(
    query_params: Dict[str, Any],
    user_context: UserContext
) -> Dict[str, Any]:
    """为查询参数添加组织过滤条件
    
    Args:
        query_params: 原始查询参数
        user_context: 用户上下文
    
    Returns:
        添加组织过滤后的查询参数
    """
    query_params = query_params.copy()
    query_params["organization_id"] = user_context.organization_id
    return query_params


def audit_log(
    action: str,
    user_context: UserContext,
    resource_type: str,
    resource_id: Optional[str] = None,
    details: Optional[Dict] = None
) -> Dict[str, Any]:
    """生成审计日志记录
    
    Args:
        action: 操作类型
        user_context: 用户上下文
        resource_type: 资源类型
        resource_id: 资源ID
        details: 详细信息
    
    Returns:
        审计日志记录
    """
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "action": action,
        "user_id": user_context.user_id,
        "organization_id": user_context.organization_id,
        "role": user_context.role,
        "is_child_account": user_context.is_child_account,
        "parent_user_id": user_context.parent_user_id,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "details": details or {},
        "ip_address": user_context.ip_address,
        "session_id": user_context.session_id,
    }
