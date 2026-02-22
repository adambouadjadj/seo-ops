from datetime import timedelta
from flask import render_template, request, abort, send_file
from app import db
from app.blueprints.tasks import tasks_bp
from app.blueprints.tasks.forms import TaskForm
from app.blueprints.tasks.services import (
    get_week_monday, parse_week_str, date_to_week_str,
    get_tasks_for_week, create_task, update_task, delete_task,
    cycle_status, export_week_to_txt, generate_recurring_tasks,
)
from app.models import Task, VALID_STATUSES


def _is_htmx():
    return request.headers.get('HX-Request') == 'true'


def _get_carry_over_count(week_monday):
    prev_monday = week_monday - timedelta(weeks=1)
    return Task.query.filter(
        Task.week_date == prev_monday,
        Task.status != 'fait',
        Task.template_id.is_(None),
    ).count()


def _stats_oob(week_monday):
    tasks = Task.query.filter_by(week_date=week_monday).all()
    return render_template(
        'tasks/_stats.html',
        todo_count=sum(1 for t in tasks if t.status == 'todo'),
        en_cours_count=sum(1 for t in tasks if t.status == 'en_cours'),
        fait_count=sum(1 for t in tasks if t.status == 'fait'),
        total=len(tasks),
        oob=True,
    )


def _render_task_list(tasks):
    return ''.join(render_template('tasks/_task_card.html', task=t) for t in tasks)


@tasks_bp.route('', methods=['GET'])
def index():
    week_monday = get_week_monday()
    tasks       = get_tasks_for_week(week_monday)
    week_str    = date_to_week_str(week_monday)
    return render_template(
        'tasks/index.html',
        tasks=tasks, form=TaskForm(),
        week_monday=week_monday, week_str=week_str,
        prev_week=date_to_week_str(week_monday - timedelta(weeks=1)),
        next_week=date_to_week_str(week_monday + timedelta(weeks=1)),
        is_current_week=True,
        carry_over_count=_get_carry_over_count(week_monday),
    )


@tasks_bp.route('/week/<string:year_week>', methods=['GET'])
def week_view(year_week):
    try:
        week_monday = parse_week_str(year_week)
    except ValueError:
        abort(400)
    tasks = get_tasks_for_week(week_monday)
    current_week_str = date_to_week_str(get_week_monday())
    is_current_week  = (year_week == current_week_str)
    return render_template(
        'tasks/index.html',
        tasks=tasks, form=TaskForm(),
        week_monday=week_monday, week_str=year_week,
        prev_week=date_to_week_str(week_monday - timedelta(weeks=1)),
        next_week=date_to_week_str(week_monday + timedelta(weeks=1)),
        is_current_week=is_current_week,
        carry_over_count=_get_carry_over_count(week_monday) if is_current_week else 0,
    )


@tasks_bp.route('', methods=['POST'])
def create():
    form = TaskForm()
    if not form.validate_on_submit():
        return render_template('tasks/_task_form.html', form=form), 422

    week_str = request.form.get('week_str', '')
    try:
        week_monday = parse_week_str(week_str) if week_str else get_week_monday()
    except ValueError:
        week_monday = get_week_monday()

    task = create_task(
        title=form.title.data, description=form.description.data,
        status=form.status.data, category=form.category.data,
        priority=form.priority.data, week_monday=week_monday,
    )

    if _is_htmx():
        return render_template('tasks/_task_card.html', task=task) + _stats_oob(week_monday)

    return render_template(
        'tasks/index.html',
        tasks=get_tasks_for_week(week_monday), form=TaskForm(),
        week_monday=week_monday, week_str=week_str or date_to_week_str(week_monday),
        prev_week=date_to_week_str(week_monday - timedelta(weeks=1)),
        next_week=date_to_week_str(week_monday + timedelta(weeks=1)),
        is_current_week=True,
    )


@tasks_bp.route('/generate', methods=['POST'])
def generate():
    """Generate recurring tasks from active templates for the given week."""
    week_str = request.form.get('week_str', '')
    try:
        week_monday = parse_week_str(week_str) if week_str else get_week_monday()
    except ValueError:
        week_monday = get_week_monday()

    created = generate_recurring_tasks(week_monday)
    tasks   = get_tasks_for_week(week_monday)

    cards_html  = _render_task_list(tasks)
    banner_html = render_template(
        'tasks/_carry_over_banner.html',
        carry_over_count=_get_carry_over_count(week_monday), week_str=week_str, oob=True,
    )
    return cards_html + _stats_oob(week_monday) + banner_html


@tasks_bp.route('/<int:task_id>/status', methods=['PATCH', 'POST'])
def update_status(task_id):
    task       = db.get_or_404(Task, task_id)
    new_status = request.form.get('status')
    if new_status and new_status in VALID_STATUSES:
        update_task(task, status=new_status)
    else:
        cycle_status(task)
    return render_template('tasks/_task_card.html', task=task) + _stats_oob(task.week_date)


@tasks_bp.route('/<int:task_id>/edit', methods=['GET'])
def edit_form(task_id):
    task = db.get_or_404(Task, task_id)
    return render_template('tasks/_task_edit_form.html', task=task, form=TaskForm(obj=task))


@tasks_bp.route('/<int:task_id>/card', methods=['GET'])
def card(task_id):
    task = db.get_or_404(Task, task_id)
    return render_template('tasks/_task_card.html', task=task)


@tasks_bp.route('/<int:task_id>', methods=['PATCH', 'POST'])
def update(task_id):
    task = db.get_or_404(Task, task_id)
    form = TaskForm(obj=task)
    if not form.validate_on_submit():
        return render_template('tasks/_task_edit_form.html', task=task, form=form), 422

    update_task(task, title=form.title.data, description=form.description.data,
                status=form.status.data, category=form.category.data, priority=form.priority.data)
    return render_template('tasks/_task_card.html', task=task) + _stats_oob(task.week_date)


@tasks_bp.route('/<int:task_id>', methods=['DELETE'])
def delete(task_id):
    task        = db.get_or_404(Task, task_id)
    week_monday = task.week_date
    delete_task(task)
    return _stats_oob(week_monday), 200


@tasks_bp.route('/carry-over', methods=['POST'])
def carry_over_tasks():
    """Move all unfinished manual tasks from last week to the current week."""
    week_str = request.form.get('week_str', '')
    try:
        week_monday = parse_week_str(week_str) if week_str else get_week_monday()
    except ValueError:
        week_monday = get_week_monday()

    prev_monday = week_monday - timedelta(weeks=1)
    to_carry = Task.query.filter(
        Task.week_date == prev_monday,
        Task.status != 'fait',
        Task.template_id.is_(None),
    ).all()
    for task in to_carry:
        task.week_date = week_monday
    db.session.commit()

    tasks      = get_tasks_for_week(week_monday)
    cards_html = _render_task_list(tasks)
    banner_html = render_template(
        'tasks/_carry_over_banner.html',
        carry_over_count=0, week_str=week_str, oob=True,
    )
    return cards_html + _stats_oob(week_monday) + banner_html


@tasks_bp.route('/complete-all', methods=['POST'])
def complete_all():
    """Mark all tasks for the given week as 'fait'."""
    week_str = request.form.get('week_str', '')
    try:
        week_monday = parse_week_str(week_str) if week_str else get_week_monday()
    except ValueError:
        week_monday = get_week_monday()

    Task.query.filter_by(week_date=week_monday).update({'status': 'fait'})
    db.session.commit()

    tasks      = get_tasks_for_week(week_monday)
    cards_html = _render_task_list(tasks)
    return cards_html + _stats_oob(week_monday)


@tasks_bp.route('/clear', methods=['POST'])
def clear_week():
    """Delete all tasks for the given week."""
    week_str = request.form.get('week_str', '')
    try:
        week_monday = parse_week_str(week_str) if week_str else get_week_monday()
    except ValueError:
        week_monday = get_week_monday()

    Task.query.filter_by(week_date=week_monday).delete()
    db.session.commit()

    empty_list = render_template('tasks/_empty_state.html')
    banner_html = render_template(
        'tasks/_carry_over_banner.html',
        carry_over_count=0, week_str=week_str, oob=True,
    )
    return empty_list + _stats_oob(week_monday) + banner_html


@tasks_bp.route('/export', methods=['GET'])
def export():
    return _do_export(get_week_monday())


@tasks_bp.route('/export/<string:year_week>', methods=['GET'])
def export_week(year_week):
    try:
        week_monday = parse_week_str(year_week)
    except ValueError:
        abort(400)
    return _do_export(week_monday)


def _do_export(week_monday):
    filepath = export_week_to_txt(week_monday)
    return send_file(filepath, as_attachment=True,
                     download_name=filepath.name, mimetype='text/plain')
