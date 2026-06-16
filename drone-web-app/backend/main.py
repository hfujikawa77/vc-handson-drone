import os
import json
import time
import threading
import functools
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pymavlink import mavutil

app = FastAPI()

# フロントエンドの場所を CWD に依存せず解決する（コンテナでも確実に見つける）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")

# 静的ファイル配信
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

# MAVLink 接続先は環境変数で切り替える（未指定なら BlueOS Extension 用の既定値）。
#   WSL でローカルテスト  : MAV_ENDPOINT=tcp:127.0.0.1:5762
#   BlueOS Extension(bridge): host.docker.internal 経由（既定）
connection_string = os.environ.get("MAV_ENDPOINT", "udpout:host.docker.internal:14550")

vehicle = None
drone_connected = False
# autopilot の機体タイプから明示的に作るモードマップ（Router 経由の取り違え対策）
MODE_MAP = {}
drone_status = {
    "connected": False,
    "armed": False,
    "mode": "UNKNOWN",
    "latitude": 0.0,
    "longitude": 0.0,
    "altitude": 0.0,
    "heading": 0,
}


# --- MAVLink 接続 ---
def _recv_autopilot_heartbeat(v, timeout=10):
    """autopilot（非GCS）の HEARTBEAT を返す。

    MAVLink Router 経由では Mission Planner 等の GCS の HEARTBEAT も流れてくるため、
    autopilot のものだけを採用する（これを誤ると機体特定・モードマップを取り違える）。
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        hb = v.recv_match(type="HEARTBEAT", blocking=True, timeout=1)
        if hb is None:
            continue
        if hb.autopilot == mavutil.mavlink.MAV_AUTOPILOT_INVALID:
            continue  # GCS / 非autopilot コンポーネントを除外
        return hb
    return None


def connect_to_vehicle():
    """接続が確立するまでリトライし続ける（起動順序に依存しない）。"""
    global vehicle, drone_connected, MODE_MAP
    while not drone_connected:
        try:
            print(f"Connecting to vehicle on: {connection_string}")
            v = mavutil.mavlink_connection(connection_string)
            # UDP Server(Router) はクライアントの最初のパケットを受けるまで送ってこないため、
            # 先に heartbeat を送って自分のアドレスを登録させる。
            v.mav.heartbeat_send(
                mavutil.mavlink.MAV_TYPE_GCS,
                mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0, 0
            )
            hb = _recv_autopilot_heartbeat(v)
            if hb is None:
                print("autopilot heartbeat not received, retrying...")
                continue
            v.target_system = hb.get_srcSystem()
            v.target_component = hb.get_srcComponent()
            # 機体タイプから明示的にモードマップを作る。
            # v.mode_mapping() は「直近の HEARTBEAT」を見るため、Router 経由だと
            # GCS や別機体を拾って誤ったマップ（例: Plane）を返すことがある。
            MODE_MAP = mavutil.mode_mapping_byname(hb.type) or {}
            # テレメトリのストリーム要求（直結TCPでは必須、Router 経由でも無害）
            v.mav.request_data_stream_send(
                v.target_system, v.target_component,
                mavutil.mavlink.MAV_DATA_STREAM_ALL, 4, 1
            )
            vehicle = v
            drone_connected = True
            drone_status["connected"] = True
            print("Vehicle connected (system %u component %u, type %u)"
                  % (v.target_system, v.target_component, hb.type))
        except Exception as e:
            print(f"Failed to connect to vehicle: {e}; retrying in 3s")
            time.sleep(3)


# --- コマンド ---
async def set_mode(mode_name):
    if not vehicle or not drone_connected:
        return False
    if mode_name not in MODE_MAP:
        print(f"Unknown mode: {mode_name}; available: {list(MODE_MAP.keys())}")
        return False
    vehicle.set_mode(MODE_MAP[mode_name])
    print(f"Mode change command sent for {mode_name}.")
    return True


async def arm_vehicle():
    if not vehicle or not drone_connected:
        return
    if not await set_mode("GUIDED"):
        print("Failed to set GUIDED mode. Cannot arm.")
        return
    print("Arming motors...")
    vehicle.mav.command_long_send(
        vehicle.target_system, vehicle.target_component,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        0, 1, 0, 0, 0, 0, 0, 0)
    print("Arm command sent.")


async def takeoff_vehicle(altitude):
    if not vehicle or not drone_connected:
        return
    if not await set_mode("GUIDED"):
        print("Failed to set GUIDED mode. Cannot takeoff.")
        return
    print(f"Taking off to altitude: {altitude} meters")
    vehicle.mav.command_long_send(
        vehicle.target_system, vehicle.target_component,
        mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
        0, 0, 0, 0, 0, 0, 0, altitude)
    print("Takeoff command sent.")


async def land_vehicle():
    if not vehicle or not drone_connected:
        return
    print("Landing vehicle...")
    vehicle.mav.command_long_send(
        vehicle.target_system, vehicle.target_component,
        mavutil.mavlink.MAV_CMD_NAV_LAND,
        0, 0, 0, 0, 0, 0, 0, 0)
    print("Land command sent.")


async def goto_location(latitude, longitude, altitude):
    if not vehicle or not drone_connected:
        return
    if not await set_mode("GUIDED"):
        print("Failed to set GUIDED mode. Cannot go to location.")
        return
    print(f"Moving to Lat: {latitude}, Lon: {longitude}, Alt: {altitude}")
    vehicle.mav.set_position_target_global_int_send(
        0,
        vehicle.target_system, vehicle.target_component,
        mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
        0b0000111111111000,
        int(latitude * 1e7),
        int(longitude * 1e7),
        altitude,
        0, 0, 0,
        0, 0, 0,
        0, 0)
    print("Go-to command sent.")


# --- WebSocket ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("WebSocket connected.")
    try:
        await websocket.send_json(drone_status)

        async def mavlink_reader():
            global drone_status
            loop = asyncio.get_event_loop()
            while True:
                try:
                    if vehicle and drone_connected:
                        msg = await loop.run_in_executor(
                            None, functools.partial(vehicle.recv_match, blocking=True, timeout=0.1)
                        )
                        # 接続した autopilot 以外（MAVProxy 等の GCS, 別機体・別コンポーネント）の
                        # メッセージは無視する。これをしないと別システムの HEARTBEAT で
                        # mode/armed が点滅する。
                        if (msg
                                and msg.get_srcSystem() == vehicle.target_system
                                and msg.get_srcComponent() == vehicle.target_component):
                            if msg.get_type() == 'GLOBAL_POSITION_INT':
                                drone_status["latitude"] = msg.lat / 1e7
                                drone_status["longitude"] = msg.lon / 1e7
                                drone_status["altitude"] = msg.relative_alt / 1000.0
                                drone_status["heading"] = msg.hdg / 100.0
                                await websocket.send_json(drone_status)
                            elif msg.get_type() == 'HEARTBEAT':
                                # ARM 状態は base_mode の SAFETY_ARMED フラグで判定する
                                drone_status["armed"] = bool(
                                    msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED
                                )
                                # custom_mode → モード名（autopilot のマップで逆引き）
                                mode_name = "UNKNOWN"
                                for name, mode_id_val in MODE_MAP.items():
                                    if mode_id_val == msg.custom_mode:
                                        mode_name = name
                                        break
                                drone_status["mode"] = mode_name
                                await websocket.send_json(drone_status)
                        else:
                            await asyncio.sleep(0.01)
                    else:
                        # 接続待ち（バックグラウンドで接続中）
                        drone_status["connected"] = drone_connected
                        await asyncio.sleep(1)
                except WebSocketDisconnect:
                    break
                except Exception as e:
                    print(f"An error occurred in mavlink_reader: {e}")
                    break

        reader_task = asyncio.create_task(mavlink_reader())

        while True:
            data = await websocket.receive_text()
            command = json.loads(data)
            print(f"Received command: {command}")

            if command["type"] == "connect":
                # 接続はサーバ起動時に自動で行う。ここでは現在の状態を返すだけ。
                await websocket.send_json({"type": "status",
                                           "message": "connected" if drone_connected else "connecting..."})
            elif command["type"] == "arm":
                await arm_vehicle()
                await websocket.send_json({"type": "status", "message": "Arm command sent."})
            elif command["type"] == "takeoff":
                altitude = float(command["altitude"])
                await takeoff_vehicle(altitude)
                await websocket.send_json({"type": "status", "message": f"Takeoff to {altitude}m command sent."})
            elif command["type"] == "land":
                await land_vehicle()
                await websocket.send_json({"type": "status", "message": "Land command sent."})
            elif command["type"] == "goto":
                lat = float(command["latitude"])
                lon = float(command["longitude"])
                alt = float(command["altitude"])
                await goto_location(lat, lon, alt)
                await websocket.send_json({"type": "status", "message": f"GoTo {lat},{lon},{alt} command sent."})
            elif command["type"] == "mode":
                mode_name = command["mode_name"].upper()
                await set_mode(mode_name)
                await websocket.send_json({"type": "status", "message": f"Mode change to {mode_name} command sent."})

    except WebSocketDisconnect:
        print("WebSocket disconnected.")
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        if 'reader_task' in locals() and not reader_task.done():
            reader_task.cancel()


# --- BlueOS Extension 連携 ---
@app.get("/register_service")
async def register_service():
    # avoid_iframes=True: BlueOS は iframe 埋め込みではなく http://<IP>:<port>/ を直接開く。
    # これにより WebSocket がリバースプロキシを経由せず直結でき、絶対パスもそのまま動く。
    return {
        "name": "Drone Web Control",
        "description": "WebSocket + 地図によるドローン操作・監視パネル",
        "icon": "mdi-drone",
        "company": "",
        "version": "1.0.0",
        "webpage": "",
        "api": "/docs",
        "avoid_iframes": True,
    }


# --- フロントエンド配信 ---
@app.get("/")
async def get_frontend():
    with open(os.path.join(FRONTEND_DIR, "index.html"), "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


# --- 起動時に自動接続（バックグラウンド・非ブロック） ---
@app.on_event("startup")
async def startup_event():
    threading.Thread(target=connect_to_vehicle, daemon=True).start()
