#!/bin/bash

AP_INTERFACE="wlan0"
AP_IP="192.168.50.1/24"
WPA_CONF="/etc/wpa_supplicant/wpa_supplicant.conf"
WAIT_LIMIT=120
CHECK_INTERVAL=5

echo "[+] Configuring $AP_INTERFACE as Access Point..."

# Set interface to AP mode
ip link set $AP_INTERFACE down
iw dev $AP_INTERFACE set type __ap
ip link set $AP_INTERFACE up
ip addr add $AP_IP dev $AP_INTERFACE

# Start services
echo "[*] Starting hostapd, dnsmasq, and app.py service..."
systemctl start hostapd
systemctl start dnsmasq
systemctl start wifi_setup.service

# Begin 3-minute monitoring window
echo "[*] Waiting for client to connect (up to $WAIT_LIMIT seconds)..."
START=$(date +%s)
CLIENT_CONNECTED=false

while true; do
    CLIENTS=$(iw dev $AP_INTERFACE station dump | grep Station | wc -l)
    NOW=$(date +%s)
    ELAPSED=$((NOW - START))

    if [ "$CLIENTS" -gt 0 ]; then
        echo "[✓] Client connected. Holding AP mode until disconnect..."
        CLIENT_CONNECTED=true
        break
    fi

    if [ "$ELAPSED" -ge "$WAIT_LIMIT" ]; then
        echo "[!] No client connected after $WAIT_LIMIT seconds."
        break
    fi

    sleep $CHECK_INTERVAL
done

# === No client ever connected ===
if [ "$CLIENT_CONNECTED" = false ]; then
    echo "[*] Stopping app.py and switching to STA (client) mode..."
    systemctl stop wifi_setup.service
    systemctl stop hostapd
    systemctl stop dnsmasq
    sleep 3

    ip addr flush dev $AP_INTERFACE
    ip link set $AP_INTERFACE down
    iw dev $AP_INTERFACE set type managed
    ip link set $AP_INTERFACE up

    echo "[*] Connecting to Wi-Fi using wpa_supplicant..."
    #sudo wpa_supplicant -B -i $AP_INTERFACE -c $WPA_CONF
    systemctl restart wpa_supplicant
    sleep 3

    echo "[*] Requesting IP address..."
    systemctl restart dhcpcd
    sleep 3

    echo "[✓] STA mode active."
    exit 0
fi

# === Client connected: wait for disconnect ===
while true; do
    CLIENTS=$(iw dev $AP_INTERFACE station dump | grep Station | wc -l)
    if [ "$CLIENTS" -eq 0 ]; then
        echo "[!] Client disconnected. Cleaning up and switching to STA..."

        systemctl stop wifi_setup.service
        systemctl stop hostapd
        systemctl stop dnsmasq
        sleep 3

        ip addr flush dev $AP_INTERFACE
        ip link set $AP_INTERFACE down
        iw dev $AP_INTERFACE set type managed
        ip link set $AP_INTERFACE 

        echo "[*] Connecting to Wi-Fi using wpa_supplicant..."
        #wpa_supplicant -B -i $AP_INTERFACE -c $WPA_CONF
        systemctl restart wpa_supplicant
        sleep 3

        echo "[*] Requesting IP address..."
        systemctl restart dhcpcd
        sleep 3

    sleep $CHECK_INTERVAL
done
