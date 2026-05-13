"""
LLM으로 논문 한 줄 요약 + 제목/abstract 번역.
Gemini와 Anthropic Claude 둘 다 지원. config.yaml의 llm.provider로 선택.
캐시: 한 번 번역된 논문은 translations.json에 저장해서 재번역 안 함.
"""

import os
import json
from typing import List, Dict


CACHE_PATH = "translations.json"


def _load_cache() -> Dict:
    """이전에 번역한 논문 캐시 로드."""
    if not os.path.exists(CACHE_PATH):
        return {}
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(cache: Dict) -> None:
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def _get_client(provider: str):
    """provider에 맞는 LLM 클라이언트 반환. 키 없으면 None."""
    if provider == "google":
        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return None
        try:
            from google import genai
            return ("google", genai.Client(api_key=api_key))
        except ImportError:
            return None
    elif provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return None
        try:
            from anthropic import Anthropic
            return ("anthropic", Anthropic(api_key=api_key))
        except ImportError:
            return None
    return None


def _call_llm(client_tuple, prompt: str, model: str, max_tokens: int = 300) -> str:
    """provider 무관하게 텍스트 응답 받기."""
    provider, client = client_tuple
    if provider == "google":
        response = client.models.generate_content(model=model, contents=prompt)
        return response.text.strip()
    elif provider == "anthropic":
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    raise ValueError(f"Unknown provider: {provider}")


def summarize_papers(papers: List[Dict], model: str = "gemini-2.5-flash", provider: str = "google") -> List[Dict]:
    """각 논문에 'summary_ko' 필드(한국어 1-2문장)를 추가. 캐시 활용."""
    client_tuple = _get_client(provider)
    cache = _load_cache()

    if client_tuple is None:
        print(f"  ⚠ {provider.upper()}_API_KEY 환경변수 없음 — 요약 건너뜀")
        for p in papers:
            p["summary_ko"] = p.get("abstract", "")[:200] + "..."
        return papers

    new_count = 0
    for i, paper in enumerate(papers, 1):
        title = paper.get("title", "")
        abstract = paper.get("abstract", "")[:1500]
        paper_id = paper.get("id") or title  # 캐시 키

        cached = cache.get(paper_id, {})
        if "summary_ko" in cached:
            paper["summary_ko"] = cached["summary_ko"]
            continue

        prompt = f"""다음 ML/AI 논문을 한국어로 1-2문장으로 요약해주세요. 핵심 contribution 위주로, 전문 용어는 그대로 두세요.

제목: {title}

Abstract: {abstract}

요약 (한국어, 1-2문장):"""

        try:
            summary = _call_llm(client_tuple, prompt, model, max_tokens=200)
            paper["summary_ko"] = summary
            cache.setdefault(paper_id, {})["summary_ko"] = summary
            new_count += 1
            print(f"  [{i}/{len(papers)}] ✓ {title[:60]}...")
        except Exception as e:
            print(f"  [{i}/{len(papers)}] ✗ 요약 실패: {e}")
            paper["summary_ko"] = abstract[:200] + "..."

    if new_count > 0:
        _save_cache(cache)
        print(f"  → 새로 번역 {new_count}편, 캐시 {len(papers) - new_count}편")
    return papers


def translate_papers(papers: List[Dict], model: str = "gemini-2.5-flash", provider: str = "google",
                     translate_abstract: bool = True) -> List[Dict]:
    """
    각 논문에 'title_ko' (제목 번역) + 'abstract_ko' (abstract 번역) 추가.
    트렌딩 페이지의 펼침 논문에 사용. 캐시 활용.
    """
    client_tuple = _get_client(provider)
    cache = _load_cache()

    if client_tuple is None:
        for p in papers:
            p["title_ko"] = ""
            p["abstract_ko"] = ""
        return papers

    new_count = 0
    cached_count = 0
    failed_count = 0

    for i, paper in enumerate(papers, 1):
        title = paper.get("title", "")
        abstract = paper.get("abstract", "")[:1200]
        paper_id = paper.get("id") or paper.get("arxiv_url", "") or title

        cached = cache.get(paper_id, {})
        needs_title = "title_ko" not in cached
        needs_abstract = translate_abstract and "abstract_ko" not in cached

        if not needs_title and not needs_abstract:
            paper["title_ko"] = cached.get("title_ko", "")
            paper["abstract_ko"] = cached.get("abstract_ko", "")
            cached_count += 1
            continue

        # 둘 다 한 번에 번역 (token 절약)
        prompt = f"""다음 AI/ML 논문의 제목과 abstract를 한국어로 번역해주세요.
- 전문 용어는 그대로 두기 (예: transformer, embedding, fine-tuning)
- 정확하고 간결하게
- JSON 형식으로만 응답: {{"title": "...", "abstract": "..."}}

영어 제목: {title}

영어 abstract: {abstract}

한국어 번역 JSON:"""

        try:
            response = _call_llm(client_tuple, prompt, model, max_tokens=600)
            # JSON 파싱 (```json...``` 마크다운 제거)
            response_clean = response.replace("```json", "").replace("```", "").strip()
            data = json.loads(response_clean)

            title_ko = data.get("title", "").strip()
            abstract_ko = data.get("abstract", "").strip()

            paper["title_ko"] = title_ko
            paper["abstract_ko"] = abstract_ko

            cache.setdefault(paper_id, {})["title_ko"] = title_ko
            cache[paper_id]["abstract_ko"] = abstract_ko
            new_count += 1
            if i % 20 == 0:
                print(f"  [{i}/{len(papers)}] 번역 중...")
                _save_cache(cache)  # 중간 저장 (긴 작업 안전)
        except Exception as e:
            failed_count += 1
            paper["title_ko"] = ""
            paper["abstract_ko"] = ""
            if failed_count <= 3:  # 처음 3번만 로그
                print(f"  [{i}/{len(papers)}] ✗ 번역 실패: {str(e)[:60]}")

    if new_count > 0:
        _save_cache(cache)
    print(f"  → 번역: 새로 {new_count}편, 캐시 {cached_count}편, 실패 {failed_count}편")
    return papers


if __name__ == "__main__":
    test = [{
        "id": "test-1",
        "title": "Retrieval-Augmented Generation with Self-Reflective Critique",
        "abstract": "We propose a novel framework for retrieval-augmented generation that combines self-reflection mechanisms with critique-based learning.",
    }]
    result = translate_papers(test, model="gemini-2.5-flash", provider="google")
    print("title_ko:", result[0].get("title_ko"))
    print("abstract_ko:", result[0].get("abstract_ko"))