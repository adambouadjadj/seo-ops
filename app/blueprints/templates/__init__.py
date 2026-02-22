from flask import Blueprint

templates_bp = Blueprint('templates', __name__, url_prefix='/templates')

from app.blueprints.templates import routes  # noqa
