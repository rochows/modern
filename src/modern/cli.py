"""CLI-интерфейс для учёта техники."""

import sys
from pathlib import Path
from datetime import datetime
import re
import subprocess
import time

import click
from click_shell import shell

from modern.database import (
    get_db, init_db, init_data, machine_exists, get_machine_info,
    STATUS_CHOICES, EVENT_TYPES, MACHINE_TYPES
)
from modern.auth import (
    Session, init_auth_db, add_user, list_users,
    set_user_role, disable_user, USER_ROLES, ROLE_NAMES
)


# ------------------------ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ------------------------
def make_double_frame(text: str) -> str:
    """Обрамляет текст двойной рамкой."""
    if not text:
        return "╔═╗\n║ ║\n╚═╝"
    lines = text.split('\n')
    max_len = max(len(line) for line in lines)
    top = "╔" + "═" * (max_len + 2) + "╗"
    bottom = "╚" + "═" * (max_len + 2) + "╝"
    return "\n".join([top] + [f"║ {line.ljust(max_len)} ║" for line in lines] + [bottom])


def validate_bort(bort: str) -> bool:
    """Проверяет, что бортовой номер не пустой."""
    return bool(bort and str(bort).strip())


def require_auth(f):
    """Декоратор для проверки аутентификации."""
    def wrapper(*args, **kwargs):
        if not Session.is_authenticated():
            click.echo(click.style("Требуется авторизация. Используйте 'login'", fg='red'))
            return
        return f(*args, **kwargs)
    return wrapper


def require_permission(role_level):
    """Декоратор для проверки прав."""
    def decorator(f):
        def wrapper(*args, **kwargs):
            if not Session.is_authenticated():
                click.echo(click.style("Требуется авторизация.", fg='red'))
                return
            if not Session.has_permission(role_level):
                click.echo(click.style(f"Недостаточно прав. Требуется: {ROLE_NAMES.get(role_level, 'unknown')}", fg='red'))
                return
            return f(*args, **kwargs)
        return wrapper
    return decorator


def run_app(cmd, delay=0.1):
    """Кроссплатформенный запуск приложений."""
    subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    time.sleep(delay)


# ------------------------ КОМАНДЫ АУТЕНТИФИКАЦИИ ------------------------
@click.command(name='login')
def login_command():
    """Вход в систему."""
    username = click.prompt("Имя пользователя", type=str)
    password = click.prompt("Пароль", type=str, hide_input=True)
    
    if Session.login(username, password):
        user = Session.get_user()
        click.echo(click.style(f"Добро пожаловать, {user['full_name'] or user['username']}! Роль: {user['role_name']}", fg='green'))
    else:
        click.echo(click.style("Неверное имя пользователя или пароль.", fg='red'))


@click.command(name='logout')
def logout_command():
    """Выход из системы."""
    if Session.is_authenticated():
        username = Session.get_user()['username']
        Session.logout()
        click.echo(click.style(f"Пользователь '{username}' вышел из системы.", fg='yellow'))
    else:
        click.echo("Вы не авторизованы.")


@click.command(name='whoami')
def whoami_command():
    """Информация о текущем пользователе."""
    if Session.is_authenticated():
        user = Session.get_user()
        click.echo(click.style(f"Пользователь: {user['username']} ({user['full_name'] or 'без имени'})", fg='cyan'))
        click.echo(click.style(f"Роль: {user['role_name']}", fg='cyan'))
    else:
        click.echo("Не авторизован.")


@click.command(name='add-user')
@require_permission(USER_ROLES['admin'])
def add_user_command():
    """Добавление нового пользователя (только админ)."""
    username = click.prompt("Имя пользователя", type=str)
    password = click.prompt("Пароль", type=str, hide_input=True)
    password2 = click.prompt("Повторите пароль", type=str, hide_input=True)
    
    if password != password2:
        click.echo(click.style("Пароли не совпадают.", fg='red'))
        return
    
    role = click.prompt("Роль (admin/manager/viewer)", type=click.Choice(['admin', 'manager', 'viewer']), default='viewer')
    full_name = click.prompt("Полное имя (Enter - пропустить)", default="", show_default=False) or None
    
    success, msg = add_user(username, password, role, full_name)
    if success:
        click.echo(click.style(msg, fg='green'))
    else:
        click.echo(click.style(msg, fg='red'))


@click.command(name='list-users')
@require_permission(USER_ROLES['admin'])
def list_users_command():
    """Список пользователей (только админ)."""
    users = list_users()
    
    if not users:
        click.echo("Нет пользователей.")
        return
    
    click.echo(click.style("\nСПИСОК ПОЛЬЗОВАТЕЛЕЙ", fg='cyan'))
    click.echo(click.style("=" * 80, fg='cyan'))
    click.echo(f"{'ID':<4} {'Имя':<15} {'Роль':<10} {'ФИО':<20} {'Активен':<8}")
    click.echo(click.style("-" * 80, fg='cyan'))
    
    for user in users:
        active = "Да" if user[5] else "Нет"
        role = ROLE_NAMES.get(user[2], 'viewer')
        click.echo(f"{user[0]:<4} {user[1]:<15} {role:<10} {(user[3] or '—')[:20]:<20} {active:<8}")
    
    click.echo(click.style("=" * 80, fg='cyan'))


# ------------------------ ОСНОВНЫЕ КОМАНДЫ ------------------------
@click.command()
def calc():
    """Запуск калькулятора"""
    if sys.platform == 'win32':
        run_app('calc.exe')
    elif sys.platform == 'darwin':
        run_app(['open', '-a', 'Calculator'])
    else:
        run_app(['gnome-calculator'])


@click.command()
def paint():
    """Запуск графического редактора"""
    if sys.platform == 'win32':
        run_app('mspaint.exe')
    elif sys.platform == 'darwin':
        run_app(['open', '-a', 'Preview'])
    else:
        run_app(['pinta'])


@click.command(name='web')
def web_command():
    """Запустить красивый веб-интерфейс в браузере."""
    import streamlit.web.cli as stcli
    
    # Находим путь к файлу streamlit_app.py, который лежит в корне проекта
    app_path = Path(__file__).parent / "app.py"
    
    if not app_path.exists():
        click.echo(click.style(f"Файл {app_path} не найден.", fg='red'))
        return
    
    click.echo(click.style("🚀 Запуск веб-интерфейса Streamlit...", fg='green'))
    sys.argv = ["streamlit", "run", str(app_path)]
    sys.exit(stcli.main())


@click.command(name='find')
@click.argument('bort')
@require_auth
def find_command(bort):
    """Поиск машины по бортовому номеру."""
    val = str(bort).strip()
    
    if not validate_bort(val):
        click.echo(click.style("Бортовой номер не может быть пустым.", fg='yellow'))
        return
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM machines WHERE bort = ?", (val,))
        rows = cursor.fetchall()
    
    if not rows:
        click.echo(click.style(f"Машина '{val}' не найдена.", fg='red'))
        return
    
    fields = ['ID', 'Борт №', 'Тип', 'Модель', 'Зав. №', 'Модель ДВС', '№ ДВС',
              'Год', 'Моточасы', 'Статус', 'Место', 'Последнее ТО', 'Заметки']
    
    for row in rows:
        info_lines = [f"{fields[i]:<22} {row[i+1] or '---'}" for i in range(len(fields))]
        click.echo(click.style(make_double_frame("\n".join(info_lines)), fg='green'))


@click.command(name='list')
@click.option('--status', help='Фильтр по статусу (working/repair/reserve/written_off)')
@click.option('--type', 'type_name', help='Фильтр по типу техники')
@click.option('--limit', default=50, help='Лимит записей')
@require_auth
def list_machines(status, type_name, limit):
    """Список машин."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        query = "SELECT bort, type, model, year, hours, status, location FROM machines WHERE bort IS NOT NULL"
        params = []
        
        if status:
            query += " AND status = ?"
            params.append(status)
        if type_name:
            query += " AND type LIKE ?"
            params.append(f"%{type_name}%")
        
        query += " ORDER BY CAST(bort AS INTEGER) LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
    
    if not rows:
        click.echo("Машин не найдено.")
        return
    
    headers = ["Борт", "Тип", "Модель", "Год", "Моточасы", "Статус", "Место"]
    col_widths = [10, 15, 15, 6, 10, 12, 15]
    
    click.echo(click.style("\n" + "=" * sum(col_widths), fg='cyan'))
    header_line = "".join(f"{h:<{w}}" for h, w in zip(headers, col_widths))
    click.echo(click.style(header_line, fg='cyan'))
    click.echo(click.style("=" * sum(col_widths), fg='cyan'))
    
    for row in rows:
        bort, typ, model, year, hours, status, location = row
        line = f"{bort or '—':<{col_widths[0]}} {typ or '—':<{col_widths[1]}} {model or '—':<{col_widths[2]}} {year or '—':<{col_widths[3]}} {hours or '—':<{col_widths[4]}} {status or '—':<{col_widths[5]}} {location or '—':<{col_widths[6]}}"
        click.echo(line)
    
    click.echo(click.style("=" * sum(col_widths), fg='cyan'))
    click.echo(click.style(f"\nВсего: {len(rows)} машин", fg='green'))


@click.command(name='stats')
@require_auth
def stats():
    """Статистика."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM machines WHERE bort IS NOT NULL")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT status, COUNT(*) FROM machines WHERE bort IS NOT NULL GROUP BY status")
        status_stats = cursor.fetchall()
        
        cursor.execute("SELECT type, COUNT(*) FROM machines WHERE bort IS NOT NULL GROUP BY type")
        type_stats = cursor.fetchall()
        
        cursor.execute("SELECT AVG(hours) FROM machines WHERE hours IS NOT NULL")
        avg_hours = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM events")
        total_events = cursor.fetchone()[0]
    
    stats_text = f"""
 СТАТИСТИКА ТЕХНИКИ
{'═' * 40}

 Всего машин: {total}
 Всего событий: {total_events}

 По статусам:
"""
    for status, count in status_stats:
        stats_text += f"   • {status or 'не указан'}: {count}\n"
    
    stats_text += f"\n По типам:\n"
    for typ, count in type_stats:
        stats_text += f"   • {typ}: {count}\n"
    
    if avg_hours:
        stats_text += f"\n Моточасы:\n   • Средние: {avg_hours:.0f}\n"
    
    click.echo(click.style(make_double_frame(stats_text), fg='green'))


@click.command(name='add-machine')
@require_permission(USER_ROLES['manager'])
def add_machine_interactive():
    """Интерактивное добавление машины."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        click.echo(click.style("\nДОБАВЛЕНИЕ НОВОЙ МАШИНЫ", fg='cyan'))
        click.echo("-" * 50)
        
        while True:
            bort = click.prompt("Бортовой номер", type=str).strip()
            if not bort:
                click.echo("Бортовой номер не может быть пустым.")
                continue
            if not bort.isdigit():
                click.echo("Введите только цифры.")
                continue
            if machine_exists(cursor, bort):
                click.echo(click.style(f"Машина с номером '{bort}' уже существует.", fg='red'))
                continue
            break
        
        type_name = click.prompt("Тип техники", type=str)
        model = click.prompt("Модель", type=str)
        serial = click.prompt("Заводской номер (Enter - пропустить)", default="", show_default=False) or None
        engine_model = click.prompt("Модель двигателя (Enter - пропустить)", default="", show_default=False) or None
        engine_number = click.prompt("Номер двигателя (Enter - пропустить)", default="", show_default=False) or None
        year_str = click.prompt("Год выпуска (Enter - пропустить)", default="", show_default=False)
        year = int(year_str) if year_str else None
        hours_str = click.prompt("Начальные моточасы (Enter - пропустить)", default="", show_default=False)
        hours = int(hours_str) if hours_str else None
        status = click.prompt("Статус", type=click.Choice(STATUS_CHOICES), default='working')
        location = click.prompt("Местоположение (Enter - пропустить)", default="", show_default=False) or None
        notes = click.prompt("Примечания (Enter - пропустить)", default="", show_default=False) or None
        
        user = Session.get_user()
        cursor.execute('''
            INSERT INTO machines (bort, type, model, serial, engine_model, engine_number,
                                 year, hours, status, location, notes, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (bort, type_name, model, serial, engine_model, engine_number,
              year, hours, status, location, notes, user['username'], datetime.now().isoformat()))
        conn.commit()
    
    click.echo(click.style(f"\nМашина '{bort}' успешно добавлена!", fg='green'))


@click.command(name='edit-machine')
@click.argument('bort')
@require_permission(USER_ROLES['manager'])
def edit_machine(bort):
    """Редактирование машины."""
    bort = str(bort).strip()
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        if not machine_exists(cursor, bort):
            click.echo(click.style(f"Машина '{bort}' не найдена.", fg='red'))
            return
        
        cursor.execute("SELECT type, model, year, hours, status, location, notes FROM machines WHERE bort = ?", (bort,))
        current = cursor.fetchone()
        
        click.echo(click.style(f"\nРЕДАКТИРОВАНИЕ МАШИНЫ {bort}", fg='cyan'))
        click.echo("-" * 50)
        
        type_name = click.prompt(f"Тип техники (текущий: {current[0]})", default=current[0])
        model = click.prompt(f"Модель (текущая: {current[1]})", default=current[1])
        year_str = click.prompt(f"Год выпуска (текущий: {current[2] or 'не указан'})", default=str(current[2]) if current[2] else "", show_default=False)
        year = int(year_str) if year_str else None
        hours_str = click.prompt(f"Моточасы (текущие: {current[3] or 'не указаны'})", default=str(current[3]) if current[3] else "", show_default=False)
        hours = int(hours_str) if hours_str else None
        status = click.prompt(f"Статус (текущий: {current[4]})", type=click.Choice(STATUS_CHOICES), default=current[4] or 'working')
        location = click.prompt(f"Местоположение (текущее: {current[5] or 'не указано'})", default=current[5] or "", show_default=False) or None
        notes = click.prompt(f"Примечания (текущие: {current[6][:50] if current[6] else 'нет'})", default=current[6] or "", show_default=False) or None
        
        user = Session.get_user()
        cursor.execute('''
            UPDATE machines SET type=?, model=?, year=?, hours=?, status=?, location=?, notes=?, updated_by=?, updated_at=?
            WHERE bort=?
        ''', (type_name, model, year, hours, status, location, notes, user['username'], datetime.now().isoformat(), bort))
        conn.commit()
    
    click.echo(click.style(f"Машина '{bort}' обновлена.", fg='green'))


@click.command(name='delete-machine')
@click.argument('bort')
@require_permission(USER_ROLES['admin'])
def delete_machine(bort):
    """Удаление машины (только админ)."""
    bort = str(bort).strip()
    
    if not click.confirm(click.style(f"Удалить машину '{bort}' и все связанные события?", fg='red')):
        click.echo("Отменено.")
        return
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM events WHERE bort = ?", (bort,))
        cursor.execute("DELETE FROM machines WHERE bort = ?", (bort,))
        conn.commit()
    
    click.echo(click.style(f"Машина '{bort}' удалена.", fg='green'))


@click.command(name='event')
@click.argument('bort', required=False)
@require_auth
def add_event_interactive(bort):
    """Интерактивное добавление события."""
    from datetime import date
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        while not bort:
            bort = click.prompt("Бортовой номер машины", type=str).strip()
        
        if not bort:
            click.echo(click.style("Бортовой номер не может быть пустым.", fg='yellow'))
            return
        
        machine = get_machine_info(cursor, bort)
        if not machine:
            click.echo(click.style(f"Машина '{bort}' не найдена.", fg='red'))
            return
        
        click.echo(click.style(f"\nМашина: {machine[0]} {machine[1]}", fg='green'))
        click.echo("-" * 50)
        
        event_type = click.prompt("Тип события", type=click.Choice(EVENT_TYPES), default='ремонт')
        description = click.prompt("Описание", type=str)
        parts = click.prompt("Запчасти (Enter - пропустить)", default="", show_default=False) or None
        hours_str = click.prompt("Моточасы (Enter - пропустить)", default="", show_default=False)
        hours = int(hours_str) if hours_str else None
        master = click.prompt("Мастер (Enter - пропустить)", default="", show_default=False) or None
        notes = click.prompt("Заметки (Enter - пропустить)", default="", show_default=False) or None
        
        use_today = click.confirm(f"Использовать сегодняшнюю дату ({date.today().isoformat()})?", default=True)
        event_date = date.today().isoformat() if use_today else click.prompt("Дата (ГГГГ-ММ-ДД)", type=str)
        
        user = Session.get_user()
        cursor.execute('''
            INSERT INTO events (bort, event_date, event_type, description, parts, hours, master, notes, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (bort, event_date, event_type, description, parts, hours, master, notes, user['username'], datetime.now().isoformat()))
        
        if hours is not None:
            cursor.execute("UPDATE machines SET hours = ? WHERE bort = ?", (hours, bort))
        
        conn.commit()
    
    click.echo(click.style(f"\nСобытие добавлено для '{bort}'!", fg='green'))


@click.command(name='events')
@click.argument('bort')
@click.option('--limit', default=10)
@require_auth
def show_events(bort, limit):
    """История событий."""
    bort = str(bort).strip()
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        machine = get_machine_info(cursor, bort)
        if not machine:
            click.echo(click.style(f"Машина '{bort}' не найдена.", fg='red'))
            return
        
        cursor.execute('''
            SELECT event_date, event_type, description, parts, hours, master, notes, created_by
            FROM events WHERE bort = ? ORDER BY event_date DESC, id DESC LIMIT ?
        ''', (bort, limit))
        events = cursor.fetchall()
    
    if not events:
        click.echo(click.style(f"Для {bort} нет событий.", fg='yellow'))
        return
    
    result = f"СОБЫТИЯ: {bort} ({machine[0]} {machine[1]})\n" + "=" * 50 + "\n\n"
    for ev in events:
        result += f"{ev[0]} | {ev[1].upper()}\n"
        result += f"  Описание: {ev[2]}\n"
        if ev[3]: result += f"  Запчасти: {ev[3]}\n"
        if ev[4]: result += f"  Моточасы: {ev[4]}\n"
        if ev[5]: result += f"  Мастер: {ev[5]}\n"
        if ev[6]: result += f"  Заметки: {ev[6]}\n"
        result += "  Добавил: " + (ev[7] or '?') + "\n"
        result += "-" * 30 + "\n"
    
    click.echo(click.style(make_double_frame(result), fg='green'))


@click.command(name='help')
def custom_help():
    """Справка."""
    help_text = """
╔══════════════════════════════════════════════════════════════════════╗
║                         MODERN - СПРАВКА                             ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  АУТЕНТИФИКАЦИЯ:                                                    ║
║    login               - вход в систему                              ║
║    logout              - выход из системы                            ║
║    whoami              - информация о текущем пользователе           ║
║                                                                      ║
║  УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ (только admin):                          ║
║    add-user            - добавить пользователя                       ║
║    list-users          - список пользователей                        ║
║                                                                      ║
║  ОСНОВНЫЕ КОМАНДЫ:                                                   ║
║    find <N>            - поиск машины (например, find 39)           ║
║    list                - список машин                                ║
║    stats               - статистика                                  ║
║                                                                      ║
║  УПРАВЛЕНИЕ ТЕХНИКОЙ:                                                ║
║    add-machine         - добавить машину (manager+)                  ║
║    edit-machine <N>    - редактировать машину (manager+)             ║
║    delete-machine <N>  - удалить машину (admin)                      ║
║                                                                      ║
║  УЧЁТ РЕМОНТОВ:                                                      ║
║    event [N]           - добавить событие                            ║
║    events <N>          - история событий                             ║
║                                                                      ║
║  ВЕБ-ИНТЕРФЕЙС:                                                      ║
║    web                 - запустить веб-интерфейс Streamlit           ║
║                                                                      ║
║  ДРУГОЕ:                                                            ║
║    calc                - калькулятор                                 ║
║    paint               - графический редактор                        ║
║    help                - эта справка                                 ║
║    exit                - выход                                       ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝

РОЛИ ПОЛЬЗОВАТЕЛЕЙ:
  admin    - полный доступ
  manager  - добавление/редактирование техники
  viewer   - только просмотр
"""
    click.echo(help_text)


# ------------------------ ОБОЛОЧКА ------------------------
@shell(prompt=lambda: f"{Session.get_user()['username'] if Session.is_authenticated() else 'guest'}@modern > ",
       intro=make_double_frame(
           "Вас приветствует modern!\n"
           "Введите 'login' для входа в систему.\n"
           "Введите 'help' для списка команд."
       ))
def cli():
    """Главная оболочка."""
    init_db()
    init_auth_db()
    init_data()


# Добавляем все команды
cli.add_command(login_command)
cli.add_command(logout_command)
cli.add_command(whoami_command)
cli.add_command(add_user_command)
cli.add_command(list_users_command)
cli.add_command(calc)
cli.add_command(paint)
cli.add_command(web_command)
cli.add_command(find_command)
cli.add_command(list_machines)
cli.add_command(stats)
cli.add_command(add_machine_interactive)
cli.add_command(edit_machine)
cli.add_command(delete_machine)
cli.add_command(add_event_interactive)
cli.add_command(show_events)
cli.add_command(custom_help)


# ------------------------ ЗАПУСК ------------------------
if __name__ == '__main__':
    cli()
