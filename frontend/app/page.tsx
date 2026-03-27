"use client";

import { useEffect, useRef, useState } from "react";
import HelpButton from "@/components/common/HelpButton";
import SampleExamples from "@/components/common/SampleExamples";
import InquiryForm from "@/components/user/InquiryForm";
import ChatHistory from "@/components/user/ChatHistory";
import UserHelpModal from "@/components/user/UserHelpModal";
import { submitUserInquiry } from "@/lib/api";
import type { ChatMessage } from "@/lib/types";

export default function UserPage() {
  const [inputText, setInputText] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | undefined>(undefined);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isHelpOpen, setIsHelpOpen] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const submit = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || isLoading) return;

    setIsLoading(true);
    setError(null);
    setInputText("");
    setMessages((prev) => [...prev, { role: "human", content: trimmed }]);

    try {
      const result = await submitUserInquiry(trimmed, conversationId);
      setConversationId(result.conversation_id);
      setMessages((prev) => [...prev, { role: "ai", content: result.answer }]);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setMessages([]);
    setConversationId(undefined);
    setError(null);
    setInputText("");
  };

  const handleFormSubmit = () => submit(inputText);

  const handleExampleSelect = (text: string) => {
    setInputText(text);
    submit(text);
  };

  return (
    <div className="flex h-[calc(100vh-56px)] flex-col">
      {/* 서브 헤더 */}
      <div className="shrink-0 border-b border-gray-100 bg-white px-6 py-3">
        <div className="mx-auto flex max-w-2xl items-center justify-between">
          <h1 className="text-base font-semibold text-gray-700">고객 문의</h1>
          <div className="flex items-center gap-2">
            {messages.length > 0 && (
              <button
                onClick={handleReset}
                className="rounded-lg border border-red-200 bg-red-50 px-3 py-1.5 text-xs font-medium text-red-600 transition-colors hover:bg-red-100"
              >
                새 대화 시작
              </button>
            )}
            <HelpButton onClick={() => setIsHelpOpen(true)} />
          </div>
        </div>
      </div>

      {/* 채팅 영역 */}
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-2xl px-6 py-6">
          {messages.length === 0 && !isLoading ? (
            <SampleExamples onSelect={handleExampleSelect} disabled={isLoading} />
          ) : messages.length > 0 ? (
            <ChatHistory messages={messages} />
          ) : null}

          {isLoading && (
            <div className="mt-3 flex justify-start">
              <div className="rounded-xl rounded-tl-sm border border-gray-200 bg-white px-4 py-3.5">
                <div className="flex items-center gap-1.5">
                  {[0, 150, 300].map((delay) => (
                    <span
                      key={delay}
                      className="h-2 w-2 rounded-full bg-gray-300 animate-bounce"
                      style={{ animationDelay: `${delay}ms` }}
                    />
                  ))}
                </div>
              </div>
            </div>
          )}

          {error && !isLoading && (
            <div className="mt-3 rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
              {error}
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </main>

      {/* 입력 영역 */}
      <div className="shrink-0 border-t border-gray-100 bg-white px-6 py-4">
        <div className="mx-auto w-full max-w-2xl">
          <InquiryForm
            value={inputText}
            onChange={setInputText}
            onSubmit={handleFormSubmit}
            isLoading={isLoading}
          />
        </div>
      </div>

      <UserHelpModal isOpen={isHelpOpen} onClose={() => setIsHelpOpen(false)} />
    </div>
  );
}
