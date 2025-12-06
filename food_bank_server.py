"""
I-70 Street Reach Food Bank Database Server
Network-accessible REST API server for multi-user access
"""
import os
import sqlite3
import json
from datetime import datetime
from flask import Flask, request, jsonify
from functools import wraps

# ============================================================================
# CONFIGURATION
# ============================================================================

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# Database path (same directory as server script)
DB_PATH = os.path.join(os.path.dirname(__file__), 'food_bank.db')

# Simple authentication - set these as environment variables or edit here
# Default credentials: admin / foodbank2024
ADMIN_USERNAME = os.getenv('FOODBANK_USERNAME', 'admin')
ADMIN_PASSWORD = os.getenv('FOODBANK_PASSWORD', 'foodbank2024')

# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================

def init_database():
    """Initialize SQLite database if it doesn't exist"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
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
            CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

# ============================================================================
# AUTHENTICATION
# ============================================================================

def token_required(f):
    """Decorator to require authentication token"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        
        if not token:
            return jsonify({'error': 'Authentication token missing'}), 401
        
        # Simple token validation (in production, use JWT)
        if token != f'Bearer {ADMIN_PASSWORD}':
            return jsonify({'error': 'Invalid authentication token'}), 401
        
        return f(*args, **kwargs)
    
    return decorated

# ============================================================================
# API ENDPOINTS - CRUD OPERATIONS
# ============================================================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint (no auth required)"""
    return jsonify({'status': 'ok', 'server': 'Food Bank Database Server'}), 200

@app.route('/api/authenticate', methods=['POST'])
def authenticate():
    """Authenticate and get token"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        return jsonify({'token': ADMIN_PASSWORD, 'message': 'Authentication successful'}), 200
    
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/api/clients', methods=['GET'])
@token_required
def get_clients():
    """Get all clients (with optional date range filter)"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Optional date range filter
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        query = 'SELECT * FROM Clients WHERE 1=1'
        params = []
        
        if start_date:
            query += ' AND VisitDate >= ?'
            params.append(start_date)
        if end_date:
            query += ' AND VisitDate <= ?'
            params.append(end_date)
        
        query += ' ORDER BY VisitDate DESC'
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        clients = [dict(row) for row in rows]
        
        conn.close()
        return jsonify(clients), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/clients/<int:client_id>', methods=['GET'])
@token_required
def get_client(client_id):
    """Get a specific client by ID"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM Clients WHERE ClientID = ?', (client_id,))
        row = cursor.fetchone()
        
        conn.close()
        
        if not row:
            return jsonify({'error': 'Client not found'}), 404
        
        return jsonify(dict(row)), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/clients', methods=['POST'])
@token_required
def create_client():
    """Create a new client record"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('FirstName') or not data.get('LastName'):
            return jsonify({'error': 'First Name and Last Name are required'}), 400
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO Clients (
                VisitDate, DriverLicenseNumber, FirstName, MiddleInitial, LastName,
                PhysicalAddress, City, State, ZipCode, County, CellPhone, Email,
                DateOfBirth, LanguageSpoken, MaritalStatus, Nationality_Race,
                CertificationStatus, IsVeteran, HowHeardAboutUs, HouseholdTotal, Notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('VisitDate', datetime.now().strftime("%m-%d-%Y")),
            data.get('DriverLicenseNumber'),
            data.get('FirstName'),
            data.get('MiddleInitial'),
            data.get('LastName'),
            data.get('PhysicalAddress'),
            data.get('City'),
            data.get('State'),
            data.get('ZipCode'),
            data.get('County'),
            data.get('CellPhone'),
            data.get('Email'),
            data.get('DateOfBirth'),
            data.get('LanguageSpoken'),
            data.get('MaritalStatus'),
            data.get('Nationality_Race'),
            data.get('CertificationStatus'),
            data.get('IsVeteran'),
            data.get('HowHeardAboutUs'),
            data.get('HouseholdTotal'),
            data.get('Notes')
        ))
        
        conn.commit()
        client_id = cursor.lastrowid
        conn.close()
        
        return jsonify({'id': client_id, 'message': 'Client created successfully'}), 201
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/clients/<int:client_id>', methods=['PUT'])
@token_required
def update_client(client_id):
    """Update an existing client record"""
    try:
        data = request.get_json()
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if client exists
        cursor.execute('SELECT * FROM Clients WHERE ClientID = ?', (client_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({'error': 'Client not found'}), 404
        
        # Build dynamic update query
        fields = []
        values = []
        for key, value in data.items():
            if key not in ('ClientID', 'CreatedAt'):
                fields.append(f'{key} = ?')
                values.append(value)
        
        values.append(client_id)
        
        if not fields:
            conn.close()
            return jsonify({'error': 'No fields to update'}), 400
        
        query = f'UPDATE Clients SET {", ".join(fields)} WHERE ClientID = ?'
        cursor.execute(query, values)
        
        conn.commit()
        conn.close()
        
        return jsonify({'message': 'Client updated successfully'}), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/clients/<int:client_id>', methods=['DELETE'])
@token_required
def delete_client(client_id):
    """Delete a client record"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if client exists
        cursor.execute('SELECT * FROM Clients WHERE ClientID = ?', (client_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({'error': 'Client not found'}), 404
        
        cursor.execute('DELETE FROM Clients WHERE ClientID = ?', (client_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'message': 'Client deleted successfully'}), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# STATISTICS ENDPOINT
# ============================================================================

@app.route('/api/statistics', methods=['GET'])
@token_required
def get_statistics():
    """Get summary statistics for all clients"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Optional date range filter
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        query = 'SELECT * FROM Clients WHERE 1=1'
        params = []
        
        if start_date:
            query += ' AND VisitDate >= ?'
            params.append(start_date)
        if end_date:
            query += ' AND VisitDate <= ?'
            params.append(end_date)
        
        cursor.execute(query, params)
        records = cursor.fetchall()
        
        # Calculate statistics (same logic as GUI)
        stats = {
            'total_clients': len(records),
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
        
        household_sizes = []
        
        for record in records:
            record_dict = dict(record)
            
            # Household size
            if record_dict.get('HouseholdTotal'):
                try:
                    household_sizes.append(int(record_dict['HouseholdTotal']))
                    stats['total_household'] += int(record_dict['HouseholdTotal'])
                except (ValueError, TypeError):
                    pass
            
            # Certification Status
            if record_dict.get('CertificationStatus'):
                certs = [c.strip() for c in str(record_dict['CertificationStatus']).split(',')]
                for cert in certs:
                    if cert:
                        stats['certification'][cert] = stats['certification'].get(cert, 0) + 1
            else:
                stats['certification'][''] = stats['certification'].get('', 0) + 1
            
            # Nationality/Race
            if record_dict.get('Nationality_Race'):
                races = [r.strip() for r in str(record_dict['Nationality_Race']).split(',')]
                for race in races:
                    if race:
                        stats['race'][race] = stats['race'].get(race, 0) + 1
            else:
                stats['race'][''] = stats['race'].get('', 0) + 1
            
            # Marital Status
            if record_dict.get('MaritalStatus'):
                marital = record_dict['MaritalStatus'].strip()
                stats['marital'][marital] = stats['marital'].get(marital, 0) + 1
            else:
                stats['marital'][''] = stats['marital'].get('', 0) + 1
            
            # Veteran Status
            if record_dict.get('IsVeteran'):
                veteran = record_dict['IsVeteran'].strip()
                if veteran == "Yes":
                    stats['veteran_yes'] += 1
                elif veteran == "No":
                    stats['veteran_no'] += 1
                else:
                    stats['veteran_unknown'] += 1
            else:
                stats['veteran_unknown'] += 1
            
            # How Heard About Us
            if record_dict.get('HowHeardAboutUs'):
                sources = [s.strip() for s in str(record_dict['HowHeardAboutUs']).split(',')]
                for source in sources:
                    if source:
                        stats['heard'][source] = stats['heard'].get(source, 0) + 1
            else:
                stats['heard'][''] = stats['heard'].get('', 0) + 1
        
        # Calculate average household size
        if household_sizes:
            stats['avg_household'] = sum(household_sizes) / len(household_sizes)
        
        conn.close()
        return jsonify(stats), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def server_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    # Initialize database
    init_database()
    print("=" * 60)
    print("I-70 Street Reach Food Bank - Network Database Server")
    print("=" * 60)
    print(f"Database: {DB_PATH}")
    print(f"Username: {ADMIN_USERNAME}")
    print(f"Password: {'*' * len(ADMIN_PASSWORD)}")
    print("=" * 60)
    print("Starting server on 0.0.0.0:5000...")
    print("Clients can connect to: http://<YOUR_SERVER_IP>:5000")
    print("=" * 60)
    
    # Run Flask app (0.0.0.0 makes it accessible from any network machine)
    app.run(host='0.0.0.0', port=5000, debug=False)
