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

- **User 모드**: `{"answer": "...", "conversation_id": "..."}` — 최종 답변과 대화 ID만 노출. 내부 분류 결과나 신뢰도는 전달하지 않습니다.
- **Operator 모드**: category, confidence, execution_trace, latency_ms 등 전체 메타데이터를 반환합니다.

이 설계의 이유는 두 가지입니다.
1. **정보 노출 최소화**: 분류 카테고리나 신뢰도 수치를 고객에게 노출하면 프롬프트 인젝션 등 악용 가능성이 생깁니다.
2. **운영 관찰 가능성**: 운영자는 동일한 문의에 대해 어떤 에이전트가 선택됐고, 얼마나 걸렸는지 실시간으로 확인할 수 있습니다.

운영자 모드는 `X-Operator-Key` 헤더로 별도 인증합니다.

### 4. 멀티턴 대화 지원

`conversation_id`를 통해 이전 대화 이력을 로드하고, 문맥을 유지한 채 답변을 생성합니다.

- 첫 요청 시 `conversation_id`를 생략하면 새 대화가 시작되고, 응답에 새 ID가 반환됩니다.
- 이후 요청에 해당 `conversation_id`를 전달하면 이전 메시지를 `chat_history`로 복원하여 라우팅과 답변 생성에 활용합니다.
- DB 없이 실행하는 경우 대화 이력은 저장되지 않으며, 각 요청은 독립적으로 처리됩니다.

### 5. DB 선택적 활성화

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

### 6. LangSmith 기반 평가 파이프라인

Safety, Router, Expert 에이전트 전체 파이프라인을 LangSmith로 체계적으로 평가합니다.

- **Safety 정확도** (`safety_correct`): expected_safe vs 실제 safety_flag — False Positive / Negative 추적
- **라우팅 정확도** (`routing_correct`): expected_category vs 실제 category
- **Fallback 정확도** (`routing_fallback`): 신뢰도 기반 Fallback 발동 여부
- **답변 품질** (`quality_relevance`, `quality_completeness`, `quality_safety`): Judge LLM(gpt-4o)이 관련성·완결성·안전성을 1~5점으로 평가

난이도(easy/medium/hard)와 텍스트 길이(short/long) 필터를 지원하여 엣지 케이스를 집중적으로 평가할 수 있습니다.

---

## 평가 설계

### 왜 평가를 설계했는가

LLM 기반 시스템은 유닛 테스트만으로는 품질을 보장하기 어렵습니다. "라우터가 올바른 카테고리를 골랐는가", "Safety가 경계선 문의를 어떻게 처리하는가", "Expert의 답변이 실제로 고객에게 도움이 되는가"는 assertion으로 검증할 수 없습니다.

이 평가 파이프라인은 두 가지 질문에 답하기 위해 설계했습니다.

> **"프롬프트나 모델을 바꿨을 때 어떤 노드에서 무엇이 깨졌는가?"**
> **"전체 파이프라인이 실제 고객 문의에서 어떻게 동작하는가?"**

### 레이어별 분리 평가 전략

파이프라인 전체를 한 번에 평가하면 어느 노드에서 실패했는지 추적이 어렵습니다. 소프트웨어 테스트의 단위/통합/E2E 분리처럼, 평가도 3단계로 격리했습니다.

```
eval_safety.py    → Safety 노드만 단독 평가
eval_router.py    → Router 노드만 단독 평가
eval_expert.py    → Expert 노드만 단독 평가 (Judge LLM)
eval_e2e.py       → 전체 파이프라인 통합 평가 (자동 검증 + Judge LLM)
```

이렇게 하면 E2E 합격률이 떨어졌을 때 "Router 정확도는 유지됐고, Expert 완결성이 낮아진 것"처럼 원인을 빠르게 좁힐 수 있습니다.

### Safety 평가 — FP/FN 분리 추적

Safety 에이전트의 실패에는 성격이 다른 두 종류가 있습니다.

- **FP (False Positive, 과차단)**: 정상 문의를 위험으로 판단해 차단 → 서비스 가용성 저하
- **FN (False Negative, 과허용)**: 위험 문의를 통과시킴 → 보안 사고 위험

두 오류를 묶어 "정확도"로만 표현하면 FP와 FN의 트레이드오프가 보이지 않습니다. 이 시스템은 fail-closed 정책(Safety 판단 실패 시 차단)을 택했으므로 FN이 FP보다 더 심각한 오류입니다. 별도 추적으로 "어느 방향의 오류가 늘었는가"를 프롬프트 변경 전후에 비교할 수 있습니다.

### Router 평가 — Confusion Matrix 기반 오분류 추적

단순 정확도(89/106)만으로는 "billing이 account로 오분류되는지, general로 오분류되는지"를 알 수 없습니다. Confusion Matrix를 통해 카테고리 간 경계가 모호한 지점을 파악하고, 프롬프트 개선의 방향을 잡을 수 있습니다.

난이도를 easy/medium/hard로 구분한 기준은 다음과 같습니다.

| 난이도 | 기준 |
|---|---|
| easy | 단일 카테고리, 명확한 키워드 포함 |
| medium | 복합 감정, 여러 요청이 혼재, 경계 카테고리 키워드 포함 |
| hard | 카테고리 간 경계 문의, 신뢰도 낮은 모호한 표현, 복합 도메인 |

### Expert 평가 — LLM-as-Judge

Expert 에이전트의 답변 품질은 정답이 없는 생성형 텍스트입니다. 규칙 기반으로 검증할 수 없기 때문에 Judge LLM(gpt-4o)을 심사위원으로 활용했습니다.

**Judge 프롬프트 설계 원칙**

단순히 "좋은 답변인가"를 묻는 대신, 고객센터 맥락에서 의미 있는 3가지 축으로 분리했습니다.

| 지표 | 측정하는 것 | 낮은 점수의 의미 |
|---|---|---|
| relevance (관련성) | 문의의 핵심을 파악했는가 | 엉뚱한 카테고리의 답변 생성 |
| completeness (완결성) | 고객이 다음 행동을 바로 취할 수 있는가 | 방향만 제시하고 절차 누락 |
| safety (안전성) | 잘못된 정보·민감정보 요청·도메인 침범이 없는가 | 카드번호 요청, 단정적 환불 확약 등 |

각 케이스에는 `eval_focus`, `must_include`, `must_not` 필드를 추가해 Judge가 집중해야 할 평가 포인트를 명시했습니다. Judge LLM에게 "좋은 답변"의 기준을 추상적으로 맡기지 않고, 케이스마다 체크리스트를 제공하는 방식입니다.

**합격 기준을 난이도별로 다르게 설정한 이유**

hard 케이스(민감 정보 요청, 타인 계정 접근, 도메인 이탈 문의)는 답변의 내용보다 **안전하게 거절하는 것**이 핵심입니다. 이 케이스에서 관련성·완결성 점수가 낮은 건 오히려 정상입니다(카드 번호를 물어보는 문의에 "환불은 이렇게 하세요"라고 답하면 안 됨). 따라서 hard는 safety ≥ 4, 그 외는 (R + C) / 2 ≥ 3.5로 기준을 분리했습니다.

### E2E 평가 — 자동 검증 + Judge LLM 조합

E2E는 두 단계로 검증합니다.

1. **자동 검증**: Safety 통과 여부, 라우팅 정확도, execution_trace 완결성 등 결정론적으로 판단 가능한 항목
2. **Judge LLM**: 최종 answer의 품질 — 자동 검증을 통과해도 답변이 나쁘면 불합격

두 조건을 AND로 결합해야 최종 합격입니다. "파이프라인은 정상 실행됐지만 답변이 엉망"인 케이스를 걸러내기 위한 설계입니다.

**hard 패턴 3가지를 별도로 정의한 이유**

hard 케이스가 같은 이유로 실패하면 개선 방향이 하나지만, 실패 원인이 다르면 수정 포인트도 달라집니다. 패턴을 분리하지 않으면 "hard 33%"라는 숫자만 남습니다.

| 패턴 | 테스트하는 것 | 기대 동작 |
|---|---|---|
| confidence_boundary | 극도로 모호한 문의 (맥락 없음) | Fallback 라우팅 + 추가 정보 요청 |
| cross_domain | 여러 카테고리에 걸친 문의 | 주요 도메인으로 올바르게 라우팅 |
| expert_boundary | 민감 정보 요청, 타인 계정, 손해배상 등 | 안전하게 거절 또는 범위 이탈 안내 |

---

## 평가 결과

### 평가 테스트셋 구성

| 평가 모듈 | 케이스 수 | easy | medium | hard | 비고 |
|---|---|---|---|---|---|
| Safety Agent | 60건 | 20 | 20 | 20 | safe 30건 / unsafe 30건 |
| Router Agent | 106건 | 37 | 39 | 30 | 5개 카테고리 균형 분포 |
| Expert Agent | 36건 | 12 | 12 | 12 | 4개 카테고리 × 3난이도 |
| E2E Pipeline | 28건 | 8 | 8 | 12 | expert 24건 / fallback 4건 |

### 합격 기준

| 평가 모듈 | 합격 기준 |
|---|---|
| Safety Agent | 전체 정확도 (correct == expected_safe) |
| Router Agent | 전체 정확도 (predicted == expected_category) |
| Expert Agent (easy/medium) | (relevance + completeness) / 2 ≥ 3.5 |
| Expert Agent (hard) | safety ≥ 4 |
| E2E Pipeline | 자동 검증 전체 통과 + Judge 점수 합격 |

### Safety Agent 평가

모델 `gpt-4o-mini` 기준, 총 60건 평가.

| 지표 | 전체 | easy | medium | hard |
|---|---|---|---|---|
| 정확도 | 81.7% (49/60) | 95.0% | 85.0% | 65.0% |
| FP (과차단) | 3건 | 0 | 1 | 2 |
| FN (과허용) | 8건 | 1 | 2 | 5 |
| Precision | 0.771 | - | - | - |
| Recall | 0.900 | - | - | - |
| F1 | 0.831 | - | - | - |
| 평균 레이턴시 | 1,321ms | - | - | - |

> FP: 정상 문의를 차단 / FN: 위험 문의를 통과시킴. hard 케이스에서 FN이 집중되어 경계선 표현·이중적 맥락 문의에 취약함.

### Router Agent 평가

모델 `gpt-4o-mini` 기준, 총 106건 평가.

| 지표 | 전체 | easy | medium | hard |
|---|---|---|---|---|
| 정확도 | 84.0% (89/106) | 97.3% | 82.1% | 70.0% |
| 파싱 실패 | 0건 | - | - | - |
| 평균 레이턴시 | 1,092ms | - | - | - |

**카테고리별 정확도**

| 카테고리 | 정확도 |
|---|---|
| billing | 68.2% (15/22) |
| account | 80.0% (20/25) |
| technical_support | 96.0% (24/25) |
| shipping | 83.3% (20/24) |
| general | 100% (10/10) |

> billing이 가장 낮음. 구독 해지, 무료 체험 전환 등 account·general과 경계가 모호한 문의에서 오분류 발생.

### Expert Agent 평가 (LLM-as-Judge)

Judge 모델 `gpt-4o`, Expert 모델 `gpt-4o-mini` 기준, 총 36건 평가.

| 지표 | 전체 | easy | medium | hard |
|---|---|---|---|---|
| 합격률 | 83.3% (30/36) | 100% | 50.0% | 100% |
| 평균 관련성 (R) | 4.44 | 4.92 | 3.92 | 4.50 |
| 평균 완결성 (C) | 4.17 | 4.75 | 3.58 | 4.17 |
| 평균 안전성 (S) | 4.86 | 4.83 | 4.92 | 4.83 |
| 평균 레이턴시 | 2,663ms | - | - | - |

**카테고리별 결과**

| 카테고리 | 합격률 | R | C | S |
|---|---|---|---|---|
| billing | 88.9% (8/9) | 4.22 | 4.11 | 4.56 |
| account | 88.9% (8/9) | 4.67 | 4.22 | 4.89 |
| technical_support | 88.9% (8/9) | 4.67 | 4.67 | 5.00 |
| shipping | 66.7% (6/9) | 4.22 | 3.67 | 5.00 |

> medium 불합격이 집중됨(6건 중 6건). 장기 환불 미처리·파손 수령 등 에스컬레이션이 필요한 케이스에서 완결성 부족. hard는 안전성 기준만 충족하면 합격이므로 100% 달성.

### E2E Pipeline 평가

전체 파이프라인(Safety → Router → Expert/Fallback → Finalize) 통합 평가, 총 28건.

| 지표 | 결과 |
|---|---|
| 전체 합격률 | 57.1% (16/28) |
| 평균 총 레이턴시 | 6,951ms |
| 평균 LLM 호출 수 | 2.9회 |

**자동 검증 통과율**

| 검증 항목 | 통과율 |
|---|---|
| safety_passed (Safety 정상 통과) | 92.9% (26/28) |
| routing_correct (Fallback 발동 정확도) | 89.3% (25/28) |
| category_correct (카테고리 분류 정확도) | 79.2% (19/24) |
| trace_complete (실행 트레이스 완결성) | 100% (28/28) |
| has_answer (답변 생성 여부) | 100% (28/28) |

**난이도별 결과**

| 난이도 | 합격률 | R | C | S | 평균 레이턴시 |
|---|---|---|---|---|---|
| easy | 100% (8/8) | 5.00 | 5.00 | 5.00 | 11,141ms |
| medium | 50.0% (4/8) | 4.25 | 4.25 | 5.00 | 5,120ms |
| hard | 33.3% (4/12) | 4.00 | 3.67 | 5.00 | 5,378ms |

**hard 패턴별 결과**

| 패턴 | 합격률 | 평균 안전성 |
|---|---|---|
| confidence_boundary (신뢰도 경계) | 0.0% (0/4) | 5.00 |
| cross_domain (복합 도메인) | 75.0% (3/4) | 5.00 |
| expert_boundary (전문가 한계 경계) | 25.0% (1/4) | 5.00 |

> confidence_boundary는 "도와주세요", "뭔가 이상해요" 등 맥락 없는 극단적 모호 문의로, 라우팅·답변 완결성 모두 낮음. expert_boundary는 카드 번호 포함 문의·타인 계정 요청 등 Safety가 차단하는 케이스로 category_correct 불합격.

### 결과 해석 및 개선 방향

**Safety (81.7%)**: FN 8건 중 5건이 hard 케이스에 집중됩니다. "이 정도면 괜찮지 않나요?", "그냥 한 번만요" 같은 우회 표현이나 정중한 어조의 위험 요청을 통과시키는 패턴입니다. 프롬프트에 우회 표현 예시를 추가하거나 few-shot 예제를 보강하면 개선 여지가 있습니다.

**Router (84.0%)**: billing이 68.2%로 가장 낮습니다. 구독 해지(`account`로 오분류), 무료 체험 전환(`general`로 오분류) 등 결제와 계정의 경계가 모호한 문의가 오분류의 대부분입니다. billing 카테고리 정의에 "구독 관련 문의 포함" 명시가 필요합니다.

**Expert (83.3%)**: medium 불합격 6건 모두 완결성 부족이 원인입니다. 장기 미처리 환불, 파손 수령 등 에스컬레이션이 필요한 케이스에서 "고객센터에 문의하세요" 수준의 답변을 생성합니다. 이는 사내 FAQ/정책 데이터가 없는 현재 구조의 한계로, RAG 도입 시 해결 가능한 문제입니다.

**E2E (57.1%)**: 단위 평가보다 합격률이 낮은 것은 자동 검증과 Judge LLM을 AND 조건으로 결합하기 때문입니다. 특히 confidence_boundary(0%) 패턴은 시스템 설계상 의도된 한계입니다. "도와주세요"처럼 맥락이 전혀 없는 문의는 어떤 LLM도 완결성 높은 답변을 생성하기 어렵고, 실제 고객 지원에서도 추가 질문이 필요한 케이스입니다. 이 점수를 높이려면 멀티턴으로 추가 정보를 수집하는 노드를 파이프라인에 추가해야 합니다.

---

## 개선 가능 사항

| 항목 | 현재 상태 | 개선 방향 |
|---|---|---|
| 답변 생성 | 프롬프트 기반 일반 답변 | 사내 FAQ/정책 문서를 벡터 DB에 적재하여 RAG 적용, 실제 정책에 근거한 정확한 답변 생성 |
| 모니터링 | LangSmith 트레이싱 | OpenTelemetry 연동으로 프로덕션 모니터링 강화 |

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
- Next.js 14 (App Router)
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
│   │   ├── repositories/    # DB 저장 레이어 (문의 기록 + 대화 이력)
│   │   ├── schemas/         # Pydantic 스키마 (InquiryState, RouterOutput, ExpertOutput)
│   │   ├── services/        # 비즈니스 로직 (InquiryService)
│   │   └── api/             # FastAPI 라우터
│   ├── main.py              # FastAPI 앱 진입점
│   ├── tests/
│   │   ├── test_*.py        # 유닛 / 통합 테스트
│   │   └── eval/            # LangSmith 평가 스크립트
│   │       └── results/     # 평가 결과 JSON
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

# LangSmith 평가 (LANGSMITH_API_KEY 및 OPENAI_API_KEY 설정 필요)
# 데이터셋 업로드 (최초 1회)
uv run python -m tests.eval.langsmith_eval upload

# 전체 평가 실행
uv run python -m tests.eval.langsmith_eval run

# 특정 항목만 평가
uv run python -m tests.eval.langsmith_eval run --target safety
uv run python -m tests.eval.langsmith_eval run --target router
uv run python -m tests.eval.langsmith_eval run --target quality

# 난이도 / 텍스트 길이 필터
uv run python -m tests.eval.langsmith_eval run --difficulty hard --length long
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
  "locale": "ko",
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `inquiry_text` | string | O | 문의 내용 (최대 2000자) |
| `mode` | `"user"` \| `"operator"` | - | 응답 모드 (기본: `user`) |
| `user_id` | string | - | 사용자 ID |
| `channel` | string | - | 문의 채널 |
| `locale` | string | - | 로케일 |
| `conversation_id` | string | - | 대화 ID (멀티턴용, user 모드 전용) |

**Response: User Mode**

```json
{
  "answer": "결제 중복 건에 대해 확인 후 환불 처리해 드리겠습니다.",
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000"
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
| `ROUTING_CONFIDENCE_LOW_THRESHOLD` | `0.50` | Fallback 전환 신뢰도 임계값 |
| `MAX_LLM_CALLS` | `5` | 요청당 최대 LLM 호출 횟수 |
| `MAX_RETRY_COUNT` | `2` | 에이전트 최대 재시도 횟수 |
| `DATABASE_URL` | - | PostgreSQL 연결 URL (미설정 시 DB 저장 비활성화) |
| `API_KEY` | - | API 인증 키 (미설정 시 인증 불필요) |
| `OPERATOR_API_KEY` | - | 운영자 모드 인증 키 |
| `ALLOWED_ORIGINS` | `["http://localhost:3000"]` | CORS 허용 오리진 (JSON 배열) |
| `RATE_LIMIT` | `20/minute` | 요청 속도 제한 |
| `DAILY_LIMIT` | `10` | 사용자당 일별 요청 제한 (KST 자정 기준 초기화) |
| `ENVIRONMENT` | `development` | 실행 환경 |
| `LANGSMITH_API_KEY` | - | LangSmith API 키 (트레이싱/평가 시 필요) |
| `LANGSMITH_TRACING_V2` | - | LangSmith 트레이싱 활성화 (`true`) |
| `LANGSMITH_PROJECT` | - | LangSmith 프로젝트 이름 |
