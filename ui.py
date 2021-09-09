#!/usr/bin/env python3

from wsgiref.simple_server import make_server
from xml.etree import ElementTree as ET

import io
import cgi
import tax

CSS = """
html {
    font-family: sans-serif;
}
body {
    margin-left: 10%;
    margin-right: 10%;
}
th {
    text-align: left;
    padding-right: 4em;
}
td {
    padding-right: 4em;
}
td.dollars {
    text-align: right;
}
td.log {
    color: #aaaaaa;
}
"""

FORM = """
<html>
<head>
<style type="text/css">%s</style>
</head>
<body>
<h1>GOOG UK Capital Gains</h1>
<p>
Head to the <a href="https://stockplan.morganstanley.com/solium/servlet/ui/activity/reports/">Stock Plan Connect Activity Report</a> page,
and use that to export all historical data in CSV format. Unzip the resulting file, and upload <code>Releases Report.csv</code> and
<code>Withdrawals Report.csv</code> here.
</p>
<form method="post" enctype="multipart/form-data">
<table>
<tr>
<td>Stock Plan Connect <code>Releases Report.csv</code></td>
<td><input type="file" accept="text/csv" name="releases"/></td>
</tr>
<tr>
<td>Stock Plan Connect <code>Withdrawals Report.csv</code></td>
<td><input type="file" accept="text/csv" name="withdrawals"/></td>
</tr>
<tr>
<td colspan="2"><input type="submit" value="Tax me!"/></td>
</tr>
</table>
</form>
</body>
</html>
""" % (CSS,)

def add_style(html):
    head = ET.SubElement(html, "head")
    style = ET.SubElement(head, "style")
    style.attrib["type"] = "text/css"
    style.text = CSS

def render_gains(fs, start_response):
    try:
        transactions, errors = tax.parse_morgan_stanley(io.StringIO(fs["releases"].value.decode("utf-8")), io.StringIO(fs["withdrawals"].value.decode("utf-8")))
    except Exception as e:
        return render_errors(["Couldn't parse files"], start_response)
    if errors:
        return render_errors(errors, start_response)
    gains = tax.calculate_gains(transactions)
    grouped = tax.group_gains(gains)
    html = ET.Element("html")
    add_style(html)
    body = ET.SubElement(html, "body")
    ET.SubElement(body, "h2").text = "Summary"
    table = ET.SubElement(body, "table")
    tr = ET.SubElement(table, "tr")
    ET.SubElement(tr, "th").text = "Tax year"
    ET.SubElement(tr, "th").text = "Proceeds"
    ET.SubElement(tr, "th").text = "Gain"
    for (ty, proceeds, gain) in grouped:
        tr = ET.SubElement(table, "tr")
        ET.SubElement(tr, "td").text = ty
        td = ET.SubElement(tr, "td")
        td.attrib["class"] = "dollars"
        td.text = str(proceeds)
        td = ET.SubElement(tr, "td")
        td.attrib["class"] = "dollars"
        td.text = str(gain)
    ET.SubElement(body, "h2").text = "Capital gains"
    table = ET.SubElement(body, "table")
    tr = ET.SubElement(table, "tr")
    ET.SubElement(tr, "th").text = "Date"
    ET.SubElement(tr, "th").text = "Proceeds"
    ET.SubElement(tr, "th").text = "Cost"
    for g in gains:
        tr = ET.SubElement(table, "tr")
        ET.SubElement(tr, "td").text = str(g.date)
        td = ET.SubElement(tr, "td")
        td.attrib["class"] = "dollars"
        td.text = str(g.proceeds)
        td = ET.SubElement(tr, "td")
        td.attrib["class"] = "dollars"
        td.text = str(g.cost)
    ET.SubElement(body, "h2").text = "Transactions"
    table = ET.SubElement(body, "table")
    tr = ET.SubElement(table, "tr")
    ET.SubElement(tr, "th").text = "Date"
    ET.SubElement(tr, "th").text = "Plan"
    ET.SubElement(tr, "th").text = "Transaction"
    ET.SubElement(tr, "th").text = "Price"
    ET.SubElement(tr, "th").text = "Quantity"
    for t in transactions:
        tr = ET.SubElement(table, "tr")
        ET.SubElement(tr, "td").text = str(t.date)
        ET.SubElement(tr, "td").text = t.plan
        ET.SubElement(tr, "td").text = t.type
        ET.SubElement(tr, "td").text = str(t.price)
        ET.SubElement(tr, "td").text = str(t.quantity)
        for message in t.log:
            tr = ET.SubElement(table, "tr")
            ET.SubElement(tr, "td")
            td = ET.SubElement(tr, "td")
            td.attrib["class"] = "log"
            td.attrib["colspan"] = "4"
            td.text = str(message)
    start_response("200 OK", [("Content-Type", "text/html")])
    return [ET.tostring(html, encoding="utf-8")]

def render_errors(errors, start_response):
    html = ET.Element("html")
    body = ET.SubElement(html, "body")
    ET.SubElement(body, "h1").text = "Failed"
    ul = ET.SubElement(body, "ul")
    for error in errors:
        ET.SubElement(ul, "li").text = error
    start_response("200 OK", [("Content-Type", "text/html")])
    return [ET.tostring(html, encoding="utf-8")]

def application(environ, start_response):
    if environ["wsgi.input"] is not None:        
        fs = cgi.FieldStorage(fp=environ["wsgi.input"], environ=environ)
        if "releases" in fs and "withdrawals" in fs:
            return render_gains(fs, start_response)
    start_response("200 OK", [("Content-Type", "text/html")])
    return [FORM.encode("utf-8")]

if __name__ == "__main__":
    make_server("localhost", 8000, application).serve_forever()
