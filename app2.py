import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
from io import BytesIO
import plotly.express as px
import plotly.graph_objects as go
from collections import Counter

# ==============================================================================
# 1. НАСТРОЙКА СТРАНИЦЫ
# ==============================================================================
st.set_page_config(
    page_title="Учет техники и ремонтов",
    layout="wide"
)

# ==============================================================================
# 2. ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ
# ==============================================================================

if "equipment_db" not in st.session_state:
    st.session_state.equipment_db = [
        {"id": "CAT-320", "name": "Caterpillar 320", "type": "Экскаватор", "status": "Доступен", "hours": 1350, "counter_ok": True},
        {"id": "KOM-D65", "name": "Komatsu D65EX", "type": "Бульдозер", "status": "Ремонт", "hours": 3480, "counter_ok": False},
        {"id": "BEL-755", "name": "БелАЗ 7555", "type": "Самосвал", "status": "В работе", "hours": 5200, "counter_ok": True},
        {"id": "HIT-350", "name": "Hitachi ZX350", "type": "Экскаватор", "status": "Доступен", "hours": 890, "counter_ok": True},
        {"id": "KOM-WB140", "name": "Komatsu WB140", "type": "Погрузчик", "status": "В работе", "hours": 2100, "counter_ok": True},
    ]

if "service_db" not in st.session_state:
    st.session_state.service_db = [
        {"id": 1, "eq_id": "CAT-320", "date": date(2026, 5, 10), "type": "ТО", "hours": 1300, "mechanic": "Иванов И.И.", 
         "description": "Замена масла и фильтров", "parts": ["Масло моторное", "Масляный фильтр"]},
        {"id": 2, "eq_id": "KOM-D65", "date": date(2026, 5, 20), "type": "Ремонт", "hours": None, "mechanic": "Петров П.П.", 
         "description": "Ремонт гидроцилиндра отвала", "parts": ["Уплотнения", "Шток"]},
        {"id": 3, "eq_id": "BEL-755", "date": date(2026, 5, 15), "type": "Ремонт", "hours": 5100, "mechanic": "Сидоров С.С.", 
         "description": "Замена тормозных колодок", "parts": ["Тормозные колодки"]},
        {"id": 4, "eq_id": "CAT-320", "date": date(2026, 5, 5), "type": "Диагностика", "hours": 1280, "mechanic": "Иванов И.И.", 
         "description": "Проверка гидравлики", "parts": []},
        {"id": 5, "eq_id": "HIT-350", "date": date(2026, 5, 18), "type": "ТО", "hours": 880, "mechanic": "Кузнецов К.К.", 
         "description": "Замена масла в двигателе", "parts": ["Масло моторное"]},
        {"id": 6, "eq_id": "BEL-755", "date": date(2026, 4, 25), "type": "Ремонт", "hours": 4900, "mechanic": "Петров П.П.", 
         "description": "Ремонт подвески", "parts": ["Амортизатор", "Сайлентблоки"]},
        {"id": 7, "eq_id": "KOM-WB140", "date": date(2026, 5, 1), "type": "Диагностика", "hours": 2100, "mechanic": "Сидоров С.С.", 
         "description": "Диагностика АКПП", "parts": []},
    ]

if "equipment_types" not in st.session_state:
    st.session_state.equipment_types = [
        {"name": "Экскаватор", "maintenance_interval": 500},
        {"name": "Бульдозер", "maintenance_interval": 400},
        {"name": "Самосвал", "maintenance_interval": 600},
        {"name": "Погрузчик", "maintenance_interval": 450},
    ]

if "mechanics_db" not in st.session_state:
    st.session_state.mechanics_db = [
        {"id": 1, "name": "Иванов И.И.", "specialization": "Гидравлика", "phone": "+7(999)123-45-67"},
        {"id": 2, "name": "Петров П.П.", "specialization": "Двигатели", "phone": "+7(999)234-56-78"},
        {"id": 3, "name": "Сидоров С.С.", "specialization": "Электрика", "phone": "+7(999)345-67-89"},
        {"id": 4, "name": "Кузнецов К.К.", "specialization": "Трансмиссия", "phone": "+7(999)456-78-90"},
    ]

if "parts_inventory" not in st.session_state:
    st.session_state.parts_inventory = [
        {"name": "Масло моторное", "unit": "л", "usage_count": 6},
        {"name": "Масляный фильтр", "unit": "шт", "usage_count": 1},
        {"name": "Тормозные колодки", "unit": "компл", "usage_count": 1},
        {"name": "Уплотнения", "unit": "компл", "usage_count": 1},
        {"name": "Шток", "unit": "шт", "usage_count": 1},
        {"name": "Амортизатор", "unit": "шт", "usage_count": 1},
        {"name": "Сайлентблоки", "unit": "компл", "usage_count": 1},
    ]

if "documents_db" not in st.session_state:
    st.session_state.documents_db = [
        {"id": 1, "title": "Паспорт Caterpillar 320", "eq_id": "CAT-320", "type": "Паспорт", "date": date(2025, 1, 10)},
        {"id": 2, "title": "Акт осмотра Komatsu D65EX", "eq_id": "KOM-D65", "type": "Акт", "date": date(2026, 4, 15)},
    ]

# ==============================================================================
# 3. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==============================================================================

def get_maintenance_interval(equipment_type):
    for t in st.session_state.equipment_types:
        if t["name"] == equipment_type:
            return t["maintenance_interval"]
    return 500

def get_next_to_date(equipment):
    if not equipment["counter_ok"]:
        return "Нет данных"
    last_service = [s for s in st.session_state.service_db if s["eq_id"] == equipment["id"] and s["type"] == "ТО" and s["hours"] is not None]
    if last_service:
        last_hours = max([s["hours"] for s in last_service])
        interval = get_maintenance_interval(equipment["type"])
        next_hours = last_hours + interval
        if next_hours <= equipment["hours"]:
            return "Просрочено"
        hours_left = next_hours - equipment["hours"]
        days_left = int(hours_left / 8)
        return f"через {days_left} дн. ({hours_left} ч.)"
    return "Требуется ТО"

def get_downtime_days(equipment):
    if equipment["status"] == "Ремонт":
        last_repair = [s for s in st.session_state.service_db if s["eq_id"] == equipment["id"] and s["type"] == "Ремонт"]
        if last_repair:
            last_date = max([s["date"] for s in last_repair])
            return (date.today() - last_date).days
    return 0

def export_to_excel(data, filename):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        pd.DataFrame(data).to_excel(writer, sheet_name='Отчет', index=False)
    return output.getvalue()

# ==============================================================================
# 4. ЗАГОЛОВОК
# ==============================================================================
st.title("Учет техники и ремонтов")

# ==============================================================================
# 5. ГЛАВНЫЕ ВКЛАДКИ
# ==============================================================================
main_tabs = st.tabs(["Обзор", "Техника", "Ремонты", "Механики", "Запчасти", "Документы", "Отчеты"])

# ==============================================================================
# ВКЛАДКА 1: ОБЗОР
# ==============================================================================
with main_tabs[0]:
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Всего техники", len(st.session_state.equipment_db))
    with col2:
        st.metric("В ремонте", len([e for e in st.session_state.equipment_db if e["status"] == "Ремонт"]))
    with col3:
        month_repairs = len([s for s in st.session_state.service_db if s["date"] > date.today() - timedelta(days=30) and s["type"] == "Ремонт"])
        st.metric("Ремонтов за месяц", month_repairs)
    with col4:
        avg_hours = sum(e["hours"] for e in st.session_state.equipment_db if e["counter_ok"]) / len(st.session_state.equipment_db) if st.session_state.equipment_db else 0
        st.metric("Средние моточасы", f"{avg_hours:.0f}")
    
    st.markdown("---")
    
    st.subheader("Ближайшее плановое обслуживание")
    to_list = []
    for eq in st.session_state.equipment_db:
        if eq["counter_ok"]:
            next_to = get_next_to_date(eq)
            to_list.append({"Техника": f"{eq['name']} ({eq['id']})", "Тип": eq["type"], "Моточасы": eq["hours"], "Следующее ТО": next_to})
    
    if to_list:
        st.dataframe(pd.DataFrame(to_list), use_container_width=True, hide_index=True)
    else:
        st.info("Нет данных")
    
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.subheader("Техника в простое")
        downtime_list = []
        for eq in st.session_state.equipment_db:
            days = get_downtime_days(eq)
            if days > 0:
                downtime_list.append({"Техника": eq["name"], "Статус": eq["status"], "Простой": f"{days} дн."})
        
        if downtime_list:
            st.dataframe(pd.DataFrame(downtime_list), use_container_width=True, hide_index=True)
        else:
            st.info("Нет техники в простое")
        
        st.subheader("Частые поломки")
        failure_counts = Counter()
        for s in st.session_state.service_db:
            if s["type"] == "Ремонт":
                words = s["description"].lower().split()[:5]
                for w in words:
                    if len(w) > 3:
                        failure_counts[w] += 1
        
        if failure_counts:
            for f, count in failure_counts.most_common(5):
                st.write(f"• {f}: {count} раз(а)")
        else:
            st.info("Нет данных")
    
    with col_right:
        st.subheader("Загруженность механиков")
        mechanic_work = Counter()
        for s in st.session_state.service_db:
            mechanic_work[s.get("mechanic", "Не указан")] += 1
        
        if mechanic_work:
            for m, count in mechanic_work.most_common():
                st.write(f"• {m}: {count} работ")
        else:
            st.info("Нет данных")
        
        st.subheader("Расход запчастей")
        parts_usage = Counter()
        for s in st.session_state.service_db:
            for p in s.get("parts", []):
                parts_usage[p] += 1
        
        if parts_usage:
            for p, count in parts_usage.most_common(5):
                st.write(f"• {p}: {count} шт.")
        else:
            st.info("Нет данных")

# ==============================================================================
# ВКЛАДКА 2: ТЕХНИКА
# ==============================================================================
with main_tabs[1]:
    tech_tabs = st.tabs(["Список", "Добавить", "Редактировать", "Типы техники"])
    
    with tech_tabs[0]:
        search = st.text_input("Поиск", placeholder="ID или название...")
        filtered = st.session_state.equipment_db
        if search:
            filtered = [x for x in filtered if search.lower() in x["name"].lower() or search.lower() in x["id"].lower()]
        
        if filtered:
            data = []
            for x in filtered:
                data.append({
                    "ID": x["id"], "Название": x["name"], "Тип": x["type"],
                    "Статус": x["status"], "Моточасы": x["hours"] if x["counter_ok"] else "—"
                })
            st.dataframe(data, use_container_width=True, hide_index=True)
    
    with tech_tabs[1]:
        with st.form("add_equipment"):
            col1, col2 = st.columns(2)
            with col1:
                new_id = st.text_input("ID")
                new_name = st.text_input("Название")
                type_names = [t["name"] for t in st.session_state.equipment_types]
                new_type = st.selectbox("Тип", type_names)
            with col2:
                new_status = st.selectbox("Статус", ["Доступен", "В работе", "Ремонт"])
                counter_ok = st.checkbox("Счетчик исправен", True)
                new_hours = st.number_input("Моточасы", min_value=0, step=10, disabled=not counter_ok)
            
            if st.form_submit_button("Добавить"):
                if new_id and new_name:
                    st.session_state.equipment_db.append({
                        "id": new_id, "name": new_name, "type": new_type,
                        "status": new_status, "hours": new_hours if counter_ok else 0, "counter_ok": counter_ok
                    })
                    st.success("Добавлено")
                    st.rerun()
    
    with tech_tabs[2]:
        ids = [x["id"] for x in st.session_state.equipment_db]
        if ids:
            selected = st.selectbox("Выберите технику", ids)
            idx = next(i for i, x in enumerate(st.session_state.equipment_db) if x["id"] == selected)
            item = st.session_state.equipment_db[idx]
            
            with st.form("edit_equipment"):
                col1, col2 = st.columns(2)
                with col1:
                    up_name = st.text_input("Название", value=item["name"])
                    type_names = [t["name"] for t in st.session_state.equipment_types]
                    type_idx = type_names.index(item["type"]) if item["type"] in type_names else 0
                    up_type = st.selectbox("Тип", type_names, index=type_idx)
                    up_status = st.selectbox("Статус", ["Доступен", "В работе", "Ремонт"], 
                                            index=["Доступен", "В работе", "Ремонт"].index(item["status"]))
                with col2:
                    up_counter = st.checkbox("Счетчик исправен", value=item["counter_ok"])
                    up_hours = st.number_input("Моточасы", value=item["hours"], disabled=not up_counter)
                
                c1, c2 = st.columns(2)
                with c1:
                    if st.form_submit_button("Сохранить"):
                        st.session_state.equipment_db[idx] = {
                            "id": selected, "name": up_name, "type": up_type,
                            "status": up_status, "hours": up_hours if up_counter else 0, "counter_ok": up_counter
                        }
                        st.success("Сохранено")
                        st.rerun()
                with c2:
                    if st.form_submit_button("Удалить"):
                        st.session_state.equipment_db.pop(idx)
                        st.success("Удалено")
                        st.rerun()
    
    with tech_tabs[3]:
        st.subheader("Типы техники и периодичность ТО")
        
        for i, t in enumerate(st.session_state.equipment_types):
            col1, col2, col3 = st.columns([2, 1, 0.5])
            with col1:
                t["name"] = st.text_input("Название", value=t["name"], key=f"type_name_{i}")
            with col2:
                t["maintenance_interval"] = st.number_input("Период ТО (ч)", value=t["maintenance_interval"], min_value=100, step=50, key=f"type_int_{i}")
            with col3:
                if st.button("Удалить", key=f"del_type_{i}"):
                    if len(st.session_state.equipment_types) > 1:
                        st.session_state.equipment_types.pop(i)
                        st.rerun()
        
        st.markdown("---")
        new_name = st.text_input("Новый тип")
        new_interval = st.number_input("Период ТО для нового типа", min_value=100, step=50, value=500)
        if st.button("Добавить тип"):
            if new_name and new_name not in [t["name"] for t in st.session_state.equipment_types]:
                st.session_state.equipment_types.append({"name": new_name, "maintenance_interval": new_interval})
                st.rerun()

# ==============================================================================
# ВКЛАДКА 3: РЕМОНТЫ
# ==============================================================================
with main_tabs[2]:
    repair_tabs = st.tabs(["Журнал", "Новая запись"])
    
    with repair_tabs[0]:
        if st.session_state.service_db:
            data = []
            for s in sorted(st.session_state.service_db, key=lambda x: x["date"], reverse=True):
                eq = next((x for x in st.session_state.equipment_db if x["id"] == s["eq_id"]), None)
                data.append({
                    "Дата": s["date"].strftime("%d.%m.%Y"),
                    "Техника": eq["name"] if eq else s["eq_id"],
                    "Тип": s["type"],
                    "Механик": s.get("mechanic", "—"),
                    "Моточасы": s["hours"] if s["hours"] else "—",
                    "Описание": s["description"][:80] + "..." if len(s["description"]) > 80 else s["description"]
                })
            st.dataframe(data, use_container_width=True, hide_index=True)
        else:
            st.info("Нет записей")
    
    with repair_tabs[1]:
        if st.session_state.equipment_db:
            with st.form("add_repair"):
                col1, col2 = st.columns(2)
                with col1:
                    eq_id = st.selectbox("Техника", [x["id"] for x in st.session_state.equipment_db])
                    repair_type = st.selectbox("Вид работ", ["ТО", "Ремонт", "Диагностика"])
                    repair_date = st.date_input("Дата", value=date.today())
                with col2:
                    eq = next(x for x in st.session_state.equipment_db if x["id"] == eq_id)
                    hours = st.number_input("Моточасы", value=int(eq["hours"])) if eq["counter_ok"] else None
                    mechanic = st.selectbox("Механик", [m["name"] for m in st.session_state.mechanics_db])
                
                desc = st.text_area("Описание работ", height=100)
                parts = st.text_area("Запчасти (каждая с новой строки)", height=100)
                
                if st.form_submit_button("Сохранить"):
                    if desc:
                        new_id = max([s["id"] for s in st.session_state.service_db]) + 1 if st.session_state.service_db else 1
                        parts_list = [p.strip() for p in parts.split('\n') if p.strip()]
                        
                        for part in parts_list:
                            existing = next((p for p in st.session_state.parts_inventory if p["name"] == part), None)
                            if existing:
                                existing["usage_count"] += 1
                            else:
                                st.session_state.parts_inventory.append({"name": part, "unit": "шт", "usage_count": 1})
                        
                        st.session_state.service_db.append({
                            "id": new_id, "eq_id": eq_id, "date": repair_date, "type": repair_type,
                            "hours": hours, "mechanic": mechanic, "description": desc, "parts": parts_list
                        })
                        
                        if hours and eq["counter_ok"] and hours > eq["hours"]:
                            idx = st.session_state.equipment_db.index(eq)
                            st.session_state.equipment_db[idx]["hours"] = hours
                        
                        st.success("Запись добавлена")
                        st.rerun()

# ==============================================================================
# ВКЛАДКА 4: МЕХАНИКИ
# ==============================================================================
with main_tabs[3]:
    mech_tabs = st.tabs(["Список", "Добавить"])
    
    with mech_tabs[0]:
        if st.session_state.mechanics_db:
            data = []
            for m in st.session_state.mechanics_db:
                work_count = len([s for s in st.session_state.service_db if s.get("mechanic") == m["name"]])
                data.append({
                    "ФИО": m["name"],
                    "Специализация": m["specialization"],
                    "Телефон": m["phone"],
                    "Работ": work_count
                })
            st.dataframe(data, use_container_width=True, hide_index=True)
    
    with mech_tabs[1]:
        with st.form("add_mechanic"):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("ФИО")
                spec = st.text_input("Специализация")
            with col2:
                phone = st.text_input("Телефон")
            
            if st.form_submit_button("Добавить"):
                if name:
                    new_id = max([m["id"] for m in st.session_state.mechanics_db]) + 1 if st.session_state.mechanics_db else 1
                    st.session_state.mechanics_db.append({"id": new_id, "name": name, "specialization": spec, "phone": phone})
                    st.success("Добавлено")
                    st.rerun()

# ==============================================================================
# ВКЛАДКА 5: ЗАПЧАСТИ
# ==============================================================================
with main_tabs[4]:
    if st.session_state.parts_inventory:
        st.dataframe(pd.DataFrame(st.session_state.parts_inventory), use_container_width=True, hide_index=True)
        
        parts_df = pd.DataFrame(st.session_state.parts_inventory)
        fig = px.bar(parts_df, x="name", y="usage_count", title="Использование запчастей")
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

# ==============================================================================
# ВКЛАДКА 6: ДОКУМЕНТЫ
# ==============================================================================
with main_tabs[5]:
    doc_tabs = st.tabs(["Список", "Добавить"])
    
    with doc_tabs[0]:
        if st.session_state.documents_db:
            data = []
            for d in st.session_state.documents_db:
                eq = next((x for x in st.session_state.equipment_db if x["id"] == d["eq_id"]), None)
                data.append({
                    "Название": d["title"],
                    "Техника": eq["name"] if eq else "—",
                    "Тип": d["type"],
                    "Дата": d["date"].strftime("%d.%m.%Y")
                })
            st.dataframe(data, use_container_width=True, hide_index=True)
    
    with doc_tabs[1]:
        with st.form("add_document"):
            col1, col2 = st.columns(2)
            with col1:
                doc_title = st.text_input("Название")
                doc_type = st.selectbox("Тип", ["Паспорт", "Акт", "Сертификат", "Договор"])
            with col2:
                eq_ids = [x["id"] for x in st.session_state.equipment_db]
                doc_eq = st.selectbox("Техника", [""] + eq_ids)
                doc_date = st.date_input("Дата", value=date.today())
            
            if st.form_submit_button("Добавить"):
                if doc_title:
                    new_id = max([d["id"] for d in st.session_state.documents_db]) + 1 if st.session_state.documents_db else 1
                    st.session_state.documents_db.append({
                        "id": new_id, "title": doc_title, "eq_id": doc_eq if doc_eq else None,
                        "type": doc_type, "date": doc_date, "file": None
                    })
                    st.success("Документ добавлен")
                    st.rerun()

# ==============================================================================
# ВКЛАДКА 7: ОТЧЕТЫ
# ==============================================================================
with main_tabs[6]:
    if st.session_state.service_db:
        col1, col2 = st.columns(2)
        with col1:
            date_from = st.date_input("От", value=date(2024, 1, 1))
        with col2:
            date_to = st.date_input("До", value=date.today())
        
        filtered = [s for s in st.session_state.service_db if date_from <= s["date"] <= date_to]
        
        if filtered:
            data = []
            for s in filtered:
                eq = next((x for x in st.session_state.equipment_db if x["id"] == s["eq_id"]), None)
                data.append({
                    "Дата": s["date"].strftime("%d.%m.%Y"),
                    "Техника": eq["name"] if eq else s["eq_id"],
                    "Тип": s["type"],
                    "Механик": s.get("mechanic", "—"),
                    "Описание": s["description"]
                })
            st.dataframe(data, use_container_width=True, hide_index=True)
            
            if st.button("Экспорт в Excel"):
                excel_data = export_to_excel(data, "report.xlsx")
                st.download_button("Скачать", data=excel_data, file_name=f"report_{date.today()}.xlsx")