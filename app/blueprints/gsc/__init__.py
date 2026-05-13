from flask import Blueprint

gsc_bp = Blueprint('gsc', __name__, url_prefix='/gsc')

from app.blueprints.gsc import routes  # noqa: E402, F401
