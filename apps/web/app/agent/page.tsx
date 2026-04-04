"use client";

import { useEffect, useMemo, useState } from "react";
import ChatInterface, { ChatConversation } from "../../components/ChatInterface";

function createConversation(title = "新对话"): ChatConversation {
  const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return {
    id,
    title,
    createdAt: Date.now(),
    updatedAt: Date.now(),
    messages: []
  };
}

export default function AgentPage() {
  const [conversations, setConversations] = useState<ChatConversation[]>([createConversation()]);
  const [activeId, setActiveId] = useState<string>(conversations[0].id);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('agent-sidebar-collapsed') === 'true';
    }
    return false;
  });

  // Persist sidebar state
  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('agent-sidebar-collapsed', isSidebarCollapsed.toString());
    }
  }, [isSidebarCollapsed]);

  useEffect(() => {
    const raw = typeof window !== "undefined" ? window.localStorage.getItem("agent-conversations") : null;
    if (!raw) return;
    try {
      const list = JSON.parse(raw) as ChatConversation[];
      if (Array.isArray(list) && list.length > 0) {
        setConversations(list);
        setActiveId(list[0].id);
      }
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem("agent-conversations", JSON.stringify(conversations));
  }, [conversations]);

  const activeConversation = useMemo(
    () => conversations.find((item) => item.id === activeId) ?? conversations[0],
    [activeId, conversations]
  );

  function handleCreateConversation() {
    const next = createConversation();
    setConversations((prev) => [next, ...prev]);
    setActiveId(next.id);
  }

  function handleSelectConversation(id: string) {
    setActiveId(id);
  }

  function handleDeleteConversation(id: string) {
    setConversations((prev) => {
      const next = prev.filter((c) => c.id !== id);
      if (next.length === 0) {
        const fallback = createConversation();
        setActiveId(fallback.id);
        return [fallback];
      }
      if (activeId === id) setActiveId(next[0].id);
      return next;
    });
  }

  function handleClearAllConversations() {
    const fallback = createConversation();
    setConversations([fallback]);
    setActiveId(fallback.id);
    if (typeof window !== "undefined") {
      window.localStorage.removeItem("agent-conversations");
    }
  }

  function handleUpdateConversation(next: ChatConversation) {
    setConversations((prev) =>
      prev
        .map((item) => (item.id === next.id ? next : item))
        .sort((a, b) => b.updatedAt - a.updatedAt)
    );
  }

  return (
    <main className="h-full bg-white">
      <div className="flex h-full">
        {/* Left Sidebar - Conversation List */}
        <aside className={`flex flex-col border-r border-gray-200 bg-white transition-all duration-300 ${isSidebarCollapsed ? 'w-12' : 'w-72'}`}>
          <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3">
            {!isSidebarCollapsed && <h1 className="text-base font-semibold text-gray-800">对话列表</h1>}
            <button
              type="button"
              onClick={handleCreateConversation}
              className={`rounded-md bg-blue-600 text-white transition hover:bg-blue-700 ${isSidebarCollapsed ? 'w-8 h-8 flex items-center justify-center px-0' : 'px-3 py-1.5 text-sm'}`}
              title="新建对话"
            >
              {isSidebarCollapsed ? '+' : '+ 新建'}
            </button>
            <button
              type="button"
              onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
              className="p-1 rounded hover:bg-gray-100 transition-colors"
              title={isSidebarCollapsed ? "展开" : "折叠"}
            >
              <span className="text-gray-500">{isSidebarCollapsed ? '→' : '←'}</span>
            </button>
          </div>
          <div className="flex-1 overflow-y-auto">
            {conversations.map((item) => {
              const isActive = item.id === activeId;
              return (
                <div
                  key={item.id}
                  onClick={() => handleSelectConversation(item.id)}
                  className={`w-full cursor-pointer border-b border-gray-100 transition ${
                    isActive
                      ? "bg-blue-50 border-l-4 border-l-blue-600"
                      : "bg-white hover:bg-gray-50"
                  } ${isSidebarCollapsed ? 'px-2 py-3' : 'px-4 py-3'}`}
                  title={isSidebarCollapsed ? item.title : undefined}
                >
                  {!isSidebarCollapsed && (
                    <>
                      <div className={`truncate text-sm font-medium ${isActive ? "text-blue-700" : "text-gray-800"}`}>
                        {item.title}
                      </div>
                      <div className="mt-1 text-xs text-gray-400">
                        {new Date(item.updatedAt).toLocaleString("zh-CN")}
                      </div>
                      {isActive && (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteConversation(item.id);
                          }}
                          className="mt-2 text-xs text-gray-400 hover:text-red-500"
                        >
                          删除
                        </button>
                      )}
                    </>
                  )}
                  {isSidebarCollapsed && (
                    <div className={`text-center text-sm ${isActive ? "text-blue-700" : "text-gray-600"}`}>
                      {item.title.charAt(0)}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </aside>

        {/* Main Chat Area */}
        <section className="flex-1 h-full bg-white">
          {activeConversation ? (
            <ChatInterface
              conversation={activeConversation}
              onConversationChange={handleUpdateConversation}
              onDeleteCurrentConversation={() => handleDeleteConversation(activeConversation.id)}
              onClearAllConversations={handleClearAllConversations}
            />
          ) : null}
        </section>
      </div>
    </main>
  );
}
