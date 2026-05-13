from flask import render_template, request, abort, send_file, send_from_directory
from app.blueprints.reporting import reporting_bp
from app.blueprints.reporting.services import (
    stage_files, fetch_gsc_for_reporting, get_available_task_files, get_past_reports, OUTPUT_DIR,
)


@reporting_bp.route('', methods=['GET'])
def index():
    return render_template(
        'reporting/index.html',
        task_files=get_available_task_files(),
        reports=get_past_reports(),
    )


@reporting_bp.route('/fetch-gsc', methods=['POST'])
def fetch_gsc():
    try:
        path = fetch_gsc_for_reporting()
        return render_template('reporting/_gsc_fetched.html', filename=path.name, error=None)
    except Exception as e:
        return render_template('reporting/_gsc_fetched.html', filename=None, error=str(e))


@reporting_bp.route('/stage', methods=['POST'])
def stage():
    monitorank_file = request.files.get('monitorank')
    gsc_file = request.files.get('gsc')
    task_filename = request.form.get('task_file', '')
    gsc_prefetched = request.form.get('gsc_prefetched', '')

    if not monitorank_file:
        abort(400)
    if not gsc_file and not gsc_prefetched:
        abort(400)

    result = stage_files(monitorank_file, gsc_file, task_filename, gsc_prefetched)
    return render_template('reporting/_staged.html', result=result)


@reporting_bp.route('/preview/<path:filename>')
def preview(filename):
    safe_path = (OUTPUT_DIR / filename).resolve()
    if not safe_path.is_relative_to(OUTPUT_DIR.resolve()):
        abort(403)
    if not safe_path.exists():
        abort(404)
    return send_from_directory(str(safe_path.parent), safe_path.name, mimetype='text/html')


@reporting_bp.route('/download/<path:filename>')
def download(filename):
    safe_path = (OUTPUT_DIR / filename).resolve()
    if not safe_path.is_relative_to(OUTPUT_DIR.resolve()):
        abort(403)
    if not safe_path.exists():
        abort(404)
    return send_from_directory(str(safe_path.parent), safe_path.name, as_attachment=True)
