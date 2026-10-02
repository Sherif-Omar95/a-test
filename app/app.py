#!/usr/bin/env python3
"""Demo web tier for the Scalable Web Application project.

Every page view is written to the shared Multi-AZ RDS database, so the page
shows which instance and Availability Zone answered each recent request.

Endpoints
  /           HTML page: this instance, shared request log, database status
  /api/info   the same data as JSON
  /health     ALB health check; never touches the database
"""
import html
import json
import os
import socket
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import boto3
import pymysql

DB_HOST = os.environ["DB_HOST"]
DB_NAME = os.environ.get("DB_NAME", "appdb")
DB_SECRET_ARN = os.environ["DB_SECRET_ARN"]
REGION = os.environ["AWS_REGION"]
CA_BUNDLE = "/opt/webapp/rds-ca.pem"
PORT = int(os.environ.get("PORT", "80"))


def imds(path):
    """Read instance metadata with IMDSv2 (session token required)."""
    try:
        req = urllib.request.Request(
            "http://169.254.169.254/latest/api/token", method="PUT",
            headers={"X-aws-ec2-metadata-token-ttl-seconds": "60"})
        token = urllib.request.urlopen(req, timeout=2).read().decode()
        req = urllib.request.Request(
            "http://169.254.169.254/latest/meta-data/" + path,
            headers={"X-aws-ec2-metadata-token": token})
        return urllib.request.urlopen(req, timeout=2).read().decode()
    except Exception:
        return "unknown"


INSTANCE = {
    "instance_id": imds("instance-id"),
    "az": imds("placement/availability-zone"),
    "private_ip": imds("local-ipv4"),
    "instance_type": imds("instance-type"),
}

_secret = {"value": None, "fetched": 0.0}


def db_credentials():
    """RDS-managed secret, cached for 5 minutes so rotation is picked up."""
    if _secret["value"] is None or time.time() - _secret["fetched"] > 300:
        sm = boto3.client("secretsmanager", region_name=REGION)
        raw = sm.get_secret_value(SecretId=DB_SECRET_ARN)["SecretString"]
        _secret["value"] = json.loads(raw)
        _secret["fetched"] = time.time()
    return _secret["value"]


def connect():
    creds = db_credentials()
    return pymysql.connect(
        host=DB_HOST, user=creds["username"], password=creds["password"],
        database=DB_NAME, connect_timeout=3, read_timeout=5,
        ssl={"ca": CA_BUNDLE}, autocommit=True)


def record_visit(path):
    """Log this request and return the shared view of the database."""
    result = {"ok": False}
    try:
        conn = connect()
        with conn.cursor() as cur:
            cur.execute(
                "CREATE TABLE IF NOT EXISTS visits ("
                " id BIGINT AUTO_INCREMENT PRIMARY KEY,"
                " instance_id VARCHAR(32), az VARCHAR(32), path VARCHAR(255),"
                " created_at TIMESTAMP(3) DEFAULT CURRENT_TIMESTAMP(3))")
            cur.execute(
                "INSERT INTO visits (instance_id, az, path) VALUES (%s,%s,%s)",
                (INSTANCE["instance_id"], INSTANCE["az"], path[:255]))
            cur.execute("SELECT COUNT(*) FROM visits")
            result["total"] = cur.fetchone()[0]
            cur.execute(
                "SELECT az, COUNT(*) FROM visits GROUP BY az ORDER BY az")
            result["by_az"] = {az: n for az, n in cur.fetchall()}
            cur.execute(
                "SELECT instance_id, az, created_at FROM visits"
                " ORDER BY id DESC LIMIT 10")
            result["recent"] = [
                {"instance_id": i, "az": a, "at": t.strftime("%H:%M:%S")}
                for i, a, t in cur.fetchall()]
            cur.execute("SELECT @@hostname, VERSION()")
            result["db_host"], result["db_version"] = cur.fetchone()
            cur.execute("SHOW SESSION STATUS LIKE 'Ssl_cipher'")
            row = cur.fetchone()
            result["tls_cipher"] = row[1] if row and row[1] else "none"
        conn.close()
        result["ok"] = True
    except Exception as exc:  # the page still renders without the database
        result["error"] = type(exc).__name__ + ": " + str(exc)[:200]
    return result


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Served from {az}</title>
<link rel="stylesheet" href="/static/style.css">
<link rel="icon" href="/static/favicon.svg">
</head><body>
<main>
<header>
<p class="lede">This request was answered by</p>
<h1>{instance_id}</h1>
<p class="where">in <strong>{az}</strong>, private address {private_ip}, {instance_type}</p>
<p class="hint">Refresh the page. The load balancer spreads requests across healthy
instances in both Availability Zones, so the answer changes.</p>
</header>
{db_section}
<footer>Path: CloudFront, WAF, Application Load Balancer, Auto Scaling group,
RDS MySQL Multi-AZ. Styles on this page come from S3 through CloudFront.</footer>
</main></body></html>"""


def render(data):
    esc = {k: html.escape(str(v)) for k, v in INSTANCE.items()}
    if not data["ok"]:
        db = ("<section class='db error'><h2>Database unreachable</h2>"
              "<p>The web tier is healthy, but this instance could not reach "
              "RDS: <code>{}</code>. During a Multi-AZ failover this clears "
              "within about two minutes.</p></section>"
              ).format(html.escape(data.get("error", "")))
        return PAGE.format(db_section=db, **esc)
    bars = "".join(
        "<li><span class='az'>{}</span><span class='n'>{}</span></li>".format(
            html.escape(az), n) for az, n in data["by_az"].items())
    rows = "".join(
        "<tr class='{}'><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            "self" if r["instance_id"] == INSTANCE["instance_id"] else "",
            r["at"], html.escape(r["instance_id"]), html.escape(r["az"]))
        for r in data["recent"])
    db = ("<section class='db'>"
          "<h2>Shared request log</h2>"
          "<p>Every instance writes to the same database, so this log shows "
          "requests answered by all of them. Rows from this instance are "
          "highlighted.</p>"
          "<table><thead><tr><th>Time (UTC)</th><th>Instance</th><th>Zone</th>"
          "</tr></thead><tbody>{rows}</tbody></table>"
          "<h3>{total} requests in total, by zone</h3><ul class='split'>{bars}</ul>"
          "<p class='meta'>Database server {host}, MySQL {ver}, "
          "TLS cipher {tls}</p></section>").format(
              rows=rows, total=data["total"], bars=bars,
              host=html.escape(str(data["db_host"])),
              ver=html.escape(str(data["db_version"])),
              tls=html.escape(str(data["tls_cipher"])))
    return PAGE.format(db_section=db, **esc)


class Handler(BaseHTTPRequestHandler):
    server_version = "webapp"

    def send(self, code, body, ctype):
        payload = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Served-By", INSTANCE["instance_id"])
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/health":
            self.send(200, "ok\n", "text/plain")
        elif path == "/api/info":
            data = record_visit(path)
            data["instance"] = INSTANCE
            data["hostname"] = socket.gethostname()
            self.send(200, json.dumps(data, default=str, indent=2),
                      "application/json")
        elif path == "/":
            self.send(200, render(record_visit(path)),
                      "text/html; charset=utf-8")
        else:
            self.send(404, "not found\n", "text/plain")

    def log_message(self, fmt, *args):
        pass  # the ALB access path is already observable in CloudWatch


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
