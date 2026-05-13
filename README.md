# AI 트렌드 뉴스레터

매일 아침 arXiv + Hugging Face Daily Papers에서 나에게 맞는 AI/ML 논문을 큐레이션해서 이메일로 보내주는 자동화 시스템.

## 동작 방식

```
arXiv (어제자 cs.LG, cs.IR, ...)  ─┐
                                    ├─→ 키워드 필터 + trending 점수 ─→ Top 10 ─→ LLM 요약 ─→ HTML + Email
Hugging Face Daily Papers ─────────┘
```

- **키워드가 설정되어 있으면**: 본인 관심 키워드에 매칭되는 논문 우선
- **키워드가 없으면**: 자동으로 트렌딩 키워드 추천 + HF likes 많은 논문 보여줌

## 셋업 (10분)

### 1. 이 repo를 본인 계정으로 fork

GitHub에서 fork 버튼 누르면 됨.

### 2. API 키 발급

**Anthropic Claude API** (요약용, 권장):
- https://console.anthropic.com 가입
- API Keys → Create Key → 복사
- 처음 가입하면 $5 free credit (논문 ~500편 요약 가능)

### 3. Gmail 앱 비밀번호 발급 (이메일 발송용)

- https://myaccount.google.com/apppasswords
- 2단계 인증 켜져 있어야 함
- "trend-newsletter" 같은 이름으로 비밀번호 생성 → 16자리 코드 복사

### 4. GitHub Secrets 등록

본인 fork한 repo → Settings → Secrets and variables → Actions → New secret

| 이름 | 값 |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API 키 |
| `EMAIL_PASSWORD` | Gmail 앱 비밀번호 |

### 5. 연구 분야 선택

`config.example.yaml`을 복사해서 `config.yaml` 만들고, `research_profile`을 본인 분야로 설정:

```yaml
research_profile: "data-mining"  # 또는 ml-general, nlp, cv, speech, robotics, database, security, all
```

이 한 줄 설정만으로 arXiv 카테고리가 자동 매핑되고, 본인 분야 트렌드만 수집해요. 자세한 매핑은 `profile.py` 참조.

### 6. 키워드 설정

키워드는 두 가지 방법으로 등록 가능:

**방법 A: 대시보드에서 (편함)**
1. GitHub Actions가 한 번 실행되면 대시보드 생성됨
2. 본인 GitHub Pages URL 접속 → "내 키워드" 패널에서 추가/제거/추천 chip 클릭
3. **트렌딩 페이지에서도 + 버튼**으로 인기 키워드 한 번에 등록 가능
4. "keywords.json 다운로드" 버튼 클릭
5. 다운로드된 파일을 GitHub repo 루트에 업로드 (또는 기존 파일 덮어쓰기)
6. 다음 실행부터 적용

**방법 B: 직접 파일 작성**
repo 루트에 `keywords.json` 파일 생성:
```json
{
  "keywords": ["data quality", "RAG", "graph neural network"],
  "updated_at": "2026-05-13"
}
```

`config.yaml`은 fallback용 (keywords.json 없을 때만 그쪽 keywords 사용).

### 6. GitHub Pages 활성화 (대시보드 보려면)

Settings → Pages → Source: "Deploy from a branch" → Branch: `main`, Folder: `/dashboard` → Save

그러면 `https://본인-username.github.io/trend-newsletter` 에서 대시보드 볼 수 있음.

### 7. Actions 활성화

Settings → Actions → General → "Allow all actions" 체크.

이후 매일 한국시간 오전 9시 (UTC 자정)에 자동 실행됨. 수동 실행하려면 Actions 탭 → Daily Newsletter → Run workflow.

## 로컬에서 테스트

```bash
pip install -r requirements.txt
cp config.example.yaml config.yaml
# config.yaml 편집
export ANTHROPIC_API_KEY="sk-ant-..."
export EMAIL_PASSWORD="your-app-password"
python main.py
```

`dashboard/index.html`을 브라우저로 열면 결과 확인.

## 비용

- arXiv API: 무료
- Hugging Face API: 무료
- GitHub Actions: 월 2000분 무료 (이 작업은 1회 ~2분 → 무료 한도 안에서 충분)
- Claude Haiku API: 논문 10편 요약 약 5~10원/일 → 월 200~300원

## 파일 구조

```
trend-newsletter/
├── profile.py          # 연구 분야 → arXiv 카테고리 매핑
├── fetcher.py          # arXiv + HF 논문 수집
├── filter.py           # 키워드 매칭 + 트렌딩 점수
├── summarizer.py       # LLM 요약
├── trending.py         # 온라인 트렌딩 키워드 수집 + 시계열 비교 + 종합 ranking
├── sender.py           # HTML + 이메일
├── main.py             # 메인 파이프라인
├── config.example.yaml
├── keywords.example.json
├── requirements.txt
├── .github/workflows/daily.yml
├── trending-archive/   # 매일 trending.json 백업 (자동 생성)
└── dashboard/
    ├── index.html      # 내 키워드 + 매일 추천
    ├── trending.html   # 온라인 트렌딩 (종합 + 3개 출처 탭)
    └── posts/          # 매일 YYYY-MM-DD.html
```

## 페이지 구성

**`index.html` (메인)**: 내 키워드 큐레이션
- 내 키워드 관리 (등록/제거/추천)
- 오늘의 추천 논문 (LLM 요약 포함)
- 키워드 칩 클릭으로 in-page 필터

**`trending.html` (별도 페이지)**: 온라인 트렌딩
- **종합 ranking** — 3개 출처 점수 정규화 평균 + 출처 다양성 가중
- **arXiv 최근 7일** — submission 빈도, ▲▼ 어제 대비 순위 변화
- **Hugging Face Daily** — 전문가 큐레이션 + likes
- **Papers with Code** — 코드 공개 (재현 가능)
- `+` 버튼으로 트렌딩 키워드 즉시 등록 (이미 등록되면 초록 체크)
- 키워드 클릭하면 관련 최근 논문 5-10편 펼쳐짐

## 커스터마이징

- **다른 카테고리 추가**: `config.yaml`의 `arxiv_categories`에 `cs.CV` 등 추가
- **더 많은 논문**: `top_n_in_newsletter` 올림
- **다른 시간**: `.github/workflows/daily.yml`의 cron 수정
- **OpenAI 사용**: `summarizer.py`의 Anthropic 부분을 OpenAI로 교체

## 트러블슈팅

**이메일 안 옴**: GitHub Actions 로그에서 에러 확인. Gmail 앱 비밀번호 다시 발급해보세요.

**요약 안 됨**: ANTHROPIC_API_KEY가 secrets에 올바르게 들어갔는지 확인. credit 잔액도.

**arXiv timeout**: 잠시 후 다시 시도. Actions 탭에서 Re-run.
