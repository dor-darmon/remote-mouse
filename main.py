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
import time
import os

# --- Library Check ---
try:
    import psutil
except ImportError:
    psutil = None

# --- New Library for Internet Access ---
try:
    from pyngrok import ngrok, conf
except ImportError:
    # Fallback/Installation instruction if missing
    print("CRITICAL: Please run 'pip install pyngrok' to use Internet Mode")
    ngrok = None

# --- Server Configuration ---
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret_key'

# --- Critical Fix: Use 'threading' mode ---
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

pyautogui.FAILSAFE = False
SERVER_PIN = ''.join(random.choices(string.digits, k=4))
authenticated_users = set()

# ==========================================
#  PASTE YOUR NGROK TOKEN HERE:
# ==========================================
NGROK_AUTH_TOKEN = ""
# ==========================================

# --- Settings ---
failed_attempts = 0
MAX_ATTEMPTS = 3
MOUSE_SENSITIVITY = 4.0

# --- Client-side HTML (Unchanged) ---
HTML_CLIENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>Pro Remote</title>
    <style>
        body { background-color: #121212; color: #00ffcc; font-family: sans-serif; margin: 0; overflow: hidden; display: flex; flex-direction: column; height: 100vh; transition: background 0.3s; }
        body.presentation-mode { background-color: #0d1b2a; color: #4facfe; }
        body.presentation-mode .m-btn { border-color: #4facfe; color: #4facfe; }
        body.presentation-mode button.login-btn { background: #4facfe; }

        #login-screen { position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: inherit; z-index: 10; display: flex; flex-direction: column; justify-content: center; align-items: center; }
        input.pin-input { padding: 15px; font-size: 24px; text-align: center; border-radius: 10px; border: 2px solid #00ffcc; background: #222; color: white; width: 60%; margin-bottom: 20px; }
        button.login-btn { padding: 15px 40px; font-size: 20px; background: #00ffcc; color: black; border: none; border-radius: 10px; font-weight: bold; }

        #app-interface { display: none; flex-direction: column; height: 100%; position: relative; }
        #top-bar { display: flex; justify-content: space-between; align-items: center; padding: 10px 15px; background: #1a1a1a; border-bottom: 1px solid #333; height: 50px; flex-shrink: 0; }
        #menu-btn { font-size: 24px; cursor: pointer; z-index: 20; padding: 10px;}
        #mode-label { font-weight: bold; font-size: 14px; text-transform: uppercase; }

        #settings-menu { position: absolute; top: 71px; left: 0; width: 100%; background: #1f1f1f; border-bottom: 2px solid #00ffcc; display: none; flex-direction: column; padding: 20px; box-sizing: border-box; z-index: 100; box-shadow: 0 10px 20px rgba(0,0,0,0.5); }
        .setting-row { margin-bottom: 20px; display: flex; flex-direction: column; }
        .setting-label { font-size: 16px; margin-bottom: 10px; color: #fff; border-bottom: 1px solid #333; padding-bottom: 5px; }

        input[type=range] { -webkit-appearance: none; width: 100%; background: transparent; }
        input[type=range]::-webkit-slider-thumb { -webkit-appearance: none; height: 20px; width: 20px; border-radius: 50%; background: #00ffcc; margin-top: -8px; }
        input[type=range]::-webkit-slider-runnable-track { width: 100%; height: 4px; background: #555; border-radius: 2px; }

        .toggle-btn { background: #333; border: 1px solid #555; color: white; padding: 15px; width: 100%; border-radius: 8px; font-size: 16px; cursor: pointer; }
        .toggle-btn.active { background: #4facfe; color: black; border-color: #4facfe; font-weight: bold; }

        .menu-media-row { display: flex; justify-content: space-between; gap: 10px; }
        .menu-media-btn { flex: 1; background: #333; border: 1px solid #555; color: white; padding: 15px; border-radius: 8px; font-size: 20px; cursor: pointer; display: flex; justify-content: center; align-items: center; }
        .menu-media-btn:active { background: #00ffcc; color: black; }

        #trackpad-container { flex-grow: 1; position: relative; display: flex; overflow: hidden; }
        #trackpad { flex-grow: 1; background: radial-gradient(circle, #2a2a2a 0%, #000000 100%); display: flex; justify-content: center; align-items: center; }
        #scroll-strip { width: 50px; background: rgba(255, 255, 255, 0.1); border-left: 1px solid #333; display: flex; flex-direction: column; justify-content: center; align-items: center; }
        #scroll-strip i { opacity: 0.5; margin-bottom: 10px; }
        #mouse-buttons { height: 120px; display: flex; flex-shrink: 0; }
        .m-btn { flex: 1; display: flex; justify-content: center; align-items: center; font-size: 24px; border: 1px solid #333; background: #1a1a1a; color: white; }
        .m-btn:active { background: currentColor; color: black; }
    </style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
</head>
<body>
    <div id="login-screen">
        <h2>Enter PIN</h2>
        <input type="tel" id="pin-input" class="pin-input" maxlength="4" placeholder="****">
        <button class="login-btn" onclick="login()">CONNECT</button>
        <p id="msg" style="color:red; display:none;">Wrong PIN</p>
    </div>

    <div id="app-interface">
        <div id="top-bar">
            <div id="menu-btn" onclick="toggleMenu()"><i class="fas fa-bars"></i></div>
            <div id="mode-label">MOUSE MODE</div>
            <div style="width: 24px;"></div>
        </div>

        <div id="settings-menu">
            <div class="setting-row">
                <div class="setting-label">Media Controls</div>
                <div class="menu-media-row">
                    <button class="menu-media-btn" onclick="media('vol_down')"><i class="fas fa-volume-down"></i></button>
                    <button class="menu-media-btn" onclick="media('playpause')"><i class="fas fa-play"></i></button>
                    <button class="menu-media-btn" onclick="media('vol_up')"><i class="fas fa-volume-up"></i></button>
                </div>
            </div>
            <div class="setting-row">
                <div class="setting-label">Mouse Sensitivity: <span id="sens-val">2.0</span></div>
                <input type="range" min="0.5" max="6.0" step="0.5" value="2.0" oninput="updateSensitivity(this.value)">
            </div>
            <div class="setting-row">
                <button id="ppt-toggle" class="toggle-btn" onclick="togglePresentationMode()">
                    Enable Presentation Mode
                </button>
            </div>
        </div>

        <div id="trackpad-container">
            <div id="trackpad">
                <i id="mode-icon" class="fas fa-fingerprint" style="opacity: 0.2; font-size: 60px;"></i>
            </div>
            <div id="scroll-strip">
                <i class="fas fa-chevron-up"></i>
                <i class="fas fa-arrows-alt-v"></i>
                <i class="fas fa-chevron-down"></i>
            </div>
        </div>

        <div id="mouse-buttons">
            <div class="m-btn" id="l-btn">L</div>
            <div class="m-btn" id="r-btn">R</div>
        </div>
    </div>

    <script>
        const socket = io({transports: ['websocket', 'polling']});
        let authenticated = false;
        let presentationMode = false;

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

        function toggleMenu() {
            const menu = document.getElementById('settings-menu');
            menu.style.display = (menu.style.display === 'flex') ? 'none' : 'flex';
        }

        function updateSensitivity(val) {
            document.getElementById('sens-val').innerText = val;
            if(authenticated) socket.emit('set_sensitivity', {value: val});
        }

        function togglePresentationMode() {
            presentationMode = !presentationMode;
            const body = document.body;
            const label = document.getElementById('mode-label');
            const icon = document.getElementById('mode-icon');
            const lBtn = document.getElementById('l-btn');
            const rBtn = document.getElementById('r-btn');
            const btn = document.getElementById('ppt-toggle');

            if(presentationMode) {
                body.classList.add('presentation-mode');
                label.innerText = "PRESENTATION";
                icon.className = "fas fa-tv";
                lBtn.innerText = "NEXT ➡";
                rBtn.innerText = "⬅ PREV";
                btn.classList.add('active');
                btn.innerText = "Disable Presentation Mode";
            } else {
                body.classList.remove('presentation-mode');
                label.innerText = "MOUSE MODE";
                icon.className = "fas fa-fingerprint";
                lBtn.innerText = "L";
                rBtn.innerText = "R";
                btn.classList.remove('active');
                btn.innerText = "Enable Presentation Mode";
            }
            document.getElementById('settings-menu').style.display = 'none';
        }

        socket.on('disconnect', () => {});
        function media(action) { if(authenticated) socket.emit('media_control', {action: action}); }

        const pad = document.getElementById('trackpad');
        let lx=0, ly=0, touch=false, lastTapTime=0, isDragging=false;

        pad.addEventListener('touchstart', e => { 
            if(!authenticated) return;
            e.preventDefault(); 
            touch=true; 
            lx=e.touches[0].clientX; 
            ly=e.touches[0].clientY; 
            const currentTime = new Date().getTime();
            if (currentTime - lastTapTime < 300 && !presentationMode) {
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

        const scrollStrip = document.getElementById('scroll-strip');
        let sy = 0;
        scrollStrip.addEventListener('touchstart', e => {
            if(!authenticated) return;
            e.preventDefault();
            sy = e.touches[0].clientY;
        }, {passive: false});

        scrollStrip.addEventListener('touchmove', e => {
            if(!authenticated) return;
            e.preventDefault();
            let cy = e.touches[0].clientY;
            let delta = sy - cy; 
            socket.emit('scroll', {dy: delta});
            sy = cy;
        }, {passive: false});

        document.getElementById('l-btn').addEventListener('click', () => { 
            if(!authenticated) return;
            if(presentationMode) socket.emit('ppt_ctrl', {cmd: 'next'});
            else socket.emit('clk', {b:'left'}); 
        });

        document.getElementById('r-btn').addEventListener('click', () => { 
            if(!authenticated) return;
            if(presentationMode) socket.emit('ppt_ctrl', {cmd: 'prev'});
            else socket.emit('clk', {b:'right'}); 
        });
    </script>
</body>
</html>
"""


# --- Server Functions ---
@app.route('/')
def index(): return render_template_string(HTML_CLIENT)


@socketio.on('auth')
def h_auth(data):
    global failed_attempts
    if data['pin'] == SERVER_PIN:
        failed_attempts = 0
        authenticated_users.add(request.sid)
        emit('auth_res', {'ok': True})
    else:
        failed_attempts += 1
        print(f"Failed Login: {failed_attempts}/{MAX_ATTEMPTS}")
        if failed_attempts >= MAX_ATTEMPTS:
            emit('auth_res', {'ok': False, 'msg': 'Server locked'})
            os._exit(0)
        else:
            emit('auth_res', {'ok': False, 'msg': 'Wrong PIN'})


@socketio.on('set_sensitivity')
def h_sens(data):
    global MOUSE_SENSITIVITY
    if request.sid in authenticated_users:
        try:
            val = float(data['value'])
            MOUSE_SENSITIVITY = val
        except:
            pass


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
            dx = float(data['dx']) * MOUSE_SENSITIVITY
            dy = float(data['dy']) * MOUSE_SENSITIVITY
            pyautogui.moveRel(dx, dy)
        except:
            pass


@socketio.on('clk')
def h_clk(data):
    if request.sid in authenticated_users: pyautogui.click(button=data['b'])


@socketio.on('scroll')
def h_scroll(data):
    if request.sid in authenticated_users:
        try:
            amount = int(float(data['dy']) * 2)
            pyautogui.scroll(amount)
        except:
            pass


@socketio.on('ppt_ctrl')
def h_ppt(data):
    if request.sid in authenticated_users:
        cmd = data['cmd']
        if cmd == 'next':
            pyautogui.press('right')
        elif cmd == 'prev':
            pyautogui.press('left')


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


# --- Network & GUI ---
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
                if ip.startswith('192.168.44') or ip.startswith('172.20.10'): return ip
    return None


def start_flask_server():
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)


class MouseApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Pro Mouse Server")
        self.root.geometry("450x700")
        self.root.configure(bg="#2c3e50")

        self.modes = ['wifi', 'bluetooth', 'network']
        self.current_mode = 'wifi'

        # Ngrok setup
        self.active_tunnel = None
        self.url = f"http://{get_local_ip()}:5000"

        tk.Label(root, text="Pro Mouse Server", font=("Helvetica", 22, "bold"), bg="#2c3e50", fg="white").pack(pady=15)

        self.btn_mode = tk.Button(root, text="Mode: WI-FI", font=("Arial", 14, "bold"),
                                  bg="#27ae60", fg="white", width=25, height=2, command=self.cycle_mode)
        self.btn_mode.pack(pady=10)

        frame_pin = tk.Frame(root, bg="#34495e", padx=20, pady=10)
        frame_pin.pack(pady=5, fill="x", padx=20)
        tk.Label(frame_pin, text="ACCESS PIN:", font=("Arial", 10), bg="#34495e", fg="#bdc3c7").pack()
        self.lbl_pin = tk.Label(frame_pin, text=SERVER_PIN, font=("Courier", 36, "bold"), bg="#34495e", fg="#e74c3c")
        self.lbl_pin.pack()

        self.qr_frame = tk.Frame(root, bg="#2c3e50")
        self.qr_frame.pack(pady=10)
        self.lbl_qr = tk.Label(self.qr_frame, bg="#2c3e50")
        self.lbl_qr.pack()

        self.lbl_msg = tk.Label(root, text="Connected to Wi-Fi", font=("Arial", 10), bg="#2c3e50", fg="#f39c12")
        self.lbl_msg.pack()

        frame_manual = tk.Frame(root, bg="#2c3e50", pady=10)
        frame_manual.pack(fill="x")
        self.entry_url = tk.Entry(frame_manual, font=("Arial", 12), justify="center", width=30, bg="#ecf0f1",
                                  fg="#2c3e50")
        self.entry_url.pack(pady=5)
        tk.Button(frame_manual, text="Copy Link", font=("Arial", 10), command=self.copy_to_clipboard, bg="#2980b9",
                  fg="white", relief="flat").pack(pady=2)

        self.lbl_status = tk.Label(root, text="Server Running...", font=("Arial", 10), bg="#2c3e50", fg="#f1c40f")
        self.lbl_status.pack(side="bottom", pady=15)

        self.generate_qr()
        self.update_entry()
        threading.Thread(target=start_flask_server, daemon=True).start()

    def cycle_mode(self):
        next_idx = (self.modes.index(self.current_mode) + 1) % len(self.modes)
        self.set_mode(self.modes[next_idx])

    def close_ngrok(self):
        if self.active_tunnel:
            ngrok.disconnect(self.active_tunnel.public_url)
            self.active_tunnel = None

    def set_mode(self, mode):
        self.current_mode = mode
        # Always close tunnel when switching modes
        self.close_ngrok()

        if mode == 'wifi':
            ip = get_local_ip()
            self.url = f"http://{ip}:5000"
            self.btn_mode.configure(text="Mode: WI-FI", bg="#27ae60")
            self.lbl_msg.configure(text="Local Connection (Same Wi-Fi)", fg="#f39c12")
            self.update_ui()

        elif mode == 'bluetooth':
            self.btn_mode.configure(text="Mode: BLUETOOTH", bg="#2980b9")
            ip = get_bluetooth_ip()
            if ip:
                self.url = f"http://{ip}:5000"
                self.lbl_msg.configure(text="Bluetooth IP Found", fg="#f39c12")
            else:
                self.url = f"http://{get_local_ip()}:5000"
                self.lbl_msg.configure(text="BT Tethering NOT FOUND!", fg="#e74c3c")
            self.update_ui()

        elif mode == 'network':
            self.btn_mode.configure(text="Mode: INTERNET", bg="#8e44ad")
            if not ngrok:
                self.lbl_msg.configure(text="Error: pyngrok missing", fg="red")
                return

            self.lbl_msg.configure(text="Connecting to Cloud...", fg="#f1c40f")
            self.root.update()

            # Start Ngrok Tunnel in a thread to keep UI responsive
            threading.Thread(target=self.start_ngrok_tunnel, daemon=True).start()

    def start_ngrok_tunnel(self):
        try:
            # Set token
            if "YOUR_NGROK_TOKEN_HERE" in NGROK_AUTH_TOKEN:
                self.lbl_msg.configure(text="Error: TOKEN MISSING IN CODE", fg="red")
                return

            ngrok.set_auth_token(NGROK_AUTH_TOKEN)

            # Open HTTP tunnel on port 5000
            self.active_tunnel = ngrok.connect(5000)
            self.url = self.active_tunnel.public_url

            print(f"Ngrok Tunnel Active: {self.url}")
            self.lbl_msg.configure(text="Online! (Internet Mode)", fg="#2ecc71")
            self.update_ui()

        except Exception as e:
            print(f"Ngrok Error: {e}")
            self.lbl_msg.configure(text="Cloud Error (Check Token)", fg="red")

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
            messagebox.showinfo("Copied", "URL copied")


if __name__ == "__main__":
    root = tk.Tk()
    app_gui = MouseApp(root)
    root.mainloop()
