from flask import Blueprint

webperf_bp = Blueprint('webperf', __name__, url_prefix='/webperf')

from app.blueprints.webperf import routes  # noqa
