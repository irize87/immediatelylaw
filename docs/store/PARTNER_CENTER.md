# Microsoft Store(Partner Center) 제출 가이드 — ImmediatelyLaw v1.6.0

## 0. 현재 상태 (로컬 검증 완료)
- `tools/make_msix.py`로 MSIX 생성·테스트 서명까지 확인
  - 산출물: `out/ImmediatelyLaw_1.6.0.0_x64.msix` (약 69.2MB, x64)
  - 개발 인증서(`CN=ImmediatelyLaw-Dev`, 비밀번호 `password`)로 서명,
    이 PC의 로컬 머신 신뢰 루트에 등록済み → `Add-AppxPackage` 설치·실행 성공
- 설치 위치가 `C:\Program Files\WindowsApps\...`로 바뀌면 앱이 자동으로
  스토어 모드를 감지한다(`immediatelylaw/buildflag.py`의 `IS_STORE`).
  스토어 모드에서 꺼지는 것:
  - zip 자기교체형 자체 update(스토어가 버전을 관리 — 정책상 필수)
  - HKCU Run 시작프로그램 등록(MSIX 경로는 갱신마다 바뀌어 무효)
- 스토어용 타일 자산과 매니페스트 원본: `storekit/`
  (1.5.7 MSIX에서 바이트 그대로 추출본. 한글 표시 이름 포함, 재타이핑 금지)

## 1. 최종 신원(identity) 확정 — 제출 전 유일한 외부 입력
파트너 센터에서 **제품 → 제품 옵션/앱 식별 정보(App identity)** 화면에
표시되는 값을 그대로 알려주면 아래 명령에 넣어 제출본을 만든다.

```
python -m tools.make_msix --name "<예약된 Name>" --publisher "<CN=...>" --no-sign
```
- `--no-sign`: 무서명 제출본. 스토어가 자체 서명(암호화)하므로 제출본은
  무서명이 표준이다. 서명본 제출도 접수되지만 무서명을 기본으로 한다.
- 파트너 센터가 예약 인증서(.cer/.pfx) 다운로드를 요구하면 `storekit/`에
  두지 말고 별도 경로에 두고 `--cert`로 지정한다(어차피 무서명이면 불요).
- 현재 기본값(개발 신원): Name=`ImmediatelyLaw`, Publisher=`CN=ImmediatelyLaw-Dev`
  → 이 신원 그대로도 제출은 가능하지만, 예약 값이 있으면 그에 맞춘다.

## 2. 제출 체크리스트 (파트너 센터 화면 순서)
1. **제품 만들기** — 앱(Windows 10 and 11) 선택, 제품 식별자 입력,
   상용/무료 선택(무료). 앱 이름: `즉시로 (ImmediatelyLaw)`
2. **제품 정보** — 한글/영문 짧은 설명·상세 설명(§3 초안 사용),
   categorized: 생산성(Productivity) / 유틸리티,
   화면 관리자 스크린샷 업로드: `docs/store/screenshots/01_light.png
   02_dark.png 03_gallery.png` (1920×1080)
3. **가격** — 무료
4. **사용 조건 / 개인정보 보호 URL** — `https://immediatelylaw.kro.kr/privacy.html`
   (이미 미러에 배포済み. 네트워크 통신 규격도 같은 페이지에 명기)
5. **검색 대상** — 키워드 초안: `법령`, `법률`, `조문`, `즉시법`, `law`,
   `Korean law`, `statute`
6. **등급(IARC)** — 인터넷 연결 유틸, 구매/채팅/폭력 없음 → 설문에 모두
   해당 없음으로 응답하면 전체이용가 예상
7. **공개 옵션** — 수동 공개로 두고 심사 통과 후 공개(첫 제출이면 권고)
8. **패키지** — §1의 무서명 MSIX 업로드. 인증(certificate) 탭에서
   `runFullTrust` 관련 고지를 요구하면 §4 문구 사용.

## 3. 목록 문구 초안
### 짧은 설명(5자 이하 아님 — 55자 이내)
- ko: `클립보드에 복사한 법령 인용을 즉시 보여주는 오프라인 법령·조문 사전`
- en: `Instant offline viewer for Korean statutes cited on your clipboard`

### 상세 설명
- ko:
  `즉시로(ImmediatelyLaw)는 다른 화면에서 복사한 「OO법 제12조」 같은 법령 인용을`
  `클립보드에서 읽어 조문 전문을 즉시 띄우는 경량 유틸리티입니다.`
  `법령 데이터는 설치 후 1회 내려받아 완전히 오프라인으로 동작하며,`
  `특정 사이트나 서버에 이용자가 노출되지 않습니다.`
  `라이트/다크 테마, 인용 이력, 법령 사본(규정) 열람 기능을 지원합니다.`
- en:
  `ImmediatelyLaw watches your clipboard for Korean statute citations such as`
  `"Article 12 of the Civil Act" and instantly shows the full text offline.`
  `The statute database is downloaded once and runs fully offline.`

### 릴리스 노트(v1.6.0)
- ko: `인용부호로 묶인 법령 인용 파싱 정확도 개선, 표기 교정, 안정성 개선.`
- en: `Better parsing of citations enclosed in quotes; text fixes; stability.`

## 4. `runFullTrust` 고지 문구(제출 시 영어)
`The app is a PyInstaller-packaged Win32 desktop utility (Tkinter UI). It uses
full trust to (1) register/unregister a per-user autostart entry in the desktop
build, and (2) replace its own program folder when applying an optional manual
update in the desktop build. In the Store package these two behaviors are
automatically disabled at runtime; the app otherwise only reads the clipboard
and writes its cache under %LOCALAPPDATA%.`

## 5. 참고 사항
- 스토어 빌드의 자체 update/HKCU Run 비활성은 런타임 경로 감지이며,
  코드 분기 빌드가 아니라 같은 바이트를 포장만 다르게 한다.
- 시작프로그램 등록은 스토어판에서 동작하지 않는다(Expansion 계약으로
  나중에 별도 처리 가능). 목록 설명에는 시작등록 기능을 명시하지 않는다.
- 심사 중 "패키지 식별자 불일치"가 뜨면 §1의 예약 값과 매니페스트가
  다른 것이니 `--name/--publisher`를 예약 값으로 교체해 재생성한다.
