from flask import Flask,render_template,request,redirect,session
import mysql.connector
import os
template_dir = os.path.abspath('templates') if os.path.isdir('templates') else '.'
app=Flask(__name__, template_folder=template_dir)
app.secret_key = 'your_secret_key_here'


def create_db_connection():
    host = os.getenv('DB_HOST', '127.0.0.1')
    user = os.getenv('DB_USER', 'root')
    password = os.getenv('DB_PASSWORD', '')
    database = os.getenv('DB_NAME', 'work_force')
    try:
        return mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            connection_timeout=5
        )
    except mysql.connector.Error as err:
        print(f"Error connecting to MySQL at {host}: {err}")
        raise SystemExit(
            f"Database connection failed. Make sure MySQL is running and accessible on {host}:3306. Error: {err}"
        )

conn = create_db_connection()
cursor = conn.cursor(buffered=True)

# Worker Registration
@app.route('/W_user_details', methods=['POST'])
def insert():
    Name=request.form['Name']
    Phone=request.form['Phone']
    Email=request.form['Email']
    Password=request.form['Password']
    Profession=request.form['Profession']
    Experience=request.form['Experience']
    Location=request.form['Location']

    cursor.execute(
        "INSERT INTO W_user_details(Name,phone,password,email,profession,experience,location) VALUES(%s,%s,%s,%s,%s,%s,%s)",
        (Name,Phone,Password,Email,Profession,Experience,Location)
    )
    conn.commit()
    return render_template('login.html', success="Worker registered successfully! Please login.")

# Customer Registration
@app.route('/c_user_details', methods=['POST'])
def c_insert():
    Name=request.form['Name']
    Phone=request.form['Phone']
    Email=request.form['Email']
    Password=request.form['Password']
    Location=request.form['Location']
    cursor.execute(
        "INSERT INTO C_user_details(Name,Phone,Email,Password,Location) VALUES(%s,%s,%s,%s,%s)",
        (Name,Phone,Email,Password,Location)
    )
    conn.commit()
    return render_template('login.html', success="Customer registered successfully! Please login.")

# Login - GET to show form, POST to authenticate
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        Phone=request.form.get('Phone')
        Password=request.form.get('Password')
        
        print(f"\n=== Login Attempt ===")
        print(f"Phone: {Phone}, Password: {Password}")
        
        local_cursor = conn.cursor(buffered=True)
        try:
            # Check worker credentials
            local_cursor.execute("SELECT * FROM W_user_details WHERE phone=%s AND password=%s", (Phone, Password))
            worker = local_cursor.fetchone()
            print(f"Worker found: {worker is not None}")
            
            if worker:
                print(f"Worker data: {worker}")
                session['user_id'] = worker[7]  # ID is the last column (index 7)
                session['user_name'] = worker[0]  # Name is the first column (index 0)
                session['role'] = 'worker'
                print(f"Session set: user_id={session.get('user_id')}, user_name={session.get('user_name')}, role={session.get('role')}")
                return redirect('/worker_dash')
            
            # Check customer credentials
            local_cursor.execute("SELECT * FROM C_user_details WHERE Phone=%s AND Password=%s", (Phone, Password))
            customer = local_cursor.fetchone()
            print(f"Customer found: {customer is not None}")
            
            if customer:
                print(f"Customer data: {customer}")
                session['user_id'] = customer[0]  # id is first column
                session['user_name'] = customer[1]  # Name is second column
                session['role'] = 'customer'
                print(f"Session set: user_id={session.get('user_id')}, user_name={session.get('user_name')}, role={session.get('role')}")
                return redirect('/dashboard')
        finally:
            local_cursor.close()
        
        # Invalid credentials
        print("Invalid credentials")
        return render_template('login.html', error="Invalid credentials")
    
    return render_template('login.html')

# Worker Dashboard
@app.route('/worker_dash', methods=['GET'])
def worker_dashboard():
    print(f"Accessing worker_dash - Session: {dict(session)}")
    print(f"user_id in session: {'user_id' in session}")
    print(f"role in session: {session.get('role')}")
    
    if 'user_id' not in session or session.get('role') != 'worker':
        print("Session check failed, redirecting to login")
        return redirect('/login')
    
    print(f"Worker dashboard accessed by: {session.get('user_name')}")
    return render_template('worker_dash.html', user_name=session.get('user_name'))

# Customer Dashboard
@app.route('/dashboard', methods=['GET'])
def customer_dashboard():
    if 'user_id' not in session or session.get('role') != 'customer':
        return redirect('/login')
    return render_template('dashboard.html', user_name=session.get('user_name'))

@app.route('/api/customer-location', methods=['GET'])
def get_customer_location():
    try:
        customer_id = session.get('user_id')
        if not customer_id:
            return {'error': 'Not authenticated'}, 401
        
        cursor.execute("SELECT Location FROM C_user_details WHERE id=%s", (customer_id,))
        result = cursor.fetchone()
        
        if result:
            return {'success': True, 'location': result[0]}
        else:
            return {'success': False, 'error': 'Customer not found'}, 404
    except Exception as e:
        print(f"Error in get_customer_location: {e}")
        return {'error': str(e)}, 500

# Routes for dashboard navigation
@app.route('/api/customer-profile', methods=['GET'])
def get_customer_profile():
    try:
        customer_id = session.get('user_id')
        if not customer_id:
            return {'success': False, 'error': 'Not authenticated'}, 401
        
        cursor.execute("SELECT id, Name, Phone, Email, Location FROM C_user_details WHERE id=%s", (customer_id,))
        customer = cursor.fetchone()
        
        if not customer:
            return {'success': False, 'error': 'Customer not found'}, 404
        
        # Get booking statistics
        cursor.execute("""
            SELECT COUNT(*) as total_bookings,
                   SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed,
                   COALESCE(SUM(CASE WHEN status='completed' THEN amount ELSE 0 END), 0) as total_spent
            FROM bookings WHERE customer_id=%s
        """, (customer_id,))
        stats = cursor.fetchone()
        
        return {
            'success': True,
            'id': customer[0],
            'name': customer[1],
            'phone': customer[2],
            'email': customer[3],
            'location': customer[4],
            'total_bookings': stats[0] or 0,
            'completed_bookings': stats[1] or 0,
            'total_spent': float(stats[2]) if stats[2] else 0
        }
    except Exception as e:
        print(f"Error in get_customer_profile: {e}")
        return {'error': str(e)}, 500

@app.route('/api/update-customer-profile', methods=['POST'])
def update_customer_profile():
    try:
        customer_id = session.get('user_id')
        if not customer_id or session.get('role') != 'customer':
            return {'success': False, 'error': 'Not authorized'}, 401
        
        data = request.json
        email = data.get('email')
        location = data.get('location')
        
        cursor.execute(
            "UPDATE C_user_details SET Email=%s, Location=%s WHERE id=%s",
            (email, location, customer_id)
        )
        conn.commit()
        
        return {'success': True, 'message': 'Profile updated successfully'}
    except Exception as e:
        print(f"Error in update_customer_profile: {e}")
        return {'error': str(e)}, 500

@app.route('/profile.html')
def profile():
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('profile.html')

@app.route('/services.html')
def services():
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('services.html')

@app.route('/contact.html')
def contact():
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('contact.html')

@app.route('/payment.html')
def payment():
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('payment.html')

@app.route('/tracking.html')
def tracking():
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('tracking.html')

@app.route('/complete.html')
def complete():
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('complete.html')

@app.route('/W_tracking.html')
def w_tracking():
    if 'user_id' not in session or session.get('role') != 'worker':
        return redirect('/login')
    return render_template('W_tracking.html')

@app.route('/login.html', methods=['GET', 'POST'])
def login_html():
    return redirect('/login')

@app.route('/register')
@app.route('/register.html')
def register_page():
    return render_template('register.html')

# Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# Admin routes
@app.route('/admin')
def admin():
    if not session.get('admin'):
        return redirect('/admin_login')
    return render_template('admin.html')

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login_page():
    if request.method == 'POST':
        username = request.form.get('Username')
        password = request.form.get('Password')
        
        # Simple admin authentication (in production, use proper database authentication)
        if username == 'admin' and password == 'admin123':
            session['admin'] = True
            return redirect('/admin')
        else:
            return render_template('admin_login.html', error="Invalid admin credentials")
    
    return render_template('admin_login.html')

@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('Username')
        password = request.form.get('Password')
        
        # Simple admin authentication (in production, use proper database authentication)
        if username == 'admin' and password == 'admin123':
            session['admin'] = True
            return redirect('/admin')
        else:
            return render_template('admin_login.html', error="Invalid admin credentials")
    
    return render_template('admin_login.html')

@app.route('/api/admin/stats')
def admin_stats():
    try:
        # Get total users
        cursor.execute("SELECT COUNT(*) FROM C_user_details")
        total_users = cursor.fetchone()[0]
        
        # Get total workers
        cursor.execute("SELECT COUNT(*) FROM W_user_details")
        total_workers = cursor.fetchone()[0]
        
        # Ensure bookings table exists with proper schema
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bookings (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    customer_id INT,
                    customer_name VARCHAR(255),
                    customer_location VARCHAR(255),
                    worker_id INT,
                    worker_name VARCHAR(255),
                    worker_location VARCHAR(255),
                    worker_lat DOUBLE,
                    worker_lng DOUBLE,
                    service VARCHAR(255),
                    amount DECIMAL(10, 2),
                    status VARCHAR(50) DEFAULT 'pending',
                    booking_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
        except mysql.connector.Error:
            pass
        
        # Get total bookings
        cursor.execute("SELECT COUNT(*) FROM bookings")
        total_bookings = cursor.fetchone()[0]
        
        # Get total revenue
        cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM bookings WHERE status='completed'")
        total_revenue = cursor.fetchone()[0]
        
        return {
            'totalUsers': total_users,
            'totalWorkers': total_workers,
            'totalBookings': total_bookings,
            'totalRevenue': float(total_revenue)
        }
    except Exception as e:
        print(f"Error in admin_stats: {e}")
        return {'error': 'Database error'}, 500

@app.route('/api/admin/users')
def admin_users():
    try:
        cursor.execute("SELECT * FROM C_user_details")
        users = cursor.fetchall()
        
        # Convert to list of dicts
        user_list = []
        for user in users:
            user_list.append({
                'id': user[0],
                'Name': user[1],
                'Phone': user[2],
                'Email': user[3],
                'Password': user[4],  # Note: In production, don't send passwords
                'Location': user[5]
            })
        
        return user_list
    except Exception as e:
        print(f"Error in admin_users: {e}")
        return {'error': 'Database error'}, 500

@app.route('/api/admin/workers')
def admin_workers():
    try:
        cursor.execute("SELECT * FROM W_user_details")
        workers = cursor.fetchall()
        
        # Convert to list of dicts
        worker_list = []
        for worker in workers:
            worker_list.append({
                'id': worker[7],  # id is the last column
                'Name': worker[0],
                'phone': worker[1],
                'password': worker[2],  # Note: In production, don't send passwords
                'email': worker[3],
                'profession': worker[4],
                'experience': worker[5],
                'location': worker[6]
            })
        
        return worker_list
    except Exception as e:
        print(f"Error in admin_workers: {e}")
        return {'error': 'Database error'}, 500

@app.route('/api/admin/bookings')
def admin_bookings():
    try:
        # Ensure bookings table exists with proper schema
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bookings (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    customer_id INT,
                    customer_name VARCHAR(255),
                    customer_location VARCHAR(255),
                    worker_id INT,
                    worker_name VARCHAR(255),
                    worker_location VARCHAR(255),
                    worker_lat DOUBLE,
                    worker_lng DOUBLE,
                    service VARCHAR(255),
                    amount DECIMAL(10, 2),
                    status VARCHAR(50) DEFAULT 'pending',
                    booking_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
        except mysql.connector.Error:
            pass
        
        # Get all bookings
        cursor.execute("SELECT * FROM bookings ORDER BY booking_date DESC")
        bookings = cursor.fetchall()
        
        booking_list = []
        for booking in bookings:
            booking_list.append({
                'id': booking[0],
                'customer_name': booking[2],
                'customer_location': booking[3],
                'worker_name': booking[5],
                'worker_location': booking[6],
                'service': booking[9],
                'amount': float(booking[10]),
                'status': booking[11],
                'date': str(booking[12])
            })
        
        return booking_list
    except Exception as e:
        print(f"Error in admin_bookings: {e}")
        return {'error': 'Database error'}, 500

@app.route('/api/workers')
def get_workers():
    try:
        local_cursor = conn.cursor(buffered=True)
        try:
            local_cursor.execute("SELECT id, Name, phone, email, profession, experience, location FROM W_user_details")
            workers = local_cursor.fetchall()
        finally:
            local_cursor.close()
        
        worker_list = []
        for worker in workers:
            # Map columns according to the SELECT order:
            # id, Name, phone, email, profession, experience, location
            wid = worker[0]
            name = worker[1]
            phone = worker[2]
            email = worker[3]
            profession = worker[4]
            experience = worker[5]
            location = worker[6]

            # Safely coerce experience to int when possible
            try:
                exp_int = int(experience) if experience is not None else 0
            except (ValueError, TypeError):
                exp_int = 0

            worker_list.append({
                'id': wid,
                'name': name,
                'phone': phone,
                'email': email,
                'profession': profession,
                'experience': experience,
                'location': location,
                'price': 300 + (exp_int * 50),  # Calculate price based on experience
                'rating': min(5.0, 3.5 + (exp_int * 0.2)),  # Calculate rating and cap at 5.0
                'distance': 2  # Default distance, can be calculated based on customer location
            })
        
        return worker_list
    except Exception as e:
        print(f"Error in get_workers: {e}")
        return {'error': 'Database error'}, 500

@app.route('/api/book-worker', methods=['POST'])
def book_worker():
    try:
        data = request.json
        customer_id = session.get('user_id')
        customer_name = session.get('user_name')
        worker_id = data.get('worker_id')
        worker_name = data.get('worker_name')
        service = data.get('profession', 'General Service')
        amount = data.get('amount', 300)
        customer_location = data.get('customer_location')
        customer_lat = data.get('customer_lat')
        customer_lng = data.get('customer_lng')
        worker_location = data.get('worker_location')

        if not customer_id or session.get('role') != 'customer':
            return {'success': False, 'error': 'Customer login required to book a worker.'}, 401
        if not worker_id:
            return {'success': False, 'error': 'Invalid worker selected.'}, 400
        if not customer_location or customer_location == 'Not available':
            return {'success': False, 'error': 'Valid customer location required.'}, 400
        
        print(f"\n=== BOOKING CREATION ===")
        print(f"Customer ID: {customer_id}")
        print(f"Customer Name: {customer_name}")
        print(f"Worker ID: {worker_id}")
        print(f"Worker Name: {worker_name}")
        print(f"Customer Location: {customer_location}")
        print(f"Customer Lat/Lng: {customer_lat}/{customer_lng}")
        print(f"Worker Location: {worker_location}")
        
        local_cursor = conn.cursor(buffered=True)
        try:
            # Create bookings table if it doesn't exist (DON'T DROP IT)
            local_cursor.execute("""
                CREATE TABLE IF NOT EXISTS bookings (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    customer_id INT,
                    customer_name VARCHAR(255),
                    customer_location VARCHAR(255),
                    customer_lat DOUBLE,
                    customer_lng DOUBLE,
                    worker_id INT,
                    worker_name VARCHAR(255),
                    worker_location VARCHAR(255),
                    worker_lat DOUBLE,
                    worker_lng DOUBLE,
                    service VARCHAR(255),
                    amount DECIMAL(10, 2),
                    status VARCHAR(50) DEFAULT 'pending',
                    booking_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            print("Ensured bookings table exists")
            
            # Check and add missing location columns for older schema versions
            missing_columns = [
                ('customer_location', 'VARCHAR(255)'),
                ('customer_lat', 'DOUBLE'),
                ('customer_lng', 'DOUBLE'),
                ('worker_location', 'VARCHAR(255)'),
                ('worker_lat', 'DOUBLE'),
                ('worker_lng', 'DOUBLE'),
                ('rating', 'INT'),
                ('feedback', 'TEXT')
            ]
            for column_name, column_type in missing_columns:
                local_cursor.execute("SHOW COLUMNS FROM bookings LIKE %s", (column_name,))
                if local_cursor.fetchone() is None:
                    try:
                        print(f"Adding missing bookings column: {column_name}")
                        local_cursor.execute(f"ALTER TABLE bookings ADD COLUMN {column_name} {column_type}")
                        conn.commit()
                    except mysql.connector.Error as e:
                        print(f"Error adding column {column_name}: {e}")
            print("Booking table schema ensured")
            
            # Insert booking with locations
            local_cursor.execute(
                "INSERT INTO bookings (customer_id, customer_name, customer_location, customer_lat, customer_lng, worker_id, worker_name, worker_location, worker_lat, worker_lng, service, amount, status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')",
                (customer_id, customer_name, customer_location, customer_lat, customer_lng, worker_id, worker_name, worker_location, None, None, service, amount)
            )
            conn.commit()
            print(f"Booking inserted successfully")
            
            # Verify booking was created
            local_cursor.execute("SELECT * FROM bookings WHERE customer_id=%s ORDER BY booking_date DESC LIMIT 1", (customer_id,))
            inserted_booking = local_cursor.fetchone()
            print(f"Verification - Booking in DB: {inserted_booking}")
            print(f"=== BOOKING COMPLETE ===\n")
        finally:
            local_cursor.close()
        
        return {'success': True, 'message': 'Booking created successfully', 'worker_location': worker_location}
    except Exception as e:
        print(f"Error in book_worker: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}, 500

@app.route('/api/complete-booking', methods=['POST'])
def complete_booking():
    try:
        data = request.json
        booking_id = data.get('booking_id')
        rating = data.get('rating', 0)
        feedback = data.get('feedback', '')
        user_id = session.get('user_id')
        role = session.get('role')
        
        if not user_id:
            return {'success': False, 'error': 'Not authenticated'}, 401
            
        local_cursor = conn.cursor(buffered=True)
        try:
            if role == 'customer':
                # Customer submitting review
                # If booking_id not provided, find the latest active/paid/completed booking for the customer
                if not booking_id:
                    local_cursor.execute("""
                        SELECT id FROM bookings 
                        WHERE customer_id=%s AND status IN ('pending', 'accepted', 'arrived', 'paid', 'completed') 
                        ORDER BY booking_date DESC LIMIT 1
                    """, (user_id,))
                    res = local_cursor.fetchone()
                    if res:
                        booking_id = res[0]
                
                if not booking_id:
                    return {'success': False, 'error': 'No active booking found'}, 404
                    
                local_cursor.execute("""
                    UPDATE bookings
                    SET status='completed', rating=%s, feedback=%s
                    WHERE id=%s AND customer_id=%s
                """, (rating, feedback, booking_id, user_id))
                conn.commit()
                return {'success': True, 'message': 'Review submitted and booking completed'}
                
            else:
                # Worker completing booking
                if not booking_id:
                    return {'success': False, 'error': 'Invalid booking ID'}, 400
                local_cursor.execute("""
                    UPDATE bookings
                    SET status='completed'
                    WHERE id=%s AND worker_id=%s AND status IN ('pending', 'accepted', 'arrived', 'paid')
                """, (booking_id, user_id))
                conn.commit()
                
                if local_cursor.rowcount == 0:
                    return {'success': False, 'error': 'Booking not found or already completed'}, 404
                
                return {'success': True, 'message': 'Booking marked as completed'}
        finally:
            local_cursor.close()
    except Exception as e:
        print(f"Error in complete_booking: {e}")
        return {'success': False, 'error': str(e)}, 500

@app.route('/api/mark-worker-arrived', methods=['POST'])
def mark_worker_arrived():
    try:
        data = request.json
        booking_id = data.get('booking_id')
        
        if not booking_id:
            return {'success': False, 'error': 'Invalid booking ID'}, 400
            
        local_cursor = conn.cursor(buffered=True)
        try:
            local_cursor.execute("""
                UPDATE bookings
                SET status='arrived'
                WHERE id=%s AND status IN ('pending', 'accepted')
            """, (booking_id,))
            conn.commit()
        finally:
            local_cursor.close()
        return {'success': True, 'message': 'Worker marked as arrived'}
    except Exception as e:
        print(f"Error in mark_worker_arrived: {e}")
        return {'success': False, 'error': str(e)}, 500

@app.route('/api/pay-booking', methods=['POST'])
def pay_booking():
    try:
        data = request.json
        booking_id = data.get('booking_id')
        
        if not booking_id:
            return {'success': False, 'error': 'Invalid booking ID'}, 400
            
        local_cursor = conn.cursor(buffered=True)
        try:
            local_cursor.execute("""
                UPDATE bookings
                SET status='paid'
                WHERE id=%s AND status IN ('pending', 'accepted', 'arrived')
            """, (booking_id,))
            conn.commit()
        finally:
            local_cursor.close()
        return {'success': True, 'message': 'Booking paid successfully'}
    except Exception as e:
        print(f"Error in pay_booking: {e}")
        return {'success': False, 'error': str(e)}, 500

@app.route('/api/check-payment', methods=['GET', 'POST'])
def check_payment():
    try:
        if request.method == 'POST':
            data = request.json or {}
            booking_id = data.get('booking_id')
        else:
            booking_id = request.args.get('booking_id')
            
        worker_id = session.get('user_id')
        
        local_cursor = conn.cursor(buffered=True)
        try:
            if not booking_id:
                # Try to get the latest booking for the worker
                local_cursor.execute("""
                    SELECT id, status FROM bookings
                    WHERE worker_id=%s
                    ORDER BY booking_date DESC LIMIT 1
                """, (worker_id,))
                res = local_cursor.fetchone()
                if res:
                    booking_id = res[0]
                    status = res[1]
                else:
                    return {'success': False, 'error': 'No active bookings found'}, 404
            else:
                local_cursor.execute("SELECT status FROM bookings WHERE id=%s", (booking_id,))
                res = local_cursor.fetchone()
                if res:
                    status = res[0]
                else:
                    return {'success': False, 'error': 'Booking not found'}, 404
        finally:
            local_cursor.close()
                
        is_paid = (status in ('paid', 'completed'))
        return {'success': True, 'booking_id': booking_id, 'status': status, 'paid': is_paid}
    except Exception as e:
        print(f"Error in check_payment: {e}")
        return {'success': False, 'error': str(e)}, 500

@app.route('/api/update-worker-location', methods=['POST'])
def update_worker_location():
    try:
        data = request.json
        booking_id = data.get('booking_id')
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        worker_id = session.get('user_id')

        if latitude is None or longitude is None:
            return {'success': False, 'error': 'Missing coordinates'}, 400

        worker_location = f"{latitude:.5f}, {longitude:.5f}"
        if booking_id:
            cursor.execute(
                "UPDATE bookings SET worker_lat=%s, worker_lng=%s, worker_location=%s WHERE id=%s AND worker_id=%s AND status IN ('accepted','pending')",
                (latitude, longitude, worker_location, booking_id, worker_id)
            )
        else:
            cursor.execute(
                "UPDATE bookings SET worker_lat=%s, worker_lng=%s, worker_location=%s WHERE worker_id=%s AND status='accepted'",
                (latitude, longitude, worker_location, worker_id)
            )
        conn.commit()

        return {'success': True}
    except Exception as e:
        print(f"Error in update_worker_location: {e}")
        return {'success': False, 'error': str(e)}, 500

@app.route('/api/update-customer-location', methods=['POST'])
def update_customer_location():
    try:
        data = request.json
        booking_id = data.get('booking_id')
        latitude = data.get('customer_lat')
        longitude = data.get('customer_lng')
        location_text = data.get('customer_location')
        customer_id = session.get('user_id')

        if latitude is None or longitude is None:
            return {'success': False, 'error': 'Missing customer coordinates'}, 400

        if booking_id:
            cursor.execute(
                "UPDATE bookings SET customer_lat=%s, customer_lng=%s, customer_location=%s WHERE id=%s AND customer_id=%s AND status IN ('pending','accepted')",
                (latitude, longitude, location_text, booking_id, customer_id)
            )
        else:
            cursor.execute(
                "UPDATE bookings SET customer_lat=%s, customer_lng=%s, customer_location=%s WHERE customer_id=%s AND status IN ('pending','accepted')",
                (latitude, longitude, location_text, customer_id)
            )
        conn.commit()

        return {'success': True}
    except Exception as e:
        print(f"Error in update_customer_location: {e}")
        return {'success': False, 'error': str(e)}, 500

@app.route('/api/customer-booking', methods=['GET'])
def get_customer_booking():
    try:
        customer_id = session.get('user_id')
        
        print(f"DEBUG: Fetching booking for customer_id: {customer_id}")
        
        if not customer_id:
            print("DEBUG: No customer_id in session")
            return {'success': False, 'error': 'Not authenticated', 'bookings': []}
        
        # Get active booking for customer with worker location, coordinates, and customer address
        local_cursor = conn.cursor(buffered=True)
        try:
            local_cursor.execute("""
                SELECT id, worker_id, worker_name, worker_location, worker_lat, worker_lng, customer_location, customer_lat, customer_lng, service, amount, status, booking_date
                FROM bookings 
                WHERE customer_id=%s AND status IN ('pending', 'accepted', 'arrived', 'paid', 'completed')
                ORDER BY booking_date DESC
                LIMIT 1
            """, (customer_id,))
            
            booking = local_cursor.fetchone()
            
            print(f"DEBUG: Booking found: {booking}")
            
            if booking:
                return {
                    'success': True,
                    'booking_id': booking[0],
                    'worker_id': booking[1],
                    'worker_name': booking[2],
                    'worker_location': booking[3],
                    'worker_lat': booking[4],
                    'worker_lng': booking[5],
                    'customer_location': booking[6],
                    'customer_lat': booking[7],
                    'customer_lng': booking[8],
                    'service': booking[9],
                    'amount': float(booking[10]),
                    'status': booking[11],
                    'booking_date': str(booking[12])
                }
            else:
                # Return all bookings for debugging
                local_cursor.execute("SELECT COUNT(*) FROM bookings")
                total = local_cursor.fetchone()[0]
                print(f"DEBUG: No booking found. Total bookings in DB: {total}")
                
                return {'success': False, 'message': 'No active booking', 'debug_total_bookings': total}
        finally:
            local_cursor.close()
    except Exception as e:
        print(f"Error in get_customer_booking: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e), 'success': False}, 500

@app.route('/api/worker-profile', methods=['GET'])
def get_worker_profile():
    try:
        worker_id = session.get('user_id')
        if not worker_id:
            return {'success': False, 'error': 'Not authenticated'}, 401
        
        cursor.execute("""
            SELECT id, Name, phone, email, profession, experience, location 
            FROM W_user_details WHERE id=%s
        """, (worker_id,))
        worker = cursor.fetchone()
        
        if not worker:
            return {'success': False, 'error': 'Worker not found'}, 404
        
        # Get booking statistics
        cursor.execute("""
            SELECT COUNT(*) as total_jobs,
                   SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed_jobs,
                   COALESCE(SUM(CASE WHEN status='completed' THEN amount ELSE 0 END), 0) as total_earned
            FROM bookings WHERE worker_id=%s
        """, (worker_id,))
        stats = cursor.fetchone()
        
        # Calculate rating (based on completed bookings, default 4.0)
        rating = 4.0 + (int(worker[5]) * 0.1) if worker[5] else 4.0
        
        return {
            'success': True,
            'id': worker[0],
            'name': worker[1],
            'phone': worker[2],
            'email': worker[3],
            'profession': worker[4],
            'experience': worker[5],
            'location': worker[6],
            'total_jobs': stats[0] or 0,
            'completed_jobs': stats[1] or 0,
            'total_earned': float(stats[2]) if stats[2] else 0,
            'rating': min(5.0, rating),
            'hourly_rate': 300 + (int(worker[5]) * 50) if worker[5] else 300
        }
    except Exception as e:
        print(f"Error in get_worker_profile: {e}")
        return {'error': str(e)}, 500

@app.route('/api/update-worker-profile', methods=['POST'])
def update_worker_profile():
    try:
        worker_id = session.get('user_id')
        if not worker_id or session.get('role') != 'worker':
            return {'success': False, 'error': 'Not authorized'}, 401
        
        data = request.json
        email = data.get('email')
        location = data.get('location')
        profession = data.get('profession')
        
        cursor.execute(
            "UPDATE W_user_details SET email=%s, location=%s, profession=%s WHERE id=%s",
            (email, location, profession, worker_id)
        )
        conn.commit()
        
        return {'success': True, 'message': 'Profile updated successfully'}
    except Exception as e:
        print(f"Error in update_worker_profile: {e}")
        return {'error': str(e)}, 500

@app.route('/api/worker-bookings', methods=['GET'])
def get_worker_bookings():
    try:
        worker_id = session.get('user_id')
        
        local_cursor = conn.cursor(buffered=True)
        try:
            # Get active bookings for worker with customer location
            local_cursor.execute("""
                SELECT id, customer_id, customer_name, customer_location, customer_lat, customer_lng, worker_location, worker_lat, worker_lng, service, amount, status, booking_date, worker_name
                FROM bookings 
                WHERE worker_id=%s AND status IN ('pending', 'accepted', 'arrived', 'paid')
                ORDER BY booking_date DESC
            """, (worker_id,))
            
            bookings = local_cursor.fetchall()
        finally:
            local_cursor.close()
        
        booking_list = []
        for booking in bookings:
            booking_list.append({
                'booking_id': booking[0],
                'customer_id': booking[1],
                'customer_name': booking[2],
                'customer_location': booking[3],
                'customer_lat': booking[4],
                'customer_lng': booking[5],
                'worker_location': booking[6],
                'worker_lat': booking[7],
                'worker_lng': booking[8],
                'service': booking[9],
                'amount': float(booking[10]),
                'status': booking[11],
                'booking_date': str(booking[12]),
                'worker_name': booking[13]
            })
        
        return {'success': True, 'bookings': booking_list}
    except Exception as e:
        print(f"Error in get_worker_bookings: {e}")
        return {'error': str(e)}, 500

@app.route('/api/worker-booking-action', methods=['POST'])
def worker_booking_action():
    try:
        data = request.json
        booking_id = data.get('booking_id')
        action = data.get('action')
        worker_id = session.get('user_id')
        
        if not booking_id or action not in ('accept', 'reject'):
            return {'success': False, 'error': 'Invalid request'}, 400
        
        if action == 'accept':
            cursor.execute(
                "UPDATE bookings SET status='accepted' WHERE id=%s AND worker_id=%s AND status='pending'",
                (booking_id, worker_id)
            )
        else:
            cursor.execute(
                "UPDATE bookings SET status='rejected' WHERE id=%s AND worker_id=%s AND status='pending'",
                (booking_id, worker_id)
            )
        conn.commit()
        
        return {'success': True, 'message': f'Booking {action}ed successfully'}
    except Exception as e:
        print(f"Error in worker_booking_action: {e}")
        return {'success': False, 'error': str(e)}, 500

# Home - Landing Page
@app.route('/')
def home():
    return render_template('landing.html')

if __name__ == '__main__':
    app.run(debug=True)