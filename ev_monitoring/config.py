from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "ev_monitoring.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

