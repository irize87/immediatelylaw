# -*- coding: utf-8 -*-
"""즉시로 실행 진입점. (pythonw run.py 로 창 없이 실행)"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# requests보다 먼저. 묶인 실행 파일은 certifi 기본 경로가 비어 있을 수 있다.
from immediatelylaw.workers import ensure_ca_bundle

ensure_ca_bundle()

from immediatelylaw.app import main

if __name__ == "__main__":
    main()
