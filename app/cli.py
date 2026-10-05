"""Local administrative bootstrap; passwords are read without terminal echo."""
import argparse
import getpass
from app.database import SessionLocal
from app.models import User, RoleEnum
from app.security import hash_password

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["create-super-admin"])
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    password = getpass.getpass("Password (8-72 UTF-8 bytes): ")
    if len(password) < 8 or len(password.encode("utf-8")) > 72:
        parser.error("Password must be 8-72 UTF-8 bytes")
    if password != getpass.getpass("Confirm password: "):
        parser.error("Passwords do not match")
    with SessionLocal() as db:
        if db.query(User).filter_by(email=args.email).first(): parser.error("Email already exists")
        db.add(User(full_name=args.name, email=args.email, password=hash_password(password), role=RoleEnum.super_admin, is_active=True))
        db.commit()
    print("Super admin created")

if __name__ == "__main__": main()
