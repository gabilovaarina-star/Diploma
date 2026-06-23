import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import psycopg2
import hashlib
import configparser
from datetime import datetime

# ========== 1. Чтение конфигурации ==========
import os
import sys

if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

config_path = os.path.join(base_dir, 'config.ini')
config = configparser.ConfigParser()
config.read(config_path)

DB_HOST = config['database']['host']
DB_PORT = config['database']['port']
DB_NAME = config['database']['database']
DB_USER = config['database']['user']
DB_PASS = config['database']['password']

# Глобальная переменная для текущего пользователя
current_user = None  # Будет содержать (user_id, login, role, employee_id)

# ========== 2. Подключение к БД ==========
def get_connection():
    """Возвращает новое соединение с БД."""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )

# ========== 3. Аутентификация ==========
def hash_password(password):
    """Вычисляет SHA-256 хеш пароля."""
    return hashlib.sha256(password.encode()).hexdigest()

def authenticate(login, password):
    """Проверяет логин/пароль и возвращает данные пользователя или None."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id, login, role, employee_id FROM users WHERE login=%s AND password_hash=%s",
                (login, hash_password(password)))
    user = cur.fetchone()
    cur.close()
    conn.close()
    return user

# ========== 4. Основные функции работы с данными ==========

# --- Клиенты ---
def get_clients():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT client_id, full_name, phone, email, registration_date FROM clients ORDER BY client_id")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def add_client(full_name, phone, email):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO clients (full_name, phone, email) VALUES (%s, %s, %s)",
                (full_name, phone, email))
    conn.commit()
    cur.close()
    conn.close()

def update_client(client_id, full_name, phone, email):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE clients SET full_name=%s, phone=%s, email=%s WHERE client_id=%s",
                (full_name, phone, email, client_id))
    conn.commit()
    cur.close()
    conn.close()

def delete_client(client_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM clients WHERE client_id=%s", (client_id,))
    conn.commit()
    cur.close()
    conn.close()

# --- Поиск клиентов ---
def search_clients(search_text):
    """Ищет клиентов по ФИО, телефону или email (регистронезависимо)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT client_id, full_name, phone, email, registration_date
        FROM clients
        WHERE full_name ILIKE %s OR phone ILIKE %s OR email ILIKE %s
        ORDER BY client_id
    """, (f'%{search_text}%', f'%{search_text}%', f'%{search_text}%'))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

# --- Товары ---
def get_products():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT product_id, product_name, description, price FROM products ORDER BY product_id")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def add_product(product_name, description, price):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO products (product_name, description, price) VALUES (%s, %s, %s)",
                (product_name, description, price))
    conn.commit()
    cur.close()
    conn.close()

def update_product(product_id, product_name, description, price):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE products SET product_name=%s, description=%s, price=%s WHERE product_id=%s",
                (product_name, description, price, product_id))
    conn.commit()
    cur.close()
    conn.close()

def delete_product(product_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE product_id=%s", (product_id,))
    conn.commit()
    cur.close()
    conn.close()

# --- Заказы ---
def get_orders():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT o.order_id, c.full_name AS client, e.full_name AS employee,
               o.order_date, o.status
        FROM orders o
        JOIN clients c ON o.client_id = c.client_id
        JOIN employees e ON o.employee_id = e.employee_id
        ORDER BY o.order_id
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def create_order(client_id, employee_id, items):
    """items - список словарей {product_id, quantity} """
    conn = get_connection()
    cur = conn.cursor()
    # Вставляем заказ
    cur.execute("INSERT INTO orders (client_id, employee_id, status) VALUES (%s, %s, 'new') RETURNING order_id",
                (client_id, employee_id))
    order_id = cur.fetchone()[0]
    # Вставляем позиции
    for item in items:
        cur.execute("INSERT INTO order_items (order_id, product_id, quantity, price_at_moment) "
                    "VALUES (%s, %s, %s, (SELECT price FROM products WHERE product_id=%s))",
                    (order_id, item['product_id'], item['quantity'], item['product_id']))
    # Обновляем итоговую сумму
    cur.execute("UPDATE orders SET total_amount = ("
                "SELECT SUM(price_at_moment * quantity) FROM order_items WHERE order_id=%s"
                ") WHERE order_id=%s", (order_id, order_id))
    conn.commit()
    cur.close()
    conn.close()

def update_order_status(order_id, new_status):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE orders SET status=%s WHERE order_id=%s", (new_status, order_id))
    conn.commit()
    cur.close()
    conn.close()

# --- Отчёты ---
def get_revenue_report(start_date, end_date):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT SUM(total_amount) FROM orders
        WHERE order_date BETWEEN %s AND %s AND status='completed'
    """, (start_date, end_date))
    total = cur.fetchone()[0]
    cur.close()
    conn.close()
    return total or 0.0

# --- Пользователи ---
def get_users():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id, login, role, employee_id FROM users ORDER BY user_id")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def add_user(login, password, role, employee_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO users (login, password_hash, role, employee_id) VALUES (%s, %s, %s, %s)",
                (login, hash_password(password), role, employee_id))
    conn.commit()
    cur.close()
    conn.close()

# ========== 5. Графический интерфейс ==========
class App:
    def __init__(self, root, user_info):
        global current_user
        current_user = user_info  # (user_id, login, role, employee_id)
        self.root = root
        self.root.title(f"ИС управления данными — {user_info[1]} ({user_info[2]})")

        # Создаём вкладки
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill='both', expand=True)

        # Вкладки, доступные всем
        self.tab_clients = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_clients, text="Клиенты")
        self.build_clients_tab()

        self.tab_products = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_products, text="Товары")
        self.build_products_tab()

        self.tab_orders = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_orders, text="Заказы")
        self.build_orders_tab()

        # Дополнительные вкладки только для директора
        if user_info[2] == 'director':
            self.tab_reports = ttk.Frame(self.notebook)
            self.notebook.add(self.tab_reports, text="Отчёты")
            self.build_reports_tab()

            self.tab_users = ttk.Frame(self.notebook)
            self.notebook.add(self.tab_users, text="Пользователи")
            self.build_users_tab()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self):
        self.root.destroy()

    # ---------- Вкладка "Клиенты" ----------
    def build_clients_tab(self):
        frame = self.tab_clients
        # Панель поиска
        search_frame = ttk.Frame(frame)
        search_frame.pack(fill='x', padx=5, pady=5)
        ttk.Label(search_frame, text="Поиск:").pack(side='left')
        self.search_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.search_var, width=30).pack(side='left', padx=5)
        ttk.Button(search_frame, text="Найти", command=self.find_clients).pack(side='left', padx=2)
        ttk.Button(search_frame, text="Сбросить", command=self.refresh_clients).pack(side='left', padx=2)

        # Таблица
        columns = ('id', 'name', 'phone', 'email', 'reg_date')
        self.tree_clients = ttk.Treeview(frame, columns=columns, show='headings')
        self.tree_clients.heading('id', text='ID')
        self.tree_clients.heading('name', text='ФИО')
        self.tree_clients.heading('phone', text='Телефон')
        self.tree_clients.heading('email', text='Email')
        self.tree_clients.heading('reg_date', text='Дата регистрации')
        self.tree_clients.pack(fill='both', expand=True, padx=5, pady=5)
        self.refresh_clients()

        # Панель управления
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="Добавить", command=self.add_client_dialog).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Изменить", command=self.edit_client_dialog).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Удалить", command=self.delete_client).pack(side='left', padx=2)

    def refresh_clients(self):
        for i in self.tree_clients.get_children():
            self.tree_clients.delete(i)
        for row in get_clients():
            self.tree_clients.insert('', 'end', values=row)

    def find_clients(self):
        search_text = self.search_var.get().strip()
        if search_text:
            rows = search_clients(search_text)
        else:
            rows = get_clients()
        for i in self.tree_clients.get_children():
            self.tree_clients.delete(i)
        for row in rows:
            self.tree_clients.insert('', 'end', values=row)

    def add_client_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Новый клиент")
        ttk.Label(dialog, text="ФИО").grid(row=0, column=0, padx=5, pady=5)
        name_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=name_var).grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(dialog, text="Телефон").grid(row=1, column=0, padx=5, pady=5)
        phone_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=phone_var).grid(row=1, column=1, padx=5, pady=5)
        ttk.Label(dialog, text="Email").grid(row=2, column=0, padx=5, pady=5)
        email_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=email_var).grid(row=2, column=1, padx=5, pady=5)
        def save():
            add_client(name_var.get(), phone_var.get(), email_var.get())
            dialog.destroy()
            self.refresh_clients()
        ttk.Button(dialog, text="Сохранить", command=save).grid(row=3, column=0, columnspan=2, pady=10)

    def edit_client_dialog(self):
        selected = self.tree_clients.selection()
        if not selected:
            messagebox.showwarning("Внимание", "Выберите клиента для изменения")
            return
        item = self.tree_clients.item(selected[0])
        client_id, old_name, old_phone, old_email, _ = item['values']
        dialog = tk.Toplevel(self.root)
        dialog.title("Изменить клиента")
        ttk.Label(dialog, text="ФИО").grid(row=0, column=0, padx=5, pady=5)
        name_var = tk.StringVar(value=old_name)
        ttk.Entry(dialog, textvariable=name_var).grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(dialog, text="Телефон").grid(row=1, column=0, padx=5, pady=5)
        phone_var = tk.StringVar(value=old_phone)
        ttk.Entry(dialog, textvariable=phone_var).grid(row=1, column=1, padx=5, pady=5)
        ttk.Label(dialog, text="Email").grid(row=2, column=0, padx=5, pady=5)
        email_var = tk.StringVar(value=old_email)
        ttk.Entry(dialog, textvariable=email_var).grid(row=2, column=1, padx=5, pady=5)
        def save():
            update_client(client_id, name_var.get(), phone_var.get(), email_var.get())
            dialog.destroy()
            self.refresh_clients()
        ttk.Button(dialog, text="Сохранить", command=save).grid(row=3, column=0, columnspan=2, pady=10)

    def delete_client(self):
        selected = self.tree_clients.selection()
        if not selected:
            messagebox.showwarning("Внимание", "Выберите клиента для удаления")
            return
        item = self.tree_clients.item(selected[0])
        client_id = item['values'][0]
        if messagebox.askyesno("Подтверждение", "Удалить выбранного клиента?"):
            delete_client(client_id)
            self.refresh_clients()

    # ---------- Вкладка "Товары" ----------
    def build_products_tab(self):
        frame = self.tab_products
        columns = ('id', 'name', 'desc', 'price')
        self.tree_products = ttk.Treeview(frame, columns=columns, show='headings')
        self.tree_products.heading('id', text='ID')
        self.tree_products.heading('name', text='Наименование')
        self.tree_products.heading('desc', text='Описание')
        self.tree_products.heading('price', text='Цена')
        self.tree_products.pack(fill='both', expand=True, padx=5, pady=5)
        self.refresh_products()

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="Добавить", command=self.add_product_dialog).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Изменить", command=self.edit_product_dialog).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Удалить", command=self.delete_product).pack(side='left', padx=2)

    def refresh_products(self):
        for i in self.tree_products.get_children():
            self.tree_products.delete(i)
        for row in get_products():
            self.tree_products.insert('', 'end', values=row)

    def add_product_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Новый товар")
        ttk.Label(dialog, text="Наименование").grid(row=0, column=0, padx=5, pady=5)
        name_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=name_var).grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(dialog, text="Описание").grid(row=1, column=0, padx=5, pady=5)
        desc_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=desc_var).grid(row=1, column=1, padx=5, pady=5)
        ttk.Label(dialog, text="Цена").grid(row=2, column=0, padx=5, pady=5)
        price_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=price_var).grid(row=2, column=1, padx=5, pady=5)
        def save():
            add_product(name_var.get(), desc_var.get(), float(price_var.get()))
            dialog.destroy()
            self.refresh_products()
        ttk.Button(dialog, text="Сохранить", command=save).grid(row=3, column=0, columnspan=2, pady=10)

    def edit_product_dialog(self):
        selected = self.tree_products.selection()
        if not selected:
            messagebox.showwarning("Внимание", "Выберите товар для изменения")
            return
        item = self.tree_products.item(selected[0])
        product_id, old_name, old_desc, old_price = item['values']
        dialog = tk.Toplevel(self.root)
        dialog.title("Изменить товар")
        ttk.Label(dialog, text="Наименование").grid(row=0, column=0, padx=5, pady=5)
        name_var = tk.StringVar(value=old_name)
        ttk.Entry(dialog, textvariable=name_var).grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(dialog, text="Описание").grid(row=1, column=0, padx=5, pady=5)
        desc_var = tk.StringVar(value=old_desc)
        ttk.Entry(dialog, textvariable=desc_var).grid(row=1, column=1, padx=5, pady=5)
        ttk.Label(dialog, text="Цена").grid(row=2, column=0, padx=5, pady=5)
        price_var = tk.StringVar(value=old_price)
        ttk.Entry(dialog, textvariable=price_var).grid(row=2, column=1, padx=5, pady=5)
        def save():
            update_product(product_id, name_var.get(), desc_var.get(), float(price_var.get()))
            dialog.destroy()
            self.refresh_products()
        ttk.Button(dialog, text="Сохранить", command=save).grid(row=3, column=0, columnspan=2, pady=10)

    def delete_product(self):
        selected = self.tree_products.selection()
        if not selected:
            messagebox.showwarning("Внимание", "Выберите товар для удаления")
            return
        item = self.tree_products.item(selected[0])
        product_id = item['values'][0]
        if messagebox.askyesno("Подтверждение", "Удалить выбранный товар?"):
            delete_product(product_id)
            self.refresh_products()

    # ---------- Вкладка "Заказы" ----------
    def build_orders_tab(self):
        frame = self.tab_orders
        columns = ('id', 'client', 'employee', 'date', 'status')
        self.tree_orders = ttk.Treeview(frame, columns=columns, show='headings')
        self.tree_orders.heading('id', text='ID')
        self.tree_orders.heading('client', text='Клиент')
        self.tree_orders.heading('employee', text='Сотрудник')
        self.tree_orders.heading('date', text='Дата')
        self.tree_orders.heading('status', text='Статус')
        self.tree_orders.pack(fill='both', expand=True, padx=5, pady=5)
        self.refresh_orders()

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="Новый заказ", command=self.create_order_dialog).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Изменить статус", command=self.change_status_dialog).pack(side='left', padx=2)

    def refresh_orders(self):
        for i in self.tree_orders.get_children():
            self.tree_orders.delete(i)
        for row in get_orders():
            self.tree_orders.insert('', 'end', values=row)

    def create_order_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Новый заказ")
        # Выбор клиента
        ttk.Label(dialog, text="Клиент").grid(row=0, column=0, padx=5, pady=5)
        clients = get_clients()
        client_dict = {f"{c[1]}": c[0] for c in clients}
        client_var = tk.StringVar()
        ttk.Combobox(dialog, textvariable=client_var, values=list(client_dict.keys())).grid(row=0, column=1, padx=5, pady=5)

        # Список товаров
        ttk.Label(dialog, text="Товары").grid(row=1, column=0, columnspan=2, pady=5)
        products = get_products()
        tree_items = ttk.Treeview(dialog, columns=('product', 'qty'), show='headings', height=5)
        tree_items.heading('product', text='Товар')
        tree_items.heading('qty', text='Количество')
        tree_items.grid(row=2, column=0, columnspan=2, padx=5, pady=5)
        items = []  # будет хранить {product_id, quantity}

        def add_item():
            select_product = simpledialog.askstring("Товар", "Введите ID товара:")
            if not select_product:
                return
            product_id = int(select_product)
            quantity = simpledialog.askinteger("Количество", "Введите количество:")
            if quantity:
                prod_name = next((p[1] for p in products if p[0] == product_id), "Неизвестно")
                tree_items.insert('', 'end', values=(prod_name, quantity))
                items.append({'product_id': product_id, 'quantity': quantity})

        ttk.Button(dialog, text="Добавить товар", command=add_item).grid(row=3, column=0, columnspan=2, pady=5)

        def save():
            client_name = client_var.get()
            if not client_name or not items:
                messagebox.showwarning("Ошибка", "Выберите клиента и добавьте хотя бы один товар")
                return
            client_id = client_dict[client_name]
            create_order(client_id, current_user[3], items)
            dialog.destroy()
            self.refresh_orders()

        ttk.Button(dialog, text="Сохранить заказ", command=save).grid(row=4, column=0, columnspan=2, pady=10)

    def change_status_dialog(self):
        selected = self.tree_orders.selection()
        if not selected:
            messagebox.showwarning("Внимание", "Выберите заказ")
            return
        item = self.tree_orders.item(selected[0])
        order_id = item['values'][0]
        new_status = simpledialog.askstring("Статус", "Введите новый статус (new/in_progress/completed/cancelled):")
        if new_status in ('new', 'in_progress', 'completed', 'cancelled'):
            update_order_status(order_id, new_status)
            self.refresh_orders()
        else:
            messagebox.showerror("Ошибка", "Недопустимый статус")

    # ---------- Вкладка "Отчёты" (только для директора) ----------
    def build_reports_tab(self):
        frame = self.tab_reports
        ttk.Label(frame, text="Выручка за период").pack(pady=10)
        ttk.Label(frame, text="Начальная дата (YYYY-MM-DD)").pack()
        start_var = tk.StringVar()
        ttk.Entry(frame, textvariable=start_var).pack()
        ttk.Label(frame, text="Конечная дата (YYYY-MM-DD)").pack()
        end_var = tk.StringVar()
        ttk.Entry(frame, textvariable=end_var).pack()
        result_label = ttk.Label(frame, text="")
        result_label.pack(pady=5)

        def calculate():
            try:
                total = get_revenue_report(start_var.get(), end_var.get())
                result_label.config(text=f"Общая выручка: {total:.2f} руб.")
            except Exception as e:
                messagebox.showerror("Ошибка", str(e))

        ttk.Button(frame, text="Рассчитать", command=calculate).pack(pady=5)

    # ---------- Вкладка "Пользователи" (только для директора) ----------
    def build_users_tab(self):
        frame = self.tab_users
        columns = ('id', 'login', 'role', 'employee_id')
        self.tree_users = ttk.Treeview(frame, columns=columns, show='headings')
        self.tree_users.heading('id', text='ID')
        self.tree_users.heading('login', text='Логин')
        self.tree_users.heading('role', text='Роль')
        self.tree_users.heading('employee_id', text='Сотрудник ID')
        self.tree_users.pack(fill='both', expand=True, padx=5, pady=5)
        self.refresh_users()

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="Добавить", command=self.add_user_dialog).pack(side='left', padx=2)

    def refresh_users(self):
        for i in self.tree_users.get_children():
            self.tree_users.delete(i)
        for row in get_users():
            self.tree_users.insert('', 'end', values=row)

    def add_user_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Новый пользователь")
        ttk.Label(dialog, text="Логин").grid(row=0, column=0, padx=5, pady=5)
        login_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=login_var).grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(dialog, text="Пароль").grid(row=1, column=0, padx=5, pady=5)
        pass_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=pass_var, show='*').grid(row=1, column=1, padx=5, pady=5)
        ttk.Label(dialog, text="Роль (manager/director)").grid(row=2, column=0, padx=5, pady=5)
        role_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=role_var).grid(row=2, column=1, padx=5, pady=5)
        ttk.Label(dialog, text="ID сотрудника").grid(row=3, column=0, padx=5, pady=5)
        emp_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=emp_var).grid(row=3, column=1, padx=5, pady=5)

        def save():
            try:
                add_user(login_var.get(), pass_var.get(), role_var.get(), int(emp_var.get()))
                dialog.destroy()
                self.refresh_users()
            except Exception as e:
                messagebox.showerror("Ошибка", str(e))

        ttk.Button(dialog, text="Сохранить", command=save).grid(row=4, column=0, columnspan=2, pady=10)


# ========== 6. Окно авторизации ==========
class LoginWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Авторизация")

        ttk.Label(self.root, text="Логин").grid(row=0, column=0, padx=10, pady=5)
        self.login_var = tk.StringVar()
        ttk.Entry(self.root, textvariable=self.login_var).grid(row=0, column=1, padx=10, pady=5)

        ttk.Label(self.root, text="Пароль").grid(row=1, column=0, padx=10, pady=5)
        self.pass_var = tk.StringVar()
        ttk.Entry(self.root, textvariable=self.pass_var, show='*').grid(row=1, column=1, padx=10, pady=5)

        ttk.Button(self.root, text="Войти", command=self.login).grid(row=2, column=0, columnspan=2, pady=10)
        self.root.mainloop()

    def login(self):
        user = authenticate(self.login_var.get(), self.pass_var.get())
        if user:
            self.root.destroy()
            main = tk.Tk()
            app = App(main, user)
            main.mainloop()
        else:
            messagebox.showerror("Ошибка", "Неверный логин или пароль")


if __name__ == "__main__":
    LoginWindow()

