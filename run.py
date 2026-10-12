#!/usr/bin/env python3
"""
Cleanux - Executável de Inicialização Nativo para Linux.
Execute diretamente com: ./run.py  ou  python3 run.py
"""

import os
import sys

base_dir = os.path.dirname(os.path.abspath(__file__))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from cleanux.app import main

if __name__ == "__main__":
    sys.exit(main())
