from flask import Flask, render_template, request, jsonify
import sys
from pathlib import Path

# Add parent directory to path so we can import vpnmon
sys.path.insert(0, str(Path(__file__).parent.parent))
from vpnmon.core import VPNMonitor

app = Flask(__name__)
monitor = VPNMonitor()

@app.route('/')
def index():
    """Landing page with form to check usage."""
    return render_template('index.html')

@app.route('/usage', methods=['GET', 'POST'])
def usage():
    """Show usage for a specific peer."""
    if request.method == 'POST':
        public_key = request.form.get('public_key')
        month = request.form.get('month')
    else:
        public_key = request.args.get('public_key')
        month = request.args.get('month')

    if not public_key:
        return render_template('index.html', error='Public key is required')
    
    # Collect fresh data before showing results
    monitor.collect_data()

    data = monitor.get_usage(public_key, month)
    return render_template('usage.html', data=data, public_key=public_key)

@app.route('/api/usage')
def api_usage():
    """API endpoint for usage data."""
    public_key = request.args.get('public_key')
    month = request.args.get('month')

    # Collect fresh data before returning results
    monitor.collect_data()
    
    data = monitor.get_usage(public_key, month)
    return jsonify(data)

if __name__ == '__main__':
    # Initialize database on startup
    monitor.setup()
    app.run(debug=True, host='0.0.0.0', port=5000)