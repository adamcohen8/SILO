"""Bounded host connectivity observations for native validation receipts."""
import urllib.request


def host_connected(report, phase):
    """Record a failed observation without preventing evidence finalization."""
    try:
        with urllib.request.urlopen('https://pypi.org/simple/', timeout=12) as response:
            return response.status == 200
    except OSError as error:
        report.setdefault('connectivity_errors', []).append({
            'phase': phase, 'exception_type': type(error).__name__})
        return False
