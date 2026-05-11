import os
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv


load_dotenv()

app = Flask(__name__)

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"postgresql://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

db = SQLAlchemy(app)


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(128), nullable=False)
    last_name = db.Column(db.String(128), nullable=False)


class RideRequest(db.Model):
    __tablename__ = "ride_requests"
    id = db.Column(db.Integer, primary_key=True)
    pickup = db.Column(db.String(255), nullable=False)
    destination = db.Column(db.String(255), nullable=False)


class Rider(db.Model):
    __tablename__ = "riders"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, unique=True)


@app.route("/")
def home():
    return "Welcome to BodaConnect Platform"

@app.route("/request-ride", methods=["POST"])
@app.route("/api/request-ride", methods=["POST"])
def request_ride():
    data = request.get_json(silent=True) or {}
    pickup = data.get("pickup")
    destination = data.get("destination")

    if not pickup or not destination:
        return jsonify({
            "error": "pickup and destination are required"
        }), 400

    ride_request = RideRequest(pickup=pickup, destination=destination)
    db.session.add(ride_request)
    db.session.commit()

    return jsonify({
        "message": "Ride request received",
        "id": ride_request.id,
        "pickup": ride_request.pickup,
        "destination": ride_request.destination
    }), 201


@app.route("/rider-dashboard")
@app.route("/api/rider-dashboard")
def rider_dashboard():
    rider = Rider.query.filter_by(name="John").first()
    ride_requests = RideRequest.query.order_by(RideRequest.id.desc()).all()

    return jsonify({
        "rider": rider.name,
        "assigned_trips": [
            {
                "id": ride_request.id,
                "pickup": ride_request.pickup,
                "destination": ride_request.destination
            }
            for ride_request in ride_requests
        ]
    })

if __name__ == "__main__":
    # Ensure database tables exist before starting the app
    with app.app_context():
        db.create_all()
        if not Rider.query.filter_by(name="John").first():
            db.session.add(Rider(name="John"))
            db.session.commit()

    app.run(host="0.0.0.0", port=5000)
