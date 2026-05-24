import streamlit as st
import datetime
import pandas as pd
import io

# 1. Инициализация базы данных (вместо часов добавили поле 'driver')
if "history" not in st.session_state:
    st.session_state.history = [
        {"id": 1, "type": "Самосвал", "model": "Камаз 65115", "date": datetime.date(2026, 5, 20), "work": "Перевозка песка", "driver": "Иванов И.И."},
        {"id": 2, "type": "Экскаватор", "model": "CAT 320", "date": datetime.date(2026, 5, 22), "work": "Рытье котлована", "driver": "Петров П.П."},
    ]

st.title("🚜 Учёт работы спецтехники")

tab1, tab2 = st.tabs(["🔍 Поиск и История", "➕ Добавить работу"])

# ==========================================
# ВКЛАДКА 1: ПОИСК, ИСТОРИЯ И ЭКСПОРТ
# ==========================================
with tab1:
    st.subheader("Фильтры поиска")
    f_col1, f_col2 = st.columns(2)
    
    with f_col1:
        search_type = st.selectbox("Тип техники", ["Все", "Самосвал", "Экскаватор"])
    with f_col2:
        search_query = st.text_input("Поиск по модели, работе или исполнителю")

    # Фильтрация данных
    filtered_history = st.session_state.history
    if search_type != "Все":
        filtered_history = [row for row in filtered_history if row["type"] == search_type]
    if search_query:
        search_query = search_query.lower()
        filtered_history = [
            row for row in filtered_history 
            if search_query in row["model"].lower() or 
               search_query in row["work"].lower() or 
               search_query in row["driver"].lower()
        ]

    # --- БЛОК ВЫГРУЗКИ В EXCEL ---
    if filtered_history:
        # Превращаем отфильтрованный список в таблицу Pandas
        df = pd.DataFrame(filtered_history)
        
        # Переименовываем колонки для красивого вывода в Excel
        df_excel = df.rename(columns={
            "type": "Тип техники",
            "model": "Модель",
            "date": "Дата",
            "work": "Выполненная работа",
            "driver": "Исполнитель"
        }).drop(columns=["id"]) # Удаляем технический ID

        # Создаем Excel-файл в оперативной памяти
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_excel.to_excel(writer, index=False, sheet_name='История работ')
        
        # Кнопка скачивания
        st.download_button(
            label="📥 Скачать текущую историю в Excel",
            data=buffer.getvalue(),
            file_name=f"history_export_{datetime.date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    # -----------------------------

    st.subheader("История выполненных работ")
    
    if not filtered_history:
        st.info("Записи не найдены по заданным фильтрам.")
    else:
        for record in filtered_history:
            with st.container(border=True):
                c1, c2, c3 = st.columns([1, 2, 1.5]) # Немного изменили пропорции колонок
                with c1:
                    st.markdown(f"**{record['type']}**")
                    st.caption(f"📅 {record['date'].strftime('%d.%m.%Y')}")
                with c2:
                    st.markdown(f"**Модель:** {record['model']}")
                    st.markdown(f"**Работа:** {record['work']}")
                with c3:
                    # Вместо часов выводим исполнителя
                    st.markdown("👤 **Исполнитель:**")
                    st.info(record['driver'])

# ==========================================
# ВКЛАДКА 2: ДОБАВЛЕНИЕ С ПОЛЕМ "ИСПОЛНИТЕЛЬ"
# ==========================================
with tab2:
    st.subheader("Ввод данных о выполненной работе")
    
    with st.form("add_work_form", clear_on_submit=True):
        form_col1, form_col2 = st.columns(2)
        with form_col1:
            tech_type = st.radio("Выберите тип техники:", ["Самосвал", "Экскаватор"], horizontal=True)
        with form_col2:
            tech_model = st.text_input("Марка и модель:")
        
        work_description = st.text_area("Описание выполненной работы:")
        
        form_col3, form_col4 = st.columns(2)
        with form_col3:
            work_date = st.date_input("Дата проведения работ:", datetime.date.today())
        with form_col4:
            # Заменили st.number_input на поле для ввода ФИО исполнителя
            tech_driver = st.text_input("ФИО исполнителя (Водитель / Машинист):")
        
        submit_btn = st.form_submit_button("Сохранить запись")
        
        if submit_btn:
            if not tech_model or not work_description or not tech_driver:
                st.error("Пожалуйста, заполните все поля (Модель, Описание и Исполнитель).")
            else:
                new_record = {
                    "id": len(st.session_state.history) + 1,
                    "type": tech_type,
                    "model": tech_model,
                    "date": work_date,
                    "work": work_description,
                    "driver": tech_driver # Записываем исполнителя
                }
                st.session_state.history.append(new_record)
                st.success(f"Запись для '{tech_model}' успешно добавлена!")
