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


def _call_llm(client_tuple, prompt: str, model: str, max_tokens: int = 300, max_retries: int = 3) -> str:
    """provider 무관하게 텍스트 응답 받기. Rate limit (429) 자동 재시도."""
    import time
    provider, client = client_tuple
    last_error = None

    for attempt in range(max_retries):
        try:
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
        except Exception as e:
            err_str = str(e)
            last_error = e
            # Rate limit (429) — 대기 후 재시도
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "rate" in err_str.lower():
                wait_time = 13  # Gemini free tier: per-minute quota는 약 12초마다 reset
                if attempt < max_retries - 1:
                    time.sleep(wait_time)
                    continue
            raise

    if last_error:
        raise last_error
    raise ValueError(f"Unknown provider: {provider}")


def summarize_papers(papers: List[Dict], model: str = "gemini-2.5-flash-lite", provider: str = "google") -> List[Dict]:
    """각 논문에 'summary_ko' 필드(한국어 1-2문장)를 추가. 캐시 + throttle."""
    import time
    client_tuple = _get_client(provider)
    cache = _load_cache()

    if client_tuple is None:
        print(f"  ⚠ {provider.upper()}_API_KEY 환경변수 없음 — 요약 건너뜀")
        for p in papers:
            p["summary_ko"] = p.get("abstract", "")[:200] + "..."
        return papers

    throttle_delay = 5.0 if "lite" in model.lower() else 13.0
    if provider != "google":
        throttle_delay = 0.5

    new_count = 0
    for i, paper in enumerate(papers, 1):
        title = paper.get("title", "")
        abstract = paper.get("abstract", "")[:1500]
        paper_id = paper.get("id") or title

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
            time.sleep(throttle_delay)
        except Exception as e:
            print(f"  [{i}/{len(papers)}] ✗ 요약 실패: {str(e)[:80]}")
            paper["summary_ko"] = abstract[:200] + "..."

    if new_count > 0:
        _save_cache(cache)
        print(f"  → 새로 번역 {new_count}편, 캐시 {len(papers) - new_count}편")
    return papers


def translate_papers(papers: List[Dict], model: str = "gemini-2.5-flash-lite", provider: str = "google",
                     translate_abstract: bool = True) -> List[Dict]:
    """
    각 논문에 'title_ko' (제목 번역) + 'abstract_ko' (abstract 번역) 추가.
    트렌딩 페이지의 펼침 논문에 사용. 캐시 활용. Rate limit 자동 throttle.
    """
    import time
    client_tuple = _get_client(provider)
    cache = _load_cache()

    if client_tuple is None:
        for p in papers:
            p["title_ko"] = ""
            p["abstract_ko"] = ""
        return papers

    # Gemini free tier 안전 throttle:
    # - gemini-2.5-flash-lite: 분당 15회 → 4.5초 간격
    # - gemini-2.5-flash: 분당 5회 → 12.5초 간격
    # 안전 마진 둠
    throttle_delay = 5.0 if "lite" in model.lower() else 13.0
    if provider != "google":
        throttle_delay = 0.5  # Anthropic은 훨씬 여유로움

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

        prompt = f"""다음 AI/ML 논문의 제목과 abstract를 한국어로 번역해주세요.
- 전문 용어는 그대로 두기 (예: transformer, embedding, fine-tuning)
- 정확하고 간결하게 (abstract는 3-4문장 이내로 짧게)
- 반드시 JSON 형식으로만 응답, 다른 설명 없이
- JSON: {{"title": "한글 제목", "abstract": "한글 요약 abstract"}}

영어 제목: {title}

영어 abstract: {abstract}

JSON:"""

        try:
            response = _call_llm(client_tuple, prompt, model, max_tokens=1200)
            response_clean = response.replace("```json", "").replace("```", "").strip()

            # JSON 파싱 — 실패 시 부분 추출 시도
            try:
                data = json.loads(response_clean)
            except json.JSONDecodeError:
                # 응답이 잘렸을 가능성. title이라도 추출 시도
                import re as _re
                title_match = _re.search(r'"title"\s*:\s*"([^"]+)"', response_clean)
                abs_match = _re.search(r'"abstract"\s*:\s*"([^"]*)', response_clean)
                if title_match:
                    data = {
                        "title": title_match.group(1),
                        "abstract": abs_match.group(1) if abs_match else "",
                    }
                else:
                    raise

            title_ko = data.get("title", "").strip()
            abstract_ko = data.get("abstract", "").strip()

            paper["title_ko"] = title_ko
            paper["abstract_ko"] = abstract_ko

            cache.setdefault(paper_id, {})["title_ko"] = title_ko
            cache[paper_id]["abstract_ko"] = abstract_ko
            new_count += 1

            if new_count % 10 == 0:
                print(f"  [{i}/{len(papers)}] 번역 중... (new={new_count})")
                _save_cache(cache)  # 중간 저장

            # Rate limit 회피용 throttle
            time.sleep(throttle_delay)
        except Exception as e:
            failed_count += 1
            paper["title_ko"] = ""
            paper["abstract_ko"] = ""
            if failed_count <= 3:
                print(f"  [{i}/{len(papers)}] ✗ 번역 실패: {str(e)[:80]}")

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