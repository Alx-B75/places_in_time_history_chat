"""List users in the chat DB with basic activity stats.

Usage (PowerShell):
  python .\scripts\list_users.py

Optional env:
  CHAT_DB_PATH: override path to chat_history.db
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime

from sqlalchemy.orm import Session

from app.database import SessionLocal, Base
from app import models


def main() -> None:
    db: Session = SessionLocal()
    try:
        users = db.query(models.User).order_by(models.User.id.asc()).all()
        domains = Counter()
        admin_count = 0
        rows: list[tuple[int, str, str, int, int, int, str]] = []
        for u in users:
            username = u.username or ""
            domain = username.split("@", 1)[1] if "@" in username else ""
            if domain:
                domains[domain] += 1
            if (u.role or "").lower() == "admin":
                admin_count += 1
            thread_cnt = db.query(models.Thread).filter(models.Thread.user_id == u.id).count()
            chat_cnt = db.query(models.Chat).filter(models.Chat.user_id == u.id).count()
            fav_cnt = db.query(models.Favorite).filter(models.Favorite.user_id == u.id).count()
            last_chat = (
                db.query(models.Chat.timestamp)
                .filter(models.Chat.user_id == u.id)
                .order_by(models.Chat.timestamp.desc())
                .limit(1)
                .scalar()
            )
            last_chat_s = last_chat.isoformat(timespec="seconds") if last_chat else "-"
            rows.append((u.id, username, u.role, thread_cnt, chat_cnt, fav_cnt, last_chat_s))

        print(f"Users: {len(users)} (admins: {admin_count})")
        if domains:
            print("Top domains:")
            for dom, cnt in domains.most_common(10):
                print(f"  - {dom}: {cnt}")
        print("\nUser details (id | username | role | threads | chats | favorites | last_chat):")
        for r in rows:
            print(f"  {r[0]:>3} | {r[1]:<30} | {r[2]:<5} | {r[3]:>3} | {r[4]:>5} | {r[5]:>3} | {r[6]}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
