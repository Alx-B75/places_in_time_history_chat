import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

DB_FILES = [
    DATA / "figures.db",
    DATA / "chat_history.db",
]

def inspect_db(path: Path) -> None:
    print("\n=== Inspecting:", path)
    if not path.exists():
        print("- Missing")
        return
    try:
        con = sqlite3.connect(str(path))
        cur = con.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        tables = [r[0] for r in cur.fetchall()]
        print(f"- Tables ({len(tables)}):", tables)
        for t in tables:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {t}")
                cnt = cur.fetchone()[0]
                print(f"  - {t}: {cnt} rows")
            except Exception as e:
                print(f"  - {t}: error -> {e}")
    except Exception as e:
        print("- Failed to inspect:", e)
    finally:
        try:
            con.close()
        except Exception:
            pass

if __name__ == "__main__":
    print("Project root:", ROOT)
    print("Data dir:", DATA)
    for db in DB_FILES:
        inspect_db(db)
