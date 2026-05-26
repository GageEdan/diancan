from flask import Blueprint, render_template, session, redirect

pages_bp = Blueprint('pages', __name__)


@pages_bp.route('/')
def index():
    if 'username' in session:
        return redirect('/menu')
    return redirect('/login')


@pages_bp.route('/login')
def login_page():
    if 'username' in session:
        return redirect('/menu')
    return render_template('login.html')


@pages_bp.route('/menu')
def menu_page():
    if 'username' not in session:
        return redirect('/login')
    return render_template('menu.html')


@pages_bp.route('/wheel')
def wheel_page():
    if 'username' not in session:
        return redirect('/login')
    return render_template('wheel.html')
