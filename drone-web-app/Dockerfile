FROM python:3.11-slim

# --- BlueOS Extension メタデータ（Docker LABEL から読まれる） ---
LABEL version="1.0.0"
# bridge ネットワーク + ポート固定(9999) + host.docker.internal を host-gateway に解決。
# avoid_iframes で :9999 を直接開くため、ポートは固定しておく。
LABEL permissions='{"ExposedPorts":{"9999/tcp":{}},"HostConfig":{"PortBindings":{"9999/tcp":[{"HostPort":"9999"}]},"ExtraHosts":["host.docker.internal:host-gateway"]}}'
LABEL authors='[{"name":"<Your Name>","email":"<you@example.com>"}]'
LABEL company='{"name":"","email":"","about":""}'
LABEL type="other"
LABEL tags='["drone","mavlink"]'
LABEL readme=''
LABEL links='{}'
LABEL requirements=''

WORKDIR /app

# 依存だけ先に入れてレイヤキャッシュを効かせる
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# アプリ本体（backend と frontend の相対関係を維持）
COPY backend/ ./backend/
COPY frontend/ ./frontend/

WORKDIR /app/backend
EXPOSE 9999
# --no-access-log: Helper の継続ヘルスチェックによるログ肥大（VIEW LOGS タイムアウト）を防ぐ
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9999", "--no-access-log"]
