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
    카테고리가 많으면 OR로 묶어 요청 수를 줄인다 (rate limit 회피).

    Args:
        categories: ["cs.LG", "cs.IR", ...]
        max_results: 그룹별 최대 결과 수
        days_back: 며칠 전까지 (기본 1 = 어제만)
    """
    import time

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days_back)
    cutoff_24h = now - timedelta(hours=24)
    papers = []
    seen_ids = set()

    client = arxiv.Client(page_size=100, delay_seconds=5, num_retries=5)

    # 카테고리를 5개씩 묶어 OR 쿼리로 — 20개 → 4번 요청
    GROUP_SIZE = 5
    groups = [categories[i:i + GROUP_SIZE] for i in range(0, len(categories), GROUP_SIZE)]

    for gi, group in enumerate(groups):
        query = " OR ".join(f"cat:{c}" for c in group)
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )

        # 429/503 대응: 최대 4회 재시도, 점점 더 오래 대기
        success = False
        for attempt in range(4):
            try:
                for result in client.results(search):
                    if result.published.replace(tzinfo=timezone.utc) < cutoff:
                        break

                    arxiv_id = result.entry_id.split("/")[-1]
                    if arxiv_id in seen_ids:
                        continue
                    seen_ids.add(arxiv_id)

                    published_utc = result.published.replace(tzinfo=timezone.utc)
                    papers.append({
                        "id": arxiv_id,
                        "title": result.title.replace("\n", " ").strip(),
                        "abstract": result.summary.replace("\n", " ").strip(),
                        "authors": [a.name for a in result.authors],
                        "categories": result.categories,
                        "published": published_utc.isoformat(),
                        "pdf_url": result.pdf_url,
                        "arxiv_url": result.entry_id,
                        "hf_likes": 0,
                        "source": "arxiv",
                        "is_recent_24h": published_utc >= cutoff_24h,
                    })
                success = True
                break
            except Exception as e:
                wait = 15 * (attempt + 1)  # 15s, 30s, 45s, 60s
                msg = str(e)
                if "429" in msg or "503" in msg:
                    print(f"  ⚠ arXiv 그룹 {gi+1} rate limit (시도 {attempt+1}/4) — {wait}초 대기")
                    time.sleep(wait)
                else:
                    print(f"  ⚠ arXiv 그룹 {gi+1} 실패: {e}")
                    break
        if not success:
            print(f"  ⚠ arXiv 그룹 {gi+1} 최종 실패 (카테고리: {group})")

        # 그룹 사이 간격 (마지막 그룹 제외)
        if gi < len(groups) - 1:
            time.sleep(5)

    print(f"   → arXiv {len(papers)}편 수집")
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
            "abstract": paper.get("summary", "").replace("\n", " ").strip(),
            "authors": [a.get("name", "") for a in paper.get("authors", [])][:5],
            "categories": [],
            "published": paper.get("publishedAt", ""),
            "arxiv_url": f"https://arxiv.org/abs/{arxiv_id}",
            "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
            "hf_likes": paper.get("upvotes", 0),
            "hf_url": f"https://huggingface.co/papers/{arxiv_id}",
            "is_recent_24h": False,
            "source": "hf",
        })

    return papers


def merge_arxiv_and_hf(arxiv_papers: List[Dict], hf_papers: List[Dict]) -> List[Dict]:
    """
    arXiv 결과에 HF Daily Papers의 likes 정보 머지.
    HF에만 있는 논문(arXiv 카테고리 밖)도 결과에 추가한다.
    """
    arxiv_by_id = {p["id"]: p for p in arxiv_papers}
    arxiv_ids_normalized = {p["id"].split("v")[0]: p for p in arxiv_papers}  # v1, v2 등 버전 제거

    merged = list(arxiv_papers)  # arXiv 논문 먼저
    seen_bases = set(arxiv_ids_normalized.keys())

    for hf in hf_papers:
        hf_id_base = hf["id"].split("v")[0]
        if hf_id_base in arxiv_ids_normalized:
            # arXiv에 이미 있는 논문 → likes 정보만 붙임
            arxiv_ids_normalized[hf_id_base]["hf_likes"] = hf["hf_likes"]
            arxiv_ids_normalized[hf_id_base]["hf_url"] = hf.get("hf_url", "")
        elif hf_id_base not in seen_bases:
            # HF에만 있는 논문 → 결과에 추가
            seen_bases.add(hf_id_base)
            merged.append(hf)

    return merged


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