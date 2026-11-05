# 즉시로 — 법령 조문을 가장 빠르고 간편하게 확인하세요
# Immediately Law — The world's fastest law check, ever.

<p align="center">
  <a href="https://immediatelylaw.kro.kr/" target="_blank" rel="noopener">
    <img src="assets/screenshot.png" width="720" alt="즉시로 화면 갈무리 — 클릭하면 홈페이지로 이동">
  </a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-v1.8.0-blue" alt="v1.8.0">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
  <img src="https://img.shields.io/badge/platform-Windows%2010%2F11-blue" alt="Windows 10/11">
  <img src="https://img.shields.io/badge/Python-v3.15-blue" alt="Python">
  <img src="https://img.shields.io/badge/Python-PSF-green" alt="Python PSF">
  <img src="https://img.shields.io/badge/PySide6-v6.12.0-blue" alt="PySide6">
  <img src="https://img.shields.io/badge/PySide6-LGPL--3.0-green" alt="PySide6 LGPL-3.0">
  <img src="https://img.shields.io/badge/requests-v2.34.2-blue" alt="requests">
  <img src="https://img.shields.io/badge/requests-Apache--2.0-green" alt="requests Apache-2.0">
  <img src="https://img.shields.io/badge/pypdf-v6.21.3-blue" alt="pypdf">
  <img src="https://img.shields.io/badge/pypdf-BSD--3--Clause-green" alt="pypdf BSD-3-Clause">
  <img src="https://img.shields.io/badge/defusedxml-v0.7.1-blue" alt="defusedxml">
  <img src="https://img.shields.io/badge/defusedxml-PSF-green" alt="defusedxml PSF">
</p>

**즉시로**(Immediately Law)는 대한민국 법령을 가장 빠르게 확인할 수 있는 프로그램입니다.

텍스트로 제시되는 법령을 복사(Ctrl + C)하면 **화면 오른쪽 아래**에 조문이 바로 출력됩니다.

> "개인정보 보호법 제15조"라고만 안내되어 직접 해당 조문을 찾아봐야 했던 번거로움,
> **이제 즉시로가 끝내드립니다.** 안내된 법령을 복사(Ctrl + C)만 하세요.
> 조문은 즉시로가 찾아드릴게요!

- **사용환경**: Windows 10/11 (64-bit)
- **속도**: 조문 열람은 전부 로컬 DB를 색인하여 즉시 보여집니다.
- **데이터**: 국가법령정보센터(법제처) OPEN API, 전체 현행 법령 + 시행령 + 시행규칙
  (약 5,600종 · 20만 조문)을 매일 자동 갱신
- **온/오프라인**: 오프라인에서도 동작하며, 온라인 상태에서는 실시간으로 현행 법령과 일치하는지를 확인하는 기능이 제공됩니다.

---

## 설치 방법

### 마이크로소프트 스토어 (공식)

공식 버전을 마이크로소프트 스토어에서도 설치할 수 있습니다. 스토어 버전은 마이크로소프트가 검증·서명한 설치형으로 보안 경고가 없고, 버전 업데이트는 마이크로소프트 스토어가 담당 (앱 자체 업데이트는 사용 안 함) 합니다. 자동 시작은 지원하지 않아 실행은 사용자가 합니다. 보안 정책이 엄격한 기관 PC에 권합니다.

**[Microsoft Store에서 받기 ↗](https://apps.microsoft.com/detail/9N2M027RBT7B)**

| 항목 | 설치형 | 무설치형(온라인) | 무설치형(오프라인) |
|---|---|---|---|
| 제공 | Microsoft Store | 공식 배포서버 | 공식 배포서버 |
| 설치 | 스토어에서 설치 | 불필요 | 불필요 |
| 법령 데이터 동봉 | ❌ (첫 실행 시 다운로드) | ❌ (첫 실행 시 다운로드) | ✅ (앱과 동봉) |
| 버전 업데이트 | 마이크로소프트 스토어가 담당 (앱 자체 업데이트는 사용 안 함) | 앱이 자동 업데이트 — 인터넷 차단 환경에서는 수동 | 앱이 자동 업데이트 — 인터넷 차단 환경에서는 수동 |
| 법령 최신화 | 자동 | 자동 — 인터넷 차단 환경에서는 수동 | 자동 — 인터넷 차단 환경에서는 수동 |
| PC 자동 시작 | 미지원 — 직접 실행 | 지원 — 기본갑 켜짐 | 지원 — 기본갑 켜짐 |
| 보안 경고 | 해당 없음 | 자동화 동작으로 백신·SmartScreen 경고가 뜰 수 있음 (악성코드 아님) | 자동화 동작으로 백신·SmartScreen 경고가 뜰 수 있음 (악성코드 아님) |

아래 ZIP 링크는 포터블(무설치) 배포판으로, 인터넷 연결 시 앱과 법령이 자동으로 갱신되고 인터넷이 차단된 폐쇄망에서는 수동으로 전달해 갱신합니다. 자동화 동작 때문에 백신·SmartScreen 경고가 나타날 수 있으나 악성코드가 아닙니다.

### 다운로드 — 항상 최신 버전 (고정 링크)

| 버전 | 파일 (최신 자동 갱신) |
|---|---|
| 온라인(앱만) | [ImmediatelyLaw-online.zip](https://gitlab.aigov.go.kr/irize/immediatelylaw/-/raw/downloads/ImmediatelyLaw-online-latest.zip) |
| 오프라인(앱+데이터) | [ImmediatelyLaw-offline.zip](https://gitlab.aigov.go.kr/irize/immediatelylaw/-/raw/downloads/ImmediatelyLaw-offline-latest.zip) |

zip을 받아 압축을 풉니다. 

`ImmediatelyLaw.exe`를 실행하면 트레이(오른쪽 아래)에 `법` 아이콘이 생성됩니다.

### 인터넷 사용 가능 PC (온라인)
1. `ImmediatelyLaw-online.zip` 다운로드 → 압축 해제 → `ImmediatelyLaw.exe` 실행
2. 첫 실행 시 법령 데이터(약 20MB)를 자동 다운로드합니다 (1회, 1분 이내)
3. 조문을 복사(Ctrl + C)하면 오른쪽 아래에 카드가 뜹니다

### 인터넷 사용 불가 PC (오프라인)
1. 다른 PC에서 `ImmediatelyLaw-offline.zip`(앱 + 데이터 동봉)을 받아 전달
2. 압축 해제 → `ImmediatelyLaw.exe` 실행 — 동봉된 데이터가 즉시 적용됩니다
3. 조문을 복사(Ctrl + C)하면 오른쪽 아래에 카드가 뜹니다
   - 이후 인터넷이 되는 날 자동으로 최신 법령을 확인합니다

### Windows의 PC 보호 (파란 경고창)
1. Windows의 PC 보호 : **Microsoft Defender SmartScreen에서 인식할 수 없는 앱의 시작을 차단했습니다. 이 앱을 실행하면 PC가 위험에 노출될 수 있습니다.** 라는 메시지가 발견되면, 추가정보 > **실행**을 클릭합니다.
2. 이 프로그램의 소스코드는 공개되어 있어 누구나 안전성을 검증할 수 있습니다.
3. 반드시 위 공식 링크(또는 배포 서버)에서 다운로드한 파일을 사용하세요. `app-latest.json`에 파일별 SHA-256이 게시되어 있어 무결성을 확인할 수 있습니다.

---

## 사용 방법

| 동작 | 방법 |
|---|---|
| 조문 표시 | `형법 제23조`, `「개인정보 보호법」 제13조`, `같은 법 제15조` 등 **복사만 하면 끝** |
| 법+시행령 함께 | `「도서관법」 제33조 및 같은 법 시행령 제19조` → 두 조문을 구분선으로 **이어서 표시** |
| 같은 법 맥락 | 이어서 `같은 법 시행령 제19조`, `같은 법 제5조`만 복사해도 **직전 조회한 법령** 기준으로 해석 |
| 헌법도 기본 법률 | `헌법 제11조`, `대한민국헌법 제31조` 모두 조회 — `헌법`은 **대한민국헌법**으로 자동 해석 |
| 직접 조회 | **Ctrl + Alt + L**(설정 > 일반에서 조합 변경 가능) 또는 트레이 클릭 → 입력 창에 `민법 750` 입력 |
| 재복사 | **[복사]** 버튼 → 조문 원문을 클립보드로 저장 |
| 글자 크기 | 좌하단 **[-] [+]** 버튼(장·절·본문 동일) |
| 법령정보센터 | **[법령정보센터 ↗]** 링크 클릭 → [www.law.go.kr](https://www.law.go.kr/) 이동 |
| 제작자 | 서초구청 홍성민 주무관 : **[제작자 ↗]** 링크 → 제작자 GitHub 페이지 이동 |
| 닫기 | 우상단 ✕ / (2초 이내) ESC 두 번 / 카드 바깥 클릭 / 자동 숨김(기본 30초, 설정에서 변경 가능) |

장·절 표기와 조문 본문은 맑은 고딕 같은 크기로 표시되며, 상태는 배지로 표시됩니다:

**현행** 초록 배지 = 법제처 현행 법령과 일치(실시간 온라인 검증)

**확인** 주황 배지 = 개정 여부 확인 필요(실시간 현행 법령과 로컬 조문 데이터 불일치)

**오프라인** 배지 = 네트워크 없이 로컬 데이터 기준

### 옵션 (트레이 우클릭 › 설정)
- **데이터**: 배포 주소(기본갑 내장 — 수정 불필요), 지금 업데이트 확인
- **자치법규**: 자치법규(hwp, hwpx, doc, pdf, txt, md 등) 파일 추가, 변경, 삭제
- **API 키**: [국가법령정보 공동활용](https://open.law.go.kr/LSO/main.do)에서 발급한
  OC 인증키 입력 시 **미보유 법령 즉시 수집 + 법제처 실시간 검증**이 추가됩니다.
  키는 Windows DPAPI로 암호화 저장되어 이 PC의 사용자만 열 수 있습니다. 없어도 전부 동작합니다.
- **오버레이**: 모드(시스템/라이트/다크), 카드 너비, 화면 위치(4곳), 글자 크기(pt 수치 지정),
  자동 숨김 시간, 현행 여부 실시간 검증
- **일반**: 단축키 사용, 클립보드 감시 일시정지, Windows 시작 시 실행(기본 갑), 새 버전 알림·자동 업데이트(기본 켬 — 새 릴리스가 나오면 안내 후 사용자가 동의할 때만 적용)
- **정보**: 제작자·연락처·소스 저장소·데이터 출처 안내

---

## 자치법규 지원

작업 표시줄 > 시스템 트레이 > 즉시로(우클릭) > 설정 > 자치법규 탭에서 조례, 규칙, 훈령 등의 추가 자료를 등록, 변경, 삭제 할 수 있습니다

조례·규칙 등 자치법규도 함께 찾고 싶다면 필요한 파일을
`%APPDATA%\immediatelylaw\data\regulations\` 폴더에 넣기만 하면 됩니다
(시작 시 자동 등록, 삭제 시 자동 정리).

- 지원 형식: `.hwpx` `.hwp` `.doc` `.docx` `.pdf` `.rtf` `.txt` `.md`
- 가장 간단한 형식 — 첫 줄에 조례명, 그 아래 `제N조(제목) …` 본문
  ```
  평창군 위원회 설립 및 지원 조례
  제1조(목적) 이 조례는 …의 설립 및 활동지원에 관한 사항을 규정함을 목적으로 한다.
  제2조(다른 법령과의 관계) …
  ```
- 법제처 국가법령정보센터에서 내려받은 `.hwp/.hwpx/.doc/.pdf` 파일도 그대로 인식됩니다
- 표시는 카드에 `[자치]` 배지로 구분됩니다

---

## 업데이트 원리

앱은 내장된 **공식 배포 서버**(기본갑 내장 — 설정에서 직접 운영 서버로 변경 가능)를
주기적으로(8시간 + 시작 시) 확인합니다. `manifest.json`의 `data_ver`가 로컬과 다르면
새 스냅샷(또는 델타)을 다운로드해 SHA-256 검증 후 적용합니다. 다운로드는 HTTPS로만
이루어지며 검증 실패 시 적용되지 않습니다. 모든 최신화는 자동화되어 있습니다.

배포 서버를 직접 운영(매일 최신화)하는 방법은
[배포 서버 운영 가이드](docs/DATA_REPO.md)를 참고하세요.

---

## 소스에서 실행 (개발자)

```
git clone https://github.com/irize87/immediatelylaw.git
cd ImmediatelyLaw
pip install PySide6 requests pypdf defusedxml
python run.py            # 창 없이 실행: pythonw run.py
```

- 패키징: `pyinstaller ImmediatelyLaw.spec` → `dist/ImmediatelyLaw/`
- 데이터 발행: `docs/DATA_REPO.md`
- 데이터 경로: 개발 중 `data/`, 설치본 `%APPDATA%\immediatelylaw\data\`
  (환경변수 `IMMEDIATELYLAW_DATA_DIR`로 변경 가능)
- 코드 구조: `immediatelylaw/` 앱 본체(watcher·overlay·resolver·db·workers…),
  `tools/` 데이터 수집·배포(publisher·daily_update_server)

## 의존 라이브러리 및 라이선스

이 프로그램이 사용하는 오픈소스 라이브러리와 라이선스입니다. (배지는 현재 릴리즈 동봉 버전)



| 라이브러리 | 동봉 버전 | 용도 | 라이선스 |
|---|---|---|---|
| Python | 3.15 (exe에 동봉) | 런타임 인터프리터 | PSF |
| PySide6 (Qt for Python) | 6.12.0 | GUI — 트레이, 오버레이 카드, 조회·설정 창 | LGPL-3.0 |
| requests | 2.34.2 | HTTPS 데이터 다운로드·법령 API 호출 | Apache-2.0 |
| pypdf | 6.21.3 | 자치법규 PDF 텍스트 추출 | BSD-3-Clause |
| defusedxml | 0.7.1 | HWPX/DOCX 등 XML 안전 파싱 | PSF |

- 프로그램 본체는 MIT 라이선스입니다.
- Qt(PySide6)는 LGPL이므로, 재링크가 가능한 onedir(폴더형 배포) 방식으로 배포하며
  본 저장소의 소스로 교체·재빌드가 가능합니다.

---

## 라이선스 및 데이터 고지

- **프로그램**: [MIT License](LICENSE) — 자유롭게 사용·복제·수정·재배포 가능
- **법령 데이터**: 국가법령정보센터(법제처·법령정보원) 공공누리 출처 표기 조건 무료 개방.
  법령의 효력 판정은 공식 원문이 기준이며, 즉시로의 표시는 참고용입니다.
- 이 프로그램의 모든 소스코드는 공개됩니다. 누구나 수정 및 재배포가 가능합니다. 
- 재배포시에는 반드시 원작자 정보를 함께 표시해주세요.
