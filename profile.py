"""
연구 분야 프로필.
대학원생이 자신의 분야를 선택하면 거기에 맞는 arXiv 카테고리와 seed 키워드를 자동으로 매핑.

다중 선택 지원: ["data-mining", "nlp"] 식으로 여러 분야 동시 선택 가능.
"""

from typing import List, Dict


PROFILES = {
    "data-mining": {
        "label": "데이터 마이닝 / Knowledge Discovery",
        "description": "KDD, CIKM, WSDM, SIGIR, ICDM, WWW",
        "arxiv_categories": ["cs.IR", "cs.DB", "cs.LG", "cs.AI"],
        "seed_keywords": [
            "graph neural network", "recommender system", "knowledge graph",
            "data mining", "anomaly detection", "time series",
            "retrieval augmented generation", "rag",
        ],
    },
    "ml-general": {
        "label": "Machine Learning (일반)",
        "description": "NeurIPS, ICML, ICLR",
        "arxiv_categories": ["cs.LG", "stat.ML", "cs.AI"],
        "seed_keywords": [
            "large language model", "diffusion", "transformer",
            "reinforcement learning", "scaling law", "fine-tuning",
            "alignment", "evaluation",
        ],
    },
    "nlp": {
        "label": "자연어처리 (NLP)",
        "description": "ACL, EMNLP, NAACL",
        "arxiv_categories": ["cs.CL", "cs.LG", "cs.AI"],
        "seed_keywords": [
            "large language model", "instruction tuning", "rag",
            "reasoning", "alignment", "hallucination", "agent",
            "in-context learning", "evaluation", "benchmark",
        ],
    },
    "cv": {
        "label": "컴퓨터 비전 (Computer Vision)",
        "description": "CVPR, ICCV, ECCV",
        "arxiv_categories": ["cs.CV", "cs.LG", "cs.AI"],
        "seed_keywords": [
            "diffusion", "vision-language", "multimodal",
            "3d generation", "video generation", "self-supervised",
            "image segmentation", "object detection",
        ],
    },
    "speech": {
        "label": "음성 / 오디오",
        "description": "INTERSPEECH, ICASSP",
        "arxiv_categories": ["cs.SD", "eess.AS", "cs.CL", "cs.LG"],
        "seed_keywords": [
            "speech", "audio", "tts", "asr", "speech recognition",
            "speech synthesis", "multimodal",
        ],
    },
    "robotics": {
        "label": "로보틱스 / 강화학습",
        "description": "RSS, CoRL, ICRA, IROS",
        "arxiv_categories": ["cs.RO", "cs.LG", "cs.AI"],
        "seed_keywords": [
            "reinforcement learning", "embodied", "manipulation",
            "imitation learning", "policy", "world model",
        ],
    },
    "database": {
        "label": "데이터베이스 / 시스템",
        "description": "SIGMOD, VLDB, ICDE",
        "arxiv_categories": ["cs.DB", "cs.LG", "cs.DC"],
        "seed_keywords": [
            "query optimization", "data quality", "data integration",
            "transactional", "indexing", "vector database",
        ],
    },
    "security": {
        "label": "AI 보안 / 프라이버시",
        "description": "S&P, USENIX Security, CCS",
        "arxiv_categories": ["cs.CR", "cs.LG", "cs.AI"],
        "seed_keywords": [
            "adversarial", "privacy", "differential privacy",
            "federated learning", "jailbreak", "watermark",
            "membership inference",
        ],
    },
}


def get_profile(profile_id: str) -> dict:
    """단일 profile_id로 프로필 dict 반환."""
    return PROFILES.get(profile_id, PROFILES["data-mining"])


def get_combined_profile(profile_ids: List[str]) -> Dict:
    """
    여러 프로필을 합쳐서 하나의 dict로.
    - arxiv_categories: union (중복 제거, 순서 유지)
    - seed_keywords: union
    - label: "데이터 마이닝, NLP" 식으로 결합
    """
    if not profile_ids:
        profile_ids = ["data-mining"]

    categories_set = []
    keywords_set = []
    labels = []

    for pid in profile_ids:
        if pid not in PROFILES:
            continue
        p = PROFILES[pid]
        for cat in p["arxiv_categories"]:
            if cat not in categories_set:
                categories_set.append(cat)
        for kw in p["seed_keywords"]:
            if kw not in keywords_set:
                keywords_set.append(kw)
        labels.append(p["label"])

    return {
        "ids": profile_ids,
        "label": " · ".join(labels) if labels else "데이터 마이닝",
        "arxiv_categories": categories_set or ["cs.LG", "cs.AI"],
        "seed_keywords": keywords_set,
    }


def list_profiles() -> List[Dict]:
    """profile 리스트 (UI 표시용)."""
    return [
        {"id": pid, "label": p["label"], "description": p["description"]}
        for pid, p in PROFILES.items()
    ]


if __name__ == "__main__":
    combined = get_combined_profile(["data-mining", "nlp"])
    print("Combined:", combined["label"])
    print("Categories:", combined["arxiv_categories"])
    print("Keywords:", combined["seed_keywords"])
