from flask import redirect, url_for
from app.blueprints.main import main_bp


@main_bp.route('/')
def index():
    return redirect(url_for('tasks.index'))
