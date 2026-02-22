from flask import Blueprint

reporting_bp = Blueprint('reporting', __name__, url_prefix='/reporting')

from app.blueprints.reporting import routes  # noqa
