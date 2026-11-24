import csv
import secrets
from pathlib import Path

from werkzeug.security import generate_password_hash


FIRST_NAMES = [
    "Aarav", "Aditi", "Ajay", "Ananya", "Arjun", "Deepa", "Dev", "Divya",
    "Gaurav", "Isha", "Karan", "Kavita", "Manish", "Meera", "Neha", "Nikhil",
    "Pooja", "Rahul", "Riya", "Rohan", "Sanjay", "Shreya", "Suresh", "Tara",
    "Vikram", "Anil", "Bhavna", "Chitra", "Dhruv", "Geeta", "Harish", "Indu",
    "Jay", "Kiran", "Lakshmi", "Mohan", "Nandini", "Prakash", "Rekha", "Varun",
]

LAST_NAMES = [
    "Sharma", "Patel", "Kumar", "Singh", "Reddy", "Nair", "Iyer", "Das",
    "Joshi", "Mehta", "Rao", "Gupta", "Verma", "Pillai", "Chowdhury",
    "Mishra", "Desai", "Khan", "Kulkarni", "Banerjee", "Shetty", "Kapoor",
    "Malhotra", "Bose", "Jain",
]

LOCATIONS = [
    "Bengaluru", "Mumbai", "Delhi", "Chennai", "Hyderabad", "Pune", "Kolkata",
    "Jaipur", "Ahmedabad", "Lucknow", "Indore", "Kochi", "Bhopal", "Patna",
    "Surat", "Nagpur", "Coimbatore", "Mysuru", "Chandigarh", "Visakhapatnam",
]

PROFESSIONS = [
    "Plumber", "Electrician", "Gardener", "Driver", "Bathroom Cleaner",
    "Carpenter", "Painter", "Mason", "House Cleaner", "AC Technician",
]

CSV_COLUMNS = [
    "role", "name", "phone", "email", "password", "profession", "experience",
    "location",
]
ACCOUNTS_PER_ROLE = 100


def build_name(index):
    return f"{FIRST_NAMES[index // len(LAST_NAMES)]} {LAST_NAMES[index % len(LAST_NAMES)]}"


def build_accounts():
    customers = []
    workers = []
    credentials = []

    for index in range(ACCOUNTS_PER_ROLE):
        name = build_name(index)
        phone = f"{index + 1:010d}"
        email = f"customer{index + 1:04d}@example.invalid"
        password = secrets.token_urlsafe(18)
        location = LOCATIONS[index % len(LOCATIONS)]
        customers.append(
            (name, phone, email, generate_password_hash(password), location)
        )
        credentials.append({
            "role": "customer",
            "name": name,
            "phone": phone,
            "email": email,
            "password": password,
            "profession": "",
            "experience": "",
            "location": location,
        })

    for index in range(ACCOUNTS_PER_ROLE):
        name = build_name(index + 500)
        phone = f"{index + 501:010d}"
        email = f"worker{index + 1:04d}@example.invalid"
        password = secrets.token_urlsafe(18)
        profession = PROFESSIONS[index % len(PROFESSIONS)]
        experience = str(index % 20 + 1)
        location = LOCATIONS[(index * 7) % len(LOCATIONS)]
        workers.append((
            name,
            phone,
            generate_password_hash(password),
            email,
            profession,
            experience,
            location,
        ))
        credentials.append({
            "role": "worker",
            "name": name,
            "phone": phone,
            "email": email,
            "password": password,
            "profession": profession,
            "experience": experience,
            "location": location,
        })

    return customers, workers, credentials


def ensure_no_conflicts(cursor, table, phone_column, email_column, records):
    phones = [record[1] for record in records]
    emails = [record[2] if table == "C_user_details" else record[3] for record in records]
    phone_placeholders = ", ".join(["%s"] * len(phones))
    email_placeholders = ", ".join(["%s"] * len(emails))
    cursor.execute(
        f"SELECT COUNT(*) FROM {table} "
        f"WHERE {phone_column} IN ({phone_placeholders}) "
        f"OR {email_column} IN ({email_placeholders})",
        phones + emails,
    )
    conflicts = cursor.fetchone()[0]
    if conflicts:
        raise RuntimeError(
            f"Found {conflicts} existing {table} rows using generated demo phone/email values; "
            "no records were inserted."
        )


def main():
    output_path = Path(__file__).resolve().with_name("seeded_user_credentials.csv")
    temporary_path = output_path.with_suffix(".csv.tmp")
    if output_path.exists():
        raise FileExistsError(
            f"{output_path.name} already exists; move it securely before generating new credentials."
        )
    if temporary_path.exists():
        raise FileExistsError(f"{temporary_path.name} already exists; remove it before retrying.")

    customers, workers, credentials = build_accounts()

    import app as workforce_app

    connection = workforce_app.conn
    cursor = connection.cursor(buffered=True)
    temporary_created = False
    committed = False
    try:
        with temporary_path.open("x", encoding="utf-8-sig", newline="") as credentials_file:
            temporary_created = True
            writer = csv.DictWriter(credentials_file, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            writer.writerows(credentials)
            credentials_file.flush()

        connection.start_transaction()
        ensure_no_conflicts(cursor, "C_user_details", "Phone", "Email", customers)
        ensure_no_conflicts(cursor, "W_user_details", "phone", "email", workers)
        cursor.executemany(
            "INSERT INTO C_user_details(Name, Phone, Email, Password, Location) "
            "VALUES(%s, %s, %s, %s, %s)",
            customers,
        )
        cursor.executemany(
            "INSERT INTO W_user_details(Name, phone, password, email, profession, experience, location) "
            "VALUES(%s, %s, %s, %s, %s, %s, %s)",
            workers,
        )
        connection.commit()
        committed = True
        temporary_path.replace(output_path)
    except Exception:
        if not committed:
            connection.rollback()
        if not committed and temporary_created and temporary_path.exists():
            temporary_path.unlink()
        raise
    finally:
        cursor.close()
        workforce_app.cursor.close()
        connection.close()

    print(
        f"Inserted {ACCOUNTS_PER_ROLE} customers and {ACCOUNTS_PER_ROLE} workers "
        "into the configured database."
    )
    print(f"Credentials saved locally to: {output_path}")


if __name__ == "__main__":
    main()
