import sys
import socket
import threading
import random
import string
import qrcode
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import pyautogui
from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit
import logging
import subprocess
import shutil
import re
import time
import os  # Added os library to close the process

# --- Library Check ---
try:
    import psutil
except ImportError:
    psutil = None

# --- Server Configuration ---
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

pyautogui.FAILSAFE = False
SERVER_PIN = ''.join(random.choices(string.digits, k=4))
authenticated_users = set()

# --- New Security Settings ---
failed_attempts = 0
MAX_ATTEMPTS = 3  # Maximum allowed attempts

# --- Client-side HTML ---
HTML_CLIENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>Pro Remote</title>
    <style>
        body { background-color: #121212; color: #00ffcc; font-family: sans-serif; margin: 0; overflow: hidden; display: flex; flex-direction: column; height: 100vh; }
        #login-screen { position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: #121212; z-index: 10; display: flex; flex-direction: column; justify-content: center; align-items: center; }
        input { padding: 15px; font-size: 24px; text-align: center; border-radius: 10px; border: 2px solid #00ffcc; background: #222; color: white; width: 60%; margin-bottom: 20px; }
        button.login-btn { padding: 15px 40px; font-size: 20px; background: #00ffcc; color: black; border: none; border-radius: 10px; font-weight: bold; }
        #app-interface { display: none; flex-direction: column; height: 100%; }
        #media-controls { display: flex; justify-content: space-around; padding: 15px; background: #1a1a1a; border-bottom: 1px solid #333; }
        .media-btn { background: #333; color: white; border: none; border-radius: 50%; width: 50px; height: 50px; font-size: 20px; display: flex; justify-content: center; align-items: center; }
        .media-btn:active { background: #00ffcc; color: black; }
        #trackpad { flex-grow: 1; background: radial-gradient(circle, #2a2a2a 0%, #000000 100%); display: flex; justify-content: center; align-items: center; }
        #mouse-buttons { height: 90px; display: flex; }
        .m-btn { flex: 1; display: flex; justify-content: center; align-items: center; font-size: 24px; border: 1px solid #333; background: #1a1a1a; color: white; }
        .m-btn:active { background: #00ffcc; color: black; }
    </style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
</head>
<body>
    <div id="login-screen">
        <h2>Enter PIN</h2>
        <input type="tel" id="pin-input" maxlength="4" placeholder="****">
        <button class="login-btn" onclick="login()">CONNECT</button>
        <p id="msg" style="color:red; display:none;">Wrong PIN</p>
    </div>

    <div id="app-interface">
        <div id="media-controls">
            <button class="media-btn" onclick="media('vol_down')"><i class="fas fa-volume-down"></i></button>
            <button class="media-btn" onclick="media('playpause')"><i class="fas fa-play"></i></button>
            <button class="media-btn" onclick="media('vol_up')"><i class="fas fa-volume-up"></i></button>
        </div>
        <div id="trackpad">
            <i class="fas fa-fingerprint" style="opacity: 0.2; font-size: 60px;"></i>
        </div>
        <div id="mouse-buttons">
            <div class="m-btn" id="l-btn">L</div>
            <div class="m-btn" id="r-btn">R</div>
        </div>
    </div>

    <script>
        const socket = io();
        let authenticated = false;

        function login() {
            const pin = document.getElementById('pin-input').value;
            socket.emit('auth', {pin: pin});
        }

        socket.on('auth_res', (data) => {
            if(data.ok) {
                authenticated = true;
                document.getElementById('login-screen').style.display = 'none';
                document.getElementById('app-interface').style.display = 'flex';
            } else {
                const msgEl = document.getElementById('msg');
                msgEl.innerText = data.msg || "Wrong PIN";
                msgEl.style.display = 'block';
            }
        });

        // Handle server disconnection
        socket.on('disconnect', () => {
             if(authenticated) alert("Server disconnected");
        });

        function media(action) {
            if(authenticated) socket.emit('media_control', {action: action});
        }

        const pad = document.getElementById('trackpad');
        let lx=0, ly=0, touch=false, lastTapTime=0, isDragging=false;

        pad.addEventListener('touchstart', e => { 
            if(!authenticated) return;
            e.preventDefault(); 
            touch=true; 
            lx=e.touches[0].clientX; 
            ly=e.touches[0].clientY; 
            const currentTime = new Date().getTime();
            if (currentTime - lastTapTime < 300) {
                socket.emit('mouse_down', {});
                isDragging = true;
            }
            lastTapTime = currentTime;
        }, {passive:false});

        pad.addEventListener('touchmove', e => {
            if(!authenticated || !touch) return;
            e.preventDefault(); 
            let cx=e.touches[0].clientX, cy=e.touches[0].clientY;
            socket.emit('mv', {dx:cx-lx, dy:cy-ly});
            lx=cx; ly=cy;
        }, {passive:false});

        pad.addEventListener('touchend', () => {
            touch=false;
            if (isDragging) { socket.emit('mouse_up', {}); isDragging = false; }
        });

        document.getElementById('l-btn').addEventListener('click', () => { if(authenticated) socket.emit('clk', {b:'left'}); });
        document.getElementById('r-btn').addEventListener('click', () => { if(authenticated) socket.emit('clk', {b:'right'}); });
    </script>
</body>
</html>
"""


# --- Server Functions ---
@app.route('/')
def index(): return render_template_string(HTML_CLIENT)


# --- Security and Auth Logic (Modified Section) ---
@socketio.on('auth')
def h_auth(data):
    global failed_attempts

    if data['pin'] == SERVER_PIN:
        failed_attempts = 0  # Reset counter on success
        authenticated_users.add(request.sid)
        emit('auth_res', {'ok': True})
    else:
        failed_attempts += 1
        print(f"Failed Login Attempt: {failed_attempts}/{MAX_ATTEMPTS}")

        if failed_attempts >= MAX_ATTEMPTS:
            print("Security Alert: Max attempts reached. Shutting down server.")
            emit('auth_res', {'ok': False, 'msg': 'Server shutting down due to security breach'})
            # Forcefully close the entire process (including GUI)
            os._exit(0)
        else:
            emit('auth_res', {'ok': False, 'msg': f'Wrong PIN ({failed_attempts}/{MAX_ATTEMPTS})'})


@socketio.on('mouse_down')
def handle_mouse_down(data):
    if request.sid in authenticated_users: pyautogui.mouseDown(button='left')


@socketio.on('mouse_up')
def handle_mouse_up(data):
    if request.sid in authenticated_users: pyautogui.mouseUp(button='left')


@socketio.on('mv')
def h_mv(data):
    if request.sid in authenticated_users:
        try:
            pyautogui.moveRel(float(data['dx']) * 2.0, float(data['dy']) * 2.0)
        except:
            pass


@socketio.on('clk')
def h_clk(data):
    if request.sid in authenticated_users: pyautogui.click(button=data['b'])


@socketio.on('media_control')
def h_media(data):
    if request.sid in authenticated_users:
        action = data['action']
        if action == 'vol_up':
            pyautogui.press('volumeup')
        elif action == 'vol_down':
            pyautogui.press('volumedown')
        elif action == 'playpause':
            pyautogui.press('playpause')


# --- Smart Network Logic ---
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


def get_bluetooth_ip():
    if not psutil: return None
    for interface, snics in psutil.net_if_addrs().items():
        for snic in snics:
            if snic.family == socket.AF_INET:
                ip = snic.address
                # Detect Android/iPhone hotspot ranges
                if ip.startswith('192.168.44') or ip.startswith('172.20.10'):
                    return ip
    return None


def start_flask_server():
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)


# --- Graphical User Interface (GUI) ---
class MouseApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Pro Mouse Server")
        self.root.geometry("450x700")
        self.root.configure(bg="#2c3e50")

        self.modes = ['wifi', 'bluetooth', 'network']
        self.current_mode = 'wifi'
        self.ssh_process = None
        self.url = f"http://{get_local_ip()}:5000"

        # HEADER
        lbl_title = tk.Label(root, text="Pro Mouse Server", font=("Helvetica", 22, "bold"), bg="#2c3e50", fg="white")
        lbl_title.pack(pady=15)

        # BUTTON: TOGGLE MODE
        self.btn_mode = tk.Button(root, text="Mode: WI-FI", font=("Arial", 14, "bold"),
                                  bg="#27ae60", fg="white", width=25, height=2, command=self.cycle_mode)
        self.btn_mode.pack(pady=10)

        # PIN DISPLAY
        frame_pin = tk.Frame(root, bg="#34495e", padx=20, pady=10)
        frame_pin.pack(pady=5, fill="x", padx=20)
        tk.Label(frame_pin, text="ACCESS PIN:", font=("Arial", 10), bg="#34495e", fg="#bdc3c7").pack()
        self.lbl_pin = tk.Label(frame_pin, text=SERVER_PIN, font=("Courier", 36, "bold"), bg="#34495e", fg="#e74c3c")
        self.lbl_pin.pack()

        # QR CODE SECTION
        self.qr_frame = tk.Frame(root, bg="#2c3e50")
        self.qr_frame.pack(pady=10)
        self.lbl_qr = tk.Label(self.qr_frame, bg="#2c3e50")
        self.lbl_qr.pack()

        # STATUS MESSAGE
        self.lbl_msg = tk.Label(root, text="Connected to Wi-Fi", font=("Arial", 10), bg="#2c3e50", fg="#f39c12")
        self.lbl_msg.pack()

        # MANUAL CONNECT
        frame_manual = tk.Frame(root, bg="#2c3e50", pady=10)
        frame_manual.pack(fill="x")
        self.entry_url = tk.Entry(frame_manual, font=("Arial", 12), justify="center", width=30, bg="#ecf0f1",
                                  fg="#2c3e50")
        self.entry_url.pack(pady=5)

        btn_copy = tk.Button(frame_manual, text="Copy Link", font=("Arial", 10), command=self.copy_to_clipboard,
                             bg="#2980b9", fg="white", relief="flat")
        btn_copy.pack(pady=2)

        self.lbl_status = tk.Label(root, text="Server Running...", font=("Arial", 10), bg="#2c3e50", fg="#f1c40f")
        self.lbl_status.pack(side="bottom", pady=15)

        self.generate_qr()
        self.update_entry()

        self.server_thread = threading.Thread(target=start_flask_server, daemon=True)
        self.server_thread.start()

    def cycle_mode(self):
        next_idx = (self.modes.index(self.current_mode) + 1) % len(self.modes)
        new_mode = self.modes[next_idx]
        self.set_mode(new_mode)

    def set_mode(self, mode):
        self.current_mode = mode

        # Close process if exists
        if self.ssh_process:
            self.ssh_process.terminate()
            self.ssh_process = None

        if mode == 'wifi':
            ip = get_local_ip()
            self.url = f"http://{ip}:5000"
            self.btn_mode.configure(text="Mode: WI-FI", bg="#27ae60")
            self.lbl_msg.configure(text="Standard local connection", fg="#f39c12")
            self.update_ui()

        elif mode == 'bluetooth':
            self.btn_mode.configure(text="Mode: BLUETOOTH", bg="#2980b9")
            ip = get_bluetooth_ip()
            if ip:
                self.url = f"http://{ip}:5000"
                self.lbl_msg.configure(text="Bluetooth IP Found", fg="#f39c12")
            else:
                current_ip = get_local_ip()
                self.url = f"http://{current_ip}:5000"
                self.lbl_msg.configure(text="BT Tethering NOT FOUND! (Using WiFi IP)", fg="#e74c3c")
            self.update_ui()

        elif mode == 'network':
            self.btn_mode.configure(text="Mode: INTERNET", bg="#8e44ad")

            if not shutil.which("ssh"):
                self.lbl_msg.configure(text="Error: OpenSSH missing in Windows", fg="red")
                return

            self.lbl_msg.configure(text="Running SSH Command... Wait...", fg="#f1c40f")
            self.root.update()

            threading.Thread(target=self.start_ssh_tunnel, daemon=True).start()

    def start_ssh_tunnel(self):
        try:
            # The exact command requested
            cmd = ["ssh", "-p", "443", "-R0:localhost:5000", "a.pinggy.io", "-o", "StrictHostKeyChecking=no"]

            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            # Combine STDOUT and STDERR to capture everything
            self.ssh_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Important - merges errors and standard output
                text=True,
                startupinfo=startupinfo,
                bufsize=1,  # Line buffered
                universal_newlines=True
            )

            print("SSH Command Executed. Listening for URL...")

            # Regex to catch any HTTP/HTTPS URL containing pinggy
            url_pattern = re.compile(r'(https?://[a-zA-Z0-9.-]+\.pinggy\.(?:io|link))')

            # Read output in real-time
            while True:
                line = self.ssh_process.stdout.readline()
                if not line:
                    break

                print(f"SSH Output: {line.strip()}")  # Debug print

                match = url_pattern.search(line)
                if match:
                    found_url = match.group(1)
                    # Ensure HTTPS
                    if "http://" in found_url:
                        found_url = found_url.replace("http://", "https://")

                    self.url = found_url
                    self.lbl_msg.configure(text="Online! (Pinggy)", fg="#2ecc71")
                    self.update_ui()
                    break  # Stop searching once found

        except Exception as e:
            print(f"SSH Error: {e}")
            self.lbl_msg.configure(text=f"SSH Error", fg="red")

    def update_ui(self):
        self.root.after(0, self.generate_qr)
        self.root.after(0, self.update_entry)

    def update_entry(self):
        self.entry_url.configure(state="normal")
        self.entry_url.delete(0, tk.END)
        self.entry_url.insert(0, self.url)
        self.entry_url.configure(state="readonly")

    def generate_qr(self):
        qr = qrcode.QRCode(box_size=6, border=2)
        qr.add_data(self.url)
        qr.make(fit=True)
        img = qr.make_image(fill='black', back_color='white')
        self.tk_img = ImageTk.PhotoImage(img)
        self.lbl_qr.configure(image=self.tk_img)

    def copy_to_clipboard(self):
        if self.url:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.url)
            messagebox.showinfo("Copied", "URL copied to clipboard!")


if __name__ == "__main__":
    root = tk.Tk()
    app_gui = MouseApp(root)
    root.mainloop()