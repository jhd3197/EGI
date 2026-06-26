"""HTTP layer for the EGI server. Each module exposes an APIRouter that the app
factory in main.py includes. Routers are thin: they parse the request and call
``modules/`` functions. Keep business logic out of here."""
