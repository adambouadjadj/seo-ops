import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
csrf = CSRFProtect()

DEFAULT_TEMPLATES = [
    {'title': 'Crawl SF + alertes GSC',               'category': 'technique',    'priority': 'normale', 'sort_order': 1},
    {'title': 'Suivi technique (4XX, 5XX, logs)',      'category': 'technique',    'priority': 'normale', 'sort_order': 2},
    {'title': 'Monitoring backlinks',                  'category': 'analyse',      'priority': 'basse',   'sort_order': 3},
    {'title': 'Recettage tickets SEO',                 'category': 'coordination', 'priority': 'normale', 'sort_order': 4},
    {'title': 'Réunion Croisière',                     'category': 'coordination', 'priority': 'haute',   'sort_order': 5},
    {'title': 'Veille SEO (algo, moves, geo)',         'category': 'analyse',      'priority': 'basse',   'sort_order': 6},
    {'title': 'Optimisation contenu méthode RRF',      'category': 'content',      'priority': 'normale', 'sort_order': 7},
    {'title': 'Optimisation maillage interne & PageRank', 'category': 'technique', 'priority': 'normale', 'sort_order': 8},
]


def create_app(config_object=None):
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)

    if config_object is None:
        from app.config import config_map, DevelopmentConfig
        flask_env = os.getenv('FLASK_ENV', 'development')
        config_object = config_map.get(flask_env, DevelopmentConfig)

    app.config.from_object(config_object)

    db.init_app(app)
    csrf.init_app(app)

    from app.blueprints.main import main_bp
    from app.blueprints.tasks import tasks_bp
    from app.blueprints.templates import templates_bp
    from app.blueprints.webperf import webperf_bp
    from app.blueprints.reporting import reporting_bp
    from app.blueprints.crawl import crawl_bp
    from app.blueprints.gsc import gsc_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(templates_bp)
    app.register_blueprint(webperf_bp)
    app.register_blueprint(reporting_bp)
    app.register_blueprint(crawl_bp)
    app.register_blueprint(gsc_bp)

    with app.app_context():
        db.create_all()
        _migrate_add_template_id()
        _seed_templates()

    return app


def _migrate_add_template_id():
    """Add template_id column and week_date index if they don't exist yet."""
    from sqlalchemy import text
    with db.engine.connect() as conn:
        # Add template_id column (SQLite has no IF NOT EXISTS for columns)
        try:
            conn.execute(text(
                'ALTER TABLE tasks ADD COLUMN template_id INTEGER REFERENCES task_templates(id) ON DELETE SET NULL'
            ))
            conn.commit()
        except Exception as e:
            if 'duplicate column name' not in str(e).lower():
                raise

        # Add index on week_date — primary filter column on every query
        conn.execute(text(
            'CREATE INDEX IF NOT EXISTS idx_tasks_week_date ON tasks (week_date)'
        ))
        conn.commit()


def _seed_templates():
    """Seed default templates on first run."""
    from app.models import TaskTemplate
    if TaskTemplate.query.count() == 0:
        for t in DEFAULT_TEMPLATES:
            db.session.add(TaskTemplate(**t))
        db.session.commit()
