"""
I-70 Street Reach Food Bank Database Server - Cloud Version
Network-accessible REST API server with user authentication and PostgreSQL support
"""
import os
import sqlite3
import json
import secrets
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, session
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

# ============================================================================
# CONFIGURATION
# ============================================================================

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', secrets.token_hex(32))
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

# Database configuration
USE_POSTGRES = os.getenv('USE_POSTGRES', 'false').lower() == 'true'
DATABASE_URL = os.getenv('DATABASE_URL', '')

if USE_POSTGRES and DATABASE_URL:
    # PostgreSQL configuration
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        DB_TYPE = 'postgresql'
    except ImportError:
        print("Warning: psycopg2 not installed. Falling back to SQLite.")
        USE_POSTGRES = False
        DB_TYPE = 'sqlite'
else:
    DB_TYPE = 'sqlite'
    DB_PATH = os.path.join(os.path.dirname(__file__), 'food_bank.db')

# ============================================================================
# DATABASE CONNECTION
# ============================================================================

def get_db_connection():
    """Get database connection based on configuration"""
    if DB_TYPE == 'postgresql':
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

def execute_query(query, params=None, fetch_one=False, fetch_all=False, commit=False):
    """Execute database query with proper connection handling"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        if commit:
            conn.commit()
            if DB_TYPE == 'postgresql':
                result = cursor.fetchone() if cursor.description else None
            else:
                result = cursor.lastrowid
        elif fetch_one:
            result = cursor.fetchone()
        elif fetch_all:
            result = cursor.fetchall()
        else:
            result = None
        
        return result
    finally:
        conn.close()

# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================

def init_database():
    """Initialize database if it doesn't exist"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create Users table
    if DB_TYPE == 'postgresql':
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Users (
                UserID SERIAL PRIMARY KEY,
                Username VARCHAR(50) UNIQUE NOT NULL,
                PasswordHash VARCHAR(255) NOT NULL,
                FullName VARCHAR(100),
                Email VARCHAR(100),
                Role VARCHAR(20) DEFAULT 'user',
                IsActive BOOLEAN DEFAULT TRUE,
                CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                LastLogin TIMESTAMP
            )
        ''')
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Users (
                UserID INTEGER PRIMARY KEY AUTOINCREMENT,
                Username TEXT UNIQUE NOT NULL,
                PasswordHash TEXT NOT NULL,
                FullName TEXT,
                Email TEXT,
                Role TEXT DEFAULT 'user',
                IsActive INTEGER DEFAULT 1,
                CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                LastLogin TIMESTAMP
            )
        ''')
    
    # Create Clients table
    if DB_TYPE == 'postgresql':
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Clients (
                ClientID SERIAL PRIMARY KEY,
                VisitDate VARCHAR(50) NOT NULL,
                DriverLicenseNumber VARCHAR(50),
                FirstName VARCHAR(50) NOT NULL,
                MiddleInitial VARCHAR(5),
                LastName VARCHAR(50) NOT NULL,
                PhysicalAddress VARCHAR(200),
                City VARCHAR(50),
                State VARCHAR(2),
                ZipCode VARCHAR(10),
                County VARCHAR(50),
                CellPhone VARCHAR(20),
                Email VARCHAR(100),
                DateOfBirth VARCHAR(50),
                LanguageSpoken VARCHAR(50),
                MaritalStatus VARCHAR(20),
                Nationality_Race VARCHAR(50),
                CertificationStatus VARCHAR(50),
                IsVeteran VARCHAR(10),
                HowHeardAboutUs VARCHAR(100),
                HouseholdTotal INTEGER,
                Notes TEXT,
                CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CreatedBy INTEGER REFERENCES Users(UserID)
            )
        ''')
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Clients (
                ClientID INTEGER PRIMARY KEY AUTOINCREMENT,
                VisitDate TEXT NOT NULL,
                DriverLicenseNumber TEXT,
                FirstName TEXT NOT NULL,
                MiddleInitial TEXT,
                LastName TEXT NOT NULL,
                PhysicalAddress TEXT,
                City TEXT,
                State TEXT,
                ZipCode TEXT,
                County TEXT,
                CellPhone TEXT,
                Email TEXT,
                DateOfBirth TEXT,
                LanguageSpoken TEXT,
                MaritalStatus TEXT,
                Nationality_Race TEXT,
                CertificationStatus TEXT,
                IsVeteran TEXT,
                HowHeardAboutUs TEXT,
                HouseholdTotal INTEGER,
                Notes TEXT,
                CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CreatedBy INTEGER,
                FOREIGN KEY (CreatedBy) REFERENCES Users(UserID)
            )
        ''')
    
    conn.commit()
    
    # Create default admin user if no users exist
    cursor.execute('SELECT COUNT(*) FROM Users')
    if DB_TYPE == 'postgresql':
        count = cursor.fetchone()['count']
    else:
        count = cursor.fetchone()[0]
    
    if count == 0:
        default_password = os.getenv('ADMIN_PASSWORD', 'foodbank2024')
        password_hash = generate_password_hash(default_password)
        cursor.execute('''
            INSERT INTO Users (Username, PasswordHash, FullName, Role)
            VALUES (?, ?, ?, ?)
        ''' if DB_TYPE == 'sqlite' else '''
            INSERT INTO Users (Username, PasswordHash, FullName, Role)
            VALUES (%s, %s, %s, %s)
        ''', ('admin', password_hash, 'Administrator', 'admin'))
        conn.commit()
        print(f"Created default admin user: admin / {default_password}")
    
    conn.close()

# ============================================================================
# AUTHENTICATION
# ============================================================================

# Global flag to track database initialization
_db_initialized = False

def ensure_database():
    """Ensure database is initialized (thread-safe)"""
    global _db_initialized
    if not _db_initialized:
        try:
            init_database()
            _db_initialized = True
            print("Database initialized on first request", flush=True)
        except Exception as e:
            print(f"Database initialization failed: {e}", flush=True)
            import traceback
            traceback.print_exc()
            # Don't set flag so it will retry on next request
            raise

def login_required(f):
    """Decorator to require user login"""
    @wraps(f)
    def decorated(*args, **kwargs):
        ensure_database()  # Ensure DB is initialized before checking auth
        user_id = session.get('user_id')
        
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        # Verify user still exists and is active
        user = execute_query(
            'SELECT * FROM Users WHERE UserID = ? AND IsActive = 1' if DB_TYPE == 'sqlite'
            else 'SELECT * FROM Users WHERE UserID = %s AND IsActive = TRUE',
            (user_id,),
            fetch_one=True
        )
        
        if not user:
            session.clear()
            return jsonify({'error': 'User not found or inactive'}), 401
        
        # Add user info to request context
        request.current_user = dict(user)
        
        return f(*args, **kwargs)
    
    return decorated

def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = session.get('user_id')
        
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        user = execute_query(
            'SELECT * FROM Users WHERE UserID = ? AND IsActive = 1' if DB_TYPE == 'sqlite'
            else 'SELECT * FROM Users WHERE UserID = %s AND IsActive = TRUE',
            (user_id,),
            fetch_one=True
        )
        
        user_dict = dict(user)
        role = user_dict.get('Role') or user_dict.get('role')
        if not user or role != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        request.current_user = dict(user)
        
        return f(*args, **kwargs)
    
    return decorated

# ============================================================================
# API ENDPOINTS - AUTHENTICATION
# ============================================================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint (no auth required)"""
    return jsonify({
        'status': 'ok',
        'server': 'Food Bank Database Server (Cloud)',
        'database': DB_TYPE,
        'initialized': _db_initialized
    }), 200

@app.route('/api/init', methods=['POST'])
def manual_init():
    """Manual database initialization endpoint"""
    try:
        init_database()
        return jsonify({
            'message': 'Database initialized successfully',
            'database': DB_TYPE
        }), 200
    except Exception as e:
        return jsonify({
            'error': str(e),
            'database': DB_TYPE
        }), 500

@app.route('/api/login', methods=['POST'])
def login():
    """User login"""
    ensure_database()  # Ensure DB is initialized before login
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    user = execute_query(
        'SELECT * FROM Users WHERE Username = ? AND IsActive = 1' if DB_TYPE == 'sqlite'
        else 'SELECT * FROM Users WHERE Username = %s AND IsActive = TRUE',
        (username,),
        fetch_one=True
    )
    
    if not user:
        return jsonify({'error': 'Invalid username or password'}), 401
    
    user_dict = dict(user)
    
    # Handle both SQLite (PasswordHash) and PostgreSQL (passwordhash) column names
    password_hash = user_dict.get('PasswordHash') or user_dict.get('passwordhash')
    if not check_password_hash(password_hash, password):
        return jsonify({'error': 'Invalid username or password'}), 401
    
    # Update last login
    user_id = user_dict.get('UserID') or user_dict.get('userid')
    execute_query(
        'UPDATE Users SET LastLogin = ? WHERE UserID = ?' if DB_TYPE == 'sqlite'
        else 'UPDATE Users SET LastLogin = %s WHERE UserID = %s',
        (datetime.now().isoformat(), user_id),
        commit=True
    )
    
    # Create session
    session.permanent = True
    session['user_id'] = user_id
    session['username'] = user_dict.get('Username') or user_dict.get('username')
    session['role'] = user_dict.get('Role') or user_dict.get('role')
    
    return jsonify({
        'message': 'Login successful',
        'user': {
            'username': session['username'],
            'fullName': user_dict.get('FullName') or user_dict.get('fullname'),
            'role': session['role']
        }
    }), 200

@app.route('/api/logout', methods=['POST'])
def logout():
    """User logout"""
    session.clear()
    return jsonify({'message': 'Logout successful'}), 200

@app.route('/api/me', methods=['GET'])
@login_required
def get_current_user():
    """Get current user info"""
    user = request.current_user
    return jsonify({
        'username': user.get('Username') or user.get('username'),
        'fullName': user.get('FullName') or user.get('fullname'),
        'email': user.get('Email') or user.get('email'),
        'role': user.get('Role') or user.get('role')
    }), 200

# ============================================================================
# API ENDPOINTS - USER MANAGEMENT (ADMIN ONLY)
# ============================================================================

@app.route('/api/users', methods=['GET'])
@admin_required
def get_users():
    """Get all users (admin only)"""
    users = execute_query('SELECT UserID, Username, FullName, Email, Role, IsActive, CreatedAt, LastLogin FROM Users ORDER BY Username', fetch_all=True)
    
    return jsonify({
        'users': [dict(u) for u in users]
    }), 200

@app.route('/api/users', methods=['POST'])
@admin_required
def create_user():
    """Create new user (admin only)"""
    data = request.get_json()
    
    username = data.get('username', '').strip()
    password = data.get('password', '')
    full_name = data.get('fullName', '').strip()
    email = data.get('email', '').strip()
    role = data.get('role', 'user')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    if role not in ['user', 'admin']:
        return jsonify({'error': 'Invalid role'}), 400
    
    # Check if username already exists
    existing = execute_query(
        'SELECT UserID FROM Users WHERE Username = ?' if DB_TYPE == 'sqlite'
        else 'SELECT UserID FROM Users WHERE Username = %s',
        (username,),
        fetch_one=True
    )
    
    if existing:
        return jsonify({'error': 'Username already exists'}), 400
    
    password_hash = generate_password_hash(password)
    
    execute_query(
        'INSERT INTO Users (Username, PasswordHash, FullName, Email, Role) VALUES (?, ?, ?, ?, ?)' if DB_TYPE == 'sqlite'
        else 'INSERT INTO Users (Username, PasswordHash, FullName, Email, Role) VALUES (%s, %s, %s, %s, %s)',
        (username, password_hash, full_name, email, role),
        commit=True
    )
    
    return jsonify({'message': 'User created successfully'}), 201

@app.route('/api/users/<int:user_id>', methods=['PUT'])
@admin_required
def update_user(user_id):
    """Update user (admin only)"""
    data = request.get_json()
    
    user = execute_query(
        'SELECT * FROM Users WHERE UserID = ?' if DB_TYPE == 'sqlite'
        else 'SELECT * FROM Users WHERE UserID = %s',
        (user_id,),
        fetch_one=True
    )
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    full_name = data.get('fullName', '').strip()
    email = data.get('email', '').strip()
    role = data.get('role')
    is_active = data.get('isActive')
    new_password = data.get('password')
    
    updates = []
    params = []
    
    if full_name is not None:
        updates.append('FullName = ?' if DB_TYPE == 'sqlite' else 'FullName = %s')
        params.append(full_name)
    
    if email is not None:
        updates.append('Email = ?' if DB_TYPE == 'sqlite' else 'Email = %s')
        params.append(email)
    
    if role and role in ['user', 'admin']:
        updates.append('Role = ?' if DB_TYPE == 'sqlite' else 'Role = %s')
        params.append(role)
    
    if is_active is not None:
        updates.append('IsActive = ?' if DB_TYPE == 'sqlite' else 'IsActive = %s')
        params.append(1 if is_active else 0 if DB_TYPE == 'sqlite' else is_active)
    
    if new_password:
        updates.append('PasswordHash = ?' if DB_TYPE == 'sqlite' else 'PasswordHash = %s')
        params.append(generate_password_hash(new_password))
    
    if updates:
        params.append(user_id)
        query = f"UPDATE Users SET {', '.join(updates)} WHERE UserID = {'?' if DB_TYPE == 'sqlite' else '%s'}"
        execute_query(query, params, commit=True)
    
    return jsonify({'message': 'User updated successfully'}), 200

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    """Delete user (admin only)"""
    current_user_id = request.current_user.get('UserID') or request.current_user.get('userid')
    if user_id == current_user_id:
        return jsonify({'error': 'Cannot delete your own account'}), 400
    
    execute_query(
        'DELETE FROM Users WHERE UserID = ?' if DB_TYPE == 'sqlite'
        else 'DELETE FROM Users WHERE UserID = %s',
        (user_id,),
        commit=True
    )
    
    return jsonify({'message': 'User deleted successfully'}), 200

# ============================================================================
# API ENDPOINTS - CLIENT CRUD OPERATIONS
# ============================================================================

@app.route('/api/clients', methods=['GET'])
@login_required
def get_clients():
    """Get all client records"""
    clients = execute_query('SELECT * FROM Clients ORDER BY CreatedAt DESC', fetch_all=True)
    
    return jsonify({
        'clients': [dict(c) for c in clients],
        'count': len(clients)
    }), 200

@app.route('/api/clients/<int:client_id>', methods=['GET'])
@login_required
def get_client(client_id):
    """Get single client record"""
    client = execute_query(
        'SELECT * FROM Clients WHERE ClientID = ?' if DB_TYPE == 'sqlite'
        else 'SELECT * FROM Clients WHERE ClientID = %s',
        (client_id,),
        fetch_one=True
    )
    
    if not client:
        return jsonify({'error': 'Client not found'}), 404
    
    return jsonify(dict(client)), 200

@app.route('/api/clients', methods=['POST'])
@login_required
def create_client():
    """Create new client record"""
    data = request.get_json()
    
    # Required fields
    required = ['FirstName', 'LastName', 'VisitDate']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400
    
    fields = [
        'VisitDate', 'DriverLicenseNumber', 'FirstName', 'MiddleInitial', 'LastName',
        'PhysicalAddress', 'City', 'State', 'ZipCode', 'County', 'CellPhone', 'Email',
        'DateOfBirth', 'LanguageSpoken', 'MaritalStatus', 'Nationality_Race',
        'CertificationStatus', 'IsVeteran', 'HowHeardAboutUs', 'HouseholdTotal', 'Notes',
        'CreatedBy'
    ]
    
    values = []
    for field in fields:
        if field == 'CreatedBy':
            values.append(request.current_user.get('UserID') or request.current_user.get('userid'))
        else:
            values.append(data.get(field))
    
    placeholders = ', '.join(['?' if DB_TYPE == 'sqlite' else '%s'] * len(fields))
    query = f"INSERT INTO Clients ({', '.join(fields)}) VALUES ({placeholders})"
    
    if DB_TYPE == 'postgresql':
        query += ' RETURNING ClientID'
        result = execute_query(query, values, commit=True)
        client_id = result['clientid'] if result else None
    else:
        client_id = execute_query(query, values, commit=True)
    
    return jsonify({
        'message': 'Client record created',
        'clientId': client_id
    }), 201

@app.route('/api/clients/<int:client_id>', methods=['PUT'])
@login_required
def update_client(client_id):
    """Update client record"""
    data = request.get_json()
    
    # Check if client exists
    client = execute_query(
        'SELECT * FROM Clients WHERE ClientID = ?' if DB_TYPE == 'sqlite'
        else 'SELECT * FROM Clients WHERE ClientID = %s',
        (client_id,),
        fetch_one=True
    )
    
    if not client:
        return jsonify({'error': 'Client not found'}), 404
    
    fields = [
        'VisitDate', 'DriverLicenseNumber', 'FirstName', 'MiddleInitial', 'LastName',
        'PhysicalAddress', 'City', 'State', 'ZipCode', 'County', 'CellPhone', 'Email',
        'DateOfBirth', 'LanguageSpoken', 'MaritalStatus', 'Nationality_Race',
        'CertificationStatus', 'IsVeteran', 'HowHeardAboutUs', 'HouseholdTotal', 'Notes'
    ]
    
    updates = []
    values = []
    
    for field in fields:
        if field in data:
            updates.append(f"{field} = {'?' if DB_TYPE == 'sqlite' else '%s'}")
            values.append(data[field])
    
    if not updates:
        return jsonify({'error': 'No fields to update'}), 400
    
    values.append(client_id)
    query = f"UPDATE Clients SET {', '.join(updates)} WHERE ClientID = {'?' if DB_TYPE == 'sqlite' else '%s'}"
    
    execute_query(query, values, commit=True)
    
    return jsonify({'message': 'Client record updated'}), 200

@app.route('/api/clients/<int:client_id>', methods=['DELETE'])
@login_required
def delete_client(client_id):
    """Delete client record"""
    execute_query(
        'DELETE FROM Clients WHERE ClientID = ?' if DB_TYPE == 'sqlite'
        else 'DELETE FROM Clients WHERE ClientID = %s',
        (client_id,),
        commit=True
    )
    
    return jsonify({'message': 'Client record deleted'}), 200

@app.route('/api/clients/search', methods=['POST'])
@login_required
def search_clients():
    """Search client records"""
    data = request.get_json()
    search_term = data.get('search', '').strip()
    
    if not search_term:
        return get_clients()
    
    query = '''
        SELECT * FROM Clients 
        WHERE FirstName LIKE ? OR LastName LIKE ? OR DriverLicenseNumber LIKE ? 
           OR CellPhone LIKE ? OR Email LIKE ?
        ORDER BY CreatedAt DESC
    ''' if DB_TYPE == 'sqlite' else '''
        SELECT * FROM Clients 
        WHERE FirstName ILIKE %s OR LastName ILIKE %s OR DriverLicenseNumber ILIKE %s 
           OR CellPhone ILIKE %s OR Email ILIKE %s
        ORDER BY CreatedAt DESC
    '''
    
    search_pattern = f'%{search_term}%'
    clients = execute_query(
        query,
        (search_pattern, search_pattern, search_pattern, search_pattern, search_pattern),
        fetch_all=True
    )
    
    return jsonify({
        'clients': [dict(c) for c in clients],
        'count': len(clients)
    }), 200

@app.route('/api/statistics', methods=['GET'])
@login_required
def get_statistics():
    """Get statistics about client records"""
    clients = execute_query('SELECT * FROM Clients', fetch_all=True)
    clients_list = [dict(c) for c in clients]
    
    stats = {
        'total_clients': len(clients_list),
        'avg_household': 0,
        'total_household': 0,
        'certification': {},
        'race': {},
        'marital': {},
        'veteran_yes': 0,
        'veteran_no': 0,
        'veteran_unknown': 0,
        'heard': {}
    }
    
    household_count = 0
    for client in clients_list:
        # Handle both uppercase (SQLite) and lowercase (PostgreSQL) keys
        household = client.get('HouseholdTotal') or client.get('householdtotal')
        if household:
            try:
                stats['total_household'] += int(household)
                household_count += 1
            except (ValueError, TypeError):
                pass
        
        # Certification status
        cert = client.get('CertificationStatus') or client.get('certificationstatus') or ''
        for c in str(cert).split(','):
            c = c.strip()
            if c:
                stats['certification'][c] = stats['certification'].get(c, 0) + 1
        
        # Race/Nationality
        race = client.get('Nationality_Race') or client.get('nationality_race') or ''
        for r in str(race).split(','):
            r = r.strip()
            if r:
                stats['race'][r] = stats['race'].get(r, 0) + 1
        
        # Marital status
        marital = client.get('MaritalStatus') or client.get('maritalstatus') or ''
        if marital:
            stats['marital'][marital] = stats['marital'].get(marital, 0) + 1
        
        # Veteran status
        veteran = str(client.get('IsVeteran') or client.get('isveteran') or '').lower()
        if veteran == 'yes':
            stats['veteran_yes'] += 1
        elif veteran == 'no':
            stats['veteran_no'] += 1
        else:
            stats['veteran_unknown'] += 1
        
        # How heard about us
        heard = client.get('HowHeardAboutUs') or client.get('howheardaboutus') or ''
        for h in str(heard).split(','):
            h = h.strip()
            if h:
                stats['heard'][h] = stats['heard'].get(h, 0) + 1
    
    if household_count > 0:
        stats['avg_household'] = stats['total_household'] / household_count
    
    return jsonify(stats), 200

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    # Get configuration from environment
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('DEBUG', 'false').lower() == 'true'
    
    print(f"Starting server on {host}:{port}")
    print("Ready for connections!")
    
    app.run(host=host, port=port, debug=debug)
