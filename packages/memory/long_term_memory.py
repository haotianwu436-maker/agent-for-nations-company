"""Long-term Memory System for RAG Agent

参考开源项目:
- Mem0 (https://github.com/mem0ai/mem0) - 个性化AI记忆层
- LangMem (https://github.com/langchain-ai/langmem) - LangChain长期记忆

核心功能:
1. 记忆提取 - 从对话中提取用户偏好、关键信息
2. 记忆存储 - 使用Redis存储结构化记忆
3. 记忆召回 - 根据查询召回相关记忆
4. 记忆管理 - 增删改查记忆条目
"""

import json
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import redis
from redis.connection import ConnectionPool
import os


@dataclass
class MemoryEntry:
    """记忆条目"""
    id: str
    user_id: str
    organization_id: str
    content: str  # 记忆内容
    memory_type: str  # "preference", "fact", "context", "instruction"
    source_query: str  # 来源查询
    source_response: str  # 来源回复
    importance_score: float  # 重要性分数 0-1
    created_at: str
    updated_at: str
    access_count: int = 0
    last_accessed_at: Optional[str] = None
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class MemoryExtractor:
    """记忆提取器 - 从对话中提取关键信息"""
    
    EXTRACTION_PROMPT = """请从以下对话中提取关键信息，作为长期记忆存储。

用户查询: {query}
助手回复: {response}

请提取以下类型的信息（JSON格式）:
1. preference - 用户偏好、喜好、习惯
2. fact - 用户提到的关键事实、背景信息
3. context - 上下文信息，有助于理解用户需求
4. instruction - 用户明确给出的指令或要求

输出格式:
{{
  "memories": [
    {{
      "type": "preference|fact|context|instruction",
      "content": "提取的记忆内容",
      "importance": 0.8,
      "tags": ["标签1", "标签2"]
    }}
  ]
}}

如果无重要信息可提取，返回 {{"memories": []}}"""

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or os.getenv("LITELLM_MODEL", "")
        self.api_key = os.getenv("LITELLM_API_KEY", "")
        self.base_url = os.getenv("LITELLM_BASE_URL")

    def extract(self, query: str, response: str) -> List[Dict[str, Any]]:
        """从对话中提取记忆"""
        if not self.model_name or not self.api_key or self.api_key == "replace_me":
            # 降级：使用简单规则提取
            return self._rule_based_extract(query, response)
        
        try:
            from litellm import completion
            
            prompt = self.EXTRACTION_PROMPT.format(query=query, response=response)
            resp = completion(
                model=self.model_name,
                api_key=self.api_key,
                base_url=self.base_url,
                messages=[
                    {"role": "system", "content": "你是专业的信息提取助手。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=500,
                timeout=30,
            )
            
            content = resp.choices[0].message.content or ""
            # 清理JSON
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            data = json.loads(content)
            return data.get("memories", [])
        except Exception as e:
            print(f"[MemoryExtractor] LLM extraction failed: {e}")
            return self._rule_based_extract(query, response)
    
    def _rule_based_extract(self, query: str, response: str) -> List[Dict[str, Any]]:
        """基于规则的简单提取（降级方案）"""
        memories = []
        
        # 提取偏好关键词
        preference_keywords = ["喜欢", "偏好", "习惯", "常用", "总是", "经常"]
        for keyword in preference_keywords:
            if keyword in query:
                memories.append({
                    "type": "preference",
                    "content": f"用户提到: {query[:100]}",
                    "importance": 0.6,
                    "tags": ["preference", "user_input"]
                })
                break
        
        return memories


class LongTermMemory:
    """长期记忆管理器"""
    
    def __init__(self, 
                 redis_host: Optional[str] = None,
                 redis_port: Optional[int] = None,
                 redis_db: int = 0,
                 redis_password: Optional[str] = None):
        """初始化长期记忆系统
        
        Args:
            redis_host: Redis主机地址
            redis_port: Redis端口
            redis_db: Redis数据库编号
            redis_password: Redis密码
        """
        host = redis_host or os.getenv("REDIS_HOST", "localhost")
        port = redis_port or int(os.getenv("REDIS_PORT", "6379"))
        password = redis_password or os.getenv("REDIS_PASSWORD") or None
        
        try:
            self.redis_client = redis.Redis(
                host=host,
                port=port,
                db=redis_db,
                password=password,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
            )
            self.redis_client.ping()
            self.enabled = True
        except Exception as e:
            print(f"[LongTermMemory] Redis connection failed: {e}")
            self.redis_client = None
            self.enabled = False
        
        self.extractor = MemoryExtractor()
        self.ttl_seconds = int(os.getenv("MEMORY_TTL_DAYS", "90")) * 24 * 3600  # 默认90天
    
    def _make_key(self, user_id: str, memory_id: str) -> str:
        """生成Redis Key"""
        return f"memory:{user_id}:{memory_id}"
    
    def _make_index_key(self, organization_id: str) -> str:
        """生成索引Key"""
        return f"memory:index:{organization_id}"
    
    def _generate_id(self, content: str) -> str:
        """生成记忆ID"""
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    def add_memory(self, 
                   user_id: str,
                   organization_id: str,
                   content: str,
                   memory_type: str = "fact",
                   source_query: str = "",
                   source_response: str = "",
                   importance_score: float = 0.5,
                   tags: Optional[List[str]] = None) -> Optional[MemoryEntry]:
        """添加记忆
        
        Args:
            user_id: 用户ID
            organization_id: 组织ID
            content: 记忆内容
            memory_type: 记忆类型
            source_query: 来源查询
            source_response: 来源回复
            importance_score: 重要性分数
            tags: 标签列表
            
        Returns:
            MemoryEntry对象
        """
        if not self.enabled:
            return None
        
        memory_id = self._generate_id(f"{user_id}:{content}")
        now = datetime.utcnow().isoformat()
        
        entry = MemoryEntry(
            id=memory_id,
            user_id=user_id,
            organization_id=organization_id,
            content=content,
            memory_type=memory_type,
            source_query=source_query,
            source_response=source_response,
            importance_score=importance_score,
            created_at=now,
            updated_at=now,
            tags=tags or []
        )
        
        try:
            key = self._make_key(user_id, memory_id)
            self.redis_client.setex(
                key,
                self.ttl_seconds,
                json.dumps(asdict(entry), ensure_ascii=False)
            )
            
            # 添加到组织索引
            index_key = self._make_index_key(organization_id)
            self.redis_client.sadd(index_key, memory_id)
            
            return entry
        except Exception as e:
            print(f"[LongTermMemory] Failed to add memory: {e}")
            return None
    
    def extract_and_store(self,
                          user_id: str,
                          organization_id: str,
                          query: str,
                          response: str) -> List[MemoryEntry]:
        """提取并存储记忆
        
        Args:
            user_id: 用户ID
            organization_id: 组织ID
            query: 用户查询
            response: 助手回复
            
        Returns:
            存储的记忆条目列表
        """
        if not self.enabled:
            return []
        
        # 提取记忆
        memories_data = self.extractor.extract(query, response)
        
        stored_memories = []
        for mem_data in memories_data:
            entry = self.add_memory(
                user_id=user_id,
                organization_id=organization_id,
                content=mem_data["content"],
                memory_type=mem_data.get("type", "fact"),
                source_query=query,
                source_response=response,
                importance_score=mem_data.get("importance", 0.5),
                tags=mem_data.get("tags", [])
            )
            if entry:
                stored_memories.append(entry)
        
        return stored_memories
    
    def recall(self,
               user_id: str,
               organization_id: str,
               query: str,
               top_k: int = 5,
               min_importance: float = 0.3) -> List[MemoryEntry]:
        """召回相关记忆
        
        Args:
            user_id: 用户ID
            organization_id: 组织ID
            query: 查询内容
            top_k: 返回条数
            min_importance: 最小重要性分数
            
        Returns:
            相关记忆列表
        """
        if not self.enabled:
            return []
        
        try:
            # 获取用户所有记忆
            pattern = f"memory:{user_id}:*"
            keys = self.redis_client.scan_iter(match=pattern, count=100)
            
            memories = []
            for key in keys:
                try:
                    data = self.redis_client.get(key)
                    if data:
                        entry_dict = json.loads(data)
                        entry = MemoryEntry(**entry_dict)
                        
                        # 过滤重要性
                        if entry.importance_score < min_importance:
                            continue
                        
                        # 计算相关性分数（简单关键词匹配）
                        relevance = self._calculate_relevance(query, entry.content)
                        entry.access_count += 1
                        entry.last_accessed_at = datetime.utcnow().isoformat()
                        
                        # 更新访问计数
                        self.redis_client.setex(
                            key,
                            self.ttl_seconds,
                            json.dumps(asdict(entry), ensure_ascii=False)
                        )
                        
                        memories.append((entry, relevance))
                except Exception as e:
                    print(f"[LongTermMemory] Error processing key {key}: {e}")
                    continue
            
            # 按相关性排序
            memories.sort(key=lambda x: x[1], reverse=True)
            
            return [m[0] for m in memories[:top_k]]
        except Exception as e:
            print(f"[LongTermMemory] Recall failed: {e}")
            return []
    
    def _calculate_relevance(self, query: str, content: str) -> float:
        """计算查询与记忆内容的相关性"""
        query_words = set(query.lower().split())
        content_words = set(content.lower().split())
        
        if not query_words:
            return 0.0
        
        overlap = query_words & content_words
        return len(overlap) / len(query_words)
    
    def get_user_memories(self,
                          user_id: str,
                          memory_type: Optional[str] = None,
                          limit: int = 50) -> List[MemoryEntry]:
        """获取用户的所有记忆
        
        Args:
            user_id: 用户ID
            memory_type: 记忆类型过滤
            limit: 返回条数
            
        Returns:
            记忆列表
        """
        if not self.enabled:
            return []
        
        try:
            pattern = f"memory:{user_id}:*"
            keys = list(self.redis_client.scan_iter(match=pattern, count=limit))
            
            memories = []
            for key in keys[:limit]:
                data = self.redis_client.get(key)
                if data:
                    entry_dict = json.loads(data)
                    entry = MemoryEntry(**entry_dict)
                    
                    if memory_type and entry.memory_type != memory_type:
                        continue
                    
                    memories.append(entry)
            
            # 按重要性排序
            memories.sort(key=lambda x: x.importance_score, reverse=True)
            return memories
        except Exception as e:
            print(f"[LongTermMemory] Get memories failed: {e}")
            return []
    
    def delete_memory(self, user_id: str, memory_id: str) -> bool:
        """删除记忆
        
        Args:
            user_id: 用户ID
            memory_id: 记忆ID
            
        Returns:
            是否成功
        """
        if not self.enabled:
            return False
        
        try:
            key = self._make_key(user_id, memory_id)
            return self.redis_client.delete(key) > 0
        except Exception as e:
            print(f"[LongTermMemory] Delete failed: {e}")
            return False
    
    def clear_user_memories(self, user_id: str) -> int:
        """清空用户所有记忆
        
        Args:
            user_id: 用户ID
            
        Returns:
            删除的记忆数量
        """
        if not self.enabled:
            return 0
        
        try:
            pattern = f"memory:{user_id}:*"
            keys = list(self.redis_client.scan_iter(match=pattern))
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            print(f"[LongTermMemory] Clear failed: {e}")
            return 0


# 全局记忆管理器实例
_memory_instance: Optional[LongTermMemory] = None


def get_memory_manager() -> LongTermMemory:
    """获取全局记忆管理器实例"""
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = LongTermMemory()
    return _memory_instance
