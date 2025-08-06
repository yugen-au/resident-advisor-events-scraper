from flask import Flask, jsonify
app = Flask(__name__)

@app.route('/', methods=['GET'])
def health_check():
    return jsonify({"status": "working", "test": "minimal"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)