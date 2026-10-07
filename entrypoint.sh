#!/bin/sh

set -e

UUID="${VLESS_UUID:-11111111-1111-1111-1111-111111111111}"
WS_PATH="${WS_PATH:-/vless}"

mkdir -p /etc/xray

cat > /etc/xray/config.json <<EOF
{
  "log": {
    "loglevel": "warning"
  },
  "inbounds": [
    {
      "listen": "0.0.0.0",
      "port": 8080,
      "protocol": "vless",
      "settings": {
        "clients": [
          {
            "id": "$UUID",
            "email": "user@vless"
          }
        ],
        "decryption": "none"
      },
      "streamSettings": {
        "network": "ws",
        "security": "none",
        "wsSettings": {
          "path": "$WS_PATH"
        }
      }
    }
  ],
  "outbounds": [
    {
      "protocol": "freedom"
    }
  ]
}
EOF

exec /usr/local/bin/xray/xray run -config /etc/xray/config.json