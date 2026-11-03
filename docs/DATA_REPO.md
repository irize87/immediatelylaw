# 배포 서버 운영 가이드

사용자 앱이 법령 데이터와 설치 파일을 내려받는 **배포 서버**를 직접 운영하며
매일 최신 상태로 유지하는 방법입니다. 데이터를 발행할 서버(발행 서버)에는 이
소스와 Python, 그리고 [국가법령정보 공동활용](https://open.law.go.kr/LSO/main.do)
**OC 인증키**가 필요합니다.

소스 코드 공개 저장소(GitHub)는 코드 전용이며, 대용량 데이터·설치 파일은
git 저장소에 올리지 않습니다. 배포는 아래 배포 서버만 사용합니다.

## 배포 서버가 제공하는 파일(레이아웃)

HTTPS로 아래 폴더(예: `~/immediatelylaw-mirror`)를 그대로 공개하면 됩니다.

```
manifest.json                        ← 앱이 매일 읽는 버전/무결성 정보
immediatelylaw-<버전>.db.xz          ← 전체 스냅샷(xz, 약 30MB, 최신 1개만 유지)
delta-<버전>.json.xz                 ← 개정분 델타(최근 30개)
app-latest.json                      ← 프로그램 자체 업데이트 정보(sha256 포함)
ImmediatelyLaw-online-<버전>.zip     ← 설치 파일(온라인)
ImmediatelyLaw-offline-<버전>.zip    ← 설치 파일(오프라인, 데이터 동봉)
ImmediatelyLaw-{online,offline}-latest.zip ← 고정 별칭(README 링크용, 항상 최신)
index.html · capitol.jpg …           ← 랜딩 페이지
```

앱은 `https://<배포서버>/manifest.json`의 `data_ver`를 로컬과 비교해 다르면
스냅샷(또는 델타 체인)을 받고 SHA-256을 검증합니다. 자체서명 인증서를 쓰면
앱이 **인증서 DER SHA-256 고정(pinning)**으로 검증하므로 CA 등록이 필요 없고,
브라우저 접속 시에는 "자세히 → 계속" 안내면 됩니다(`tools/mirror_serve.py` 참고).

## 매일의 발행 사이클

### 자동(권장) — cron

발행 서버의 crontab에 한 줄이면 충분합니다.

```cron
CRON_TZ=Asia/Seoul
0 3 * * * $HOME/ImmediatelyLaw/tools/daily_update_server.sh
```

`tools/daily_update_server.sh`는 순서대로:
1. `tools.publisher update` — 개정·폐지 법령만 수집(바뀐 게 없으면 버전 유지 — 앱 트래픽 0)
2. `tools.publisher package` — `data/dist/`에 새 스냅샷·델타·manifest 생성
3. 전체 스냅샷은 최신 1개만 유지한 뒤, **배포 서버 폴더로 복사** — 그것으로 발행 끝

사전 준비: `$APP/.env`에 `export IMMEDIATELYLAW_OC=<OC키>`(chmod 600),
배포 서버 폴더를 HTTPS로 제공하는 서비스(systemd + `tools/mirror_serve.py`).

### 수동(테스트·복구)

발행 PC에서 프로젝트 폴더에 PowerShell(또는 서버에서 bash)로:

```powershell
$env:IMMEDIATELYLAW_OC='본인OC키'      # 설정에 저장해뒀으면 생략 가능
python -m tools.publisher update       # 개정·폐지 법령만 수집 (대개 수 분)
python -m tools.publisher package      # data/dist/에 새 스냅샷 + manifest 생성
```

그 다음 `data/dist/` 내용을 배포 서버 폴더에 복사(또는 scp)하면 발행됩니다.

## 초기 전체 수집 (재해복구·처음 구축)

```powershell
python -m tools.publisher build        # 전체 현행 법령 수집(재개 지원, 약 35분)
python -m tools.publisher package
```

DB가 망가졌을 때도 동일합니다. 중간에 종료되면 같은 명령을 다시 실행하면 이어서 합니다.
생성된 `data/dist/`를 배포 서버 폴더로 복사하면 새 배포 서버가 그대로 완성됩니다.

## 프로그램 릴리스 발행

새 버전을 만들면(README의 빌드 안내 참고):

```powershell
python -m tools.make_release --server ubuntu@<발행서버>
```

`app-latest.json`(버전·크기·SHA-256)과 설치 zip 2종을 생성해 발행 서버의
`data/dist/`로 scp하고, 이후 배포 서버 폴더 동기화로 사용자 앱에 반영됩니다.
앱의 자동 업데이트는 이 `app-latest.json`만 사용하며 SHA-256 검증을 요구합니다.

## 오프라인 배포본 만들기

오프라인 환경 사용자에게 줄 zip은 **앱 폴더에 스냅샷을 동봉**하면 됩니다.
앱은 데이터가 비어 있으면 exe 옆의 `immediatelylaw-*.db.xz`를 찾아 네트워크 없이
복원합니다. (`tools/make_release.py`가 이 작업을 자동화합니다.)

```powershell
Copy-Item data\dist\immediatelylaw-*.db.xz dist\ImmediatelyLaw\
Compress-Archive dist\ImmediatelyLaw\* ImmediatelyLaw-offline.zip
```

## 확인 명령

```powershell
python -m tools.publisher status       # DB 규모·버전·미완성/실패 건수
```

```bash
curl -k https://<배포서버>/manifest.json   # 발행된 판 확인
```

- `미완/실패 표시`가 0이 아니면 `python -m tools.publisher build`로 실패분 재시도.
- 앱이 정상 반영됐으려면 해당 PC 앱에서 8시간 대기하거나, 설정 › 데이터 ›
  [업데이트]를 눌러 "이미 최신" 문구를 확인합니다.
