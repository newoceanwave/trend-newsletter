"""
온라인 트렌딩 키워드 수집.

3개 출처에서 신호를 모아 학계 트렌딩 키워드 ranking 생성:
1. arXiv 최근 7일 (cs.LG, cs.IR, cs.DB, cs.CL, cs.AI) - 연구 활동 그 자체
2. Hugging Face Daily Papers - 전문가 큐레이션 + likes
3. Papers with Code trending - 코드 공개된 (재현 가능) 논문

각 출처에서 키워드 빈도를 따로 계산해서 출처별로 표시.
이렇게 하면 사용자가 "어느 신호가 강한지" 판단 가능.
"""

import re
import json
import math
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple

import requests
import arxiv


# 도메인 키워드 사전 (filter.py의 KEYWORD_VOCAB과 같음 — 향후 외부 파일로 분리 가능)
KEYWORD_VOCAB = [
    "large language model", "llm", "diffusion", "transformer",
    "retrieval augmented generation", "rag", "agent", "multi-agent",
    "graph neural network", "gnn", "knowledge graph",
    "recommender system", "recommendation",
    "time series", "forecasting",
    "computer vision", "vision-language", "multimodal",
    "reinforcement learning", "rlhf", "dpo", "alignment",
    "fine-tuning", "instruction tuning", "lora", "peft",
    "in-context learning", "few-shot", "zero-shot",
    "data quality", "data augmentation", "data curation", "data selection",
    "federated learning", "privacy", "differential privacy",
    "interpretability", "explainability", "fairness",
    "speech", "audio", "video generation",
    "code generation", "code llm",
    "robotics", "embodied",
    "scaling law", "emergent",
    "hallucination", "factuality", "evaluation", "benchmark",
    "self-supervised", "contrastive",
    "neural architecture search", "nas",
    "anomaly detection", "outlier detection",
    "causal inference", "causal discovery",
    "world model", "planning", "reasoning",
    "watermark", "adversarial",
    "mixture of experts", "moe",
    "state space model", "mamba",
    "embedding", "representation learning",
    "active learning",
    "distillation", "quantization", "pruning",
    "self-improvement", "self-reflection",
    "synthetic data", "data generation",
    "long context", "long-context",
    "tool use", "function calling",
]


def _count_keywords(texts: List[str], weights: List[float] = None) -> Counter:
    """텍스트 리스트에서 KEYWORD_VOCAB의 키워드 빈도를 카운트. weight 옵션으로 가중."""
    if weights is None:
        weights = [1.0] * len(texts)

    counter = Counter()
    for text, w in zip(texts, weights):
        text_lower = text.lower()
        for kw in KEYWORD_VOCAB:
            pattern = r"\b" + re.escape(kw) + r"\b"
            if re.search(pattern, text_lower):
                counter[kw] += w
    return counter


def fetch_arxiv_trending(categories: List[str], days_back: int = 7, max_per_cat: int = 200) -> List[Dict]:
    """arXiv 최근 N일 논문에서 키워드 빈도 집계."""
    print(f"  📥 arXiv 최근 {days_back}일 ({categories})")
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

    all_papers = []
    client = arxiv.Client(page_size=100, delay_seconds=3, num_retries=3)

    for cat in categories:
        search = arxiv.Search(
            query=f"cat:{cat}",
            max_results=max_per_cat,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )
        try:
            for result in client.results(search):
                if result.published.replace(tzinfo=timezone.utc) < cutoff:
                    break
                all_papers.append({
                    "id": result.entry_id.split("/")[-1],
                    "title": result.title.replace("\n", " ").strip(),
                    "abstract": result.summary.replace("\n", " ").strip(),
                    "arxiv_url": result.entry_id,
                    "pdf_url": result.pdf_url,
                    "categories": result.categories,
                    "published": result.published.isoformat(),
                })
        except Exception as e:
            print(f"    ⚠ {cat} 실패: {e}")

    print(f"    → {len(all_papers)}편 수집")

    # 제목 가중치 ↑ (제목에 등장하면 더 핵심 토픽)
    titles = [p["title"] for p in all_papers]
    abstracts = [p["abstract"] for p in all_papers]
    title_counter = _count_keywords(titles, [3.0] * len(titles))
    abs_counter = _count_keywords(abstracts, [1.0] * len(abstracts))
    total = title_counter + abs_counter

    keywords = []
    for kw, count in total.most_common(30):
        # 이 키워드 포함하는 논문들
        related = [p for p in all_papers if re.search(r"\b" + re.escape(kw) + r"\b", (p["title"] + " " + p["abstract"]).lower())]
        related.sort(key=lambda p: p["published"], reverse=True)
        keywords.append({
            "keyword": kw,
            "score": round(count, 1),
            "paper_count": len(related),
            "papers": related[:10],
        })

    return keywords


def fetch_hf_trending(top_n: int = 30) -> List[Dict]:
    """Hugging Face Daily Papers — 큐레이션된 trending paper의 제목/abstract 키워드 빈도."""
    print(f"  📥 Hugging Face Daily Papers")
    url = "https://huggingface.co/api/daily_papers"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"    ⚠ 실패: {e}")
        return []

    papers = []
    for item in data:
        paper_info = item.get("paper", {})
        arxiv_id = paper_info.get("id", "")
        if not arxiv_id:
            continue
        papers.append({
            "id": arxiv_id,
            "title": paper_info.get("title", "").replace("\n", " ").strip(),
            "abstract": paper_info.get("summary", "").replace("\n", " ").strip(),
            "likes": paper_info.get("upvotes", 0),
            "arxiv_url": f"https://arxiv.org/abs/{arxiv_id}",
            "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
            "hf_url": f"https://huggingface.co/papers/{arxiv_id}",
            "published": paper_info.get("publishedAt", ""),
        })
    print(f"    → {len(papers)}편 수집")

    # likes 기반 가중치 (log scale)
    titles = [p["title"] for p in papers]
    weights = [3.0 * (1 + math.log10(max(p["likes"], 1))) for p in papers]
    title_counter = _count_keywords(titles, weights)

    abstracts = [p["abstract"] for p in papers]
    weights_abs = [1.0 * (1 + math.log10(max(p["likes"], 1))) for p in papers]
    abs_counter = _count_keywords(abstracts, weights_abs)

    total = title_counter + abs_counter

    keywords = []
    for kw, count in total.most_common(top_n):
        related = [p for p in papers if re.search(r"\b" + re.escape(kw) + r"\b", (p["title"] + " " + p["abstract"]).lower())]
        related.sort(key=lambda p: p["likes"], reverse=True)
        keywords.append({
            "keyword": kw,
            "score": round(count, 1),
            "paper_count": len(related),
            "papers": related[:10],
        })

    return keywords


def fetch_pwc_trending(top_n: int = 30) -> List[Dict]:
    """
    Papers with Code trending — 코드 공개된 최근 인기 논문.
    공식 API: https://paperswithcode.com/api/v1/papers/?ordering=-trending
    실패하면 alphaxiv API로 fallback.
    """
    print(f"  📥 Papers with Code trending")
    url = "https://paperswithcode.com/api/v1/papers/"
    params = {"ordering": "-trending"}
    headers = {"Accept": "application/json", "User-Agent": "Mozilla/5.0 (trend-newsletter)"}

    # 재시도 로직
    data = None
    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            break
        except Exception as e:
            print(f"    ⚠ 시도 {attempt + 1}/3 실패: {e}")
            if attempt < 2:
                import time
                time.sleep(2)

    # Papers with Code 실패 시 alphaxiv fallback
    if data is None:
        print(f"    → Papers with Code 모두 실패, alphaxiv로 fallback")
        return _fetch_alphaxiv_trending(top_n)

    results = data.get("results", [])
    papers = []
    for item in results[:100]:
        arxiv_id = (item.get("arxiv_id") or "").strip()
        papers.append({
            "id": arxiv_id or item.get("id", ""),
            "title": (item.get("title") or "").replace("\n", " ").strip(),
            "abstract": (item.get("abstract") or "").replace("\n", " ").strip(),
            "arxiv_url": f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else item.get("url_abs", ""),
            "pdf_url": item.get("url_pdf") or (f"https://arxiv.org/pdf/{arxiv_id}" if arxiv_id else ""),
            "pwc_url": item.get("url_abs", ""),
            "published": item.get("published", ""),
        })
    print(f"    → {len(papers)}편 수집")

    titles = [p["title"] for p in papers]
    title_counter = _count_keywords(titles, [3.0] * len(titles))
    abstracts = [p["abstract"] for p in papers]
    abs_counter = _count_keywords(abstracts, [1.0] * len(abstracts))
    total = title_counter + abs_counter

    keywords = []
    for kw, count in total.most_common(top_n):
        related = [p for p in papers if re.search(r"\b" + re.escape(kw) + r"\b", (p["title"] + " " + p["abstract"]).lower())]
        keywords.append({
            "keyword": kw,
            "score": round(count, 1),
            "paper_count": len(related),
            "papers": related[:10],
        })

    return keywords


def _fetch_alphaxiv_trending(top_n: int = 30) -> List[Dict]:
    """alphaxiv: arXiv 위에 ML 커뮤니티 큐레이션. Papers with Code fallback."""
    url = "https://api.alphaxiv.org/v2/papers/list/popular"
    params = {"limit": 100}

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"    ⚠ alphaxiv도 실패: {e}")
        return []

    items = data.get("papers", []) if isinstance(data, dict) else data
    papers = []
    for item in items[:100]:
        arxiv_id = (item.get("paper_id") or item.get("arxiv_id") or "").strip()
        if not arxiv_id:
            continue
        papers.append({
            "id": arxiv_id,
            "title": (item.get("title") or "").replace("\n", " ").strip(),
            "abstract": (item.get("abstract") or "").replace("\n", " ").strip(),
            "arxiv_url": f"https://arxiv.org/abs/{arxiv_id}",
            "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
            "published": item.get("publishedAt", ""),
        })

    if not papers:
        return []
    print(f"    → alphaxiv {len(papers)}편 수집")

    titles = [p["title"] for p in papers]
    title_counter = _count_keywords(titles, [3.0] * len(titles))
    abstracts = [p["abstract"] for p in papers]
    abs_counter = _count_keywords(abstracts, [1.0] * len(abstracts))
    total = title_counter + abs_counter

    keywords = []
    for kw, count in total.most_common(top_n):
        related = [p for p in papers if re.search(r"\b" + re.escape(kw) + r"\b", (p["title"] + " " + p["abstract"]).lower())]
        keywords.append({
            "keyword": kw,
            "score": round(count, 1),
            "paper_count": len(related),
            "papers": related[:10],
        })

    return keywords


def collect_trending(categories: List[str] = None) -> Dict:
    """3개 출처에서 trending keyword 집계해서 dict로 반환."""
    if categories is None:
        categories = ["cs.LG", "cs.IR", "cs.DB", "cs.CL", "cs.AI"]

    print("🌐 트렌딩 키워드 수집")

    arxiv_kw = fetch_arxiv_trending(categories, days_back=7)
    hf_kw = fetch_hf_trending()
    pwc_kw = fetch_pwc_trending()

    return {
        "arxiv": arxiv_kw[:20],  # top 20 표시
        "hf": hf_kw[:20],
        "pwc": pwc_kw[:20],
        "collected_at": datetime.now().isoformat(),
    }


def save_trending(trending: Dict, path: str = "trending.json", archive_dir: str = "trending-archive"):
    """수집 결과를 JSON으로 저장. 추가로 archive 폴더에 일자별 사본 저장 (시계열 비교용)."""
    import os
    with open(path, "w", encoding="utf-8") as f:
        json.dump(trending, f, ensure_ascii=False, indent=2)
    print(f"  ✓ {path}")

    # archive (날짜별)
    os.makedirs(archive_dir, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    archive_path = os.path.join(archive_dir, f"{today}.json")
    with open(archive_path, "w", encoding="utf-8") as f:
        json.dump(trending, f, ensure_ascii=False, indent=2)
    print(f"  ✓ {archive_path}")


def load_previous_trending(archive_dir: str = "trending-archive", days_ago: int = 1) -> Dict:
    """N일 전 trending 데이터 로드. 없으면 빈 dict."""
    import os
    target_date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
    path = os.path.join(archive_dir, f"{target_date}.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def compute_rank_changes(current: Dict, previous: Dict) -> Dict:
    """
    현재 vs 이전 trending에서 각 키워드의 순위 변화를 계산.

    Returns: {source: {keyword: change_int}} 형태
    - change > 0: 순위 상승 (예: 5위 → 2위면 +3)
    - change < 0: 순위 하락
    - change == 0: 동일
    - change == "new": 새로 진입
    """
    changes = {"arxiv": {}, "hf": {}, "pwc": {}}

    for src in ("arxiv", "hf", "pwc"):
        cur_list = current.get(src, [])
        prev_list = previous.get(src, [])

        prev_rank = {k["keyword"]: i for i, k in enumerate(prev_list)}

        for i, k in enumerate(cur_list):
            kw = k["keyword"]
            if kw in prev_rank:
                changes[src][kw] = prev_rank[kw] - i  # 이전 순위 - 현재 순위
            else:
                changes[src][kw] = "new"

    return changes


def compute_aggregate_ranking(trending: Dict, top_n: int = 20) -> List[Dict]:
    """
    3개 출처 점수를 normalize해서 통합 ranking 생성.
    각 출처에서 max score = 100으로 스케일링 후 평균.
    """
    score_map = {}  # keyword -> {arxiv: x, hf: y, pwc: z}

    for src in ("arxiv", "hf", "pwc"):
        items = trending.get(src, [])
        if not items:
            continue
        max_score = max((k["score"] for k in items), default=1.0)
        for k in items:
            kw = k["keyword"]
            normalized = (k["score"] / max_score) * 100
            if kw not in score_map:
                score_map[kw] = {"arxiv": 0, "hf": 0, "pwc": 0, "papers": []}
            score_map[kw][src] = round(normalized, 1)
            # 관련 논문 합치기 (중복 제거)
            for p in k.get("papers", []):
                if p not in score_map[kw]["papers"]:
                    score_map[kw]["papers"].append(p)

    # 평균 점수 계산
    results = []
    for kw, scores in score_map.items():
        avg = (scores["arxiv"] + scores["hf"] + scores["pwc"]) / 3
        sources_present = sum(1 for s in ("arxiv", "hf", "pwc") if scores[s] > 0)
        results.append({
            "keyword": kw,
            "aggregate_score": round(avg, 1),
            "sources_present": sources_present,  # 3개 출처 중 몇 개에서 등장
            "scores": {"arxiv": scores["arxiv"], "hf": scores["hf"], "pwc": scores["pwc"]},
            "papers": scores["papers"][:10],
        })

    # 점수 + 출처 다양성 둘 다 고려 (3개 출처 모두 등장하면 가중 +)
    results.sort(key=lambda r: (r["aggregate_score"] * (1 + 0.2 * (r["sources_present"] - 1))), reverse=True)
    return results[:top_n]


if __name__ == "__main__":
    result = collect_trending()
    save_trending(result)
    for source, label in [("arxiv", "arXiv 7일"), ("hf", "HF Daily"), ("pwc", "Papers with Code")]:
        print(f"\n=== {label} top 10 ===")
        for kw in result[source][:10]:
            print(f"  {kw['keyword']:35s} score={kw['score']:5.1f} papers={kw['paper_count']}")