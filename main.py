import customtkinter as ctk
import threading
import time
from collections import deque
from nexus_api import download_with_selenium
import os

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("PirNex")
        self.geometry("600x750")

        self.queue = deque() # Очередь для ссылок
        self.is_running = False

        # Окно истории активности (лог)
        self.chat_label = ctk.CTkLabel(self, text="ЛОГ АКТИВНОСТИ", font=("Arial", 13, "bold"))
        self.chat_label.pack(pady=(15, 0))
        
        self.chat_log = ctk.CTkTextbox(self, width=560, height=450, state="disabled", font=("Consolas", 12))
        self.chat_log.pack(pady=10, padx=20)

        # Поле ввода новых ссылок
        self.input_label = ctk.CTkLabel(self, text="ВСТАВЬТЕ ССЫЛКИ СЮДА:", font=("Arial", 12, "bold"))
        self.input_label.pack(pady=(10, 0))

        self.link_input = ctk.CTkTextbox(self, width=560, height=80)
        self.link_input.pack(pady=10, padx=20)

        # Кнопочная панель
        self.button_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.button_frame.pack(pady=10)

        self.send_btn = ctk.CTkButton(self.button_frame, text="ОТПРАВИТЬ В ОЧЕРЕДЬ", 
                                      fg_color="#d98f40", hover_color="#bf7a30",
                                      command=self.add_to_chat)
        self.send_btn.pack(side="left", padx=5)

        self.folder_btn = ctk.CTkButton(self.button_frame, text="ОТКРЫТЬ ПАПКУ", 
                                        fg_color="#4a4a4a", hover_color="#333333",
                                        command=self.open_downloads_folder)
        self.folder_btn.pack(side="left", padx=5)

    def open_downloads_folder(self):
        folder_path = os.path.abspath("downloads")
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        os.startfile(folder_path)
        self.log_message(f"📂 Папка открыта: {folder_path}")

    def log_message(self, message):
        self.chat_log.configure(state="normal")
        self.chat_log.insert("end", f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.chat_log.configure(state="disabled")
        self.chat_log.see("end")

    def add_to_chat(self):
        raw_text = self.link_input.get("1.0", "end-1c").strip()
        if not raw_text: return
        new_links = [l.strip() for l in raw_text.split('\n') if l.strip()]
        for link in new_links:
            self.queue.append(link)
            self.log_message(f"📥 Добавлено в очередь: {link[:50]}...")
        self.link_input.delete("1.0", "end")
        if not self.is_running:
            self.is_running = True
            threading.Thread(target=self.worker_thread, daemon=True).start()

    def worker_thread(self):
        while self.queue:
            current_link = self.queue.popleft()
            self.log_message(f"🚀 Приступаю: {current_link[:50]}...")
            try:
                download_with_selenium(current_link, "downloads")
                self.log_message(f"✅ Готово!")
            except Exception as e:
                self.log_message(f"❌ Ошибка: {str(e)[:50]}")
            time.sleep(2) 
        self.is_running = False
        self.log_message("⌛ Очередь пуста. Жду новых ссылок...")

if __name__ == "__main__":
    app = App()
    app.mainloop()