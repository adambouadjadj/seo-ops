from flask import render_template, request, abort, send_from_directory
from app.blueprints.crawl import crawl_bp
from app.blueprints.crawl.services import (
    start_crawl, get_job, get_past_crawls, OUTPUT_DIR,
)


@crawl_bp.route('', methods=['GET'])
def index():
    return render_template(
        'crawl/index.html',
        crawls=get_past_crawls(),
    )


@crawl_bp.route('/start', methods=['POST'])
def start():
    url = request.form.get('url', '').strip()
    if not url:
        abort(400)
    job_id = start_crawl(url)
    job = get_job(job_id)
    return render_template('crawl/_status.html', job_id=job_id, job=job)


@crawl_bp.route('/status/<job_id>', methods=['GET'])
def status(job_id):
    job = get_job(job_id)
    if job is None:
        abort(404)
    return render_template('crawl/_status.html', job_id=job_id, job=job)


@crawl_bp.route('/preview/<filename>', methods=['GET'])
def preview(filename):
    safe_path = (OUTPUT_DIR / filename).resolve()
    if safe_path.parent.resolve() != OUTPUT_DIR.resolve():
        abort(403)
    if not safe_path.exists():
        abort(404)
    return send_from_directory(str(OUTPUT_DIR), filename, mimetype='text/html')


@crawl_bp.route('/download/<filename>', methods=['GET'])
def download(filename):
    safe_path = (OUTPUT_DIR / filename).resolve()
    if safe_path.parent.resolve() != OUTPUT_DIR.resolve():
        abort(403)
    if not safe_path.exists():
        abort(404)
    return send_from_directory(str(OUTPUT_DIR), filename, as_attachment=True)
