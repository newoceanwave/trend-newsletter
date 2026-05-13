"""
논문 수집기.
- arXiv: 어제 submit된 논문 (카테고리별)
- Hugging Face Daily Papers: 큐레이션된 trending paper (인기 신호로 활용)
"""

import arxiv
import requests
from datetime import datetime, timedelta, timezone
from typing import List, Dict


def fetch_arxiv_papers(categories: List[str], max_results: int = 200, days_back: int = 1) -> List[Dict]:
    """
    arXiv에서 지정한 카테고리의 최근 논문을 가져온다.

    Args:
        categories: ["cs.LG", "cs.IR", ...]
        max_results: 카테고리별 최대 결과 수
        days_back: 며칠 전까지 (기본 1 = 어제만)

    Returns:
        논문 dict 리스트. 각 dict는 다음 키를 가짐:
        - id, title, abstract, authors, categories, published, pdf_url, arxiv_url
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    papers = []
    seen_ids = set()

    client = arxiv.Client(page_size=100, delay_seconds=3, num_retries=3)

    for cat in categories:
        query = f"cat:{cat}"
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )

        try:
            for result in client.results(search):
                # 어제 이전 논문이면 중단 (최신순 정렬이므로)
                if result.published.replace(tzinfo=timezone.utc) < cutoff:
                    break

                arxiv_id = result.entry_id.split("/")[-1]
                if arxiv_id in seen_ids:
                    continue
                seen_ids.add(arxiv_id)

                papers.append({
                    "id": arxiv_id,
                    "title": result.title.replace("\n", " ").strip(),
                    "abstract": result.summary.replace("\n", " ").strip(),
                    "authors": [a.name for a in result.authors],
                    "categories": result.categories,
                    "published": result.published.isoformat(),
                    "pdf_url": result.pdf_url,
                    "arxiv_url": result.entry_id,
                    "hf_likes": 0,  # 나중에 HF에서 채움
                    "source": "arxiv",
                })
        except Exception as e:
            print(f"  ⚠ arXiv {cat} fetch 실패: {e}")
            continue

    return papers


def fetch_hf_daily_papers() -> List[Dict]:
    """
    Hugging Face Daily Papers — 큐레이션된 trending 논문 목록.
    https://huggingface.co/papers — JSON API로 접근.

    arXiv 논문과 매칭해서 "HF에서 큐레이션된 / 좋아요 받은 것" 신호로 사용.
    """
    url = "https://huggingface.co/api/daily_papers"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  ⚠ HF Daily Papers fetch 실패: {e}")
        return []

    papers = []
    for item in data:
        paper = item.get("paper", {})
        arxiv_id = paper.get("id", "")
        if not arxiv_id:
            continue

        papers.append({
            "id": arxiv_id,
            "title": paper.get("title", "").replace("\n", " ").strip(),
            "hf_likes": paper.get("upvotes", 0),
            "hf_url": f"https://huggingface.co/papers/{arxiv_id}",
        })

    return papers


def merge_arxiv_and_hf(arxiv_papers: List[Dict], hf_papers: List[Dict]) -> List[Dict]:
    """
    arXiv 결과에 HF Daily Papers의 likes 정보 머지.
    HF에만 있는 논문은 별도로 추가.
    """
    arxiv_by_id = {p["id"]: p for p in arxiv_papers}
    arxiv_ids_normalized = {p["id"].split("v")[0]: p for p in arxiv_papers}  # v1, v2 등 버전 제거

    for hf in hf_papers:
        hf_id_base = hf["id"].split("v")[0]
        if hf_id_base in arxiv_ids_normalized:
            arxiv_ids_normalized[hf_id_base]["hf_likes"] = hf["hf_likes"]
            arxiv_ids_normalized[hf_id_base]["hf_url"] = hf.get("hf_url", "")

    return list(arxiv_by_id.values())


def fetch_all(categories: List[str], max_papers: int = 200) -> List[Dict]:
    """전체 fetch 파이프라인."""
    print(f"📥 arXiv에서 논문 가져오는 중... (카테고리: {categories})")
    arxiv_papers = fetch_arxiv_papers(categories, max_results=max_papers)
    print(f"   → {len(arxiv_papers)}편 수집")

    print(f"📥 Hugging Face Daily Papers 가져오는 중...")
    hf_papers = fetch_hf_daily_papers()
    print(f"   → {len(hf_papers)}편 (큐레이션 신호)")

    merged = merge_arxiv_and_hf(arxiv_papers, hf_papers)
    hf_matched = sum(1 for p in merged if p.get("hf_likes", 0) > 0)
    print(f"   → 머지 완료. HF에서도 픽한 논문: {hf_matched}편")

    return merged


if __name__ == "__main__":
    # 테스트
    papers = fetch_all(["cs.LG", "cs.IR"], max_papers=20)
    print(f"\n총 {len(papers)}편")
    for p in papers[:3]:
        print(f"- {p['title'][:80]}... [HF likes: {p['hf_likes']}]")
