from flask import render_template, request
from app.blueprints.webperf import webperf_bp
from app.blueprints.webperf.services import run_script, get_month_options, get_slides_url


@webperf_bp.route('', methods=['GET'])
def index():
    return render_template(
        'webperf/index.html',
        month_options=get_month_options(),
        slides_url=get_slides_url(),
    )


@webperf_bp.route('/collect', methods=['POST'])
def collect():
    month = request.form.get('month', get_month_options()[0])
    result = run_script('webperf_runner.py', [month])
    return render_template(
        'webperf/_output.html',
        result=result,
        action='Collecte PSI',
        month=month,
    )


@webperf_bp.route('/update-slides', methods=['POST'])
def update_slides():
    result = run_script('slides_updater.py')
    return render_template(
        'webperf/_output.html',
        result=result,
        action='Mise à jour Google Slides',
        month=None,
    )
