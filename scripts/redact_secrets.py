#!/usr/bin/env python3
"""Scan and redact secrets from a file before it is written to migration artifacts.

Usage:
    python redact_secrets.py <filepath>

Exits 0 if no secrets found, 1 if secrets were found and redacted.
"""
import re, sys

PATTERNS = [
    (r'sk-[a-zA-Z0-9]{20,}', '<REDACTED:api_key>'),
    (r'ghp_[a-zA-Z0-9]{36}', '<REDACTED:github_token>'),
    (r'Bearer\s+[a-zA-Z0-9._-]+', 'Bearer <REDACTED:token>'),
    (r'postgres(?:ql)?://[^:]+:[^@]+@', 'postgresql://<REDACTED:user:pass>@'),
    (r'redis://[^:]+:[^@]+@', 'redis://<REDACTED:pass>@'),
    (r'-----BEGIN (?:RSA |EC )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC )?PRIVATE KEY-----', '<REDACTED:private_key>'),
    (r'eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+', '<REDACTED:jwt>'),
]

def redact(text):
    found = False
    for pattern, replacement in PATTERNS:
        new_text = re.sub(pattern, replacement, text)
        if new_text != text:
            found = True
            text = new_text
    return text, found

def main():
    if len(sys.argv) < 2:
        print("Usage: redact_secrets.py <filepath>", file=sys.stderr)
        sys.exit(2)

    filepath = sys.argv[1]
    with open(filepath) as f:
        content = f.read()

    redacted, found = redact(content)

    if found:
        with open(filepath, 'w') as f:
            f.write(redacted)
        print(f"REDACTED: secrets found and replaced in {filepath}", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"CLEAN: no secrets found in {filepath}")
        sys.exit(0)

if __name__ == "__main__":
    main()
