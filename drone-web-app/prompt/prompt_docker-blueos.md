# プロンプト: drone-web-app を BlueOS Extension 化する（Docker化 + Extension化）

## 役割・前提

あなたは ArduPilot / BlueOS 向けの Companion Computer アプリ開発を行うエンジニアです。
既存の `drone-web-app`（ローカル SITL で動作する Web 制御アプリ）を、**変更を最小限にしつつ** Raspberry Pi 上の **BlueOS Extension** として動作するように改修してください。

**既存アプリの構成（変更しない技術スタック）**
- バックエンド: FastAPI + pymavlink、リアルタイムは **WebSocket**
- フロントエンド: 静的 HTML/JS + **Leaflet** 地図
- ディレクトリ: `drone-web-app/{backend/main.py, frontend/{index.html,script.js,style.css}}`

**ゴール**
- ローカル（WSL + SITL）でも、BlueOS 上の Extension でも、**同一コード・同一イメージ**で動く。
- BlueOS の左メニューに表示され、クリックで操作パネル（地図・ステータス・コマンド）が開く。

---

## 重要前提: BlueOS Extension の「効かせ方」と落とし穴

実装前に、以下の BlueOS 固有の挙動を必ず踏まえること（AI が外しがちな点であり、本改修の核心）。

1. **メタデータは Docker イメージの LABEL から読まれる**（`metadata.json` は読まれない）。
2. **左メニュー登録は実行時の `GET /register_service`** が返す JSON で行われる。
3. **Helper は `GET /` が HTTP 200 を返すサービスのみ「有効」と判定**し、その後 `/register_service` を呼ぶ。`/` が 404 だとメニューに出ない。
4. **`permissions` LABEL は Docker のコンテナ作成設定としてそのまま渡される**。`NetworkMode` 等はトップレベルではなく **`HostConfig` の下**に置く。さらに **Create from scratch でインストールする場合、Web UI の JSON エディタ（= `user_permissions`）が LABEL より優先される**ので、同じ内容をそこにも入力する必要がある。
5. **bridge ネットワーク + ポートバインディング**が公式推奨（`NetworkMode: host` は非推奨）。bridge では BlueOS-core のネットワークを共有しないため、MAVLink/API へは `localhost` ではなく **`host.docker.internal`** でアクセスする（`HostConfig.ExtraHosts` に `host.docker.internal:host-gateway`）。
6. **MAVLink Router 経由は複数システムが混在する**（autopilot に加え Mission Planner 等の GCS、MAVProxy など）。`HEARTBEAT` をどれでも拾うと機体特定・モードマップ・mode/armed 表示を誤る。
7. **本アプリは WebSocket を使う**。BlueOS が自動生成する nginx ルート（`/extensionv2/<name>/`）には WS アップグレードヘッダが無いため、iframe 埋め込みだと WS が繋がらない。→ **`register_service` に `avoid_iframes: true`** を指定し、`http://<IP>:<port>/` を直接開かせる（プロキシを経由しないので WS も絶対パスもそのまま動く）。ポートは固定（`9999`）にする。

---

## 実装タスク

### 1. `backend/main.py`

- **接続先を環境変数化**: `connection_string = os.environ.get("MAV_ENDPOINT", "udpout:host.docker.internal:14550")`
  - 既定は BlueOS（bridge）用。ローカルは `MAV_ENDPOINT=tcp:127.0.0.1:5762` で上書きする運用。
- **接続はバックグラウンドスレッドでリトライし続ける**（起動順序に依存しない／import 時にブロックしない）。FastAPI 起動時に開始。
- **autopilot の HEARTBEAT を特定して target を固定**する。`autopilot == MAV_AUTOPILOT_INVALID`（GCS 等）は除外。先に自分の GCS heartbeat を送って UDP Server に登録させる。
- **モードマップは機体タイプから明示生成**: `MODE_MAP = mavutil.mode_mapping_byname(hb.type)`。`vehicle.mode_mapping()` は「直近の HEARTBEAT」を見て Plane/Copter を取り違える（例: Plane の GUIDED=15 を Copter に送ると AUTOTUNE になる）ので使わない。
- **受信ループは自機のメッセージのみ処理**: `msg.get_srcSystem()==target_system and msg.get_srcComponent()==target_component` のときだけ status を更新（さもないと GCS の HEARTBEAT で mode/armed が点滅する）。
- **ARM 判定は `base_mode & MAV_MODE_FLAG_SAFETY_ARMED`**（`system_status==ACTIVE` ではない）。
- **`GET /register_service`** を追加（必須キー: name/description/icon/company/version/webpage/api、**`avoid_iframes: true`**）。
- **`GET /`** は index.html を 200 で返す。
- **静的ファイル/Webページのパスは CWD 非依存**（`__file__` 基準で `frontend/` を解決）。

### 2. `frontend/`（Leaflet をローカル同梱）

- `unpkg.com` 等の **外部 CDN 依存を排除**。`leaflet.js` / `leaflet.css` / マーカー画像を `frontend/leaflet/`（`images/` 含む）に同梱し、`index.html` を `/static/leaflet/...` 参照に変更する。
  - 理由: BlueOS のホットスポットに接続した PC はインターネットに出られず、CDN を名前解決できないため地図が表示されない（`L is not defined`）。
- **地図タイル（OSM）のオフライン対応はスコープ外（発展課題）**。オフラインでは灰色背景＋マーカー/航跡が出ればよい。

### 3. `drone-web-app/Dockerfile`

- `python:3.11-slim`、`backend/`・`frontend/` の相対関係を維持して COPY、`WORKDIR /app/backend`。
- 起動: `uvicorn main:app --host 0.0.0.0 --port 9999 --no-access-log`
  - `--no-access-log` は、Helper の継続ヘルスチェックでログが肥大化し BlueOS の VIEW LOGS が全件取得でタイムアウトするのを防ぐため。
- **BlueOS Extension LABEL** を付与（`<...>` は各自）:
  ```dockerfile
  LABEL version="1.0.0"
  LABEL permissions='{"ExposedPorts":{"9999/tcp":{}},"HostConfig":{"PortBindings":{"9999/tcp":[{"HostPort":"9999"}]},"ExtraHosts":["host.docker.internal:host-gateway"]}}'
  LABEL authors='[{"name":"<Your Name>","email":"<you@example.com>"}]'
  LABEL company='{"name":"","email":"","about":""}'
  LABEL type="other"
  LABEL tags='["drone","mavlink"]'
  LABEL readme=''
  LABEL links='{}'
  LABEL requirements=''
  ```

### 4. 無視設定

- `drone-web-app/.dockerignore`: `__pycache__/`, `*.pyc`, `.git`, `*.md` 等。
- リポジトリ root `.gitignore`: Python（`__pycache__/`, `*.py[cod]`, venv）、SITL/MAVProxy 生成物（`mav.tlog*`, `mav.parm`, `eeprom.bin`, `*.BIN`, `logs/`, `terrain/`, `*.log`）、OS/エディタ。

---

## ビルド & デプロイ

```bash
# ローカル確認（SITL を先に起動しておく）
docker build -t drone-web-app .
docker run --rm --network host -e MAV_ENDPOINT=tcp:127.0.0.1:5762 drone-web-app
#  → http://localhost:9999/

# BlueOS 配布（Pi は arm64。マルチアーキ + push。push エラー時は --provenance=false）
docker buildx build --platform linux/amd64,linux/arm64 --provenance=false \
  -t <user>/drone-web-app:latest --push .
```

BlueOS Web UI → `Extensions` → `INSTALLED` → `+` → `Create from scratch`:

| 項目 | 値 |
|---|---|
| Extension Identifier | `<user>.drone-web-control` |
| Extension Name | `Drone Web Control` |
| Docker image | `<user>/drone-web-app` |
| Docker tag | `latest` |

**JSON エディタ**（LABEL と同じ内容を必ず入力。空 `{}` だと bridge/ポートが効かずメニューに出ない）:
```json
{"ExposedPorts":{"9999/tcp":{}},"HostConfig":{"PortBindings":{"9999/tcp":[{"HostPort":"9999"}]},"ExtraHosts":["host.docker.internal:host-gateway"]}}
```

---

## 受け入れ条件（Definition of Done）

- [ ] 左メニューに **Drone Web Control** が表示される。
- [ ] クリックで `http://<BlueOS_IP>:9999/` が開き、UI が表示される（avoid_iframes）。
- [ ] ステータス（接続/ARM/モード/緯度経度/高度）が **点滅せず安定**して表示される。
- [ ] ARM / TAKEOFF / LAND / GoTo / モード変更が機能し、**TAKEOFF で AUTOTUNE 等の誤モードにならない**（GUIDED に入る）。
- [ ] オフライン（ホットスポット接続）でも **地図ウィジェット・マーカー・航跡が描画**される（タイルは灰色で可）。
- [ ] ローカルでは `docker run --network host -e MAV_ENDPOINT=tcp:127.0.0.1:5762` で同じく動作する。

## スコープ外（発展課題）

- 地図タイルのオフライン表示（事前タイル同梱／ローカルタイルサーバ）。
- ユーザー認証、WSS（TLS）。
