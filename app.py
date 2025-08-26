from flask import Flask, render_template, request, url_for, redirect, flash, session, request
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash
from datetime import datetime, timedelta
import yfinance as yf
import requests
import time 
import os

# Initialize Flask app and database
app = Flask(__name__)

# Set static folder
app.static_folder = 'static'

# Set session timeout
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

#Secret key for session management - found in Railway environment variables
app.secret_key = os.getenv('SECRET_KEY')  


#User credentials - Found in Railway environment variables
USER_CREDENTIALS = {
    'username': os.getenv('APP_USERNAME'),
    'password': os.getenv('APP_PASSWORD')
}

#Check if user credentials are set.
if USER_CREDENTIALS['username'] is None or USER_CREDENTIALS['password'] is None:
    raise ValueError("Environment variables APP_USERNAME and APP_PASSWORD must be set!")

#Configuration for Database
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///reports.db')
app.config['SQLALCHEMY_BINDS'] = {
    'portfolio': os.getenv('PORTFOLIO_DATABASE_URL', 'sqlite:///portfolio.db')
}
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

#Report model (reports.db)
class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True) 
    ticker = db.Column(db.String(10), nullable=False)
    title = db.Column(
        db.String(100), nullable=False)
    snippet = db.Column(db.Text, nullable=False) #Might want to get rid of this later
    date = db.Column(db.String(20), nullable=False)

#DCF model (reports.db)
class DCFAnalysis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(20), nullable=False)
    fcf = db.Column(db.Float, nullable=False)
    growth_1_5 = db.Column(db.Float, nullable=False)
    growth_6_10 = db.Column(db.Float, nullable=False)
    discount = db.Column(db.Float, nullable=False)
    terminal_growth = db.Column(db.Float, nullable=False)
    shares = db.Column(db.Float, nullable=False)
    intrinsic_value = db.Column(db.Float, nullable=False)
    date = db.Column(db.String(20), nullable=False)

#Portfolio model (portfolio.db)
class PortfolioHolding(db.Model):
    __bind_key__ = 'portfolio'  # Specify the bind key for this model
    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(10), nullable=False)
    shares = db.Column(db.Float, nullable=False)
    avg_price = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), nullable=False, default='EUR') # Default currency is EUR
    date_added = db.Column(db.String(20), nullable=False)

#Wishlist model (portfolio.db)
class WishlistItem(db.Model):
    __bind_key__ = 'portfolio'
    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(10), nullable=False)
    desired_price = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), nullable=False, default='EUR')  
    date_added = db.Column(db.String(20), nullable=False) 

#Helper Function Exchange Rates
def get_usd_eur_rate():
    app_id = os.getenv('OPENEXCHANGE_APP_ID', 'default_app_id')
    url = f"https://openexchangerates.org/api/latest.json?app_id={app_id}&symbols=EUR"
    try:
        response = requests.get(url)
        data = response.json()
        return data['rates']['EUR']
    except Exception as e:
        print("Exchange rate fetch error:", e)
        return 0.92  # fallback to a reasonable default


#Main page
@app.route('/')
def index():
    holdings = PortfolioHolding.query.all()
    tickers = [h.ticker for h in holdings]
    stock_data = get_stock_data(tickers) if tickers else {}
    portfolio = []
    for h in holdings:
        price = stock_data.get(h.ticker, {}).get('current_price')
        portfolio.append({
            'ticker': h.ticker,
            'shares': h.shares,
            'currency': h.currency,
            'price': price
        })
    return render_template('index.html', portfolio=portfolio)

#Login page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        # Validate credentials
        if username == USER_CREDENTIALS['username'] and password == USER_CREDENTIALS['password']:
            session['user'] = username
            session.permanent = True  # Make the session permanent so it uses the timeout defined
            return redirect(url_for('index'))  # Redirect to the main page after login
        else:
            flash('Invalid username or password.', 'danger')
    return render_template('login.html')  # Render the login page

#Logout Function
@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))


@app.before_request
def require_login():
    # Allow access to static files, login/logout routes, and handle NoneType endpoints
    if request.endpoint is None or request.endpoint in ['login', 'logout'] or request.endpoint.startswith('static'):
        return
    if 'user' not in session:
        return redirect(url_for('login'))

# Portfolio CRUD
@app.route('/portfolio', methods=['GET', 'POST'])
def portfolio_page():
    if request.method == 'POST':
        ticker = request.form['ticker'].upper()
        currency = request.form['currency']
        shares = float(request.form['shares'])
        avg_price = float(request.form['avg_price'])
        date_added = datetime.now().strftime('%Y-%m-%d')
        new_holding = PortfolioHolding(ticker=ticker, currency=currency, shares=shares, avg_price=avg_price, date_added=date_added)
        db.session.add(new_holding)
        db.session.commit()
        flash('Holding added to portfolio!', 'success')
        return redirect(url_for('portfolio_page'))
    holdings = PortfolioHolding.query.order_by(PortfolioHolding.id.desc()).all()
    tickers = [h.ticker for h in holdings]
    stock_data = get_stock_data(tickers) if tickers else {}

    #Fetch exchange rate for USD to EUR
    usd_eur = get_usd_eur_rate()

    # Total value and total gain/loss
    total_value = 0
    total_gain = 0
    for h in holdings:
        price = stock_data.get(h.ticker, {}).get('current_price')
        if price:
            #Convert to EUR if currency is USD
            if h.currency == 'USD':
                price_eur = price * usd_eur
                avg_price_eur = h.avg_price * usd_eur
            else:
                price_eur = price
                avg_price_eur = h.avg_price
            total_value += price_eur * h.shares
            total_gain += (price_eur - avg_price_eur) * h.shares

    return render_template(
        'portfolio.html',
        holdings=holdings,
        stock_data=stock_data,
        total_value=total_value,
        total_gain=total_gain
    )


stock_cache = {}
CACHE_TTL = 900  # 15 minutes

# Fetch stock data using yfinance
def get_stock_data(tickers):
    global stock_cache
    now = time.time()
    cache_key = tuple(sorted(tickers))
    # Check cache
    if cache_key in stock_cache and now - stock_cache[cache_key]['timestamp'] < CACHE_TTL:
        return stock_cache[cache_key]['data']
    # Fetch fresh data
    data = {}
    tickers_str = " ".join(tickers).upper()
    stocks = yf.Tickers(tickers_str)
    for ticker in tickers:
        try:
            info = stocks.tickers[ticker].info
            data[ticker] = {
                "current_price": info.get("regularMarketPrice"),
                "pe_ratio": info.get("trailingPE"),
                "roic": info.get("returnOnEquity"),  # Yahoo uses ROE, not ROIC
                "profitMargins": info.get("profitMargins"),
            }
        except Exception as e:
            print(f"Error fetching data for {ticker}: {e}")
            data[ticker] = {
                "current_price": None,
                "pe_ratio": None,
                "roic": None,
                "profitMargins": None,
        }
    stock_cache[cache_key] = {
        'timestamp': now,
        'data': data
    }
    return data

# Edit and delete portfolio holdings
@app.route('/portfolio/edit/<int:holding_id>', methods=['GET', 'POST'])
def edit_holding(holding_id):
    holding = PortfolioHolding.query.get_or_404(holding_id)
    if request.method == 'POST':
        holding.ticker = request.form['ticker']
        holding.currency = request.form['currency']
        holding.shares = float(request.form['shares'])
        holding.avg_price = float(request.form['avg_price'])
        db.session.commit()
        flash('Holding updated!', 'success')
        return redirect(url_for('portfolio_page'))
    return render_template('edit_holding.html', holding=holding)

@app.route('/portfolio/delete/<int:holding_id>')
def delete_holding(holding_id):
    holding = PortfolioHolding.query.get_or_404(holding_id)
    db.session.delete(holding)
    db.session.commit()
    flash('Holding deleted!', 'success')
    return redirect(url_for('portfolio_page'))

@app.route('/dcf', methods=['GET', 'POST'])
def dcf():
    result = None
    form_data = {}
    saved_dcfs = DCFAnalysis.query.order_by(DCFAnalysis.id.desc()).all()
    current_price = None
    if request.method == 'POST':
        ticker = request.form.get('ticker', '')
        fcf = float(request.form.get('fcf', 0))
        growth_1_5 = float(request.form.get('growth_1_5', 0))
        growth_6_10 = float(request.form.get('growth_6_10', 0))
        discount = float(request.form.get('discount', 0))
        terminal_growth = float(request.form.get('terminal_growth', 0))
        shares = float(request.form.get('shares', 0))
        form_data = {
            'ticker': ticker,
            'fcf': fcf,
            'growth_1_5': growth_1_5,
            'growth_6_10': growth_6_10,
            'discount': discount,
            'terminal_growth': terminal_growth,
            'shares': shares
        }
        if ticker:
            stock_data = get_stock_data([ticker])
            current_price = stock_data.get(ticker, {}).get('current_price')
            if current_price is None:
                flash(f"Data for ticker {ticker} is not available.", "danger")
                return redirect(url_for('dcf'))

        #Validate inputs
        if float(fcf) <= 0:
            flash('Free Cash Flow must be greater than 0.', 'danger')
            return redirect(url_for('dcf'))
        if discount <= terminal_growth:
            flash('Discount rate must be greater than terminal growth rate!', 'danger')
            return redirect(url_for('dcf'))

        if shares <= 0:
            flash('Shares Outstanding must be greater than 0.', 'danger')
            return redirect(url_for('dcf'))

        if request.form['action'] == 'calculate':
            from dcf.dcf_calculator import dcf_valuation
            
            result = dcf_valuation(
                fcf,
                growth_1_5,
                growth_6_10,
                discount,
                terminal_growth,
                shares
            )
            form_data['result'] = result

        elif request.form['action'] == 'save':
            result = float(request.form.get('result', 0))
            if result == 0:
                flash('Please calculate the intrinsic value before saving.', 'danger')
                return redirect(url_for('dcf'))
            from dcf.dcf_calculator import dcf_valuation
            new_dcf = DCFAnalysis(
                ticker=ticker,
                fcf=fcf,
                growth_1_5=growth_1_5,
                growth_6_10=growth_6_10,
                discount=discount,
                terminal_growth=terminal_growth,
                shares=shares,
                intrinsic_value=result,
                date=datetime.now().strftime('%Y-%m-%d')
            )
            db.session.add(new_dcf)
            db.session.commit()
            flash('DCF analysis saved!', 'success')
            return redirect(url_for('dcf'))
    return render_template('dcf.html', result=result, form_data=form_data, saved_dcfs=saved_dcfs, current_price=current_price)


#Deleting DCF entries
@app.route('/dcf/delete/<int:dcf_id>', methods=['POST', 'GET'])
def delete_dcf(dcf_id):
    dcf_entry = DCFAnalysis.query.get_or_404(dcf_id)
    db.session.delete(dcf_entry)
    db.session.commit()
    flash('DCF analysis deleted!', 'success')
    return redirect(url_for('dcf'))

@app.route('/reports', methods=['GET', 'POST'])
def reports_page():
    if request.method == 'POST':
        ticker = request.form['ticker']
        title = request.form['title']
        snippet = request.form['snippet']
        date = datetime.now().strftime('%Y-%m-%d')
        new_report = Report(ticker=ticker, title=title, snippet=snippet, date=date)
        db.session.add(new_report)
        db.session.commit()
        flash('Report created successfully!', 'success')
        return redirect(url_for('reports_page'))
    search = request.args.get('search', '').strip()
    from_dcf = request.args.get('from_dcf')
    prefill = {}
    if from_dcf:
        prefill = {
            'ticker': request.args.get('ticker', ''),
            'intrinsic_value': request.args.get('intrinsic_value', ''),
            'fcf': request.args.get('fcf', ''),
            'growth_1_5': request.args.get('growth_1_5', ''),
            'growth_6_10': request.args.get('growth_6_10', ''),
            'discount': request.args.get('discount', ''),
            'terminal_growth': request.args.get('terminal_growth', ''),
            'shares': request.args.get('shares', ''),
        }
    if search:
        reports = Report.query.filter(Report.ticker.ilike(f"%{search}%")).order_by(Report.id.desc()).all()
    else:
        reports = Report.query.order_by(Report.id.desc()).all()
    return render_template('reports.html', reports=reports, prefill=prefill)


@app.route('/reports/view/<int:report_id>')
def view_report(report_id):
    report = Report.query.get_or_404(report_id)
    return render_template('view_report.html', report=report)

@app.route('/reports/edit/<int:report_id>', methods=['GET', 'POST'])
def edit_report(report_id):
    report = Report.query.get_or_404(report_id)
    if request.method == 'POST':
        report.ticker = request.form['ticker']
        report.title = request.form['title']
        report.snippet = request.form['snippet']
        db.session.commit()
        flash('Report updated successfully!', 'success')
        return redirect(url_for('reports_page'))
    return render_template('edit_report.html', report=report)

@app.route('/reports/delete/<int:report_id>')
def delete_report(report_id):
    report = Report.query.get_or_404(report_id)
    db.session.delete(report)
    db.session.commit()
    flash('Report deleted successfully!', 'success')
    return redirect(url_for('reports_page'))


@app.route('/wishlist', methods=['GET', 'POST'])
def wishlist_page():
    if request.method == 'POST':
        ticker = request.form['ticker'].upper()
        desired_price = float(request.form['desired_price'])
        currency = request.form['currency']
        date_added = datetime.now().strftime('%Y-%m-%d')
        new_item = WishlistItem(ticker=ticker, desired_price=desired_price, currency=currency, date_added=date_added)
        db.session.add(new_item)
        db.session.commit()
        flash('Ticker added to wishlist!', 'success')
        return redirect(url_for('wishlist_page'))
    wishlist = WishlistItem.query.order_by(WishlistItem.id.desc()).all()
    # Get all tickers with reports for quick lookup
    reports = Report.query.with_entities(Report.ticker).distinct().all()
    report_tickers = set([r.ticker.upper() for r in reports])
    return render_template('wishlist.html', wishlist=wishlist, report_tickers=report_tickers)

@app.route('/wishlist/delete/<int:item_id>', methods=['POST', 'GET'])
def delete_wishlist(item_id):
    item = WishlistItem.query.get_or_404(item_id)
    if request.method == 'GET':
        db.session.delete(item)
        db.session.commit()
        flash('Wishlist item deleted!', 'success')
    return redirect(url_for('wishlist_page'))
    


if __name__ == '__main__':
    app.run(debug=False) #Debug false for production, true for development