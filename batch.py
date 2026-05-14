"""
batch.py — 멀티유저 매일 배치 작업

매일 1회 GitHub Actions가 실행:
  1. arXiv + HF 논문 수집 (공유 풀 — 1번만)
  2. LLM 요약 생성 (공유 — 1번만)
  3. daily_papers 테이블에 저장
  4. Supabase에서 전체 사용자 + 각자 키워드/분야 읽기
  5. 사용자별 필터링 → user_recommendations 테이블에 저장
  6. email_enabled 사용자에게 Resend로 이메일 발송

환경변수 (GitHub Secrets):
  SUPABASE_URL, SUPABASE_SERVICE_KEY, RESEND_API_KEY,
  ANTHROPIC_API_KEY, RESEND_FROM_EMAIL
"""

import os
import sys
import json
from datetime import datetime, timezone

import requests

from fetcher import fetch_all
from filter import filter_and_rank, compute_score
from summarizer import summarize_papers
from profile import get_combined_profile
from trending import collect_trending, compute_aggregate_ranking


# ============================================
# 환경변수
# ============================================
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = os.environ.get("RESEND_FROM_EMAIL", "onboarding@resend.dev")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

LLM_MODEL = "claude-haiku-4-5-20251001"
LLM_PROVIDER = "anthropic"
TOP_N = 10


def _check_env():
    missing = []
    for name, val in [
        ("SUPABASE_URL", SUPABASE_URL),
        ("SUPABASE_SERVICE_KEY", SUPABASE_SERVICE_KEY),
        ("RESEND_API_KEY", RESEND_API_KEY),
        ("ANTHROPIC_API_KEY", ANTHROPIC_API_KEY),
    ]:
        if not val:
            missing.append(name)
    if missing:
        print(f"❌ 환경변수 누락: {', '.join(missing)}")
        sys.exit(1)
    # summarizer.py가 ANTHROPIC_API_KEY를 env에서 읽으므로 보장
    os.environ["ANTHROPIC_API_KEY"] = ANTHROPIC_API_KEY


# ============================================
# Supabase REST API 헬퍼 (service_role 키 = RLS 우회)
# ============================================
def _sb_headers():
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }


def sb_select(table: str, query: str = ""):
    """SELECT — query는 '?select=*&...' 형태."""
    url = f"{SUPABASE_URL}/rest/v1/{table}{query}"
    resp = requests.get(url, headers=_sb_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


def sb_insert(table: str, rows: list, upsert: bool = False):
    """INSERT (여러 행). upsert=True면 충돌 시 무시/갱신."""
    if not rows:
        return []
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = _sb_headers()
    headers["Prefer"] = "resolution=merge-duplicates" if upsert else "return=minimal"
    # 큰 배열은 나눠서
    CHUNK = 500
    for i in range(0, len(rows), CHUNK):
        chunk = rows[i:i + CHUNK]
        resp = requests.post(url, headers=headers, json=chunk, timeout=60)
        if resp.status_code >= 400:
            print(f"  ⚠ insert 실패 ({table}): {resp.status_code} {resp.text[:300]}")
            resp.raise_for_status()
    return True


def sb_delete(table: str, query: str):
    """DELETE — query는 '?run_date=eq.2026-05-14' 형태."""
    url = f"{SUPABASE_URL}/rest/v1/{table}{query}"
    resp = requests.delete(url, headers=_sb_headers(), timeout=30)
    if resp.status_code >= 400:
        print(f"  ⚠ delete 실패 ({table}): {resp.status_code} {resp.text[:200]}")


# ============================================
# 1~2. 논문 수집 + 요약 (공유 풀)
# ============================================
def collect_and_summarize():
    """모든 분야 카테고리 합쳐서 한 번에 수집 + 요약."""
    # 15개 분야의 모든 arxiv 카테고리 union
    all_field_ids = ["data-mining", "ml-general", "nlp", "cv",
                     "speech", "robotics", "database", "security",
                     "multimodal", "graph-ml", "theory", "hci",
                     "software", "bioinformatics", "graphics"]
    combined = get_combined_profile(all_field_ids)
    categories = combined["arxiv_categories"]
    print(f"📡 논문 수집 — 카테고리: {categories}")

    papers = fetch_all(categories, max_papers=200)
    print(f"   → {len(papers)}편 수집")

    if not papers:
        print("   ⚠ 수집된 논문 없음")
        return []

    # 전체 요약 (캐시 활용 — summarizer가 translations.json 캐시 사용)
    print(f"📝 LLM 요약 생성 중... ({len(papers)}편, 캐시 활용)")
    papers = summarize_papers(papers, model=LLM_MODEL, provider=LLM_PROVIDER)
    print(f"   → 요약 완료")

    return papers


# ============================================
# 3. daily_papers 테이블에 저장
# ============================================
def save_daily_papers(papers: list, run_date: str):
    print(f"💾 daily_papers 저장 ({run_date})")
    # 같은 날짜 기존 데이터 삭제 (재실행 대비)
    sb_delete("daily_papers", f"?run_date=eq.{run_date}")

    rows = []
    for p in papers:
        rows.append({
            "run_date": run_date,
            "paper_id": p.get("id", ""),
            "title": p.get("title", ""),
            "abstract": p.get("abstract", ""),
            "summary_ko": p.get("summary_ko", ""),
            "arxiv_url": p.get("arxiv_url", ""),
            "pdf_url": p.get("pdf_url", ""),
            "hf_url": p.get("hf_url", ""),
            "categories": p.get("categories", []),
            "hf_likes": p.get("hf_likes", 0),
            "is_recent_24h": p.get("is_recent_24h", False),
        })
    sb_insert("daily_papers", rows, upsert=True)
    print(f"   → {len(rows)}편 저장")


# ============================================
# 4. 전체 사용자 + 키워드/분야 읽기
# ============================================
def load_all_users():
    """profiles + user_keywords + user_fields 를 합쳐서 사용자별 dict."""
    profiles = sb_select("profiles", "?select=id,email,display_name,email_enabled")
    keywords = sb_select("user_keywords", "?select=user_id,keyword")
    fields = sb_select("user_fields", "?select=user_id,field_id")

    # user_id → 키워드 리스트
    kw_map = {}
    for k in keywords:
        kw_map.setdefault(k["user_id"], []).append(k["keyword"])
    # user_id → 분야 리스트
    fld_map = {}
    for f in fields:
        fld_map.setdefault(f["user_id"], []).append(f["field_id"])

    users = []
    for p in profiles:
        uid = p["id"]
        users.append({
            "id": uid,
            "email": p.get("email", ""),
            "display_name": p.get("display_name", ""),
            "email_enabled": p.get("email_enabled", True),
            "keywords": kw_map.get(uid, []),
            "fields": fld_map.get(uid, []),
        })
    print(f"👥 사용자 {len(users)}명 로드")
    return users


# ============================================
# 5. 사용자별 필터링 → user_recommendations 저장
# ============================================
def build_recommendations(users: list, papers: list, run_date: str):
    print(f"🎯 사용자별 추천 생성")
    # 같은 날짜 기존 추천 삭제 (재실행 대비)
    sb_delete("user_recommendations", f"?run_date=eq.{run_date}")

    all_rows = []
    # 사용자별 결과도 메모리에 들고 있음 (이메일 발송용)
    user_results = {}

    for user in users:
        uid = user["id"]
        keywords = user["keywords"]
        field_ids = user["fields"]

        # picks: 키워드 매칭 상위
        picks = filter_and_rank(papers, keywords, top_n=TOP_N) if keywords else []

        # new: 24시간 이내 + 키워드 매칭
        recent = [p for p in papers if p.get("is_recent_24h", False)]
        new_papers = filter_and_rank(recent, keywords, top_n=TOP_N) if keywords else []

        # field: 분야 seed 키워드 기반
        field_papers = []
        if field_ids:
            combined = get_combined_profile(field_ids)
            seed_kw = combined.get("seed_keywords", [])
            if seed_kw:
                used_ids = {p.get("id") for p in picks} | {p.get("id") for p in new_papers}
                remaining = [p for p in papers if p.get("id") not in used_ids]
                field_papers = filter_and_rank(remaining, seed_kw, top_n=TOP_N)

        user_results[uid] = {
            "picks": picks,
            "new": new_papers,
            "field": field_papers,
            "user": user,
        }

        # DB 행 만들기
        for rec_type, plist in [("picks", picks), ("new", new_papers), ("field", field_papers)]:
            for rank, p in enumerate(plist, 1):
                all_rows.append({
                    "user_id": uid,
                    "run_date": run_date,
                    "rec_type": rec_type,
                    "paper_id": p.get("id", ""),
                    "rank": rank,
                    "matched_keywords": p.get("matched_keywords", []),
                })

    sb_insert("user_recommendations", all_rows)
    print(f"   → 추천 {len(all_rows)}건 저장 ({len(users)}명 분)")
    return user_results


# ============================================
# 6. 이메일 발송 (Resend)
# ============================================
def send_email(to_email: str, display_name: str, results: dict, run_date: str):
    """한 사용자에게 추천 이메일 발송."""
    picks = results["picks"]
    new_papers = results["new"]
    field_papers = results["field"]

    if not (picks or new_papers or field_papers):
        return False  # 보낼 내용 없음

    def paper_block(p):
        title = (p.get("title", "")).replace("<", "&lt;")
        summary = (p.get("summary_ko") or p.get("abstract", "")[:200]).replace("<", "&lt;")
        url = p.get("arxiv_url", "#")
        return (
            f'<div style="margin-bottom:16px;padding-bottom:16px;border-bottom:1px solid #f0f0f0">'
            f'<a href="{url}" style="color:#191f28;text-decoration:none;font-weight:600;font-size:15px">{title}</a>'
            f'<p style="color:#4e5968;font-size:13px;line-height:1.6;margin:6px 0 0">{summary}</p>'
            f'</div>'
        )

    sections = []
    if picks:
        sections.append(
            '<h3 style="font-size:14px;color:#191f28;margin:24px 0 12px">📌 오늘의 추천</h3>'
            + "".join(paper_block(p) for p in picks[:5])
        )
    if new_papers:
        sections.append(
            '<h3 style="font-size:14px;color:#191f28;margin:24px 0 12px">✨ 새로 읽을 것</h3>'
            + "".join(paper_block(p) for p in new_papers[:5])
        )
    if field_papers:
        sections.append(
            '<h3 style="font-size:14px;color:#191f28;margin:24px 0 12px">🎓 내 분야 소식</h3>'
            + "".join(paper_block(p) for p in field_papers[:5])
        )

    html = (
        f'<div style="font-family:-apple-system,sans-serif;max-width:600px;margin:0 auto;padding:24px">'
        f'<h1 style="font-size:20px;color:#191f28">AI 트렌드 뉴스레터</h1>'
        f'<p style="color:#8b95a1;font-size:13px">{run_date} · {display_name}님을 위한 추천</p>'
        + "".join(sections)
        + '<p style="color:#b0b8c1;font-size:12px;margin-top:32px">'
          'Trend Newsletter · 설정에서 이메일 수신을 끌 수 있어요</p>'
        f'</div>'
    )

    resp = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "from": RESEND_FROM_EMAIL,
            "to": [to_email],
            "subject": f"[AI 트렌드] {run_date} 오늘의 추천 논문",
            "html": html,
        },
        timeout=30,
    )
    if resp.status_code >= 400:
        print(f"   ⚠ 이메일 실패 ({to_email}): {resp.status_code} {resp.text[:200]}")
        return False
    return True


def send_all_emails(user_results: dict, run_date: str):
    print(f"📧 이메일 발송")
    sent = 0
    skipped = 0
    for uid, results in user_results.items():
        user = results["user"]
        if not user["email_enabled"]:
            skipped += 1
            continue
        if not user["email"]:
            skipped += 1
            continue
        ok = send_email(user["email"], user["display_name"] or "사용자", results, run_date)
        if ok:
            sent += 1
        else:
            skipped += 1
    print(f"   → 발송 {sent}건, 건너뜀 {skipped}건")


# ============================================
# 트렌딩 수집 + 저장 (전체 공통)
# ============================================
def collect_and_save_trending(run_date: str):
    """트렌딩 키워드 수집 → daily_trending 테이블에 저장."""
    print(f"🌐 트렌딩 수집")
    try:
        trending = collect_trending()
    except Exception as e:
        print(f"   ⚠ 트렌딩 수집 실패: {e}")
        return

    # 같은 날짜 기존 데이터 삭제
    sb_delete("daily_trending", f"?run_date=eq.{run_date}")

    rows = []
    # arxiv / hf / active(구 pwc) 3개 소스
    for source in ["arxiv", "hf", "pwc"]:
        # 죽은 pwc는 라벨을 active로 저장 (데이터는 HF fallback)
        label = "active" if source == "pwc" else source
        for rank, item in enumerate(trending.get(source, []), 1):
            rows.append({
                "run_date": run_date,
                "source": label,
                "keyword": item.get("keyword", ""),
                "count": item.get("count", 0),
                "rank": rank,
            })

    if rows:
        sb_insert("daily_trending", rows, upsert=True)
        print(f"   → 트렌딩 {len(rows)}건 저장")
    else:
        print(f"   ⚠ 저장할 트렌딩 데이터 없음")


# ============================================
# 메인
# ============================================
def main():
    print("=" * 50)
    print("멀티유저 배치 작업 시작")
    print("=" * 50)
    _check_env()

    run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"📅 실행 날짜: {run_date}\n")

    # 1~2. 수집 + 요약
    papers = collect_and_summarize()
    if not papers:
        print("논문이 없어 종료합니다.")
        return
    print()

    # 3. daily_papers 저장
    save_daily_papers(papers, run_date)
    print()

    # 4. 사용자 로드
    users = load_all_users()
    if not users:
        print("사용자가 없어 종료합니다.")
        return
    print()

    # 5. 사용자별 추천 생성 + 저장
    user_results = build_recommendations(users, papers, run_date)
    print()

    # 6. 이메일 발송
    send_all_emails(user_results, run_date)
    print()

    # 7. 트렌딩 수집 + 저장 (전체 공통)
    collect_and_save_trending(run_date)
    print()

    print("=" * 50)
    print("✅ 배치 작업 완료!")
    print("=" * 50)


if __name__ == "__main__":
    main()