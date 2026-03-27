import type {
  InquiryMode,
  OperatorInquiryResponse,
  UserInquiryResponse,
} from "./types";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

const ENDPOINT = `${BACKEND_URL}/api/v1/inquiries/respond`;

interface InquiryRequestBody {
  inquiry_text: string;
  user_id?: string;
  channel?: string;
  locale?: string;
  mode: InquiryMode;
  conversation_id?: string;
}

async function postInquiry<T>(body: InquiryRequestBody): Promise<T> {
  const res = await fetch(ENDPOINT, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    let errorCode = "INTERNAL_ERROR";
    let errorMessage = "일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.";
    try {
      const errBody = await res.json();
      errorCode = errBody?.detail?.code ?? errorCode;
      errorMessage = errBody?.detail?.message ?? errorMessage;
    } catch {
      // JSON 파싱 실패 시 기본 메시지 사용
    }
    const err = new Error(errorMessage) as Error & { code: string };
    err.code = errorCode;
    throw err;
  }

  return res.json() as Promise<T>;
}

export async function submitUserInquiry(
  inquiryText: string,
  conversationId?: string
): Promise<UserInquiryResponse> {
  return postInquiry<UserInquiryResponse>({
    inquiry_text: inquiryText,
    mode: "user",
    conversation_id: conversationId,
  });
}

export async function submitOperatorInquiry(
  inquiryText: string
): Promise<OperatorInquiryResponse> {
  return postInquiry<OperatorInquiryResponse>({
    inquiry_text: inquiryText,
    mode: "operator",
  });
}
