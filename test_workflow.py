import unittest
import mysql.connector
import os
import sys
from werkzeug.security import check_password_hash

# Ensure templates directory is in python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'templates')))

from app import app, create_db_connection, conn as app_connection

class TestWorkforceWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Establish direct DB connection for cleanup/verification
        cls.db = create_db_connection()
        cls.cursor = cls.db.cursor(buffered=True)
        
        # Test accounts data
        cls.customer_phone = "9999999901"
        cls.customer_email = "customer@test.com"
        cls.worker_phone = "9999999902"
        cls.worker_email = "worker@test.com"
        
        # Pre-cleanup in case previous tests crashed
        cls.cleanup_test_data()

    @classmethod
    def tearDownClass(cls):
        # Post-cleanup
        cls.cleanup_test_data()
        cls.cursor.close()
        cls.db.close()

    @classmethod
    def cleanup_test_data(cls):
        try:
            print("\nCleaning up test data from database...")
            cls.db.rollback()
            
            # Find and delete bookings related to test accounts
            cls.cursor.execute("SELECT id FROM C_user_details WHERE Phone=%s", (cls.customer_phone,))
            cust = cls.cursor.fetchone()
            if cust:
                cls.cursor.execute("DELETE FROM bookings WHERE customer_id=%s", (cust[0],))
                
            cls.cursor.execute("SELECT id FROM W_user_details WHERE phone=%s", (cls.worker_phone,))
            wrk = cls.cursor.fetchone()
            if wrk:
                cls.cursor.execute("DELETE FROM bookings WHERE worker_id=%s", (wrk[0],))
            
            # Delete users
            cls.cursor.execute("DELETE FROM C_user_details WHERE Phone=%s OR Email=%s", (cls.customer_phone, cls.customer_email))
            cls.cursor.execute("DELETE FROM W_user_details WHERE phone=%s OR email=%s", (cls.worker_phone, cls.worker_email))
            cls.db.commit()
            print("Cleanup successful.")
        except Exception as e:
            print(f"Error during cleanup: {e}")

    def test_complete_flow(self):
        # Configure app for testing
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        
        # Create a client for the customer session
        customer_client = app.test_client()
        # Create a client for the worker session
        worker_client = app.test_client()
        # Create a client for the admin session
        admin_client = app.test_client()

        # ----------------------------------------------------
        # 1. Customer and Worker Registration
        # ----------------------------------------------------
        print("\nStep 1: Registering customer and worker...")
        
        # Register Customer
        cust_payload = {
            'Name': 'Test Customer',
            'Phone': self.customer_phone,
            'Email': self.customer_email,
            'Password': 'password123',
            'Location': 'Downtown Area'
        }
        response = customer_client.post('/c_user_details', data=cust_payload)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Customer registered successfully", response.data)
        self.cursor.execute("SELECT Password FROM C_user_details WHERE Phone=%s", (self.customer_phone,))
        customer_password_hash = self.cursor.fetchone()[0]
        self.assertTrue(check_password_hash(customer_password_hash, 'password123'))
        self.db.commit()

        # Register Worker
        work_payload = {
            'Name': 'Test Worker',
            'Phone': self.worker_phone,
            'Email': self.worker_email,
            'Password': 'password123',
            'Profession': 'Plumber',
            'Experience': '5',
            'Location': 'Uptown Area'
        }
        response = worker_client.post('/W_user_details', data=work_payload)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Worker registered successfully", response.data)
        self.cursor.execute("SELECT password FROM W_user_details WHERE phone=%s", (self.worker_phone,))
        self.assertTrue(check_password_hash(self.cursor.fetchone()[0], 'password123'))

        # Verify DB insertions
        self.cursor.execute("SELECT id, Name FROM C_user_details WHERE Phone=%s", (self.customer_phone,))
        customer_record = self.cursor.fetchone()
        self.assertIsNotNone(customer_record)
        customer_id = customer_record[0]
        print(f"Customer registered with ID: {customer_id}")

        self.cursor.execute("SELECT id, Name FROM W_user_details WHERE phone=%s", (self.worker_phone,))
        worker_record = self.cursor.fetchone()
        self.assertIsNotNone(worker_record)
        worker_id = worker_record[0]
        print(f"Worker registered with ID: {worker_id}")

        # ----------------------------------------------------
        # 2. Logins
        # ----------------------------------------------------
        print("\nStep 2: Logging in customer and worker...")
        
        # Login Customer
        response = customer_client.post('/login', data={
            'Phone': self.customer_phone,
            'Password': customer_password_hash
        })
        self.assertEqual(response.status_code, 200)
        app_connection.commit()
        self.cursor.execute(
            "UPDATE C_user_details SET Password=%s WHERE Phone=%s",
            ('password123', self.customer_phone)
        )
        self.db.commit()

        login_cust_payload = {
            'Phone': self.customer_phone,
            'Password': 'password123'
        }
        # We do POST /login, it should redirect to /dashboard
        response = customer_client.post('/login', data=login_cust_payload)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/dashboard'))
        self.cursor.execute("SELECT Password FROM C_user_details WHERE Phone=%s", (self.customer_phone,))
        self.assertTrue(check_password_hash(self.cursor.fetchone()[0], 'password123'))
        self.db.commit()

        # Verify Customer session access by getting profile API
        response = customer_client.get('/api/customer-profile')
        self.assertEqual(response.status_code, 200)
        profile_data = response.json
        self.assertTrue(profile_data['success'])
        self.assertEqual(profile_data['id'], customer_id)
        self.assertEqual(profile_data['name'], 'Test Customer')

        # Login Worker
        login_work_payload = {
            'Phone': self.worker_phone,
            'Password': 'password123'
        }
        # We do POST /login, it should redirect to /worker_dash
        response = worker_client.post('/login', data=login_work_payload)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/worker_dash'))

        # Verify Worker session access by getting profile API
        response = worker_client.get('/api/worker-profile')
        self.assertEqual(response.status_code, 200)
        worker_profile_data = response.json
        self.assertTrue(worker_profile_data['success'])
        self.assertEqual(worker_profile_data['id'], worker_id)
        self.assertEqual(worker_profile_data['name'], 'Test Worker')

        # ----------------------------------------------------
        # 3. Get Worker List (Customer side)
        # ----------------------------------------------------
        print("\nStep 3: Customer searching for available workers...")
        response = customer_client.get('/api/workers')
        self.assertEqual(response.status_code, 200)
        workers_list = response.json
        self.assertIsInstance(workers_list, list)
        
        # Check if our test worker is in the list
        test_worker_item = None
        for w in workers_list:
            if w['id'] == worker_id:
                test_worker_item = w
                break
        
        self.assertIsNotNone(test_worker_item)
        self.assertEqual(test_worker_item['name'], 'Test Worker')
        self.assertEqual(test_worker_item['profession'], 'Plumber')
        self.assertEqual(test_worker_item['price'], 300 + (5 * 50)) # 550 based on experience calculation

        # ----------------------------------------------------
        # 4. Booking Flow
        # ----------------------------------------------------
        print("\nStep 4: Customer booking worker...")
        book_payload = {
            'worker_id': worker_id,
            'worker_name': 'Test Worker',
            'profession': 'Plumber',
            'amount': test_worker_item['price'],
            'customer_location': 'Downtown Area',
            'customer_lat': 12.9715987,
            'customer_lng': 77.5945627,
            'worker_location': 'Uptown Area'
        }
        response = customer_client.post('/api/book-worker', json=book_payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['success'])
        
        # Verify active booking from customer's endpoint
        response = customer_client.get('/api/customer-booking')
        self.assertEqual(response.status_code, 200)
        active_booking = response.json
        self.assertTrue(active_booking['success'])
        booking_id = active_booking['booking_id']
        self.assertEqual(active_booking['worker_id'], worker_id)
        self.assertEqual(active_booking['status'], 'pending')
        print(f"Booking created successfully with ID: {booking_id}")

        # ----------------------------------------------------
        # 5. Worker accepts booking
        # ----------------------------------------------------
        print("\nStep 5: Worker fetching and accepting the job request...")
        
        # Get worker active bookings
        response = worker_client.get('/api/worker-bookings')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['success'])
        worker_bookings = response.json['bookings']
        self.assertGreater(len(worker_bookings), 0)
        self.assertEqual(worker_bookings[0]['booking_id'], booking_id)
        self.assertEqual(worker_bookings[0]['status'], 'pending')

        # Accept booking
        action_payload = {
            'booking_id': booking_id,
            'action': 'accept'
        }
        response = worker_client.post('/api/worker-booking-action', json=action_payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['success'])

        # Verify status is accepted from customer side
        response = customer_client.get('/api/customer-booking')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['status'], 'accepted')

        # ----------------------------------------------------
        # 6. Location Tracking Updates
        # ----------------------------------------------------
        print("\nStep 6: Simulating coordinates tracking updates...")
        
        # Worker updates location
        worker_loc_payload = {
            'booking_id': booking_id,
            'latitude': 12.9790,
            'longitude': 77.5912
        }
        response = worker_client.post('/api/update-worker-location', json=worker_loc_payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['success'])

        # Customer updates location
        cust_loc_payload = {
            'booking_id': booking_id,
            'customer_lat': 12.9715,
            'customer_lng': 77.5945,
            'customer_location': 'Downtown Shopping Mall'
        }
        response = customer_client.post('/api/update-customer-location', json=cust_loc_payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['success'])

        # Fetch and verify updated tracking coordinates
        response = customer_client.get('/api/customer-booking')
        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertEqual(data['worker_lat'], 12.9790)
        self.assertEqual(data['worker_lng'], 77.5912)
        self.assertEqual(data['customer_lat'], 12.9715)
        self.assertEqual(data['customer_lng'], 77.5945)
        self.assertEqual(data['customer_location'], 'Downtown Shopping Mall')

        # ----------------------------------------------------
        # 7. Complete Booking
        # ----------------------------------------------------
        print("\nStep 7: Worker completing the job...")
        complete_payload = {
            'booking_id': booking_id,
            'rating': 5,
            'feedback': 'Excellent service!'
        }
        response = worker_client.post('/api/complete-booking', json=complete_payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['success'])

        # Verify completed booking status
        response = customer_client.get('/api/customer-booking')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['status'], 'completed')

        # ----------------------------------------------------
        # 8. Admin Panel APIs
        # ----------------------------------------------------
        print("\nStep 8: Admin login and dashboard stats check...")
        
        admin_login_payload = {
            'Username': 'admin',
            'Password': 'admin123'
        }
        response = admin_client.post('/admin-login', data=admin_login_payload)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/admin'))

        # Fetch Admin Stats
        response = admin_client.get('/api/admin/stats')
        self.assertEqual(response.status_code, 200)
        stats = response.json
        self.assertIn('totalUsers', stats)
        self.assertIn('totalWorkers', stats)
        self.assertIn('totalBookings', stats)
        self.assertIn('totalRevenue', stats)
        self.assertGreater(stats['totalUsers'], 0)
        self.assertGreater(stats['totalWorkers'], 0)
        self.assertGreater(stats['totalBookings'], 0)

        # Fetch admin users list
        response = admin_client.get('/api/admin/users')
        self.assertEqual(response.status_code, 200)
        users = response.json
        self.assertGreater(len(users), 0)
        self.assertTrue(any(u['Phone'] == self.customer_phone for u in users))
        self.assertTrue(all('Password' not in user for user in users))

        # Fetch admin workers list
        response = admin_client.get('/api/admin/workers')
        self.assertEqual(response.status_code, 200)
        workers = response.json
        self.assertGreater(len(workers), 0)
        self.assertTrue(any(w['phone'] == self.worker_phone for w in workers))
        self.assertTrue(all('password' not in worker for worker in workers))

        print("\nAll integration flow steps passed successfully!")

if __name__ == '__main__':
    unittest.main()
