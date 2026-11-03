# -*- coding: utf-8 -*-
"""실행 중인 빌드의 종류를 런타임에 감지한다.

MSIX(Store) 버전은 실행 파일이 C:\\Program Files\\WindowsApps\\ 아래에
깔리므로 경로 판별로 안다. 빌드 플래그나 별도 분기 빌드가 필요 없고,
같은 소스에서 패키징 방식으로만 갈린다.

스토어 버전에서 끄는 것:
- zip 자기교체형 자체 업데이트(스토어가 버전을 관리한다 — 정책상 필수)
- HKCU Run 시작프로그램 등록(MSIX 실행 경로는 갱신마다 바뀌어 무효가 된다;
  시작 등록이 필요하면 MSIX 시작 작업 계약으로 나중에 별도 처리)
"""
import sys

IS_STORE = "\\windowsapps\\" in sys.executable.lower()
