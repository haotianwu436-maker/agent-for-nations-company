"use client";

import { memo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type Props = {
  content: string;
  citations?: Array<Record<string, unknown>>;
};

function MemoizedMarkdownInner({ content, citations = [] }: Props) {
  return (
    <div
      className={[
        "prose prose-invert max-w-none text-slate-100",
        "prose-headings:mb-3 prose-headings:mt-6 prose-headings:font-semibold prose-headings:text-slate-100",
        "prose-p:my-3 prose-p:leading-7 prose-p:text-slate-200",
        "prose-strong:text-slate-100",
        "prose-ul:my-3 prose-ul:list-disc prose-ul:pl-6 prose-ol:my-3 prose-ol:list-decimal prose-ol:pl-6",
        "prose-li:my-1 prose-li:text-slate-200",
        "prose-blockquote:my-4 prose-blockquote:rounded-r-lg prose-blockquote:border-l-4 prose-blockquote:border-l-blue-400",
        "prose-blockquote:bg-slate-900/80 prose-blockquote:px-4 prose-blockquote:py-2 prose-blockquote:text-slate-200",
        "prose-code:rounded prose-code:bg-slate-900 prose-code:px-1.5 prose-code:py-0.5 prose-code:text-sky-300 prose-code:before:content-none prose-code:after:content-none",
        "prose-pre:overflow-x-auto prose-pre:rounded-xl prose-pre:border prose-pre:border-slate-600 prose-pre:bg-slate-950 prose-pre:px-4 prose-pre:py-3",
        "prose-a:text-blue-300 prose-a:underline-offset-4 hover:prose-a:text-blue-200",
        "prose-table:my-4 prose-table:w-full prose-th:border prose-th:border-slate-600 prose-th:bg-slate-800 prose-th:px-3 prose-th:py-2 prose-th:text-slate-100",
        "prose-td:border prose-td:border-slate-700 prose-td:bg-slate-900/70 prose-td:px-3 prose-td:py-2 prose-td:text-slate-200"
      ].join(" ")}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]}>
        {content}
      </ReactMarkdown>
      {citations.length > 0 ? (
        <div className="mt-5 rounded-xl border border-slate-700 bg-slate-900/70 p-3">
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">来源引用</div>
          <ul className="space-y-1.5 text-sm">
            {citations.map((item, idx) => {
              const title = String(item.title || item.source_name || item.id || `来源 ${idx + 1}`);
              const href = String(item.source_url || item.url || "");
              return (
                <li key={`${title}-${idx}`} className="text-slate-300">
                  {href ? (
                    <a href={href} target="_blank" rel="noreferrer" className="text-blue-300 hover:text-blue-200">
                      [{idx + 1}] {title}
                    </a>
                  ) : (
                    <span>[{idx + 1}] {title}</span>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

const MemoizedMarkdown = memo(
  MemoizedMarkdownInner,
  (prev, next) => prev.content === next.content && prev.citations === next.citations
);

export default MemoizedMarkdown;
