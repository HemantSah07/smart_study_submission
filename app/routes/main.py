from flask import Blueprint, render_template

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def home():
    return render_template('public/home.html')

@main_bp.route('/app_tour')
def app_tour():
    return render_template('public/app_tour.html')

@main_bp.route('/about')
def about():
    return render_template('public/about.html')

@main_bp.route('/study_tips')
def study_tips():
    return render_template('public/study_tips.html')
