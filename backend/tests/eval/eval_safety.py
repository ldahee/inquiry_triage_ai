"""
Safety Agent 평가 스크립트.

실행:
    cd backend
    python -m tests.eval.eval_safety                         # 전체 실행
    python -m tests.eval.eval_safety --difficulty hard       # 특정 난이도만
    python -m tests.eval.eval_safety --type fp               # FP 위험 케이스만 (safe 문의)
    python -m tests.eval.eval_safety --type fn               # FN 위험 케이스만 (unsafe 문의)
    python -m tests.eval.eval_safety --output tests/eval/results/safety_results.json   # JSON 저장

의존성:
    - OPENAI_API_KEY 환경변수 또는 .env 파일 필요
"""
import argparse
import asyncio
import json
import sys
import time
from typing import Optional

from tests.eval.safety_testset import SAFETY_TESTSET
from app.agents.safety import safety_chain

DIFFICULTIES = ["easy", "medium", "hard"]


# ──────────────────────────────────────────────
# 평가 실행
# ──────────────────────────────────────────────

async def evaluate_single(case: dict) -> dict:
    """케이스 하나를 실행하고 결과를 반환합니다."""
    start = time.monotonic()
    try:
        result = await safety_chain.ainvoke({"inquiry_text": case["text"]})
        is_safe = result.is_safe
        reason = result.reason
        parse_failed = False
    except Exception as e:
        is_safe = False  # fail-closed
        reason = f"[ERROR] {e}"
        parse_failed = True

    latency_ms = int((time.monotonic() - start) * 1000)
    correct = (is_safe == case["expected_safe"])

    # 오류 유형 분류
    error_type = None
    if not correct:
        error_type = "FP" if case["expected_safe"] else "FN"

    return {
        **case,
        "predicted_safe": is_safe,
        "reason": reason,
        "correct": correct,
        "error_type": error_type,
        "parse_failed": parse_failed,
        "latency_ms": latency_ms,
    }


async def run_evaluation(
    difficulty: Optional[str] = None,
    filter_type: Optional[str] = None,  # "fp" | "fn"
    concurrency: int = 5,
) -> list[dict]:
    cases = SAFETY_TESTSET

    if difficulty:
        cases = [c for c in cases if c["difficulty"] == difficulty]
    if filter_type == "fp":
        cases = [c for c in cases if c["expected_safe"] is True]
    elif filter_type == "fn":
        cases = [c for c in cases if c["expected_safe"] is False]

    if not cases:
        print("조건에 맞는 케이스가 없습니다.")
        return []

    safe_count = sum(1 for c in cases if c["expected_safe"])
    unsafe_count = len(cases) - safe_count
    print(f"\n평가 시작: {len(cases)}개 케이스 (safe={safe_count}, unsafe={unsafe_count}, concurrency={concurrency})")
    print("─" * 70)

    semaphore = asyncio.Semaphore(concurrency)

    async def run_with_semaphore(case: dict, idx: int) -> dict:
        async with semaphore:
            result = await evaluate_single(case)
            status = "✓" if result["correct"] else "✗"
            diff_label = result["difficulty"].upper()[:1]
            expected_label = "SAFE  " if result["expected_safe"] else "UNSAFE"
            predicted_label = "SAFE  " if result["predicted_safe"] else "UNSAFE"
            err = f" ← {result['error_type']}" if result["error_type"] else ""
            print(
                f"[{idx+1:03d}/{len(cases)}] {status} [{diff_label}] "
                f"{expected_label} → {predicted_label}{err}  "
                f"{result['text'][:45]}\n"
                f"         근거: {result.get('reason', '') or ''}"
            )
            return result

    tasks = [run_with_semaphore(case, i) for i, case in enumerate(cases)]
    return list(await asyncio.gather(*tasks))


# ──────────────────────────────────────────────
# 리포트 출력
# ──────────────────────────────────────────────

def print_report(results: list[dict]) -> None:
    if not results:
        return

    total = len(results)
    correct = sum(1 for r in results if r["correct"])
    fp_cases = [r for r in results if r["error_type"] == "FP"]
    fn_cases = [r for r in results if r["error_type"] == "FN"]
    parse_failed = sum(1 for r in results if r.get("parse_failed"))
    avg_latency = sum(r["latency_ms"] for r in results) / total

    safe_results = [r for r in results if r["expected_safe"]]
    unsafe_results = [r for r in results if not r["expected_safe"]]

    print("\n" + "═" * 70)
    print("SAFETY AGENT 평가 리포트")
    print("═" * 70)
    print(f"전체 정확도  : {correct}/{total}  ({correct/total*100:.1f}%)")
    print(f"파싱 실패    : {parse_failed}건")
    print(f"평균 레이턴시: {avg_latency:.0f}ms")

    print("\n[오류 유형별 집계]")
    if safe_results:
        fp_count = len(fp_cases)
        print(f"  FP (과차단) : {fp_count:2d}/{len(safe_results):2d}  ({fp_count/len(safe_results)*100:.1f}%)  — 정상 문의를 차단")
    if unsafe_results:
        fn_count = len(fn_cases)
        print(f"  FN (과허용) : {fn_count:2d}/{len(unsafe_results):2d}  ({fn_count/len(unsafe_results)*100:.1f}%)  — 위험 문의를 통과")

    print("\n[Confusion Matrix]")
    print(f"{'':20s} {'예측: SAFE':>12s} {'예측: UNSAFE':>12s}")
    tp = sum(1 for r in results if r["expected_safe"] and r["predicted_safe"])
    fp_m = sum(1 for r in results if r["expected_safe"] and not r["predicted_safe"])
    fn_m = sum(1 for r in results if not r["expected_safe"] and r["predicted_safe"])
    tn = sum(1 for r in results if not r["expected_safe"] and not r["predicted_safe"])
    print(f"  실제: SAFE  {'':8s} {tp:>12d} {fp_m:>12d}")
    print(f"  실제: UNSAFE{'':8s} {fn_m:>12d} {tn:>12d}")

    precision = tp / (tp + fn_m) if (tp + fn_m) else 0
    recall = tp / (tp + fp_m) if (tp + fp_m) else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0
    print(f"\n  Precision (safe)  : {precision:.3f}")
    print(f"  Recall    (safe)  : {recall:.3f}")
    print(f"  F1        (safe)  : {f1:.3f}")

    print("\n[난이도별 정확도]")
    for diff in DIFFICULTIES:
        group = [r for r in results if r["difficulty"] == diff]
        if not group:
            continue
        g_correct = sum(1 for r in group if r["correct"])
        g_fp = sum(1 for r in group if r["error_type"] == "FP")
        g_fn = sum(1 for r in group if r["error_type"] == "FN")
        print(
            f"  {diff:8s}: {g_correct:2d}/{len(group):2d}  ({g_correct/len(group)*100:.1f}%)"
            f"  FP={g_fp} FN={g_fn}"
        )

    # FP 오답 케이스
    if fp_cases:
        print(f"\n[FP 오답 — 정상 문의를 차단한 케이스 ({len(fp_cases)}건)]")
        for r in sorted(fp_cases, key=lambda x: x["difficulty"]):
            print(
                f"  [{r['difficulty'].upper()[:1]}] {r['text']}\n"
                f"         reason : {r.get('reason', '')}\n"
                f"         note   : {r.get('note', '')}\n"
            )

    # FN 오답 케이스
    if fn_cases:
        print(f"\n[FN 오답 — 위험 문의를 통과시킨 케이스 ({len(fn_cases)}건)]")
        for r in sorted(fn_cases, key=lambda x: x["difficulty"]):
            print(
                f"  [{r['difficulty'].upper()[:1]}] {r['text']}\n"
                f"         reason : {r.get('reason', '')}\n"
                f"         note   : {r.get('note', '')}\n"
            )

    print("═" * 70)


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Safety Agent 평가")
    parser.add_argument(
        "--difficulty",
        choices=DIFFICULTIES,
        default=None,
        help="특정 난이도만 평가",
    )
    parser.add_argument(
        "--type",
        choices=["fp", "fn"],
        default=None,
        dest="filter_type",
        help="fp: safe 케이스만(과차단 위험), fn: unsafe 케이스만(과허용 위험)",
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
        filter_type=args.filter_type,
        concurrency=args.concurrency,
    )

    if not results:
        sys.exit(1)

    print_report(results)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n결과 저장 완료: {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
