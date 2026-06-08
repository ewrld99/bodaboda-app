import os
import base64
import hashlib
import hmac
import json
import time
from pathlib import Path
from functools import wraps
from flask import Flask, request, jsonify
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from flask_sqlalchemy import SQLAlchemy
from prometheus_flask_exporter import PrometheusMetrics
from dotenv import load_dotenv
from werkzeug.security import check_password_hash, generate_password_hash

try:
    from .mqtt_client import RIDE_STATUS_TOPIC, publish_ride_status_update
except ImportError:
    from mqtt_client import RIDE_STATUS_TOPIC, publish_ride_status_update

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__)

metrics = PrometheusMetrics(app)

DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "bodaconnect")
DATABASE_URL = os.getenv("DATABASE_URL")

if DB_HOST == "db" and not Path("/.dockerenv").exists():
    DB_HOST = "localhost"

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")
app.config["JWT_EXP_SECONDS"] = int(os.getenv("JWT_EXP_SECONDS", "86400"))

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL or (
    f"postgresql://{DB_USER}:{DB_PASSWORD}" f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

db = SQLAlchemy(app)

RIDE_STATUS_VALUES = {"pending", "accepted", "started", "completed"}
MQTT_RIDE_STATUS_VALUES = {"accepted", "started", "completed"}
RIDE_STATUS_ALIASES = {"in_progress": "accepted"}


def _b64url_encode(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value):
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def create_access_token(user):
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "iat": now,
        "exp": now + app.config["JWT_EXP_SECONDS"],
    }
    signing_input = ".".join(
        [
            _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
            _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
        ]
    )
    signature = hmac.new(
        app.config["SECRET_KEY"].encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_b64url_encode(signature)}"


def decode_access_token(token):
    try:
        header_part, payload_part, signature_part = token.split(".")
        signing_input = f"{header_part}.{payload_part}"
        expected_signature = hmac.new(
            app.config["SECRET_KEY"].encode("utf-8"),
            signing_input.encode("ascii"),
            hashlib.sha256,
        ).digest()

        if not hmac.compare_digest(_b64url_encode(expected_signature), signature_part):
            return None

        payload = json.loads(_b64url_decode(payload_part))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None

        return payload
    except (ValueError, json.JSONDecodeError, TypeError):
        return None


def current_token_user():
    auth_header = request.headers.get("Authorization", "")
    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None

    payload = decode_access_token(token)
    if not payload:
        return None

    return db.session.get(User, int(payload["sub"]))


def token_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_token_user()
        if not user:
            return jsonify({"error": "valid login token is required"}), 401
        return view(user, *args, **kwargs)

    return wrapped


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(128), nullable=False)
    last_name = db.Column(db.String(128), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(32), nullable=False)


class RideRequest(db.Model):
    __tablename__ = "ride_requests"
    id = db.Column(db.Integer, primary_key=True)
    pickup = db.Column(db.String(255), nullable=False)
    destination = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(32), nullable=False, default="pending")
    rider_id = db.Column(db.Integer, db.ForeignKey("riders.id"), nullable=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    rider = db.relationship("Rider", lazy=True)
    customer = db.relationship("User", foreign_keys=[customer_id], lazy=True)


class Rider(db.Model):
    __tablename__ = "riders"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True
    )
    user = db.relationship(
        "User", backref=db.backref("rider_profile", uselist=False), lazy=True
    )


def serialize_user(user):
    full_name = f"{user.first_name} {user.last_name}".strip()
    return {
        "id": user.id,
        "name": full_name,
        "email": user.email,
        "role": user.role,
        "rider_id": user.rider_profile.id if user.rider_profile else None,
    }


def ensure_database():
    db.create_all()

    # create_all does not modify existing tables. This keeps older local
    # Postgres databases compatible after adding riders.user_id.
    inspector = inspect(db.engine)
    if "riders" in inspector.get_table_names():
        rider_columns = {column["name"] for column in inspector.get_columns("riders")}
        if "user_id" not in rider_columns:
            with db.engine.begin() as connection:
                connection.exec_driver_sql(
                    "ALTER TABLE riders ADD COLUMN user_id INTEGER"
                )

    if "ride_requests" in inspector.get_table_names():
        ride_columns = {
            column["name"] for column in inspector.get_columns("ride_requests")
        }
        if "status" not in ride_columns:
            with db.engine.begin() as connection:
                connection.exec_driver_sql(
                    "ALTER TABLE ride_requests ADD COLUMN status VARCHAR(32) NOT NULL DEFAULT 'pending'"
                )
        if "rider_id" not in ride_columns:
            with db.engine.begin() as connection:
                connection.exec_driver_sql(
                    "ALTER TABLE ride_requests ADD COLUMN rider_id INTEGER"
                )
        if "customer_id" not in ride_columns:
            with db.engine.begin() as connection:
                connection.exec_driver_sql(
                    "ALTER TABLE ride_requests ADD COLUMN customer_id INTEGER"
                )


def serialize_ride_request(ride_request):
    customer_username = None
    if ride_request.customer and ride_request.customer.email:
        customer_username = ride_request.customer.email.split("@", 1)[0]

    return {
        "id": ride_request.id,
        "pickup": ride_request.pickup,
        "destination": ride_request.destination,
        "status": ride_request.status,
        "rider_id": ride_request.rider_id,
        "rider_name": ride_request.rider.name if ride_request.rider else None,
        "customer_id": ride_request.customer_id,
        "customer_username": customer_username,
    }


def normalize_ride_status(status):
    status = (status or "").strip().lower()
    return RIDE_STATUS_ALIASES.get(status, status)


def ride_status_mqtt_message(ride_request):
    return {
        "ride_id": ride_request.id,
        "status": ride_request.status,
    }


@app.route("/")
def home():
    return "Welcome to BodaConnect Platform"


@app.route("/register", methods=["POST"])
@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    app.logger.info("/register payload: %s", data)
    # Accept either `first_name`/`last_name` or a combined `name` field.
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    role = (data.get("role") or "").strip().lower()

    # If first/last missing, try to split `name`.
    if (not first_name or not last_name) and name:
        parts = name.split(None, 1)
        first_name = first_name or (parts[0] if parts else "")
        last_name = last_name or (parts[1] if len(parts) > 1 else "")

    if (
        not first_name
        or not last_name
        or not email
        or not password
        or role not in {"customer", "rider"}
    ):
        return (
            jsonify(
                {
                    "error": "first_name, last_name, email, password, and a valid role are required"
                }
            ),
            400,
        )

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "account already exists"}), 409

    user = User(
        first_name=first_name,
        last_name=last_name,
        email=email,
        role=role,
        password_hash=generate_password_hash(password),
    )

    try:
        db.session.add(user)
        db.session.flush()

        full_name = f"{first_name} {last_name}".strip()
        if role == "rider":
            db.session.add(Rider(name=full_name, user_id=user.id))

        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        app.logger.exception("IntegrityError during registration")
        return jsonify({"error": "account already exists"}), 409
    except Exception as e:
        db.session.rollback()
        app.logger.exception("Unexpected error during registration: %s", e)
        return jsonify({"error": "server error", "details": str(e)}), 500

    return (
        jsonify(
            {
                "message": "Account created",
                "account": serialize_user(user),
                "token": create_access_token(user),
            }
        ),
        201,
    )


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    role = (data.get("role") or "").strip().lower()

    if not email or not password or role not in {"customer", "rider"}:
        return jsonify({"error": "email, password, and a valid role are required"}), 400

    user = User.query.filter_by(email=email, role=role).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "invalid login details"}), 401

    return jsonify(
        {
            "message": "Logged in",
            "account": serialize_user(user),
            "token": create_access_token(user),
        }
    )


@app.route("/api/me")
@token_required
def me(user):
    return jsonify(
        {
            "account": serialize_user(user),
        }
    )


@app.route("/api/riders")
def riders():
    rider_list = Rider.query.order_by(Rider.name.asc()).all()

    return jsonify(
        {
            "riders": [
                {
                    "id": rider.id,
                    "name": rider.name,
                }
                for rider in rider_list
            ]
        }
    )


@app.route("/api/site-stats")
def site_stats():
    return jsonify(
        {
            "total_trips": RideRequest.query.count(),
            "total_riders": Rider.query.count(),
        }
    )


@app.route("/request-ride", methods=["POST"])
@app.route("/api/request-ride", methods=["POST"])
def request_ride():
    data = request.get_json(silent=True) or {}
    user = current_token_user()
    pickup = (data.get("pickup") or "").strip()
    destination = (data.get("destination") or "").strip()
    rider_id = data.get("rider_id")

    if not pickup or not destination or not rider_id:
        return jsonify({"error": "pickup, destination, and rider_id are required"}), 400

    try:
        rider_id = int(rider_id)
    except (TypeError, ValueError):
        return jsonify({"error": "rider_id must be a number"}), 400

    rider = db.session.get(Rider, rider_id)
    if not rider:
        return jsonify({"error": "selected rider was not found"}), 404

    ride_request = RideRequest(
        pickup=pickup,
        destination=destination,
        rider_id=rider.id,
        customer_id=user.id if user and user.role == "customer" else None,
    )
    db.session.add(ride_request)
    db.session.commit()

    return (
        jsonify(
            {
                "message": "Ride request received",
                **serialize_ride_request(ride_request),
            }
        ),
        201,
    )


@app.route("/api/ride-requests/<int:ride_id>/status", methods=["PATCH"])
def update_ride_status(ride_id):
    data = request.get_json(silent=True) or {}
    status = normalize_ride_status(data.get("status"))

    if status not in RIDE_STATUS_VALUES:
        return (
            jsonify(
                {
                    "error": (
                        "status must be pending, accepted, started, or completed"
                    )
                }
            ),
            400,
        )

    ride_request = db.session.get(RideRequest, ride_id)
    if not ride_request:
        return jsonify({"error": "ride request not found"}), 404

    ride_request.status = status
    db.session.commit()

    if status in MQTT_RIDE_STATUS_VALUES:
        publish_ride_status_update(ride_status_mqtt_message(ride_request))

    return jsonify(serialize_ride_request(ride_request))


@app.route("/api/ride-requests/<int:ride_id>", methods=["DELETE"])
def delete_ride_request(ride_id):
    ride_request = db.session.get(RideRequest, ride_id)
    if not ride_request:
        return jsonify({"error": "ride request not found"}), 404

    if ride_request.status != "completed":
        return jsonify({"error": "only completed rides can be deleted"}), 400

    db.session.delete(ride_request)
    db.session.commit()

    return jsonify({"message": "Ride request deleted", "id": ride_id})


@app.route("/api/customer-dashboard")
@token_required
def customer_dashboard(user):
    if user.role != "customer":
        return jsonify({"error": "customer account is required"}), 403

    ride_requests = (
        RideRequest.query.filter_by(customer_id=user.id)
        .order_by(RideRequest.id.desc())
        .all()
    )

    return jsonify(
        {
            "assigned_trips": [
                serialize_ride_request(ride_request) for ride_request in ride_requests
            ]
        }
    )


@app.route("/rider-dashboard")
@app.route("/api/rider-dashboard")
def rider_dashboard():
    rider = Rider.query.join(User).order_by(Rider.id.asc()).first()
    user = current_token_user()

    ride_query = RideRequest.query
    if user and user.role == "rider" and user.rider_profile:
        rider = user.rider_profile
        ride_query = ride_query.filter_by(rider_id=rider.id)

    ride_requests = ride_query.order_by(RideRequest.id.desc()).all()

    return jsonify(
        {
            "rider": rider.name if rider else "No rider registered",
            "rider_user_id": rider.user_id if rider else None,
            "assigned_trips": [
                serialize_ride_request(ride_request) for ride_request in ride_requests
            ],
        }
    )


if __name__ == "__main__":
    with app.app_context():
        ensure_database()

    app.run(host="0.0.0.0", port=5000)
