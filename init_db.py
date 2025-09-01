from sqlalchemy import select
from db import engine, get_session
from models import Base, User

def main():
    Base.metadata.create_all(bind=engine)
    # Optional: ensure a demo user exists
    with get_session() as s:
        demo = s.scalar(select(User).where(User.username == "demo"))
        if not demo:
            s.add(User(username="demo"))

if __name__ == "__main__":
    main()

