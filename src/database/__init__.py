from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base
from pathlib import Path

# Database file path
DB_PATH = Path("db.sqlite")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Create engine
engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False
    },  # Needed for SQLite -> sqlite is thread sensitive
    echo=False,
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def init_db():
    Base.metadata.create_all(bind=engine)
    # migrate_schema()


def migrate_schema():
    inspector = inspect(engine)
    with engine.connect() as conn:
        # Check if notes table exists
        if "notes" in inspector.get_table_names():
            columns = [col["name"] for col in inspector.get_columns("notes")]

            # Add 'note' column if it doesn't exist
            if "note" not in columns:
                conn.execute(text("ALTER TABLE notes ADD COLUMN note TEXT"))
                conn.commit()
                print("Added 'note' column to notes table")

            # Add 'error' column if it doesn't exist
            if "error" not in columns:
                conn.execute(text("ALTER TABLE notes ADD COLUMN error TEXT"))
                conn.commit()
                print("Added 'error' column to notes table")


def get_db():
    """Dependency for getting database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
