# Inquiry Triage AI

LangChain + LangGraph 기반 멀티 에이전트 고객 문의 분류 및 답변 생성 시스템.

고객 문의를 자동으로 분류하여 전문 에이전트가 답변을 생성하고, 운영자는 처리 과정의 메타데이터를 실시간으로 확인할 수 있습니다.

---

## 프로젝트 배경

고객 지원 팀은 반복적인 문의(결제, 배송, 기술 문제 등)를 수동으로 분류하고 담당자에게 배분하는 데 상당한 시간을 소비합니다. 이 프로젝트는 다음 질문에서 출발했습니다.

> **"LLM을 단순한 챗봇이 아닌, 문의를 분류하고 전문 에이전트에게 라우팅하는 오케스트레이터로 활용할 수 있을까?"**

단일 LLM 체인으로는 분류 → 답변 생성 → 안전 검사 → 폴백 처리를 명시적으로 제어하기 어렵습니다. 이를 해결하기 위해 **LangGraph의 상태 그래프**로 각 단계를 독립 노드로 분리하고, 신뢰도 기반 조건 분기와 fail-closed 안전 정책을 적용했습니다.

---

## 스크린샷

**고객 화면 (User Mode)** — 문의를 입력하면 최종 답변만 표시
![이미지](docs/screenshots/user_1.png)
![이미지](docs/screenshots/user_2.png)

**운영자 화면 (Operator Mode)** — 분류 카테고리, 신뢰도, 실행 트레이스 등 내부 메타데이터 표시
![이미지](docs/screenshots/operator_1.png)
![이미지](docs/screenshots/operator_2.png)

---

## 아키텍처

```
고객 문의 입력
    │
    ▼
input_node
    │
    ▼
safety_check_node ──(위반)──► safe_response_node
    │(안전)                            │
    ▼                                 │
router_node                           │
    │                                 │
    ├── billing_agent_node            │
    ├── account_agent_node            │
    ├── technical_support_agent_node  │
    ├── shipping_agent_node           │
    └── fallback_agent_node           │
             │                        │
             ▼                        │
    response_finalize_node ◄──────────┘
             │
             ▼
            END
```

**분류 카테고리**

| 카테고리 | 설명 |
|---|---|
| `billing` | 결제, 환불, 청구 관련 |
| `account` | 계정, 로그인, 개인정보 관련 |
| `technical_support` | 기술 문제, 오류, 사용법 관련 |
| `shipping` | 배송, 배달, 반품 관련 |
| `general` | 위 카테고리에 해당하지 않는 일반 문의 |

라우터의 신뢰도(confidence)가 0.50 미만이면 Fallback Agent로 처리됩니다.

---

## 핵심 설계 결정

### 1. LangGraph를 선택한 이유

단순한 LangChain 체인 파이프라인은 선형 흐름만 지원합니다. 이 시스템에는 다음이 필요했습니다.

- **조건 분기**: Safety 차단 여부, 라우터 신뢰도에 따라 다른 노드로 분기
- **공유 상태 관리**: 문의 ID, LLM 호출 횟수, 실행 트레이스 등을 노드 간에 안전하게 전달
- **명시적인 실행 흐름**: 어떤 순서로 어떤 에이전트가 호출됐는지 코드 레벨에서 추적 가능

LangGraph의 `StateGraph`는 이 요구사항을 타입 안전한 상태(`TypedDict`)와 명시적인 엣지로 표현할 수 있게 해줍니다.

### 2. Safety 에이전트의 fail-closed 정책

Safety 에이전트 호출이 예외로 실패하면, 안전하다고 가정하는 대신 **차단(block)** 처리합니다.

```python
# graphs/inquiry_graph.py
except Exception as e:
    logger.error("[%s] safety_check_node failed: %s — blocking as unsafe (fail-closed)", inquiry_id, e)
    is_safe = False  # 안전 판단 실패 시 차단 (fail-closed)
```

이는 **보안 우선 원칙**에 따른 결정입니다. 안전 판단 시스템의 오류를 "통과"로 처리하면 유해한 요청이 전문 에이전트에게 도달할 수 있습니다. 가용성보다 안전성을 우선합니다.

### 3. User / Operator 모드 분리

동일한 API 엔드포인트(`POST /api/v1/inquiries/respond`)가 `mode` 파라미터에 따라 다른 응답을 반환합니다.

- **User 모드**: `{"answer": "..."}` — 최종 답변만 노출. 내부 분류 결과나 신뢰도는 전달하지 않습니다.
- **Operator 모드**: category, confidence, execution_trace, latency_ms 등 전체 메타데이터를 반환합니다.

이 설계의 이유는 두 가지입니다.
1. **정보 노출 최소화**: 분류 카테고리나 신뢰도 수치를 고객에게 노출하면 프롬프트 인젝션 등 악용 가능성이 생깁니다.
2. **운영 관찰 가능성**: 운영자는 동일한 문의에 대해 어떤 에이전트가 선택됐고, 얼마나 걸렸는지 실시간으로 확인할 수 있습니다.

운영자 모드는 `X-Operator-Key` 헤더로 별도 인증합니다.

### 4. DB 선택적 활성화

`DATABASE_URL` 환경 변수를 설정하지 않으면 DB 저장 로직이 아예 실행되지 않습니다. DB 저장 실패가 발생해도 고객 응답에는 영향을 주지 않습니다.

```python
# services/inquiry_service.py
async def _save_to_db(self, ...):
    if not is_db_enabled():
        return  # DB 없이도 정상 동작
    try:
        ...
    except Exception as e:
        logger.error("[%s] DB 저장 실패 (응답에는 영향 없음): %s", state.get("inquiry_id"), e)
```

이를 통해 로컬 개발 시 PostgreSQL 없이도 전체 기능을 실행할 수 있으며, DB 장애가 서비스 중단으로 이어지지 않습니다.

---

## 현재 한계 및 개선 가능 사항

| 항목 | 현재 상태 | 개선 방향 |
|---|---|---|
| 멀티턴 대화 | 미지원 (단일 문의 단위 처리) | LangGraph의 `checkpointer`로 대화 히스토리 유지 |
| 모니터링 | 로그 기반 | LangSmith 또는 OpenTelemetry 연동 |
| 답변 생성 | 프롬프트 기반 일반 답변 | 사내 FAQ/정책 문서를 벡터 DB에 적재하여 RAG 적용, 실제 정책에 근거한 정확한 답변 생성 |

---

## 기술 스택

**Backend**
- Python 3.11+
- FastAPI + Uvicorn
- LangChain / LangGraph
- OpenAI API (gpt-4o-mini)
- LangSmith (트레이싱 / 평가)
- SQLAlchemy (asyncio) + asyncpg + Alembic
- slowapi (Rate Limiting)
- uv (패키지 관리)

**Frontend**
- Next.js 15 (App Router)
- TypeScript
- Tailwind CSS

---

## 프로젝트 구조

```
inquiry_triage_ai/
├── backend/
│   ├── app/
│   │   ├── agents/          # Router, Safety, Fallback, Expert 에이전트
│   │   │   └── experts/     # billing, account, technical_support, shipping
│   │   ├── chains/          # 에이전트 체인 실행 래퍼
│   │   ├── config/          # 설정, DB, Rate Limiter
│   │   ├── graphs/          # LangGraph 상태 그래프 (inquiry_graph)
│   │   ├── prompts/         # 각 에이전트별 프롬프트
│   │   ├── repositories/    # DB 저장 레이어
│   │   ├── schemas/         # Pydantic 스키마 (InquiryState, RouterOutput, ExpertOutput)
│   │   ├── services/        # 비즈니스 로직 (InquiryService)
│   │   └── api/             # FastAPI 라우터
│   ├── main.py              # FastAPI 앱 진입점
│   ├── tests/
│   │   ├── test_*.py        # 유닛 / 통합 테스트
│   │   └── eval/            # LangSmith 평가 스크립트
│   └── pyproject.toml
└── frontend/
    ├── app/
    │   ├── page.tsx         # 고객 화면 (User Mode)
    │   └── operator/        # 운영자 화면 (Operator Mode)
    ├── components/
    └── lib/
        ├── api.ts
        └── types.ts
```

---

## 시작하기

### Backend

**1. 환경 설정**

```bash
cd backend
cp .env.example .env
```

`.env` 파일에 필수 값 설정:

```env
OPENAI_API_KEY=sk-...

# 선택 사항
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/inquiry_triage

# LangSmith (선택 사항 — 평가/트레이싱 시 필요)
LANGSMITH_API_KEY=ls__...
LANGSMITH_TRACING_V2=true
LANGSMITH_PROJECT=inquiry-triage-eval
```

**2. 의존성 설치 및 실행**

```bash
# uv 사용
uv sync
uv run uvicorn main:app --reload

# 또는 pip 사용
pip install -e .
uvicorn main:app --reload
```

서버가 `http://localhost:8000` 에서 실행됩니다.

**3. 테스트 실행**

```bash
# 유닛 / 통합 테스트
uv run pytest

# LangSmith 평가 (LANGSMITH_API_KEY 설정 필요)
uv run python -m tests.eval.langsmith_eval
```

### Frontend

```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

프론트엔드가 `http://localhost:3000` 에서 실행됩니다.

---

## API

### GET `/health`

서버 상태를 확인합니다.

```json
{"status": "ok"}
```

---

### POST `/api/v1/inquiries/respond`

고객 문의를 분류하고 답변을 생성합니다.

**Request Body**

```json
{
  "inquiry_text": "결제가 두 번 되었어요.",
  "mode": "user",
  "user_id": "user-123",
  "channel": "web",
  "locale": "ko"
}
```

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `inquiry_text` | string | O | 문의 내용 (최대 2000자) |
| `mode` | `"user"` \| `"operator"` | - | 응답 모드 (기본: `user`) |
| `user_id` | string | - | 사용자 ID |
| `channel` | string | - | 문의 채널 |
| `locale` | string | - | 로케일 |

**Response: User Mode**

```json
{
  "answer": "결제 중복 건에 대해 확인 후 환불 처리해 드리겠습니다."
}
```

**Response: Operator Mode**

```json
{
  "category": "billing",
  "confidence": 0.95,
  "selected_agent": "billing_expert_agent",
  "answer": "결제 중복 건에 대해 확인 후 환불 처리해 드리겠습니다.",
  "fallback_used": false,
  "routing_reason": "결제/환불 관련 문의로 판단",
  "execution_trace": [
    {"node_name": "input_node", "status": "completed", "duration_ms": 0},
    {"node_name": "safety_check_node", "status": "completed", "duration_ms": 312},
    {"node_name": "router_node", "status": "completed", "duration_ms": 540},
    {"node_name": "billing_agent_node", "status": "completed", "duration_ms": 820},
    {"node_name": "response_finalize_node", "status": "completed", "duration_ms": 0}
  ],
  "latency_ms": 1720
}
```

**인증 헤더**

| 헤더 | 설명 |
|---|---|
| `X-API-Key` | 일반 API 키 (`API_KEY` 설정 시 필수) |
| `X-Operator-Key` | 운영자 모드 접근 키 (`OPERATOR_API_KEY` 설정 시 필수) |

**에러 코드**

| 코드 | HTTP | 설명 |
|---|---|---|
| `INVALID_INPUT` | 400 | 잘못된 요청 |
| `SAFETY_BLOCKED` | 400 | 정책 위반 문의 |
| `ROUTING_FAILED` | 500 | 라우팅 실패 |
| `AGENT_EXECUTION_FAILED` | 500 | 에이전트 실행 실패 |
| `OUTPUT_PARSE_FAILED` | 500 | 라우터 출력 파싱 실패 |
| `INTERNAL_ERROR` | 500 | 내부 서버 오류 |

---

## 환경 변수 전체 목록

| 변수 | 기본값 | 설명 |
|---|---|---|
| `OPENAI_API_KEY` | - | OpenAI API 키 (필수) |
| `OPENAI_BASE_URL` | - | 커스텀 OpenAI 엔드포인트 |
| `ROUTER_MODEL` | `gpt-4o-mini` | 라우터 에이전트 모델 |
| `BILLING_MODEL` | `gpt-4o-mini` | 결제 에이전트 모델 |
| `ACCOUNT_MODEL` | `gpt-4o-mini` | 계정 에이전트 모델 |
| `TECHNICAL_SUPPORT_MODEL` | `gpt-4o-mini` | 기술지원 에이전트 모델 |
| `SHIPPING_MODEL` | `gpt-4o-mini` | 배송 에이전트 모델 |
| `FALLBACK_MODEL` | `gpt-4o-mini` | Fallback 에이전트 모델 |
| `SAFETY_MODEL` | `gpt-4o-mini` | Safety 에이전트 모델 |
| `ROUTING_CONFIDENCE_THRESHOLD` | `0.80` | 고신뢰도 라우팅 임계값 |
| `ROUTING_CONFIDENCE_LOW_THRESHOLD` | `0.50` | Fallback 전환 신뢰도 임계값 |
| `MAX_LLM_CALLS` | `5` | 요청당 최대 LLM 호출 횟수 |
| `MAX_RETRY_COUNT` | `2` | 에이전트 최대 재시도 횟수 |
| `DATABASE_URL` | - | PostgreSQL 연결 URL (미설정 시 DB 저장 비활성화) |
| `API_KEY` | - | API 인증 키 (미설정 시 인증 불필요) |
| `OPERATOR_API_KEY` | - | 운영자 모드 인증 키 |
| `ALLOWED_ORIGINS` | `["http://localhost:3000"]` | CORS 허용 오리진 (JSON 배열) |
| `RATE_LIMIT` | `20/minute` | 요청 속도 제한 |
| `ENVIRONMENT` | `development` | 실행 환경 |
| `LANGSMITH_API_KEY` | - | LangSmith API 키 (트레이싱/평가 시 필요) |
| `LANGSMITH_TRACING_V2` | - | LangSmith 트레이싱 활성화 (`true`) |
| `LANGSMITH_PROJECT` | - | LangSmith 프로젝트 이름 |
