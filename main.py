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

# --- הגדרות שרת ---
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

pyautogui.FAILSAFE = False
SERVER_PIN = ''.join(random.choices(string.digits, k=4))
authenticated_users = set()

# --- HTML צד לקוח (כולל השיפור לגרירה) ---
HTML_CLIENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>Pro Remote</title>
    <meta name="apple-mobile-web-app-capable" content="yes">
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
                document.getElementById('msg').style.display = 'block';
            }
        });

        function media(action) {
            if(authenticated) socket.emit('media_control', {action: action});
        }

        // --- Touchpad Logic with Drag Support ---
        const pad = document.getElementById('trackpad');
        let lx=0, ly=0;
        let touch=false;
        let lastTapTime = 0;
        let isDragging = false;

        pad.addEventListener('touchstart', e => { 
            if(!authenticated) return;

            // מניעת גלילה של המסך
            e.preventDefault(); 

            touch=true; 
            lx=e.touches[0].clientX; 
            ly=e.touches[0].clientY; 

            // בדיקת לחיצה כפולה לגרירה
            const currentTime = new Date().getTime();
            const tapLength = currentTime - lastTapTime;

            if (tapLength < 300 && tapLength > 0) {
                // זיהה לחיצה כפולה - מתחיל גרירה
                socket.emit('mouse_down', {});
                isDragging = true;
            }
            lastTapTime = currentTime;

        }, {passive:false});

        pad.addEventListener('touchmove', e => {
            if(!authenticated || !touch) return;
            e.preventDefault(); // חשוב מאוד לגרירה חלקה

            let cx=e.touches[0].clientX;
            let cy=e.touches[0].clientY;

            // שליחת תזוזה (גם אם גוררים וגם אם לא)
            socket.emit('mv', {dx:cx-lx, dy:cy-ly});

            lx=cx; 
            ly=cy;
        }, {passive:false});

        pad.addEventListener('touchend', () => {
            touch=false;
            // אם היינו במצב גרירה - משחררים את העכבר
            if (isDragging) {
                socket.emit('mouse_up', {});
                isDragging = false;
            }
        });

        document.getElementById('l-btn').addEventListener('click', () => { if(authenticated) socket.emit('clk', {b:'left'}); });
        document.getElementById('r-btn').addEventListener('click', () => { if(authenticated) socket.emit('clk', {b:'right'}); });
    </script>
</body>
</html>
"""


# --- נתיבי Flask ---
@app.route('/')
def index(): return render_template_string(HTML_CLIENT)


@socketio.on('auth')
def h_auth(data):
    if data['pin'] == SERVER_PIN:
        authenticated_users.add(request.sid)
        emit('auth_res', {'ok': True})


# --- פונקציות העכבר החדשות ---
@socketio.on('mouse_down')
def handle_mouse_down(data):
    if request.sid in authenticated_users:
        pyautogui.mouseDown(button='left')


@socketio.on('mouse_up')
def handle_mouse_up(data):
    if request.sid in authenticated_users:
        pyautogui.mouseUp(button='left')


@socketio.on('mv')
def h_mv(data):
    if request.sid in authenticated_users:
        try:
            # הגברתי מעט את הרגישות ל-2.0 לנוחות גרירה
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


# --- הרצת השרת ---
def start_flask_server():
    # הוספתי את allow_unsafe_werkzeug כדי למנוע את השגיאה שהייתה לך
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)


def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1));
        ip = s.getsockname()[0]
    except:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


# --- ממשק GUI של המחשב ---
class MouseApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Pro Mouse Server")
        self.root.geometry("450x650")
        self.root.configure(bg="#2c3e50")

        self.ip = get_ip()
        self.url = f"http://{self.ip}:5000"

        # HEADER
        lbl_title = tk.Label(root, text="Pro Mouse Server", font=("Helvetica", 22, "bold"), bg="#2c3e50", fg="white")
        lbl_title.pack(pady=15)

        # PIN DISPLAY
        frame_pin = tk.Frame(root, bg="#34495e", padx=20, pady=10)
        frame_pin.pack(pady=5, fill="x", padx=20)

        tk.Label(frame_pin, text="ACCESS PIN:", font=("Arial", 10), bg="#34495e", fg="#bdc3c7").pack()
        self.lbl_pin = tk.Label(frame_pin, text=SERVER_PIN, font=("Courier", 36, "bold"), bg="#34495e", fg="#e74c3c")
        self.lbl_pin.pack()

        # QR CODE SECTION
        self.qr_frame = tk.Frame(root, bg="#2c3e50")
        self.qr_frame.pack(pady=10)
        self.generate_qr(self.url)

        # MANUAL CONNECT SECTION
        frame_manual = tk.Frame(root, bg="#2c3e50", pady=10)
        frame_manual.pack(fill="x")

        tk.Label(frame_manual, text="--- OR MANUAL CONNECT ---", font=("Arial", 10, "bold"), bg="#2c3e50",
                 fg="#95a5a6").pack()

        self.entry_url = tk.Entry(frame_manual, font=("Arial", 14), justify="center", width=25, bg="#ecf0f1",
                                  fg="#2c3e50")
        self.entry_url.insert(0, self.url)
        self.entry_url.configure(state="readonly")
        self.entry_url.pack(pady=5)

        btn_copy = tk.Button(frame_manual, text="Copy Link", font=("Arial", 10), command=self.copy_to_clipboard,
                             bg="#2980b9", fg="white", relief="flat")
        btn_copy.pack(pady=2)

        # STATUS FOOTER
        self.lbl_status = tk.Label(root, text="Server Running...", font=("Arial", 10), bg="#2c3e50", fg="#f1c40f")
        self.lbl_status.pack(side="bottom", pady=15)

        self.server_thread = threading.Thread(target=start_flask_server, daemon=True)
        self.server_thread.start()

    def generate_qr(self, data):
        qr = qrcode.QRCode(box_size=6, border=2)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill='black', back_color='white')
        self.tk_img = ImageTk.PhotoImage(img)
        lbl_qr = tk.Label(self.qr_frame, image=self.tk_img)
        lbl_qr.pack()

    def copy_to_clipboard(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.url)
        messagebox.showinfo("Copied", "URL copied to clipboard!")


if __name__ == "__main__":
    root = tk.Tk()
    app_gui = MouseApp(root)
    root.mainloop()