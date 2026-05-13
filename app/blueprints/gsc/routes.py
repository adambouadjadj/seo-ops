import datetime

from flask import render_template, request, Response
from app.blueprints.gsc import gsc_bp
from app.blueprints.gsc.services import (
    run_insights, list_tracked_pages, add_tracked_page,
    delete_tracked_page, take_snapshot_for, refresh_due_snapshots,
    snapshot_map, parse_top_queries,
    run_questions_longtail, get_semrush_questions, build_questions_csv,
    build_insights_csv,
)


@gsc_bp.route('', methods=['GET'])
def index():
    pages = list_tracked_pages()
    return render_template(
        'gsc/index.html',
        pages=pages,
        snapshot_map=snapshot_map,
        day_offsets=_day_offsets(),
        offset_labels=_offset_labels(),
    )


@gsc_bp.route('/insights', methods=['POST'])
def insights():
    days = int(request.form.get('days', 90))
    data = run_insights(days=days)
    return render_template('gsc/_insights.html', data=data, days=days)


@gsc_bp.route('/tracker', methods=['POST'])
def tracker_add():
    url    = request.form.get('url', '').strip()
    label  = request.form.get('label', '').strip()
    reason = request.form.get('reason', '').strip() or None
    if not url or not label:
        return render_template('gsc/_tracker_error.html',
                               msg="URL et libellé requis."), 422
    try:
        page = add_tracked_page(url, label, reason)
    except Exception as e:
        return render_template('gsc/_tracker_error.html', msg=str(e)), 500
    pages = list_tracked_pages()
    return render_template(
        'gsc/_tracker_table.html',
        pages=pages,
        snapshot_map=snapshot_map,
        day_offsets=_day_offsets(),
        offset_labels=_offset_labels(),
    )


@gsc_bp.route('/tracker/<int:page_id>/snapshot', methods=['POST'])
def tracker_snapshot(page_id):
    offset = int(request.args.get('offset', 0))
    try:
        page = take_snapshot_for(page_id, offset)
    except Exception as e:
        return render_template('gsc/_tracker_error.html', msg=str(e)), 500
    pages = list_tracked_pages()
    return render_template(
        'gsc/_tracker_table.html',
        pages=pages,
        snapshot_map=snapshot_map,
        day_offsets=_day_offsets(),
        offset_labels=_offset_labels(),
    )


@gsc_bp.route('/tracker/refresh', methods=['POST'])
def tracker_refresh():
    result = refresh_due_snapshots()
    pages  = list_tracked_pages()
    return render_template(
        'gsc/_tracker_table.html',
        pages=pages,
        snapshot_map=snapshot_map,
        day_offsets=_day_offsets(),
        offset_labels=_offset_labels(),
        refresh_result=result,
    )


@gsc_bp.route('/tracker/<int:page_id>', methods=['DELETE'])
def tracker_delete(page_id):
    delete_tracked_page(page_id)
    pages = list_tracked_pages()
    return render_template(
        'gsc/_tracker_table.html',
        pages=pages,
        snapshot_map=snapshot_map,
        day_offsets=_day_offsets(),
        offset_labels=_offset_labels(),
    )


@gsc_bp.route('/tracker/<int:page_id>/queries', methods=['GET'])
def tracker_queries(page_id):
    from app.models import PageSnapshot
    offset = int(request.args.get('offset', 0))
    snap = PageSnapshot.query.filter_by(
        tracked_page_id=page_id, day_offset=offset
    ).first_or_404()
    queries = parse_top_queries(snap)
    return render_template('gsc/_queries_modal.html', queries=queries,
                           offset_label=_offset_labels().get(offset, f"J+{offset}"))


# ── Questions GEO ─────────────────────────────────────────────────────────────

@gsc_bp.route('/insights/export', methods=['GET'])
def insights_export():
    days = int(request.args.get('days', 90))
    data = run_insights(days=days)
    if "error" in data:
        return data["error"], 500
    csv_content = build_insights_csv(data)
    filename = f"gsc_insights_{datetime.date.today().strftime('%Y-%m-%d')}.csv"
    return Response(
        "\ufeff" + csv_content,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@gsc_bp.route('/questions/gsc', methods=['POST'])
def questions_gsc():
    days = int(request.form.get('days', 28))
    data = run_questions_longtail(days=days)
    return render_template('gsc/_questions_gsc.html', data=data, days=days)


@gsc_bp.route('/questions/semrush', methods=['POST'])
def questions_semrush():
    keyword  = request.form.get('keyword', '').strip()
    database = request.form.get('database', 'fr')
    data     = get_semrush_questions(keyword, database)
    return render_template('gsc/_questions_semrush.html', data=data)


@gsc_bp.route('/questions/export', methods=['GET'])
def questions_export():
    days     = int(request.args.get('days', 28))
    keyword  = request.args.get('keyword', '').strip()
    database = request.args.get('database', 'fr')

    gsc_data     = run_questions_longtail(days=days)
    semrush_data = get_semrush_questions(keyword, database) if keyword else {"rows": []}
    csv_content  = build_questions_csv(gsc_data, semrush_data)

    filename = f"gsc_questions_GEO_{datetime.date.today().strftime('%Y-%m-%d')}.csv"
    return Response(
        "\ufeff" + csv_content,   # BOM UTF-8 pour Excel
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ── Helpers ────────────────────────────────────────────────────────────────────

def _day_offsets():
    return [-7, 0, 7, 14, 30, 60]


def _offset_labels():
    return {-7: "J-7 (base)", 0: "J0", 7: "J+7", 14: "J+14", 30: "J+30", 60: "J+60"}
