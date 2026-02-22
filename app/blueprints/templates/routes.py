from flask import render_template, request, abort
from app import db
from app.blueprints.templates import templates_bp
from app.blueprints.templates.forms import TemplateForm
from app.models import TaskTemplate


@templates_bp.route('', methods=['GET'])
def index():
    templates = TaskTemplate.query.order_by(TaskTemplate.sort_order, TaskTemplate.id).all()
    form = TemplateForm()
    return render_template('templates/index.html', templates=templates, form=form)


@templates_bp.route('', methods=['POST'])
def create():
    form = TemplateForm()
    if not form.validate_on_submit():
        templates = TaskTemplate.query.order_by(TaskTemplate.sort_order, TaskTemplate.id).all()
        return render_template('templates/index.html', templates=templates, form=form), 422

    # New template gets sort_order after existing ones
    max_order = db.session.query(db.func.max(TaskTemplate.sort_order)).scalar() or 0
    tmpl = TaskTemplate(
        title=form.title.data.strip(),
        description=form.description.data.strip() if form.description.data else None,
        category=form.category.data,
        priority=form.priority.data,
        sort_order=max_order + 1,
    )
    db.session.add(tmpl)
    db.session.commit()
    return render_template('templates/_template_row.html', tmpl=tmpl)


@templates_bp.route('/<int:tmpl_id>/row', methods=['GET'])
def row(tmpl_id):
    tmpl = db.get_or_404(TaskTemplate, tmpl_id)
    return render_template('templates/_template_row.html', tmpl=tmpl)


@templates_bp.route('/<int:tmpl_id>/edit', methods=['GET'])
def edit_form(tmpl_id):
    tmpl = db.get_or_404(TaskTemplate, tmpl_id)
    form = TemplateForm(obj=tmpl)
    return render_template('templates/_template_edit_form.html', tmpl=tmpl, form=form)


@templates_bp.route('/<int:tmpl_id>', methods=['POST', 'PATCH'])
def update(tmpl_id):
    tmpl = db.get_or_404(TaskTemplate, tmpl_id)
    form = TemplateForm(obj=tmpl)
    if not form.validate_on_submit():
        return render_template('templates/_template_edit_form.html', tmpl=tmpl, form=form), 422

    tmpl.title       = form.title.data.strip()
    tmpl.description = form.description.data.strip() if form.description.data else None
    tmpl.category    = form.category.data
    tmpl.priority    = form.priority.data
    db.session.commit()
    return render_template('templates/_template_row.html', tmpl=tmpl)


@templates_bp.route('/<int:tmpl_id>/toggle', methods=['POST'])
def toggle(tmpl_id):
    tmpl = db.get_or_404(TaskTemplate, tmpl_id)
    tmpl.is_active = not tmpl.is_active
    db.session.commit()
    return render_template('templates/_template_row.html', tmpl=tmpl)


@templates_bp.route('/<int:tmpl_id>', methods=['DELETE', 'POST'])
def delete(tmpl_id):
    if request.method == 'POST' and request.form.get('_method') != 'DELETE':
        abort(405)
    tmpl = db.get_or_404(TaskTemplate, tmpl_id)
    db.session.delete(tmpl)
    db.session.commit()
    return '', 200
