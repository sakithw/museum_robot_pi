#!/usr/bin/env python3
from flask import Flask, render_template, request, jsonify
import requests

app = Flask(__name__)
API = "http://localhost:5000"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/<path:path>', methods=['GET','POST'])
def proxy(path):
    try:
        if request.method == 'POST':
            r = requests.post(f"{API}/{path}",
                            json=request.get_json(silent=True),
                            timeout=2.0)
        else:
            r = requests.get(f"{API}/{path}", timeout=2.0)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("Display server on http://localhost:8080")
    app.run(host='0.0.0.0', port=8080, debug=False)
