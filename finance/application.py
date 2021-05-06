import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # Select user's current cash to display

    cash = (db.execute("SELECT cash FROM users WHERE id=?", session["user_id"]))[0]["cash"]

    # Select user's current stocks to display with rendered HTML page
    currentStocks = db.execute("SELECT * FROM stocks WHERE userID=?", session["user_id"])

    # Lookup the stocks' values and store in a dictionary to be used to render HTML page
    stockPrices = {}
    stockTotal = {}
    for key in currentStocks:
        stockPrices[key["stockName"]] = (lookup(key["stockName"]))["price"]
        stockTotal[key["stockName"]] = (lookup(key["stockName"]))["price"] * key["quantity"]

    # Get the total stock values

    allStocksTotal = 0
    for key in stockTotal:
        allStocksTotal += stockTotal[key]

    # Get the total stock values plus cash value
    totalValue = cash + allStocksTotal


    return render_template("index.html", cash=cash, currentStocks=currentStocks, stockPrices=stockPrices, stockTotal=stockTotal, allStocksTotal=allStocksTotal, totalValue=totalValue)



@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Obtain the stock symbol and amount of shares from form
        symbol = request.form.get("symbol").upper()
        shares = request.form.get("shares")

        # Obtain the stock price using API (lookup)
        stock = lookup(symbol)
        price = stock["price"]

        if stock is None:
            return apology("invalid symbol", 400)

        # SELECT user's cash

        cash = (db.execute("SELECT cash FROM users WHERE id=?", session["user_id"]))[0]["cash"]

        # Check total cost of shares

        cost = (float(shares)*price)

        # Return error if cost is greater than cash

        if cost > cash:
            return apology("Insufficient funds", 400)

        # Check to see how many stocks user already has [0]["quantity"]

        currentStockQuantity = db.execute("SELECT quantity FROM stocks WHERE userID=? AND stockName=?", session["user_id"], symbol)

        # If user has no stock, then we will insert into the database
        if currentStockQuantity == []:

            db.execute("INSERT INTO stocks (userID, stockName, quantity) VALUES (?, ?, ?)", session["user_id"], symbol, shares)

        # Otherwise, add amount of purchased shares to shares already held

        else:

            newStockQuantity = currentStockQuantity[0]["quantity"] + int(shares)

            db.execute("UPDATE stocks SET quantity=? WHERE userID=? AND stockName=?", newStockQuantity, session["user_id"], symbol)

        # Subtract cash from account

        newCash = cash - cost

        db.execute("UPDATE users SET cash=? WHERE id=?", newCash, session["user_id"])

        # Insert into history

        db.execute("INSERT INTO history (userID, stockName, price, shares, type) VALUES (?, ?, ?, ?, 'PURCHASE')", session["user_id"], symbol, price, shares)

        return render_template("bought.html", shares=shares, symbol=symbol)

    # User reached route via GET
    if request.method == "GET":

        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    history = db.execute("SELECT * FROM history WHERE userID=?", session["user_id"])


    return render_template("history.html", history=history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # User reached route via POST
    if request.method == "POST":

        symbol = request.form.get("symbol").upper()
        stock = lookup(symbol)
        if stock is None:
            return apology("invalid symbol", 400)
        return render_template("quoted.html", stockName={
            "name": stock["name"],
            "symbol": stock["symbol"],
            "price": usd(stock["price"]),
        })


    # User reached route via GET

    if request.method == "GET":

        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # User reached route via POST (as by submitting a form via POST)

    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Ensure confirmation matches password
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("password does not match confirmation", 403)

        # Generate an ID based on the current max ID

        userID = (db.execute("SELECT MAX(id) FROM users"))[0]["MAX(id)"]

        if userID == None:
            userID = 1
        else:
            userID += 1;

        # Obtain username from form

        userName = request.form.get("username")

        # Generate password hash from password obtained from form

        passwordHash = generate_password_hash(request.form.get("password"))

        # Check to make sure there is no other duplicate username in the database already

        if not db.execute("SELECT username FROM users WHERE username = ?", userName) == []:
            return apology("username already in use", 403)

        # Insert new user data into database

        db.execute("INSERT INTO users (id, username, hash) VALUES (?, ?, ?)", userID, userName, passwordHash)

        # Redirect user back to login page

        return render_template("login.html")

    # User reached route via GET

    if request.method == "GET":

        return render_template("register.html")



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    if request.method == "POST":

        # Obtain the stock symbol and amount of shares from form
        symbol = request.form.get("symbol").upper()
        shares = request.form.get("shares")

        # Obtain the stock price using API (lookup)
        stock = lookup(symbol)
        price = stock["price"]

        # Obtain amount of stocks held
        currentStockQuantity = db.execute("SELECT quantity FROM stocks WHERE stockName=? AND userID=?", symbol, session["user_id"])[0]["quantity"]

        # Return an error if trying to sell more stocks than amount currently held
        if currentStockQuantity < int(shares):
            return apology("Insufficient shares", 400)

        # SELECT user's cash

        cash = (db.execute("SELECT cash FROM users WHERE id=?", session["user_id"]))[0]["cash"]

        # Check total cost of shares

        cost = (float(shares)*price)

        # Subtract the amount of shares sold from the user's account

        newStockQuantity = currentStockQuantity - int(shares)

        # If the amount of stocks left is 0, then delete the entry in the database

        if newStockQuantity == 0:

            db.execute("DELETE FROM stocks WHERE stockName=? AND userID=?", symbol, session["user_id"])

        else:

            db.execute("UPDATE stocks SET quantity=? WHERE userID=? AND stockName=?", newStockQuantity, session["user_id"], symbol)

        # Update cash

        newCash = cash + cost

        db.execute("UPDATE users SET cash=? WHERE id=?", newCash, session["user_id"])

        # Insert into history

        db.execute("INSERT INTO history (userID, stockName, price, shares, type) VALUES (?, ?, ?, ?, 'SALE')", session["user_id"], symbol, price, shares)

        return redirect("/")


    if request.method == "GET":

        stockSymbols = db.execute("SELECT stockName FROM stocks WHERE userID=?", session["user_id"])
        print(stockSymbols)

        return render_template("sell.html", stockSymbols=stockSymbols)

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

