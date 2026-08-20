from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"status": "success", "message": "WET server is running!"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9999)
