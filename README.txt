This python application is created to configure the network of a raspberry pi. 

The raspberry pi will be act as a hotspot for 3 mins when it boots up. During this time, user can connect to the raspberry pi hotspot and access the network configuration webpage 192.168.50.1:80 via a phone or computer.

BOOT → ap_then_sta.service → ap_then_sta.sh
    |
    ├─> Sets AP mode (hostapd + dnsmasq + Flask UI)
    ├─> Waits 3 minutes for user to connect
    │
    └─> If no user connected:
           └─> Stop AP
           └─> Switch to STA mode (wpa_supplicant)

Below are the files associated for hosting this application.

The hosting of the webpage is using the systemctl. Here are the .service and .sh files associate for running the network configuration webpage.

package needed:
1. sudo apt install dnsmasq
2. sudo apt install hostapd

/etc/dnsmasq.conf
========================================
interface=wlan0
dhcp-range=192.168.50.2,192.168.50.100,255.255.255.0,365d

========================================

/etc/hostapd/hostapd.conf
========================================
interface=wlan0
driver=nl80211
ssid=SEAL_Setup
hw_mode=g
channel=6
auth_algs=1
wmm_enabled=0
ignore_broadcast_ssid=0
========================================

/etc/network/interfaces
========================================
source /etc/network/interfaces.d/*

# WiFi AP Configuration
allow-hotplug wlan0
iface wlan0 inet static
address 192.168.50.1
netmask 255.255.255.0
========================================

# /etc/systemd/system/wifi_setup.service
========================================
[Unit]
Description=WiFi Setup Web Interface
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/pi/wifi_setup/app.py
WorkingDirectory=/home/pi/wifi_setup/
Restart=always
User=root

[Install]
WantedBy=multi-user.target
========================================

/usr/local/bin/ap_then_sta.sh
========================================
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
========================================

# /etc/systemd/system/ap_then_sta.service
========================================
# /etc/systemd/system/ap_then_sta.service
[Unit]
Description=Start AP then fallback to STA
After=network.target

[Service]
ExecStart=/usr/local/bin/ap_then_sta.sh
Type=oneshot
RemainAfterExit=no

[Install]
WantedBy=multi-user.target

========================================

