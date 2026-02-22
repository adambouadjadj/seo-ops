from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField
from wtforms.validators import DataRequired, Length, Optional

STATUS_CHOICES = [('todo', 'À faire'), ('en_cours', 'En cours'), ('fait', 'Fait')]
CATEGORY_CHOICES = [
    ('dev', 'Dev'), ('content', 'Content'), ('technique', 'Technique'),
    ('coordination', 'Coordination'), ('analyse', 'Analyse'), ('autre', 'Autre'),
]
PRIORITY_CHOICES = [('haute', 'Haute'), ('normale', 'Normale'), ('basse', 'Basse')]


class TaskForm(FlaskForm):
    title = StringField('Titre', validators=[DataRequired(), Length(max=500)])
    description = TextAreaField('Description', validators=[Optional()])
    status = SelectField('Statut', choices=STATUS_CHOICES, default='todo')
    category = SelectField('Catégorie', choices=CATEGORY_CHOICES, default='autre')
    priority = SelectField('Priorité', choices=PRIORITY_CHOICES, default='normale')
