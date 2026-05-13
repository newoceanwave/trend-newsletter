"""
LLM으로 논문 한 줄 요약 생성.
"""

import os
from typing import List, Dict


def summarize_papers(papers: List[Dict], model: str = "claude-haiku-4-5-20251001") -> List[Dict]:
    """
    각 논문에 'summary_ko' 필드(한국어 1-2문장)를 추가.
    실패해도 처음의 abstract 일부로 fallback.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("  ⚠ ANTHROPIC_API_KEY 환경변수 없음 — 요약 건너뜀")
        for p in papers:
            p["summary_ko"] = p.get("abstract", "")[:200] + "..."
        return papers

    try:
        from anthropic import Anthropic
    except ImportError:
        print("  ⚠ anthropic 패키지 없음 — pip install anthropic")
        for p in papers:
            p["summary_ko"] = p.get("abstract", "")[:200] + "..."
        return papers

    client = Anthropic(api_key=api_key)

    for i, paper in enumerate(papers, 1):
        title = paper.get("title", "")
        abstract = paper.get("abstract", "")[:1500]  # 너무 길면 자름

        prompt = f"""다음 ML/AI 논문을 한국어로 1-2문장으로 요약해주세요. 핵심 contribution 위주로, 전문 용어는 그대로 두세요.

제목: {title}

Abstract: {abstract}

요약 (한국어, 1-2문장):"""

        try:
            response = client.messages.create(
                model=model,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            summary = response.content[0].text.strip()
            paper["summary_ko"] = summary
            print(f"  [{i}/{len(papers)}] ✓ {title[:60]}...")
        except Exception as e:
            print(f"  [{i}/{len(papers)}] ✗ 요약 실패: {e}")
            paper["summary_ko"] = abstract[:200] + "..."

    return papers


if __name__ == "__main__":
    test = [{
        "title": "Test paper on LLMs",
        "abstract": "We propose a new method for fine-tuning large language models efficiently.",
    }]
    result = summarize_papers(test)
    print(result[0].get("summary_ko"))
