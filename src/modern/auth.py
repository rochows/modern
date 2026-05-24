"""Аутентификация и управление пользователями."""

import hashlib
import secrets
from datetime import datetime
from contextlib import contextmanager
import sqlite3
from pathlib import Path
import click

from modern.database import get_db, DATA_DIR

# Роли пользователей
USER_ROLES = {
    'admin': 3,      # Полный доступ
    'manager': 2,    # Добавление/редактирование техники, просмотр
    'viewer': 1,     # Только просмотр
}

ROLE_NAMES = {v: k for k, v in USER_ROLES.items()}


def hash_password(password: str) -> str:
    """Хеширует пароль с солью."""
    salt = secrets.token_hex(16)
    hash_obj = hashlib.sha256((password + salt).encode())
    return f"{salt}:{hash_obj.hexdigest()}"


def verify_password(password: str, hashed: str) -> bool:
    """Проверяет пароль."""
    try:
        salt, hash_value = hashed.split(':')
        new_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        return new_hash == hash_value
    except:
        return False


def init_auth_db():
    """Создаёт таблицу пользователей."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role INTEGER DEFAULT 1,
                full_name TEXT,
                created_at DATE,
                last_login DATE,
                active INTEGER DEFAULT 1
            )
        ''')
        
        # Создаём админа по умолчанию, если нет пользователей
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            admin_pass = hash_password("admin123")
            cursor.execute('''
                INSERT INTO users (username, password_hash, role, full_name, created_at, active)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', ('admin', admin_pass, 3, 'Administrator', datetime.now().isoformat(), 1))
            click.echo(click.style("Создан пользователь admin (пароль: admin123)", fg='yellow'))
        
        conn.commit()


def authenticate(username: str, password: str) -> dict | None:
    """Аутентификация пользователя."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, password_hash, role, full_name FROM users WHERE username = ? AND active = 1", (username,))
        user = cursor.fetchone()
        
        if user and verify_password(password, user[2]):
            # Обновляем время последнего входа
            cursor.execute("UPDATE users SET last_login = ? WHERE id = ?", (datetime.now().isoformat(), user[0]))
            conn.commit()
            return {
                'id': user[0],
                'username': user[1],
                'role': user[3],
                'role_name': ROLE_NAMES.get(user[3], 'viewer'),
                'full_name': user[4]
            }
    return None


def check_permission(user_role: int, required_role: int) -> bool:
    """Проверяет, есть ли у пользователя права."""
    return user_role >= required_role


def add_user(username: str, password: str, role: str = 'viewer', full_name: str = None):
    """Добавляет нового пользователя (только для админа)."""
    role_level = USER_ROLES.get(role.lower(), 1)
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            return False, "Пользователь уже существует"
        
        password_hash = hash_password(password)
        cursor.execute('''
            INSERT INTO users (username, password_hash, role, full_name, created_at, active)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (username, password_hash, role_level, full_name, datetime.now().isoformat(), 1))
        conn.commit()
        return True, "Пользователь добавлен"


def list_users():
    """Возвращает список пользователей."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, role, full_name, last_login, active FROM users")
        return cursor.fetchall()


def set_user_role(username: str, role: str):
    """Изменяет роль пользователя."""
    role_level = USER_ROLES.get(role.lower())
    if not role_level:
        return False
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET role = ? WHERE username = ?", (role_level, username))
        conn.commit()
        return cursor.rowcount > 0


def disable_user(username: str):
    """Блокирует пользователя."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET active = 0 WHERE username = ?", (username,))
        conn.commit()
        return cursor.rowcount > 0


class Session:
    """Сессия текущего пользователя."""
    
    _current_user = None
    
    @classmethod
    def login(cls, username: str, password: str) -> bool:
        """Вход в систему."""
        user = authenticate(username, password)
        if user:
            cls._current_user = user
            return True
        return False
    
    @classmethod
    def logout(cls):
        """Выход из системы."""
        cls._current_user = None
    
    @classmethod
    def get_user(cls):
        return cls._current_user
    
    @classmethod
    def is_authenticated(cls) -> bool:
        return cls._current_user is not None
    
    @classmethod
    def has_permission(cls, required_role: int) -> bool:
        if not cls._current_user:
            return False
        return cls._current_user['role'] >= required_role
    
    @classmethod
    def is_admin(cls) -> bool:
        return cls.has_permission(USER_ROLES['admin'])
    
    @classmethod
    def is_manager(cls) -> bool:
        return cls.has_permission(USER_ROLES['manager'])
    
    @classmethod
    def get_role_name(cls) -> str:
        return cls._current_user['role_name'] if cls._current_user else 'guest'