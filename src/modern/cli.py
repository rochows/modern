"""Streamlit веб-интерфейс для учёта техники."""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import sys
from pathlib import Path

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent / "src"))

from modern.database import (
    get_db, init_db, init_data, machine_exists, get_machine_info,
    get_all_machines, STATUS_CHOICES, EVENT_TYPES, TYPE_SUFFIX, SUFFIX_TYPE
)
from modern.auth import (
    Session, init_auth_db, authenticate, add_user, list_users,
    set_user_role, disable_user, USER_ROLES, ROLE_NAMES
)

# ------------------------ НАСТРОЙКА СТРАНИЦЫ ------------------------
st.set_page_config(
    page_title="Modern - Учёт техники",
    page_icon="🚜",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Инициализация БД
init_db()
init_auth_db()
init_data()

# ------------------------ АУТЕНТИФИКАЦИЯ ------------------------
def init_session_state():
    """Инициализация session state."""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user' not in st.session_state:
        st.session_state.user = None
    if 'page' not in st.session_state:
        st.session_state.page = "login"


def login_page():
    """Страница входа."""
    st.title("🚜 Modern - Учёт техники")
    st.markdown("### Вход в систему")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input("Имя пользователя")
            password = st.text_input("Пароль", type="password")
            submitted = st.form_submit_button("Войти", use_container_width=True)
            
            if submitted:
                if Session.login(username, password):
                    st.session_state.authenticated = True
                    st.session_state.user = Session.get_user()
                    st.rerun()
                else:
                    st.error("Неверное имя пользователя или пароль")


def logout():
    """Выход из системы."""
    Session.logout()
    st.session_state.authenticated = False
    st.session_state.user = None
    st.rerun()


# ------------------------ ОСНОВНОЙ ИНТЕРФЕЙС ------------------------
def show_sidebar():
    """Показывает боковую панель."""
    with st.sidebar:
        st.image("https://img.icons8.com/color/96/tractor.png", width=80)
        st.markdown(f"### 🚜 Modern")
        st.markdown(f"**Пользователь:** {st.session_state.user['username']}")
        st.markdown(f"**Роль:** {st.session_state.user['role_name']}")
        st.markdown("---")
        
        # Навигация
        pages = {
            "📊 Дашборд": "dashboard",
            "🚜 Машины": "machines",
            "🔧 События": "events",
            "📈 Статистика": "stats",
            "👥 Пользователи": "users",
            "📄 Отчёты": "reports",
        }
        
        # Показываем только доступные страницы
        for label, page in pages.items():
            if page == "users" and not Session.is_admin():
                continue
            if st.button(label, use_container_width=True, key=page):
                st.session_state.page = page
                st.rerun()
        
        st.markdown("---")
        if st.button("🚪 Выход", use_container_width=True):
            logout()


def dashboard_page():
    """Дашборд."""
    st.title("📊 Дашборд")
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Основные метрики
        cursor.execute("SELECT COUNT(*) FROM machines WHERE bort IS NOT NULL")
        total_machines = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM events")
        total_events = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM machines WHERE status = 'repair'")
        in_repair = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM machines WHERE hours > 0")
        with_hours = cursor.fetchone()[0]
    
    # Карточки
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🚜 Всего машин", total_machines)
    with col2:
        st.metric("🔧 Событий", total_events)
    with col3:
        st.metric("⚙️ В ремонте", in_repair, delta=f"{in_repair/total_machines*100:.0f}%" if total_machines else None)
    with col4:
        st.metric("📊 С моточасами", with_hours)
    
    st.markdown("---")
    
    # Графики
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Машины по типам")
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT type, COUNT(*) FROM machines WHERE bort IS NOT NULL GROUP BY type ORDER BY COUNT(*) DESC")
            data = cursor.fetchall()
        if data:
            df = pd.DataFrame(data, columns=["Тип", "Количество"])
            fig = px.pie(df, values="Количество", names="Тип", title="Распределение по типам")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Нет данных")
    
    with col2:
        st.subheader("Статус машин")
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status, COUNT(*) FROM machines WHERE bort IS NOT NULL GROUP BY status")
            data = cursor.fetchall()
        if data:
            df = pd.DataFrame(data, columns=["Статус", "Количество"])
            fig = px.bar(df, x="Статус", y="Количество", title="Статус", color="Статус")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Нет данных")
    
    # Последние события
    st.subheader("📋 Последние события")
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT e.event_date, e.bort, m.type, m.model, e.event_type, e.description
            FROM events e
            JOIN machines m ON e.bort = m.bort
            ORDER BY e.event_date DESC, e.id DESC
            LIMIT 10
        ''')
        events = cursor.fetchall()
    
    if events:
        df = pd.DataFrame(events, columns=["Дата", "Борт", "Тип", "Модель", "Событие", "Описание"])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Нет событий")


def machines_page():
    """Управление машинами."""
    st.title("🚜 Управление машинами")
    
    # Вкладки
    tab1, tab2, tab3 = st.tabs(["📋 Список машин", "➕ Добавить машину", "✏️ Редактировать"])
    
    with tab1:
        # Фильтры
        col1, col2, col3 = st.columns(3)
        with col1:
            status_filter = st.selectbox("Статус", ["Все"] + STATUS_CHOICES)
        with col2:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT type FROM machines WHERE bort IS NOT NULL")
                types = [row[0] for row in cursor.fetchall()]
            type_filter = st.selectbox("Тип", ["Все"] + types)
        with col3:
            suffix_filter = st.selectbox("Суффикс", ["Все"] + list(SUFFIX_TYPE.keys()))
        
        # Получаем данные
        with get_db() as conn:
            cursor = conn.cursor()
            query = "SELECT bort, type, model, year, hours, status, location FROM machines WHERE bort IS NOT NULL"
            params = []
            
            if status_filter != "Все":
                query += " AND status = ?"
                params.append(status_filter)
            if type_filter != "Все":
                query += " AND type = ?"
                params.append(type_filter)
            if suffix_filter != "Все":
                query += " AND bort LIKE ?"
                params.append(f"%{suffix_filter}")
            
            query += " ORDER BY bort"
            cursor.execute(query, params)
            machines = cursor.fetchall()
        
        if machines:
            df = pd.DataFrame(machines, columns=["Борт", "Тип", "Модель", "Год", "Моточасы", "Статус", "Место"])
            
            # Цветовая индикация статуса
            def color_status(val):
                colors = {'working': 'green', 'repair': 'red', 'reserve': 'orange', 'written_off': 'gray'}
                return f'color: {colors.get(val, "black")}'
            
            st.dataframe(df.style.applymap(color_status, subset=['Статус']), use_container_width=True, hide_index=True)
            
            # Детальный просмотр
            st.markdown("---")
            st.subheader("🔍 Детальный просмотр")
            selected = st.selectbox("Выберите машину", [row[0] for row in machines])
            
            if selected:
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM machines WHERE bort = ?", (selected,))
                    row = cursor.fetchone()
                
                if row:
                    cols = st.columns(2)
                    fields = ["Борт", "Тип", "Модель", "Заводской номер", "Модель ДВС", "Номер ДВС", "Год", "Моточасы", "Статус", "Место", "Заметки"]
                    for i, field in enumerate(fields):
                        col = cols[i % 2]
                        col.metric(field, row[i+1] or "—")
        else:
            st.info("Нет машин")
    
    with tab2:
        if Session.is_manager():
            st.subheader("➕ Добавление новой машины")
            
            col1, col2 = st.columns(2)
            with col1:
                number = st.text_input("Цифровая часть номера", placeholder="39")
                suffix = st.selectbox("Суффикс", list(SUFFIX_TYPE.keys()))
                bort = f"{number}{suffix}" if number else ""
                if number and suffix:
                    st.info(f"Бортовой номер: **{bort}**")
            
            with col2:
                type_name = st.text_input("Тип техники", placeholder="Экскаватор, Самосвал...")
                model = st.text_input("Модель", placeholder="PC2000-8")
            
            serial = st.text_input("Заводской номер", placeholder="Необязательно")
            engine_model = st.text_input("Модель двигателя", placeholder="Необязательно")
            engine_number = st.text_input("Номер двигателя", placeholder="Необязательно")
            
            col1, col2 = st.columns(2)
            with col1:
                year = st.number_input("Год выпуска", min_value=1980, max_value=2030, step=1, value=None, placeholder="Необязательно")
                hours = st.number_input("Начальные моточасы", min_value=0, step=100, value=None, placeholder="Необязательно")
            with col2:
                status = st.selectbox("Статус", STATUS_CHOICES)
                location = st.text_input("Местоположение", placeholder="Необязательно")
            
            notes = st.text_area("Примечания", placeholder="Необязательно")
            
            if st.button("💾 Сохранить машину", type="primary"):
                if not number or not suffix or not type_name or not model:
                    st.error("Заполните обязательные поля")
                else:
                    with get_db() as conn:
                        cursor = conn.cursor()
                        if machine_exists(cursor, bort):
                            st.error(f"Машина '{bort}' уже существует")
                        else:
                            user = st.session_state.user
                            cursor.execute('''
                                INSERT INTO machines (bort, type, model, serial, engine_model, engine_number,
                                                     year, hours, status, location, notes, created_by, created_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (bort, type_name, model, serial, engine_model, engine_number,
                                  year, hours, status, location, notes, user['username'], datetime.now().isoformat()))
                            conn.commit()
                            st.success(f"Машина '{bort}' добавлена!")
                            st.rerun()
        else:
            st.warning("Недостаточно прав. Требуется роль manager или admin.")
    
    with tab3:
        if Session.is_manager():
            st.subheader("✏️ Редактирование машины")
            
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT bort, type, model FROM machines WHERE bort IS NOT NULL ORDER BY bort")
                machines_list = cursor.fetchall()
            
            if machines_list:
                selected_bort = st.selectbox("Выберите машину", [row[0] for row in machines_list])
                
                if selected_bort:
                    with get_db() as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT type, model, year, hours, status, location, notes FROM machines WHERE bort = ?", (selected_bort,))
                        current = cursor.fetchone()
                    
                    if current:
                        type_name = st.text_input("Тип техники", value=current[0])
                        model = st.text_input("Модель", value=current[1])
                        year = st.number_input("Год выпуска", min_value=1980, max_value=2030, value=current[2] or 2000, step=1)
                        hours = st.number_input("Моточасы", min_value=0, value=current[3] or 0, step=100)
                        status = st.selectbox("Статус", STATUS_CHOICES, index=STATUS_CHOICES.index(current[4]) if current[4] in STATUS_CHOICES else 0)
                        location = st.text_input("Местоположение", value=current[5] or "")
                        notes = st.text_area("Примечания", value=current[6] or "")
                        
                        if st.button("💾 Сохранить изменения", type="primary"):
                            with get_db() as conn:
                                cursor = conn.cursor()
                                user = st.session_state.user
                                cursor.execute('''
                                    UPDATE machines SET type=?, model=?, year=?, hours=?, status=?, location=?, notes=?, updated_by=?, updated_at=?
                                    WHERE bort=?
                                ''', (type_name, model, year, hours, status, location, notes, user['username'], datetime.now().isoformat(), selected_bort))
                                conn.commit()
                            st.success(f"Машина '{selected_bort}' обновлена!")
                            st.rerun()
                        
                        if Session.is_admin():
                            st.markdown("---")
                            if st.button("🗑️ Удалить машину", type="secondary"):
                                with get_db() as conn:
                                    cursor = conn.cursor()
                                    cursor.execute("DELETE FROM events WHERE bort = ?", (selected_bort,))
                                    cursor.execute("DELETE FROM machines WHERE bort = ?", (selected_bort,))
                                    conn.commit()
                                st.success(f"Машина '{selected_bort}' удалена!")
                                st.rerun()
            else:
                st.info("Нет машин")
        else:
            st.warning("Недостаточно прав. Требуется роль manager или admin.")


def events_page():
    """Управление событиями."""
    st.title("🔧 Управление событиями")
    
    tab1, tab2 = st.tabs(["📋 История событий", "➕ Добавить событие"])
    
    with tab1:
        # Выбор машины
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT bort, type, model FROM machines WHERE bort IS NOT NULL ORDER BY bort")
            machines = cursor.fetchall()
        
        selected_bort = st.selectbox("Выберите машину", [f"{row[0]} ({row[1]} {row[2]})" for row in machines], key="event_select")
        bort = selected_bort.split()[0] if selected_bort else None
        
        if bort:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT event_date, event_type, description, parts, hours, master, notes, created_by, created_at
                    FROM events WHERE bort = ? ORDER BY event_date DESC, id DESC
                ''', (bort,))
                events = cursor.fetchall()
            
            if events:
                df = pd.DataFrame(events, columns=["Дата", "Тип", "Описание", "Запчасти", "Моточасы", "Мастер", "Заметки", "Кто добавил", "Когда"])
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info(f"Нет событий для машины {bort}")
    
    with tab2:
        if Session.is_authenticated():
            st.subheader("➕ Добавление события")
            
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT bort, type, model FROM machines WHERE bort IS NOT NULL ORDER BY bort")
                machines = cursor.fetchall()
            
            selected_bort = st.selectbox("Машина", [f"{row[0]} ({row[1]} {row[2]})" for row in machines], key="event_add")
            bort = selected_bort.split()[0] if selected_bort else None
            
            if bort:
                event_type = st.selectbox("Тип события", EVENT_TYPES)
                description = st.text_area("Описание", placeholder="Что было сделано?")
                parts = st.text_input("Запчасти", placeholder="Необязательно")
                hours = st.number_input("Моточасы", min_value=0, step=100, value=None, placeholder="Необязательно")
                master = st.text_input("Мастер", placeholder="Необязательно")
                notes = st.text_area("Заметки", placeholder="Необязательно")
                event_date = st.date_input("Дата события", value=datetime.now())
                
                if st.button("💾 Сохранить событие", type="primary"):
                    if description:
                        with get_db() as conn:
                            cursor = conn.cursor()
                            user = st.session_state.user
                            cursor.execute('''
                                INSERT INTO events (bort, event_date, event_type, description, parts, hours, master, notes, created_by, created_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (bort, event_date.isoformat(), event_type, description, parts or None, hours or None, master or None, notes or None, user['username'], datetime.now().isoformat()))
                            
                            if hours:
                                cursor.execute("UPDATE machines SET hours = ? WHERE bort = ?", (hours, bort))
                            
                            conn.commit()
                        st.success(f"Событие добавлено для машины {bort}!")
                        st.rerun()
                    else:
                        st.error("Заполните описание")
        else:
            st.warning("Требуется авторизация")


def stats_page():
    """Статистика."""
    st.title("📈 Статистика")
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Общая статистика
        cursor.execute("SELECT COUNT(*) FROM machines WHERE bort IS NOT NULL")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM events")
        events_total = cursor.fetchone()[0]
        
        cursor.execute("SELECT AVG(hours) FROM machines WHERE hours IS NOT NULL")
        avg_hours = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(hours) FROM machines WHERE hours IS NOT NULL")
        total_hours = cursor.fetchone()[0]
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🚜 Всего машин", total)
    with col2:
        st.metric("🔧 Всего событий", events_total)
    with col3:
        st.metric("⏱️ Средние моточасы", f"{avg_hours:.0f}" if avg_hours else "—")
    with col4:
        st.metric("📊 Общие моточасы", f"{total_hours:,.0f}" if total_hours else "—")
    
    st.markdown("---")
    
    # Графики
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Машины по типам")
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT type, COUNT(*) FROM machines WHERE bort IS NOT NULL GROUP BY type")
            data = cursor.fetchall()
        if data:
            df = pd.DataFrame(data, columns=["Тип", "Количество"])
            fig = px.bar(df, x="Тип", y="Количество", title="Количество по типам", color="Тип")
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("События по месяцам")
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT strftime('%Y-%m', event_date) as month, COUNT(*) FROM events GROUP BY month ORDER BY month")
            data = cursor.fetchall()
        if data:
            df = pd.DataFrame(data, columns=["Месяц", "Количество"])
            fig = px.line(df, x="Месяц", y="Количество", title="Динамика событий", markers=True)
            st.plotly_chart(fig, use_container_width=True)
    
    # Топ машин по ремонтам
    st.subheader("🔧 Топ машин по количеству ремонтов")
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT e.bort, m.type, m.model, COUNT(*) as repair_count
            FROM events e
            JOIN machines m ON e.bort = m.bort
            WHERE e.event_type IN ('ремонт', 'замена')
            GROUP BY e.bort
            ORDER BY repair_count DESC
            LIMIT 10
        ''')
        data = cursor.fetchall()
    
    if data:
        df = pd.DataFrame(data, columns=["Борт", "Тип", "Модель", "Ремонтов"])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Нет данных")


def users_page():
    """Управление пользователями (только админ)."""
    if not Session.is_admin():
        st.error("Доступ запрещён. Требуются права администратора.")
        return
    
    st.title("👥 Управление пользователями")
    
    tab1, tab2 = st.tabs(["📋 Список пользователей", "➕ Добавить пользователя"])
    
    with tab1:
        users = list_users()
        if users:
            df = pd.DataFrame(users, columns=["ID", "Имя", "Роль", "ФИО", "Последний вход", "Активен"])
            df["Роль"] = df["Роль"].apply(lambda x: ROLE_NAMES.get(x, 'viewer'))
            df["Активен"] = df["Активен"].apply(lambda x: "✅" if x else "❌")
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            st.subheader("Управление")
            col1, col2 = st.columns(2)
            with col1:
                user_to_edit = st.selectbox("Выберите пользователя", [row[1] for row in users if row[1] != st.session_state.user['username']])
                new_role = st.selectbox("Новая роль", ['admin', 'manager', 'viewer'])
                if st.button("Изменить роль"):
                    if set_user_role(user_to_edit, new_role):
                        st.success(f"Роль {user_to_edit} изменена на {new_role}")
                        st.rerun()
            with col2:
                user_to_disable = st.selectbox("Заблокировать пользователя", [row[1] for row in users if row[5] and row[1] != st.session_state.user['username']])
                if st.button("Заблокировать", type="secondary"):
                    if disable_user(user_to_disable):
                        st.success(f"Пользователь {user_to_disable} заблокирован")
                        st.rerun()
        else:
            st.info("Нет пользователей")
    
    with tab2:
        st.subheader("➕ Добавление пользователя")
        with st.form("add_user_form"):
            username = st.text_input("Имя пользователя")
            password = st.text_input("Пароль", type="password")
            password2 = st.text_input("Повторите пароль", type="password")
            role = st.selectbox("Роль", ['viewer', 'manager', 'admin'])
            full_name = st.text_input("Полное имя", placeholder="Необязательно")
            
            if st.form_submit_button("Добавить"):
                if not username or not password:
                    st.error("Заполните имя и пароль")
                elif password != password2:
                    st.error("Пароли не совпадают")
                else:
                    success, msg = add_user(username, password, role, full_name or None)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)


def reports_page():
    """Отчёты."""
    st.title("📄 Отчёты")
    
    report_type = st.selectbox("Тип отчёта", ["Все машины", "События по периоду", "Машины в ремонте", "ТО просрочено"])
    
    if report_type == "Все машины":
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT bort, type, model, year, hours, status, location, notes FROM machines WHERE bort IS NOT NULL ORDER BY bort")
            machines = cursor.fetchall()
        
        if machines:
            df = pd.DataFrame(machines, columns=["Борт", "Тип", "Модель", "Год", "Моточасы", "Статус", "Место", "Заметки"])
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Скачать CSV", csv, "machines.csv", "text/csv")
    
    elif report_type == "События по периоду":
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Начальная дата", value=datetime.now().replace(month=1, day=1))
        with col2:
            end_date = st.date_input("Конечная дата", value=datetime.now())
        
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT e.event_date, e.bort, m.type, m.model, e.event_type, e.description, e.master
                FROM events e
                JOIN machines m ON e.bort = m.bort
                WHERE e.event_date BETWEEN ? AND ?
                ORDER BY e.event_date DESC
            ''', (start_date.isoformat(), end_date.isoformat()))
            events = cursor.fetchall()
        
        if events:
            df = pd.DataFrame(events, columns=["Дата", "Борт", "Тип", "Модель", "Событие", "Описание", "Мастер"])
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Скачать CSV", csv, f"events_{start_date}_{end_date}.csv", "text/csv")
        else:
            st.info("Нет событий за выбранный период")
    
    elif report_type == "Машины в ремонте":
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT bort, type, model, hours, location, notes FROM machines WHERE status = 'repair' ORDER BY bort")
            machines = cursor.fetchall()
        
        if machines:
            df = pd.DataFrame(machines, columns=["Борт", "Тип", "Модель", "Моточасы", "Место", "Заметки"])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Нет машин в ремонте")
    
    elif report_type == "ТО просрочено":
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT bort, type, model, hours, last_maintenance, location
                FROM machines 
                WHERE last_maintenance IS NOT NULL 
                AND julianday('now') - julianday(last_maintenance) > 365
                ORDER BY last_maintenance
            ''')
            machines = cursor.fetchall()
        
        if machines:
            df = pd.DataFrame(machines, columns=["Борт", "Тип", "Модель", "Моточасы", "Последнее ТО", "Место"])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Нет машин с просроченным ТО")


# ------------------------ ГЛАВНАЯ ЛОГИКА ------------------------
def main():
    """Главная функция."""
    init_session_state()
    
    if not st.session_state.authenticated:
        login_page()
    else:
        show_sidebar()
        
        # Отображение выбранной страницы
        page = st.session_state.get('page', 'dashboard')
        
        if page == 'dashboard':
            dashboard_page()
        elif page == 'machines':
            machines_page()
        elif page == 'events':
            events_page()
        elif page == 'stats':
            stats_page()
        elif page == 'users':
            users_page()
        elif page == 'reports':
            reports_page()
        else:
            dashboard_page()



if __name__ == "__main__":
    main()