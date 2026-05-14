"""
trend-newsletter 메인 파이프라인.

매일 1회 실행:
1. config.yaml 로드
2. arXiv + HF Daily Papers fetch
3. 사용자 키워드로 필터링 + 점수 매기기 (없으면 키워드 자동 추천)
4. 상위 N편 LLM으로 요약
5. HTML 대시보드 생성 + 이메일 발송
"""

import sys
import os
import json
import yaml
from datetime import datetime, timedelta

from fetcher import fetch_all
from filter import filter_and_rank, suggest_keywords, compute_score
from summarizer import summarize_papers
from sender import save_dashboard, send_email, save_trending_page
from trending import collect_trending, save_trending
from profile import get_combined_profile


def load_profiles_file(path: str = "profiles.json") -> list:
    """
    profiles.json 우선 로드. 없으면 None → config.yaml의 research_profile 사용.

    파일 구조:
    {
      "profiles": ["data-mining", "nlp"],
      "updated_at": "2026-05-13"
    }
    """
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("profiles", [])
    except Exception as e:
        print(f"  ⚠ {path} 로드 실패: {e}")
        return None


RECOMMENDED_HISTORY_PATH = "recommended-history.json"
RECOMMENDED_HISTORY_DAYS = 14  # 최근 14일치 유지


def _load_recommended_ids() -> set:
    """이전에 추천된 paper id 모음 (최근 14일치)."""
    if not os.path.exists(RECOMMENDED_HISTORY_PATH):
        return set()
    try:
        with open(RECOMMENDED_HISTORY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        cutoff = (datetime.now() - timedelta(days=RECOMMENDED_HISTORY_DAYS)).strftime("%Y-%m-%d")
        all_ids = set()
        for date_str, ids in data.get("by_date", {}).items():
            if date_str >= cutoff:
                all_ids.update(ids)
        return all_ids
    except Exception as e:
        print(f"  ⚠ {RECOMMENDED_HISTORY_PATH} 로드 실패: {e}")
        return set()


def _save_recommended_ids(papers: list):
    """오늘 추천한 paper id를 기록에 추가."""
    today = datetime.now().strftime("%Y-%m-%d")
    cutoff = (datetime.now() - timedelta(days=RECOMMENDED_HISTORY_DAYS)).strftime("%Y-%m-%d")

    try:
        if os.path.exists(RECOMMENDED_HISTORY_PATH):
            with open(RECOMMENDED_HISTORY_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {"by_date": {}}
    except Exception:
        data = {"by_date": {}}

    new_ids = list({p.get("id") for p in papers if p.get("id")})
    existing = set(data["by_date"].get(today, []))
    existing.update(new_ids)
    data["by_date"][today] = sorted(existing)

    # 오래된 기록 정리
    data["by_date"] = {k: v for k, v in data["by_date"].items() if k >= cutoff}

    with open(RECOMMENDED_HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _select_new_papers(papers: list, keywords: list, top_n: int = 10) -> list:
    """
    '오늘 새로 읽을 것' 선정.

    1차: 24시간 이내 새 논문 + 키워드 매칭
    1차 결과 < 3편이면 → 2차: 지난 14일 추천 기록 제외 + 키워드 매칭
    """
    # 1차: 24h 이내
    recent_papers = [p for p in papers if p.get("is_recent_24h", False)]
    print(f"🆕 오늘 새로 읽을 것 — 24시간 이내 {len(recent_papers)}편 검토")
    primary = filter_and_rank(recent_papers, keywords, top_n=top_n)

    if len(primary) >= 3:
        print(f"   → 1차 (24h 이내): {len(primary)}편 선정")
        return primary

    # 1차 빈약 → 2차: 추천 기록 제외
    print(f"   → 1차 결과 적음 ({len(primary)}편). 2차 fallback (지난 {RECOMMENDED_HISTORY_DAYS}일 추천 제외)")
    seen_ids = _load_recommended_ids()
    fresh_papers = [p for p in papers if p.get("id") not in seen_ids]
    print(f"      기록 제외 후 {len(fresh_papers)}편")
    secondary = filter_and_rank(fresh_papers, keywords, top_n=top_n)

    # 1차 + 2차 머지 (1차 우선, 중복 제거)
    primary_ids = {p.get("id") for p in primary}
    merged = primary + [p for p in secondary if p.get("id") not in primary_ids]
    print(f"   → 최종 {len(merged[:top_n])}편 (1차 {len(primary)} + 2차 {len(merged) - len(primary)})")
    return merged[:top_n]


def load_keywords_file(path: str = "keywords.json") -> list:
    """
    keywords.json 우선 로드. 없으면 None 반환 → config.yaml 사용.

    파일 구조:
    {
      "keywords": ["RAG", "data quality", ...],
      "updated_at": "2026-05-13"
    }
    """
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("keywords", [])
    except Exception as e:
        print(f"  ⚠ {path} 로드 실패: {e}")
        return None


def load_config(path: str = "config.yaml") -> dict:
    """config 로드. config.yaml 없으면 config.example.yaml 사용."""
    if not os.path.exists(path):
        fallback = "config.example.yaml"
        if os.path.exists(fallback):
            print(f"⚠ {path} 없음 — {fallback} 사용 (편집 후 config.yaml로 복사 권장)")
            path = fallback
        else:
            print(f"✗ {path} 없음. config.example.yaml 복사해서 만드세요.")
            sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    print("=" * 60)
    print("🚀 AI 트렌드 뉴스레터")
    print("=" * 60)

    config = load_config()

    # 연구 분야 프로필 적용 (다중 분야 지원)
    # 우선순위: profiles.json > config.yaml의 research_profile (단일/리스트 둘 다 지원)
    profile_ids = load_profiles_file()
    if profile_ids is None:
        config_profile = config.get("research_profile", "data-mining")
        if isinstance(config_profile, str):
            profile_ids = [config_profile]
        elif isinstance(config_profile, list):
            profile_ids = config_profile
        else:
            profile_ids = ["data-mining"]
        print(f"   (profiles.json 없음 — config.yaml에서 {profile_ids} 사용)")
    else:
        print(f"   (profiles.json에서 {len(profile_ids)}개 분야 로드: {profile_ids})")

    profile = get_combined_profile(profile_ids)
    print(f"🎓 연구 분야: {profile['label']}")

    user_keywords = load_keywords_file()
    if user_keywords is None:
        user_keywords = config.get("keywords", []) or []
        print(f"   (keywords.json 없음 — config.yaml의 keywords 사용)")
    else:
        print(f"   (keywords.json에서 {len(user_keywords)}개 로드)")

    # 카테고리: config의 arxiv_categories가 명시되어 있으면 우선, 아니면 profile에서
    categories = config.get("arxiv_categories") or profile["arxiv_categories"]
    print(f"   arXiv 카테고리: {categories}")
    max_papers = config.get("max_papers_per_day", 200)
    top_n = config.get("top_n_in_newsletter", 10)
    output_dir = config.get("output_dir", "dashboard")
    llm_config = config.get("llm", {})
    llm_provider = llm_config.get("provider", "google")
    llm_model = llm_config.get("model", "gemini-2.5-flash")

    today = datetime.now().strftime("%Y-%m-%d")
    print(f"📅 날짜: {today}")
    print(f"🔑 사용자 키워드: {user_keywords if user_keywords else '(없음 — 자동 추천 모드)'}")
    print()

    # 1) 논문 수집
    papers = fetch_all(categories, max_papers=max_papers)
    if not papers:
        print("✗ 수집된 논문이 없습니다.")
        return
    print()

    # 2) 키워드 추천 (cold start)
    suggested = []
    if not user_keywords:
        print("💡 키워드가 없어서 트렌딩 키워드 자동 추천 중...")
        suggested = suggest_keywords(papers, top_n=8)
        print(f"   → {suggested}")
        print()

    # 3) 필터링 + 정렬
    top_papers = filter_and_rank(papers, user_keywords, top_n=top_n)
    print()

    # 3-1) 오늘 새로 읽을 것 (탭 2)
    # 우선순위: 24시간 이내 새 논문 → 비어있으면 "지난 추천 제외" 방식
    new_papers = _select_new_papers(papers, user_keywords, top_n=top_n)
    print()

    # 3-2) 내 분야 소식 — seed 키워드 기반 별도 추천 (user_keywords와 별개)
    field_papers = []
    seed_keywords = profile.get("seed_keywords", [])
    if seed_keywords:
        print(f"🎓 내 분야 소식 — '{profile['label']}' seed 키워드로 별도 추천...")
        # 이미 top_papers/new_papers에 포함된 건 제외 (중복 방지)
        used_ids = {p.get("id") for p in top_papers} | {p.get("id") for p in new_papers}
        remaining = [p for p in papers if p.get("id") not in used_ids]
        field_papers = filter_and_rank(remaining, seed_keywords, top_n=10)
        print()

    # 4) 요약 생성
    if top_papers:
        print(f"📝 상위 {len(top_papers)}편 LLM 요약 생성 중... (provider: {llm_provider}, 모델: {llm_model})")
        top_papers = summarize_papers(top_papers, model=llm_model, provider=llm_provider)
        print()

    if new_papers:
        # new_papers 중 top_papers와 겹치는 건 캐시에서 요약 가져옴
        print(f"📝 오늘 새로 읽을 것 {len(new_papers)}편 요약 생성 중...")
        new_papers = summarize_papers(new_papers, model=llm_model, provider=llm_provider)
        print()

    if field_papers:
        print(f"📝 내 분야 소식 {len(field_papers)}편 요약 생성 중...")
        field_papers = summarize_papers(field_papers, model=llm_model, provider=llm_provider)
        print()

    # 추천 기록 저장 (어떤 id를 보여줬는지)
    _save_recommended_ids(top_papers + new_papers)

    # 5) HTML 저장 + 이메일 발송
    print("📤 출력 생성 중...")
    save_dashboard(top_papers, today, user_keywords, suggested, output_dir,
                   field_papers=field_papers, profile_label=profile["label"],
                   profile_ids=profile["ids"],
                   new_papers=new_papers)

    email_config = config.get("email", {})
    if email_config.get("enabled"):
        send_email(top_papers, today, user_keywords, suggested, email_config)

    # 6) 온라인 트렌딩 페이지 생성 (별도)
    print()
    print("🌐 온라인 트렌딩 키워드 수집 중...")
    try:
        from trending import load_previous_trending, compute_rank_changes, compute_aggregate_ranking
        from summarizer import translate_papers

        trending = collect_trending(categories)
        save_trending(trending, "trending.json", archive_dir="trending-archive")

        # 시계열 변화 계산
        previous = load_previous_trending(archive_dir="trending-archive", days_ago=1)
        rank_changes = compute_rank_changes(trending, previous) if previous else None
        if previous:
            print(f"  ✓ 어제 데이터와 비교해 순위 변화 계산")

        # 통합 ranking
        aggregate = compute_aggregate_ranking(trending, top_n=20)
        print(f"  ✓ 종합 ranking 생성 ({len(aggregate)}개 키워드)")

        # 트렌딩 펼침 논문 번역 (제목 + abstract)
        # 무료 한도 절약을 위해 각 키워드의 상위 5편만 번역 + 캐시 활용
        print(f"  📝 트렌딩 논문 번역 중... (각 키워드 상위 5편)")
        all_trending_papers = []
        seen_ids = set()
        for src in ("arxiv", "hf", "pwc"):
            for kw_data in trending.get(src, []):
                for p in kw_data.get("papers", [])[:5]:  # 키워드당 상위 5편만
                    pid = p.get("id") or p.get("arxiv_url", "")
                    if pid and pid not in seen_ids:
                        seen_ids.add(pid)
                        all_trending_papers.append(p)
        for kw_data in aggregate or []:
            for p in kw_data.get("papers", [])[:5]:
                pid = p.get("id") or p.get("arxiv_url", "")
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    all_trending_papers.append(p)
        print(f"     중복 제거 후 {len(all_trending_papers)}편 번역 대상")

        if all_trending_papers:
            translated = translate_papers(all_trending_papers, model=llm_model, provider=llm_provider)
            # 번역 결과를 원본 trending에 반영
            id_to_translation = {}
            for p in translated:
                pid = p.get("id") or p.get("arxiv_url", "")
                if pid:
                    id_to_translation[pid] = {
                        "title_ko": p.get("title_ko", ""),
                        "abstract_ko": p.get("abstract_ko", ""),
                    }
            for src in ("arxiv", "hf", "pwc"):
                for kw_data in trending.get(src, []):
                    for p in kw_data.get("papers", []):
                        pid = p.get("id") or p.get("arxiv_url", "")
                        if pid in id_to_translation:
                            p["title_ko"] = id_to_translation[pid]["title_ko"]
                            p["abstract_ko"] = id_to_translation[pid]["abstract_ko"]
            for kw_data in aggregate or []:
                for p in kw_data.get("papers", []):
                    pid = p.get("id") or p.get("arxiv_url", "")
                    if pid in id_to_translation:
                        p["title_ko"] = id_to_translation[pid]["title_ko"]
                        p["abstract_ko"] = id_to_translation[pid]["abstract_ko"]

        save_trending_page(trending, today, output_dir,
                           rank_changes=rank_changes,
                           aggregate=aggregate,
                           user_keywords=user_keywords)
    except Exception as e:
        import traceback
        print(f"  ⚠ 트렌딩 수집 실패: {e}")
        traceback.print_exc()

    print()
    print("=" * 60)
    print(f"✅ 완료! {len(top_papers)}편 추천")
    print(f"   대시보드: {output_dir}/index.html")
    print("=" * 60)


if __name__ == "__main__":
    main()