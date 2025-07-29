from flask import Flask, request
import os
import subprocess
import pycountry

def get_country_from_timezone():
    try:
        result = subprocess.run(['timedatectl'], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if "Time zone:" in line:
                timezone = line.split(":")[1].strip().split(" ")[0]
                region_parts = timezone.split('/')
                if len(region_parts) > 1:
                    country_name = region_parts[1].replace('_', ' ')
                    return country_name
    except Exception as e:
        print(f"Error: {e}")
    return None

def get_country_code_from_name(name):
    try:
        country = pycountry.countries.search_fuzzy(name)[0]
        return country.alpha_2
    except:
        return None

app = Flask(__name__)

@app.route('/')
def index():
    return '''
        <html>
        <head>
            <title>SEAL WiFi Configuration</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    background-color: #f9f9f9;
                    padding: 40px;
                    display: flex;
                    justify-content: center;
                }
                .container {
                    background-color: #fff;
                    padding: 30px 40px;
                    border-radius: 8px;
                    box-shadow: 0 0 15px rgba(0,0,0,0.1);
                    width: 360px;
                }
                h2 {
                    color: #333;
                    margin-bottom: 20px;
                }
                .form-group {
                    display: flex;
                    flex-direction: column;
                    margin-bottom: 15px;
                }
                .form-group label {
                    margin-bottom: 5px;
                    font-weight: bold;
                }
                input[type=text],
                input[type=password],
                select {
                    padding: 8px;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    font-size: 14px;
                }
                input[type=submit] {
                    background-color: #4CAF50;
                    color: white;
                    padding: 10px;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                    font-size: 16px;
                }
                input[type=submit]:hover {
                    background-color: #45a049;
                }
                #idField {
                    display: none;
                }
            </style>
            <script>
                function toggleEAPfield() {
                    var type = document.getElementById("key_mgmt").value;
                    var field = document.getElementById("idField");
                    field.style.display = (type === "WPA-EAP") ? "block" : "none";
                }

                function toggleStaticIP() {
                    var staticCheckbox = document.getElementById("check_StaticIP");
                    var staticFields = document.getElementById("staticFields");
                    staticFields.style.display = staticCheckbox.checked ? "block" : "none";
                }
            </script>
        </head>
        <body>
            <div class="container">
                <h2>SEAL WiFi Configuration</h2>
                <form action="/configure" method="post">
                    <div class="form-group">
                        <label for="ssid">SSID:</label>
                        <input type="text" id="ssid" name="ssid">
                    </div>
                    <div class="form-group">
                        <label for="password">Password:</label>
                        <input type="password" id="password" name="password">
                    </div>
                    <div class="form-group">
                        <label for="key_mgmt">Security Type:</label>
                        <select id="key_mgmt" name="key_mgmt" onchange="toggleEAPfield()">
                            <option value="NONE" selected>None</option>
                            <option value="WPA-PSK">WPA-PSK</option>
                            <option value="WPA-EAP">WPA-EAP</option>
                            <option value="SAE">SAE</option>
                        </select>
                    </div>
                    <div id="idField">
                        <div class="form-group">
                            <label for="identity">Identity (for WPA-EAP only):</label>
                            <input type="text" id="identity" name="identity">
                        </div>
                    </div>
                    <div class="form-group">
                        <label for="staticIP">
                            <input type="checkbox" id="check_StaticIP" name="check_StaticIP" onchange="toggleStaticIP()">
                            Static IP Configuration
                        </label>
                    </div>

                    <div id="staticFields" style="display: none;">
                        <div class="form-group">
                            <label for="static_ip">Static IP Address:</label>
                            <input type="text" id="static_ip" name="static_ip" placeholder="e.g. 192.168.1.100/24">
                    </div>
                    <div class="form-group">
                            <label for="gateway">Gateway:</label>
                            <input type="text" id="gateway" name="gateway" placeholder="e.g. 192.168.1.1">
                    </div>

                    <div class="form-group">
                       <label for="interface_type">Network Interface:</label>
                       <select id="interface_type" name="interface_type">
                           <option value="wifi" selected>Wi-Fi</option>
                           <option value="ethernet">Ethernet</option>
                       </select>
                    </div>

                    <input type="submit" value="Apply Configuration">
                </form>
            </div>
         </body>
         </html>
    '''

@app.route('/configure', methods=['POST'])
def configure():
    ssid = request.form['ssid']
    password = request.form['password']
    key_management = request.form['key_mgmt']
    identity = request.form.get('identity', '')

    country_code = None
    country_name = get_country_from_timezone()
    if country_name:
        country_code = get_country_code_from_name(country_name)

    # Build wpa_supplicant config lines
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
        file.write("\n".join(config_lines))

    use_static_ip = 'check_StaticIP' in request.form

    interface_selection = request.form.get('interface_type')
    selected_interface = None
    if interface_selection == 'wifi':
        selected_interface = 'wlan0'
    else:
        selected_interface = 'eth0'

    user_ip = request.form.get('static_ip')
    user_gateway = request.form.get('gateway')

    if use_static_ip:

        with open('/etc/dhcpcd.conf', 'r') as file:
            original_lines = file.readlines()

        cleaned_lines = []

        for line in original_lines:
            stripped_line = line.strip()
            if stripped_line.startswith("interface wlan0") or stripped_line.startswith("interface eth0"):
                break

            cleaned_lines.append(line)

        if user_ip and user_gateway:
            cleaned_lines += [
                f'interface {selected_interface}',
                f'static ip_address={user_ip}',
                f'static routers={user_gateway}',
                f'static domain_name_servers={user_gateway}',
                ''
            ]
        with open('/etc/dhcpcd.conf', 'w') as file:
            file.write("\n".join(cleaned_lines))

    return "Configuration Applied. Connection now..."

if __name__ == "__main__":
    app.run(debug=True, port=5000)
