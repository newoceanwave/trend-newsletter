"""
논문 필터링 + 트렌딩 스코어 계산.

전략:
1. 키워드 매칭 (제목/abstract에 키워드 등장 → 강한 시그널)
2. HF Daily Papers likes (커뮤니티 신호)
3. arXiv 메인 카테고리 (cs.LG 등 가중치)

키워드가 비어있으면 (cold start) → HF likes 기준으로 trending paper만 보여줌.
"""

import re
from typing import List, Dict


def keyword_match_score(paper: Dict, keywords: List[str]) -> float:
    """
    키워드 매칭 점수.
    - 제목에 등장: +3
    - abstract에 등장: +1
    - 여러 키워드 매칭 시 합산
    """
    if not keywords:
        return 0.0

    title = paper.get("title", "").lower()
    abstract = paper.get("abstract", "").lower()
    score = 0.0
    matched_keywords = []

    for kw in keywords:
        kw_lower = kw.lower().strip()
        if not kw_lower:
            continue

        # word boundary 사용해서 부분일치 방지 ("ML"이 "MLM"에 매칭되지 않게)
        pattern = r"\b" + re.escape(kw_lower) + r"\b"

        if re.search(pattern, title):
            score += 3.0
            matched_keywords.append(kw)
        elif re.search(pattern, abstract):
            score += 1.0
            matched_keywords.append(kw)

    paper["matched_keywords"] = list(set(matched_keywords))
    return score


def trending_score(paper: Dict) -> float:
    """
    HF Daily Papers likes 기반 trending 점수.
    log scale: 10 likes = 1점, 100 likes = 2점, 1000 likes = 3점
    """
    likes = paper.get("hf_likes", 0)
    if likes <= 0:
        return 0.0
    import math
    return math.log10(likes + 1)


def compute_score(paper: Dict, keywords: List[str]) -> float:
    """
    종합 점수.
    - 키워드 매칭 (강한 시그널)
    - 트렌딩 (보조 시그널)

    키워드가 없으면 trending만으로 점수.
    """
    kw_score = keyword_match_score(paper, keywords)
    trend_score = trending_score(paper)

    if not keywords:
        # cold start: trending만으로
        return trend_score * 10  # 가시성을 위해 가중

    # 키워드 + trending 결합. 키워드가 메인.
    return kw_score + trend_score * 2


def filter_and_rank(papers: List[Dict], keywords: List[str], top_n: int = 10) -> List[Dict]:
    """
    논문 필터링 + 정렬.

    Returns: (필터링된 논문 리스트, top_n으로 잘림)
    """
    # 점수 계산
    for p in papers:
        p["score"] = compute_score(p, keywords)

    # 점수 0보다 큰 것만
    filtered = [p for p in papers if p["score"] > 0]

    # 점수 내림차순
    filtered.sort(key=lambda p: p["score"], reverse=True)

    print(f"🔍 필터링: {len(papers)}편 중 {len(filtered)}편이 조건 통과")
    print(f"   상위 {top_n}편 선정")

    return filtered[:top_n]


def suggest_keywords(papers: List[Dict], top_n: int = 8) -> List[str]:
    """
    cold start 용. 수집된 논문들에서 자주 등장하는 키워드를 추천한다.

    방법:
    - 제목에서 자주 등장하는 2-3 단어 phrase 추출
    - 일반적인 stopword 제거
    - HF likes 많은 논문일수록 가중치
    """
    from collections import Counter

    # 흔한 ML/AI 키워드 후보 (도메인 사전)
    # 이 사전에 있는 단어가 제목에 등장하면 카운트
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
    ]

    counter = Counter()
    for paper in papers:
        text = (paper.get("title", "") + " " + paper.get("abstract", "")).lower()
        weight = 1 + trending_score(paper)  # HF likes 있으면 가중

        for kw in KEYWORD_VOCAB:
            pattern = r"\b" + re.escape(kw) + r"\b"
            if re.search(pattern, text):
                counter[kw] += weight

    return [kw for kw, _ in counter.most_common(top_n)]


if __name__ == "__main__":
    # 테스트
    test_papers = [
        {"title": "Large Language Models for RAG", "abstract": "we propose...", "hf_likes": 50},
        {"title": "Random theory paper", "abstract": "something irrelevant", "hf_likes": 0},
    ]
    filtered = filter_and_rank(test_papers, ["llm", "rag"], top_n=5)
    for p in filtered:
        print(p["score"], p["title"])
