from datetime import date, timedelta
from app import db


def get_week_monday(d=None):
    if d is None:
        d = date.today()
    return d - timedelta(days=d.weekday())


VALID_STATUSES    = ('todo', 'en_cours', 'fait')
VALID_CATEGORIES  = ('dev', 'content', 'technique', 'coordination', 'analyse', 'autre')
VALID_PRIORITIES  = ('haute', 'normale', 'basse')
PRIORITY_ORDER    = {'haute': 0, 'normale': 1, 'basse': 2}
STATUS_ORDER      = {'todo': 0, 'en_cours': 1, 'fait': 2}


class TaskTemplate(db.Model):
    __tablename__ = 'task_templates'

    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title       = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category    = db.Column(db.String(30), nullable=False, default='autre')
    priority    = db.Column(db.String(10), nullable=False, default='normale')
    is_active   = db.Column(db.Boolean, nullable=False, default=True)
    sort_order  = db.Column(db.Integer, nullable=False, default=0)
    created_at  = db.Column(db.DateTime, nullable=False, default=db.func.now())

    @property
    def category_label(self):
        return {'dev': 'Dev', 'content': 'Content', 'technique': 'Technique',
                'coordination': 'Coordination', 'analyse': 'Analyse', 'autre': 'Autre'
                }.get(self.category, self.category)

    @property
    def priority_label(self):
        return {'haute': 'Haute', 'normale': 'Normale', 'basse': 'Basse'}.get(self.priority, self.priority)


class Task(db.Model):
    __tablename__ = 'tasks'

    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title       = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status      = db.Column(db.String(20), nullable=False, default='todo')
    category    = db.Column(db.String(30), nullable=False, default='autre')
    priority    = db.Column(db.String(10), nullable=False, default='normale')
    week_date   = db.Column(db.Date, nullable=False, default=get_week_monday)
    created_at  = db.Column(db.DateTime, nullable=False, default=db.func.now())
    updated_at  = db.Column(db.DateTime, nullable=False,
                            default=db.func.now(), onupdate=db.func.now())
    template_id = db.Column(db.Integer,
                            db.ForeignKey('task_templates.id', ondelete='SET NULL'),
                            nullable=True)

    @property
    def is_recurring(self):
        return self.template_id is not None

    @property
    def status_label(self):
        return {'todo': 'À faire', 'en_cours': 'En cours', 'fait': 'Fait'}.get(self.status, self.status)

    @property
    def category_label(self):
        return {'dev': 'Dev', 'content': 'Content', 'technique': 'Technique',
                'coordination': 'Coordination', 'analyse': 'Analyse', 'autre': 'Autre'
                }.get(self.category, self.category)

    @property
    def priority_label(self):
        return {'haute': 'Haute', 'normale': 'Normale', 'basse': 'Basse'}.get(self.priority, self.priority)

    @property
    def next_status(self):
        return {'todo': 'en_cours', 'en_cours': 'fait', 'fait': 'todo'}.get(self.status, 'todo')
