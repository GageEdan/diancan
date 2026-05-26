import os
import uuid
import traceback

from flask import Blueprint, request, jsonify, session

from config import BASE_DIR
from database import (
    get_all_menu, add_menu_item, update_menu_item, delete_menu_item,
    get_user_by_username, create_user, update_user_password, update_user_avatar,
    get_all_config, get_config, set_config, create_order, get_all_orders,
    update_menu_order, get_daily_revenue
)
from utils import hash_password, verify_password, send_order_email, admin_required

api_bp = Blueprint('api', __name__)

UPLOAD_DIR = os.path.join(BASE_DIR, 'static', 'images')
AVATAR_DIR = os.path.join(BASE_DIR, 'static', 'avatars')
ALLOWED_EXT = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp'}


# ---------- 认证 ----------

@api_bp.route('/api/login', methods=['POST'])
def api_login():
    d = request.get_json()
    username = d.get('username', '').strip()
    password = d.get('password', '')

    if not username or not password:
        return jsonify({'ok': False, 'msg': '账号和密码不能为空哟~'})

    user = get_user_by_username(username)
    if user and verify_password(password, user['password_hash']):
        session['username'] = username
        return jsonify({'ok': True, 'msg': '登录成功！欢迎回来~'})

    return jsonify({'ok': False, 'msg': '账号或密码错误，再试试看~'})


@api_bp.route('/api/register', methods=['POST'])
def api_register():
    d = request.get_json()
    username = d.get('username', '').strip()
    password = d.get('password', '')

    if not username or not password:
        return jsonify({'ok': False, 'msg': '账号和密码不能为空哟~'})
    if len(username) < 2:
        return jsonify({'ok': False, 'msg': '账号至少2个字符哟~'})
    if len(password) < 4:
        return jsonify({'ok': False, 'msg': '密码至少4位哟~'})

    if get_user_by_username(username):
        return jsonify({'ok': False, 'msg': '这个账号已经被注册啦，换一个吧~'})

    create_user(username, hash_password(password), 'user')
    session['username'] = username
    return jsonify({'ok': True, 'msg': '注册成功！欢迎新朋友~'})


@api_bp.route('/api/logout', methods=['POST'])
def api_logout():
    session.pop('username', None)
    return jsonify({'ok': True})


# ---------- 菜单 ----------

@api_bp.route('/api/menu')
def api_menu():
    return jsonify(get_all_menu())


# ---------- 用户信息 ----------

@api_bp.route('/api/user')
def api_user():
    u = session.get('username')
    if not u:
        return jsonify({'ok': False})
    user = get_user_by_username(u)
    if not user:
        return jsonify({'ok': False})
    return jsonify({
        'ok': True,
        'username': user['username'],
        'role': user.get('role', 'user'),
        'avatar': user.get('avatar', '')
    })


# ---------- 用户：个人信息管理 ----------

@api_bp.route('/api/user/profile', methods=['PUT'])
def api_update_profile():
    if 'username' not in session:
        return jsonify({'ok': False, 'msg': '请先登录'}), 401

    d = request.get_json()
    new_password = d.get('password', '').strip()

    if new_password:
        if len(new_password) < 4:
            return jsonify({'ok': False, 'msg': '密码至少4位哟~'})
        update_user_password(session['username'], hash_password(new_password))

    return jsonify({'ok': True, 'msg': '个人信息已更新'})


@api_bp.route('/api/user/avatar', methods=['POST'])
def api_upload_avatar():
    if 'username' not in session:
        return jsonify({'ok': False, 'msg': '请先登录'}), 401

    if 'file' not in request.files:
        return jsonify({'ok': False, 'msg': '没有选择文件'}), 400
    file = request.files['file']
    if not file.filename:
        return jsonify({'ok': False, 'msg': '没有选择文件'}), 400

    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in ALLOWED_EXT:
        return jsonify({'ok': False, 'msg': '不支持的图片格式'}), 400

    os.makedirs(AVATAR_DIR, exist_ok=True)
    filename = f"avatar_{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(AVATAR_DIR, filename))

    update_user_avatar(session['username'], filename)

    return jsonify({'ok': True, 'filename': filename})


# ---------- 管理员：菜单管理 ----------

@api_bp.route('/api/menu', methods=['POST'])
@admin_required
def api_menu_add():
    d = request.get_json()
    name = d.get('name', '').strip()
    price = d.get('price')
    category = d.get('category', '').strip()
    emoji = d.get('emoji', '').strip()
    image = d.get('image', '').strip()

    if not name or price is None or not category:
        return jsonify({'ok': False, 'msg': '名称、价格和分类不能为空'})

    new_id = add_menu_item(name, float(price), category, emoji or '🍽️', image)
    return jsonify({'ok': True, 'msg': '菜品已添加', 'id': new_id})


@api_bp.route('/api/menu/<int:dish_id>', methods=['PUT'])
@admin_required
def api_menu_update(dish_id):
    d = request.get_json()
    kwargs = {}
    if 'name' in d:
        kwargs['name'] = d['name'].strip()
    if 'price' in d:
        kwargs['price'] = float(d['price'])
    if 'category' in d:
        kwargs['category_name'] = d['category'].strip()
    if 'emoji' in d:
        kwargs['emoji'] = d['emoji'].strip()
    if 'image' in d:
        kwargs['image'] = d['image'].strip()

    if not kwargs:
        return jsonify({'ok': False, 'msg': '没有要更新的内容'})

    update_menu_item(dish_id, **kwargs)
    return jsonify({'ok': True, 'msg': '菜品已更新'})


@api_bp.route('/api/menu/<int:dish_id>', methods=['DELETE'])
@admin_required
def api_menu_delete(dish_id):
    delete_menu_item(dish_id)
    return jsonify({'ok': True, 'msg': '菜品已删除'})


# ---------- 管理员：图片上传 ----------

@api_bp.route('/api/upload', methods=['POST'])
@admin_required
def api_upload():
    if 'file' not in request.files:
        return jsonify({'ok': False, 'msg': '没有选择文件'}), 400
    file = request.files['file']
    if not file.filename:
        return jsonify({'ok': False, 'msg': '没有选择文件'}), 400

    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in ALLOWED_EXT:
        return jsonify({'ok': False, 'msg': '不支持的图片格式，支持 jpg/png/gif/webp/bmp'}), 400

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(UPLOAD_DIR, filename))
    return jsonify({'ok': True, 'filename': filename})


# ---------- 管理员：邮箱配置 ----------

@api_bp.route('/api/config', methods=['GET'])
@admin_required
def api_config_get():
    cfg = get_all_config()
    return jsonify({'ok': True, 'config': {
        'notify_email': cfg.get('notify_email', ''),
        'smtp_pass': '***' if cfg.get('smtp_pass') else ''
    }})


@api_bp.route('/api/config', methods=['PUT'])
@admin_required
def api_config_update():
    d = request.get_json()
    if 'notify_email' in d:
        set_config('notify_email', d['notify_email'].strip())
    if 'smtp_pass' in d and d['smtp_pass'] and d['smtp_pass'] != '***':
        set_config('smtp_pass', d['smtp_pass'])
    return jsonify({'ok': True, 'msg': '邮箱配置已更新'})


# ---------- 用户：下单结算 ----------

@api_bp.route('/api/checkout', methods=['POST'])
def api_checkout():
    if 'username' not in session:
        return jsonify({'ok': False, 'msg': '请先登录'}), 401

    d = request.get_json()
    items = d.get('items', [])
    total = d.get('total', 0)
    if total is None:
        total = 0

    if not items:
        return jsonify({'ok': False, 'msg': '订单数据有误'}), 400

    user = get_user_by_username(session['username'])
    if not user:
        return jsonify({'ok': False, 'msg': '用户不存在'}), 404

    try:
        create_order(user['id'], total, items, username=session['username'])
    except Exception as e:
        traceback.print_exc()
        return jsonify({'ok': False, 'msg': '订单提交失败，请稍后重试'}), 500

    username = session['username']
    try:
        email_sent = send_order_email(username, items, total)
    except Exception as e:
        traceback.print_exc()
        email_sent = False

    return jsonify({
        'ok': True,
        'msg': '下单成功！订单已保存' + (' 已通知商家~' if email_sent else ''),
        'email_sent': email_sent
    })


# ---------- 菜品排序 ----------

@api_bp.route('/api/menu/reorder', methods=['POST'])
def api_menu_reorder():
    if 'username' not in session:
        return jsonify({'ok': False, 'msg': '请先登录'}), 401
    d = request.get_json()
    items = d.get('items', [])
    if not items:
        return jsonify({'ok': False, 'msg': '排序数据为空'}), 400
    update_menu_order(items)
    return jsonify({'ok': True, 'msg': '排序已保存'})


# ---------- 每日流水 ----------

@api_bp.route('/api/revenue')
def api_revenue():
    if 'username' not in session:
        return jsonify({'ok': False, 'msg': '请先登录'}), 401
    days = request.args.get('days', 365, type=int)
    daily = get_daily_revenue(days)
    return jsonify({'ok': True, 'daily': daily})


# ---------- 订单记录 ----------

@api_bp.route('/api/orders')
def api_orders():
    if 'username' not in session:
        return jsonify({'ok': False, 'msg': '请先登录'}), 401
    return jsonify({'ok': True, 'orders': get_all_orders()})
