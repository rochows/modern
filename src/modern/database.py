import sqlite3
from pathlib import Path
from contextlib import contextmanager
import click
import pandas as pd

# Пути
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"

DATA_DIR.mkdir(exist_ok=True)

DB_FILE = DATA_DIR / "modern.db"
EXCEL_FILE = DATA_DIR / "tech_base.xlsx"

# Константы
STATUS_CHOICES = ['working', 'repair', 'reserve', 'written_off']
EVENT_TYPES = ['ремонт', 'ТО', 'диагностика', 'замена', 'заметка', 'поломка']

# Типы техники (для справки)
MACHINE_TYPES = ['экскаватор', 'самосвал', 'погрузчик', 'грейдер', 'бульдозер', 'автогрейдер', 'телескоп', 'вилочный', 'шинный']


@contextmanager
def get_db():
    """Контекстный менеджер для работы с БД."""
    conn = sqlite3.connect(DB_FILE)
    try:
        yield conn
    finally:
        conn.close()


def machine_exists(cursor, bort: str) -> bool:
    """Проверяет существование машины по бортовому номеру."""
    cursor.execute("SELECT 1 FROM machines WHERE bort = ?", (bort,))
    return cursor.fetchone() is not None


def get_machine_info(cursor, bort: str):
    """Возвращает тип и модель машины."""
    cursor.execute("SELECT type, model FROM machines WHERE bort = ?", (bort,))
    return cursor.fetchone()


def get_all_machines(cursor, limit=100):
    """Возвращает список всех машин."""
    cursor.execute("SELECT bort, type, model, year, hours, status, location FROM machines WHERE bort IS NOT NULL ORDER BY CAST(bort AS INTEGER) LIMIT ?", (limit,))
    return cursor.fetchall()


def init_db():
    """Создаёт таблицы и индексы."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Таблица машин (bort — просто число или строка)
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
        
        # Таблица событий
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
        
        # Индексы
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bort ON machines(bort)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_bort ON events(bort)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_date ON events(event_date)")
        
        conn.commit()


def import_from_excel(conn: sqlite3.Connection):
    """Импортирует данные из tech_base.xlsx в таблицу machines."""
    if not EXCEL_FILE.exists():
        click.echo(click.style(f"Файл {EXCEL_FILE} не найден.", fg='yellow'))
        return

    df = pd.read_excel(EXCEL_FILE, sheet_name=0, dtype=str, engine='openpyxl')
    df = df.fillna('')
    df.columns = [c.strip().lower() for c in df.columns]

    # Приводим имена колонок
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

    # Очистка
    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].str.replace(r'\.0$', '', regex=True)

    # Удаляем пустые бортовые номера
    df = df[df['bort'].notna() & (df['bort'] != '')]
    
    # Убираем дубликаты
    df = df.drop_duplicates(subset=['bort'], keep='first')
    
    # Пустые строки -> None
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
            
            
def get_vehicle_types():
    """Возвращает список типов техники из БД."""
    with get_db() as conn:
        cursor = conn.cursor()
        # Создаём таблицу для хранения типов, если её нет
        cursor.execute("CREATE TABLE IF NOT EXISTS vehicle_types (type TEXT UNIQUE)")
        cursor.execute("SELECT type FROM vehicle_types ORDER BY type")
        types = [row[0] for row in cursor.fetchall()]
        if not types:
            # Добавляем типы по умолчанию
            default_types = ["Экскаватор", "Бульдозер", "Самосвал", "Погрузчик", "Грейдер"]
            for t in default_types:
                cursor.execute("INSERT OR IGNORE INTO vehicle_types (type) VALUES (?)", (t,))
            conn.commit()
            return default_types
        return types


def add_vehicle_type(vehicle_type: str):
    """Добавляет новый тип техники."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS vehicle_types (type TEXT UNIQUE)")
        cursor.execute("INSERT OR IGNORE INTO vehicle_types (type) VALUES (?)", (vehicle_type,))
        conn.commit()