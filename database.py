import json
import os
from contextlib import contextmanager

import mysql.connector
from mysql.connector import pooling

from config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE, DATA_DIR

_pool = None
_use_json_fallback = False

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS menu_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    price DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    category_id INT NOT NULL,
    emoji VARCHAR(10) DEFAULT '🍽️',
    image VARCHAR(255) DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(10) DEFAULT 'user',
    avatar VARCHAR(255) DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    total_amount DECIMAL(10, 2) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS order_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    menu_item_id INT NOT NULL,
    name VARCHAR(100) NOT NULL DEFAULT '',
    quantity INT NOT NULL DEFAULT 1,
    price DECIMAL(10, 2) NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    FOREIGN KEY (menu_item_id) REFERENCES menu_items(id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS config (
    id INT AUTO_INCREMENT PRIMARY KEY,
    config_key VARCHAR(100) NOT NULL UNIQUE,
    config_value VARCHAR(500) NOT NULL
) ENGINE=InnoDB;
"""


def init_db():
    global _pool, _use_json_fallback
    try:
        conn = mysql.connector.connect(
            host=MYSQL_HOST, port=MYSQL_PORT,
            user=MYSQL_USER, password=MYSQL_PASSWORD
        )
        try:
            cur = conn.cursor()
            try:
                cur.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{MYSQL_DATABASE}` "
                    f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            finally:
                cur.close()
        finally:
            conn.close()

        _pool = pooling.MySQLConnectionPool(
            pool_name="dopamine_pool",
            pool_size=10,
            host=MYSQL_HOST, port=MYSQL_PORT,
            user=MYSQL_USER, password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE,
            charset='utf8mb4'
        )

        conn = _pool.get_connection()
        try:
            cur = conn.cursor()
            try:
                for stmt in SCHEMA_SQL.split(';'):
                    stmt = stmt.strip()
                    if stmt:
                        cur.execute(stmt)
                conn.commit()
            finally:
                cur.close()
        finally:
            conn.close()

        _migrate_from_json()
        _use_json_fallback = False
    except Exception as e:
        print(f'[警告] MySQL 连接失败，使用 JSON 文件存储: {e}')
        _pool = None
        _use_json_fallback = True


@contextmanager
def get_db(dictionary=False):
    """数据库连接上下文管理器，自动释放连接和游标回池。"""
    conn = None
    cur = None
    try:
        if _use_json_fallback:
            yield None, None
            return

        try:
            conn = get_conn()
        except Exception:
            yield None, None
            return

        if conn is None:
            yield None, None
            return

        cur = conn.cursor(dictionary=dictionary)
        yield conn, cur
    finally:
        if cur is not None:
            try:
                cur.close()
            except Exception:
                pass
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def get_conn():
    global _pool
    if _use_json_fallback:
        return None
    if _pool is None:
        init_db()
    if _use_json_fallback:
        return None
    return _pool.get_connection()


# ---------- JSON 文件操作（备用） ----------

def _json_read(filename):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return [] if filename in ('users.json', 'menu.json', 'orders.json') else {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _json_write(filename, data):
    path = os.path.join(DATA_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------- 数据迁移 ----------

def _migrate_from_json():
    with get_db() as (conn, cur):
        if conn is None:
            return

        cur.execute("SELECT COUNT(*) FROM users")
        if cur.fetchone()[0] == 0:
            _import_users(cur)

        cur.execute("SELECT COUNT(*) FROM categories")
        if cur.fetchone()[0] == 0:
            _import_menu(cur)

        cur.execute("SELECT COUNT(*) FROM config")
        if cur.fetchone()[0] == 0:
            _import_config(cur)

        conn.commit()


def _import_users(cur):
    path = os.path.join(DATA_DIR, 'users.json')
    if not os.path.exists(path):
        return
    from werkzeug.security import generate_password_hash
    with open(path, 'r', encoding='utf-8') as f:
        users = json.load(f)
    for u in users:
        pw_hash = u.get('password_hash') or generate_password_hash(u.get('password', ''))
        cur.execute(
            "INSERT INTO users (username, password_hash, role, avatar) VALUES (%s, %s, %s, %s)",
            (u['username'], pw_hash, u.get('role', 'user'), u.get('avatar', None))
        )


def _import_menu(cur):
    path = os.path.join(DATA_DIR, 'menu.json')
    if not os.path.exists(path):
        return
    with open(path, 'r', encoding='utf-8') as f:
        items = json.load(f)
    for item in items:
        category_name = item.get('category', '未分类')
        cur.execute("SELECT id FROM categories WHERE name = %s", (category_name,))
        row = cur.fetchone()
        if row:
            cat_id = row[0]
        else:
            cur.execute("INSERT INTO categories (name) VALUES (%s)", (category_name,))
            cat_id = cur.lastrowid
        cur.execute(
            "INSERT INTO menu_items (id, name, price, category_id, emoji, image) VALUES (%s, %s, %s, %s, %s, %s)",
            (item['id'], item['name'], item['price'], cat_id, item.get('emoji', '🍽️'), item.get('image', ''))
        )


def _import_config(cur):
    path = os.path.join(DATA_DIR, 'config.json')
    if not os.path.exists(path):
        return
    with open(path, 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    for k, v in cfg.items():
        cur.execute(
            "INSERT INTO config (config_key, config_value) VALUES (%s, %s)",
            (k, str(v))
        )


# ---------- 用户操作 ----------

def get_user_by_username(username):
    if _use_json_fallback:
        users = _json_read('users.json')
        for u in users:
            if u['username'] == username:
                return {
                    'id': u.get('id', 0),
                    'username': u['username'],
                    'password_hash': u['password_hash'],
                    'role': u.get('role', 'user'),
                    'avatar': u.get('avatar', None),
                }
        return None

    with get_db(dictionary=True) as (conn, cur):
        if conn is None:
            return None
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        return cur.fetchone()


def create_user(username, password_hash, role='user'):
    if _use_json_fallback:
        users = _json_read('users.json')
        new_id = max([u.get('id', 0) for u in users], default=0) + 1
        users.append({
            'id': new_id,
            'username': username,
            'password_hash': password_hash,
            'role': role,
            'avatar': None,
        })
        _json_write('users.json', users)
        return

    with get_db() as (conn, cur):
        if conn is None:
            raise RuntimeError('数据库连接不可用')
        cur.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
            (username, password_hash, role)
        )
        conn.commit()


def update_user_password(username, password_hash):
    if _use_json_fallback:
        users = _json_read('users.json')
        for u in users:
            if u['username'] == username:
                u['password_hash'] = password_hash
                break
        _json_write('users.json', users)
        return

    with get_db() as (conn, cur):
        if conn is None:
            raise RuntimeError('数据库连接不可用')
        cur.execute(
            "UPDATE users SET password_hash = %s WHERE username = %s",
            (password_hash, username)
        )
        conn.commit()


def update_user_avatar(username, avatar):
    if _use_json_fallback:
        users = _json_read('users.json')
        for u in users:
            if u['username'] == username:
                u['avatar'] = avatar
                break
        _json_write('users.json', users)
        return

    with get_db() as (conn, cur):
        if conn is None:
            raise RuntimeError('数据库连接不可用')
        cur.execute(
            "UPDATE users SET avatar = %s WHERE username = %s",
            (avatar, username)
        )
        conn.commit()


# ---------- 菜单操作 ----------

def get_all_menu():
    if _use_json_fallback:
        items = _json_read('menu.json')
        for item in items:
            item['price'] = float(item['price'])
        return items

    with get_db(dictionary=True) as (conn, cur):
        if conn is None:
            return []
        cur.execute("""
            SELECT m.id, m.name, m.price, c.name AS category, m.emoji, m.image
            FROM menu_items m
            JOIN categories c ON m.category_id = c.id
            ORDER BY m.id
        """)
        rows = cur.fetchall()
        for row in rows:
            row['price'] = float(row['price'])
        return rows


def get_or_create_category(name):
    if _use_json_fallback:
        return name

    with get_db() as (conn, cur):
        if conn is None:
            raise RuntimeError('数据库连接不可用')
        cur.execute("SELECT id FROM categories WHERE name = %s", (name,))
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute("INSERT INTO categories (name) VALUES (%s)", (name,))
        conn.commit()
        return cur.lastrowid


def add_menu_item(name, price, category_name, emoji='🍽️', image=''):
    if _use_json_fallback:
        items = _json_read('menu.json')
        new_id = max([i.get('id', 0) for i in items], default=0) + 1
        items.append({
            'id': new_id, 'name': name, 'price': float(price),
            'category': category_name, 'emoji': emoji, 'image': image,
        })
        _json_write('menu.json', items)
        return new_id

    cat_id = get_or_create_category(category_name)
    with get_db() as (conn, cur):
        if conn is None:
            raise RuntimeError('数据库连接不可用')
        cur.execute(
            "INSERT INTO menu_items (name, price, category_id, emoji, image) VALUES (%s, %s, %s, %s, %s)",
            (name, price, cat_id, emoji, image)
        )
        new_id = cur.lastrowid
        conn.commit()
        return new_id


def update_menu_item(item_id, **kwargs):
    if _use_json_fallback:
        items = _json_read('menu.json')
        for item in items:
            if item['id'] == item_id:
                if 'name' in kwargs and kwargs['name'] is not None:
                    item['name'] = kwargs['name']
                if 'price' in kwargs and kwargs['price'] is not None:
                    item['price'] = float(kwargs['price'])
                if 'category_name' in kwargs and kwargs['category_name']:
                    item['category'] = kwargs['category_name']
                if 'emoji' in kwargs and kwargs['emoji'] is not None:
                    item['emoji'] = kwargs['emoji']
                if 'image' in kwargs and kwargs['image'] is not None:
                    item['image'] = kwargs['image']
                break
        _json_write('menu.json', items)
        return True

    allowed = {'name', 'price', 'emoji', 'image'}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}

    if 'category_name' in kwargs and kwargs['category_name']:
        cat_id = get_or_create_category(kwargs['category_name'])
        updates['category_id'] = cat_id

    if not updates:
        return False

    with get_db() as (conn, cur):
        if conn is None:
            raise RuntimeError('数据库连接不可用')
        set_clause = ', '.join(f"{k} = %s" for k in updates)
        values = list(updates.values()) + [item_id]
        cur.execute(f"UPDATE menu_items SET {set_clause} WHERE id = %s", values)
        conn.commit()
        return True


def delete_menu_item(item_id):
    if _use_json_fallback:
        items = _json_read('menu.json')
        items = [i for i in items if i['id'] != item_id]
        _json_write('menu.json', items)
        return

    with get_db() as (conn, cur):
        if conn is None:
            raise RuntimeError('数据库连接不可用')
        cur.execute("DELETE FROM menu_items WHERE id = %s", (item_id,))
        conn.commit()


# ---------- 订单操作 ----------

def create_order(user_id, total_amount, items, username=None):
    if _use_json_fallback:
        orders = _json_read('orders.json')
        new_id = max([o.get('id', 0) for o in orders], default=0) + 1
        orders.append({
            'id': new_id, 'user_id': user_id,
            'username': username or '未知用户',
            'total_amount': total_amount, 'status': 'pending', 'items': items,
        })
        _json_write('orders.json', orders)
        return new_id

    with get_db() as (conn, cur):
        if conn is None:
            raise RuntimeError('数据库连接不可用')
        cur.execute(
            "INSERT INTO orders (user_id, total_amount) VALUES (%s, %s)",
            (user_id, total_amount)
        )
        order_id = cur.lastrowid
        for item in items:
            cur.execute(
                "INSERT INTO order_items (order_id, menu_item_id, name, quantity, price) VALUES (%s, %s, %s, %s, %s)",
                (order_id, item['id'], item.get('name', ''), item['qty'], item['price'])
            )
        conn.commit()
        return order_id


def get_all_orders():
    if _use_json_fallback:
        orders = _json_read('orders.json')
        result = []
        for o in reversed(orders):
            items = []
            for it in o.get('items', []):
                items.append({
                    'name': it.get('name', ''),
                    'quantity': it.get('qty', it.get('quantity', 1)),
                    'price': float(it.get('price', 0)),
                    'emoji': it.get('emoji', '🍽️'),
                })
            result.append({
                'id': o['id'],
                'username': o.get('username', '未知用户'),
                'total_amount': float(o['total_amount']),
                'status': o.get('status', 'pending'),
                'created_at': o.get('created_at', ''),
                'items': items,
            })
        return result

    with get_db(dictionary=True) as (conn, cur):
        if conn is None:
            return []
        cur.execute("""
            SELECT o.id, u.username, o.total_amount, o.status, o.created_at
            FROM orders o
            JOIN users u ON o.user_id = u.id
            ORDER BY o.id DESC
        """)
        orders = cur.fetchall()
        for o in orders:
            o['total_amount'] = float(o['total_amount'])
            if hasattr(o['created_at'], 'strftime'):
                o['created_at'] = o['created_at'].strftime('%Y-%m-%d %H:%M:%S')
            cur.execute("""
                SELECT oi.name, oi.quantity, oi.price, m.emoji
                FROM order_items oi
                LEFT JOIN menu_items m ON oi.menu_item_id = m.id
                WHERE oi.order_id = %s
            """, (o['id'],))
            o['items'] = cur.fetchall()
            for item in o['items']:
                item['price'] = float(item['price'])
        return orders


# ---------- 配置操作 ----------

def get_config(key):
    if _use_json_fallback:
        cfg = _json_read('config.json')
        return cfg.get(key, None)

    with get_db() as (conn, cur):
        if conn is None:
            return None
        cur.execute("SELECT config_value FROM config WHERE config_key = %s", (key,))
        row = cur.fetchone()
        return row[0] if row else None


def get_all_config():
    if _use_json_fallback:
        return _json_read('config.json')

    with get_db() as (conn, cur):
        if conn is None:
            return {}
        cur.execute("SELECT config_key, config_value FROM config")
        rows = cur.fetchall()
        return dict(rows)


def set_config(key, value):
    if _use_json_fallback:
        cfg = _json_read('config.json')
        cfg[key] = str(value)
        _json_write('config.json', cfg)
        return

    with get_db() as (conn, cur):
        if conn is None:
            raise RuntimeError('数据库连接不可用')
        cur.execute(
            "INSERT INTO config (config_key, config_value) VALUES (%s, %s) "
            "ON DUPLICATE KEY UPDATE config_value = VALUES(config_value)",
            (key, str(value))
        )
        conn.commit()
