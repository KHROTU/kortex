import sqlite3
import datetime

DB_PATH = "kortex_memory.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reminders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reminder_text TEXT NOT NULL,
        due_at TIMESTAMP NOT NULL,
        triggered BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS alarms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        alarm_name TEXT,
        due_at TIMESTAMP NOT NULL,
        triggered BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    conn.commit()
    conn.close()
    print("Database initialized successfully.")

def add_note(content):
    conn = get_db_connection()
    conn.execute("INSERT INTO notes (content) VALUES (?)", (content,))
    conn.commit()
    conn.close()

def get_notes(limit=5):
    conn = get_db_connection()
    notes = conn.execute("SELECT content FROM notes ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [note['content'] for note in notes]

def add_reminder(reminder_text, due_at):
    conn = get_db_connection()
    conn.execute("INSERT INTO reminders (reminder_text, due_at) VALUES (?, ?)", (reminder_text, due_at))
    conn.commit()
    conn.close()

def add_alarm(due_at, alarm_name="Alarm"):
    conn = get_db_connection()
    conn.execute("INSERT INTO alarms (alarm_name, due_at) VALUES (?, ?)", (alarm_name, due_at))
    conn.commit()
    conn.close()

def get_due_tasks(task_type="reminders"):
    conn = get_db_connection()
    now = datetime.datetime.now()
    query = f"SELECT * FROM {task_type} WHERE due_at <= ? AND triggered = 0"
    tasks = conn.execute(query, (now,)).fetchall()
    conn.close()
    return tasks

def mark_task_triggered(task_id, task_type="reminders"):
    conn = get_db_connection()
    query = f"UPDATE {task_type} SET triggered = 1 WHERE id = ?"
    conn.execute(query, (task_id,))
    conn.commit()
    conn.close()