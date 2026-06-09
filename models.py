from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Analysis(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    text = db.Column(
        db.Text,
        nullable=False
    )

    sentiment = db.Column(
        db.String(50)
    )

    polarity = db.Column(
        db.Float
    )

    subjectivity = db.Column(
        db.Float
    )

    bert_sentiment = db.Column(
        db.String(20)
    )

    bert_confidence = db.Column(
        db.Float
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    def __repr__(self):
        return f"<Analysis {self.id}>"


# NEW MODEL

class BatchReport(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    total_reviews = db.Column(
        db.Integer
    )

    positive = db.Column(
        db.Integer
    )

    negative = db.Column(
        db.Integer
    )

    neutral = db.Column(
        db.Integer
    )

    processing_time = db.Column(
        db.Float
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    def __repr__(self):
        return f"<BatchReport {self.id}>"