# 사용자 규정집 확장 설계 검토 (2026-11-05)

기준: HEAD `2bb92cb` (A~E 오탐 차단 배포 후), pytest 71 passed.
검토 대상: 사용자 제시 "사용자 규정집 확장 설계 및 오탐 방지" 문서.

## 0. HWPX 등록 대화상자 조사 결과

- `settingsdlg.py` `LOCAL_FILTER`에 `*.hwpx`는 **v1.3.0(`cf4e2de`, 2026-10-29)부터 포함**되어 있고,
  태그 `v1.5.6`에도 존재. `scan_dir` 확장자·hwpx 파서도 지원.
- 즉 1.3.0 이상 빌드에서는 "자치법규 파일" 필터로 hwpx가 보여야 정상이며,
  안 보이면 (a) 실행 중인 빌드가 구버전 또는 (b) Windows 네이티브 대화상자 문제.
- 즉시 우회로: 파일을 `regulations` 폴더에 두면 시작 시 자동 등록됨.
- 후보 대응(승인 시): 필터를 확장자별로 분리 표기(`HWPX (*.hwpx;;HWP (*.hwp);;...`)하거나
  `DontUseNativeDialog` 대안 경로 추가.

## 1. 설계 항목 ↔ 현재 코드 대조

| 설계 항목 | 현재 | 판정 |
|---|---|---|
| 어미·후보 자동 학습을 전역 규칙에 즉시 반영 금지 | 런타임 학습 없음. 어미 추가는 코드+회귀테스트로만(수동 검토 체계) | 충족(정책 일치) |
| 식별 부분 없는 어미 전용 후보 자동확정 금지 | `GENERIC_TAILS` 필터 + tier4 길이게이트(2bb92cb) | 충족(방금 반영) |
| 정확일치 우선, 부분일치가 정확일치를 앞지르지 못함 | 후보별 사다리가 **후보 단위로 완주** — 짧은 후보의 4단계(포함)가 긴 후보의 정확일치보다 먼저 답을 낼 수 있음 | **갭 G3** |
| 본법/시행령 자동 덧붙여 확정 금지 | refparse가 문구에 없는데도 시행령/시행규칙 변형 후보를 생성, 전체 사다리(포함 단계 포함)에 참여 | 부분 · **G7** |
| 정확 문서인데 조문 없으면 다른 문서로 대체 금지 | 다음 후보(축약명)의 퍼지 매칭으로 다른 법령에 도달 가능 | **갭 G4 (위험)** |
| API 동일 정책, 불확실 시 미찾음 | `resolve_current` 마지막에 `rows[0]` 무조건 채택 → 남남 법령을 라이브 캐시까지 태움 | **갭 G2 (위험)** |
| 포함 LIKE % _ 이스케이프 | 3곳(db alias tier · contains tier · `local_search`) 미이스케이프 | **갭 G1** |
| 별칭 즉시 등록·삭제/교체 시 정리 | 사용자 별칭 입력 UI 없음. 로컬 등록 alias는 INSERT되나 **조회 경로가 전혀 없음**(`get_alias` 호출 0, tier3 JOIN은 law 표만). 교체 시 구버전 키도 방치 | **갭 G5** |
| 표제·기관·문서종류 추출 후 사용자 확인 | 첫 줄/파일명 자동 추후 사후 통보만 | 부분 · G8 |
| 기관·버전 중복 선택 UI / 메타 표시 | 없음(kind만 "자치법규") | 백로그 |
| 한 파일 다수 규정 분리 | 없음(1파일=1문서) | 백로그 |
| 짧지만 유효한 이름(2자) 보호 | tier4 게이트는 포함단계만; 정확일치는 무관. 테스트로 고정됨 | 충족 |
| 정규화 해시/trie 인덱스 | `replace(name,' ')` 조건으로 law 전체 스캔(호출당) | G9(저순위) |
| 매칭 근거 구조화 로그, 원본 비저장 | 자유로그(`immediatelylaw.log`)만 | G10(저순위) |
| 부분일치는 추천 전용, 팝업 확정 금지 | 부분일치도 팝업 정답으로 표시됨 | G6(제품 판단) |

## 2. 보완 제안

**P1 — 오탐 직결, 저위험 (권장 즉시)**
- G1 LIKE 와일드카드 이스케이프 + `ESCAPE` — `db.py` 3곳. 회귀: `_`·`%` 포함 문서명 케이스.
- G2 `lawapi.resolve_current`의 `rows[0]` 폴백 제거(정확/약칭 일치 없으면 None). 라이브 캐시 오염 원천 차단.
- G3 `resolver.resolve` 2단계화: 전 후보 정확 tier → 전 후보 부분 tier.
- G4 정확히 매칭된 문서에 조문이 없으면 이후 후보 진행 중단, `found=False + law_name/사유` 반환(카드는 "OOO에 제N조 없음" 안내).
- G5 자치법규 alias 실배선(정확조회에서 local 매칭) + 이름 교체 시 구키 삭제·삭제 시 전 키 정리.

**P2 — 동작 정책(제품 결정)**
- G6 부분일치 결과의 팝업 취급: G3+G4 도입 후에도 '낮은 신뢰' 배지 표기 vs 팝업 제외.
- G7 자동 변형(시행령/시행규칙) 후보는 정확 tier만 허용(auto 플래그).
- G8 등록 후 표제 확인·수정 대화상자, 이름 수정 시 alias 키 갱신 연동.

**P3 — 성능·운영**
- G9 `name_norm` 인덱스 열(빌더+온디맨드 캐시 유지)로 전체 스캔 제거.
- G10 매칭 근거 JSONL(후보·tier·mst만, 원문/클립보드 미저장, 로테이션).

**백로그(명시 보류 권장)**: 규정집 다중 분리, 기관·버전 선택 UI, 런타임 어미 학습 큐.

## 3. 필수 회귀 7종 ↔ 테스트 매핑

| 요구 | 상태 |
|---|---|
| FP1(gang-ryeong) 미대체 | 커버 `test_generic_fp_does_not_resolve` |
| FP2(un-yeong-gyu-jeong) 미대체 | 커버 동일 |
| 어미 전용 3종 자동확정 금지 | 커버 `test_generic_tail_not_offered_as_candidate`·tier4 게이트 |
| 긴 문장 내 인용 | 단독·따옴표만 커버, 긴 문장 변형 1건 추가 |
| 2자 유효명 차단 금지 | 커버(민법/형법/헌법) |
| 신규 사용자 규정 낯선 어미 조회/삭제 연동 | 미커버 → G5/G8 구현 시 추가 |
| 이름에 숫자·괄호·%·_ | 미커버 → G1과 함께 추가 |

## 4. 구현 기록 (2026-11-05, G1~G8 + HWPX)

- G1: `db.py` `_like_esc` + alias/포함/`local_search` LIKE `ESCAPE` 적용. 회귀 `test_g1_like_wildcards_are_literal`.
- G2: `lawapi.resolve_current`의 `rows[0]` 채택 제거(정확/약칭 아니면 None). 회귀 `test_g2_api_no_first_hit_fallback`.
- G3/G4: `resolver.resolve` 4단계 재작성 — 전 후보 정확 tier → 자치법규(alias 정확→제명 정확→포함) → 전국 포함 → 라이브.
  정확 제명인데 조문 없으면 `found=False, reason=law_no_article`로 종료(대체 금지). 회귀 `test_g4_no_article_never_substitutes`, `test_g3_g6_containment_last_and_low_conf`.
- G5: `localreg`을 `preview_file`/`commit_file`로 분리 — 제명 변경 시 구 alias 키 폐기, `scan_dir`/삭제 경로도 `law_id`별 alias 정리.
  자치법규 alias가 조회 경로(alias 정확→제명 정확→포함)에 실제 배선됨. 회귀 `test_g5_local_commit_rename_alias_lifecycle`.
- G6: 포함 단계 결과는 `low_conf=True` → 카드 배지 '확인' + 툴팁 '이름 일부 일치로 표시 — 실시간 확인 필요'. 팝업 노출은 유지(배지 강등 방식 채택).
- G7: `refparse`가 시행령/시행규칙 추론 변형을 `law_all`과 분리해 `law_auto`로 전달, resolver는 auto 후보를 포함 단계에서 제외.
  호출부(`app.py`, `workers.ResolveWorker`) 배선. 회귀 `test_g7_auto_variants_exact_only`.
- G8: 등록/교체 시 `preview_file` → '제목 확인' 입력상자(수정 가능, 취소 시 미등록) → `commit_file`. 자동 스캔(시작 시)은 무확인 유지.
- HWPX: 자치법규 파일 열기/교체 대화상자를 `DontUseNativeDialog`(Qt 자체 필터)로 전환 + 필터에 'HWPX (*.hwpx)' 전용 항목 추가.
  (v1.6.0 포터블에서 네이티브 셸이 결합 필터 내 *.hwpx를 노출하지 않음 — 사용자 환경 확인됨.)
- 검증: pytest 78 passed(신규 7), `_koval2` FAILS NONE, UI 신규 한글 전부 HEAD 실바이트 witness CLEAN,
  실 DB 원 재현 스크립트 FP 2건 미Resolve 유지 + 정탐(형법 제3조/운영규정) 정상.
- 백로그(미구개시 명시): 규정집 다중 분리, 기관·버전 선택 UI, `name_norm` 인덱스(정확 tier는 이미 expression 인덱스 사용 중이라 저순위),
  매칭 근거 JSONL 로그, 사용자 별칭 추가 UI.
