Scout San José

Repositorio del proyecto web "Diario San José" (Flask + SQLite).

- Frontend: `scout/templates/index.html`
- Backend: `scout/app.py`

Instrucciones rápidas:

1. Crear entorno virtual e instalar dependencias:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Ejecutar la app:

```powershell
python scout/app.py
```

Persistencia actual: `localStorage` para comunicados (se añadió opción para persistir en perfil admin).
