# Stock Dashboard App

## Overview
The Stock Dashboard App is a web application designed to help me manage my stock portfolio, perform DCF (Discounted Cash Flow) analysis, and track reports and wishlist items. The app is built using Flask and integrates with external APIs like Yahoo Finance for stock data.

## Features
- **Login and Logout**: Secure login functionality with session management.
- **Portfolio Management**: Add, edit, and delete stock holdings in your portfolio.
- **DCF Analysis**: Perform Discounted Cash Flow analysis for stocks.
- **Reports**: Create, edit, and view reports related to stocks.
- **Wishlist**: Add stocks to a wishlist with desired prices.

## Project Structure
```
Stock_Dashboard_App/
├── app.py                # Main Flask application
├── requirements.txt      # Python dependencies
├── runtime.txt           # Specifies Python runtime version
├── procfile              # Deployment configuration for platforms like Railway
├── static/
│   └── styles.css        # CSS for styling the web application
├── templates/
│   ├── index.html        # Homepage template
│   ├── login.html        # Login page template
│   ├── portfolio.html    # Portfolio page template
│   ├── dcf.html          # DCF analysis page template
│   ├── reports.html      # Reports page template
│   ├── wishlist.html     # Wishlist page template
│   └── sidebar.html      # Sidebar template
├── dcf/
│   ├── dcf_calculator.py # Logic for DCF calculations
```


## Deployment
The app is configured for deployment on platforms like Railway or Heroku. Use the `procfile` and `runtime.txt` for deployment.
