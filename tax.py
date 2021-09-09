import csv
import datetime
import re

DATE_COLUMN = 0
PLAN_COLUMN = 2
TYPE_COLUMN = 3
PRICE_COLUMN = 5
QUANTITY_COLUMN = 6
NET_SHARES_COLUMN = 8

DATE_PATTERN = re.compile(r"(\d+)-([A-Z-a-z]+)-(\d+)")

MONTHS = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}

class Transaction:

    def __init__(self, date, type, price, quantity, plan):
        self.date = date
        self.type = type
        self.price = price
        self.quantity = quantity
        self.plan = plan
        self.log = []

    def __cmp__(self, other):
        c = cmp(self.date, other.date)
        if c == 0:
            c = cmp(TYPE_ORDER[self.type], TYPE_ORDER[other.type])
        return c

    def __str__(self):
        return "%s: %s %s %d at %d" % (self.date, self.type, self.plan, self.quantity, self.price)

# See https://assets.publishing.service.gov.uk/government/uploads/system/uploads/attachment_data/file/596595/HS284_Example_3__2017.pdf
class Section104Holding:

    def __init__(self, name):
        self.name = name
        self.cost = Dollars(0)
        self.quantity = 0.0

    def Add(self, quantity, price, log):
        self.cost += (quantity * price)
        self.quantity += quantity
        log.append("Section 104 %s: add %d at %s, total %d average %s" % (self.name, quantity, price, self.quantity, self.cost / self.quantity,))

    def Withdraw(self, quantity, log):
        if quantity > self.quantity:
            raise Exception("Section 2014 exhausted")
        cost = self.cost * (quantity/self.quantity)
        self.quantity -= quantity
        self.cost -= cost
        average = 0
        if self.quantity > 0:
            average = self.cost / self.quantity
        log.append("Section 104 %s: withdraw %d average %s, leaving %d average %s" % (self.name, quantity, cost/quantity, self.quantity, average,))
        return cost

    def Split(self, new_name, ratio):        
        new_holding = Section104Holding(new_name)
        new_holding.quantity = self.quantity
        new_holding.cost = self.cost * ratio
        new_holding.acquisitions = [SPLIT_DATE] * int(self.quantity)
        new_holding.disposals = []
        return new_holding, ("Split %s -> %s: %d at %s (average %s)" % (self.name, new_name, new_holding.quantity, new_holding.cost, new_holding.cost/new_holding.quantity))

SPLIT_DATE = datetime.date(2014, 3, 27)
SPLIT_PRICE_A = 573.39
SPLIT_PRICE_C = 569.85

class Gain:

    def __init__(self, date, proceeds, cost):
        self.date = date
        self.proceeds = proceeds
        self.cost = cost

    def __str__(self):
        return "%s: Gain %s (%s - %s)" % (self.date, self.proceeds - self.cost, self.proceeds, self.cost)

def parse_morgan_stanley(releases, withdrawals):
    transactions = []
    errors = []
    for f in (releases, withdrawals):
        r = csv.reader(f)
        zip(range(0, 1), r) # Skip header
        for (line, row) in enumerate(r):
            try:
                match = DATE_PATTERN.match(row[DATE_COLUMN])
                if match is None:
                    continue
                d = datetime.date(int(match.group(3)), MONTHS[match.group(2)], int(match.group(1)))
                if row[TYPE_COLUMN] == "Sale":
                    transactions.append(Transaction(d, row[TYPE_COLUMN], parse_dollars(row[PRICE_COLUMN]), abs(float(row[QUANTITY_COLUMN].replace(",", ""))), row[PLAN_COLUMN]))
                elif row[TYPE_COLUMN] == "Release":
                    transactions.append(Transaction(d, row[TYPE_COLUMN], parse_dollars(row[PRICE_COLUMN]), abs(float(row[NET_SHARES_COLUMN].replace(",", ""))), row[PLAN_COLUMN]))
            except Exception as e:
                errors.append("line %d: %s: %s" % (line, e, row))
    transactions.sort(key=lambda t:t.date)
    return (transactions, errors)

def calculate_gains(transactions):
    gains = []
    holdings = {"GSU": Section104Holding("GSU")}
    split = False
    for t in transactions:
        if t.date > SPLIT_DATE and not split:
            split = True
            holdings["GSU Class A"], log = holdings["GSU"].Split("GSU Class A", SPLIT_PRICE_A / (SPLIT_PRICE_A + SPLIT_PRICE_C))
            t.log.append(log)
            holdings["GSU Class C"], log = holdings["GSU"].Split("GSU Class C", SPLIT_PRICE_C / (SPLIT_PRICE_A + SPLIT_PRICE_C))
            t.log.append(log)
            del holdings["GSU"]
        if t.type == "Release":
            holdings[t.plan].Add(t.quantity, t.price, t.log)
        elif t.type == "Sale":
            quantity = t.quantity
            total_cost = Dollars(0)
            # Attempt to match shares released on the same day, or the following 30 days
            for match in transactions:
                if match.type != "Release":
                    continue
                if match.plan != t.plan: # This ignores the stock split, which I think is right.
                    continue
                delta = (match.date - t.date).days
                if delta < 0:
                    continue
                if delta > 30:
                    break
                assigned = min(match.quantity, quantity)
                if assigned > 0:
                    t.log.append("Assign same/30 %s: %d on %s at %s" % (match.plan, assigned, match.date, match.price))
                total_cost += (assigned * match.price)
                match.quantity -= assigned
                match.log.append("Assigned %.2f to sale on %s" % (assigned, t.date))
                quantity -= assigned
                if quantity == 0:
                    break
            total_cost += holdings[t.plan].Withdraw(quantity, t.log)
            t.log.append("Proceeds: %s" % (t.price * t.quantity))
            t.log.append("Cost: %s" % total_cost)
            t.log.append("Gain: %s" % ((t.price * t.quantity) - total_cost))
            gains.append(Gain(t.date, t.price * t.quantity, total_cost))
    return gains

def group_gains(gains):
    ty = tax_year(gains[0].date)
    today = datetime.date.today()
    gains.append(Gain(datetime.date(today.year + 1, today.month, today.day), Dollars(0), Dollars(0))) # Sentinel, to force output of last tax year
    grouped = []
    total_proceeds = Dollars(0)
    total_gain = Dollars(0)
    for gain in gains:
        if tax_year(gain.date) != ty:
            grouped.append((ty, total_proceeds, total_gain))
            ty = tax_year(gain.date)
            total_proceeds = Dollars(0)
            total_gain = Dollars(0)
        total_proceeds += gain.proceeds
        total_gain += gain.proceeds - gain.cost
    return grouped

class Dollars:
    
    def __init__(self, cents):
        self.cents = cents

    def __add__(self, other):
        return Dollars(self.cents + other.cents)

    def __sub__(self, other):
        return Dollars(self.cents - other.cents)

    def __iadd__(self, other):
        self.cents += other.cents
        return self

    def __isub__(self, other):
        self.cents -= other.cents
        return self

    def __mul__(self, factor):
        return Dollars(self.cents * factor)

    def __rmul__(self, factor):
        return Dollars(self.cents * factor)

    def __truediv__(self, factor):
        return Dollars(self.cents / factor)

    def __str__(self):
        return "$%d.%02d" % (self.cents / 100, self.cents % 100)

def parse_dollars(d):
    return Dollars(int(float(d.replace("$", "").replace(",", "")) * 100))

def tax_year(d):
    if d > datetime.date(d.year, 4, 5):
        return "%d-%d" % (d.year, d.year + 1)
    else:
        return "%d-%d" % (d.year - 1, d.year)



