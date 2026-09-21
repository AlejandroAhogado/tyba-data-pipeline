"""Configuracion común de las pruebas, para importar src/pipeline.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))