"""Streamlit веб-интерфейс для учёта техники."""

import streamlit as st
import pandas as pd
from datetime import datetime

from modern.database import (
    get_db, init_db, init_data, machine_exists,
    STATUS_CHOICES, get_vehicle_types, add_vehicle_type
)
from modern.auth import (
    Session, init_auth_db, list_users, set_user_role, disable_user, add_user,
    get_mechanics, add_mechanic, update_mechanic, delete_mechanic
)

# ------------------------ НАСТРОЙКА СТРАНИЦЫ ------------------------
st.set_page_config(
    page_title="Modern - Учёт техники",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Скрытие бокового меню
st.markdown(
    "<style>[data-testid='stSidebarCollapse'] {display: none !important;}</style>",
    unsafe_allow_html=True
)

# ------------------------ ИНИЦИАЛИЗАЦИЯ ------------------------
init_db()
init_auth_db()
init_data()

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'current_page' not in st.session_state:
    st.session_state.current_page = "dashboard"


# ------------------------ СТРАНИЦА ВХОДА ------------------------
def login_page():
    """Страница входа в систему."""
    st.markdown("<h2 style='text-align: center;'>Вход в систему Modern</h2>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input("Имя пользователя")
            password = st.text_input("Пароль", type="password")
            
            if st.form_submit_button("Войти", use_container_width=True):
                if Session.login(username, password):
                    st.session_state.authenticated = True
                    st.session_state.user = Session.get_user()
                    st.session_state.current_page = "dashboard"
                    st.rerun()
                else:
                    st.error("Неверное имя пользователя или пароль")


# ------------------------ ОСНОВНОЙ ИНТЕРФЕЙС ------------------------
def main_interface():
    """Главный интерфейс после авторизации."""
    
    # Верхняя панель
    col_user, col_page, col_logout = st.columns([2, 2, 1])
    with col_user:
        st.markdown(
            f"Пользователь: **{st.session_state.user['username']}** | "
            f"Роль: **{st.session_state.user['role_name']}**"
        )
    with col_page:
        # Выбор страницы
        pages = ["Дашборд", "Поиск техники", "Добавление и редактирование", "Ремонты и события", "Механики"]
        if Session.is_admin():
            pages.append("Пользователи")
        
        selected_page = st.selectbox(
            "Раздел",
            pages,
            index=pages.index(st.session_state.current_page) if st.session_state.current_page in pages else 0,
            label_visibility="collapsed"
        )
        st.session_state.current_page = selected_page
    
    with col_logout:
        if st.button("Выйти", use_container_width=True):
            Session.logout()
            st.session_state.authenticated = False
            st.rerun()
    
    st.markdown("---")
    
    # Получаем типы техники из БД
    vehicle_types = get_vehicle_types()
    
    # =====================================================================
    # 1. ДАШБОРД
    # =====================================================================
    if st.session_state.current_page == "Дашборд":
        st.subheader("Сводная статистика парка техники")
        
        with get_db() as conn:
            df_machines = pd.read_sql_query(
                "SELECT * FROM machines WHERE bort IS NOT NULL", conn
            )
            df_events = pd.read_sql_query("SELECT * FROM events", conn)
            df_mechanics = pd.read_sql_query("SELECT * FROM mechanics WHERE active = 1", conn)
        
        if not df_machines.empty:
            total = len(df_machines)
            in_work = len(df_machines[df_machines["status"] == "working"]) if "working" in df_machines["status"].values else 0
            in_repair = len(df_machines[df_machines["status"] == "repair"]) if "repair" in df_machines["status"].values else 0
            
            # Метрики
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Всего машин", total)
            col2.metric("В работе", in_work)
            col3.metric("В ремонте", in_repair)
            col4.metric("Всего событий", len(df_events))
            
            st.markdown("---")
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**По типам техники:**")
                type_counts = df_machines["type"].value_counts().reset_index()
                type_counts.columns = ["Тип", "Количество"]
                st.dataframe(type_counts, use_container_width=True, hide_index=True)
            
            with col2:
                st.markdown("**По статусам:**")
                status_counts = df_machines["status"].value_counts().reset_index()
                status_counts.columns = ["Статус", "Количество"]
                st.dataframe(status_counts, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            st.markdown("**Последние события:**")
            if not df_events.empty:
                last_events = df_events.sort_values("event_date", ascending=False).head(10)
                cols = ["event_date", "bort", "event_type", "description"]
                st.dataframe(last_events[cols], use_container_width=True, hide_index=True)
            
            st.markdown("---")
            st.markdown("**Активные механики:**")
            if not df_mechanics.empty:
                st.dataframe(df_mechanics[["name", "specialty", "phone"]], use_container_width=True, hide_index=True)
            else:
                st.info("Нет активных механиков")
        else:
            st.info("База данных техники пуста. Добавьте машины во вкладке 'Добавление и редактирование'.")
    
    # =====================================================================
    # 2. ПОИСК ТЕХНИКИ
    # =====================================================================
    elif st.session_state.current_page == "Поиск техники":
        st.subheader("Поиск техники и история ремонтов")
        
        col1, col2 = st.columns(2)
        with col1:
            search_bort = st.text_input("Бортовой номер", placeholder="39 или 39Э")
        with col2:
            search_type = st.selectbox("Тип техники", ["Все"] + vehicle_types)
        
        query = "SELECT bort, type, model, hours, status, location, notes FROM machines WHERE bort IS NOT NULL"
        params = []
        
        if search_bort:
            query += " AND bort LIKE ?"
            params.append(f"%{search_bort}%")
        if search_type != "Все":
            query += " AND type = ?"
            params.append(search_type)
        
        query += " ORDER BY CAST(bort AS INTEGER) NULLS LAST, bort"
        
        with get_db() as conn:
            df = pd.read_sql_query(query, conn, params=params)
        
        if not df.empty:
            st.markdown(f"**Найдено машин: {len(df)}**")
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            st.markdown("### История обслуживания")
            
            selected_bort = st.selectbox("Выберите машину", df["bort"].tolist())
            
            if selected_bort:
                with get_db() as conn:
                    events = pd.read_sql_query(
                        """
                        SELECT event_date, event_type, description, parts, hours, master, notes
                        FROM events WHERE bort = ? ORDER BY event_date DESC
                        """,
                        conn,
                        params=[selected_bort]
                    )
                
                if not events.empty:
                    st.dataframe(events, use_container_width=True, hide_index=True)
                    
                    csv = events.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Скачать историю в CSV",
                        data=csv,
                        file_name=f"history_{selected_bort}.csv",
                        mime="text/csv"
                    )
                else:
                    st.info(f"Для машины {selected_bort} нет событий")
        else:
            st.warning("Машины, соответствующие критериям поиска, не найдены.")
    
    # =====================================================================
    # 3. ДОБАВЛЕНИЕ И РЕДАКТИРОВАНИЕ
    # =====================================================================
    elif st.session_state.current_page == "Добавление и редактирование":
        st.subheader("Управление парком техники")
        
        sub_tab1, sub_tab2, sub_tab3 = st.tabs([
            "Добавить машину",
            "Редактировать машину",
            "Типы техники"
        ])
        
        # ----- Вкладка: Добавление -----
        with sub_tab1:
            st.markdown("### Добавление новой единицы техники")
            
            with st.form("add_machine_form"):
                col1, col2 = st.columns(2)
                with col1:
                    bort = st.text_input("Бортовой номер", placeholder="39 или EXC-001").strip()
                    v_type = st.selectbox("Тип техники", vehicle_types)
                    model = st.text_input("Модель", placeholder="CAT 320")
                with col2:
                    status = st.selectbox("Статус", STATUS_CHOICES)
                    location = st.text_input("Местоположение", placeholder="Необязательно")
                    hours = st.number_input("Моточасы", min_value=0, step=100, value=0)
                
                serial = st.text_input("Заводской номер", placeholder="Необязательно")
                engine_model = st.text_input("Модель двигателя", placeholder="Необязательно")
                engine_number = st.text_input("Номер двигателя", placeholder="Необязательно")
                notes = st.text_area("Примечания", placeholder="Дополнительная информация")
                
                if st.form_submit_button("Сохранить машину", type="primary"):
                    if not bort or not model:
                        st.error("Заполните обязательные поля: Бортовой номер и Модель")
                    else:
                        with get_db() as conn:
                            cursor = conn.cursor()
                            if machine_exists(cursor, bort):
                                st.error(f"Машина с номером '{bort}' уже существует")
                            else:
                                cursor.execute('''
                                    INSERT INTO machines (bort, type, model, serial, engine_model, engine_number,
                                                         hours, status, location, notes, created_by, created_at)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                ''', (bort, v_type, model, serial, engine_model, engine_number,
                                      hours, status, location, notes,
                                      st.session_state.user['username'], datetime.now().isoformat()))
                                conn.commit()
                                st.success(f"Машина '{bort}' успешно добавлена!")
                                st.rerun()
        
        # ----- Вкладка: Редактирование -----
        with sub_tab2:
            st.markdown("### Редактирование данных машины")
            
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT bort, type, model FROM machines WHERE bort IS NOT NULL ORDER BY bort")
                machines = cursor.fetchall()
            
            if machines:
                selected = st.selectbox(
                    "Выберите машину",
                    [f"{row[0]} ({row[1]} {row[2]})" for row in machines]
                )
                selected_bort = selected.split()[0]
                
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT type, model, hours, status, location, notes, serial, engine_model, engine_number "
                        "FROM machines WHERE bort = ?",
                        (selected_bort,)
                    )
                    current = cursor.fetchone()
                
                if current:
                    with st.form("edit_machine_form"):
                        col1, col2 = st.columns(2)
                        with col1:
                            edit_type = st.selectbox(
                                "Тип техники",
                                vehicle_types,
                                index=vehicle_types.index(current[0]) if current[0] in vehicle_types else 0
                            )
                            edit_model = st.text_input("Модель", value=current[1])
                            edit_serial = st.text_input("Заводской номер", value=current[6] or "")
                        with col2:
                            edit_status = st.selectbox(
                                "Статус",
                                STATUS_CHOICES,
                                index=STATUS_CHOICES.index(current[3]) if current[3] in STATUS_CHOICES else 0
                            )
                            edit_location = st.text_input("Местоположение", value=current[4] or "")
                            edit_hours = st.number_input("Моточасы", min_value=0, step=100, value=int(current[2] or 0))
                        
                        edit_engine_model = st.text_input("Модель двигателя", value=current[7] or "")
                        edit_engine_number = st.text_input("Номер двигателя", value=current[8] or "")
                        edit_notes = st.text_area("Примечания", value=current[5] or "")
                        
                        if st.form_submit_button("Сохранить изменения", type="primary"):
                            with get_db() as conn:
                                cursor = conn.cursor()
                                cursor.execute('''
                                    UPDATE machines 
                                    SET type=?, model=?, hours=?, status=?, location=?, notes=?,
                                        serial=?, engine_model=?, engine_number=?,
                                        updated_by=?, updated_at=?
                                    WHERE bort=?
                                ''', (edit_type, edit_model, edit_hours, edit_status, edit_location, edit_notes,
                                      edit_serial, edit_engine_model, edit_engine_number,
                                      st.session_state.user['username'], datetime.now().isoformat(), selected_bort))
                                conn.commit()
                                st.success(f"Машина '{selected_bort}' обновлена")
                                st.rerun()
                    
                    if Session.is_admin():
                        st.markdown("---")
                        st.markdown("### Опасная зона")
                        if st.button("Удалить машину", type="secondary"):
                            if st.checkbox("Подтверждаю удаление машины и всех её событий"):
                                with get_db() as conn:
                                    cursor = conn.cursor()
                                    cursor.execute("DELETE FROM events WHERE bort = ?", (selected_bort,))
                                    cursor.execute("DELETE FROM machines WHERE bort = ?", (selected_bort,))
                                    conn.commit()
                                st.success(f"Машина '{selected_bort}' удалена")
                                st.rerun()
            else:
                st.info("В базе данных ещё нет машин")
        
        # ----- Вкладка: Типы техники -----
        with sub_tab3:
            st.markdown("### Справочник типов техники")
            
            st.markdown("**Текущие доступные типы:**")
            st.write(", ".join(vehicle_types))
            
            st.markdown("---")
            with st.form("add_type_form", clear_on_submit=True):
                new_type = st.text_input("Название нового типа", placeholder="Например: Автокран").strip()
                if st.form_submit_button("Добавить новый тип"):
                    if not new_type:
                        st.error("Название типа не может быть пустым")
                    elif new_type in vehicle_types:
                        st.error("Этот тип уже существует")
                    else:
                        add_vehicle_type(new_type)
                        st.success(f"Тип '{new_type}' добавлен")
                        st.rerun()
    
    # =====================================================================
    # 4. РЕМОНТЫ И СОБЫТИЯ
    # =====================================================================
    elif st.session_state.current_page == "Ремонты и события":
        st.subheader("Регистрация ремонтов, ТО и событий")
        
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT bort, type, model FROM machines WHERE bort IS NOT NULL ORDER BY bort")
            machines = cursor.fetchall()
        
        # Получаем список механиков
        mechanics = get_mechanics()
        mechanic_names = [""] + [m[1] for m in mechanics]  # Пустая строка для "не выбрано"
        
        if machines:
            with st.form("add_event_form"):
                col1, col2 = st.columns(2)
                with col1:
                    selected = st.selectbox(
                        "Машина",
                        [f"{row[0]} ({row[1]} {row[2]})" for row in machines]
                    )
                    bort = selected.split()[0]
                    event_type = st.selectbox(
                        "Тип события",
                        ["ремонт", "ТО", "диагностика", "замена", "заметка", "поломка"]
                    )
                    event_date = st.date_input("Дата события", value=datetime.today())
                
                with col2:
                    hours = st.number_input("Моточасы", min_value=0, step=100, value=0, help="Если указаны, обновят моточасы машины")
                    # Выбор мастера из списка механиков
                    master = st.selectbox("Мастер / Исполнитель", mechanic_names, index=0)
                    parts = st.text_input("Запчасти", placeholder="Например: Масляный фильтр, насос")
                
                description = st.text_area("Описание работ", placeholder="Что было сделано?", height=100)
                notes = st.text_area("Дополнительные заметки", placeholder="Любая дополнительная информация", height=80)
                
                if st.form_submit_button("Записать событие", type="primary"):
                    if not description.strip():
                        st.error("Заполните описание работ")
                    else:
                        with get_db() as conn:
                            cursor = conn.cursor()
                            cursor.execute('''
                                INSERT INTO events (bort, event_date, event_type, description, parts, hours, master, notes,
                                                   created_by, created_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (bort, event_date.isoformat(), event_type, description.strip(),
                                  parts.strip() if parts else None,
                                  hours if hours > 0 else None,
                                  master if master else None,
                                  notes.strip() if notes else None,
                                  st.session_state.user['username'],
                                  datetime.now().isoformat()))
                            
                            if hours > 0:
                                cursor.execute("UPDATE machines SET hours = ? WHERE bort = ?", (hours, bort))
                            
                            conn.commit()
                            st.success(f"Событие для машины '{bort}' добавлено")
                            st.rerun()
        else:
            st.info("Нет машин в базе данных. Сначала добавьте машины.")
    
    # =====================================================================
    # 5. МЕХАНИКИ
    # =====================================================================
    elif st.session_state.current_page == "Механики":
        st.subheader("Управление механиками")
        
        tab1, tab2 = st.tabs(["Список механиков", "Добавить механика"])
        
        with tab1:
            mechanics = get_mechanics()
            if mechanics:
                df = pd.DataFrame(mechanics, columns=["ID", "Имя", "Специализация", "Телефон"])
                st.dataframe(df, use_container_width=True, hide_index=True)
                
                if Session.is_admin():
                    st.markdown("---")
                    st.markdown("### Редактирование механика")
                    
                    selected_mechanic = st.selectbox(
                        "Выберите механика",
                        [f"{m[1]} ({m[2]})" for m in mechanics],
                        key="edit_mechanic"
                    )
                    mechanic_id = mechanics[[f"{m[1]} ({m[2]})" for m in mechanics].index(selected_mechanic)][0]
                    
                    with st.form("edit_mechanic_form"):
                        new_name = st.text_input("Имя", value=selected_mechanic.split(" (")[0])
                        new_specialty = st.text_input("Специализация", value=mechanics[[m[0] for m in mechanics].index(mechanic_id)][2] or "")
                        new_phone = st.text_input("Телефон", value=mechanics[[m[0] for m in mechanics].index(mechanic_id)][3] or "")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.form_submit_button("Сохранить изменения"):
                                if update_mechanic(mechanic_id, new_name, new_specialty or None, new_phone or None):
                                    st.success("Данные механика обновлены")
                                    st.rerun()
                                else:
                                    st.error("Ошибка при обновлении")
                        with col2:
                            if st.form_submit_button("Удалить механика", type="secondary"):
                                if delete_mechanic(mechanic_id):
                                    st.success("Механик удален")
                                    st.rerun()
                                else:
                                    st.error("Ошибка при удалении")
            else:
                st.info("Нет механиков")
        
        with tab2:
            if Session.is_manager():
                with st.form("add_mechanic_form"):
                    name = st.text_input("Имя механика", placeholder="Иванов И.И.")
                    specialty = st.text_input("Специализация", placeholder="Гидравлика, двигатели...")
                    phone = st.text_input("Телефон", placeholder="+7-999-123-45-67")
                    
                    if st.form_submit_button("Добавить механика"):
                        if not name:
                            st.error("Введите имя механика")
                        else:
                            add_mechanic(name, specialty or None, phone or None)
                            st.success(f"Механик '{name}' добавлен")
                            st.rerun()
            else:
                st.warning("Недостаточно прав для добавления механиков")
    
    # =====================================================================
    # 6. УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ (только admin)
    # =====================================================================
    elif st.session_state.current_page == "Пользователи" and Session.is_admin():
        st.subheader("Управление пользователями системы")
        
        users = list_users()
        if users:
            df = pd.DataFrame(users, columns=["ID", "Имя", "Роль", "ФИО", "Последний вход", "Активен"])
            df["Роль"] = df["Роль"].apply(lambda x: {3: "admin", 2: "manager", 1: "viewer"}.get(x, "viewer"))
            df["Активен"] = df["Активен"].apply(lambda x: "Да" if x else "Нет")
            
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            st.markdown("### Действия с пользователями")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Изменение роли**")
                users_list = [u[1] for u in users if u[1] != st.session_state.user['username']]
                if users_list:
                    user_to_edit = st.selectbox("Пользователь", users_list, key="role_user")
                    new_role = st.selectbox("Новая роль", ["admin", "manager", "viewer"], key="new_role")
                    if st.button("Изменить роль", key="change_role"):
                        if set_user_role(user_to_edit, new_role):
                            st.success(f"Роль пользователя '{user_to_edit}' изменена на '{new_role}'")
                            st.rerun()
                        else:
                            st.error("Ошибка при изменении роли")
                else:
                    st.info("Нет других пользователей")
            
            with col2:
                st.markdown("**Блокировка пользователя**")
                active_users = [u[1] for u in users if u[5] and u[1] != st.session_state.user['username']]
                if active_users:
                    user_to_disable = st.selectbox("Пользователь", active_users, key="disable_user")
                    if st.button("Заблокировать пользователя", key="disable_btn"):
                        if disable_user(user_to_disable):
                            st.success(f"Пользователь '{user_to_disable}' заблокирован")
                            st.rerun()
                        else:
                            st.error("Ошибка при блокировке")
                else:
                    st.info("Нет активных пользователей для блокировки")
            
            st.markdown("---")
            st.markdown("### Добавление нового пользователя")
            
            with st.form("add_user_form"):
                col1, col2 = st.columns(2)
                with col1:
                    new_username = st.text_input("Имя пользователя", placeholder="username")
                    new_password = st.text_input("Пароль", type="password", placeholder="......")
                with col2:
                    new_password2 = st.text_input("Повторите пароль", type="password", placeholder="......")
                    new_role = st.selectbox("Роль", ["viewer", "manager", "admin"])
                
                new_full_name = st.text_input("Полное имя", placeholder="Необязательно")
                
                if st.form_submit_button("Добавить пользователя"):
                    if not new_username or not new_password:
                        st.error("Заполните имя пользователя и пароль")
                    elif new_password != new_password2:
                        st.error("Пароли не совпадают")
                    else:
                        success, msg = add_user(new_username, new_password, new_role, new_full_name or None)
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
        else:
            st.info("Нет пользователей")


# ------------------------ ЗАПУСК ------------------------
if not st.session_state.authenticated:
    login_page()
else:
    main_interface()