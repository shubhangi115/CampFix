"""Create one administrator from the project root: python -m scripts.create_admin."""

from getpass import getpass

from mysql.connector import Error, errorcode
from pydantic import TypeAdapter, ValidationError

from backend.auth import hasher
from backend.database import db
from backend.schemas import Email


def main():
    try:
        email = TypeAdapter(Email).validate_python(input("Administrator email: ").strip()).lower()
    except ValidationError:
        raise SystemExit("Enter a valid administrator email.") from None

    password = getpass("Administrator password (8–128 characters): ")
    confirmation = getpass("Confirm password: ")
    if not 8 <= len(password) <= 128 or not password.strip() or password != confirmation:
        raise SystemExit("Enter a valid password and make sure both passwords match.")

    try:
        with db() as cursor:
            cursor.execute(
                "INSERT INTO admins (email, password_hash) VALUES (%s, %s)",
                (email, hasher.hash(password)),
            )
    except Error as exc:
        if exc.errno == errorcode.ER_DUP_ENTRY:
            raise SystemExit("An administrator already uses that email.") from None
        raise SystemExit(f"MySQL operation failed (error {exc.errno}). Check your configuration.") from None
    print(f"Administrator created for {email}.")


if __name__ == "__main__":
    main()
