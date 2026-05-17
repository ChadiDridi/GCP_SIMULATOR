#!/usr/bin/env python3
"""
Generate a local GCP service account JSON key and register it in the simulator DB.

Usage:
    python scripts/generate_service_account.py \
        --project local-dev \
        --email dev@local-dev.iam.gserviceaccount.com \
        --db-url postgresql://postgres:simulator-pg-pass@localhost:5432/gcp_simulator \
        --token-uri http://localhost:9099/o/oauth2/token \
        --output ./service-account.json
"""

import argparse
import json
import uuid
import sys
from datetime import datetime, timezone


def main():
    parser = argparse.ArgumentParser(description="Generate GCP simulator service account key")
    parser.add_argument("--project", default="local-dev", help="GCP project ID")
    parser.add_argument("--email", default=None, help="Service account email")
    parser.add_argument(
        "--db-url",
        default="postgresql://postgres:simulator-pg-pass@localhost:5432/gcp_simulator",
        help="PostgreSQL connection URL (sync)",
    )
    parser.add_argument(
        "--token-uri",
        default="http://localhost:9099/o/oauth2/token",
        help="Token URI in the generated key file",
    )
    parser.add_argument("--output", default="service-account.json", help="Output JSON key path")
    args = parser.parse_args()

    try:
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
    except ImportError:
        print("ERROR: cryptography package required. Run: pip install cryptography")
        sys.exit(1)

    try:
        import psycopg2
    except ImportError:
        print("ERROR: psycopg2 required for key registration. Run: pip install psycopg2-binary")
        print("Generating key file without DB registration...")
        register = False
    else:
        register = True

    project_id = args.project
    email = args.email or f"simulator@{project_id}.iam.gserviceaccount.com"
    key_id = str(uuid.uuid4()).replace("-", "")[:24]
    client_id = str(int(uuid.uuid4().int % (10**21))).zfill(21)

    # Generate RSA-2048 key pair
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()

    key_data = {
        "type": "service_account",
        "project_id": project_id,
        "private_key_id": key_id,
        "private_key": private_pem,
        "client_email": email,
        "client_id": client_id,
        "auth_uri": args.token_uri.replace("/o/oauth2/token", "/o/oauth2/auth"),
        "token_uri": args.token_uri,
        "auth_provider_x509_cert_url": args.token_uri.replace("/o/oauth2/token", "/oauth2/v1/certs"),
        "client_x509_cert_url": args.token_uri.replace("/o/oauth2/token", "/oauth2/v1/certs"),
    }

    with open(args.output, "w") as f:
        json.dump(key_data, f, indent=2)

    print(f"Service account key written to: {args.output}")

    if register:
        try:
            conn = psycopg2.connect(args.db_url)
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO auth.service_accounts (id, key_id, email, project_id, public_key_pem, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (key_id) DO UPDATE SET public_key_pem = EXCLUDED.public_key_pem
                """,
                (str(uuid.uuid4()), key_id, email, project_id, public_pem, datetime.now(timezone.utc)),
            )
            conn.commit()
            cur.close()
            conn.close()
            print(f"Service account registered in DB: {email}")
        except Exception as e:
            print(f"WARNING: Could not register in DB: {e}")
            print("Run the simulator first, then re-run this script.")

    print(f"\nSet GOOGLE_APPLICATION_CREDENTIALS={args.output}")
    print(f"The token_uri in the key file points to: {args.token_uri}")


if __name__ == "__main__":
    main()
