"""
연구 분야 프로필.
대학원생이 자신의 분야를 선택하면 거기에 맞는 arXiv 카테고리와 seed 키워드를 자동으로 매핑.

분야는 단일 선택 — 한 사람이 보통 한 분야 깊이 파니까.
필요하면 본인이 keywords.json 수정해서 customize.
"""

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
        "description": "ACL, EMNLP, NAACL, NeurIPS NLP track",
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
    "all": {
        "label": "전체 AI/ML (분야 미정)",
        "description": "분야 정하기 전 광범위 탐색",
        "arxiv_categories": ["cs.LG", "cs.AI", "cs.CL", "cs.CV", "cs.IR"],
        "seed_keywords": [],
    },
}


def get_profile(profile_id: str) -> dict:
    """profile_id로 프로필 dict 반환. 없으면 'all' 반환."""
    return PROFILES.get(profile_id, PROFILES["all"])


def list_profiles() -> list:
    """profile 리스트 (UI 표시용)."""
    return [
        {"id": pid, "label": p["label"], "description": p["description"]}
        for pid, p in PROFILES.items()
    ]


if __name__ == "__main__":
    for pid, p in PROFILES.items():
        print(f"{pid:15s} {p['label']:35s} {p['arxiv_categories']}")
