<div align="center">

<img src="https://raw.githubusercontent.com/S-warm/.github/main/images/swarm_icon.png" width="70"/>

# UX-Swarm AI Framework

### 연령별 인지제약 기반 AI 사용자 시뮬레이션 엔진

**Prompt로 인간을 연기시키는 대신,  
인간이 인식하지 못하는 정보는 AI에게도 보여주지 않습니다.**

<br/>

`AI Framework Design` · `Cognitive Simulation` · `Web Automation` · `Distributed Processing`

<br/>

**2026 캡스톤 디자인 · 한성대학교 웹공학 트랙 교수 평가 1위**

</div>

---

## 📌 Project Overview

기존 LLM 기반 UX 테스트는 AI에게 `"70대 사용자처럼 행동하세요"`와 같은 Persona Prompt를 제공하더라도,  
AI가 실제로는 **페이지 전체 DOM과 풍부한 Context를 인식한 상태에서 판단한다는 한계**가 있습니다.

실제 사용자는 그렇지 않습니다.

작은 글씨를 놓칠 수 있고, 낮은 대비의 요소를 인식하지 못할 수 있으며,  
한 번에 기억할 수 있는 정보와 탐색할 수 있는 범위에도 한계가 있습니다.

UX-Swarm은 이 차이를 줄이기 위해 **인간의 인지적 제약을 Prompt가 아닌 Python 코드 레벨에서 적용**했습니다.

```text
Prompt-based Persona

Full DOM
   ↓
"70대처럼 행동하세요"
   ↓
LLM
   ↓
Action


UX-Swarm

Raw DOM
   ↓
WebNormalizer
   ↓
Standard UI Node
   ↓
Code-Level Cognitive Constraints
   ↓
Persona가 인식 가능한 Context
   ↓
Navigator AI
   ↓
Action
```

즉, AI에게 특정 연령대를 연기하도록 요구하는 것이 아니라  
**각 Persona가 실제로 인식할 수 있도록 제한된 정보 안에서 행동을 결정하도록 설계한 시뮬레이션 엔진**입니다.

---

## 👤 My Role

**4인 팀 팀장 · AI Framework 전체 설계 및 개발**

프로젝트 아이디어 구체화부터 AI Framework의 구조 설계, 웹 탐색 엔진, 인지제약 시스템,  
캐싱 및 대규모 로그 분석 파이프라인까지 AI 영역의 핵심 시스템을 담당했습니다.

| Area | Contribution |
|---|---|
| AI Framework | 전체 구조 설계 및 핵심 모듈 개발 |
| WebNormalizer | DOM → Standard UI Node 표준화 |
| Cognitive Layer | Pre-attentive / 연령별 인지제약 설계 |
| Navigation | Section / Tier 기반 절차적 탐색 엔진 |
| Agent Memory | Working / Task / Context / Long-Term Memory |
| Web Automation | Playwright 기반 실제 웹사이트 탐색 |
| Dynamic Web | MutationObserver 기반 증분 파싱 및 SPA 대응 |
| Vision | Claude Vision + 이미지 분류 / 색상 추출 |
| Cache | Parsing / Incremental / Screenshot / pHash Cache |
| Reliability | Task Parser, Success Verification, 새 탭 처리 |
| Analysis Pipeline | Step Functions + Lambda 기반 로그 분석 |
| Optimization | Prompt Context, Parsing, Vision 호출 최적화 |

---

# 🏗️ Architecture

## System Architecture

<p align="center">
  <img src="https://raw.githubusercontent.com/S-warm/.github/main/images/system_architecture.png" width="900"/>
</p>

UX-Swarm은 **Web Application과 AI Simulation Engine을 분리**했습니다.

```text
React
  ↓
Spring Boot
  ↓
Redis / Celery
  ↓
FastAPI AI Framework
  ↓
Playwright Simulation Workers
  ↓
S3 Raw Logs
  ↓
Step Functions + Lambda
  ↓
Auditor / Aggregation
  ↓
Result Dashboard
```

Spring Boot는 사용자 요청과 서비스 API를 담당하고,  
FastAPI 기반 AI Framework는 실제 웹 탐색과 Persona Simulation을 담당합니다.

시뮬레이션 작업은 Redis + Celery Queue를 통해 Worker에 분배하고,  
대용량 로그와 Screenshot은 S3에 저장한 뒤 별도의 분석 파이프라인에서 처리하도록 분리했습니다.

---

## AI Framework Architecture

<p align="center">
  <img src="https://raw.githubusercontent.com/S-warm/.github/main/images/ai_architecture.png" width="1000"/>
</p>

AI Framework의 핵심은 다음 흐름입니다.

```text
URL + Goal
    ↓
Playwright
    ↓
WebNormalizer
    ↓
Standard UI Node
    ↓
Pre-attentive Processing
    ↓
Section / Tier Scanning
    ↓
Age-based Cognitive Constraints
    ↓
Memory Context
    ↓
Navigator AI
    ↓
ActionExecutor
    ↓
Real Browser Action
    ↓
Re-observe
```

Navigator AI는 웹사이트의 전체 정보를 직접 전달받지 않습니다.

Python Layer에서 먼저 웹 정보를 표준화하고 Persona의 인지 조건에 따라 제한한 뒤,  
**현재 Persona가 인식할 수 있는 Context만 AI에게 전달**합니다.

---

# 🧠 Core Engineering

## 01. Code-Level Cognitive Constraint

### Prompt가 아니라 Input 자체를 제한했습니다

처음에는 LLM에게 연령별 Persona를 Prompt로 부여하는 방법도 검토했습니다.

하지만 Prompt만 변경하면 AI는 여전히 전체 DOM을 알고 있습니다.

```text
"70대처럼 행동해"

하지만 AI가 실제로 보는 정보:

- 모든 버튼
- 모든 링크
- 작은 글씨
- 낮은 대비 요소
- 페이지 전체 구조
```

이는 인간의 제한된 인지 환경과 다르다고 판단했습니다.

그래서 UX-Swarm에서는 **LLM 호출 이전에 Python이 인식 가능한 정보를 결정**합니다.

```text
DOM
 ↓
Standard UI Node
 ↓
Visual Priority
 ↓
Pre-attentive Filter
 ↓
Persona Cognitive Filter
 ↓
Filtered Context
 ↓
LLM
```

### 2-Layer Cognitive System

**Layer 1 — Universal Cognitive Constraints**

- 시각적 현저성 기반 Pre-attentive Processing
- 색상 대비
- 요소 크기
- Font Size / Thickness
- 제한된 Working Memory
- 순차적 정보 탐색

**Layer 2 — Persona-specific Constraints**

- 20대 / 50대 / 70대 기준 인지 파라미터
- 연령별 시각적 인지 차이
- Digital Literacy
- Persona별 Working Memory Limit

핵심 원칙은 단순합니다.

> **AI에게 인간처럼 행동하라고 지시하는 것이 아니라,  
> 인간처럼 제한된 정보를 보고 판단하도록 만든다.**

---

## 02. WebNormalizer — 웹을 AI가 이해할 수 있는 형태로 표준화

실제 웹사이트의 DOM은 AI가 그대로 사용하기에는 지나치게 복잡합니다.

중첩된 `div`, CSS, Script, 숨겨진 요소, 반복되는 Container 등이 포함되며  
사이트마다 구조도 모두 다릅니다.

이를 해결하기 위해 WebNormalizer를 설계했습니다.

```text
Raw DOM
   ↓
WebNormalizer
   ↓
Standard UI Node

{
  type,
  content,
  bbox,
  font_size,
  contrast,
  selector,
  xpath,
  ancestor_tags,
  image_analysis,
  ...
}
```

### 책임 분리

WebNormalizer에서는 **웹 구조를 정규화하는 역할만 수행**합니다.

```text
Normalizer
→ 렌더링되지 않는 정보 제거
→ DOM 구조 표준화
→ UI 속성 추출

Cognitive Layer
→ 작은 요소 제거
→ 낮은 대비 요소 제거
→ Persona별 인지 가능 여부 판단
```

인지 기준까지 Normalizer에 넣지 않은 이유는  
웹 파싱과 인간 인지 시뮬레이션이라는 서로 다른 책임을 분리하기 위해서였습니다.

이를 통해 향후 입력이 Web DOM이 아니더라도

```text
Web
Figma
Mobile
   ↓
Normalizer
   ↓
Standard UI Node
   ↓
Cognitive Layer
```

형태로 확장할 수 있도록 설계했습니다.

---

## 03. Section-Based Procedural Navigation

### 전체 DOM을 한 번에 탐색하지 않습니다

초기 방식에서는 AI에게 많은 DOM 요소를 한 번에 전달했습니다.

하지만 실제 인간은 페이지 전체를 동시에 읽지 않고  
특정 영역에 주의를 두며 순차적으로 탐색합니다.

이를 반영하기 위해 웹페이지를 의미 단위로 나눴습니다.

```text
HEADER
  ↓
NAV
  ↓
MAIN
  ↓
FOOTER
```

각 Section 내부에서는 다시 시각적 우선순위에 따라 Tier를 구성합니다.

```text
Section
 ├── High Tier
 ├── Medium Tier
 └── Low Tier
```

AI는 높은 시각적 우선순위의 요소부터 탐색하고,  
필요한 경우 다음 Tier 또는 Section으로 이동합니다.

### DOM 계층 구조 처리

실제 웹사이트에서는 다음과 같이 깊은 구조가 흔합니다.

```text
header
 └─ div
    └─ nav
       └─ ul
          └─ li
             └─ a
```

단순 `parent_tag`만 사용하면 이 `<a>`가 Header에 속한다는 사실을 알 수 없었습니다.

따라서 DOM 추출 단계에서 전체 조상 태그를 저장했습니다.

```text
ancestor_tags = ["li", "ul", "nav", "div", "header"]
```

이를 기반으로 Section을 분류하여 깊게 중첩된 실제 웹사이트에서도 의미 구조를 유지했습니다.

---

## 04. Stateful Agent over Stateless LLM

### 처음 했던 잘못된 가정

초기 설계에서는 증분 DOM만 AI에게 전달하면  
LLM이 이전 페이지 상태를 기억할 수 있다고 생각했습니다.

```text
Previous DOM
   +
Delta DOM
   ↓
LLM이 이전 상태를 기억할 것이라고 가정
```

하지만 API 호출 간 상태는 애플리케이션에서 직접 관리해야 했고,  
Delta만 전달해서는 Navigator가 이전 페이지 상태를 안정적으로 유지할 수 없었습니다.

그래서 **Memory의 책임을 LLM이 아닌 Python Layer로 이동**했습니다.

### Memory Architecture

```text
MemoryManager
 ├── WorkingMemory
 ├── TaskMemory
 ├── ContextMemory
 └── LongTermMemory
```

**WorkingMemory**

최근 행동과 현재 탐색 정보를 관리합니다.

**TaskMemory**

현재 Goal과 Step, 실패 횟수를 관리합니다.

**ContextMemory**

현재 페이지에서 Persona가 인식하고 있는 UI 상태를 관리합니다.

**LongTermMemory**

반복 실패와 Episode Summary 등 장기적으로 필요한 정보를 관리합니다.

매 LLM 호출 시 필요한 Memory를 조합해 Context를 생성합니다.

```text
Python Memory
     ↓
Prompt Context
     ↓
Stateless LLM
     ↓
Action
     ↓
Memory Update
```

이 과정에서 증분 파싱의 역할도 다시 정의했습니다.

```text
초기 생각

Incremental Parsing
→ LLM에게 Delta만 전달
→ Token 절감


최종 설계

Incremental Parsing
→ Python ContextMemory를 효율적으로 갱신

Context Compression
→ 실제 LLM Token 절감
```

이 경험을 통해 **웹 상태 관리와 LLM Context 최적화는 서로 다른 문제**라는 점을 구조적으로 분리했습니다.

---

## 05. Task Parser + Python Success Verification

### 300 Step을 반복하던 AI

초기 E2E 테스트에서는 AI가 실제 목표에 도달했음에도  
성공 여부를 정확하게 판단하지 못해 탐색을 계속하는 문제가 있었습니다.

결과적으로 최대 Step까지 반복했습니다.

```text
Goal
 ↓
Navigation
 ↓
Target 도달
 ↓
LLM이 성공 여부를 확신하지 못함
 ↓
다시 탐색
 ↓
...
 ↓
300 Step Timeout
```

Prompt에

```text
"목표를 달성했다면 즉시 declare_success 하세요."
```

와 같은 경고도 추가했지만 안정적으로 해결되지 않았습니다.

### 해결 1 — Task Parser

자연어 Goal을 시뮬레이션 시작 시 한 번 구조화합니다.

```text
Natural Language Goal
        ↓
Task Parser
        ↓
goal
final_target
success_condition
```

### 해결 2 — Python Success Verification

성공 여부와 같이 시스템 실행을 결정하는 중요한 분기를  
LLM의 판단에만 맡기지 않았습니다.

Navigation Loop 상단에서 Python이 직접 성공 조건을 검증합니다.

```text
Navigation Step
      ↓
Python Success Verification
      ↓
SUCCESS? ─── Yes ──→ Finish
      │
      No
      ↓
Navigator AI
```

### E2E Test Result

| Metric | Before | After |
|:---|---:|---:|
| Navigation Steps | **300** | **3** |
| Input Tokens | **63,068** | **1,966** |
| Result | Timeout | **Success** |
| Estimated API Cost | $0.0105 | **$0.0004** |

> 위 수치는 `example.com` 기반 E2E 테스트에서 Task Parser와 Success Verification 적용 전후를 비교한 결과입니다.

이 경험은 UX-Swarm의 중요한 설계 원칙으로 이어졌습니다.

> **LLM에게 판단을 맡길 수는 있지만,  
> 시스템의 Critical Control Flow까지 맡기지는 않는다.**

---

# 🎬 AI Simulation in Action

### 실제 웹사이트를 탐색하는 Navigator AI

<p align="center">
  <img width="800" height="519" alt="swarm-dev" src="https://github.com/user-attachments/assets/7e998dea-3195-4659-9454-e72b0d985252" />
</p>

<p align="center">
  <sub>
    한성대학교 컴퓨터공학부 홈페이지에서
    <b>구성원 → 교수진</b> 경로를 탐색하는 Navigator AI
  </sub>
</p>

Navigator AI는 단순히 다음 행동을 텍스트로 생성하는 것이 아니라,

```text
Perception
   ↓
Cognitive Filtering
   ↓
Section / Tier Navigation
   ↓
LLM Decision
   ↓
ActionExecutor
   ↓
Playwright Click / Input
   ↓
DOM Re-observation
```

과정을 반복하며 **실제 브라우저를 직접 조작**합니다.

---

# 🌐 Dynamic Web & Real-Site Reliability

## 06. Incremental Parsing

현대 웹사이트는 클릭할 때마다 전체 페이지가 새로 로드되지 않습니다.

Dropdown, Modal, SPA Component와 같이 일부 DOM만 변경되는 경우가 많기 때문에  
매 행동마다 전체 DOM을 다시 파싱하는 것은 비효율적입니다.

UX-Swarm은 `MutationObserver` 기반 증분 파싱을 구현했습니다.

```text
User Action
    ↓
MutationObserver
    ↓
Added / Modified / Removed Nodes
    ↓
Incremental Parser
    ↓
ContextMemory Merge
```

구조 역시 역할별로 분리했습니다.

```text
WebNormalizerIncremental
 ├── MutationObserver   # 변경 감지
 ├── CacheManager       # Node 상태 관리
 └── Delta Parser       # 변경 내용 판단
```

---

## 07. SPA Transition Detection

쇼핑몰 실사이트 테스트 중 URL이 변경되지 않는 SPA 전환을 발견했습니다.

기존 로직:

```text
URL changed
→ New Page

URL unchanged
→ Same Page
```

이 방식으로는 카테고리 필터처럼 URL 없이 전체 상품 목록이 교체되는 상황을 탐지할 수 없었습니다.

이를 위해 **Weak Delta Fallback**을 추가했습니다.

```text
URL unchanged
     ↓
Mutation Delta 검사
     ↓
Text Node 없음
+
Container 3개 이상 변경
     ↓
List Structure Replacement로 판단
     ↓
Parsing Cache 삭제
     ↓
Full Parsing Fallback
```

단순 URL 변화가 아니라 **DOM 구조 변화까지 페이지 상태 판단에 활용**하도록 확장했습니다.

---

## 08. Vision Pipeline & pHash Cache

DOM만으로는 이미지가 무엇을 의미하는지 알 수 없습니다.

따라서 이미지 요소는 별도의 Vision Pipeline으로 처리했습니다.

```text
Full-page Screenshot
       ↓
Bounding Box Crop
       ↓
Claude Vision
       ↓
type + description
       ↓
Optional Color Extraction
       ↓
Standard UI Node
```

### N번 Screenshot → 1번 Screenshot

초기 구현에서는 이미지마다 Playwright Screenshot을 호출했습니다.

```text
34 Images
→ page.screenshot() × 34
```

화면 밖 요소에서는 Clip 오류도 발생했습니다.

이를 다음과 같이 변경했습니다.

```text
page.screenshot(full_page=True) × 1
              ↓
          PIL Crop
              ↓
        Individual Images
```

한 번의 Full-page Screenshot을 기준으로 각 이미지의 Bounding Box를 Crop하도록 변경해  
반복적인 브라우저 Screenshot 호출과 화면 밖 Clip 오류를 함께 줄였습니다.

### pHash Cache

이미지 URL을 Cache Key로 사용하면 같은 이미지가 압축되거나 크기가 변경됐을 때  
다른 이미지로 인식됩니다.

따라서 URL 대신 **Perceptual Hash(pHash)** 를 Cache Key로 사용했습니다.

```text
Same Visual Image

/image/product_100.png
/image/product_300.webp
/cdn/compressed/product.jpg
          ↓
        pHash
          ↓
      Same Cache
```

이를 통해 시각적으로 동일한 이미지에 대한 Vision AI 중복 호출을 줄였습니다.

---

# 🔥 Troubleshooting

## 01. DBpia — 526개의 링크가 있는데 AI는 논문을 보지 못했다

실사이트 검증 과정에서 DBpia 검색 결과 페이지의 목표 논문 링크가  
DOM에는 존재하지만 AI에게 전달되지 않는 문제가 발생했습니다.

```text
<a> Tags in DOM : 526
Target after normalize : 0
```

처음부터 특정 모듈을 의심하는 대신 파싱 파이프라인 전체에 추적 로그를 삽입했습니다.

```text
normalize()
   ↓
pre_attentive
   ↓
group_by_html_tag()
   ↓
classify_by_percentile()
   ↓
persona.filter_nodes()
```

각 단계에서 목표 논문 키워드의 생존 여부를 추적했습니다.

```text
[TRACK_NORMALIZE]
[TRACK]
```

그 결과 `normalize()` 직후부터 목표 요소가 정상적으로 노출되지 않는 것을 확인했고,  
원인을 `TypeExtractor`까지 좁혔습니다.

### Root Cause

`<body>`와 같은 Container가 자손의 `textContent`를 가지고 있다는 이유로  
`text` Node로 분류되고 있었습니다.

```text
<body>
  ↓
All Descendant textContent
  ↓
One Giant Text Node
  ↓
Actual Links lose priority
```

### Fix

```text
Before
Container + textContent
→ text

After
div / section / body / header ...
→ always container
```

Container의 직접 텍스트는 별도로 제한하여 의미를 보존했습니다.

### Result

수정 후 DBpia에서 20대 / 50대 / 70대 Persona 모두 실제 사이트 E2E 탐색을 완료했습니다.

> **파싱 파이프라인 문제는 추측으로 수정하지 않고,  
> 각 단계의 입력과 출력을 추적해 데이터가 사라지는 정확한 지점을 찾는다.**

---

## 02. New Tab Race Condition

DBpia 논문 링크는 `target="_blank"`로 새 탭을 생성했습니다.

기존에는 클릭 직후

```python
context.pages[-1]
```

을 확인했는데, 새 탭 생성은 비동기이므로 실행 시점에 따라 성공 여부가 달라지는 Race Condition이 발생했습니다.

이를 해결하기 위해 책임을 재설계했습니다.

```text
Before

ActionExecutor
→ Click

NavigationLoop
→ Tab Detection
→ Page Swap


After

ActionExecutor
→ Click
→ New Tab Detection
→ Return new_page

NavigationLoop
→ Page Swap only
```

`ActionExecutor`가 클릭과 그 결과로 발생한 새 탭까지 책임지도록 변경하고,  
NavigationLoop는 반환된 Page를 교체하는 역할만 담당하도록 분리했습니다.

---

## 03. Prompt Context Explosion

Main Section에 수백 개의 Node가 존재하면  
중·하위 Tier 전체를 Prompt에 전달하면서 **85,000자 이상**의 Context가 생성됐습니다.

하지만 탐색하지 않은 Tier의 모든 세부 정보가 필요한 것은 아니었습니다.

따라서 Context의 목적에 따라 표현 방법을 나눴습니다.

```text
Explored Tier
→ element_id + type + content
→ 다시 돌아가 행동할 수 있어야 함

Unexplored Tier
→ type별 개수만 전달
→ 구조 파악만 필요
```

```text
Before
85,000+ chars

After
수천 자 수준
```

단순 문자열 자르기가 아니라  
**Context가 어떤 판단에 사용되는지를 기준으로 정보량을 조절**했습니다.

---

## 04. Stateful Object Reuse

Guide AI와 Persona Simulation은 비용 절감과 Cache 공유를 위해  
일부 Stateful Object를 재사용했습니다.

하지만 이 과정에서 다음 상태 오염 문제가 발생했습니다.

```text
Guide AI
 ↓
log_dir 변경
screenshot_cache 생성
page가 성공 URL까지 이동
 ↓
Persona Simulation
```

그 결과

- Persona 로그가 Guide 폴더에 저장
- Screenshot Cache 공유 실패
- Persona가 성공 페이지에서 시작해 즉시 성공 처리

등의 문제가 발생했습니다.

각 실행 단계 진입 시 초기 상태를 명시적으로 보장하도록 변경했습니다.

```text
Guide Finish
    ↓
log_dir Restore
ScreenshotCache Share
page.goto(target_url)
    ↓
Persona Start
```

> **Stateful Object를 재사용할 때는  
> 각 Lifecycle 진입 시 초기 상태를 명시적으로 보장한다.**

---

<details>
<summary><b>그 외 해결한 주요 문제 보기</b></summary>

<br/>

### MutationObserver

- `display:none → block` 속성 변경 감지
- Dropdown 형제 Node 감지
- Modal 등 전역 Layer 대응
- Removed Node의 Image Pipeline 진입 방지

### NavigationLoop

- `step_count` 증가 누락으로 발생 가능한 무한 루프 수정
- SectionNavigator 반복 재생성으로 인한 탐색 상태 초기화 해결
- `header → nav → main → footer` 순서 명시적 보장
- 클릭 후 URL 변경 대기 추가

### Memory

- `TaskMemory.set_goal()`이 누적 실패 횟수를 초기화하던 Lifecycle 오류 수정
- `reset / clear / set_goal` 책임 분리

### Lambda Pipeline

- 설계 문서와 실제 `final_issues.json` Schema 불일치 수정
- `20대` / `20s` S3 경로 규약 불일치 수정
- S3 Prefix 전체 탐색 후 `session_id → key` Cache 생성

### Docker / AWS

- Stateful Worker의 Guide → Persona 상태 오염 해결
- S3 경로에 `title_slug`를 도입해 프로젝트별 결과 충돌 방지
- Lambda Pipeline 전체에 `title_slug` 전파

</details>

---

# ⚡ Performance & Optimization

UX-Swarm은 대규모 Persona Simulation을 고려하여  
브라우저 처리, LLM Context, Vision 호출, 로그 분석 각각에 최적화 전략을 적용했습니다.

| Problem | Optimization | Result / Purpose |
|---|---|---|
| 목표 판단 반복 | Task Parser + Python Verification | **300 → 3 Steps** |
| LLM Context 증가 | Tier Summary / Count | **85K+ → 수천 자** |
| E2E Input Tokens | Task 구조화 + Context 개선 | **63,068 → 1,966** |
| 이미지별 Screenshot | Full Screenshot + PIL Crop | **N calls → 1 call** |
| Vision 중복 호출 | pHash Cache | 동일 이미지 재분석 방지 |
| 반복 DOM Parsing | Guide AI + ParsingCache | Persona 간 Parsing 결과 재사용 |
| Dynamic DOM | Incremental Parsing | 변경 Node 중심 처리 |
| 대규모 로그 | Map-Reduce Pipeline | 분석 단계 분산 |
| 독립 분석 작업 | Step Functions Parallel | Lambda 5/6/7 병렬 처리 |

> 측정값은 개발 과정의 해당 E2E 테스트 조건에서 기록된 결과이며, 사이트와 시뮬레이션 조건에 따라 달라질 수 있습니다.

---

# ☁️ Distributed Analysis Pipeline

Persona Simulation에서 생성되는 대규모 로그를 한 번에 LLM에 전달하지 않고  
AWS Step Functions + Lambda 기반 분석 파이프라인으로 분리했습니다.

<p align="center">
  <img width="307" height="481" alt="스크린샷 2026-09-01 오후 4 29 25" src="https://github.com/user-attachments/assets/0af02872-ec71-4d59-9051-9dda043578e4" />
</p>

```text
S3 Raw Logs
     ↓
Lambda 1
Session Grouping
     ↓
Lambda 2
Structuring
     ↓
Lambda 3
Embedding + Issue Analysis
     ↓
Lambda 4
Issue Reduce / Deduplication
     ↓
┌──────────────────────────────┐
│      Parallel Processing     │
│                              │
│ Lambda 5   Lambda 6  Lambda 7│
│ AI Fix     Heatmap   Overview│
└──────────────────────────────┘
     ↓
Lambda 8
Spring Boot POST
```

### Lambda 4 — Issue Reduce

연령별 분석 결과를 `text-embedding-3-small` Embedding 유사도로 비교하여  
동일한 UX Issue를 병합합니다.

### Lambda 5 — AI Fix Suggestion

Issue가 발생한 URL의 DOM을 가져와 Claude Haiku를 이용해

```text
Issue
 ↓
Problem Element Selector
 ↓
Current CSS
 ↓
Before / After Fix
```

형태의 수정 제안을 생성합니다.

### Lambda 6 — Heatmap Aggregation

실패 좌표를 연령대별로 집계하고 가까운 좌표를 Cluster로 묶어  
실제 Screenshot 위에 UX Failure Point를 표시할 수 있도록 가공합니다.

### Lambda 7 — Overview

세션별 결과를 기반으로

- Success Rate
- Failure Rate
- Average Duration
- Average Actions

등을 연령대별로 집계합니다.

### Parallel Processing

Lambda 5, 6, 7은 모두 Lambda 4의 결과를 필요로 하지만  
서로에게는 의존하지 않습니다.

따라서 순차 실행하지 않고 Step Functions의 Parallel State로 구성했습니다.

```text
Lambda 4
   ↓
 ┌─ Lambda 5
 ├─ Lambda 6
 └─ Lambda 7
   ↓
Lambda 8
```

---

# 🔌 Service Communication Design

Spring Boot와 AI Framework가 내부 저장소 구조에 직접 의존하지 않도록  
서비스 간 통신은 REST Interface를 기준으로 설계했습니다.

```text
Spring Boot
    ↓
FastAPI REST API
    ↓
Redis / Celery
```

Spring이 AI 서비스의 Redis Key를 직접 읽는 방식은 사용하지 않았습니다.

```text
Spring ─X→ AI Redis

Spring → FastAPI → AI Internal Storage
```

AI 내부 구현이 변경되더라도 Spring에 영향을 최소화하기 위한 선택입니다.

### Progress Tracking

작업 완료 알림만 보내는 Webhook 대신  
실시간 진행률을 조회할 수 있도록 Polling 방식을 선택했습니다.

```text
Simulation
     ↓
Redis Atomic Counter
     ↓
FastAPI /status
     ↑
Spring Polling
```

분석 완료 상태는 EC2 Lifecycle과 독립적으로 유지하기 위해  
S3의 완료 데이터를 함께 사용하도록 설계했습니다.

```text
running
→ Simulation 진행

analyzing
→ Simulation 완료 / Analysis 진행

completed
→ Analysis 완료
```

---

# 🛠️ Tech Stack

<div align="center">

### AI / Simulation

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![Playwright](https://img.shields.io/badge/Playwright-2EAD33?style=flat-square&logo=playwright&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=flat-square&logo=openai&logoColor=white)
![Claude](https://img.shields.io/badge/Claude-D97757?style=flat-square)

### Backend / Data

![Spring Boot](https://img.shields.io/badge/Spring_Boot-6DB33F?style=flat-square&logo=springboot&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-DC382D?style=flat-square&logo=redis&logoColor=white)
![Celery](https://img.shields.io/badge/Celery-37814A?style=flat-square&logo=celery&logoColor=white)

### Infrastructure

![AWS](https://img.shields.io/badge/AWS-232F3E?style=flat-square&logo=amazonwebservices&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white)

</div>

| Category | Technologies |
|---|---|
| Language | Python |
| AI Framework | FastAPI, Playwright |
| LLM | GPT-4o-mini, GPT-4o |
| Vision / Fix | Claude Vision, Claude Haiku |
| Cognitive Processing | NumPy, scikit-learn, PIL |
| Queue | Redis, Celery |
| Backend | Spring Boot |
| Database | PostgreSQL / AWS RDS |
| Storage | AWS S3 |
| Pipeline | AWS Step Functions, Lambda |
| Infrastructure | AWS EC2, Docker |

---

# 🏆 Project Results

<div align="center">

### 2026 한성대학교 캡스톤 디자인

## 웹공학 트랙 교수 평가 1위

</div>

AI에게 Persona를 Prompt로 부여하는 기존 접근에서 출발했지만,  
개발 과정에서 **인지제약 → 웹 탐색 → Memory → Dynamic Web → 대규모 분석**까지 직접 구조화하며  
실제 웹사이트에서 동작하는 AI 사용자 시뮬레이션 Framework로 발전시켰습니다.

### Award

<p align="center">
  <!-- 상장 사진 업로드 후 src만 변경 -->
  <img width="400" height="600" alt="KakaoTalk_Photo_2026-09-01-16-23-57" src="https://github.com/user-attachments/assets/bd03e4c8-f455-47d6-bcf9-4b45126de9e0" />
</p>

<p align="center">
  <sub>캡스톤 디자인 수상 상장</sub>
</p>

---

# 🎤 Presentation & Demo

<p align="center">
  <img width="612" height="408" alt="KakaoTalk_Photo_2026-09-01-15-14-38_evoto_edited" src="https://github.com/user-attachments/assets/1f90da1b-ed20-4b1c-a935-b9faa7f8830b" />
</p>

<p align="center">
  <sub>
    2026 캡스톤 디자인 현장에서 UX-Swarm의 AI Framework 구조와
    실제 Persona Simulation 과정을 시연했습니다.
  </sub>
</p>

<br/>

<table align="center">
  <tr>
    <td width="50%" align="center">
      <img
        src="https://github.com/user-attachments/assets/9e9356a4-48ab-4db3-8576-aa7d9db9959b"
        width="100%"
        alt="프로젝트 현장 시연"
      />
      <br/>
      <b>프로젝트 현장 시연</b>
    </td>
    <td width="50%" align="center">
      <img
        src="https://github.com/user-attachments/assets/cd899a49-a8a8-4d90-918b-dc08caa414c6"
        width="100%"
        alt="Swarm 시뮬레이션 구동 환경"
      />
      <br/>
      <b>AI Simulation 구동 환경</b>
    </td>
  </tr>
</table>

---

# 🔗 Related Repositories

| Repository | Description |
|---|---|
| **BE_AI_Framework** | AI Framework · Cognitive Layer · Navigator · WebNormalizer · Analysis Pipeline |
| **BE** | Spring Boot API Server · PostgreSQL · Infrastructure |
| **FE** | React + TypeScript Dashboard |
| **Swarm Organization** | 프로젝트 전체 소개 및 Architecture |

---

# 💡 What I Learned

UX-Swarm을 개발하면서 가장 크게 배운 것은  
**LLM의 성능만으로 Agent의 품질이 결정되지 않는다는 점**이었습니다.

웹 상태와 Memory를 어떻게 관리할지,  
AI에게 어떤 정보를 보여줄지,  
어떤 판단을 LLM에게 맡기고 어떤 판단을 코드에서 보장할지에 따라  
Agent의 안정성과 비용이 크게 달라졌습니다.

특히 프로젝트를 진행하며 다음 원칙을 실제 문제를 통해 정립했습니다.

> **1. LLM의 행동을 바꾸려면 Prompt뿐 아니라 Input 구조를 설계해야 한다.**

> **2. Memory는 LLM이 아니라 Application Layer가 관리한다.**

> **3. Critical Control Flow는 LLM 응답에만 의존하지 않는다.**

> **4. Dynamic Web은 URL이 아니라 실제 DOM 상태를 함께 봐야 한다.**

> **5. 최적화 전에 데이터가 어디서 생성되고 어디서 소비되는지 먼저 확인한다.**

초기 설계를 그대로 구현하는 것보다,  
실제 웹사이트에서 실패하는 지점을 추적하고 가정을 수정하면서  
**AI가 실제 환경에서 안정적으로 동작하기 위한 시스템을 설계하는 과정**에 집중했습니다.

---

<div align="center">

### UX-Swarm

**Code-Level Cognitive Constraints for AI User Simulation**

<br/>

2026 Capstone Design · Hansung University

</div>
