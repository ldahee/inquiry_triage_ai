import ReactMarkdown from "react-markdown";
import remarkBreaks from "remark-breaks";
import type { ChatMessage } from "@/lib/types";

interface ChatHistoryProps {
  messages: ChatMessage[];
}

export default function ChatHistory({ messages }: ChatHistoryProps) {
  return (
    <div className="space-y-3">
      {messages.map((msg, i) => (
        <div
          key={i}
          className={msg.role === "human" ? "flex justify-end" : "flex justify-start"}
        >
          <div
            className={
              msg.role === "human"
                ? "max-w-[80%] rounded-xl rounded-tr-sm bg-blue-500 px-4 py-3 text-sm text-white"
                : "max-w-[80%] rounded-xl rounded-tl-sm border border-gray-200 bg-white px-4 py-3 text-sm text-gray-800"
            }
          >
            {msg.role === "human" ? (
              <div className="prose prose-sm max-w-none leading-relaxed
                prose-p:text-white prose-p:my-1
                prose-ul:my-1 prose-ol:my-1
                prose-li:text-white prose-li:my-0
                prose-strong:text-white
                prose-headings:text-white prose-headings:font-semibold
                prose-code:bg-blue-400 prose-code:px-1 prose-code:rounded prose-code:text-xs prose-code:text-white">
                <ReactMarkdown remarkPlugins={[remarkBreaks]}>{msg.content}</ReactMarkdown>
              </div>
            ) : (
              <div className="prose prose-sm max-w-none leading-relaxed
                prose-headings:font-semibold prose-headings:text-gray-800
                prose-p:text-gray-800 prose-p:my-1
                prose-ul:my-1 prose-ol:my-1
                prose-li:text-gray-800 prose-li:my-0
                prose-strong:text-gray-900
                prose-code:bg-gray-100 prose-code:px-1 prose-code:rounded prose-code:text-xs
                prose-pre:bg-gray-100 prose-pre:rounded-lg prose-pre:text-xs">
                <ReactMarkdown remarkPlugins={[remarkBreaks]}>{msg.content}</ReactMarkdown>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
