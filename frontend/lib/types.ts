export interface ExecutionTraceItem {
  node_name: string;
  status: string;
  duration_ms?: number;
}

export interface UserInquiryResponse {
  answer: string;
  conversation_id: string;
}

export interface ChatMessage {
  role: "human" | "ai";
  content: string;
}

export interface OperatorInquiryResponse {
  category: string | null;
  confidence: number | null;
  selected_agent: string | null;
  answer: string | null;
  fallback_used: boolean;
  routing_reason: string | null;
  execution_trace: ExecutionTraceItem[];
  latency_ms: number;
}

export interface ApiError {
  code: string;
  message: string;
}

export interface ApiErrorResponse {
  detail: ApiError;
}

export type InquiryMode = "user" | "operator";
