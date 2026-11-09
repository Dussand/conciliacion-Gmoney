"""Punto de entrada de Streamlit Cloud (el archivo de inicio no se puede cambiar).
Ejecuta el diseño modular app.py. La versión anterior quedó en conciG_legacy.py.
Rollback: git revert de este commit."""
import runpy

runpy.run_path("app.py", run_name="__main__")
