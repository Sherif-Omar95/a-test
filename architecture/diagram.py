"""Generates architecture/architecture.svg and architecture.png.

Fixed layout (not auto-placed) so the tiers and Availability Zones line up.
Icons are the official AWS architecture icons bundled with the `diagrams`
package. Requirements: pip install diagrams playwright && playwright install chromium

    python3 architecture/diagram.py
"""
import base64
import os
import pathlib

import diagrams

HERE = pathlib.Path(__file__).resolve().parent
ICONS = pathlib.Path(diagrams.__file__).resolve().parent.parent / "resources" / "aws"
W, H = 1660, 1010
out = []


def icon(path, cx, cy, label, size=54):
    data = base64.b64encode((ICONS / path).read_bytes()).decode()
    x, y = cx - size / 2, cy - size / 2
    out.append(f'<image href="data:image/png;base64,{data}" x="{x}" y="{y}" '
               f'width="{size}" height="{size}"/>')
    for i, line in enumerate(label.split("\n")):
        weight = "600" if i == 0 else "400"
        out.append(f'<text x="{cx}" y="{cy + size / 2 + 16 + i * 14}" '
                   f'text-anchor="middle" class="t" font-weight="{weight}">{line}</text>')


def box(x, y, w, h, label, fill, stroke, dash="", radius=8, bold=False):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" '
               f'fill="{fill}" stroke="{stroke}" stroke-width="1.5"{d}/>')
    out.append(f'<text x="{x + 10}" y="{y + 20}" class="{"h" if bold else "s"}">{label}</text>')


def line(points, style="solid", label="", lx=None, ly=None, color="#232F3E", arrow=True):
    dash = {"solid": "", "dashed": ' stroke-dasharray="7 5"',
            "dotted": ' stroke-dasharray="2 4"'}[style]
    marker = ' marker-end="url(#a)"' if arrow else ""
    pts = " ".join(f"{x},{y}" for x, y in points)
    out.append(f'<polyline points="{pts}" fill="none" stroke="{color}" '
               f'stroke-width="1.6"{dash}{marker}/>')
    if label:
        out.append(f'<text x="{lx}" y="{ly}" class="e" text-anchor="middle">{label}</text>')


# ------------------------------------------------------------------ canvas
out.append(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')
out.append('<text x="40" y="44" class="title">Scalable Web Application with ALB and Auto Scaling</text>')
out.append('<text x="40" y="68" class="sub">AWS Solutions Architect Associate project. '
           'Two Availability Zones, three subnet tiers, everything deployed by one CloudFormation stack.</text>')

# ------------------------------------------------------------------- edge
icon("general/users.png", 80, 470, "Users")
icon("network/route-53.png", 80, 660, "Route 53\noptional custom\ndomain (alias)")
icon("network/cloudfront.png", 235, 470, "CloudFront\nHTTPS, HTTP/2+3\nPriceClass_100")

# ------------------------------------------------------------------ region
box(330, 95, 1300, 890, "AWS Region", "#FAFBFC", "#7D8998", dash="6 4", bold=True)
icon("storage/simple-storage-service-s3-bucket.png", 405, 200,
     "S3 static assets\nprivate, read via OAC\n/static/*")
icon("security/waf.png", 405, 470, "AWS WAF\norigin header check\nrate limit per IP\nmanaged rule sets")

# --------------------------------------------------------------------- VPC
box(495, 120, 845, 840, "VPC 10.0.0.0/16", "#F2F8EE", "#3F8624", bold=True)
icon("network/internet-gateway.png", 495, 545, "", size=46)
out.append('<text x="495" y="590" class="t" text-anchor="middle" font-weight="600">Internet</text>')
out.append('<text x="495" y="604" class="t" text-anchor="middle" font-weight="600">Gateway</text>')

AZ = [("Availability Zone A", 160), ("Availability Zone B", 560)]
for name, y in AZ:
    box(530, y, 790, 380, "", "none", "#147EBA", dash="8 5")
    out.append(f'<text x="1310" y="{y + 20}" class="s" text-anchor="end">{name}</text>')
    box(550, y + 32, 200, 330, "Public subnet", "#E6F2DD", "#7AA116")
    box(790, y + 32, 230, 330, "Private app subnet", "#E3EEF8", "#147EBA")
    box(1060, y + 32, 245, 330, "Isolated data subnet", "#FBEFDC", "#C7511F")

subnet_cidrs = [("10.0.0.0/24", "10.0.10.0/24", "10.0.20.0/24", 160),
                ("10.0.1.0/24", "10.0.11.0/24", "10.0.21.0/24", 560)]
for pub, app, data, y in subnet_cidrs:
    for x, cidr in ((560, pub), (800, app), (1070, data)):
        out.append(f'<text x="{x}" y="{y + 68}" class="s">{cidr}</text>')

# ALB straddles both public subnets: it has a node in each AZ.
out.append('<rect x="575" y="398" width="150" height="190" rx="10" fill="#ffffff" '
           'stroke="#8C4FFF" stroke-width="1.5"/>')
icon("network/elb-application-load-balancer.png", 650, 470,
     "Application\nLoad Balancer\nnode in each AZ\nhealth check /health\n/admin* returns 403", size=58)

icon("network/nat-gateway.png", 650, 245, "NAT Gateway", size=44)
icon("network/nat-gateway.png", 650, 765, "NAT Gateway B\nonly when\nNatGatewayMode=per-az", size=44)
out.append('<rect x="620" y="736" width="60" height="60" fill="none" stroke="#7AA116" stroke-dasharray="4 3"/>')

# Auto Scaling group spans both app subnets.
box(810, 245, 190, 610, "", "none", "#ED7100", dash="8 5")
icon("compute/ec2-auto-scaling.png", 905, 528,
     "Auto Scaling group\nmin 2, max 6", size=44)
icon("compute/ec2-instance.png", 905, 340, "Web instance\nAmazon Linux 2023\nIMDSv2, no SSH")
icon("compute/ec2-instance.png", 905, 740, "Web instance\nAmazon Linux 2023\nIMDSv2, no SSH")

icon("database/rds-mysql-instance.png", 1180, 340, "RDS MySQL 8.4\nprimary\nencrypted, TLS required")
icon("database/rds-mysql-instance.png", 1180, 740, "RDS MySQL 8.4\nstandby\nno traffic until failover")

# ---------------------------------------------------- operations column
box(1365, 120, 245, 840, "Operations and security", "#FFFFFF", "#7D8998", bold=True)
icon("management/cloudwatch.png", 1430, 210, "CloudWatch\n5 alarms, dashboard")
icon("integration/simple-notification-service-sns.png", 1550, 210, "SNS\nemail alerts")
icon("network/vpc-flow-logs.png", 1430, 365, "VPC Flow Logs\nrejected traffic")
icon("security/secrets-manager.png", 1550, 365, "Secrets Manager\nRDS-managed\npassword")
icon("security/identity-and-access-management-iam-role.png", 1430, 530,
     "Instance role\nSSM + one secret")
icon("management/systems-manager.png", 1550, 530, "Session Manager\nshell access\nwithout SSH")
line([(1460, 210), (1518, 210)])
line([(1430, 337), (1430, 280)])

# legend
ly = 680
out.append(f'<text x="1380" y="{ly}" class="h">Legend</text>')
for i, (style, text) in enumerate([("solid", "user request path"),
                                   ("dashed", "replication, scaling"),
                                   ("dotted", "outbound from instances")]):
    y = ly + 26 + i * 24
    line([(1382, y - 4), (1430, y - 4)], style=style, arrow=False)
    out.append(f'<text x="1440" y="{y}" class="t">{text}</text>')
out.append(f'<text x="1380" y="{ly + 110}" class="t">Security group chain:</text>')
out.append(f'<text x="1380" y="{ly + 126}" class="t">ALB SG &gt; app SG :80 &gt; DB SG :3306</text>')
out.append(f'<text x="1380" y="{ly + 150}" class="t">Data subnets: local route only</text>')
out.append(f'<text x="1380" y="{ly + 230}" class="t">S3 gateway endpoint on app routes</text>')
out.append(f'<text x="1380" y="{ly + 246}" class="t">Scaling: CPU 50%, requests/target</text>')
out.append(f'<text x="1380" y="{ly + 174}" class="t">CloudFront to ALB: secret header</text>')
out.append(f'<text x="1380" y="{ly + 190}" class="t">checked by WAF, so the ALB</text>')
out.append(f'<text x="1380" y="{ly + 206}" class="t">cannot be used directly</text>')

# ------------------------------------------------------------------ edges
line([(112, 470), (203, 470)], label="HTTPS", lx=158, ly=462)
line([(80, 500), (80, 628)], style="dashed", label="DNS", lx=100, ly=570)
line([(235, 440), (235, 200), (373, 200)], label="/static/*", lx=290, ly=192)
line([(267, 470), (373, 470)], label="everything else", lx=320, ly=462)
line([(437, 470), (470, 470), (470, 545), (470, 545)], arrow=False)
line([(470, 545), (518, 545)])
line([(520, 545), (574, 545)])
line([(679, 455), (760, 455), (760, 340), (873, 340)], label="HTTP :80", lx=815, ly=332)
line([(679, 485), (760, 485), (760, 740), (873, 740)], label="HTTP :80", lx=815, ly=732)
line([(937, 340), (1148, 340)], label="MySQL :3306, TLS", lx=1045, ly=332)
line([(937, 740), (1030, 740), (1030, 360), (1148, 360)])
line([(1180, 410), (1180, 705)], style="dashed", label="synchronous", lx=1228, ly=520)
out.append('<text x="1228" y="534" class="e" text-anchor="middle">replication</text>')
line([(905, 504), (905, 380)], style="dashed")
line([(905, 585), (905, 705)], style="dashed")
line([(873, 325), (760, 255), (676, 250)], style="dotted")

STYLE = """
.title{font:600 24px 'Segoe UI',Arial,sans-serif;fill:#232F3E}
.sub{font:400 14px 'Segoe UI',Arial,sans-serif;fill:#5A6B7B}
.h{font:600 14px 'Segoe UI',Arial,sans-serif;fill:#232F3E}
.s{font:500 12px 'Segoe UI',Arial,sans-serif;fill:#3B4A59}
.t{font:400 11.5px 'Segoe UI',Arial,sans-serif;fill:#232F3E;paint-order:stroke;stroke:#fff;stroke-width:3px}
.e{font:italic 11px 'Segoe UI',Arial,sans-serif;fill:#5A6B7B;paint-order:stroke;stroke:#fff;stroke-width:4px}
"""
svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">'
       f'<defs><style>{STYLE}</style><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" '
       f'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
       f'<path d="M0,0 L10,5 L0,10 z" fill="#232F3E"/></marker></defs>'
       + "\n".join(out) + "</svg>")
(HERE / "architecture.svg").write_text(svg)

try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=2)
        page.goto((HERE / "architecture.svg").as_uri())
        page.screenshot(path=str(HERE / "architecture.png"))
        browser.close()
except ImportError:
    print("playwright not installed: wrote SVG only")
print("wrote", HERE / "architecture.svg")
