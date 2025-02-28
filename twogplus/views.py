from datetime import datetime
from traceback import format_exception
import traceback

from flask import session, request, flash
from flask.helpers import url_for
from flask.templating import render_template
from werkzeug.exceptions import InternalServerError
from werkzeug.utils import redirect

from twogplus import app, db
from twogplus.certificates import verify_test_cert, verify_vaccinated_cert
from twogplus.models import User


@app.get("/")
def home():
    if "username" not in session:
        return render_template("home.html", user=None)
    user = User.query.filter(User.name == session["username"]).first()
    return render_template("home.html", user=user)


@app.post("/")
def upload_cert():

    test_file = request.files["testFile"]
    vaccine_file = request.files["vaccineFile"]
    # If the user does not select a file, the browser submits an
    # empty file without a filename.
    if vaccine_file.filename == "" and test_file.filename == "":
        flash("You must at least upload one file", "danger")
        return render_template("home.html")

    try:
        vaccine_username = test_username = None
        if vaccine_file.filename != "":
            vaccine_username = verify_vaccinated_cert(vaccine_file)
        if test_file.filename != "":
            test_username = verify_test_cert(test_file)

    except Exception as e:
        traceback.print_exc()

        if hasattr(e, "message"):
            message = e.message
        else:
            message = str(e)
        flash(message, "danger")
        return home()

    is_tested = test_username is not None
    is_vaccinated = vaccine_username is not None

    if is_tested and is_vaccinated and vaccine_username != test_username:
        flash(
            "The name in the test and the vaccine certificate don't match. "
            f"Test name: '{test_username}', "
            f"Vaccine name: '{vaccine_username}'",
            "danger",
        )
        return render_template("home.html")

    username = vaccine_username if is_vaccinated else test_username
    session["username"] = username

    user_found = User.query.filter(User.name == username).first()
    if user_found:
        user = user_found
        if is_vaccinated:
            db.session.query(User).filter(User.name == username).update(
                {"is_vaccinated": is_vaccinated}
            )
            db.session.commit()
        if is_tested:
            db.session.query(User).filter(User.name == username).update(
                {"is_tested": is_tested}
            )
            db.session.commit()

    else:
        user = User(username, is_vaccinated, is_tested)
        db.session.add(user)
        db.session.commit()

    message_vaccinated = "a valid vaccination certificate" if is_vaccinated else ""
    message_and = " and " if is_vaccinated and is_tested else ""
    message_tested = "a valid test" if is_tested else ""
    flash(
        f"Successfully uploaded {message_vaccinated}{message_and}{message_tested} 😀",
        "success",
    )
    return render_template("home.html", user=user)


@app.get("/admin")
def admin():
    users = User.query.all()
    users.sort(key=lambda u: u.name)
    return render_template(
        "admin.html",
        now=datetime.now(),
        users=users,
    )


@app.errorhandler(InternalServerError)
def handle_bad_request(e):
    return (
        render_template(
            "500.html",
            traceback="".join(
                format_exception(
                    None,
                    e.original_exception,
                    e.original_exception.__traceback__,
                )
            ),
        ),
        500,
    )


@app.post("/delete-user")
def delete_user():
    db.session.query(User).filter(User.name == session["username"]).delete()
    db.session.commit()
    session.clear()
    flash("Deleted cookies and stored data.", "info")
    return redirect(url_for("home"))


@app.get("/crash-now")
def crash_now():
    return f"{4/0}"
