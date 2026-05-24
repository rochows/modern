import streamlit as st
import pandas as pd
from datetime import datetime

# Настройка страницы (широкий экран)
st.set_page_config(page_title="Учёт Техники и Ремонтов", layout="wide")

# Инициализация базы данных в сессии (имитация БД)
if "vehicle_types" not in st.session_state:
    st.session_state.vehicle_types = ["Экскаватор", "Бульдозер", "Самосвал", "Грейдер"]

if "vehicles" not in st.session_state:
    st.session_state.vehicles = pd.DataFrame([
        {"board_id": "EXC-001", "type": "Экскаватор", "model": "CAT 320", "status": "В работе"},
        {"board_id": "DZR-002", "type": "Бульдозер", "model": "Komatsu D65", "status": "В ремонте"}
    ])

if "records" not in st.session_state:
    st.session_state.records = pd.DataFrame([
        {"date": "2026-05-20", "board_id": "DZR-002", "type": "Ремонт", "description": "Замена гидроцилиндра отвала"},
        {"date": "2026-05-24", "board_id": "EXC-001", "type": "Событие", "description": "Плановое ТО-1"}
    ])

# Главный заголовок
st.title("Система управления автопарком")
st.caption("Учёт техники, ремонтов и эксплуатационных событий")

# Верхнее меню (Вкладки)
tab_search, tab_add_vehicle, tab_add_record, tab_settings = st.tabs([
    "Поиск и Просмотр", 
    "Добавление / Редактирование техники", 
    "Добавление ремонта / события", 
    "Настройка типов техники"
])

# =====================================================================
# ВКЛАДКА 1: ПОИСК И ПРОСМОТР
# =====================================================================
with tab_search:
    st.subheader("Поиск по автопарку")
    
    col1, col2 = st.columns(2)
    with col1:
        search_id = st.text_input("Поиск по бортовому номеру").strip().upper()
    with col2:
        search_type = st.selectbox("Фильтр по типу", ["Все типы"] + st.session_state.vehicle_types)
    
    # Фильтрация данных техники
    df_filtered = st.session_state.vehicles.copy()
    if search_id:
        df_filtered = df_filtered[df_filtered["board_id"].str.contains(search_id)]
    if search_type != "Все типы":
        df_filtered = df_filtered[df_filtered["type"] == search_type]
        
    st.markdown("### Сводная таблица техники")
    st.dataframe(df_filtered, use_container_width=True, hide_index=True)
    
    # История ремонтов и событий для выбранной техники
    st.markdown("---")
    st.subheader("История ремонтов и событий")
    
    if not df_filtered.empty:
        selected_board_id = st.selectbox(
            "Выберите бортовой номер для просмотра истории", 
            df_filtered["board_id"].unique()
        )
        
        df_records_filtered = st.session_state.records[
            st.session_state.records["board_id"] == selected_board_id
        ]
        
        if not df_records_filtered.empty:
            st.dataframe(df_records_filtered, use_container_width=True, hide_index=True)
        else:
            st.info("По данной технике записей о ремонтах или событиях не найдено.")
    else:
        st.warning("Техника для отображения истории отсутствует.")

# =====================================================================
# ВКЛАДКА 2: ДОБАВЛЕНИЕ / РЕДАКТИРОВАНИЕ ТЕХНИКИ
# =====================================================================
with tab_add_vehicle:
    st.subheader("Управление карточками техники")
    
    mode = st.radio("Выберите действие", ["Добавить новую технику", "Редактировать существующую"], horizontal=True)
    
    if mode == "Добавить новую технику":
        with st.form("add_vehicle_form"):
            b_id = st.text_input("Бортовой номер (уникальный)", placeholder="Например, DZR-005").strip().upper()
            v_type = st.selectbox("Тип техники", st.session_state.vehicle_types)
            v_model = st.text_input("Модель / Марка", placeholder="Например, Shantui SD16")
            v_status = st.selectbox("Текущий статус", ["В работе", "В ремонте", "В простое", "Списан"])
            
            submit = st.form_submit_button("Сохранить в базу")
            if submit:
                if not b_id:
                    st.error("Бортовой номер не может быть пустым.")
                elif b_id in st.session_state.vehicles["board_id"].values:
                    st.error(f"Техника с бортовым номером {b_id} уже существует.")
                else:
                    new_row = {"board_id": b_id, "type": v_type, "model": v_model, "status": v_status}
                    st.session_state.vehicles = pd.concat([st.session_state.vehicles, pd.DataFrame([new_row])], ignore_index=True)
                    st.success(f"Техника {b_id} успешно добавлена!")
                    st.rerun()

    elif mode == "Редактировать существующую":
        if not st.session_state.vehicles.empty:
            edit_id = st.selectbox("Выберите технику для редактирования", st.session_state.vehicles["board_id"])
            current_data = st.session_state.vehicles[st.session_state.vehicles["board_id"] == edit_id].iloc[0]
            
            with st.form("edit_vehicle_form"):
                v_type = st.selectbox(
                    "Тип техники", 
                    st.session_state.vehicle_types, 
                    index=st.session_state.vehicle_types.index(current_data["type"]) if current_data["type"] in st.session_state.vehicle_types else 0
                )
                v_model = st.text_input("Модель / Марка", value=current_data["model"])
                v_status = st.selectbox(
                    "Текущий статус", 
                    ["В работе", "В ремонте", "В простое", "Списан"],
                    index=["В работе", "В ремонте", "В простое", "Списан"].index(current_data["status"])
                )
                
                submit = st.form_submit_button("Обновить данные")
                if submit:
                    idx = st.session_state.vehicles[st.session_state.vehicles["board_id"] == edit_id].index[0]
                    st.session_state.vehicles.at[idx, "type"] = v_type
                    st.session_state.vehicles.at[idx, "model"] = v_model
                    st.session_state.vehicles.at[idx, "status"] = v_status
                    st.success(f"Данные техники {edit_id} успешно обновлены!")
                    st.rerun()
        else:
            st.info("В базе еще нет техники для редактирования.")

# =====================================================================
# ВКЛАДКА 3: ДОБАВЛЕНИЕ РЕМОНТА / СОБЫТИЯ
# =====================================================================
with tab_add_record:
    st.subheader("Регистрация нового события или ремонта")
    
    if not st.session_state.vehicles.empty:
        with st.form("add_record_form"):
            col_rec1, col_rec2 = st.columns(2)
            
            with col_rec1:
                rec_board_id = st.selectbox("Бортовой номер техники", st.session_state.vehicles["board_id"])
                rec_type = st.selectbox("Тип записи", ["Ремонт", "Событие", "Заправка", "Инспекция"])
            
            with col_rec2:
                rec_date = st.date_input("Дата", value=datetime.today())
                rec_desc = st.text_area("Описание (что было сделано / что произошло)")
                
            submit_record = st.form_submit_button("Внести запись")
            if submit_record:
                if not rec_desc.strip():
                    st.error("Пожалуйста, заполните описание.")
                else:
                    new_record = {
                        "date": str(rec_date),
                        "board_id": rec_board_id,
                        "type": rec_type,
                        "description": rec_desc.strip()
                    }
                    st.session_state.records = pd.concat([st.session_state.records, pd.DataFrame([new_record])], ignore_index=True)
                    st.success("Запись успешно добавлена в историю!")
                    st.rerun()
    else:
        st.warning("Сначала добавьте хотя бы одну единицу техники на вкладке управления.")

# =====================================================================
# ВКЛАДКА 4: НАСТРОЙКА ТИПОВ ТЕХНИКИ
# =====================================================================
with tab_settings:
    st.subheader("Управление справочником типов техники")
    
    # Отображение текущих типов
    st.markdown("**Текущие доступные типы:**")
    st.write(", ".join(st.session_state.vehicle_types))
    
    # Форма добавления нового типа
    with st.form("add_type_form", clear_on_submit=True):
        new_type = st.text_input("Название нового типа техники (например, Автокран)", placeholder="Введите тип...").strip()
        submit_type = st.form_submit_button("Добавить тип")
        
        if submit_type:
            if not new_type:
                st.error("Название не может быть пустым.")
            elif new_type in st.session_state.vehicle_types:
                st.error("Такой тип техники уже существует.")
            else:
                st.session_state.vehicle_types.append(new_type)
                st.success(f"Тип '{new_type}' успешно добавлен в справочник!")
                st.rerun()
