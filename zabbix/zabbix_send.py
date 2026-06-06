#!/usr/bin/env python3
"""
Script auxiliar para integração Zabbix → WhatsApp API.

Configuração no Zabbix (Media Type → Script):
  Script: /etc/zabbix/scripts/zabbix_send.py
  Parâmetros:
    {ALERT.SENDTO}
    {ALERT.SUBJECT}
    {ALERT.MESSAGE}

Variáveis de ambiente necessárias no servidor Zabbix:
  WA_API_URL  — URL base da API (ex: http://192.168.1.10:8000)
  WA_API_KEY  — Chave de autenticação
  WA_IS_GROUP — "true" se o destino padrão for um grupo (opcional)
"""

import json
import os
import sys
import urllib.error
import urllib.request

# ─── Config ──────────────────────────────────────────────────────────────────

API_URL  = os.environ.get("WA_API_URL", "http://localhost:8000").rstrip("/")
API_KEY  = os.environ.get("WA_API_KEY", "")
IS_GROUP = os.environ.get("WA_IS_GROUP", "false").lower() == "true"


# ─── Helpers ─────────────────────────────────────────────────────────────────

def parse_subject(subject: str) -> dict:
    """Extrai status e severidade do assunto gerado pelo Zabbix."""
    result: dict = {"status": None, "severity": None}

    upper = subject.upper()
    if "RESOLVED" in upper or ": OK" in upper:
        result["status"] = "RESOLVED"
    elif "PROBLEM" in upper:
        result["status"] = "PROBLEM"

    for sev in ("Disaster", "High", "Average", "Warning", "Information", "Not classified"):
        if sev.lower() in subject.lower():
            result["severity"] = sev
            break

    return result


def send_alert(to: str, subject: str, body: str) -> None:
    parsed  = parse_subject(subject)
    payload = json.dumps(
        {
            "to":       to,
            "subject":  subject,
            "body":     body,
            "status":   parsed["status"],
            "severity": parsed["severity"],
            "is_group": IS_GROUP,
        }
    ).encode("utf-8")

    url = f"{API_URL}/api/v1/zabbix/alert"
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-API-Key":    API_KEY,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            if data.get("success"):
                print("OK: alert sent")
                sys.exit(0)
            else:
                print(f"FAIL: {data.get('error')}", file=sys.stderr)
                sys.exit(1)

    except urllib.error.HTTPError as exc:
        body_txt = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code}: {body_txt}", file=sys.stderr)
        sys.exit(1)

    except urllib.error.URLError as exc:
        print(f"Connection error: {exc.reason}", file=sys.stderr)
        sys.exit(1)


# ─── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(
            "Uso: zabbix_send.py <destinatario> <assunto> <mensagem>",
            file=sys.stderr,
        )
        sys.exit(1)

    send_alert(
        to      = sys.argv[1],
        subject = sys.argv[2],
        body    = sys.argv[3],
    )
