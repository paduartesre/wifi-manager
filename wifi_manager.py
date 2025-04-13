from flask import Flask, render_template, request, redirect, url_for, jsonify
import subprocess
import re
import os
import time
import pywifi
from pywifi import const

app = Flask(__name__)

@app.route('/')
def index():
    ssids = get_ssids()
    connected_ssid = get_connected_ssid()
    return render_template('index.html', ssids=ssids, connected_ssid=connected_ssid)

@app.route('/get_connected_ssid')
def get_connected_ssid_endpoint():
    connected_ssid = get_connected_ssid()
    return jsonify(connected_ssid=connected_ssid)

@app.route('/connect', methods=['POST'])
def connect():
    ssid = request.form.get('ssid')
    password = request.form.get('password')
    try:
        connect_to_ssid(ssid, password)
        log_action("Conection", f"Successfully connected to SSID '{ssid}'")
    except Exception as e:
        log_action("Error", f"Error connecting to SSID '{ssid}': {e}")
    return redirect(url_for('index'))

@app.route('/refresh_ssids', methods=['GET'])
def refresh_ssids():
    try:
        current_ssid = get_connected_ssid()
        refresh_wifi_adapters()
        if current_ssid:
            reconnect_to_ssid(current_ssid)
        log_action("Update", "Wi-Fi adapters successfully restarted.")
    except Exception as e:
        log_action("Error", f"Error when restarting Wi-Fi adapters: {e}")
    return redirect(url_for('index'))

def get_ssids():
    try:
        result = subprocess.check_output(['netsh', 'wlan', 'show', 'networks'], universal_newlines=True)
        ssids = re.findall(r'SSID \d+ : (.+)', result)
        return [ssid.strip() for ssid in ssids]
    except Exception as e:
        log_action("Error", f"SSID search error: {e}")
        return []

def get_connected_ssid():
    try:
        result = subprocess.check_output(['netsh', 'wlan', 'show', 'interfaces'], universal_newlines=True)
        match = re.search(r'SSID\s+:\s+(.*)', result)
        if match:
            return match.group(1).strip()
        return None
    except Exception as e:
        log_action("Error", f"Error when searching for connected SSID: {e}")
        return None

def log_action(action, details=""):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open("logs/wifi_manager.log", "a") as log_file:
        log_file.write(f"[{timestamp}] {action}: {details}\n")

def profile_exists(ssid):
    """Checks if a profile for the specified SSID already exists."""
    wifi = pywifi.PyWiFi()
    iface = wifi.interfaces()[0]
    return ssid in [profile.ssid for profile in iface.network_profiles()]

def delete_profile(ssid):
    """Removes the existing profile."""
    wifi = pywifi.PyWiFi()
    iface = wifi.interfaces()[0]
    profiles = iface.network_profiles()
    for profile in profiles:
        if profile.ssid == ssid:
            iface.remove_network_profile(profile)

def connect_to_ssid(ssid, password):
    if profile_exists(ssid):
        delete_profile(ssid)
    
    wifi = pywifi.PyWiFi()
    iface = wifi.interfaces()[0]

    # Create a profile
    profile = pywifi.Profile()
    profile.ssid = ssid
    profile.auth = const.AUTH_ALG_OPEN
    profile.akm.append(const.AKM_TYPE_WPA2PSK)
    profile.cipher = const.CIPHER_TYPE_CCMP
    profile.key = password

    iface.add_network_profile(profile)

    # Connecting Network
    iface.connect(profile)
    time.sleep(10)  # gives time for the connection to be established

    # Check if the connection was successful
    if iface.status() != const.IFACE_CONNECTED:
        raise Exception(f"Unable to connect to SSID '{ssid}'.")

def get_active_interface():
    try:
        result = subprocess.check_output(['netsh', 'wlan', 'show', 'interfaces'], universal_newlines=True)
        matches = re.findall(r'Nome\s+:\s+(.*)', result)
        if matches:
            return matches[0].strip()
        return None
    except Exception as e:
        log_action("Error", f"Error searching for active interface: {e}")
        return None

def refresh_wifi_adapters():
    interface_name = get_active_interface()
    if not interface_name:
        log_action("Error", "We couldn't find the active interface.")
        return

    current_ssid = get_connected_ssid()
    subprocess.run(['netsh', 'interface', 'set', 'interface', interface_name, 'admin=disable'], check=True)
    time.sleep(3)  # Wait for a while while disabling the network adapter
    subprocess.run(['netsh', 'interface', 'set', 'interface', interface_name, 'admin=enable'], check=True)
    time.sleep(3)  # Wait a while for the adapter to become fully active
    if current_ssid:
        reconnect_to_ssid(current_ssid)


def reconnect_to_ssid(ssid):
    wifi = pywifi.PyWiFi()
    iface = wifi.interfaces()[0]
    profiles = iface.network_profiles()
    for profile in profiles:
        if profile.ssid == ssid:
            iface.connect(profile)
            time.sleep(10)  # gives the connection time to establish
            return

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
