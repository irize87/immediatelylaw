# -*- coding: utf-8 -*-
"""즉시로 실행 진입점. (pythonw run.py 로 창 없이 실행)"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from immediatelylaw.app import main

if __name__ == "__main__":
    main()
