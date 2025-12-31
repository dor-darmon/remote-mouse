#  Pro Mouse Server - Remote Control for PC

**Pro Mouse Server** is a Python-based application that turns your smartphone into a powerful remote mouse and keyboard controller for your computer. It uses a secure SocketIO connection to provide low-latency control over WiFi.

##  Features
* **Touchpad:** Control mouse movement seamlessly from your phone screen.
* **Tap-to-Click:** Tap once for Left Click.
* **Drag & Drop:** Double-tap and hold to drag windows and icons.
* **Media Controls:** Play/Pause and Volume control.
* **Secure Connection:** Random PIN generation for secure access.
* **QR Code Pairing:** Scan and connect instantly without typing IP addresses.

##  Built With
* **Python 3.13**
* **Flask & Flask-SocketIO** (Server & Communication)
* **PyAutoGUI** (Mouse/Keyboard Automation)
* **Tkinter** (Desktop GUI)
* **Pillow & Qrcode** (Image processing)

---

##  How to Run (Installation)

### Option A: Run from Source
1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/YOUR_USERNAME/ProMouseServer.git](https://github.com/YOUR_USERNAME/ProMouseServer.git)
    cd ProMouseServer
    ```
2.  **Install dependencies:**
    ```bash
    pip install Flask Flask-SocketIO PyAutoGUI Pillow qrcode[pil]
    ```
3.  **Run the application:**
    ```bash
    python main.py
    ```

### Option B: Run via EXE (Windows)
1.  Download the `ProMouseServer.exe` from the Releases section.
2.  Run the file (Allow access in Windows Firewall if prompted).
3.  Scan the QR code with your phone.

---

##  Usage
1.  Launch the application on your PC.
2.  Ensure both PC and Phone are on the **same WiFi network**.
3.  Scan the QR code displayed on the desktop app.
4.  Enter the 4-digit PIN shown on the screen.
5.  **Controls:**
    * **Move:** Slide finger on trackpad.
    * **Left Click:** Tap buttons or double-tap trackpad.
    * **Drag:** Double-tap and hold, then move finger.

##  License
This project is open-source and available under the MIT License.
