from datetime import datetime, date, timedelta
from pathlib import Path
import re

from app import db
from app.models import Task, TaskTemplate, VALID_STATUSES, VALID_CATEGORIES, VALID_PRIORITIES, PRIORITY_ORDER

BASE_DIR  = Path(__file__).parent.parent.parent.parent  # seo-ops/
TASKS_DIR = BASE_DIR / 'tasks'


# ─── Week helpers ────────────────────────────────────────────────────────────

def get_week_monday(d=None):
    if d is None:
        d = date.today()
    return d - timedelta(days=d.weekday())


def parse_week_str(year_week_str):
    if not re.match(r'^\d{4}-W\d{1,2}$', year_week_str):
        raise ValueError(f"Invalid week format: {year_week_str}")
    return datetime.strptime(f"{year_week_str}-1", "%G-W%V-%u").date()


def date_to_week_str(d):
    year, week, _ = d.isocalendar()
    return f"{year}-W{week:02d}"


# ─── Task CRUD ────────────────────────────────────────────────────────────────

def get_tasks_for_week(week_monday):
    tasks = Task.query.filter_by(week_date=week_monday).all()
    return sorted(tasks, key=lambda t: (
        {'todo': 0, 'en_cours': 1, 'fait': 2}.get(t.status, 9),
        PRIORITY_ORDER.get(t.priority, 9),
        t.created_at,
    ))


def create_task(title, description=None, status='todo', category='autre',
                priority='normale', week_monday=None, template_id=None):
    if status   not in VALID_STATUSES:   raise ValueError(f"Invalid status: {status}")
    if category not in VALID_CATEGORIES: raise ValueError(f"Invalid category: {category}")
    if priority not in VALID_PRIORITIES: raise ValueError(f"Invalid priority: {priority}")

    task = Task(
        title=title.strip(),
        description=description.strip() if description else None,
        status=status,
        category=category,
        priority=priority,
        week_date=week_monday or get_week_monday(),
        template_id=template_id,
    )
    db.session.add(task)
    db.session.commit()
    return task


def update_task(task, title=None, description=None, status=None,
                category=None, priority=None):
    if title       is not None: task.title       = title.strip()
    if description is not None: task.description = description.strip() if description else None
    if status      is not None:
        if status not in VALID_STATUSES: raise ValueError(f"Invalid status: {status}")
        task.status = status
    if category    is not None:
        if category not in VALID_CATEGORIES: raise ValueError(f"Invalid category: {category}")
        task.category = category
    if priority    is not None:
        if priority not in VALID_PRIORITIES: raise ValueError(f"Invalid priority: {priority}")
        task.priority = priority
    db.session.commit()
    return task


def delete_task(task):
    db.session.delete(task)
    db.session.commit()


def cycle_status(task):
    task.status = {'todo': 'en_cours', 'en_cours': 'fait', 'fait': 'todo'}.get(task.status, 'todo')
    db.session.commit()
    return task


# ─── Recurring templates ──────────────────────────────────────────────────────

def generate_recurring_tasks(week_monday):
    """
    Create task instances from active templates for the given week.
    Skips templates already instantiated for this week (idempotent).
    Returns list of newly created tasks.
    """
    templates = (TaskTemplate.query
                 .filter_by(is_active=True)
                 .order_by(TaskTemplate.sort_order, TaskTemplate.id)
                 .all())
    existing_ids = {
        row[0] for row in
        db.session.query(Task.template_id).filter(
            Task.week_date == week_monday,
            Task.template_id.isnot(None),
        ).all()
    }
    created = []
    for tmpl in templates:
        if tmpl.id in existing_ids:
            continue
        task = Task(
            title=tmpl.title,
            description=tmpl.description,
            status='todo',
            category=tmpl.category,
            priority=tmpl.priority,
            week_date=week_monday,
            template_id=tmpl.id,
        )
        db.session.add(task)
        created.append(task)
    if created:
        db.session.commit()
    return created


# ─── Export ───────────────────────────────────────────────────────────────────

def export_week_to_txt(week_monday):
    """
    Export tasks for week_monday to tasks/task_DD_MM_YY.txt.

    Format:
        Actions terminées :
        • Titre tâche faite
          Description si présente

        Actions prévues semaine prochaine :
        • Titre tâche todo/en_cours
          Description si présente

    Returns the Path of the written file.
    """
    TASKS_DIR.mkdir(parents=True, exist_ok=True)

    filename = f"task_{week_monday.strftime('%d_%m_%y')}.txt"
    filepath = TASKS_DIR / filename

    # Path traversal guard
    resolved      = filepath.resolve()
    tasks_resolved = TASKS_DIR.resolve()
    try:
        resolved.relative_to(tasks_resolved)
    except ValueError:
        raise ValueError("Path traversal detected — export aborted.")

    tasks = Task.query.filter_by(week_date=week_monday).all()

    done    = sorted([t for t in tasks if t.status == 'fait'],
                     key=lambda t: (PRIORITY_ORDER.get(t.priority, 9), t.created_at))
    pending = sorted([t for t in tasks if t.status != 'fait'],
                     key=lambda t: (PRIORITY_ORDER.get(t.priority, 9), t.created_at))

    def _format_task(t):
        lines = [f"• {t.title}"]
        if t.description:
            lines.append(f"  {t.description}")
        return '\n'.join(lines)

    sections = []

    if done:
        block = '\n'.join(_format_task(t) for t in done)
        sections.append(f"Actions terminées :\n{block}")

    if pending:
        block = '\n'.join(_format_task(t) for t in pending)
        sections.append(f"Actions prévues semaine prochaine :\n{block}")

    filepath.write_text('\n\n'.join(sections), encoding='utf-8')
    return filepath
