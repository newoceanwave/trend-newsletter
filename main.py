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
from datetime import datetime

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

    # 3-2) 내 분야 소식 — seed 키워드 기반 별도 추천 (user_keywords와 별개)
    field_papers = []
    seed_keywords = profile.get("seed_keywords", [])
    if seed_keywords:
        print(f"🎓 내 분야 소식 — '{profile['label']}' seed 키워드로 별도 추천...")
        # 이미 top_papers에 포함된 건 제외 (중복 방지)
        top_ids = {p.get("id") for p in top_papers}
        remaining = [p for p in papers if p.get("id") not in top_ids]
        field_papers = filter_and_rank(remaining, seed_keywords, top_n=10)
        print()

    # 4) 요약 생성
    if top_papers:
        print(f"📝 상위 {len(top_papers)}편 LLM 요약 생성 중... (provider: {llm_provider}, 모델: {llm_model})")
        top_papers = summarize_papers(top_papers, model=llm_model, provider=llm_provider)
        print()

    if field_papers:
        print(f"📝 내 분야 소식 {len(field_papers)}편 요약 생성 중...")
        field_papers = summarize_papers(field_papers, model=llm_model, provider=llm_provider)
        print()

    # 5) HTML 저장 + 이메일 발송
    print("📤 출력 생성 중...")
    save_dashboard(top_papers, today, user_keywords, suggested, output_dir,
                   field_papers=field_papers, profile_label=profile["label"],
                   profile_ids=profile["ids"])

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