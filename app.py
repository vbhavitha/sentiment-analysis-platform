from flask import Flask, render_template, request, redirect, Response, jsonify, send_file
from textblob import TextBlob
from models import db, Analysis
import csv
from io import StringIO
from datetime import datetime, timedelta
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import os
import re
import time
from collections import Counter
from transformers import pipeline
from models import db, Analysis, BatchReport
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle
)
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__)

batch_results = []
latest_batch_stats = {}

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///sentiment.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

classifier = pipeline(
    "sentiment-analysis"
)

def extract_keywords(text):

    words = re.findall(
        r'\b[a-zA-Z]+\b',
        text.lower()
    )

    stop_words = {
        "i", "me", "my", "we", "our",
        "you", "your", "he", "she",
        "it", "they", "the", "a", "an",
        "and", "or", "but", "is", "are",
        "was", "were", "this", "that",
        "to", "of", "in", "on", "for",
        "with", "at", "by"
    }

    filtered_words = [
        word
        for word in words
        if word not in stop_words
    ]

    keyword_counts = Counter(
        filtered_words
    )

    return keyword_counts.most_common(10)

@app.route("/dashboard")
def dashboard():

    total = Analysis.query.count()

    positive = Analysis.query.filter(
        Analysis.sentiment.contains("Positive")
    ).count()

    negative = Analysis.query.filter(
        Analysis.sentiment.contains("Negative")
    ).count()

    neutral = Analysis.query.filter(
        Analysis.sentiment.contains("Neutral")
    ).count()

    return render_template(
        "dashboard.html",
        total=total,
        positive=positive,
        negative=negative,
        neutral=neutral
    )

@app.route("/", methods=["GET", "POST"])
def home():

    sentiment = ""
    polarity = 0
    subjectivity = 0
    user_text = ""
    keywords = []
    sentence_results = []

    bert_sentiment = ""
    bert_confidence = 0

    if request.method == "POST":

        user_text = request.form["text"]

        blob = TextBlob(user_text)

        bert_result = classifier(user_text)
        bert_sentiment = (bert_result[0]["label"])
        bert_confidence = round(bert_result[0]["score"] * 100,2)

        for sentence in blob.sentences:

            sentence_blob = TextBlob(str(sentence))

            score = sentence_blob.sentiment.polarity

            if score > 0:
                label = "Positive"

            elif score < 0:
                label = "Negative"

            else:
                label = "Neutral"

            sentence_results.append({
                "sentence": str(sentence),
                "sentiment": label,
                "polarity": round(score, 2)
            })

        keywords = extract_keywords(
            user_text
        )

        polarity = round(blob.sentiment.polarity, 2)
        subjectivity = round(blob.sentiment.subjectivity, 2)

        if polarity >= 0.75:
            sentiment = "Very Positive 🟢"

        elif polarity >= 0.25:
            sentiment = "Moderately Positive 😊"

        elif polarity > 0:
            sentiment = "Slightly Positive 🟡"

        elif polarity == 0:
            sentiment = "Neutral ⚪"

        elif polarity > -0.25:
            sentiment = "Slightly Negative 🟠"

        elif polarity > -0.75:
            sentiment = "Moderately Negative 😞"

        else:
            sentiment = "Very Negative 🔴"

        analysis = Analysis(
            text=user_text,
            sentiment=sentiment,
            polarity=polarity,
            subjectivity=subjectivity,
            bert_sentiment=bert_sentiment,
            bert_confidence=bert_confidence
        )

        db.session.add(analysis)
        db.session.commit()

        print(Analysis.query.all())

    return render_template(
        "index.html",
        sentiment=sentiment,
        polarity=polarity,
        subjectivity=subjectivity,
        user_text=user_text,
        keywords=keywords,
        sentence_results=sentence_results,
        bert_sentiment=bert_sentiment,
        bert_confidence=bert_confidence
    )

@app.route("/history")
def history():

    analyses = Analysis.query.all()

    return render_template(
        "history.html",
        analyses=analyses
    )

@app.route("/delete/<int:id>")
def delete(id):

    analysis = Analysis.query.get_or_404(id)

    db.session.delete(analysis)

    db.session.commit()

    return redirect("/history")

@app.route("/clear-history")
def clear_history():

    print("CLEAR HISTORY CLICKED")

    Analysis.query.delete()

    db.session.commit()

    return redirect("/history")

@app.route("/export-csv")
def export_csv():

    print("EXPORT CLICKED")
    print("Records:", Analysis.query.count())

    analyses = Analysis.query.all()

    output = StringIO()

    writer = csv.writer(output)

    writer.writerow([
        "Text",
        "Sentiment",
        "Polarity",
        "Subjectivity"
    ])

    for item in analyses:

        writer.writerow([
            item.text,
            item.sentiment,
            item.polarity,
            item.subjectivity
        ])

    output.seek(0)

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition":
            "attachment; filename=sentiment_history.csv"
        }
    )

@app.route("/trends")
def trends():

    today = datetime.utcnow().date()

    trend_data = []

    for i in range(6, -1, -1):

        day = today - timedelta(days=i)

        count = Analysis.query.filter(
            db.func.date(
                Analysis.created_at
            ) == day
        ).count()

        trend_data.append({
            "date": day.strftime("%d-%b"),
            "count": count
        })

    return render_template(
        "trends.html",
        trend_data=trend_data
    )

@app.route("/wordcloud")
def wordcloud():

    positive_reviews = Analysis.query.filter(
        Analysis.sentiment.contains("Positive")
    ).all()

    negative_reviews = Analysis.query.filter(
        Analysis.sentiment.contains("Negative")
    ).all()

    all_reviews = Analysis.query.all()

    positive_text = " ".join(
        item.text for item in positive_reviews
    )

    negative_text = " ".join(
        item.text for item in negative_reviews
    )

    all_text = " ".join(
        item.text for item in all_reviews
    )

    # Fallbacks

    if not positive_text.strip():
        positive_text = "No Positive Reviews"

    if not negative_text.strip():
        negative_text = "No Negative Reviews"

    if not all_text.strip():
        all_text = "No Reviews"

    # Generate Images

    WordCloud(
        width=1000,
        height=500,
        background_color="white"
    ).generate(
        positive_text
    ).to_file(
        "static/positive_wordcloud.png"
    )

    WordCloud(
        width=1000,
        height=500,
        background_color="white"
    ).generate(
        negative_text
    ).to_file(
        "static/negative_wordcloud.png"
    )

    WordCloud(
        width=1000,
        height=500,
        background_color="white"
    ).generate(
        all_text
    ).to_file(
        "static/all_wordcloud.png"
    )

    return render_template(
        "wordcloud.html"
    )

@app.route("/keywords")
def keywords():

    all_reviews = Analysis.query.all()

    positive_reviews = Analysis.query.filter(
        Analysis.sentiment.contains("Positive")
    ).all()

    negative_reviews = Analysis.query.filter(
        Analysis.sentiment.contains("Negative")
    ).all()

    all_text = " ".join(
        item.text for item in all_reviews
    )

    positive_text = " ".join(
        item.text for item in positive_reviews
    )

    negative_text = " ".join(
        item.text for item in negative_reviews
    )

    all_keywords = extract_keywords(
        all_text
    )

    positive_keywords = extract_keywords(
        positive_text
    )

    negative_keywords = extract_keywords(
        negative_text
    )

    return render_template(
        "keywords.html",
        all_keywords=all_keywords,
        positive_keywords=positive_keywords,
        negative_keywords=negative_keywords
    )

@app.route("/api/analyze", methods=["POST"])
def api_analyze():

    data = request.get_json()

    if not data or "text" not in data:

        return jsonify({
            "error": "Please provide text"
        }), 400

    text = data["text"]

    blob = TextBlob(text)

    polarity = round(
        blob.sentiment.polarity,
        2
    )

    subjectivity = round(
        blob.sentiment.subjectivity,
        2
    )

    if polarity >= 0.75:
        sentiment = "Very Positive"

    elif polarity >= 0.25:
        sentiment = "Moderately Positive"

    elif polarity > 0:
        sentiment = "Slightly Positive"

    elif polarity == 0:
        sentiment = "Neutral"

    elif polarity > -0.25:
        sentiment = "Slightly Negative"

    elif polarity > -0.75:
        sentiment = "Moderately Negative"

    else:
        sentiment = "Very Negative"

    return jsonify({

        "text": text,

        "sentiment": sentiment,

        "polarity": polarity,

        "subjectivity": subjectivity

    })

@app.route("/api-test")
def api_test():

    return render_template(
        "api_test.html"
    )

@app.route("/api-docs")
def api_docs():

    return render_template(
        "api_docs.html"
    )

@app.route("/live-analysis", methods=["POST"])
def live_analysis():

    text = request.json.get(
        "text",
        ""
    )

    blob = TextBlob(text)

    polarity = round(
        blob.sentiment.polarity,
        2
    )

    subjectivity = round(
        blob.sentiment.subjectivity,
        2
    )

    return jsonify({

        "polarity": polarity,

        "subjectivity": subjectivity

    })

@app.route("/compare", methods=["GET", "POST"])
def compare():

    result_a = None
    result_b = None

    text_a = ""
    text_b = ""

    if request.method == "POST":

        text_a = request.form["text_a"]

        text_b = request.form["text_b"]

        blob_a = TextBlob(text_a)
        blob_b = TextBlob(text_b)

        polarity_a = round(
            blob_a.sentiment.polarity,
            2
        )

        polarity_b = round(
            blob_b.sentiment.polarity,
            2
        )

        # Sentiment for Text A

        sentiment_a = (
            "Positive"
            if polarity_a > 0
            else "Negative"
            if polarity_a < 0
            else "Neutral"
        )

        # Sentiment for Text B

        sentiment_b = (
            "Positive"
            if polarity_b > 0
            else "Negative"
            if polarity_b < 0
            else "Neutral"
        )

        result_a = {
            "text": text_a,
            "polarity": polarity_a,
            "sentiment": sentiment_a
        }

        result_b = {
            "text": text_b,
            "polarity": polarity_b,
            "sentiment": sentiment_b
        }

    return render_template(
        "compare.html",
        result_a=result_a,
        result_b=result_b,
        text_a=text_a if request.method == "POST" else "",
        text_b=text_b if request.method == "POST" else ""
    )

@app.route("/batch-analysis", methods=["GET", "POST"])
def batch_analysis():

    results = []

    top_keywords = []

    positive_keywords = []

    negative_keywords = []

    processing_time = 0

    positive = 0
    negative = 0
    neutral = 0
    bert_positive = 0
    bert_negative = 0

    if request.method == "POST":

        start_time = time.time()

        file = request.files["csv_file"]

        results = []

    if request.method == "POST":

        file = request.files["csv_file"]

        global batch_results

        batch_results = []

        if file:

            import pandas as pd

            df = pd.read_csv(file)

            for review in df["Review"]:

                blob = TextBlob(str(review))

                polarity = round(
                    blob.sentiment.polarity,
                    2
                )

                if polarity > 0:

                    sentiment = "Positive"
                    positive += 1

                elif polarity < 0:

                    sentiment = "Negative"
                    negative += 1

                else:

                    sentiment = "Neutral"
                    neutral += 1

                bert_result = classifier(review)

                bert_sentiment = (bert_result[0]["label"])

                bert_confidence = round(bert_result[0]["score"] * 100, 2)

                if bert_sentiment == "POSITIVE":

                    bert_positive += 1

                else:

                    bert_negative += 1

                results.append({

                    "review": review,

                    "sentiment": sentiment,

                    "polarity": round(polarity,2),

                    "bert_sentiment":bert_sentiment,

                    "bert_confidence":bert_confidence

                })

                batch_results.append({
                    "review": review,
                    "sentiment": sentiment,
                    "polarity": polarity,
                    "bert_sentiment": bert_sentiment,
                    "bert_confidence": bert_confidence
                })

            # Calculate processing time once

            processing_time = round(
                time.time() - start_time,
                2
            )

            # Combine all reviews

            combined_text = " ".join(
                item["review"]
                for item in results
            )

            positive_text = " ".join(

                item["review"]

                for item in results

                if item["sentiment"] == "Positive"

            )

            negative_text = " ".join(

                item["review"]

                for item in results

                if item["sentiment"] == "Negative"

            )

            positive_keywords = extract_keywords(
                positive_text
            )

            negative_keywords = extract_keywords(
                negative_text
            )

            # Prevent empty word cloud

            if not combined_text.strip():

                combined_text = "No Reviews"

            # Generate word cloud once

            WordCloud(
                width=1200,
                height=600,
                background_color="white"
            ).generate(
                combined_text
            ).to_file(
                "static/batch_wordcloud.png"
            )

            # Extract keywords once

            top_keywords = extract_keywords(
                combined_text
            )

            positive_keywords = extract_keywords(
                positive_text
            )

            negative_keywords = extract_keywords(
                negative_text
            )
               

    total = positive + negative + neutral

    positive_rate = round(
        (positive / total) * 100,
        2
    ) if total else 0

    negative_rate = round(
        (negative / total) * 100,
        2
    ) if total else 0

    neutral_rate = round(
        (neutral / total) * 100,
        2
    ) if total else 0

    bert_positive_rate = (
        round((bert_positive / total) * 100, 2)
        if total else 0
    )

    bert_negative_rate = (
        round((bert_negative / total) * 100, 2)
        if total else 0
    )

    positive_rate = (
        round((positive / total) * 100, 2)
        if total else 0
    )

    negative_rate = (
        round((negative / total) * 100, 2)
        if total else 0
    )

    neutral_rate = (
        round((neutral / total) * 100, 2)
        if total else 0
    )

    global latest_batch_stats

    latest_batch_stats = {

        "total": total,

        "positive": positive,

        "negative": negative,

        "neutral": neutral,

        "processing_time": processing_time,

        "positive_rate": positive_rate,

        "negative_rate": negative_rate,

        "neutral_rate": neutral_rate,

        "positive_keywords": positive_keywords,

        "negative_keywords": negative_keywords

    }

    if total > 0:

        batch_report = BatchReport(
            total_reviews=total,
            positive=positive,
            negative=negative,
            neutral=neutral,
            processing_time=processing_time
        )

        db.session.add(batch_report)
        db.session.commit()

    

    return render_template(
        "batch_analysis.html",
        results=results,
        positive=positive,
        negative=negative,
        neutral=neutral,
        processing_time=processing_time,
        total=total,
        positive_rate=positive_rate,
        negative_rate=negative_rate,
        neutral_rate=neutral_rate,
        top_keywords=top_keywords,
        positive_keywords=positive_keywords,
        negative_keywords=negative_keywords,
        bert_positive=bert_positive,
        bert_negative=bert_negative,
        bert_positive_rate=bert_positive_rate,
        bert_negative_rate=bert_negative_rate
    )

@app.route("/export-batch-report")
def export_batch_report():

    global batch_results

    output = StringIO()

    writer = csv.writer(output)

    writer.writerow([
        "Review",
        "Sentiment",
        "Polarity",
        "BERT Sentiment",
        "BERT Confidence"
    ])

    for item in batch_results:

        writer.writerow([
            item["review"],
            item["sentiment"],
            item["polarity"],
            item["bert_sentiment"],
            item["bert_confidence"]
        ])

    output.seek(0)

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition":
            "attachment; filename=batch_report.csv"
        }
    )

@app.route("/batch-history")
def batch_history():

    reports = BatchReport.query.order_by(
        BatchReport.created_at.asc()
    ).all()

    chart_labels = [
        f"Batch {report.id}"
        for report in reports
    ]

    chart_reviews = [
        report.total_reviews
        for report in reports
    ]

    chart_time = [
        report.processing_time
        for report in reports
    ]

    return render_template(
        "batch_history.html",
        reports=reports,
        chart_labels=chart_labels,
        chart_reviews=chart_reviews,
        chart_time=chart_time
    )

@app.route("/export-batch-pdf")
def export_batch_pdf():

    global batch_results
    global latest_batch_stats

    pdf_path = "static/batch_report.pdf"

    doc = SimpleDocTemplate(
        pdf_path
    )

    styles = getSampleStyleSheet()

    elements = []

    # Title

    elements.append(

        Paragraph(
            "Customer Feedback Analytics Report",
            styles["Title"]
        )

    )

    elements.append(
        Spacer(1, 20)
    )

    # Executive Summary Heading

    elements.append(

        Paragraph(
            "Executive Summary",
            styles["Heading2"]
        )

    )

    elements.append(
        Spacer(1, 10)
    )

    elements.append(

        Paragraph(
            f"Generated On: {datetime.now().strftime('%d-%b-%Y %I:%M %p')}",
            styles["BodyText"]
        )

    )

    elements.append(
        Spacer(1, 10)
    )

    # Summary

    elements.append(

        Paragraph(
            f"Total Reviews: {latest_batch_stats.get('total',0)}",
            styles["BodyText"]
        )

    )

    elements.append(

        Paragraph(
            f"Positive Reviews: {latest_batch_stats.get('positive',0)}",
            styles["BodyText"]
        )

)

    elements.append(

        Paragraph(
            f"Negative Reviews: {latest_batch_stats.get('negative',0)}",
            styles["BodyText"]
        )

    )

    elements.append(

        Paragraph(
            f"Neutral Reviews: {latest_batch_stats.get('neutral',0)}",
            styles["BodyText"]
        )

    )

    elements.append(
        Spacer(1, 10)
    )

    elements.append(

        Paragraph(
            "Sentiment Distribution",
            styles["Heading3"]
        )

    )

    elements.append(

        Paragraph(
            f"Positive Rate: {latest_batch_stats.get('positive_rate',0)}%",
            styles["BodyText"]
        )

    )


    elements.append(

        Paragraph(
            f"Negative Rate: {latest_batch_stats.get('negative_rate',0)}%",
            styles["BodyText"]
        )

    )


    elements.append(

        Paragraph(
            f"Neutral Rate: {latest_batch_stats.get('neutral_rate',0)}%",
            styles["BodyText"]
        )

    )

    elements.append(

        Paragraph(
            f"Positive Rate: {latest_batch_stats.get('positive_rate',0)}%",
            styles["BodyText"]
        )

    )

    elements.append(

        Paragraph(
            f"Negative Rate: {latest_batch_stats.get('negative_rate',0)}%",
            styles["BodyText"]
        )

    )

    elements.append(

        Paragraph(
            f"Neutral Rate: {latest_batch_stats.get('neutral_rate',0)}%",
            styles["BodyText"]
        )

    )

    elements.append(

        Paragraph(
            f"Processing Time: {latest_batch_stats.get('processing_time',0)} sec",
            styles["BodyText"]
        )

    )

    elements.append(
        Spacer(1, 10)
    )

    # AI Models Used

    elements.append(

        Paragraph(
            "AI Models Used",
            styles["Heading3"]
        )

    )

    elements.append(

        Paragraph(
            "• TextBlob (Traditional NLP)",
            styles["BodyText"]
        )

    )

    elements.append(

        Paragraph(
            "• DistilBERT (Transformer-Based AI)",
            styles["BodyText"]
        )

    )

    elements.append(
        Spacer(1, 10)
    )

    # Top Positive Keywords

    elements.append(

        Paragraph(
            "Top Positive Keywords",
            styles["Heading3"]
        )

    )

    positive_words = ", ".join(

        word

        for word, count in
            latest_batch_stats.get(
            "positive_keywords",
            []
        )[:5]

    )

    elements.append(

        Paragraph(
            positive_words,
            styles["BodyText"]
        )

    )

    elements.append(
        Spacer(1, 10)
    )

    # Top Negative Keywords

    elements.append(

        Paragraph(
            "Top Negative Keywords",
            styles["Heading3"]
        )

    )

    negative_words = ", ".join(

        word

        for word, count in
        latest_batch_stats.get(
            "negative_keywords",
            []
        )[:5]

    )

    elements.append(

        Paragraph(
            negative_words,
            styles["BodyText"]
        )
    )

    elements.append(
        Spacer(1, 20)
    )

    # Results Table

    table_data = [

        [
            "Review",
            "TextBlob",
            "Polarity",
            "BERT",
            "Confidence"
        ]

    ]

    for item in batch_results:

        table_data.append([

            str(item["review"]),

            str(item["sentiment"]),

            str(item["polarity"]),

            str(item["bert_sentiment"]),

            f'{item["bert_confidence"]}%'

        ])

    table = Table(table_data)

    table.setStyle(

        TableStyle([

            ("BACKGROUND",(0,0),(-1,0),colors.grey),

            ("TEXTCOLOR",(0,0),(-1,0),colors.whitesmoke),

            ("GRID",(0,0),(-1,-1),1,colors.black),

            ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold")

        ])

    )

    elements.append(

        Paragraph(
            "Generated by Sentiment Analysis Platform",
            styles["Italic"]
        )

    )

    elements.append(
        Spacer(1, 10)
    )

    elements.append(table)

    doc.build(elements)

    return send_file(
        pdf_path,
        as_attachment=True
    )

if __name__ == "__main__":

    with app.app_context():
        db.create_all()

    app.run(debug=True)