import subprocess
import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]  # seo-ops/


def run_script(script_name: str, args: list = None) -> dict:
    """Run a tool script as a subprocess from PROJECT_ROOT.

    Returns {'success': bool, 'output': str, 'error': str}.
    """
    if args is None:
        args = []
    cmd = ['python', f'tools/{script_name}'] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(PROJECT_ROOT),
        )
        return {
            'success': result.returncode == 0,
            'output': result.stdout,
            'error': result.stderr,
        }
    except subprocess.TimeoutExpired:
        return {'success': False, 'output': '', 'error': 'Timeout (300s dépassé)'}
    except Exception as e:
        return {'success': False, 'output': '', 'error': str(e)}


def get_month_options() -> list:
    """Return [current_month, previous_month] as 'YYYY-MM' strings."""
    now = datetime.date.today()
    current = now.strftime('%Y-%m')
    if now.month == 1:
        prev = f'{now.year - 1}-12'
    else:
        prev = f'{now.year}-{now.month - 1:02d}'
    return [current, prev]


def get_slides_url() -> str:
    """Read SLIDES_ID from tools/.env or fall back to the hardcoded PRESENTATION_ID."""
    env_path = PROJECT_ROOT / 'tools' / '.env'
    slides_id = None
    try:
        with open(env_path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('SLIDES_ID='):
                    slides_id = line.split('=', 1)[1].strip()
                    break
    except FileNotFoundError:
        pass

    if not slides_id:
        # Fallback: PRESENTATION_ID hardcoded in slides_updater.py
        slides_id = '1O5uFDwyMXchEi4LiaRBaF6Tie9XpKZ_1v7sefQObZp4'

    return f'https://docs.google.com/presentation/d/{slides_id}/edit'
