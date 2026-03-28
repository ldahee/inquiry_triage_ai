"""
Router Agent 분류 정확도 평가 스크립트.

실행:
    cd backend
    python -m tests.eval.eval_router                         # 전체 실행
    python -m tests.eval.eval_router --difficulty hard       # 특정 난이도만
    python -m tests.eval.eval_router --category billing      # 특정 카테고리만
    python -m tests.eval.eval_router --output tests/eval/results/router_results.json   # JSON 저장

의존성:
    - OPENAI_API_KEY 환경변수 또는 .env 파일 필요
    - scikit-learn: pip install scikit-learn
"""
import argparse
import asyncio
import json
import sys
import time
from collections import defaultdict
from typing import Optional

from tests.eval.router_testset import ROUTER_TESTSET
from app.chains.router_chain import run_router_chain

CATEGORIES = ["billing", "account", "technical_support", "shipping", "general"]
DIFFICULTIES = ["easy", "medium", "hard"]


# ──────────────────────────────────────────────
# 평가 실행
# ──────────────────────────────────────────────

async def evaluate_single(case: dict) -> dict:
    """케이스 하나를 실행하고 결과를 반환합니다."""
    start = time.monotonic()
    result = await run_router_chain(case["text"])
    latency_ms = int((time.monotonic() - start) * 1000)

    if result is None:
        return {
            **case,
            "predicted": None,
            "confidence": None,
            "routing_reason": None,
            "correct": False,
            "parse_failed": True,
            "latency_ms": latency_ms,
        }

    return {
        **case,
        "predicted": result.category,
        "confidence": result.confidence,
        "routing_reason": result.routing_reason,
        "correct": result.category == case["expected"],
        "parse_failed": False,
        "latency_ms": latency_ms,
    }


async def run_evaluation(
    difficulty: Optional[str] = None,
    category: Optional[str] = None,
    concurrency: int = 5,
) -> list[dict]:
    """테스트셋 전체(또는 필터된)를 평가하고 결과 리스트를 반환합니다."""
    cases = ROUTER_TESTSET

    if difficulty:
        cases = [c for c in cases if c["difficulty"] == difficulty]
    if category:
        cases = [c for c in cases if c["expected"] == category]

    if not cases:
        print("조건에 맞는 케이스가 없습니다.")
        return []

    print(f"\n평가 시작: {len(cases)}개 케이스 (concurrency={concurrency})")
    print("─" * 60)

    results = []
    semaphore = asyncio.Semaphore(concurrency)

    async def run_with_semaphore(case: dict, idx: int) -> dict:
        async with semaphore:
            result = await evaluate_single(case)
            status = "✓" if result["correct"] else "✗"
            diff_label = result["difficulty"].upper()[:1]  # E/M/H
            print(
                f"[{idx+1:03d}/{len(cases)}] {status} [{diff_label}] "
                f"{result['expected']:20s} → {str(result['predicted']):20s} "
                f"({result.get('confidence', 0) or 0:.2f})  "
                f"{result['text'][:40]}\n"
                f"         근거: {result.get('routing_reason', '') or ''}"
            )
            return result

    tasks = [run_with_semaphore(case, i) for i, case in enumerate(cases)]
    results = await asyncio.gather(*tasks)
    return list(results)


# ──────────────────────────────────────────────
# 리포트 출력
# ──────────────────────────────────────────────

def print_report(results: list[dict]) -> None:
    if not results:
        return

    total = len(results)
    correct = sum(1 for r in results if r["correct"])
    parse_failed = sum(1 for r in results if r.get("parse_failed"))
    avg_latency = sum(r["latency_ms"] for r in results) / total

    print("\n" + "═" * 60)
    print("ROUTER 평가 리포트")
    print("═" * 60)
    print(f"전체 정확도  : {correct}/{total}  ({correct/total*100:.1f}%)")
    print(f"파싱 실패    : {parse_failed}건")
    print(f"평균 레이턴시: {avg_latency:.0f}ms")

    # 난이도별 정확도
    print("\n[난이도별 정확도]")
    for diff in DIFFICULTIES:
        group = [r for r in results if r["difficulty"] == diff]
        if not group:
            continue
        g_correct = sum(1 for r in group if r["correct"])
        print(f"  {diff:8s}: {g_correct:3d}/{len(group):3d}  ({g_correct/len(group)*100:.1f}%)")

    # 카테고리별 정확도
    print("\n[카테고리별 정확도]")
    for cat in CATEGORIES:
        group = [r for r in results if r["expected"] == cat]
        if not group:
            continue
        g_correct = sum(1 for r in group if r["correct"])
        print(f"  {cat:20s}: {g_correct:3d}/{len(group):3d}  ({g_correct/len(group)*100:.1f}%)")

    # Confusion matrix (expected × predicted)
    print("\n[Confusion Matrix]")
    header = f"{'':20s}" + "".join(f"{c[:8]:>10s}" for c in CATEGORIES)
    print(header)
    for expected in CATEGORIES:
        row = [r for r in results if r["expected"] == expected]
        if not row:
            continue
        counts = defaultdict(int)
        for r in row:
            pred = r["predicted"] or "parse_fail"
            counts[pred] += 1
        line = f"{expected:20s}" + "".join(f"{counts.get(c, 0):>10d}" for c in CATEGORIES)
        print(line)

    # 오답 케이스
    wrong = [r for r in results if not r["correct"]]
    if wrong:
        print(f"\n[오답 케이스 — {len(wrong)}건]")
        for r in sorted(wrong, key=lambda x: x["difficulty"]):
            diff_label = r["difficulty"].upper()
            print(
                f"  [{diff_label}] expected={r['expected']:20s} predicted={str(r['predicted']):20s}\n"
                f"         text   : {r['text']}\n"
                f"         reason : {r.get('routing_reason', '')}\n"
                f"         note   : {r.get('note', '')}\n"
            )

    print("═" * 60)


# ──────────────────────────────────────────────
# Confusion matrix (sklearn) — optional
# ──────────────────────────────────────────────

def print_sklearn_report(results: list[dict]) -> None:
    try:
        from sklearn.metrics import classification_report, confusion_matrix
    except ImportError:
        print("\n(scikit-learn 미설치 — 상세 분류 리포트 생략)")
        return

    y_true = [r["expected"] for r in results if not r.get("parse_failed")]
    y_pred = [r["predicted"] for r in results if not r.get("parse_failed")]

    if not y_true:
        return

    print("\n[sklearn classification_report]")
    print(classification_report(y_true, y_pred, labels=CATEGORIES, zero_division=0))


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Router Agent 분류 정확도 평가")
    parser.add_argument(
        "--difficulty",
        choices=DIFFICULTIES,
        default=None,
        help="특정 난이도만 평가 (easy/medium/hard)",
    )
    parser.add_argument(
        "--category",
        choices=CATEGORIES,
        default=None,
        help="특정 카테고리만 평가",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="동시 LLM 호출 수 (기본값: 5)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="결과를 저장할 JSON 파일 경로",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    results = await run_evaluation(
        difficulty=args.difficulty,
        category=args.category,
        concurrency=args.concurrency,
    )

    if not results:
        sys.exit(1)

    print_report(results)
    print_sklearn_report(results)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n결과 저장 완료: {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
