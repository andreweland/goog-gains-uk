# UK capital gains for Google stock

This is a simple tool that I wrote to calculate the UK captial gains for
transactions of Google stock, using data exported from the Morgan Stanley
Stock Plan Connect tool. It hasn't been reviewed by an accountant, and
no guarantee can me made to it's accuracy.

## Running

Start a websever listening on localhost:8000 with:

`python3 ui.py`

Output as text with:

`python3 tax.py "--releases=data/Releases Report.csv" "--withdrawals=data/Withdrawals Report.csv"`