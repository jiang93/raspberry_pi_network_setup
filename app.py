from flask import Flask, request, render_template, flash, redirect, url_for
import os
import subprocess

# Extract country using timezone
def get_country_from_timezone():
    try:
        result = subprocess.run(["timedatectl"], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if "Time zone:" in line:
                timezone = line.split(":")[1].strip().split(" ")[0]
                region_parts = timezone.split('/')
                if len(region_parts) > 1:
                    country_name = region_parts[1].replace('_', ' ')
                    return country_name
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None
    

# Extract country code using zoneinfo
def get_country_code_from_name(name):
    try:
        command = f"cat /usr/share/zoneinfo/zone.tab | grep {name} | awk '{{print $1}}'"
        result = subprocess.run(command, shell=True, capture_output=True, text=True)

        country_code = result.stdout.strip() 
        if country_code:
            return country_code
        else:
            return None
    except:
        return None

# Initialization flask app
app = Flask(__name__)
app.secret_key = "EpeCom680401!"

# index.html 
@app.route('/')
def index():
    return render_template('index.html')

# form action
@app.route('/configure', methods=['POST'])
def configure():

    interface_type = request.form['interface_type']
    ip_mode = request.form['ip_mode']
    print(interface_type, ip_mode)

    # ---------------------------------- Ethernet ---------------------------------- #
    if interface_type == "ethernet":
            
        # clean dhcpcd.conf
        with open('/etc/dhcpcd.conf', 'r') as file:
            original_lines = file.readlines()

        cleaned_lines = []

        for line in original_lines:
            stripped_line = line.strip()
            if not stripped_line:
                continue
            if stripped_line.startswith("interface eth0"):
                break
            
            cleaned_lines.append(line)

        if ip_mode == "static":
            
            user_ip = request.form.get('static_ip')
            user_gateway = request.form.get('gateway')

            cleaned_lines += ['interface eth0', f'static ip_address={user_ip}', f'static routers={user_gateway}', f'static domain_name_servers={user_gateway}']
        
        with open('/etc/dhcpcd.conf', 'w') as file:
            file.write('\n'.join(cleaned_lines) + '\n')
                
    # ---------------------------------- Wi-Fi ---------------------------------- #

    if interface_type == "wifi":

        # wpa_supplicant config
        country_code = None
        country_name = get_country_from_timezone()
        if country_name:
            country_code = get_country_code_from_name(country_name)
        
        ssid = request.form['ssid']
        password = request.form['password']
        key_management = request.form['key_mgmt']

        config_lines = []
        if country_code:
            config_lines.append(f"country={country_code}")
        config_lines += [
            "ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev",
            "update_config=1",
            "",
            "network={",
            f'ssid="{ssid}"'
        ]

        if key_management == "WPA-EAP":
            identity = request.form.get('identity', '')
            config_lines += [
                f'identity="{identity}"',
                f'password="{password}"',
                f'eap=PEAP',
                f'phase2="auth=MSCHAPV2"',
                '}'
            ]
        else:
            config_lines += [
                f'psk="{password}"',
                f'key_mgmt={key_management}',
                '}'
            ]

        with open('/etc/wpa_supplicant/wpa_supplicant.conf', 'w') as file:
            file.write('\n'.join(config_lines) + '\n')

         # clean dhcpcd.conf
        with open('/etc/dhcpcd.conf', 'r') as file:
            original_lines = file.readlines()

        cleaned_lines = []

        for line in original_lines:
            stripped_line = line.strip()
            if not stripped_line:
                continue
            if stripped_line.startswith("interface wlan0"):
                break

            cleaned_lines.append(line)

        if ip_mode == "static":

            # dhcpcd.conf
            user_ip = request.form.get('static_ip')
            user_gateway = request.form.get('gateway')

            cleaned_lines += ['interface wlan0', f'static ip_address={user_ip}', f'static routers={user_gateway}', f'static domain_name_servers={user_gateway}']

        with open('/etc/dhcpcd.conf', 'w') as file:
            file.write('\n'.join(cleaned_lines) + '\n')
    
    return render_template('index.html')

# exceptions handling
@app.errorhandler(Exception)
def handle_all_exceptions(e):
    print(e)
    return render_template("error.html")

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=80)

