"""평가셋 전체를 돌려 Text-to-SQL 정확도(Execution Accuracy)를 계산합니다.

실행 예:
  python evaluate.py                                   (app.py 설정 그대로 1번)
  python evaluate.py --name exp2_rag                   (결과 파일에 실험 이름 붙이기)
  python evaluate.py --mode none --repeat 3 --name baseline_v2
                                                       (용어 사전 없이 3번 반복)
  python evaluate.py --mode rag --repeat 3 --name exp2_rag
  python evaluate.py --type glossary                   (용어 문제만)
  python evaluate.py --limit 5                         (앞의 5문제만 빠르게 테스트)

--mode 를 주면 app.py의 GLOSSARY_MODE 대신 그 값을 씁니다 (none / full / rag).
"""
import argparse
import csv
import json
import os
import sqlite3
import statistics
import time
from datetime import datetime

import app  # app.py의 설정과 함수를 그대로 사용

TIMEOUT_SEC = 20  # 너무 오래 걸리는 쿼리는 중단
TYPES = ("basic", "glossary")


def normalize(rows):
    """결과 비교용으로 정리: 소수는 반올림, 행 순서와 열 순서는 무시."""
    out = []
    for row in rows:
        vals = []
        for v in row:
            if isinstance(v, float):
                v = round(v, 2)
            vals.append(str(v))
        out.append(tuple(sorted(vals)))
    return sorted(out)


def run(sql):
    conn = sqlite3.connect(f"file:{app.DB_PATH}?mode=ro", uri=True)  # 읽기 전용
    start = time.time()
    # 20초가 넘으면 쿼리 중단 (잘못된 JOIN으로 끝나지 않는 경우 대비)
    conn.set_progress_handler(lambda: int(time.time() - start > TIMEOUT_SEC), 100000)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def acc(rows):
    return 100 * sum(r["correct"] for r in rows) / len(rows) if rows else 0.0


def evaluate_once(items, round_no, total_rounds):
    results = []
    for item in items:
        pred_sql, error, correct = "", "", False
        try:
            pred_sql = app.text_to_sql(item["question"])
            if not app.is_safe(pred_sql):
                error = "SELECT가 아닌 쿼리"
            else:
                correct = normalize(run(pred_sql)) == normalize(run(item["sql"]))
        except Exception as e:
            error = str(e)[:200]
            if error == "interrupted":
                error = f"시간 초과 ({TIMEOUT_SEC}초)"

        mark = "O" if correct else "X"
        prefix = f"[{round_no}/{total_rounds}]" if total_rounds > 1 else ""
        print(f"{prefix}[{mark}] {item['id']:>2} ({item.get('type', '-')}/{item['level']}) {item['question']}")
        if error:
            print(f"      오류: {error}")
        results.append({**item, "pred_sql": pred_sql, "correct": correct, "error": error})
        time.sleep(0.5)  # API 요청 사이 잠깐 쉬기
    return results


def print_summary(results):
    def line(label, rows):
        if rows:
            print(f"  {label:<9}: {acc(rows):5.1f}%  ({sum(r['correct'] for r in rows)}/{len(rows)})")

    print(f"전체: {acc(results):.1f}%  ({sum(r['correct'] for r in results)}/{len(results)})")
    print("[문제 종류별]")
    for t in TYPES:
        line(t, [r for r in results if r.get("type") == t])
    print("[난이도별]")
    for level in ("easy", "medium", "hard"):
        line(level, [r for r in results if r["level"] == level])


def save_csv(results, path):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f, fieldnames=["id", "type", "level", "question", "correct", "sql", "pred_sql", "error"]
        )
        writer.writeheader()
        for r in results:
            writer.writerow({k: r.get(k, "") for k in writer.fieldnames})


def mean_range(values):
    m = statistics.mean(values)
    sd = statistics.stdev(values) if len(values) > 1 else 0.0
    return f"평균 {m:5.1f}%  (표준편차 {sd:.1f}, 최저 {min(values):.1f} ~ 최고 {max(values):.1f})"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="run", help="실험 이름")
    parser.add_argument("--mode", choices=["none", "full", "rag"], help="용어 사전 모드 (생략하면 app.py 설정)")
    parser.add_argument("--repeat", type=int, default=1, help="같은 설정으로 반복할 횟수")
    parser.add_argument("--eval", default="eval_set.json", help="평가셋 파일")
    parser.add_argument("--type", default=None, help="basic 또는 glossary만 실행")
    parser.add_argument("--limit", type=int, default=None, help="앞에서 N문제만 실행")
    args = parser.parse_args()

    if args.mode:
        app.GLOSSARY_MODE = args.mode
    mode = getattr(app, "GLOSSARY_MODE", "-")

    with open(args.eval, encoding="utf-8") as f:
        items = json.load(f)
    if args.type:
        items = [x for x in items if x.get("type") == args.type]
    if args.limit:
        items = items[: args.limit]

    os.makedirs("results", exist_ok=True)
    stamp = f"{datetime.now():%Y%m%d_%H%M}"
    all_runs = []

    for i in range(1, args.repeat + 1):
        results = evaluate_once(items, i, args.repeat)
        all_runs.append(results)
        suffix = f"_r{i}" if args.repeat > 1 else ""
        path = f"results/{stamp}_{args.name}{suffix}.csv"
        save_csv(results, path)
        print(f"\n========== 결과 ({i}/{args.repeat}) ==========")
        print(f"실험: {args.name}  (DB: {app.DB_PATH}, 용어 사전: {mode}, 평가셋: {args.eval})")
        print_summary(results)
        print(f"자세한 결과: {path}\n")

    if args.repeat == 1:
        return

    # ── 반복 실행 요약 ──
    print("=" * 50)
    print(f"반복 요약: {args.name}  ({args.repeat}번, 용어 사전: {mode})")
    print(f"  전체     : {mean_range([acc(r) for r in all_runs])}")
    for t in TYPES:
        vals = [acc([x for x in r if x.get("type") == t]) for r in all_runs]
        if any(x.get("type") == t for x in all_runs[0]):
            print(f"  {t:<9}: {mean_range(vals)}")

    # 문제별로 몇 번 맞았는지
    passes = {}
    for r in all_runs:
        for x in r:
            passes.setdefault(x["id"], {"item": x, "n": 0, "preds": []})
            passes[x["id"]]["n"] += int(x["correct"])
            if not x["correct"]:
                passes[x["id"]]["preds"].append(x["pred_sql"] or x["error"])

    flaky = [p for p in passes.values() if 0 < p["n"] < args.repeat]
    always_wrong = [p for p in passes.values() if p["n"] == 0]

    print(f"\n가끔 틀리는 문제 (변동성): {len(flaky)}개")
    for p in flaky:
        print(f"  - {p['item']['id']}번 ({p['n']}/{args.repeat} 정답) {p['item']['question']}")
    print(f"항상 틀리는 문제 (실제 약점): {len(always_wrong)}개")
    for p in always_wrong:
        print(f"  - {p['item']['id']}번 {p['item']['question']}")

    # 틀린 문제 상세는 파일로
    path = f"results/{stamp}_{args.name}_wrong.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["id", "type", "정답 횟수", "question", "정답 SQL", "틀린 SQL (예시)"])
        for p in flaky + always_wrong:
            it = p["item"]
            w.writerow([it["id"], it.get("type", ""), f"{p['n']}/{args.repeat}", it["question"], it["sql"], p["preds"][0]])
    print(f"\n틀린 문제 상세: {path}")


if __name__ == "__main__":
    main()
