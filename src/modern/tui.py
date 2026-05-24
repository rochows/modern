#!/usr/bin/env python3
"""
Абстрактное TUI-приложение для демонстрации возможностей Textual.
Запуск: python tui.py
"""

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, Container
from textual.widgets import Header, Footer, Button, Static, Input, Label, ListView, ListItem
from textual.reactive import reactive
from textual.message import Message


class CounterWidget(Static):
    """Виджет счётчика с кнопками."""
    
    class ValueChanged(Message):
        """Событие изменения значения."""
        def __init__(self, value: int) -> None:
            self.value = value
            super().__init__()
    
    count = reactive(0)
    
    def compose(self) -> ComposeResult:
        yield Horizontal(
            Button("-", id="minus", variant="error"),
            Static("0", id="counter-value", classes="counter-number"),
            Button("+", id="plus", variant="success"),
            classes="counter-row"
        )
    
    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "plus":
            self.count += 1
        elif event.button.id == "minus":
            self.count -= 1
    
    def watch_count(self, old: int, new: int) -> None:
        """Обновляет отображение при изменении счётчика."""
        value_widget = self.query_one("#counter-value", Static)
        value_widget.update(str(new))
        self.post_message(self.ValueChanged(new))


class ColorBox(Static):
    """Виджет, меняющий цвет при клике."""
    
    def __init__(self, color: str = "blue"):
        super().__init__()
        self.color = color
        self.click_count = 0
    
    def compose(self) -> ComposeResult:
        yield Static(f"🟦 Цвет: {self.color}\nКликов: {self.click_count}")
    
    def on_click(self):
        self.click_count += 1
        colors = ["red", "green", "blue", "yellow", "magenta", "cyan"]
        self.color = colors[self.click_count % len(colors)]
        self.query_one(Static).update(f"🟦 Цвет: {self.color}\nКликов: {self.click_count}")


class SimpleTUI(App):
    """Главное приложение."""
    
    CSS = """
    Screen {
        background: $surface;
    }
    
    .title {
        text-style: bold;
        text-align: center;
        background: $primary;
        color: $text;
        padding: 1;
        margin-bottom: 1;
    }
    
    .card {
        border: solid $accent;
        padding: 1;
        margin: 1;
        background: $panel;
    }
    
    .counter-row {
        align: center middle;
        height: 3;
    }
    
    .counter-number {
        width: 5;
        text-align: center;
        content-align: center middle;
        padding: 0 1;
    }
    
    Button {
        margin: 0 1;
    }
    
    #log-area {
        height: 8;
        border: solid $primary;
        overflow-y: auto;
    }
    
    .log-entry {
        padding: 0 1;
    }
    
    .info {
        color: $text-muted;
        text-align: center;
        margin: 1;
    }
    
    .two-columns {
        height: 1fr;
    }
    
    .column {
        width: 50%;
        margin: 0 1;
    }
    
    #bottom-panel {
        height: 10;
        margin-top: 1;
    }
    """
    
    def compose(self) -> ComposeResult:
        yield Header()
        
        yield Static("🎨 Абстрактное TUI-приложение", classes="title")
        
        with Horizontal(classes="two-columns"):
            with Vertical(classes="column"):
                yield Label("📊 Счётчик с кнопками", classes="info")
                yield CounterWidget()
                yield Label("💾 Примеры виджетов", classes="info")
                yield Input(placeholder="Введите текст...", id="text-input")
                yield Button("Показать сообщение", id="show-msg", variant="primary")
            
            with Vertical(classes="column"):
                yield Label("🎨 Интерактивный блок", classes="info")
                yield ColorBox()
                yield Label("📝 Список действий", classes="info")
                yield ListView(id="action-list")
        
        with Vertical(id="bottom-panel"):
            yield Label("📋 Лог событий", classes="info")
            yield Static("", id="log-area")
        
        yield Footer()
    
    def on_mount(self):
        """При запуске добавляем приветствие в лог."""
        # Инициализируем хранилище логов
        self._log_lines = []
        self.log_message("Приложение запущено")
        
        # Заполняем список действий примерами
        list_view = self.query_one("#action-list", ListView)
        for item in ["Нажмите на цветной блок", "Используйте счётчик", "Введите текст"]:
            list_view.append(ListItem(Static(f"• {item}")))
    
    def on_button_pressed(self, event: Button.Pressed):
        """Обработка кнопок."""
        if event.button.id == "show-msg":
            input_widget = self.query_one("#text-input", Input)
            text = input_widget.value or "пусто"
            self.log_message(f"Введено: {text}")
            input_widget.value = ""
    
    def on_input_submitted(self, event: Input.Submitted):
        """При нажатии Enter в поле ввода."""
        self.log_message(f"Отправлено: {event.value}")
        event.input.value = ""
    
    def on_counter_widget_value_changed(self, event: CounterWidget.ValueChanged):
        """При изменении счётчика."""
        self.log_message(f"Счётчик = {event.value}")
    
    def log_message(self, msg: str):
        """Добавляет сообщение в лог-область."""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        self._log_lines.append(f"[{timestamp}] {msg}")
        if len(self._log_lines) > 20:
            self._log_lines = self._log_lines[-20:]
        
        log = self.query_one("#log-area", Static)
        log.update("\n".join(self._log_lines))


def main():
    """Точка входа."""
    SimpleTUI().run()


if __name__ == "__main__":
    main()