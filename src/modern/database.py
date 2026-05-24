"""Работа с базой данных."""

import sqlite3
from pathlib import Path
from contextlib import contextmanager
import click
import pandas as pd
import re

# Пути
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"

DATA_DIR.mkdir(exist_ok=True)

DB_FILE = DATA_DIR / "modern.db"
EXCEL_FILE = DATA_DIR / "tech_base.xlsx"

# Константы
STATUS_CHOICES = ['working', 'repair', 'reserve', 'written_off']
EVENT_TYPES = ['ремонт', 'ТО', 'диагностика', 'замена', 'заметка', 'поломка']

# Соответствие типа суффиксу
TYPE_SUFFIX = {
    'экскаватор': 'Э',
    'грейдер': 'Г',
    'автогрейдер': 'Г',
    'самосвал': 'С',
    'погрузчик': 'П',
    'бульдозер': 'Б',
    'телескоп': 'Т',
    'вилочный': 'В',
    'шинный': 'Ш',
}

SUFFIX_TYPE = {v: k for k, v in TYPE_SUFFIX.items()}


@contextmanager
def get_db():
    """Контекстный менеджер для работы с БД."""
    conn = sqlite3.connect(DB_FILE)
    try:
        yield conn
    finally:
        conn.close()


def machine_exists(cursor, bort: str) -> bool:
    """Проверяет существование машины."""
    cursor.execute("SELECT 1 FROM machines WHERE bort = ?", (bort,))
    return cursor.fetchone() is not None


def get_machine_info(cursor, bort: str):
    """Возвращает тип и модель машины."""
    cursor.execute("SELECT type, model FROM machines WHERE bort = ?", (bort,))
    return cursor.fetchone()


def get_all_machines(cursor, limit=100):
    """Возвращает список всех машин."""
    cursor.execute("SELECT bort, type, model, year, hours, status, location FROM machines WHERE bort IS NOT NULL ORDER BY bort LIMIT ?", (limit,))
    return cursor.fetchall()


def get_suffix_by_type(tech_type: str) -> str:
    """Возвращает суффикс по типу техники."""
    tech_type_lower = tech_type.lower().strip()
    for key, suffix in TYPE_SUFFIX.items():
        if key in tech_type_lower:
            return suffix
    return ''


def init_db():
    """Создаёт таблицы и индексы."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS machines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT,
                bort TEXT UNIQUE,
                type TEXT,
                model TEXT,
                serial TEXT,
                engine_model TEXT,
                engine_number TEXT,
                year INTEGER,
                hours INTEGER,
                status TEXT,
                location TEXT,
                last_maintenance DATE,
                next_maintenance_hours INTEGER,
                notes TEXT,
                created_by TEXT,
                created_at DATE,
                updated_by TEXT,
                updated_at DATE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bort TEXT,
                event_date DATE,
                event_type TEXT,
                description TEXT,
                parts TEXT,
                cost INTEGER,
                hours INTEGER,
                master TEXT,
                notes TEXT,
                created_by TEXT,
                created_at DATE,
                FOREIGN KEY (bort) REFERENCES machines(bort)
            )
        ''')
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bort ON machines(bort)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_bort ON events(bort)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_date ON events(event_date)")
        
        conn.commit()


def import_from_excel(conn: sqlite3.Connection):
    """Импортирует данные из Excel."""
    if not EXCEL_FILE.exists():
        click.echo(click.style(f"Файл {EXCEL_FILE} не найден.", fg='yellow'))
        return
    
    df = pd.read_excel(EXCEL_FILE, sheet_name=0, dtype=str, engine='openpyxl')
    df = df.fillna('')
    df.columns = [c.strip().lower() for c in df.columns]
    
    if 'serial_number' in df.columns:
        df.rename(columns={'serial_number': 'serial'}, inplace=True)
    
    expected_cols = [
        'code', 'bort', 'type', 'model', 'serial', 'engine_model', 'engine_number',
        'year', 'hours', 'status', 'location', 'last_maintenance', 'notes'
    ]
    for col in expected_cols:
        if col not in df.columns:
            df[col] = ''
    df = df[expected_cols]
    
    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].str.replace(r'\.0$', '', regex=True)
    
    def add_suffix(row):
        bort = row.get('bort', '')
        if pd.isna(bort) or str(bort).strip() == '':
            return None
        bort_str = str(bort).strip()
        if re.search(r'[А-Яа-яA-Za-z]', bort_str):
            return bort_str
        suffix = get_suffix_by_type(row.get('type', ''))
        return f"{bort_str}{suffix}" if suffix else bort_str
    
    df['bort'] = df.apply(add_suffix, axis=1)
    df = df[df['bort'].notna()]
    df = df.drop_duplicates(subset=['bort'], keep='first')
    df = df.where(pd.notnull(df), None)
    df.to_sql('machines', conn, if_exists='append', index=False)
    
    click.echo(click.style(f"Импортировано {len(df)} записей из Excel.", fg='green'))


def init_data():
    """Инициализирует данные, если таблица пуста."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM machines")
        if cursor.fetchone()[0] == 0:
            import_from_excel(conn)