from flask import Flask, request, render_template, make_response, url_for
from markupsafe import Markup
import pdfkit
import os
import difflib
import html
import traceback

# Reviewer import
try:
    from reviewers.code_analysis import FullReviewer
except Exception as e:
    raise ImportError("Could not import reviewers.code_analysis.FullReviewer: " + str(e))

# PDF Export Config
_default_wk_path = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
if os.path.exists(_default_wk_path):
    try:
        config = pdfkit.configuration(wkhtmltopdf=_default_wk_path)
    except Exception:
        config = None
else:
    config = None  # rely on PATH

app = Flask(__name__)
reviewer = FullReviewer()

# Global state (demo only)
latest_code = ""
latest_feedback = {}

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

def get_side_by_side_diff(original_code: str, formatted_code: str):
    original_escaped = html.escape(original_code or "")
    formatted_escaped = html.escape(formatted_code or "")

    try:
        differ = difflib.HtmlDiff(wrapcolumn=80)
        diff_table = differ.make_table(
            (original_code or "").splitlines(),
            (formatted_code or "").splitlines(),
            fromdesc="Original Code",
            todesc="Formatted Code",
            context=True,
            numlines=2,
        )
    except Exception:
        diff_table = ""

    return {
        "original_html": Markup(f"<pre>{original_escaped}</pre>"),
        "formatted_html": Markup(f"<pre>{formatted_escaped}</pre>"),
        "diff_html": Markup(diff_table) if diff_table else "",
        "original_raw": original_code or "",
        "formatted_raw": formatted_code or "",
        "formatted": formatted_code or "",
    }

@app.route("/review", methods=["GET", "POST"])
def review():
    global latest_code, latest_feedback

    if request.method == "POST":
        try:
            # Get code from form
            code = request.form.get("code", "") or ""
            code = code.strip()

            # Handle file upload safely
            uploaded_file = request.files.get("file")
            if uploaded_file and uploaded_file.filename.lower().endswith(".py"):
                code = uploaded_file.read().decode("utf-8", errors="ignore")

            if not code:
                code = "# No code provided"

            # Review code safely
            feedback = reviewer.safe_review_code(code)

            # Get formatted code
            original = feedback.get("formatted_code", {}).get("original", code) if feedback else code
            formatted = feedback.get("formatted_code", {}).get("formatted", code) if feedback else code
            formatted_code_dict = get_side_by_side_diff(original, formatted)

            # Save only code and feedback in memory
            latest_code = code
            latest_feedback = feedback or {}

            return render_template(
                "review.html",
                code=code,
                ai_feedback=feedback.get("ai_feedback", "⚠️ No AI feedback available"),
                rule_feedback=feedback.get("rule_feedback", []),
                complexity_feedback=feedback.get("complexity_feedback", []),
                flake8_feedback=feedback.get("flake8_feedback", ""),
                formatted_code=formatted_code_dict,
                original_lines=original.splitlines(),
                formatted_lines=formatted.splitlines(),
                export_mode=False,
            )

        except Exception as e:
            print("💥 ERROR in /review:", str(e))
            traceback.print_exc()
            return "⚠️ Server Error while reviewing code. Check server logs.", 500

    # GET request → show index
    return render_template("index.html")

@app.route("/download_report", methods=["GET"])
def download_report():
    global latest_code, latest_feedback

    original = latest_feedback.get("formatted_code", {}).get("original", latest_code)
    formatted = latest_feedback.get("formatted_code", {}).get("formatted", latest_code)
    formatted_code_dict = get_side_by_side_diff(original, formatted)

    original_lines = (formatted_code_dict.get("original_raw") or "").splitlines()
    formatted_lines = (formatted_code_dict.get("formatted_raw") or "").splitlines()

    try:
        rendered = render_template(
            "review.html",
            code=latest_code or "# No code reviewed yet",
            ai_feedback=latest_feedback.get("ai_feedback", "⚠️ No AI feedback available"),
            rule_feedback=latest_feedback.get("rule_feedback", []),
            complexity_feedback=latest_feedback.get("complexity_feedback", []),
            flake8_feedback=latest_feedback.get("flake8_feedback", ""),
            formatted_code=formatted_code_dict,
            original_lines=original_lines,
            formatted_lines=formatted_lines,
            export_mode=True,
        )
    except Exception as e:
        print("💥 ERROR rendering report:", str(e))
        traceback.print_exc()
        return "⚠️ Server Error while rendering report.", 500

    if not config:
        return "⚠️ wkhtmltopdf not configured or not found.", 500

    try:
        pdf = pdfkit.from_string(rendered, False, configuration=config)
    except Exception as e:
        print("💥 pdfkit error:", str(e))
        traceback.print_exc()
        return "⚠️ PDF generation failed. Check wkhtmltopdf installation.", 500

    response = make_response(pdf)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "attachment; filename=code_review.pdf"
    return response

if __name__ == "__main__":
    app.run(debug=True)
