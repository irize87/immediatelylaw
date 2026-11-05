#!/usr/bin/env bash
# 즉시로 배포 서버 1회 설치(서버 root) — 자체서명 인증서 + systemd 서비스.
# 사용: sudo bash tools/install_mirror.sh
set -e
SUDO_USER_HOME="$(getent passwd "${SUDO_USER:-ubuntu}" | cut -d: -f6)"
APP="${SUDO_USER_HOME}/ImmediatelyLaw"
ETC=/etc/immediatelylaw-mirror
DIR="${SUDO_USER_HOME}/immediatelylaw-mirror"
# 미러 IP는 하드코딩하지 않는다(소스 공개 정책). 환경변수로 주거나 첫 IPv4를 쓴다.
IP="${IMMEDIATELYLAW_MIRROR_IP:-$(hostname -I | cut -d' ' -f1)}"

if [ "$(id -u)" != "0" ]; then echo "root로 실행하세요(sudo)."; exit 1; fi

mkdir -p "$ETC" "$DIR"
if [ ! -f "$ETC/cert.pem" ]; then
    openssl req -x509 -newkey rsa:2048 -sha256 -days 3650 -nodes \
        -keyout "$ETC/key.pem" -out "$ETC/cert.pem" \
        -subj "/CN=$IP" \
        -addext "subjectAltName=IP:$IP" >/dev/null 2>&1
    chmod 600 "$ETC/key.pem"
    echo "인증서 생성: $ETC/cert.pem (10년)"
fi
HASH=$(openssl x509 -in "$ETC/cert.pem" -outform DER | sha256sum | cut -d' ' -f1)
echo "$HASH" > "$ETC/cert_hash.txt"
echo "인증서 고정갑(workers.py CERT_PINS에 기록): $HASH"

# 첫 동기화
cp -f "$APP/data/dist/"* "$DIR"/ 2>/dev/null || true
cp -rf "$APP/web/." "$DIR"/ 2>/dev/null || true
chown -R "${SUDO_USER:-ubuntu}":"${SUDO_USER:-ubuntu}" "$DIR"

cat >/etc/systemd/system/immediatelylaw-mirror.service <<EOF
[Unit]
Description=ImmediatelyLaw distribution server (static HTTPS)
After=network-online.target

[Service]
ExecStart=$SUDO_USER_HOME/ImmediatelyLaw/.venv/bin/python3 $SUDO_USER_HOME/ImmediatelyLaw/tools/mirror_serve.py --dir $DIR --cert $ETC/cert.pem --key $ETC/key.pem --port 443
WorkingDirectory=$SUDO_USER_HOME/ImmediatelyLaw
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now immediatelylaw-mirror.service
sleep 1
systemctl is-active immediatelylaw-mirror.service && \
    echo "배포 서버 실행 중 — https://$IP/manifest.json (방화벽·보안 리스트에서 443 허용 필요)"
