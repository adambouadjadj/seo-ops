from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField
from wtforms.validators import DataRequired, Length, Optional

from app.blueprints.tasks.forms import CATEGORY_CHOICES, PRIORITY_CHOICES


class TemplateForm(FlaskForm):
    title       = StringField('Titre', validators=[DataRequired(), Length(max=500)])
    description = TextAreaField('Description par défaut', validators=[Optional()])
    category    = SelectField('Catégorie', choices=CATEGORY_CHOICES, default='autre')
    priority    = SelectField('Priorité',  choices=PRIORITY_CHOICES, default='normale')
