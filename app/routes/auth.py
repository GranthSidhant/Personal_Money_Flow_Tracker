from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError
from app.extensions import db
from app.models.user import User
from app.utils.security import is_safe_url

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


# --- WTForms ---

class LoginForm(FlaskForm):
    email = StringField(
        "Email Address",
        validators=[DataRequired(message="Email is required."), Email(message="Enter a valid email address.")],
        render_kw={"placeholder": "name@example.com", "autocomplete": "email"}
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(message="Password is required.")],
        render_kw={"placeholder": "••••••••", "autocomplete": "current-password"}
    )
    remember_me = BooleanField("Remember Me")
    submit = SubmitField("Log In")


class RegisterForm(FlaskForm):
    name = StringField(
        "Full Name",
        validators=[
            DataRequired(message="Name is required."),
            Length(min=2, max=100, message="Name must be between 2 and 100 characters.")
        ],
        render_kw={"placeholder": "John Doe", "autocomplete": "name"}
    )
    email = StringField(
        "Email Address",
        validators=[
            DataRequired(message="Email is required."),
            Email(message="Enter a valid email address.")
        ],
        render_kw={"placeholder": "name@example.com", "autocomplete": "email"}
    )
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(message="Password is required."),
            Length(min=8, message="Password must be at least 8 characters long.")
        ],
        render_kw={"placeholder": "At least 8 characters", "autocomplete": "new-password"}
    )
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[
            DataRequired(message="Please confirm your password."),
            EqualTo("password", message="Passwords must match.")
        ],
        render_kw={"placeholder": "Repeat password", "autocomplete": "new-password"}
    )
    submit = SubmitField("Create Account")

    def validate_email(self, field):
        normalized_email = field.data.strip().lower()
        if User.query.filter_by(email=normalized_email).first():
            raise ValidationError("An account with this email address already exists.")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField(
        "Current Password",
        validators=[DataRequired(message="Current password is required.")],
        render_kw={"placeholder": "••••••••"}
    )
    new_password = PasswordField(
        "New Password",
        validators=[
            DataRequired(message="New password is required."),
            Length(min=8, message="New password must be at least 8 characters long.")
        ],
        render_kw={"placeholder": "At least 8 characters"}
    )
    confirm_new_password = PasswordField(
        "Confirm New Password",
        validators=[
            DataRequired(message="Please confirm your new password."),
            EqualTo("new_password", message="Passwords must match.")
        ],
        render_kw={"placeholder": "Repeat new password"}
    )
    submit = SubmitField("Update Password")


class ProfileForm(FlaskForm):
    name = StringField(
        "Full Name",
        validators=[
            DataRequired(message="Name is required."),
            Length(min=2, max=100, message="Name must be between 2 and 100 characters.")
        ]
    )
    submit = SubmitField("Save Changes")


# --- Routes ---

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    
    form = RegisterForm()
    if form.validate_on_submit():
        user = User(
            name=form.name.data.strip(),
            email=form.email.data.strip().lower()
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        
        login_user(user)
        flash("Welcome to Personal Money Flow Tracker! Your account is ready.", "success")
        return redirect(url_for("dashboard.index"))
        
    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
        
    form = LoginForm()
    if form.validate_on_submit():
        normalized_email = form.email.data.strip().lower()
        user = User.query.filter_by(email=normalized_email).first()
        
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            flash("Welcome back!", "success")
            
            next_page = request.args.get("next")
            if next_page and is_safe_url(next_page):
                return redirect(next_page)
            return redirect(url_for("dashboard.index"))
        else:
            flash("Invalid email or password. Please check your credentials.", "danger")
            
    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been successfully logged out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        current_user.name = form.name.data.strip()
        db.session.commit()
        flash("Your profile details have been updated.", "success")
        return redirect(url_for("auth.profile"))
        
    return render_template("auth/profile.html", form=form)


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash("Your current password was entered incorrectly.", "danger")
        else:
            current_user.set_password(form.new_password.data)
            db.session.commit()
            flash("Your password has been updated successfully.", "success")
            return redirect(url_for("auth.profile"))
            
    return render_template("auth/change_password.html", form=form)
