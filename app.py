from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "TRANSICIÓN ENERGÉTICA Y ENERGÍAS RENOVABLES"

if __name__ == "__main__":
    app.run(debug=True)