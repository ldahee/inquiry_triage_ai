"""
Router Agent 분류 정확도 평가용 테스트셋.

각 케이스: {"text": str, "expected": str, "difficulty": str, "note": str}
- expected   : billing / account / technical_support / shipping / general
- difficulty : easy / medium / hard
  - easy   : 카테고리 키워드가 문장에 직접 포함되어 있음
  - medium : 간접 표현이지만 한 카테고리로 추론 가능
  - hard   : 키워드 없음, 구어체 모호, 또는 표면 키워드가 정답과 다른 카테고리를 가리킴
"""

ROUTER_TESTSET = [

    # ══════════════════════════════════════════════
    # billing
    # ══════════════════════════════════════════════

    # easy ─────────────────────────────────────────
    {
        "text": "환불 신청했는데 아직 금액이 안 들어왔어요.",
        "expected": "billing",
        "difficulty": "easy",
        "note": "환불 미처리, 키워드 명확",
    },
    {
        "text": "지난달 결제가 두 번 된 것 같아요. 확인해주세요.",
        "expected": "billing",
        "difficulty": "easy",
        "note": "중복 결제, 키워드 명확",
    },
    {
        "text": "세금계산서 발행 요청드립니다.",
        "expected": "billing",
        "difficulty": "easy",
        "note": "세금계산서 발행",
    },
    {
        "text": "자동 결제를 중지하고 싶어요.",
        "expected": "billing",
        "difficulty": "easy",
        "note": "자동결제 해지",
    },
    {
        "text": "청구서에 모르는 항목이 있어요. 무슨 요금인가요?",
        "expected": "billing",
        "difficulty": "easy",
        "note": "청구 항목 문의",
    },
    {
        "text": "결제 수단을 신용카드에서 계좌이체로 바꾸고 싶어요.",
        "expected": "billing",
        "difficulty": "easy",
        "note": "결제 수단 변경",
    },
    {
        "text": "할인 쿠폰을 적용했는데 할인이 안 됐어요.",
        "expected": "billing",
        "difficulty": "easy",
        "note": "쿠폰 미적용",
    },
    {
        "text": "환불 처리 기간이 얼마나 걸리나요?",
        "expected": "billing",
        "difficulty": "easy",
        "note": "환불 기간 문의",
    },

    # medium ───────────────────────────────────────
    {
        "text": "이번 달 청구 금액이 저번 달보다 갑자기 많이 올랐어요.",
        "expected": "billing",
        "difficulty": "medium",
        "note": "청구액 증가 — 청구 키워드 있지만 원인 파악 필요",
    },
    {
        "text": "플랜을 다운그레이드했는데 차액을 돌려받을 수 있나요?",
        "expected": "billing",
        "difficulty": "medium",
        "note": "다운그레이드 후 차액 환불 — billing/account 혼동 가능",
    },
    {
        "text": "무료 체험 기간이 끝나면 자동으로 유료 전환이 되나요?",
        "expected": "billing",
        "difficulty": "medium",
        "note": "자동 유료 전환 — billing 키워드 없고 account와 혼동 가능",
    },
    {
        "text": "3개월치 영수증을 한꺼번에 받을 수 있나요?",
        "expected": "billing",
        "difficulty": "medium",
        "note": "복수 영수증 — billing이지만 '영수증' 키워드 약함",
    },
    {
        "text": "월정액인 줄 알았는데 연간으로 결제가 된 것 같아요.",
        "expected": "billing",
        "difficulty": "medium",
        "note": "결제 주기 오인 — 결제 키워드 있으나 account와 혼동 가능",
    },
    {
        "text": "구독을 해지하고 싶어요.",
        "expected": "billing",
        "difficulty": "medium",
        "note": "구독 해지 — account처럼 보이지만 billing 영역",
    },
    {
        "text": "무료 플랜과 유료 플랜의 기능 차이가 궁금해요.",
        "expected": "billing",
        "difficulty": "medium",
        "note": "요금제 비교 — billing이지만 general로 분류될 수 있음",
    },
    {
        "text": "결제가 pending 상태인데 언제 처리되나요?",
        "expected": "billing",
        "difficulty": "medium",
        "note": "pending 결제 — technical_support로 오인 가능",
    },
    {
        "text": "포인트로 결제하는 방법을 모르겠어요.",
        "expected": "billing",
        "difficulty": "medium",
        "note": "포인트 결제 — technical_support와 혼동 가능",
    },

    # hard ─────────────────────────────────────────
    {
        "text": "모르는 금액이 빠져나갔어요.",
        "expected": "billing",
        "difficulty": "hard",
        "note": "결제/청구 키워드 없음, '빠져나가다'는 간접 표현",
    },
    {
        "text": "멤버십 끊었는데 왜 또 나가요?",
        "expected": "billing",
        "difficulty": "hard",
        "note": "구어체, 결제 키워드 없음, account로 오인 가능",
    },
    {
        "text": "두 번 빠져나간 것 같아요.",
        "expected": "billing",
        "difficulty": "hard",
        "note": "결제/환불 키워드 전혀 없음, 중복 결제 의미",
    },
    {
        "text": "무료라고 해서 썼는데 돈이 나갔어요.",
        "expected": "billing",
        "difficulty": "hard",
        "note": "무료체험 후 자동결제, '결제' 키워드 없음",
    },
    {
        "text": "결제 페이지에서 버튼이 계속 안 눌려요.",
        "expected": "technical_support",
        "difficulty": "hard",
        "note": "표면은 '결제' 키워드이지만 실제는 UI 버그 → technical_support",
    },
    {
        "text": "처리됐다고 하셨는데 아직도 반영이 안 됐어요.",
        "expected": "billing",
        "difficulty": "hard",
        "note": "환불/결제 키워드 없음, 컨텍스트 없는 미반영 불만",
    },
    {
        "text": "로그인할 때마다 결제 정보를 새로 입력하라고 떠요.",
        "expected": "account",
        "difficulty": "hard",
        "note": "표면은 '결제' 키워드이지만 실제 원인은 세션/계정 설정 → account",
    },

    # ══════════════════════════════════════════════
    # account
    # ══════════════════════════════════════════════

    # easy ─────────────────────────────────────────
    {
        "text": "비밀번호를 잊어버렸어요. 재설정 방법을 알려주세요.",
        "expected": "account",
        "difficulty": "easy",
        "note": "비밀번호 분실, 키워드 명확",
    },
    {
        "text": "로그인이 안 됩니다. 계정이 잠긴 것 같아요.",
        "expected": "account",
        "difficulty": "easy",
        "note": "계정 잠금, 키워드 명확",
    },
    {
        "text": "이메일 주소를 변경하고 싶어요.",
        "expected": "account",
        "difficulty": "easy",
        "note": "계정 이메일 변경",
    },
    {
        "text": "계정을 삭제하고 싶습니다.",
        "expected": "account",
        "difficulty": "easy",
        "note": "계정 탈퇴",
    },
    {
        "text": "팀원에게 관리자 권한을 부여하고 싶어요.",
        "expected": "account",
        "difficulty": "easy",
        "note": "권한 관리",
    },
    {
        "text": "회원가입할 때 이메일 인증 메일이 안 와요.",
        "expected": "account",
        "difficulty": "easy",
        "note": "가입 인증 메일 미수신",
    },
    {
        "text": "계정이 해킹된 것 같아요. 빨리 조치해주세요.",
        "expected": "account",
        "difficulty": "easy",
        "note": "계정 보안 침해",
    },
    {
        "text": "2단계 인증 코드를 못 받고 있어요.",
        "expected": "account",
        "difficulty": "easy",
        "note": "2FA 인증 실패",
    },

    # medium ───────────────────────────────────────
    {
        "text": "가입한 이메일이 뭔지 기억이 안 나요.",
        "expected": "account",
        "difficulty": "medium",
        "note": "가입 이메일 분실 — account이지만 general로 오인 가능",
    },
    {
        "text": "다른 기기에서 로그인된 세션을 모두 끊고 싶어요.",
        "expected": "account",
        "difficulty": "medium",
        "note": "세션 강제 종료 — technical_support로 오인 가능",
    },
    {
        "text": "휴면 처리된 계정을 다시 쓰고 싶어요.",
        "expected": "account",
        "difficulty": "medium",
        "note": "휴면 계정 복구 — billing으로 오인 가능",
    },
    {
        "text": "특정 메뉴에 접근이 거부돼요. 권한 문제인가요?",
        "expected": "account",
        "difficulty": "medium",
        "note": "권한 부족 — technical_support와 혼동 가능",
    },
    {
        "text": "임시 비밀번호를 받았는데 그걸로 로그인이 안 돼요.",
        "expected": "account",
        "difficulty": "medium",
        "note": "임시 비밀번호 오류 — technical_support로 오인 가능",
    },
    {
        "text": "이메일 인증 링크를 눌렀는데 에러가 나요.",
        "expected": "account",
        "difficulty": "medium",
        "note": "인증 링크 오류 — technical_support처럼 보이지만 인증 흐름",
    },
    {
        "text": "탈퇴하면 제 결제 내역은 어떻게 되나요?",
        "expected": "account",
        "difficulty": "medium",
        "note": "탈퇴 + 결제 복합 — 주 의도는 탈퇴(account)",
    },
    {
        "text": "로그인이 안 돼서 결제를 못 하고 있어요.",
        "expected": "account",
        "difficulty": "medium",
        "note": "로그인 문제가 결제를 막음 — billing처럼 보이지만 root cause는 account",
    },
    {
        "text": "팀원을 초대했는데 상대방이 초대 메일을 못 받았대요.",
        "expected": "account",
        "difficulty": "medium",
        "note": "팀 초대 메일 — technical_support, shipping으로 오인 가능",
    },

    # hard ─────────────────────────────────────────
    {
        "text": "갑자기 못 들어가게 됐어요.",
        "expected": "account",
        "difficulty": "hard",
        "note": "로그인/계정 키워드 없음, technical_support로 오인 가능",
    },
    {
        "text": "제가 아닌 다른 사람이 접근하고 있는 것 같아요.",
        "expected": "account",
        "difficulty": "hard",
        "note": "해킹 의심, 계정 키워드 없음",
    },
    {
        "text": "예전엔 됐는데 오늘 들어가려니 없다고 나와요.",
        "expected": "account",
        "difficulty": "hard",
        "note": "계정 삭제/비활성 의심, technical_support로 오인 매우 쉬움",
    },
    {
        "text": "팀에서 제 권한이 갑자기 줄어든 것 같아요.",
        "expected": "account",
        "difficulty": "hard",
        "note": "권한 키워드 약함, technical_support로 오인 가능",
    },
    {
        "text": "아무것도 안 했는데 갑자기 나가졌어요.",
        "expected": "account",
        "difficulty": "hard",
        "note": "강제 로그아웃, 구어체, technical_support로 오인 매우 쉬움",
    },
    {
        "text": "친구 추천 링크로 가입하려는데 계속 막혀요.",
        "expected": "account",
        "difficulty": "hard",
        "note": "가입 흐름 오류, technical_support로 오인 가능",
    },
    {
        "text": "환불은 됐는데 아직도 계정에서 유료로 표시돼요.",
        "expected": "account",
        "difficulty": "hard",
        "note": "표면은 '환불(billing)' 키워드, 실제 문제는 계정 상태 동기화 → account",
    },

    # ══════════════════════════════════════════════
    # technical_support
    # ══════════════════════════════════════════════

    # easy ─────────────────────────────────────────
    {
        "text": "앱이 실행되자마자 꺼져요.",
        "expected": "technical_support",
        "difficulty": "easy",
        "note": "앱 크래시, 맥락 명확",
    },
    {
        "text": "파일을 업로드하려는데 계속 오류가 발생해요.",
        "expected": "technical_support",
        "difficulty": "easy",
        "note": "업로드 오류",
    },
    {
        "text": "API 호출할 때 500 에러가 납니다.",
        "expected": "technical_support",
        "difficulty": "easy",
        "note": "API 서버 오류",
    },
    {
        "text": "웹훅이 동작하지 않아요.",
        "expected": "technical_support",
        "difficulty": "easy",
        "note": "웹훅 오류",
    },
    {
        "text": "화면이 하얗게 뜨고 아무것도 안 나와요.",
        "expected": "technical_support",
        "difficulty": "easy",
        "note": "화이트스크린",
    },
    {
        "text": "크롬에서는 되는데 사파리에서는 안 돼요.",
        "expected": "technical_support",
        "difficulty": "easy",
        "note": "브라우저 호환성",
    },
    {
        "text": "인터넷은 되는데 서비스에만 접속이 안 돼요.",
        "expected": "technical_support",
        "difficulty": "easy",
        "note": "서비스 접속 장애",
    },
    {
        "text": "앱 업데이트 후부터 자꾸 튕겨요.",
        "expected": "technical_support",
        "difficulty": "easy",
        "note": "업데이트 후 크래시",
    },

    # medium ───────────────────────────────────────
    {
        "text": "저장을 했는데 새로 고침하면 데이터가 사라져요.",
        "expected": "technical_support",
        "difficulty": "medium",
        "note": "데이터 유실 — account로 오인 가능",
    },
    {
        "text": "모바일에서는 정상인데 PC에서만 이상하게 나와요.",
        "expected": "technical_support",
        "difficulty": "medium",
        "note": "플랫폼 특정 버그 — 오류 키워드 약함",
    },
    {
        "text": "날짜 필터를 적용해도 전체 데이터가 나와요.",
        "expected": "technical_support",
        "difficulty": "medium",
        "note": "필터 기능 오류 — general로 오인 가능",
    },
    {
        "text": "그래프가 실제와 다른 숫자를 보여줘요.",
        "expected": "technical_support",
        "difficulty": "medium",
        "note": "데이터 시각화 오류 — billing으로 오인 가능(금액 관련 시)",
    },
    {
        "text": "공유 링크를 보내줬는데 상대방이 열 수가 없대요.",
        "expected": "technical_support",
        "difficulty": "medium",
        "note": "공유 링크 오류 — account 권한으로 오인 가능",
    },
    {
        "text": "대용량 파일 처리 중 계속 멈춰요.",
        "expected": "technical_support",
        "difficulty": "medium",
        "note": "타임아웃/처리 오류 — 오류 키워드 약함",
    },
    {
        "text": "연동해둔 외부 서비스에서 데이터가 안 넘어와요.",
        "expected": "technical_support",
        "difficulty": "medium",
        "note": "외부 서비스 연동 오류 — account로 오인 가능",
    },
    {
        "text": "서비스가 갑자기 엄청 느려졌어요.",
        "expected": "technical_support",
        "difficulty": "medium",
        "note": "성능 저하 — 명확한 오류 키워드 없음",
    },
    {
        "text": "보고서 생성을 눌렀는데 빈 파일이 다운로드돼요.",
        "expected": "technical_support",
        "difficulty": "medium",
        "note": "보고서 생성 버그 — billing 보고서라면 혼동 가능",
    },

    # hard ─────────────────────────────────────────
    {
        "text": "자꾸 먹통이 돼요.",
        "expected": "technical_support",
        "difficulty": "hard",
        "note": "구어체, 오류 키워드 없음, account로 오인 가능",
    },
    {
        "text": "다 입력했는데 처음부터 다시 하라고 떠요.",
        "expected": "technical_support",
        "difficulty": "hard",
        "note": "폼/세션 초기화 버그, 오류 키워드 없음",
    },
    {
        "text": "어제까지는 잘 됐는데 오늘은 안 돼요.",
        "expected": "technical_support",
        "difficulty": "hard",
        "note": "기능 돌발 중단, account/shipping으로 오인 가능",
    },
    {
        "text": "배송 조회 페이지가 오류가 나요.",
        "expected": "technical_support",
        "difficulty": "hard",
        "note": "표면은 '배송' 키워드이지만 실제는 페이지 오류 → technical_support",
    },
    {
        "text": "입력한 내용이 계속 날아가요.",
        "expected": "technical_support",
        "difficulty": "hard",
        "note": "데이터 유실, '오류' 키워드 없음, 구어체",
    },
    {
        "text": "오늘 서비스가 점검 중인가요?",
        "expected": "technical_support",
        "difficulty": "hard",
        "note": "장애/점검 확인 — general로 오인 가능",
    },
    {
        "text": "뭔가 이상하게 표시돼요.",
        "expected": "technical_support",
        "difficulty": "hard",
        "note": "매우 모호한 UI 오류, 어느 카테고리도 명확하지 않음",
    },

    # ══════════════════════════════════════════════
    # shipping
    # ══════════════════════════════════════════════

    # easy ─────────────────────────────────────────
    {
        "text": "주문한 지 5일이 지났는데 배송이 안 왔어요.",
        "expected": "shipping",
        "difficulty": "easy",
        "note": "배송 지연, 키워드 명확",
    },
    {
        "text": "운송장 번호를 알 수 있을까요?",
        "expected": "shipping",
        "difficulty": "easy",
        "note": "운송장 번호 문의",
    },
    {
        "text": "배송지 주소를 변경하고 싶어요.",
        "expected": "shipping",
        "difficulty": "easy",
        "note": "배송지 변경",
    },
    {
        "text": "물건이 파손된 채로 도착했어요.",
        "expected": "shipping",
        "difficulty": "easy",
        "note": "배송 중 파손",
    },
    {
        "text": "오배송된 것 같아요. 다른 상품이 왔어요.",
        "expected": "shipping",
        "difficulty": "easy",
        "note": "오배송",
    },
    {
        "text": "반품 신청했는데 수거가 안 왔어요.",
        "expected": "shipping",
        "difficulty": "easy",
        "note": "반품 수거 미이행",
    },
    {
        "text": "재배송을 요청하고 싶어요.",
        "expected": "shipping",
        "difficulty": "easy",
        "note": "재배송 요청",
    },
    {
        "text": "출고 예정일을 알 수 있을까요?",
        "expected": "shipping",
        "difficulty": "easy",
        "note": "출고 예정일",
    },

    # medium ───────────────────────────────────────
    {
        "text": "배달 완료라고 뜨는데 받지 못했어요.",
        "expected": "shipping",
        "difficulty": "medium",
        "note": "배송 완료 오류 — technical_support로 오인 가능",
    },
    {
        "text": "주문한 상품 중 일부만 왔어요.",
        "expected": "shipping",
        "difficulty": "medium",
        "note": "부분 배송 — 배송 키워드 약함",
    },
    {
        "text": "주문 후 배송 준비에 며칠이나 걸리나요?",
        "expected": "shipping",
        "difficulty": "medium",
        "note": "출고 준비 기간 — general로 오인 가능",
    },
    {
        "text": "주문을 취소하면 이미 출고된 상품은 어떻게 되나요?",
        "expected": "shipping",
        "difficulty": "medium",
        "note": "출고 후 취소 — billing으로 오인 가능",
    },
    {
        "text": "교환 신청 후 새 상품은 언제 오나요?",
        "expected": "shipping",
        "difficulty": "medium",
        "note": "교환 배송 일정 — billing으로 오인 가능",
    },
    {
        "text": "배송 중 주소 변경이 가능한가요?",
        "expected": "shipping",
        "difficulty": "medium",
        "note": "배송 중 주소 변경 — account로 오인 가능",
    },
    {
        "text": "배송 조회를 하니까 '배송 준비중'에서 안 바뀌어요.",
        "expected": "shipping",
        "difficulty": "medium",
        "note": "배송 상태 고착 — technical_support로 오인 가능",
    },
    {
        "text": "포장이 너무 부실하게 왔어요.",
        "expected": "shipping",
        "difficulty": "medium",
        "note": "포장 불량 — 배송 키워드 없음",
    },
    {
        "text": "주문했는데 확인 이메일이 안 왔어요.",
        "expected": "shipping",
        "difficulty": "medium",
        "note": "주문 확인 메일 미수신 — account/technical_support로 오인 가능",
    },

    # hard ─────────────────────────────────────────
    {
        "text": "분명히 왔다고 하는데 없어요.",
        "expected": "shipping",
        "difficulty": "hard",
        "note": "배송 완료 오류, '배송' 키워드 없음",
    },
    {
        "text": "아직도 소식이 없어요.",
        "expected": "shipping",
        "difficulty": "hard",
        "note": "배송 지연, 배송 키워드 전혀 없음, 가장 모호한 케이스",
    },
    {
        "text": "열어봤더니 다 망가져 있었어요.",
        "expected": "shipping",
        "difficulty": "hard",
        "note": "배송 중 파손, '배송' 키워드 없음",
    },
    {
        "text": "집에 아무도 없을 것 같은데 어떻게 하죠?",
        "expected": "shipping",
        "difficulty": "hard",
        "note": "수령 방법/재배송 문의, 배송 키워드 전혀 없음",
    },
    {
        "text": "언제 오는지 전혀 모르겠어요.",
        "expected": "shipping",
        "difficulty": "hard",
        "note": "배송 추적 불가, 배송 키워드 없음, general로 오인 가능",
    },
    {
        "text": "배송 주소를 바꾸려는데 계정 설정에서 하면 되나요?",
        "expected": "shipping",
        "difficulty": "hard",
        "note": "표면은 '계정' 키워드이지만 목적은 배송지 변경 → shipping",
    },
    {
        "text": "받으러 갔는데 없었어요.",
        "expected": "shipping",
        "difficulty": "hard",
        "note": "배송 분실/오류, 배송 키워드 없음",
    },

    # ══════════════════════════════════════════════
    # general
    # ══════════════════════════════════════════════

    # easy ─────────────────────────────────────────
    {
        "text": "서비스 운영 시간이 어떻게 되나요?",
        "expected": "general",
        "difficulty": "easy",
        "note": "운영 시간 문의",
    },
    {
        "text": "채용 공고를 보고 싶어요.",
        "expected": "general",
        "difficulty": "easy",
        "note": "채용 문의",
    },
    {
        "text": "서비스 이용 약관을 보고 싶어요.",
        "expected": "general",
        "difficulty": "easy",
        "note": "약관 문의",
    },
    {
        "text": "제휴나 파트너십을 제안하고 싶어요.",
        "expected": "general",
        "difficulty": "easy",
        "note": "제휴 제안",
    },
    {
        "text": "개인정보처리방침은 어디서 볼 수 있나요?",
        "expected": "general",
        "difficulty": "easy",
        "note": "개인정보 방침",
    },

    # medium ───────────────────────────────────────
    {
        "text": "서비스를 처음 써보려는데 어떻게 시작하면 되나요?",
        "expected": "general",
        "difficulty": "medium",
        "note": "온보딩 문의 — account로 오인 가능",
    },
    {
        "text": "언론사 취재 관련해서 연락드리고 싶어요.",
        "expected": "general",
        "difficulty": "medium",
        "note": "PR 문의 — general이지만 account로 오인 가능",
    },
    {
        "text": "접근성 지원(스크린리더 등)이 되나요?",
        "expected": "general",
        "difficulty": "medium",
        "note": "접근성 문의 — technical_support로 오인 가능",
    },

    # hard ─────────────────────────────────────────
    {
        "text": "그냥 한번 써보고 싶은데 어디서 시작해야 할지 모르겠어요.",
        "expected": "general",
        "difficulty": "hard",
        "note": "온보딩, 매우 모호, account/technical_support로 오인 가능",
    },
    {
        "text": "담당자랑 직접 통화하고 싶어요.",
        "expected": "general",
        "difficulty": "hard",
        "note": "연락처 문의, 어느 카테고리로도 분류하기 어려움",
    },
]
