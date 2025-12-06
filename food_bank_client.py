"""
I-70 Street Reach Food Bank - Network Client GUI
Connects to food_bank_server.py for multi-user database access
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import requests
import json
import subprocess
import socket
import os
from csv import writer as csv_writer
import traceback

try:
    import keyring
except Exception:
    keyring = None

try:
    import openpyxl
except Exception:
    openpyxl = None

class FoodBankClientGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("I-70 Street Reach Food Bank - Client Entry Form (Network)")
        self.root.geometry("900x900")
        self.root.resizable(True, True)
        
        # Set minimum window size
        self.root.minsize(800, 600)
        
        # Server configuration
        self.server_url = "http://localhost:5000"  # Change to server IP/hostname
        self.session = requests.Session()  # Use session for cookies
        self.authenticated = False
        self.current_user = None
        
        # Try to load server URL from config file
        self.load_config()

        # Track whether we're editing an existing record (ClientID) or creating new
        self.editing_id = None

        # Attempt automatic sign-in using default credentials to reduce prompts.
        # If automatic auth fails, fall back to showing the authentication dialog.
        try:
            if not self.try_auto_login():
                self.setup_authentication()
        except Exception:
            # On any unexpected error, fall back to interactive auth
            self.setup_authentication()

    def try_auto_login(self):
        """Attempt to authenticate automatically using default credentials.
        Returns True on success (and initializes GUI), False otherwise.
        """
        config_path = os.path.join(os.path.dirname(__file__), 'server_config.txt')
        # ensure server_url is up-to-date from config file
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    self.server_url = f.read().strip() or self.server_url
            except:
                pass

        default_user = 'admin'
        default_pass = 'foodbank2024'

        try:
            response = self.session.post(
                f"{self.server_url}/api/login",
                json={'username': default_user, 'password': default_pass},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                self.current_user = data.get('user', {})
                self.authenticated = True
                # Save server URL to config for future runs
                try:
                    with open(config_path, 'w') as f:
                        f.write(self.server_url)
                except:
                    pass
                # Initialize the main GUI
                self.setup_gui()
                return True
        except requests.exceptions.RequestException:
            return False
        except Exception:
            return False
        return False

    def attempt_remote_start(self, host, admin_user, admin_pass):
        """Attempt to run the scheduled task remotely using schtasks.
        Returns True if the command was issued successfully, False otherwise.
        """
        # Use schtasks to run the named task on the remote host
        task_name = "I70StreetReach_FoodBank_Server"
        # Construct schtasks command: schtasks /Run /S <host> /U <user> /P <pass> /TN <task>
        cmd = [
            'schtasks', '/Run', '/S', host, '/U', admin_user, '/P', admin_pass, '/TN', task_name
        ]
        try:
            # Run the command and capture output
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if proc.returncode == 0:
                messagebox.showinfo("Server Start", "Remote start command issued successfully. Waiting a moment and retrying connection...")
                # Wait a short moment then try authenticating again
                self.root.after(3000, lambda: self.setup_authentication())
                return True
            else:
                messagebox.showerror("Remote Start Failed", f"Failed to start server remotely:\n{proc.stdout}\n{proc.stderr}")
                return False
        except FileNotFoundError:
            messagebox.showerror("Error", "Unable to find 'schtasks' command. This feature is only supported on Windows.")
            return False

    # ------------------------- Credential & WOL helpers -------------------------
    def _settings_path(self):
        return os.path.join(os.path.dirname(__file__), 'client_settings.json')

    def load_client_settings(self):
        path = self._settings_path()
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def save_client_settings(self, settings):
        path = self._settings_path()
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(settings, f)
        except Exception:
            pass

    def send_wol(self, mac, broadcast='<broadcast>', port=9):
        """Send Wake-on-LAN magic packet to MAC address."""
        try:
            mac_bytes = bytes.fromhex(mac.replace(':', '').replace('-', ''))
            if len(mac_bytes) != 6:
                raise ValueError('Invalid MAC address')
            packet = b'\xff' * 6 + mac_bytes * 16
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(packet, (broadcast, port))
            sock.close()
            return True
        except Exception as e:
            messagebox.showerror('WOL Error', f'Failed to send Wake-on-LAN packet: {e}')
            return False

    def save_admin_credentials(self, host, admin_user, admin_pass):
        if keyring is None:
            return False
        try:
            service = 'I70StreetReach_FoodBank_Admin'
            key = f"{host}|{admin_user}"
            keyring.set_password(service, key, admin_pass)
            return True
        except Exception:
            return False

    def get_saved_admin_credentials(self, host, admin_user='admin'):
        if keyring is None:
            return None
        try:
            service = 'I70StreetReach_FoodBank_Admin'
            key = f"{host}|{admin_user}"
            pwd = keyring.get_password(service, key)
            if pwd:
                return (admin_user, pwd)
        except Exception:
            return None
        return None
    
    def load_config(self):
        """Load server URL from config file if it exists"""
        config_path = os.path.join(os.path.dirname(__file__), 'server_config.txt')
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    self.server_url = f.read().strip()
            except:
                pass
    
    def setup_authentication(self):
        """Show authentication dialog"""
        auth_window = tk.Toplevel(self.root)
        auth_window.title("Network Database Authentication")
        auth_window.geometry("420x360")
        auth_window.resizable(False, False)
        auth_window.transient(self.root)
        auth_window.grab_set()
        
        # Title
        ttk.Label(auth_window, text="Connect to Food Bank Database", font=("Arial", 12, "bold")).pack(pady=20)
        
        # Server URL
        ttk.Label(auth_window, text="Server Address:").pack(anchor=tk.W, padx=20, pady=(10, 0))
        server_entry = ttk.Entry(auth_window, width=50)
        server_entry.insert(0, self.server_url)
        server_entry.pack(padx=20, pady=5)
        
        # Username
        ttk.Label(auth_window, text="Username:").pack(anchor=tk.W, padx=20, pady=(10, 0))
        username_entry = ttk.Entry(auth_window, width=50)
        username_entry.pack(padx=20, pady=5)
        
        # Password
        ttk.Label(auth_window, text="Password:").pack(anchor=tk.W, padx=20, pady=(10, 0))
        password_entry = ttk.Entry(auth_window, width=50, show="*")
        password_entry.pack(padx=20, pady=5)
        
        def authenticate():
            self.server_url = server_entry.get()
            username = username_entry.get()
            password = password_entry.get()
            
            try:
                # Test connection
                response = self.session.post(
                    f"{self.server_url}/api/login",
                    json={'username': username, 'password': password},
                    timeout=5
                )
                
                if response.status_code == 200:
                    data = response.json()
                    self.current_user = data.get('user', {})
                    self.authenticated = True
                    
                    # Save server URL to config
                    config_path = os.path.join(os.path.dirname(__file__), 'server_config.txt')
                    with open(config_path, 'w') as f:
                        f.write(self.server_url)
                    
                    auth_window.destroy()
                    self.setup_gui()
                else:
                    messagebox.showerror("Authentication Failed", "Invalid username or password")
            except requests.exceptions.ConnectionError:
                messagebox.showerror("Connection Error", f"Cannot connect to server at {self.server_url}")
            except Exception as e:
                messagebox.showerror("Error", f"Authentication error: {str(e)}")

        # Start Server dialog: prompt for admin creds, optional Save, optional WOL
        def open_start_server_dialog():
            host = server_entry.get().split('//')[-1].split(':')[0]

            # Try to pre-fill saved admin credentials (if keyring available)
            saved = self.get_saved_admin_credentials(host)
            cred_win = tk.Toplevel(auth_window)
            cred_win.title("Server Admin Credentials")
            cred_win.geometry("420x240")
            cred_win.transient(auth_window)
            cred_win.grab_set()

            ttk.Label(cred_win, text="Admin Username:").pack(anchor=tk.W, padx=20, pady=(10,0))
            admin_user = ttk.Entry(cred_win, width=40)
            admin_user.pack(padx=20, pady=5)
            if saved:
                admin_user.insert(0, saved[0])
            else:
                admin_user.insert(0, 'admin')

            ttk.Label(cred_win, text="Admin Password:").pack(anchor=tk.W, padx=20, pady=(10,0))
            admin_pass = ttk.Entry(cred_win, width=40, show='*')
            admin_pass.pack(padx=20, pady=5)
            if saved:
                admin_pass.insert(0, saved[1])

            settings = self.load_client_settings()
            mac_pref = settings.get('server_mac', '')

            ttk.Label(cred_win, text="Server MAC (optional, used for Wake-on-LAN):").pack(anchor=tk.W, padx=20, pady=(10,0))
            mac_entry = ttk.Entry(cred_win, width=40)
            mac_entry.pack(padx=20, pady=5)
            if mac_pref:
                mac_entry.insert(0, mac_pref)

            save_var = tk.BooleanVar()
            ttk.Checkbutton(cred_win, text="Save admin credentials (Windows Credential Manager)", variable=save_var).pack(anchor=tk.W, padx=20, pady=5)
            save_mac_var = tk.BooleanVar()
            ttk.Checkbutton(cred_win, text="Remember MAC for this client", variable=save_mac_var).pack(anchor=tk.W, padx=20, pady=2)

            def run_start():
                auser = admin_user.get().strip()
                apass = admin_pass.get().strip()
                mac = mac_entry.get().strip()
                cred_win.destroy()

                # Optionally send WOL first
                if mac:
                    self.send_wol(mac)

                # Attempt remote scheduled task run
                ok = self.attempt_remote_start(host, auser, apass)
                if ok and save_var.get():
                    self.save_admin_credentials(host, auser, apass)
                if save_mac_var.get() and mac:
                    settings['server_mac'] = mac
                    self.save_client_settings(settings)

            ttk.Button(cred_win, text="Start Server", command=run_start).pack(pady=10)

        def open_wake_dialog():
            settings = self.load_client_settings()
            mac_pref = settings.get('server_mac', '')
            wake_win = tk.Toplevel(auth_window)
            wake_win.title('Wake Server (Wake-on-LAN)')
            wake_win.geometry('420x160')
            wake_win.transient(auth_window)
            wake_win.grab_set()

            ttk.Label(wake_win, text='Server MAC Address:').pack(anchor=tk.W, padx=20, pady=(10,0))
            mac_entry = ttk.Entry(wake_win, width=40)
            mac_entry.pack(padx=20, pady=5)
            if mac_pref:
                mac_entry.insert(0, mac_pref)

            save_mac = tk.BooleanVar()
            ttk.Checkbutton(wake_win, text='Remember MAC for this client', variable=save_mac).pack(anchor=tk.W, padx=20, pady=2)

            def run_wake():
                mac = mac_entry.get().strip()
                wake_win.destroy()
                if not mac:
                    messagebox.showinfo('WOL', 'Please enter a MAC address')
                    return
                ok = self.send_wol(mac)
                if ok and save_mac.get():
                    settings['server_mac'] = mac
                    self.save_client_settings(settings)

            ttk.Button(wake_win, text='Send Wake', command=run_wake).pack(pady=8)

        # Buttons: Start Server, Wake Server, Connect
        btn_frame = ttk.Frame(auth_window)
        btn_frame.pack(side=tk.BOTTOM, pady=12)
        ttk.Button(btn_frame, text='Start Server (Admin)', command=open_start_server_dialog).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text='Wake Server', command=open_wake_dialog).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text='Connect', command=authenticate).pack(side=tk.LEFT, padx=6)
        auth_window.bind('<Return>', lambda e: authenticate())
        
        # Make window modal and center it
        auth_window.update_idletasks()
        x = (auth_window.winfo_screenwidth() // 2) - (auth_window.winfo_width() // 2)
        y = (auth_window.winfo_screenheight() // 2) - (auth_window.winfo_height() // 2)
        auth_window.geometry(f"+{x}+{y}")
    
    def setup_gui(self):
        """Setup main GUI after authentication"""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="I-70 Street Reach Food Bank - Client Information Form (Network)", 
                               font=("Arial", 14, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=10)
        
        # Create scrollable frame
        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Bind mouse wheel scrolling to canvas
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        canvas.bind("<MouseWheel>", _on_mousewheel)
        scrollable_frame.bind("<MouseWheel>", _on_mousewheel)
        
        # Dictionary to store entry widgets
        self.entries = {}
        
        # Row counter for form
        row = 0
        
        # Date (editable, defaults to today)
        ttk.Label(scrollable_frame, text="Date (MM-DD-YYYY):", font=("Arial", 10, "bold")).grid(row=row, column=0, sticky=tk.W, pady=5)
        self.entries['VisitDate'] = ttk.Entry(scrollable_frame, width=30)
        self.entries['VisitDate'].insert(0, datetime.now().strftime("%m-%d-%Y"))
        self.entries['VisitDate'].grid(row=row, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        # ID/Driver's License Number
        ttk.Label(scrollable_frame, text="ID/Driver's License Number:", font=("Arial", 10)).grid(row=row, column=0, sticky=tk.W, pady=5)
        self.entries['DriverLicenseNumber'] = ttk.Entry(scrollable_frame, width=30)
        self.entries['DriverLicenseNumber'].grid(row=row, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        # First Name, Middle Initial, Last Name
        ttk.Label(scrollable_frame, text="First Name:", font=("Arial", 10)).grid(row=row, column=0, sticky=tk.W, pady=5)
        self.entries['FirstName'] = ttk.Entry(scrollable_frame, width=25)
        self.entries['FirstName'].grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(scrollable_frame, text="Middle Initial:", font=("Arial", 10)).grid(row=row, column=1, sticky=tk.E, padx=(5, 0))
        self.entries['MiddleInitial'] = ttk.Entry(scrollable_frame, width=3)
        self.entries['MiddleInitial'].grid(row=row, column=2, sticky=tk.W, pady=5, padx=(0, 5))
        row += 1
        
        ttk.Label(scrollable_frame, text="Last Name:", font=("Arial", 10)).grid(row=row, column=0, sticky=tk.W, pady=5)
        self.entries['LastName'] = ttk.Entry(scrollable_frame, width=30)
        self.entries['LastName'].grid(row=row, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        # Address Info
        ttk.Label(scrollable_frame, text="Physical Address:", font=("Arial", 10)).grid(row=row, column=0, sticky=tk.W, pady=5)
        self.entries['PhysicalAddress'] = ttk.Entry(scrollable_frame, width=30)
        self.entries['PhysicalAddress'].grid(row=row, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        ttk.Label(scrollable_frame, text="City:", font=("Arial", 10)).grid(row=row, column=0, sticky=tk.W, pady=5)
        self.entries['City'] = ttk.Entry(scrollable_frame, width=15)
        self.entries['City'].grid(row=row, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(scrollable_frame, text="State:", font=("Arial", 10)).grid(row=row, column=1, sticky=tk.E, padx=(5, 0))
        states = ['AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA', 
                  'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
                  'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
                  'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
                  'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY']
        self.entries['State'] = ttk.Combobox(scrollable_frame, values=states, width=3, state='readonly')
        self.entries['State'].grid(row=row, column=2, sticky=tk.W, pady=5, padx=(0, 5))
        row += 1
        
        ttk.Label(scrollable_frame, text="Zip Code:", font=("Arial", 10)).grid(row=row, column=0, sticky=tk.W, pady=5)
        self.entries['ZipCode'] = ttk.Entry(scrollable_frame, width=15)
        self.entries['ZipCode'].grid(row=row, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(scrollable_frame, text="County:", font=("Arial", 10)).grid(row=row, column=1, sticky=tk.E, padx=(5, 0))
        self.entries['County'] = ttk.Entry(scrollable_frame, width=15)
        self.entries['County'].grid(row=row, column=2, sticky=(tk.W, tk.E), pady=5, padx=(0, 5))
        row += 1
        
        # Contact Info
        ttk.Label(scrollable_frame, text="Cell Phone:", font=("Arial", 10)).grid(row=row, column=0, sticky=tk.W, pady=5)
        self.entries['CellPhone'] = ttk.Entry(scrollable_frame, width=30)
        self.entries['CellPhone'].grid(row=row, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        ttk.Label(scrollable_frame, text="Email:", font=("Arial", 10)).grid(row=row, column=0, sticky=tk.W, pady=5)
        self.entries['Email'] = ttk.Entry(scrollable_frame, width=30)
        self.entries['Email'].grid(row=row, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        # Date of Birth
        ttk.Label(scrollable_frame, text="Date of Birth (MM-DD-YYYY):", font=("Arial", 10)).grid(row=row, column=0, sticky=tk.W, pady=5)
        self.entries['DateOfBirth'] = ttk.Entry(scrollable_frame, width=30)
        self.entries['DateOfBirth'].grid(row=row, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        # Language Spoken
        ttk.Label(scrollable_frame, text="Language Spoken:", font=("Arial", 10)).grid(row=row, column=0, sticky=tk.W, pady=5)
        self.entries['LanguageSpoken'] = ttk.Entry(scrollable_frame, width=30)
        self.entries['LanguageSpoken'].grid(row=row, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        # Marital Status
        ttk.Label(scrollable_frame, text="Marital Status:", font=("Arial", 10, "bold")).grid(row=row, column=0, sticky=tk.W, pady=5)
        row += 1
        
        marital_frame = ttk.Frame(scrollable_frame)
        marital_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=5)
        
        self.marital_status = tk.StringVar()
        for status in ['Married', 'Divorced', 'Widowed', 'Single']:
            ttk.Radiobutton(marital_frame, text=status, variable=self.marital_status, value=status).pack(side=tk.LEFT, padx=5)
        row += 1
        
        # Nationality/Race
        ttk.Label(scrollable_frame, text="Nationality/Race:", font=("Arial", 10, "bold")).grid(row=row, column=0, sticky=tk.W, pady=5)
        row += 1
        
        race_frame = ttk.Frame(scrollable_frame)
        race_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=5)
        
        self.race_vars = {}
        for race in ['Hispanic', 'African American', 'American Indian', 'Asian', 'White', 'Other']:
            self.race_vars[race] = tk.BooleanVar()
            ttk.Checkbutton(race_frame, text=race, variable=self.race_vars[race]).pack(side=tk.LEFT, padx=5)
        row += 1
        
        # Certification Status
        ttk.Label(scrollable_frame, text="Certification Status:", font=("Arial", 10, "bold")).grid(row=row, column=0, sticky=tk.W, pady=5)
        row += 1
        
        cert_frame = ttk.Frame(scrollable_frame)
        cert_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=5)
        
        self.cert_vars = {}
        for cert in ['Homeless', 'Disabled', 'Unemployed', 'Food Stamps', 'None of the Above']:
            self.cert_vars[cert] = tk.BooleanVar()
            ttk.Checkbutton(cert_frame, text=cert, variable=self.cert_vars[cert]).pack(side=tk.LEFT, padx=5)
        row += 1
        
        # Veteran Status
        ttk.Label(scrollable_frame, text="Veteran Status:", font=("Arial", 10)).grid(row=row, column=0, sticky=tk.W, pady=5)
        row += 1
        
        veteran_frame = ttk.Frame(scrollable_frame)
        veteran_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=5)
        
        self.veteran_status = tk.StringVar()
        ttk.Radiobutton(veteran_frame, text="Yes", variable=self.veteran_status, value="Yes").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(veteran_frame, text="No", variable=self.veteran_status, value="No").pack(side=tk.LEFT, padx=5)
        row += 1
        
        # How did you hear about us
        ttk.Label(scrollable_frame, text="How Did You Hear About Us?:", font=("Arial", 10, "bold")).grid(row=row, column=0, sticky=tk.W, pady=5)
        row += 1
        
        heard_frame = ttk.Frame(scrollable_frame)
        heard_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=5)
        
        self.heard_vars = {}
        for source in ['Church', 'Social Media/Website', 'Friend/Family', 'Other']:
            self.heard_vars[source] = tk.BooleanVar()
            ttk.Checkbutton(heard_frame, text=source, variable=self.heard_vars[source]).pack(side=tk.LEFT, padx=5)
        row += 1
        
        # Household Total
        ttk.Label(scrollable_frame, text="Household Total:", font=("Arial", 10)).grid(row=row, column=0, sticky=tk.W, pady=5)
        self.entries['HouseholdTotal'] = ttk.Entry(scrollable_frame, width=30)
        self.entries['HouseholdTotal'].grid(row=row, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        # Notes Section
        ttk.Label(scrollable_frame, text="Notes:", font=("Arial", 10, "bold")).grid(row=row, column=0, sticky=tk.W, pady=5)
        row += 1
        
        self.entries['Notes'] = tk.Text(scrollable_frame, height=5, width=60)
        self.entries['Notes'].grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        # Make Tab key skip to next field instead of inserting tabs
        self.entries['Notes'].bind('<Tab>', lambda e: e.widget.tk_focusNext().focus() or 'break')
        self.entries['Notes'].bind('<Shift-Tab>', lambda e: e.widget.tk_focusPrev().focus() or 'break')
        row += 1
        
        # Buttons
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.grid(row=row, column=0, columnspan=3, pady=20, sticky=(tk.W, tk.E))
        
        self.save_button = ttk.Button(button_frame, text="Save", command=self.save_data)
        self.save_button.pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear", command=self.clear_form).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="View Records", command=self.view_records).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Generate Report", command=self.generate_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Search", command=self.open_search_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Import CSV", command=self.import_csv).pack(side=tk.LEFT, padx=5)
        self.cancel_edit_button = ttk.Button(button_frame, text="Cancel Edit", command=self.cancel_edit)
        self.cancel_edit_button.pack(side=tk.LEFT, padx=5)
        self.cancel_edit_button.config(state='disabled')
        
        # Add canvas and scrollbar to main frame
        canvas.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        scrollbar.grid(row=1, column=3, sticky=(tk.N, tk.S))
        
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
    
    def get_headers(self):
        """Get authorization headers (session-based auth doesn't need explicit headers)"""
        return {}
    
    def save_data(self):
        """Save form data to server"""
        try:
            # Collect races
            races = [race for race, var in self.race_vars.items() if var.get()]
            nationality_race = ', '.join(races) if races else ''
            
            # Collect certifications
            certs = [cert for cert, var in self.cert_vars.items() if var.get()]
            certification_status = ', '.join(certs) if certs else ''
            
            # Collect heard about us
            heard = [source for source, var in self.heard_vars.items() if var.get()]
            how_heard = ', '.join(heard) if heard else ''
            
            # Validate required fields
            if not self.entries['FirstName'].get() or not self.entries['LastName'].get():
                messagebox.showerror("Error", "First Name and Last Name are required!")
                return
            
            # Prepare data
            data = {
                'VisitDate': self.entries['VisitDate'].get(),
                'DriverLicenseNumber': self.entries['DriverLicenseNumber'].get(),
                'FirstName': self.entries['FirstName'].get(),
                'MiddleInitial': self.entries['MiddleInitial'].get(),
                'LastName': self.entries['LastName'].get(),
                'PhysicalAddress': self.entries['PhysicalAddress'].get(),
                'City': self.entries['City'].get(),
                'State': self.entries['State'].get(),
                'ZipCode': self.entries['ZipCode'].get(),
                'County': self.entries['County'].get(),
                'CellPhone': self.entries['CellPhone'].get(),
                'Email': self.entries['Email'].get(),
                'DateOfBirth': self.entries['DateOfBirth'].get(),
                'LanguageSpoken': self.entries['LanguageSpoken'].get(),
                'MaritalStatus': self.marital_status.get(),
                'Nationality_Race': nationality_race,
                'CertificationStatus': certification_status,
                'IsVeteran': self.veteran_status.get(),
                'HowHeardAboutUs': how_heard,
                'HouseholdTotal': self.entries['HouseholdTotal'].get() if self.entries['HouseholdTotal'].get() else None,
                'Notes': self.entries['Notes'].get('1.0', tk.END).strip()
            }
            
            # Send to server: create new or update existing
            if self.editing_id:
                # Update existing record
                resp = self.session.put(
                    f"{self.server_url}/api/clients/{self.editing_id}",
                    json=data,
                    headers=self.get_headers(),
                    timeout=10
                )
                if resp.status_code == 200:
                    messagebox.showinfo("Success", "Client record updated successfully!")
                    # reset editing state
                    self.editing_id = None
                    self.save_button.config(text='Save')
                    self.cancel_edit_button.config(state='disabled')
                    self.clear_form()
                else:
                    messagebox.showerror("Error", f"Failed to update record: {resp.json().get('error','Unknown')}")
            else:
                response = self.session.post(
                    f"{self.server_url}/api/clients",
                    json=data,
                    headers=self.get_headers(),
                    timeout=10
                )
                if response.status_code == 201:
                    messagebox.showinfo("Success", "Client record saved successfully!")
                    self.clear_form()
                else:
                    error_msg = response.json().get('error', 'Unknown error')
                    messagebox.showerror("Error", f"Failed to save record: {error_msg}")
        
        except requests.exceptions.Timeout:
            messagebox.showerror("Error", "Server connection timeout")
        except requests.exceptions.ConnectionError:
            messagebox.showerror("Error", f"Cannot connect to server at {self.server_url}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save record: {str(e)}")
    
    def clear_form(self):
        """Clear all form fields"""
        for entry in self.entries.values():
            if isinstance(entry, tk.Text):
                entry.delete('1.0', tk.END)
            else:
                entry.delete(0, tk.END)
        
        self.entries['VisitDate'].insert(0, datetime.now().strftime("%m-%d-%Y"))
        
        self.marital_status.set('')
        self.veteran_status.set('')
        
        for var in self.race_vars.values():
            var.set(False)
        for var in self.cert_vars.values():
            var.set(False)
        for var in self.heard_vars.values():
            var.set(False)

        # If we were editing, cancel edit mode
        if getattr(self, 'editing_id', None):
            self.editing_id = None
            try:
                self.save_button.config(text='Save')
                self.cancel_edit_button.config(state='disabled')
            except Exception:
                pass
    
    def view_records(self):
        """Open a new window to view all records from server"""
        try:
            response = self.session.get(
                f"{self.server_url}/api/clients",
                headers=self.get_headers(),
                timeout=10
            )
            
            if response.status_code != 200:
                messagebox.showerror("Error", "Failed to fetch records from server")
                return
            
            records = response.json()
            
            view_window = tk.Toplevel(self.root)
            view_window.title("View Records")
            view_window.geometry("1000x500")
            
            # Create treeview
            columns = ('ID', 'Date', 'First Name', 'Last Name', 'City', 'Phone', 'Household')
            tree = ttk.Treeview(view_window, columns=columns, height=20, show='headings')
            
            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=100)
            
            for record in records:
                tree.insert('', tk.END, values=(
                    record.get('ClientID'),
                    record.get('VisitDate'),
                    record.get('FirstName'),
                    record.get('LastName'),
                    record.get('City'),
                    record.get('CellPhone'),
                    record.get('HouseholdTotal')
                ))

            # Allow double-click to edit a record
            def on_double_click(event):
                item = tree.focus()
                if not item:
                    return
                vals = tree.item(item, 'values')
                if not vals:
                    return
                client_id = vals[0]
                try:
                    resp = self.session.get(f"{self.server_url}/api/clients/{client_id}", headers=self.get_headers(), timeout=10)
                    if resp.status_code == 200:
                        record = resp.json()
                        # Populate main GUI form for editing instead of opening modal
                        self.load_record_into_form(record)
                        view_window.destroy()
                    else:
                        messagebox.showerror('Error', f'Failed to fetch record {client_id}')
                except Exception as e:
                    messagebox.showerror('Error', f'Failed to fetch record: {e}')

            tree.bind('<Double-1>', on_double_click)

            # Add Edit/Delete buttons under the tree
            btn_frame = ttk.Frame(view_window)
            btn_frame.grid(row=1, column=0, columnspan=2, pady=8)

            def edit_selected():
                sel = tree.selection()
                if not sel:
                    messagebox.showinfo('Edit', 'Please select a record to edit')
                    return
                vals = tree.item(sel[0], 'values')
                client_id = vals[0]
                try:
                    resp = self.session.get(f"{self.server_url}/api/clients/{client_id}", headers=self.get_headers(), timeout=10)
                    if resp.status_code == 200:
                        record = resp.json()
                        self.load_record_into_form(record)
                        view_window.destroy()
                    else:
                        messagebox.showerror('Error', f'Failed to fetch record {client_id}')
                except Exception as e:
                    messagebox.showerror('Error', f'Failed to fetch record: {e}')

            def delete_selected():
                sel = tree.selection()
                if not sel:
                    messagebox.showinfo('Delete', 'Please select a record to delete')
                    return
                vals = tree.item(sel[0], 'values')
                client_id = vals[0]
                if not messagebox.askyesno('Confirm Delete', f'Are you sure you want to delete record ID {client_id}?'):
                    return
                try:
                    resp = self.session.delete(f"{self.server_url}/api/clients/{client_id}", headers=self.get_headers(), timeout=10)
                    if resp.status_code == 200:
                        messagebox.showinfo('Deleted', 'Record deleted successfully')
                        view_window.destroy()
                        self.view_records()
                    else:
                        messagebox.showerror('Error', resp.json().get('error', 'Delete failed'))
                except Exception as e:
                    messagebox.showerror('Error', f'Delete failed: {e}')

            ttk.Button(btn_frame, text='Edit Selected', command=edit_selected).pack(side=tk.LEFT, padx=6)
            ttk.Button(btn_frame, text='Delete Selected', command=delete_selected).pack(side=tk.LEFT, padx=6)
            
            # Add scrollbar
            scrollbar = ttk.Scrollbar(view_window, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscroll=scrollbar.set)
            
            tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
            
            view_window.columnconfigure(0, weight=1)
            view_window.rowconfigure(0, weight=1)
        
        except requests.exceptions.ConnectionError:
            messagebox.showerror("Error", f"Cannot connect to server at {self.server_url}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to fetch records: {str(e)}")

    def open_search_dialog(self):
        """Open a dialog to enter search criteria and show filtered results."""
        dlg = tk.Toplevel(self.root)
        dlg.title("Search Records")
        dlg.geometry("420x300")
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text="First Name:").grid(row=0, column=0, sticky=tk.W, padx=10, pady=(10,5))
        first_entry = ttk.Entry(dlg, width=40)
        first_entry.grid(row=0, column=1, padx=10, pady=(10,5))

        ttk.Label(dlg, text="Last Name:").grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)
        last_entry = ttk.Entry(dlg, width=40)
        last_entry.grid(row=1, column=1, padx=10, pady=5)

        ttk.Label(dlg, text="City:").grid(row=2, column=0, sticky=tk.W, padx=10, pady=5)
        city_entry = ttk.Entry(dlg, width=40)
        city_entry.grid(row=2, column=1, padx=10, pady=5)

        ttk.Label(dlg, text="Driver License #: ").grid(row=3, column=0, sticky=tk.W, padx=10, pady=5)
        dl_entry = ttk.Entry(dlg, width=40)
        dl_entry.grid(row=3, column=1, padx=10, pady=5)

        ttk.Label(dlg, text="Start Date (MM-DD-YYYY):").grid(row=4, column=0, sticky=tk.W, padx=10, pady=5)
        start_entry = ttk.Entry(dlg, width=20)
        start_entry.grid(row=4, column=1, sticky=tk.W, padx=10, pady=5)

        ttk.Label(dlg, text="End Date (MM-DD-YYYY):").grid(row=5, column=0, sticky=tk.W, padx=10, pady=5)
        end_entry = ttk.Entry(dlg, width=20)
        end_entry.grid(row=5, column=1, sticky=tk.W, padx=10, pady=5)

        def run_search():
            criteria = {
                'first': first_entry.get().strip(),
                'last': last_entry.get().strip(),
                'city': city_entry.get().strip(),
                'dl': dl_entry.get().strip(),
                'start': start_entry.get().strip(),
                'end': end_entry.get().strip()
            }
            dlg.destroy()
            self.perform_search(criteria)

        ttk.Button(dlg, text="Search", command=run_search).grid(row=6, column=0, columnspan=2, pady=15)

        dlg.update_idletasks()
        x = (dlg.winfo_screenwidth() // 2) - (dlg.winfo_width() // 2)
        y = (dlg.winfo_screenheight() // 2) - (dlg.winfo_height() // 2)
        dlg.geometry(f"+{x}+{y}")

    def perform_search(self, criteria):
        """Fetch records (with optional date range) then filter client-side by criteria."""
        try:
            params = {}
            if criteria.get('start'):
                params['start_date'] = criteria['start']
            if criteria.get('end'):
                params['end_date'] = criteria['end']

            response = self.session.get(f"{self.server_url}/api/clients", headers=self.get_headers(), params=params, timeout=10)
            if response.status_code != 200:
                messagebox.showerror("Error", "Failed to fetch records from server")
                return

            records = response.json()

            # Apply client-side filtering
            def matches(rec):
                def ci_contains(field, value):
                    if not value:
                        return True
                    f = str(rec.get(field, '') or '')
                    return value.lower() in f.lower()

                if not ci_contains('FirstName', criteria.get('first')):
                    return False
                if not ci_contains('LastName', criteria.get('last')):
                    return False
                if not ci_contains('City', criteria.get('city')):
                    return False
                if not ci_contains('DriverLicenseNumber', criteria.get('dl')):
                    return False
                return True

            filtered = [r for r in records if matches(r)]

            # Show results in the same viewer window
            view_window = tk.Toplevel(self.root)
            view_window.title(f"Search Results ({len(filtered)} records)")
            view_window.geometry("1000x500")

            columns = ('ID', 'Date', 'First Name', 'Last Name', 'City', 'Phone', 'Household')
            tree = ttk.Treeview(view_window, columns=columns, height=20, show='headings')
            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=140 if col == 'ID' else 140)

            for record in filtered:
                tree.insert('', tk.END, values=(
                    record.get('ClientID'),
                    record.get('VisitDate'),
                    record.get('FirstName'),
                    record.get('LastName'),
                    record.get('City'),
                    record.get('CellPhone'),
                    record.get('HouseholdTotal')
                ))

            # allow double-click to edit
            def on_double(event):
                item = tree.focus()
                if not item:
                    return
                vals = tree.item(item, 'values')
                if not vals:
                    return
                cid = vals[0]
                try:
                    resp = self.session.get(f"{self.server_url}/api/clients/{cid}", headers=self.get_headers(), timeout=10)
                    if resp.status_code == 200:
                        rec = resp.json()
                        self.load_record_into_form(rec)
                        view_window.destroy()
                    else:
                        messagebox.showerror('Error', 'Failed to fetch record')
                except Exception as e:
                    messagebox.showerror('Error', f'Failed to fetch record: {e}')

            tree.bind('<Double-1>', on_double)

            scrollbar = ttk.Scrollbar(view_window, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscroll=scrollbar.set)

            tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

            view_window.columnconfigure(0, weight=1)
            view_window.rowconfigure(0, weight=1)

        except requests.exceptions.ConnectionError:
            messagebox.showerror("Error", f"Cannot connect to server at {self.server_url}")
        except Exception as e:
            messagebox.showerror("Error", f"Search failed: {str(e)}")

    def open_record_editor(self, record, refresh_callback=None):
        """Open an editor populated with `record` dict. On save, PUT to server; on delete, DELETE."""
        editor = tk.Toplevel(self.root)
        editor.title(f"Edit Record ID {record.get('ClientID')}")
        editor.geometry('700x700')
        editor.transient(self.root)
        editor.grab_set()

        fields = [
            ('VisitDate','VisitDate'),('DriverLicenseNumber','DriverLicenseNumber'),
            ('FirstName','FirstName'),('MiddleInitial','MiddleInitial'),('LastName','LastName'),
            ('PhysicalAddress','PhysicalAddress'),('City','City'),('State','State'),('ZipCode','ZipCode'),
            ('County','County'),('CellPhone','CellPhone'),('Email','Email'),('DateOfBirth','DateOfBirth'),
            ('LanguageSpoken','LanguageSpoken'),('MaritalStatus','MaritalStatus'),('Nationality_Race','Nationality_Race'),
            ('CertificationStatus','CertificationStatus'),('IsVeteran','IsVeteran'),('HowHeardAboutUs','HowHeardAboutUs'),
            ('HouseholdTotal','HouseholdTotal')
        ]

        entries = {}
        row = 0
        frm = ttk.Frame(editor, padding=8)
        frm.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        for label_text, key in fields:
            ttk.Label(frm, text=label_text+':').grid(row=row, column=0, sticky=tk.W, pady=4)
            ent = ttk.Entry(frm, width=50)
            val = record.get(key) if record.get(key) is not None else ''
            ent.insert(0, str(val))
            ent.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=4)
            entries[key] = ent
            row += 1

        ttk.Label(frm, text='Notes:').grid(row=row, column=0, sticky=tk.W, pady=4)
        notes_text = tk.Text(frm, height=6, width=50)
        notes_text.grid(row=row, column=1, pady=4)
        notes_text.insert('1.0', record.get('Notes') or '')
        # Make Tab key skip to next field instead of inserting tabs
        notes_text.bind('<Tab>', lambda e: e.widget.tk_focusNext().focus() or 'break')
        notes_text.bind('<Shift-Tab>', lambda e: e.widget.tk_focusPrev().focus() or 'break')
        row += 1

        def save_changes():
            data = {}
            for key, ent in entries.items():
                v = ent.get().strip()
                if v == '':
                    data[key] = None
                else:
                    # try cast HouseholdTotal
                    if key == 'HouseholdTotal':
                        try:
                            data[key] = int(v)
                        except Exception:
                            data[key] = v
                    else:
                        data[key] = v
            data['Notes'] = notes_text.get('1.0', tk.END).strip()

            try:
                cid = record.get('ClientID')
                resp = self.session.put(f"{self.server_url}/api/clients/{cid}", json=data, headers=self.get_headers(), timeout=10)
                if resp.status_code == 200:
                    messagebox.showinfo('Saved', 'Record updated successfully')
                    editor.destroy()
                    if refresh_callback:
                        refresh_callback()
                else:
                    messagebox.showerror('Error', resp.json().get('error', 'Failed to update'))
            except Exception as e:
                messagebox.showerror('Error', f'Update failed: {e}')

        def delete_record():
            cid = record.get('ClientID')
            if not messagebox.askyesno('Confirm Delete', f'Are you sure you want to delete record ID {cid}?'):
                return
            try:
                resp = self.session.delete(f"{self.server_url}/api/clients/{cid}", headers=self.get_headers(), timeout=10)
                if resp.status_code == 200:
                    messagebox.showinfo('Deleted', 'Record deleted successfully')
                    editor.destroy()
                    if refresh_callback:
                        refresh_callback()
                else:
                    messagebox.showerror('Error', resp.json().get('error', 'Delete failed'))
            except Exception as e:
                messagebox.showerror('Error', f'Delete failed: {e}')

        btns = ttk.Frame(frm)
        btns.grid(row=row, column=0, columnspan=2, pady=12)
        ttk.Button(btns, text='Save', command=save_changes).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text='Delete', command=delete_record).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text='Cancel', command=editor.destroy).pack(side=tk.LEFT, padx=6)

        editor.update_idletasks()
        x = (editor.winfo_screenwidth() // 2) - (editor.winfo_width() // 2)
        y = (editor.winfo_screenheight() // 2) - (editor.winfo_height() // 2)
        editor.geometry(f'+{x}+{y}')

    def load_record_into_form(self, record):
        """Populate the main form with values from `record` and switch to edit mode."""
        try:
            # Set entries
            for key, widget in self.entries.items():
                if isinstance(widget, tk.Text):
                    # Notes
                    if key == 'Notes':
                        widget.delete('1.0', tk.END)
                        widget.insert('1.0', record.get('Notes') or '')
                    else:
                        widget.delete(0, tk.END)
                        widget.insert(0, record.get(key) or '')
                else:
                    widget.delete(0, tk.END)
                    widget.insert(0, record.get(key) or '')

            # Special fields
            self.marital_status.set(record.get('MaritalStatus') or '')
            self.veteran_status.set(record.get('IsVeteran') or '')

            # Races, certification, heard about
            for k in self.race_vars:
                self.race_vars[k].set(False)
            for k in self.cert_vars:
                self.cert_vars[k].set(False)
            for k in self.heard_vars:
                self.heard_vars[k].set(False)

            def apply_multi(field_name, var_dict):
                val = record.get(field_name) or ''
                parts = [p.strip() for p in str(val).split(',') if p.strip()]
                for p in parts:
                    if p in var_dict:
                        var_dict[p].set(True)

            apply_multi('Nationality_Race', self.race_vars)
            apply_multi('CertificationStatus', self.cert_vars)
            apply_multi('HowHeardAboutUs', self.heard_vars)

            # Set editing state
            self.editing_id = record.get('ClientID')
            self.save_button.config(text='Save Changes')
            self.cancel_edit_button.config(state='normal')

            # Bring main window to front
            try:
                self.root.deiconify()
                self.root.lift()
                self.root.focus_force()
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror('Error', f'Failed to load record into form: {e}')

    def cancel_edit(self):
        """Cancel edit mode and clear the form."""
        self.editing_id = None
        try:
            self.save_button.config(text='Save')
            self.cancel_edit_button.config(state='disabled')
        except Exception:
            pass
        self.clear_form()
    
    def generate_report(self):
        """Generate report from server data"""
        try:
            # Fetch statistics from server
            response = self.session.get(
                f"{self.server_url}/api/statistics",
                headers=self.get_headers(),
                timeout=10
            )
            
            if response.status_code != 200:
                messagebox.showerror("Error", "Failed to fetch statistics from server")
                return
            
            stats = response.json()
            
            # Ask user where to save
            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialfile=f"FoodBank_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )
            
            if not file_path:
                return
            
            # Fetch full records
            records_response = self.session.get(
                f"{self.server_url}/api/clients",
                headers=self.get_headers(),
                timeout=10
            )
            
            if records_response.status_code != 200:
                messagebox.showerror("Error", "Failed to fetch records from server")
                return
            
            records = records_response.json()
            
            # Write report
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("=" * 100 + "\n")
                f.write("I-70 STREET REACH FOOD BANK - CLIENT REPORT\n")
                f.write(f"Generated: {datetime.now().strftime('%m-%d-%Y %H:%M:%S')}\n")
                f.write(f"Total Records: {len(records)}\n")
                f.write("=" * 100 + "\n\n")
                
                # Write summary statistics
                f.write("SUMMARY STATISTICS\n")
                f.write("-" * 100 + "\n")
                f.write(f"Total Clients: {stats['total_clients']}\n")
                f.write(f"Average Household Size: {stats['avg_household']:.2f}\n")
                f.write(f"Total Household Members: {stats['total_household']}\n\n")
                
                # Certification Status
                f.write("CERTIFICATION STATUS BREAKDOWN:\n")
                for cert, count in sorted(stats['certification'].items(), key=lambda x: x[1], reverse=True):
                    if cert:
                        f.write(f"  {cert}: {count}\n")
                f.write(f"  None Listed: {stats['certification'].get('', 0)}\n\n")
                
                # Nationality/Race
                f.write("NATIONALITY/RACE BREAKDOWN:\n")
                for race, count in sorted(stats['race'].items(), key=lambda x: x[1], reverse=True):
                    if race:
                        f.write(f"  {race}: {count}\n")
                f.write(f"  None Listed: {stats['race'].get('', 0)}\n\n")
                
                # Marital Status
                f.write("MARITAL STATUS BREAKDOWN:\n")
                for status, count in sorted(stats['marital'].items(), key=lambda x: x[1], reverse=True):
                    if status:
                        f.write(f"  {status}: {count}\n")
                f.write(f"  None Listed: {stats['marital'].get('', 0)}\n\n")
                
                # Veteran Status
                f.write("VETERAN STATUS:\n")
                f.write(f"  Yes: {stats['veteran_yes']}\n")
                f.write(f"  No: {stats['veteran_no']}\n")
                f.write(f"  Not Specified: {stats['veteran_unknown']}\n\n")
                
                # How Heard About Us
                f.write("HOW CLIENTS HEARD ABOUT US:\n")
                for source, count in sorted(stats['heard'].items(), key=lambda x: x[1], reverse=True):
                    if source:
                        f.write(f"  {source}: {count}\n")
                f.write(f"  None Listed: {stats['heard'].get('', 0)}\n\n")
            
            messagebox.showinfo("Success", f"Report saved successfully!\n\n{file_path}")
        
        except requests.exceptions.ConnectionError:
            messagebox.showerror("Error", f"Cannot connect to server at {self.server_url}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate report: {str(e)}")

    def import_csv(self):
        """Import client records from a CSV or Excel file with column mapping"""
        file_path = filedialog.askopenfilename(
            title="Select file to import",
            filetypes=[("Excel files", "*.xlsx"), ("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            # Check if file exists and is readable
            if not os.path.exists(file_path):
                messagebox.showerror("Error", f"File not found: {file_path}")
                return
            
            if not os.access(file_path, os.R_OK):
                messagebox.showerror("Error", f"Cannot read file. Please close it if it's open in another program and try again.")
                return
            
            records = []
            file_ext = os.path.splitext(file_path)[1].lower()
            
            if file_ext == '.xlsx':
                if not openpyxl:
                    messagebox.showerror("Error", "openpyxl not installed. Install with: pip install openpyxl")
                    return
                
                try:
                    # Open in read-only mode to avoid conflicts
                    wb = openpyxl.load_workbook(file_path, data_only=True)
                    ws = wb.active
                    
                    # Get headers from first row
                    headers = []
                    for cell in ws[1]:
                        if cell.value:
                            headers.append(str(cell.value))
                    
                    if not headers:
                        messagebox.showerror("Error", "Excel file has no headers in first row")
                        return
                    
                    # Get data rows
                    for row in ws.iter_rows(min_row=2, values_only=True):
                        if any(cell for cell in row):  # Skip empty rows
                            record = {}
                            for idx, header in enumerate(headers):
                                if idx < len(row):
                                    record[header] = row[idx]
                            records.append(record)
                    
                    wb.close()
                except PermissionError:
                    messagebox.showerror("Error", "Permission denied reading Excel file. Please close it if it's open in Excel and try again.")
                    return
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to read Excel file: {str(e)}")
                    return
                
            elif file_ext == '.csv':
                import csv
                try:
                    with open(file_path, 'r', encoding='utf-8') as csvfile:
                        reader = csv.DictReader(csvfile)
                        if not reader.fieldnames:
                            messagebox.showerror("Error", "CSV file is empty or invalid")
                            return
                        
                        for row in reader:
                            records.append(row)
                except PermissionError:
                    messagebox.showerror("Error", "Permission denied reading CSV file. Please close it if it's open and try again.")
                    return
                except UnicodeDecodeError:
                    messagebox.showerror("Error", "CSV file encoding error. Please ensure the file is saved as UTF-8.")
                    return
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to read CSV file: {str(e)}")
                    return
            else:
                messagebox.showerror("Error", "Unsupported file format. Use .xlsx or .csv")
                return
            
            if not records:
                messagebox.showinfo("Import", "No records found in file")
                return
            
            # Show column mapping dialog
            self.show_column_mapping(records, file_path)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read file: {str(e)}")
            import traceback
            traceback.print_exc()

    def show_column_mapping(self, records, file_path):
        """Show a dialog to map source columns to database fields"""
        mapping_window = tk.Toplevel(self.root)
        mapping_window.title("Column Mapping")
        mapping_window.geometry("700x600")
        
        ttk.Label(mapping_window, text="Map source columns to database fields", 
                 font=("Arial", 11, "bold")).pack(pady=10)
        
        # Get database fields from the form entries
        db_fields = sorted([k for k in self.entries.keys()])
        
        # Get source columns from first record
        source_columns = sorted(list(records[0].keys())) if records else []
        
        # Create mapping dictionary
        mapping = {}
        
        # Create canvas with scrollbar for mapping controls
        canvas = tk.Canvas(mapping_window)
        scrollbar = ttk.Scrollbar(mapping_window, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Bind mouse wheel
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        # Create mapping widgets for each source column
        dropdowns = {}
        for source_col in source_columns:
            frame = ttk.Frame(scrollable_frame)
            frame.pack(fill=tk.X, padx=10, pady=5)
            
            ttk.Label(frame, text=f"Source: {source_col}", width=25, font=("Arial", 9)).pack(side=tk.LEFT, padx=5)
            
            ttk.Label(frame, text="â†’", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)
            
            var = tk.StringVar()
            dropdown = ttk.Combobox(frame, textvariable=var, values=["(Skip)"] + db_fields, width=30, state='readonly')
            dropdown.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
            
            # Try to auto-match columns
            for db_field in db_fields:
                if source_col.lower() in db_field.lower() or db_field.lower() in source_col.lower():
                    dropdown.set(db_field)
                    break
            
            if not dropdown.get():
                dropdown.set("(Skip)")
            
            dropdowns[source_col] = var
            mapping[source_col] = var
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Buttons
        button_frame = ttk.Frame(mapping_window)
        button_frame.pack(pady=10)
        
        def proceed_with_mapping():
            # Build final mapping
            final_mapping = {}
            for source_col, var in mapping.items():
                target = var.get()
                if target != "(Skip)":
                    final_mapping[source_col] = target
            
            if not final_mapping:
                messagebox.showwarning("Warning", "No columns mapped. Please map at least one column.")
                return
            
            mapping_window.destroy()
            self.show_import_preview(records, file_path, final_mapping)
        
        ttk.Button(button_frame, text="Next", command=proceed_with_mapping).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=mapping_window.destroy).pack(side=tk.LEFT, padx=5)

    def show_import_preview(self, records, file_path, column_mapping=None):
        """Show a preview of records to be imported with option to proceed"""
        preview_window = tk.Toplevel(self.root)
        preview_window.title("Import Preview")
        preview_window.geometry("700x500")
        
        # Title
        ttk.Label(preview_window, text=f"Preview: {len(records)} records to import from {os.path.basename(file_path)}", 
                  font=("Arial", 10, "bold")).pack(pady=10)
        
        # Create a treeview to show preview
        tree_frame = ttk.Frame(preview_window)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        hsb = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)
        
        # Define columns - use mapped columns if available
        if column_mapping:
            columns = list(column_mapping.values())[:5]
        else:
            columns = list(records[0].keys())[:5] if records else []
        
        tree = ttk.Treeview(tree_frame, columns=columns, height=15, yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        vsb.config(command=tree.yview)
        hsb.config(command=tree.xview)
        
        tree.column("#0", width=0, stretch=tk.NO)
        tree.heading("#0", text="", anchor=tk.W)
        
        for col in columns:
            tree.column(col, anchor=tk.W, width=120)
            tree.heading(col, text=col, anchor=tk.W)
        
        # Add records to tree
        for idx, record in enumerate(records[:100]):  # Show first 100 records
            if column_mapping:
                # Map the columns
                values = []
                for source_col, target_col in list(column_mapping.items())[:5]:
                    values.append(record.get(source_col, ""))
            else:
                values = [record.get(col, "") for col in columns]
            
            tree.insert("", tk.END, text=str(idx+1), values=values)
        
        if len(records) > 100:
            ttk.Label(tree_frame, text=f"... and {len(records) - 100} more records", 
                     font=("Arial", 9)).pack()
        
        tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        
        # Info label
        info_label = ttk.Label(preview_window, 
                               text=f"File has {len(records)} records",
                               font=("Arial", 9))
        info_label.pack(pady=5)
        
        # Buttons
        button_frame = ttk.Frame(preview_window)
        button_frame.pack(pady=10)
        
        def proceed_import():
            preview_window.destroy()
            self.perform_import(records, column_mapping)
        
        ttk.Button(button_frame, text="Import All", command=proceed_import).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=preview_window.destroy).pack(side=tk.LEFT, padx=5)

    def perform_import(self, records, column_mapping=None):
        """Perform the actual import of records with optional column mapping"""
        import_window = tk.Toplevel(self.root)
        import_window.title("Importing Records")
        import_window.geometry("400x150")
        
        status_label = ttk.Label(import_window, text="Starting import...", font=("Arial", 10))
        status_label.pack(pady=20)
        
        progress = ttk.Progressbar(import_window, length=300, mode='determinate')
        progress.pack(pady=10)
        progress['maximum'] = len(records)
        
        result_label = ttk.Label(import_window, text="", font=("Arial", 9))
        result_label.pack(pady=10)
        
        import_window.update()
        
        successful = 0
        failed = 0
        errors = []
        
        for idx, record in enumerate(records):
            progress['value'] = idx + 1
            status_label.config(text=f"Importing record {idx + 1} of {len(records)}...")
            result_label.config(text=f"Successful: {successful}, Failed: {failed}")
            import_window.update()
            
            try:
                # Prepare data for the server API
                data = {}
                
                if column_mapping:
                    # Use column mapping to transform data
                    for source_col, target_col in column_mapping.items():
                        value = record.get(source_col, "")
                        if value:
                            data[target_col] = value.strip() if isinstance(value, str) else value
                else:
                    # Direct mapping (no transformation)
                    for key, value in record.items():
                        # Clean up the key (remove leading/trailing spaces)
                        clean_key = key.strip() if key else ""
                        if clean_key:
                            data[clean_key] = value.strip() if isinstance(value, str) else value
                
                # Skip empty records
                if not any(data.values()):
                    continue
                
                # Send to server
                response = self.session.post(
                    f"{self.server_url}/api/clients",
                    json=data,
                    headers=self.get_headers(),
                    timeout=10
                )
                
                if response.status_code == 201:
                    successful += 1
                else:
                    failed += 1
                    errors.append(f"Record {idx + 1}: {response.text[:100]}")
            except Exception as e:
                failed += 1
                errors.append(f"Record {idx + 1}: {str(e)[:100]}")
        
        status_label.config(text="Import complete!")
        result_label.config(text=f"Successful: {successful}, Failed: {failed}")
        
        # Show results
        ttk.Button(import_window, text="OK", command=import_window.destroy).pack(pady=10)
        
        if errors:
            # Show error details
            if messagebox.askyesno("Import Results", 
                                   f"Imported {successful} records successfully, {failed} failed.\n\nView error details?"):
                error_window = tk.Toplevel(import_window)
                error_window.title("Import Errors")
                error_window.geometry("500x300")
                
                text_widget = tk.Text(error_window, wrap=tk.WORD, font=("Arial", 9))
                text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
                
                for error in errors[:50]:  # Show first 50 errors
                    text_widget.insert(tk.END, error + "\n")
                text_widget.config(state='disabled')
        else:
            messagebox.showinfo("Import Complete", f"Successfully imported {successful} records!")

if __name__ == "__main__":
    try:
        root = tk.Tk()
        gui = FoodBankClientGUI(root)
        root.mainloop()
    except Exception as e:
        # Log traceback for debugging and show a messagebox
        log_path = os.path.join(os.path.dirname(__file__), 'client_error.log')
        with open(log_path, 'w', encoding='utf-8') as lf:
            lf.write('Exception during client startup:\n')
            traceback.print_exc(file=lf)
        try:
            messagebox.showerror('Client Error', f'An error occurred starting the client. See {log_path} for details.')
        except Exception:
            pass
        print(f'An error occurred. See {log_path} for details.')
        raise

