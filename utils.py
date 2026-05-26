import re
import smtplib
from email.mime.text import MIMEText
from functools import wraps

from flask import session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

from database import get_user_by_username, get_all_config


def hash_password(password):
    return generate_password_hash(password)


def verify_password(password, password_hash):
    return check_password_hash(password_hash, password)


def is_valid_email(email):
    return re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email)


def send_order_email(username, items, total):
    cfg = get_all_config()
    notify_email = cfg.get('notify_email', '')
    smtp_pass = cfg.get('smtp_pass', '')
    if not notify_email or not smtp_pass:
        return False

    try:
        total_f = float(total) if total else 0.0
    except (TypeError, ValueError):
        total_f = 0.0

    lines = ['<h2>新订单通知</h2>',
             '<p>用户 <b>%s</b> 刚刚下单：</p>' % username,
             '<table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;width:100%%;max-width:500px">',
             '<tr style="background:#FF6B6B;color:#fff;"><th>菜品</th><th>单价</th><th>数量</th><th>小计</th></tr>']
    for item in items:
        try:
            price = float(item.get('price', 0))
        except (TypeError, ValueError):
            price = 0.0
        try:
            qty = int(item.get('qty', 1))
        except (TypeError, ValueError):
            qty = 1
        subtotal = price * qty
        lines.append('<tr><td>%s %s</td><td>¥%.2f</td><td>%d</td><td>¥%.2f</td></tr>' %
                     (item.get('emoji', ''), item.get('name', '菜品'), price, qty, subtotal))
    lines.append('<tr style="font-weight:bold;background:#FFF0F0;"><td colspan="3">合计</td><td>¥%.2f</td></tr>' % total_f)
    lines.append('</table>')
    lines.append('<p style="color:#999;">来自 多巴胺美食点餐系统</p>')

    msg = MIMEText('\n'.join(lines), 'html', 'utf-8')
    msg['Subject'] = '新订单 - %s 下单 ¥%.2f' % (username, total_f)
    msg['From'] = notify_email
    msg['To'] = notify_email

    try:
        server = smtplib.SMTP_SSL('smtp.qq.com', 465, timeout=10)
        server.login(notify_email, smtp_pass)
        server.sendmail(notify_email, [notify_email], msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print('邮件发送失败:', e)
        return False


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'username' not in session:
            return jsonify({'ok': False, 'msg': '请先登录'}), 401
        user = get_user_by_username(session['username'])
        if not user or user.get('role') != 'admin':
            return jsonify({'ok': False, 'msg': '需要管理员权限'}), 403
        return f(*args, **kwargs)
    return decorated
