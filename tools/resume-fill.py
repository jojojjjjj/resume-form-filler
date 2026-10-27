#!/usr/bin/env python3
"""Source-checkout entrypoint. Installation also provides this short command."""
from pathlib import Path
import runpy
import sys
scripts = Path(__file__).resolve().parents[1] / 'skills/resume-form-filler/scripts'
sys.path.insert(0, str(scripts))
runpy.run_path(str(scripts / 'run.py'), run_name='__main__')
