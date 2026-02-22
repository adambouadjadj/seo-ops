from flask import render_template, request, abort, send_file, send_from_directory
from app.blueprints.reporting import reporting_bp
from app.blueprints.reporting.services import (
    stage_files, get_available_task_files, get_past_reports, OUTPUT_DIR,
)


@reporting_bp.route('', methods=['GET'])
def index():
    return render_template(
        'reporting/index.html',
        task_files=get_available_task_files(),
        reports=get_past_reports(),
    )


@reporting_bp.route('/stage', methods=['POST'])
def stage():
    monitorank_file = request.files.get('monitorank')
    gsc_file = request.files.get('gsc')
    task_filename = request.form.get('task_file', '')

    if not monitorank_file or not gsc_file:
        abort(400)

    result = stage_files(monitorank_file, gsc_file, task_filename)
    return render_template('reporting/_staged.html', result=result)


@reporting_bp.route('/preview/<filename>')
def preview(filename):
    safe_path = (OUTPUT_DIR / filename).resolve()
    if safe_path.parent.resolve() != OUTPUT_DIR.resolve():
        abort(403)
    if not safe_path.exists():
        abort(404)
    return send_from_directory(str(OUTPUT_DIR), filename, mimetype='text/html')


@reporting_bp.route('/download/<filename>')
def download(filename):
    safe_path = (OUTPUT_DIR / filename).resolve()
    if safe_path.parent.resolve() != OUTPUT_DIR.resolve():
        abort(403)
    if not safe_path.exists():
        abort(404)
    return send_from_directory(str(OUTPUT_DIR), filename, as_attachment=True)
