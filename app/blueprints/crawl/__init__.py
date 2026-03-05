from flask import Blueprint

crawl_bp = Blueprint('crawl', __name__, url_prefix='/crawl')

from app.blueprints.crawl import routes  # noqa
