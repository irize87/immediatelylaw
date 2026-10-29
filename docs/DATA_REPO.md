# 데이터 저장소 운영 가이드 — immediatelylaw-data

사용자 앱이 법령 데이터를 내려받는 저장소
[github.com/nazgregory/immediatelylaw-data](https://github.com/nazgregory/immediatelylaw-data)
를 매일 최신 상태로 유지하는 방법입니다.
데이터를 발행할 PC(발행 PC)에는 이 소스와 Python, 그리고
[국가법령정보 공동활용](https://open.law.go.kr/LSO/main.do) **OC 인증키**가 필요합니다.

## 저장소 구조

- 브랜치 **`dist`** 한 개만 사용(고아 브랜치). 파일은 평면 배치:
  ```
  manifest.json                        ← 앱이 매일 읽는 버전/무결성 정보
  immediatelylaw-<버전>.db.xz          ← 전체 스냅샷(xz, 약 20MB)
  delta-<버전>.json.xz                 ← (선택) 개정분 델타
  ```
- 앱은 `https://raw.githubusercontent.com/nazgregory/immediatelylaw-data/dist/manifest.json`
  의 `data_ver`를 로컬과 비교해 다르면 스냅샷을 받고 SHA-256을 검증합니다.

## 매일의 갱신 사이클 (수동)

발행 PC에서 프로젝트 폴더에 PowerShell을 열고:

```powershell
$env:IMMEDIATELYLAW_OC='본인OC키'      # 설정에 저장해뒀으면 생략 가능
python -m tools.publisher update       # 개정·폐지 법령만 수집 (대개 수 분)
python -m tools.publisher package      # data/dist/에 새 스냅샷 + manifest 생성
python -m tools.push_dist --repo https://github.com/nazgregory/immediatelylaw-data.git `
    --msg "daily 2026-10-29"           # dist 브랜치에 push
```

- `update`는 법령 목록 재열거(약 1분) 후 마스터와 비교해 바뀐 법령만 다시 수집합니다.
  바뀐 게 0개면 스냅샷만 새로 올리고 끝납니다(버전만 갱신).
- `push_dist`는 `data/_distrepo`에 저장소를 클론해 두고 `data/dist` 내용을
  `dist` 브랜치에 미러링합니다. 첫 실행 시 자동 클론되므로 추가 설정이 필요 없습니다.
- git 인증이 처음이면 `gh auth login`(또는 PAT)으로 로그인해 두세요.

## 공식 데이터는 매일 자동 최신화 됩니다

공식 데이터베이스(https://github.com/nazgregory/immediatelylaw-data)는 매일 03시에 법령 변경 사항이 자동으로 최신화 됩니다

## PC 수동 최신화

PC에서 수동 발행도 그대로 가능합니다(설정에 OC 키 저장 시 불필요):

```powershell
$env:IMMEDIATELYLAW_OC = '본인OC키'
python -m tools.publisher update
python -m tools.publisher package
python -m tools.push_dist --repo https://github.com/nazgregory/immediatelylaw-data.git
```

수동 백업용 크론 예시(과거 방식):

PowerShell 스크립트를 만들고(`tools/daily_update.ps1` 예):

```powershell
Set-Location C:\path\to\ImmediatelyLaw
$env:IMMEDIATELYLAW_OC = '본인OC키'
python -m tools.publisher update  *>> data\daily.log
python -m tools.publisher package *>> data\daily.log
python -m tools.push_dist --repo https://github.com/nazgregory/immediatelylaw-data.git `
    --msg ("daily " + (Get-Date -Format s)) *>> data\daily.log
```

작업 스케줄러에서 매일 시각(예: 07:00)에 아래 명령을 실행하도록 등록합니다.
(사용자 로그인 상태에서 실행 — gh 인증은 사용자 계정에 저장되어 있습니다)

```
powershell -NoProfile -ExecutionPolicy Bypass -File C:\path\to\ImmediatelyLaw\tools\daily_update.ps1
```

한 번의 명령으로 등록하려면(관리자 불필요 — 로그인 상태 실행):

```powershell
$a = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument '-NoProfile -ExecutionPolicy Bypass -File C:\path\to\ImmediatelyLaw\tools\daily_update.ps1' `
    -WorkingDirectory 'C:\path\to\ImmediatelyLaw'
Register-ScheduledTask -TaskName 'ImmediatelyLaw-DailyUpdate' -Action $a `
    -Trigger (New-ScheduledTaskTrigger -Daily -At 3am) `
    -Settings (New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew)
```

## 초기 전체 수집 (재해복구·처음 구축)

```powershell
python -m tools.publisher build        # 전체 현행 법령 수집(재개 지원, 약 35분)
python -m tools.publisher package
python -m tools.push_dist --repo <데이터 저장소 URL> --msg "initial"
```

DB가 망가졌을 때도 동일합니다. 중간에 종료되면 같은 명령을 다시 실행하면 이어서 합니다.

## 오프라인 배포본 만들기

오프라인 환경 사용자에게 줄 zip은 **앱 폴더에 스냅샷을 동봉**하면 됩니다.
앱은 데이터가 비어 있으면 exe 옆의 `immediatelylaw-*.db.xz`를 찾아 네트워크 없이
복원합니다.

```powershell
Copy-Item data\dist\immediatelylaw-*.db.xz dist\ImmediatelyLaw\
Compress-Archive dist\ImmediatelyLaw\* ImmediatelyLaw-offline.zip
```

## 확인 명령

```powershell
python -m tools.publisher status       # DB 규모·버전·미완성/실패 건수
```

- `미완/실패 표시`가 0이 아니면 `python -m tools.publisher build`로 실패분 재시도.
- 앱이 정상 반영됐으려면 해당 PC 앱에서 8시간 대기하거나, 설정 › 데이터 ›
  [업데이트]를 눌러 "이미 최신" 문구를 확인합니다.
