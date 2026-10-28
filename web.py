"""Arranca la bandeja desde cualquier carpeta: python web.py [--puerto 8765]."""
import sys

from ordena_poc.main import main

sys.exit(main(["web", *sys.argv[1:]]))
