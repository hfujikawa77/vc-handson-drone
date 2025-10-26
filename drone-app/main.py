import time
import argparse
from pymavlink import mavutil

# 接続文字列
connection_string = 'tcp:127.0.0.1:5763'
vehicle = None

def connect_to_vehicle():
    global vehicle
    print(f"Connecting to vehicle on: {connection_string}")
    try:
        vehicle = mavutil.mavlink_connection(connection_string, wait_heartbeat=True)
        vehicle.wait_heartbeat()
        print("Heartbeat from system (system %u component %u)" % (vehicle.target_system, vehicle.target_component))
        return True
    except Exception as e:
        print(f"Failed to connect to vehicle: {e}")
        return False

def set_mode(mode_name):
    if not vehicle:
        print("Vehicle not connected.")
        return False

    print(f"Setting mode to {mode_name}...")
    # Check if mode is available
    if mode_name not in vehicle.mode_mapping():
        print(f"Unknown mode: {mode_name}")
        print("Available modes: ", list(vehicle.mode_mapping().keys()))
        return False

    mode_id = vehicle.mode_mapping()[mode_name]
    vehicle.set_mode(mode_id)

    # Assume mode change is successful after sending the command and a short delay
    time.sleep(1)
    print(f"Mode change command sent for {mode_name}.")
    return True

def arm_vehicle():
    if not vehicle:
        print("Vehicle not connected.")
        return

    # Ensure vehicle is in GUIDED mode before arming
    if not set_mode("GUIDED"):
        print("Failed to set GUIDED mode. Cannot arm.")
        return

    print("Arming motors...")
    vehicle.mav.command_long_send(
        vehicle.target_system,
        vehicle.target_component,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        0,
        1, 0, 0, 0, 0, 0, 0)
    
    # Wait for arming to complete
    # In a real application, you would monitor vehicle status
    time.sleep(5) # Give it some time to arm
    print("Motors armed!")

def takeoff_vehicle(altitude):
    if not vehicle:
        print("Vehicle not connected.")
        return

    # Ensure vehicle is in GUIDED mode before takeoff
    if not set_mode("GUIDED"):
        print("Failed to set GUIDED mode. Cannot takeoff.")
        return

    print(f"Taking off to altitude: {altitude} meters")
    vehicle.mav.command_long_send(
        vehicle.target_system,
        vehicle.target_component,
        mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
        0,
        0, 0, 0, 0, 0, 0, altitude)
    
    # Wait for vehicle to reach target altitude (simplified)
    time.sleep(10) # Give it some time to ascend
    print("Takeoff complete.")

def goto_location(latitude, longitude, altitude):
    if not vehicle:
        print("Vehicle not connected.")
        return

    # Ensure vehicle is in GUIDED mode before moving
    if not set_mode("GUIDED"):
        print("Failed to set GUIDED mode. Cannot move.")
        return

    print(f"Moving to Lat: {latitude}, Lon: {longitude}, Alt: {altitude}")
    vehicle.mav.set_position_target_global_int_send(
        0,       # time_boot_ms (not used)
        vehicle.target_system,
        vehicle.target_component,
        mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
        0b0000111111111000, # type_mask (only speeds enabled)
        int(latitude * 1e7),
        int(longitude * 1e7),
        altitude,
        0,       # vx
        0,       # vy
        0,       # vz
        0, 0, 0, # afx, afy, afz (not used)
        0, 0)    # yaw, yaw_rate (not used)
    
    time.sleep(15) # Give it some time to move
    print("Movement complete.")

def land_vehicle():
    if not vehicle:
        print("Vehicle not connected.")
        return

    print("Landing vehicle...")
    vehicle.mav.command_long_send(
        vehicle.target_system,
        vehicle.target_component,
        mavutil.mavlink.MAV_CMD_NAV_LAND,
        0,
        0, 0, 0, 0, 0, 0, 0)
    
    # Wait for disarming to complete (simplified)
    time.sleep(10) # Give it some time to land and disarm
    print("Vehicle landed and disarmed.")

def main():
    print("""
+----------------------------------+
|      Drone Control System        |
+----------------------------------+
""")
    if not connect_to_vehicle():
        print("Exiting due to connection failure.")
        return

    print("\\nAvailable commands: arm, takeoff <altitude>, goto <lat> <lon> <alt>, land, mode <mode_name>, exit/quit")
    while True:
        try:
            command_line = input("Enter command > ").strip().split()
            if not command_line:
                continue

            command = command_line[0].lower()

            if command == "arm":
                arm_vehicle()
            elif command == "takeoff":
                if len(command_line) < 2:
                    print("Usage: takeoff <altitude>")
                    continue
                try:
                    altitude = float(command_line[1])
                    takeoff_vehicle(altitude)
                except ValueError:
                    print("Invalid altitude. Please provide a number.")
            elif command == "goto":
                if len(command_line) < 4:
                    print("Usage: goto <latitude> <longitude> <altitude>")
                    continue
                try:
                    latitude = float(command_line[1])
                    longitude = float(command_line[2])
                    altitude = float(command_line[3])
                    goto_location(latitude, longitude, altitude)
                except ValueError:
                    print("Invalid coordinates or altitude. Please provide numbers.")
            elif command == "land":
                land_vehicle()
            elif command == "mode":
                if len(command_line) < 2:
                    print("Usage: mode <mode_name>")
                    continue
                mode_name = command_line[1]
                set_mode(mode_name.upper())
            elif command in ["exit", "quit"]:
                print("Exiting application.")
                break
            else:
                print("Unknown command. Available commands: arm, takeoff, goto, land, mode, exit/quit")
        except KeyboardInterrupt:
            print("\\nExiting application.")
            break
        except Exception as e:
            print(f"An error occurred: {e}")

if __name__ == '__main__':
    main()