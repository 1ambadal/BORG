"""
This module provides database operations for the application.
"""

import psycopg2
import psycopg2.extras
import logging
import os
from datetime import datetime
import json
from typing import List, Dict, Any, Generator, Optional, Union
import re
from contextlib import contextmanager
from core.config import settings

logger = logging.getLogger(__name__)

QUANTITY_PATTERN = re.compile(r"^([\d\.]+)\s*(.*)$")


def get_db_connection():
    """Returns a database connection."""
    conn = psycopg2.connect(settings.DATABASE_URL)
    return conn


@contextmanager
def db_session() -> Generator[psycopg2.extensions.cursor, None, None]:
    """Provides a managed database cursor with automatic commit/rollback and closure."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        yield cursor
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database session error: {e}", exc_info=True)
        raise
    finally:
        cursor.close()
        conn.close()


def init_db():
    """Initializes the SQLite database and creates all necessary tables."""
    try:
        os.makedirs(settings.DB_DIR, exist_ok=True)

        conn = get_db_connection()
        cursor = conn.cursor()

        # Enable WAL mode for better concurrency and efficiency
        

        # --- Tables ---

        # Resume + Cover Letter
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS resume_entries (
                id SERIAL PRIMARY KEY,
                file_path TEXT,
                file_name TEXT,
                resume_text TEXT,
                cover_letter_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # To-dos
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS todos (
                id SERIAL PRIMARY KEY,
                task TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                date TEXT
            )
        """
        )

        # Bookmarks
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS bookmarks (
                id SERIAL PRIMARY KEY,
                url TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Topics (Learning Path)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS topics (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL UNIQUE,
                type TEXT DEFAULT 'main',
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Sub Topics (Learning Path)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sub_topics (
                id SERIAL PRIMARY KEY,
                topic_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                content_summary TEXT,
                examples TEXT,
                questions TEXT,
                metadata TEXT,
                status TEXT DEFAULT 'pending',
                order_index INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (topic_id) REFERENCES topics (id) ON DELETE CASCADE
            )
        """
        )

        # Missing Skills
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS missing_skills (
                id SERIAL PRIMARY KEY,
                skill TEXT NOT NULL UNIQUE,
                count INTEGER DEFAULT 1,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Facts
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS facts (
                id SERIAL PRIMARY KEY,
                fact_text TEXT NOT NULL UNIQUE,
                category TEXT DEFAULT 'general',
                hit_count INTEGER DEFAULT 0,
                last_used INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Workouts
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS workouts (
                id SERIAL PRIMARY KEY,
                exercise TEXT NOT NULL,
                sets INTEGER NOT NULL,
                reps INTEGER NOT NULL,
                weight REAL NOT NULL,
                date TEXT NOT NULL
            )
        """
        )

        # Master Exercise Data
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS workout_master (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Messages (Chat History)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                thread_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                tool_calls TEXT,
                tool_call_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Finance Categories
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS finance_categories (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                type TEXT DEFAULT 'expense',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(name)
            )
        """
        )

        # Finance Transactions
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS finance_transactions (
                id SERIAL PRIMARY KEY,
                amount REAL NOT NULL,
                category_id INTEGER NOT NULL,
                description TEXT,
                date_logged TEXT DEFAULT CURRENT_DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES finance_categories (id) ON DELETE CASCADE
            )
        """
        )

        # Nutrition Targets
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_nutrition_targets (
                id INTEGER PRIMARY KEY DEFAULT 1,
                calories INTEGER DEFAULT 1985,
                protein REAL DEFAULT 150.0,
                carbs REAL DEFAULT 200.0,
                fat REAL DEFAULT 65.0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Food Logs
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS food_logs (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                quantity TEXT,
                calories INTEGER DEFAULT 0,
                protein REAL DEFAULT 0.0,
                carbs REAL DEFAULT 0.0,
                fat REAL DEFAULT 0.0,
                fiber REAL DEFAULT 0.0,
                sugar REAL DEFAULT 0.0,
                diet_type TEXT,
                date_logged TEXT DEFAULT CURRENT_DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Job Applications
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS job_applications (
                id SERIAL PRIMARY KEY,
                company TEXT NOT NULL,
                position TEXT NOT NULL,
                email TEXT,
                status TEXT DEFAULT 'Pending',
                notes TEXT,
                url TEXT,
                date_applied TEXT DEFAULT CURRENT_DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )


        # Scraped Jobs
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS scraped_jobs (
                id SERIAL PRIMARY KEY,
                title TEXT,
                company TEXT,
                location TEXT,
                date_posted TEXT,
                url TEXT UNIQUE,
                status TEXT DEFAULT 'new'
            )
        """
        )

        # LLM Usage
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_usage (
                id SERIAL PRIMARY KEY,
                model TEXT,
                input_tokens INTEGER,
                output_tokens INTEGER,
                total_tokens INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Brain Dumps
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS brain_dumps (
                id SERIAL PRIMARY KEY,
                title TEXT,
                content TEXT NOT NULL,
                category TEXT DEFAULT 'Note',
                tags TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # User Settings
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """
        )

        # --- Indexes ---
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_todos_task ON todos(task)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_sub_topics_topic_id ON sub_topics(topic_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_food_logs_date ON food_logs(date_logged)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_finance_trans_date ON finance_transactions(date_logged)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_history ON messages(thread_id, created_at DESC)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_job_apps_status ON job_applications(status)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_facts_ranking ON facts(hit_count DESC, last_used DESC, created_at DESC)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_brain_dumps_cat ON brain_dumps(category)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_scraped_jobs_url ON scraped_jobs(url)"
        )


        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_scraped_jobs_status ON scraped_jobs(status)"
        )

        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")


# --- Message Persistence (Decoupled History) ---


def save_message(
    thread_id: str,
    role: str,
    content: str,
    tool_calls: Optional[str] = None,
    tool_call_id: Optional[str] = None,
):
    """Persists a single message to the database."""
    try:
        with db_session() as cursor:
            cursor.execute(
                """
                INSERT INTO messages (thread_id, role, content, tool_calls, tool_call_id)
                VALUES (%s, %s, %s, %s, %s)
            """,
                (thread_id, role, content, tool_calls, tool_call_id),
            )
    except Exception as e:
        logger.error(f"Failed to save message: {e}")


def get_recent_messages(thread_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Retrieves the most recent messages for a thread context."""
    try:
        with db_session() as cursor:
            cursor.execute(
                """
                SELECT * FROM (
                    SELECT * FROM messages 
                    WHERE thread_id = %s 
                    ORDER BY created_at DESC 
                    LIMIT %s
                ) ORDER BY created_at ASC
            """,
                (thread_id, limit),
            )
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Failed to get recent messages: {e}")
        return []


def delete_checkpoint_data(thread_id: str):
    """Deletes LangGraph checkpoints for a specific thread."""
    try:
        with db_session() as cursor:
            cursor.execute("DELETE FROM checkpoints WHERE thread_id = %s", (thread_id,))
            cursor.execute("DELETE FROM checkpoint_writes WHERE thread_id = %s", (thread_id,))
            cursor.execute("DELETE FROM checkpoint_blobs WHERE thread_id = %s", (thread_id,))
        logger.info(f"Checkpoints cleared for thread {thread_id}")
    except Exception as e:
        logger.error(f"Failed to delete checkpoints for thread {thread_id}: {e}")


# --- Fact DB ---


# Filler and stop words to strip when performing semantic similarity comparison on facts
FACT_STOP_WORDS = {
    "the",
    "a",
    "an",
    "is",
    "are",
    "was",
    "were",
    "to",
    "for",
    "of",
    "in",
    "on",
    "at",
    "by",
    "user",
    "hopes",
    "hope",
    "wants",
    "want",
    "actively",
    "i",
    "my",
    "me",
    "with",
    "and",
    "about",
    "prefers",
    "prefer",
    "likes",
    "like",
    "it",
}


def _clean_and_tokenize_fact(text: str) -> set[str]:
    """Normalizes and extracts a set of key terms from a fact string."""
    return {w for w in re.findall(r"\b\w+\b", text.lower()) if w not in FACT_STOP_WORDS}


def add_user_facts(facts: Union[str, List[str]], category: str = "general") -> bool:
    """Persists user facts to the database, skipping semantic duplicates."""
    try:
        fact_list = [facts] if isinstance(facts, str) else facts
        existing_facts = get_user_facts(limit=100)

        # Pre-tokenize existing facts to avoid O(N * M) redundant string parsing
        existing_tokens = [
            _clean_and_tokenize_fact(f["fact_text"]) for f in existing_facts
        ]

        with db_session() as cursor:
            for fact in fact_list:
                cleaned = fact.strip() if fact else ""
                if not cleaned:
                    continue

                new_tokens = _clean_and_tokenize_fact(cleaned)
                if not new_tokens or any(
                    (len(new_tokens & orig) / len(new_tokens | orig) >= 0.7)
                    or (
                        len(new_tokens & orig) / min(len(new_tokens), len(orig)) >= 0.85
                    )
                    for orig in existing_tokens
                    if orig
                ):
                    logger.info("Skipping duplicate fact: '%s'", cleaned)
                    continue

                cursor.execute(
                    """
                    INSERT INTO facts (fact_text, category)
                    VALUES (%s, %s) ON CONFLICT (fact_text) DO NOTHING
                """,
                    (cleaned, category),
                )

                # Append to current memory block to handle intra-batch duplicates
                existing_tokens.append(new_tokens)

        return True
    except Exception as e:
        logger.error("Failed to add facts: %s", e, exc_info=True)
        return False


def get_user_facts(
    query: Optional[str] = None, limit: int = 15
) -> List[Dict[str, Any]]:
    """Retrieves top stored facts for a user based on frequency and recency."""
    try:
        if query and not isinstance(query, str):
            query = str(query)

        with db_session() as cursor:
            if query:
                cursor.execute(
                    """
                    SELECT * FROM facts 
                    WHERE fact_text LIKE %s
                    ORDER BY hit_count DESC, last_used DESC, created_at DESC
                    LIMIT %s
                """,
                    (f"%{query.strip()}%", limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM facts 
                    ORDER BY hit_count DESC, last_used DESC, created_at DESC
                    LIMIT %s
                """,
                    (limit,),
                )

            facts = [dict(row) for row in cursor.fetchall()]
            return facts
    except Exception as e:
        logger.error("Failed to get facts: %s", e)
        return []


def update_fact_stats(fact_ids: List[int]):
    """Updates hit_count and last_used for specified facts (Background usage)."""
    if not fact_ids:
        return
    try:
        with db_session() as cursor:
            now_ts = int(datetime.now().timestamp())
            cursor.execute(
                f"""
                UPDATE facts 
                SET hit_count = hit_count + 1, last_used = %s
                WHERE id IN ({','.join(['%s']*len(fact_ids))})
            """,
                (now_ts, *fact_ids),
            )
    except Exception as e:
        logger.error("Failed to update fact stats: %s", e)


def delete_fact(fact_id: int) -> bool:
    """Deletes a specific user fact."""
    try:
        with db_session() as cursor:
            cursor.execute("DELETE FROM facts WHERE id = %s", (fact_id,))
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to delete fact: {e}")
        return False


# --- Food Tracker ---


def merge_quantities(q1, q2) -> str:
    """Merges two quantity strings by parsing and summing their numeric components if units match."""
    if not q1:
        return str(q2) if q2 else ""
    if not q2:
        return str(q1)

    q1_clean = str(q1).strip()
    q2_clean = str(q2).strip()

    m1 = QUANTITY_PATTERN.match(q1_clean)
    m2 = QUANTITY_PATTERN.match(q2_clean)

    if m1 and m2:
        try:
            val1 = float(m1.group(1))
            unit1 = m1.group(2).strip().lower()
            val2 = float(m2.group(1))
            unit2 = m2.group(2).strip().lower()

            # Merge if the units are identical
            if unit1 == unit2:
                total = val1 + val2
                total_str = str(int(total)) if total.is_integer() else f"{total:.1f}"
                # Keep the casing of the first unit
                orig_unit = m1.group(2).strip()
                return f"{total_str} {orig_unit}".strip()
        except ValueError:
            pass

    return f"{q1_clean} + {q2_clean}"


def add_food_log(item: Dict[str, Any], date_logged: Optional[str] = None) -> int:
    """Adds or aggregates a food log entry if the food already exists for today."""
    try:
        with db_session() as cursor:
            # Use provided date or fallback to today
            log_date = date_logged or datetime.now().strftime("%d-%m-%Y")
            food_name = item.get("name", "Unknown Food").strip().lower()

            # Check if this exact canonical food has already been logged today
            cursor.execute(
                """
                SELECT id, quantity, calories, protein, carbs, fat, fiber, sugar 
                FROM food_logs 
                WHERE date_logged = %s AND lower(name) = %s
                """,
                (log_date, food_name),
            )
            existing = cursor.fetchone()

            if existing:
                # Aggregate existing values
                existing_id = existing["id"]
                ext_qty = existing["quantity"]
                ext_cal = existing["calories"]
                ext_pro = existing["protein"]
                ext_carb = existing["carbs"]
                ext_fat = existing["fat"]
                ext_fib = existing["fiber"]
                ext_sug = existing["sugar"]

                new_qty = merge_quantities(ext_qty, item.get("quantity"))
                new_cal = (ext_cal or 0) + int(item.get("calories", 0) or 0)
                new_pro = (ext_pro or 0.0) + float(item.get("protein", 0.0) or 0.0)
                new_carb = (ext_carb or 0.0) + float(item.get("carbs", 0.0) or 0.0)
                new_fat = (ext_fat or 0.0) + float(item.get("fat", 0.0) or 0.0)
                new_fib = (ext_fib or 0.0) + float(item.get("fiber", 0.0) or 0.0)
                new_sug = (ext_sug or 0.0) + float(item.get("sugar", 0.0) or 0.0)

                cursor.execute(
                    """
                    UPDATE food_logs 
                    SET quantity = %s, calories = %s, protein = %s, carbs = %s, fat = %s, fiber = %s, sugar = %s
                    WHERE id = %s
                    """,
                    (
                        new_qty,
                        new_cal,
                        new_pro,
                        new_carb,
                        new_fat,
                        new_fib,
                        new_sug,
                        existing_id,
                    ),
                )
                return existing_id

            cursor.execute(
                """
                INSERT INTO food_logs 
                (name, quantity, calories, protein, carbs, fat, fiber, sugar, diet_type, date_logged)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """,
                (
                    food_name,
                    item.get("quantity"),
                    item.get("calories", 0),
                    item.get("protein", 0.0),
                    item.get("carbs", 0.0),
                    item.get("fat", 0.0),
                    item.get("fiber", 0.0),
                    item.get("sugar", 0.0),
                    item.get("diet_type"),
                    log_date,
                ),
            )
            return cursor.fetchone()[0]
    except Exception as e:
        logger.error(f"Failed to add food log: {e}")
        return -1


def get_food_logs_by_date(date: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves all food logs for a specific date."""
    date = date or datetime.now().strftime("%d-%m-%Y")
    try:
        with db_session() as cursor:
            cursor.execute(
                """
                SELECT * FROM food_logs 
                WHERE date_logged = %s
                ORDER BY created_at ASC
            """,
                (date,),
            )
            return [dict(r) for r in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Failed to get food logs: {e}")
        return []


def delete_food_log(log_id: int) -> bool:
    """Deletes a specific food log entry."""
    try:
        with db_session() as cursor:
            cursor.execute("DELETE FROM food_logs WHERE id = %s", (log_id,))
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to delete food log: {e}")
        return False


def update_food_log(log_id: int, updates: Dict[str, Any]) -> bool:
    """Updates selected fields of a food log entry."""
    try:
        allowed_fields = ["name", "quantity", "calories", "protein", "carbs", "fat"]
        set_clauses = []
        params = []

        for field in allowed_fields:
            if field in updates:
                set_clauses.append(f"{field} = %s")
                params.append(updates[field])

        if not set_clauses:
            return False

        params.append(log_id)
        query = f"UPDATE food_logs SET {', '.join(set_clauses)} WHERE id = %s"

        with db_session() as cursor:
            cursor.execute(query, tuple(params))
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to update food log: {e}")
        return False


def set_user_nutrition_targets(targets: Dict[str, Any]) -> bool:
    """Sets or updates nutritional targets using UPSERT."""
    try:
        with db_session() as cursor:
            cursor.execute(
                """
                INSERT INTO user_nutrition_targets (id, calories, protein, carbs, fat)
                VALUES (1, %s, %s, %s, %s)
                ON CONFLICT(id) DO UPDATE SET
                    calories = excluded.calories,
                    protein = excluded.protein,
                    carbs = excluded.carbs,
                    fat = excluded.fat,
                    updated_at = CURRENT_TIMESTAMP
            """,
                (
                    targets.get("calories", 1985),
                    targets.get("protein", 150.0),
                    targets.get("carbs", 200.0),
                    targets.get("fat", 65.0),
                ),
            )
            return True
    except Exception as e:
        logger.error(f"Failed to set user nutrition targets: {e}")
        return False


def get_user_nutrition_targets() -> Dict[str, Any]:
    """Retrieves nutritional targets, returning defaults if not found."""
    try:
        with db_session() as cursor:
            cursor.execute("SELECT * FROM user_nutrition_targets LIMIT 1")
            row = cursor.fetchone()
            if row:
                return dict(row)
    except Exception as e:
        logger.error(f"Failed to get user nutrition targets: {e}")

    return {"calories": 1985, "protein": 150.0, "carbs": 200.0, "fat": 65.0}


# -----delete all data---------


def delete_user_custom_data():
    """Deletes all data associated with a user from the database (System-wide)."""
    try:
        with db_session() as cursor:
            # Note: IDs are ignored as this is now a single-user system
            cursor.execute("DELETE FROM resume_entries")
            cursor.execute("DELETE FROM todos")
            cursor.execute("DELETE FROM bookmarks")
            cursor.execute("DELETE FROM topics")
            cursor.execute("DELETE FROM sub_topics")
            cursor.execute("DELETE FROM food_logs")
            cursor.execute("DELETE FROM user_nutrition_targets")
            cursor.execute("DELETE FROM finance_transactions")
            cursor.execute("DELETE FROM finance_categories")
            cursor.execute("DELETE FROM missing_skills")
            cursor.execute("DELETE FROM facts")
            cursor.execute("DELETE FROM llm_usage")
            cursor.execute("DELETE FROM brain_dumps")
            cursor.execute("DELETE FROM workouts")
            cursor.execute("DELETE FROM job_applications")
            cursor.execute("DELETE FROM scraped_jobs")
            cursor.execute("DELETE FROM messages")
            logger.info("All user-specific table data cleared.")

    except Exception as e:
        logger.error(f"Failed to delete user data: {e}")


def delete_all_checkpoints():
    """Deletes all LangGraph checkpoints for all threads."""
    try:
        with db_session() as cursor:
            cursor.execute("DELETE FROM checkpoints")
            cursor.execute("DELETE FROM checkpoint_blobs")
            cursor.execute("DELETE FROM checkpoint_writes")
        logger.info("All checkpoints cleared.")
    except Exception as e:
        logger.error(f"Failed to delete all checkpoints: {e}")


# --- Workouts ---


def add_workout_entry(
    exercise: str, sets: int, reps: int, weight: float, date: str
) -> int:
    """Adds a workout entry to the database."""
    with db_session() as cursor:
        cursor.execute(
            """
            INSERT INTO workouts (exercise, sets, reps, weight, date)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """,
            (exercise, sets, reps, weight, date),
        )
        return cursor.fetchone()[0]


def add_workout_entries(entries: List[Dict[str, Any]]) -> int:
    """Adds multiple workout entries efficiently."""
    if not entries:
        return 0
    try:
        with db_session() as cursor:
            data = [
                (
                    e["exercise"],
                    e["sets"],
                    e["reps"],
                    e["weight"],
                    e["date"],
                )
                for e in entries
            ]
            cursor.executemany(
                """
                INSERT INTO workouts (exercise, sets, reps, weight, date)
                VALUES (%s, %s, %s, %s, %s)
            """,
                data,
            )
            return cursor.rowcount
    except Exception as e:
        logger.error(f"Failed to bulk add workouts: {e}")
        return -1


def get_workouts(date: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves workout entries, optionally filtered by date."""
    with db_session() as cursor:
        if date:
            cursor.execute(
                "SELECT * FROM workouts WHERE date = %s ORDER BY id DESC", (date,)
            )
        else:
            cursor.execute("SELECT * FROM workouts ORDER BY id DESC")
        return [dict(row) for row in cursor.fetchall()]


def get_unique_exercises() -> List[str]:
    """Retrieves a list of all unique exercise names from the master table."""
    with db_session() as cursor:
        cursor.execute("SELECT name FROM workout_master ORDER BY name ASC")
        return [row[0] for row in cursor.fetchall()]


def delete_workout_entry(entry_id: int) -> bool:
    """Deletes a workout entry."""
    with db_session() as cursor:
        cursor.execute("DELETE FROM workouts WHERE id = %s", (entry_id,))
        return cursor.rowcount > 0


def ensure_exercise_in_master(name: str):
    """Ensures an exercise exists in the master table."""
    name = name.strip().title()
    with db_session() as cursor:
        cursor.execute(
            "INSERT INTO workout_master (name) VALUES (%s) ON CONFLICT (name) DO NOTHING", (name,)
        )


def add_todo_entry(task: str, date: Optional[str] = None) -> int:
    """Adds a new todo entry."""
    try:
        if not date:
            date = datetime.now().strftime("%d-%m-%Y")
        with db_session() as cursor:
            cursor.execute(
                "INSERT INTO todos (task, date) VALUES (%s, %s) RETURNING id",
                (task, date),
            )
            return cursor.fetchone()[0]
    except Exception as e:
        logger.error(f"Failed to add todo entry: {e}")
        return -1


def get_user_todos(
    start_date: Optional[int] = None, end_date: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Retrieves todos with optional date range filtering (YYYY-MM-DD strings)."""
    query = "SELECT * FROM todos WHERE 1=1"
    params = []

    if start_date is not None and end_date is not None:
        query += " AND date BETWEEN %s AND %s"
        params.extend([start_date, end_date])
    elif start_date is not None:
        query += " AND date >= %s"
        params.append(start_date)

    query += " ORDER BY COALESCE(substr(date, 7, 4) || '-' || substr(date, 4, 2) || '-' || substr(date, 1, 2), '9999-12-31') ASC, id ASC"

    with db_session() as cursor:
        cursor.execute(query, tuple(params))
        return [dict(row) for row in cursor.fetchall()]


def update_todo_entry(
    todo_id: Optional[int] = None,
    target_date: Optional[str] = None,
    task: Optional[str] = None,
    status: Optional[str] = None,
    date: Optional[str] = None,
) -> bool:
    """Updates a todo entry by ID or all entries for a given date."""
    if not todo_id and not target_date:
        return False

    if isinstance(date, int):
        date = datetime.fromtimestamp(date).strftime("%d-%m-%Y")

    fields = {"task": task, "status": status, "date": date}
    updates = {k: v for k, v in fields.items() if v is not None}

    if not updates:
        return False

    set_clause = ", ".join(f"{k} = %s" for k in updates.keys())
    params = list(updates.values())

    if todo_id:
        sql = f"UPDATE todos SET {set_clause} WHERE id = %s"
        params.append(todo_id)
    else:
        sql = f"UPDATE todos SET {set_clause} WHERE date = %s"
        params.append(target_date)

    with db_session() as cursor:
        cursor.execute(sql, params)
        return cursor.rowcount > 0

    return False


def delete_todo_entry(
    todo_id: Optional[int] = None, date: Optional[str] = None
) -> bool:
    """Deletes a todo entry by ID or all entries for a given date string."""
    with db_session() as cursor:
        if todo_id:
            cursor.execute("DELETE FROM todos WHERE id = %s", (todo_id,))
        elif date:
            cursor.execute("DELETE FROM todos WHERE date = %s", (date,))
        else:
            return False
        return cursor.rowcount > 0

    return False


# -----Bookmarks-----


def add_bookmark_entry(url: str) -> int:
    """Adds a new bookmark."""
    try:
        with db_session() as cursor:
            cursor.execute(
                """
                INSERT INTO bookmarks (url)
                VALUES (%s)
                RETURNING id
            """,
                (url,),
            )
            return cursor.fetchone()[0]
    except Exception as e:
        logger.error(f"Failed to add bookmark: {e}")
        return -1


def get_user_bookmarks() -> List[Dict[str, Any]]:
    """Retrieves all bookmarks."""
    try:
        with db_session() as cursor:
            cursor.execute("SELECT * FROM bookmarks ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Failed to get bookmarks: {e}")
        return []


def delete_bookmark_entry(bookmark_id: int) -> bool:
    """Deletes a specific bookmark entry."""
    try:
        with db_session() as cursor:
            cursor.execute(
                "DELETE FROM bookmarks WHERE id = %s",
                (bookmark_id,),
            )
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to delete bookmark: {e}")
        return False


# --- Learning Paths ---


def add_topic(title: str, topic_type: str = "main") -> int:
    """Adds a new learning topic."""
    try:
        with db_session() as cursor:
            cursor.execute(
                "INSERT INTO topics (title, type) VALUES (%s, %s) RETURNING id", (title, topic_type)
            )
            return cursor.fetchone()[0]
    except Exception as e:
        logger.error(f"Failed to add topic: {e}")
        return -1


def add_sub_topics(topic_id: int, sub_topics: List[Dict[str, Any]]) -> bool:
    """Adds multiple sub-topics/lessons to a parent topic."""
    try:
        with db_session() as cursor:
            for idx, st in enumerate(sub_topics):
                questions_json = json.dumps(st.get("questions", []))
                examples_json = json.dumps(st.get("examples", []))
                metadata_json = json.dumps(st.get("metadata", {}))
                cursor.execute(
                    """
                    INSERT INTO sub_topics (topic_id, title, content_summary, examples, questions, metadata, order_index)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                    (
                        topic_id,
                        st["title"],
                        st["content_summary"],
                        examples_json,
                        questions_json,
                        metadata_json,
                        idx,
                    ),
                )
            return True
    except Exception as e:
        logger.error(f"Failed to add sub-topics: {e}")
        return False


def get_topics(status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves all topics with lesson completion counts using an optimized JOIN."""
    try:
        query = """
            SELECT t.*, 
                   COUNT(st.id) as total_lessons,
                   SUM(CASE WHEN st.status = 'completed' THEN 1 ELSE 0 END) as completed_lessons
            FROM topics t
            LEFT JOIN sub_topics st ON t.id = st.topic_id
            WHERE 1=1
        """
        params = []

        if status:
            query += " AND t.status = %s"
            params.append(status)

        query += " GROUP BY t.id ORDER BY t.created_at DESC"

        with db_session() as cursor:
            cursor.execute(query, tuple(params))
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Failed to get topics: {e}")
        return []


def get_topic_by_id(topic_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves a single topic by ID."""
    try:
        with db_session() as cursor:
            cursor.execute("SELECT * FROM topics WHERE id = %s", (topic_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Failed to get topic by id: {e}")
        return None


def get_sub_topics(topic_id: int) -> List[Dict[str, Any]]:
    """Retrieves all sub-topics (lessons) for a specific topic ID."""
    try:
        with db_session() as cursor:
            cursor.execute(
                "SELECT * FROM sub_topics WHERE topic_id = %s ORDER BY order_index ASC",
                (topic_id,),
            )
            rows = cursor.fetchall()

        res = []
        for row in rows:
            d = dict(row)
            try:
                d["questions"] = (
                    json.loads(d["questions"]) if d.get("questions") else []
                )
                d["examples"] = json.loads(d["examples"]) if d.get("examples") else []
            except (json.JSONDecodeError, TypeError):
                d["questions"] = d.get("questions", [])
                d["examples"] = d.get("examples", [])
            res.append(d)
        return res
    except Exception as e:
        logger.error(f"Failed to get sub-topics: {e}")
        return []


def update_sub_topic_status(sub_topic_id: int, status: str) -> bool:
    """Updates a lesson status and automatically marks topic as completed if all lessons are done."""
    try:
        with db_session() as cursor:
            cursor.execute(
                "UPDATE sub_topics SET status = %s WHERE id = %s", (status, sub_topic_id)
            )

            if status == "completed":
                # Check if all sub-topics for this topic are now completed
                cursor.execute(
                    "SELECT topic_id FROM sub_topics WHERE id = %s", (sub_topic_id,)
                )
                topic_row = cursor.fetchone()
                if topic_row:
                    topic_id = topic_row[0]
                    cursor.execute(
                        "SELECT COUNT(*) FROM sub_topics WHERE topic_id = %s AND status != 'completed'",
                        (topic_id,),
                    )
                    pending_count = cursor.fetchone()[0]
                    if pending_count == 0:
                        cursor.execute(
                            "UPDATE topics SET status = 'completed' WHERE id = %s",
                            (topic_id,),
                        )
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to update sub-topic status: {e}")
        return False


def update_topic_status(topic_id: int, status: str) -> bool:
    """Updates the overall status of a learning topic."""
    try:
        with db_session() as cursor:
            cursor.execute(
                "UPDATE topics SET status = %s WHERE id = %s", (status, topic_id)
            )
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to update topic status: {e}")
        return False


def get_next_pending_sub_topic() -> Optional[Dict[str, Any]]:
    """Retrieves the next uncompleted lesson from the oldest active learning topic."""
    try:
        with db_session() as cursor:
            # Find the first active topic
            cursor.execute(
                "SELECT id FROM topics WHERE status = 'active' ORDER BY created_at ASC LIMIT 1"
            )
            topic_row = cursor.fetchone()
            if not topic_row:
                return None

            topic_id = topic_row["id"]
            # Find the first pending sub-topic
            cursor.execute(
                "SELECT * FROM sub_topics WHERE topic_id = %s AND status = 'pending' ORDER BY order_index ASC LIMIT 1",
                (topic_id,),
            )
            sub_row = cursor.fetchone()

            if sub_row:
                d = dict(sub_row)
                try:
                    d["questions"] = (
                        json.loads(d["questions"]) if d["questions"] else []
                    )
                except (json.JSONDecodeError, TypeError):
                    d["questions"] = []
                return d
            return None
    except Exception as e:
        logger.error(f"Failed to get next pending sub-topic: {e}")
        return None


# --- Finance ---


def _ensure_default_categories():
    """Ensures a user has the default categories. Safe to call repeatedly."""
    defaults = [
        ("Housing", "expense"),
        ("Food & Dining", "expense"),
        ("Transportation", "expense"),
        ("Utilities", "expense"),
        ("Healthcare", "expense"),
        ("Insurance", "expense"),
        ("Savings & Investments", "expense"),
        ("Personal Care", "expense"),
        ("Entertainment", "expense"),
        ("Miscellaneous", "expense"),
        ("Salary", "income"),
        ("Other Income", "income"),
    ]
    try:
        with db_session() as cursor:
            # Check if user has any categories
            cursor.execute("SELECT COUNT(*) FROM finance_categories")
            if cursor.fetchone()[0] == 0:
                cursor.executemany(
                    """
                    INSERT INTO finance_categories (name, type) 
                    VALUES (%s, %s) ON CONFLICT (name) DO NOTHING
                    """,
                    defaults,
                )
    except Exception as e:
        logger.error(f"Failed to ensure default categories: {e}")


def get_finance_categories() -> List[Dict[str, Any]]:
    """Retrieves all finance categories for a user, auto-populating defaults if none exist."""
    _ensure_default_categories()
    try:
        with db_session() as cursor:
            cursor.execute(
                """
                SELECT * FROM finance_categories 
                ORDER BY type, name
            """
            )
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Failed to get finance categories: {e}")
        return []


def add_finance_category(name: str, category_type: str = "expense") -> int:
    """Adds a custom finance category for a user."""
    try:
        with db_session() as cursor:
            cursor.execute(
                """
                INSERT INTO finance_categories (name, type)
                VALUES (%s, %s)
                RETURNING id
            """,
                (name, category_type),
            )
            return cursor.fetchone()[0]
    except psycopg2.IntegrityError:
        logger.warning(f"Category '{name}' already exists")
        return -1
    except Exception as e:
        logger.error(f"Failed to add finance category: {e}")
        return -1


def delete_finance_category(category_id: int) -> bool:
    """Deletes a custom finance category."""
    try:
        with db_session() as cursor:
            cursor.execute(
                "DELETE FROM finance_categories WHERE id = %s",
                (category_id,),
            )
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to delete finance category: {e}")
        return False


def add_finance_transactions(
    transactions: List[Dict[str, Any]], default_date: Optional[str] = None
) -> int:
    """Adds multiple financial transactions efficiently and supports custom dates."""
    if not transactions:
        return 0
    try:
        with db_session() as cursor:
            insert_data = []
            for t in transactions:
                amt = t.get("amount", 0.0)
                cat_id = t.get("category_id")
                desc = t.get("description", "")
                dl = t.get("date_logged") or default_date
                if not dl:
                    dl = datetime.now().strftime("%d-%m-%Y")
                insert_data.append((amt, cat_id, desc, dl))

            cursor.executemany(
                """
                INSERT INTO finance_transactions (amount, category_id, description, date_logged)
                VALUES (%s, %s, %s, %s)
            """,
                insert_data,
            )
            return cursor.rowcount
    except Exception as e:
        logger.error(f"Failed to add finance transactions: {e}")
        return -1


def get_finance_transactions(
    month: Optional[str] = None, date: Optional[str] = None, limit: int = 50
) -> List[Dict[str, Any]]:
    """Retrieves transactions, with optional month or specific date filtering."""
    try:
        query = """
            SELECT t.id, t.amount, t.description, t.date_logged, c.id as category_id, c.name as category_name, c.type as category_type
            FROM finance_transactions t
            JOIN finance_categories c ON t.category_id = c.id
            WHERE 1=1
        """
        params = []

        if date:
            query += " AND t.date_logged = %s"
            params.append(date)
        elif month:
            # month is typically YYYY-MM from UI, convert to MM-YYYY for storage search
            try:
                y, m = month.split("-")
                search_pattern = f"%-{m}-{y}"
                query += " AND t.date_logged LIKE %s"
                params.append(search_pattern)
            except:
                query += " AND t.date_logged LIKE %s"
                params.append(f"%{month}%")

        query += """
            ORDER BY substr(t.date_logged, 7, 4) DESC, substr(t.date_logged, 4, 2) DESC, substr(t.date_logged, 1, 2) DESC, t.created_at DESC
            LIMIT %s
        """
        params.append(limit)

        with db_session() as cursor:
            cursor.execute(query, tuple(params))
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Failed to get finance transactions: {e}")
        return []


def delete_finance_transaction(transaction_id: int) -> bool:
    """Deletes a specific financial transaction."""
    try:
        with db_session() as cursor:
            cursor.execute(
                "DELETE FROM finance_transactions WHERE id = %s",
                (transaction_id,),
            )
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to delete finance transaction: {e}")
        return False


def update_finance_transaction(transaction_id: int, updates: Dict[str, Any]) -> bool:
    """Updates selected fields of a financial transaction."""
    try:
        allowed_fields = ["amount", "category_id", "description", "date_logged"]
        set_clauses = []
        params = []

        for field in allowed_fields:
            if field in updates:
                val = updates[field]
                set_clauses.append(f"{field} = %s")
                params.append(val)

        if not set_clauses:
            return False

        params.append(transaction_id)
        query = f"UPDATE finance_transactions SET {', '.join(set_clauses)} WHERE id = %s"

        with db_session() as cursor:
            cursor.execute(query, tuple(params))
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to update finance transaction: {e}")
        return False


# ---- Application ----


def add_application_entry(
    company: str,
    position: str,
    email: Optional[str] = None,
    status: str = "Pending",
    notes: Optional[str] = None,
    url: Optional[str] = None,
) -> str:
    """Adds a new job application."""
    with db_session() as cursor:
        cursor.execute(
            """
            INSERT INTO job_applications (company, position, email, status, notes, url)
            VALUES (%s, %s, %s, %s, %s, %s)
        """,
            (company, position, email, status, notes, url),
        )
        return "Added to DB."


def get_applications(status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves all job applications, matching the old Google Sheets keys."""

    query = "SELECT * FROM job_applications"
    params = []
    if status_filter:
        query += " WHERE status LIKE %s"
        params.append(f"%{status_filter}%")

    query += " ORDER BY created_at DESC"

    with db_session() as cursor:
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()

    apps = []
    for r in rows:
        app = {
            "Company": r["company"],
            "Position": r["position"],
            "Email": r["email"] or "",
            "Status": r["status"],
            "Date Applied": r["date_applied"],
            "Notes": r["notes"] or "",
            "id": r["id"],
        }
        try:
            app["URL"] = r["url"] or ""
        except (IndexError, KeyError):
            app["URL"] = ""
        apps.append(app)
    return apps


def update_application_status(company: str, position: str, new_status: str) -> str:
    """Updates the status of a matching application."""
    c_clean = company.strip().lower()
    p_clean = position.strip().lower()

    with db_session() as cursor:
        cursor.execute(
            """
            UPDATE job_applications
            SET status = %s
            WHERE lower(company) = %s AND lower(position) = %s
            """,
            (new_status, c_clean, p_clean),
        )
        if cursor.rowcount > 0:
            return f"Status updated to '{new_status}'."
        return f"Application for '{position}' at '{company}' not found."


def update_application_entry(
    app_id: Optional[int] = None,
    old_company: Optional[str] = None,
    old_position: Optional[str] = None,
    company: Optional[str] = None,
    position: Optional[str] = None,
    email: Optional[str] = None,
    status: Optional[str] = None,
    notes: Optional[str] = None,
    url: Optional[str] = None,
) -> bool:
    """Updates selected fields of a job application entry."""
    try:
        set_clauses = []
        params = []

        if company is not None:
            set_clauses.append("company = %s")
            params.append(company.strip())
        if position is not None:
            set_clauses.append("position = %s")
            params.append(position.strip())
        if email is not None:
            set_clauses.append("email = %s")
            params.append(email.strip() if email else None)
        if status is not None:
            set_clauses.append("status = %s")
            params.append(status.strip())
            # Auto-update date_applied when status transitions to 'Applied'
            if status.strip().lower() == "applied":
                set_clauses.append("date_applied = CURRENT_DATE")
        if notes is not None:
            set_clauses.append("notes = %s")
            params.append(notes.strip() if notes else None)
        if url is not None:
            set_clauses.append("url = %s")
            params.append(url.strip() if url else None)

        if not set_clauses:
            return False

        with db_session() as cursor:
            if app_id:
                params.append(app_id)
                query = f"UPDATE job_applications SET {', '.join(set_clauses)} WHERE id = %s"
                cursor.execute(query, tuple(params))
            elif old_company and old_position:
                params.append(old_company.strip().lower())
                params.append(old_position.strip().lower())
                query = f"UPDATE job_applications SET {', '.join(set_clauses)} WHERE lower(company) = %s AND lower(position) = %s"
                cursor.execute(query, tuple(params))
            else:
                return False

            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to update application entry: {e}", exc_info=True)
        return False



def delete_application_entry(
    app_id: Optional[int] = None,
    company: Optional[str] = None,
    position: Optional[str] = None,
) -> bool:
    """Deletes a job application by ID or by company and position."""
    with db_session() as cursor:
        if app_id:
            cursor.execute("DELETE FROM job_applications WHERE id = %s", (app_id,))
        elif company and position:
            cursor.execute(
                "DELETE FROM job_applications WHERE lower(company) = %s AND lower(position) = %s",
                (company.strip().lower(), position.strip().lower()),
            )
        else:
            return False

        return cursor.rowcount > 0


# --- Scraped Jobs ---


def add_scraped_jobs(jobs: List[Dict[str, Any]]) -> int:
    """Inserts scraped jobs into the database, ignoring duplicates based on URL."""
    if not jobs:
        return 0
    inserted = 0
    with db_session() as cursor:
        for job in jobs:
            try:
                cursor.execute(
                    """
                    INSERT INTO scraped_jobs (title, company, location, date_posted, url, status)
                    VALUES (%s, %s, %s, %s, %s, 'new')
                    ON CONFLICT(url) DO UPDATE SET
                        title = excluded.title,
                        company = excluded.company,
                        location = excluded.location,
                        date_posted = excluded.date_posted
                        -- status is intentionally NOT overwritten so tracked jobs stay tracked
                """,
                    (
                        job.get("title", "N/A"),
                        job.get("company", "N/A"),
                        job.get("location", "N/A"),
                        job.get("date_posted", "Recent"),
                        job.get("url"),
                    ),
                )
                if cursor.rowcount > 0:
                    inserted += 1
            except Exception as e:
                logger.error(f"Failed to insert scraped job {job.get('url')}: {e}")
    return inserted


def get_scraped_jobs(
    keyword: Optional[str] = None,
    location: Optional[str] = None,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieves scraped jobs with filters applied, ordered by ID descending.
    Pass status='new'/'tracked'/'dismissed' to filter by status, or None for all.
    """
    query = "SELECT * FROM scraped_jobs WHERE 1=1"
    params = []

    if status:
        query += " AND status = %s"
        params.append(status)
    if keyword:
        query += " AND title LIKE %s"
        params.append(f"%{keyword}%")
    if location:
        query += " AND location LIKE %s"
        params.append(f"%{location}%")

    query += " ORDER BY id DESC"

    try:
        with db_session() as cursor:
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Failed to get scraped jobs: {e}")
        return []


def update_scraped_job_status(job_id: int, status: str) -> bool:
    """Updates the status of a scraped job. status: 'new' | 'tracked' | 'dismissed'."""
    try:
        with db_session() as cursor:
            cursor.execute(
                "UPDATE scraped_jobs SET status = %s WHERE id = %s",
                (status, job_id),
            )
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to update scraped job status: {e}")
        return False


def delete_scraped_job(job_id: int) -> bool:
    """Deletes a scraped job by ID."""
    try:
        with db_session() as cursor:
            cursor.execute("DELETE FROM scraped_jobs WHERE id = %s", (job_id,))
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to delete scraped job: {e}")
        return False


def clear_all_scraped_jobs() -> bool:
    """Clears all scraped jobs."""
    try:
        with db_session() as cursor:
            cursor.execute("DELETE FROM scraped_jobs")
            return True
    except Exception as e:
        logger.error(f"Failed to clear scraped jobs: {e}")
        return False


# --- Skill Tracking (Local DB) ---


def upsert_missing_skill(skill: str, increment: int = 1) -> bool:
    """Adds a new missing skill or increments the count for an existing one."""
    try:
        skill = skill.strip().lower()
        if not skill:
            return False

        with db_session() as cursor:
            cursor.execute(
                """
                INSERT INTO missing_skills (skill, count)
                VALUES (%s, %s)
                ON CONFLICT(skill) DO UPDATE SET
                    count = count + %s,
                    updated_at = CURRENT_TIMESTAMP
            """,
                (skill, increment, increment),
            )
        return True
    except Exception as e:
        logger.error(f"Failed to upsert missing skill {skill}: {e}")
        return False


def get_all_missing_skills() -> List[Dict[str, Any]]:
    """Retrieves all missing skills for a user, sorted by frequency (count)."""
    try:
        with db_session() as cursor:
            cursor.execute(
                """
                SELECT skill, count FROM missing_skills 
                ORDER BY count DESC
            """
            )
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Failed to get missing skills: {e}")
        return []


def delete_missing_skill(skill: str) -> bool:
    """Deletes a specific missing skill for a user."""
    try:
        with db_session() as cursor:
            cursor.execute(
                """
                DELETE FROM missing_skills WHERE skill = %s
            """,
                (skill.strip().lower(),),
            )
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to delete skill {skill}: {e}")
        return False


# ---- Resume ----
def save_resume_entry(
    file_path: str, file_name: str, resume_text: str, cover_letter_text: str
) -> int:
    """Saves a parsed resume and its generated cover letter."""
    try:
        with db_session() as cursor:
            # Robust handle if parameters are passed as lists (common with some model outputs)
            if isinstance(resume_text, (list, set)):
                resume_text = "\n".join(map(str, resume_text))
            if isinstance(cover_letter_text, (list, set)):
                cover_letter_text = "\n".join(map(str, cover_letter_text))

            cursor.execute(
                """
                INSERT INTO resume_entries (file_path, file_name, resume_text, cover_letter_text)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """,
                (file_path, file_name, resume_text, cover_letter_text),
            )
            return cursor.fetchone()[0]
    except Exception as e:
        logger.error(f"Failed to save resume entry: {e}")
        return -1


def get_resume_entry() -> Optional[Dict[str, Any]]:
    """Retrieves the system resume entry."""
    try:
        with db_session() as cursor:
            cursor.execute("SELECT * FROM resume_entries LIMIT 1")
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Failed to get resume entry: {e}")
        return None


def clear_resume_table() -> bool:
    """Deletes all resume entries."""
    try:
        with db_session() as cursor:
            cursor.execute("DELETE FROM resume_entries")
            return True
    except Exception as e:
        logger.error(f"Error clearing resume table: {e}")
        return False


def update_cover_letter(cover_letter_text: str) -> bool:
    """Updates the cover letter of the existing resume entry."""
    try:
        with db_session() as cursor:
            cursor.execute(
                "UPDATE resume_entries SET cover_letter_text = %s",
                (cover_letter_text,)
            )
            return True
    except Exception as e:
        logger.error(f"Failed to update cover letter: {e}")
        return False


def save_llm_usage(
    model: str, input_tokens: int, output_tokens: int, total_tokens: int
):
    """Saves LLM token usage to the database."""
    try:
        with db_session() as cursor:
            cursor.execute(
                """
                INSERT INTO llm_usage (model, input_tokens, output_tokens, total_tokens)
                VALUES (%s, %s, %s, %s)
            """,
                (model, input_tokens, output_tokens, total_tokens),
            )
    except Exception as e:
        logger.error(f"Error saving LLM usage: {e}")


def get_llm_usage_stats():
    """Retrieves aggregate LLM usage stats."""
    try:
        with db_session() as cursor:
            cursor.execute(
                """
                SELECT 
                    SUM(input_tokens) as total_input,
                    SUM(output_tokens) as total_output,
                    SUM(total_tokens) as total_all,
                    COUNT(*) as total_calls
                FROM llm_usage
            """
            )
            row = cursor.fetchone()
            return {
                "total_input": row["total_input"] or 0,
                "total_output": row["total_output"] or 0,
                "total_all": row["total_all"] or 0,
                "total_calls": row["total_calls"] or 0,
            }
    except Exception as e:
        logger.error(f"Error getting LLM stats: {e}")
        return {"total_input": 0, "total_output": 0, "total_all": 0, "total_calls": 0}


# --- Brain Dumps ---


def add_brain_dump(
    content: str,
    title: Optional[str] = None,
    category: str = "Note",
    tags: Optional[List[str]] = None,
) -> int:
    """Adds a new brain dump entry."""
    tags_json = json.dumps(tags) if tags else None
    with db_session() as cursor:
        cursor.execute(
            """
            INSERT INTO brain_dumps (title, content, category, tags)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """,
            (title, content, category, tags_json),
        )
        return cursor.fetchone()[0]


def add_brain_dumps(entries: List[Dict[str, Any]]) -> int:
    """Adds multiple brain dump entries efficiently."""
    if not entries:
        return 0
    try:
        with db_session() as cursor:
            data = [
                (
                    e.get("title"),
                    e["content"],
                    e.get("category", "Note"),
                    json.dumps(e.get("tags")),
                )
                for e in entries
            ]
            cursor.executemany(
                """
                INSERT INTO brain_dumps (title, content, category, tags)
                VALUES (%s, %s, %s, %s)
            """,
                data,
            )
            return cursor.rowcount
    except Exception as e:
        logger.error(f"Failed to bulk add brain dumps: {e}")
        return -1


def get_brain_dumps(
    category: Optional[str] = None, tag: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Retrieves brain dumps with optional filtering."""
    query = "SELECT * FROM brain_dumps WHERE 1=1"
    params = []

    if category:
        query += " AND category = %s"
        params.append(category)

    if tag:
        query += " AND tags LIKE %s"
        params.append(f'%"{tag}"%')

    query += " ORDER BY created_at DESC"

    with db_session() as cursor:
        cursor.execute(query, tuple(params))
        return [
            {**dict(row), "tags": json.loads(row["tags"]) if row["tags"] else []}
            for row in cursor.fetchall()
        ]


def delete_brain_dump(dump_id: int) -> bool:
    """Deletes a brain dump entry."""
    with db_session() as cursor:
        cursor.execute("DELETE FROM brain_dumps WHERE id = %s", (dump_id,))
        return cursor.rowcount > 0


def get_unique_dump_metadata() -> Dict[str, List[str]]:
    """Returns a list of all unique categories and tags used in dumps (Optimized)."""
    with db_session() as cursor:
        cursor.execute("SELECT DISTINCT category FROM brain_dumps")
        categories = [row["category"] for row in cursor.fetchall() if row["category"]]

        # Efficiently extract unique tags using PostgreSQL JSON features
        cursor.execute(
            """
            SELECT DISTINCT tag 
            FROM brain_dumps, json_array_elements_text(tags::json) AS tag 
            WHERE tags IS NOT NULL AND tags != '' AND tags != 'null'
            """
        )
        tags = [row[0] for row in cursor.fetchall() if row[0]]

        return {"categories": sorted(categories), "tags": sorted(tags)}


def set_setting(key: str, value: Any) -> None:
    """Saves or updates a setting in the database."""
    val_str = json.dumps(value)
    with db_session() as cursor:
        cursor.execute(
            """
            INSERT INTO user_settings (key, value)
            VALUES (%s, %s)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, val_str),
        )


def get_setting(key: str, default: Any = None) -> Any:
    """Retrieves a setting from the database, returning default if not found."""
    try:
        with db_session() as cursor:
            cursor.execute("SELECT value FROM user_settings WHERE key = %s", (key,))
            row = cursor.fetchone()
            if row:
                return json.loads(row["value"])
    except Exception as e:
        logger.error(f"Error loading setting '{key}': {e}")
    return default
