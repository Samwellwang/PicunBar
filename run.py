#!/usr/bin/env python3
import sys
from pathlib import Path

src_dir = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(src_dir))

from picun_menubar import main

if __name__ == "__main__":
    main()
