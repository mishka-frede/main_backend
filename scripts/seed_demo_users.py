import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import SessionLocal
from app.models.address import Address
from app.models.user import User
from app.models.user_address import UserAddress
from app.security.hashing import hash_password
from app.services.user_roles import clear_user_addresses
from scripts.seed_test_data import ADDRESSES
from scripts.seed_test_data import USER_ADDRESS_LINKS
from scripts.seed_test_data import USERS
from scripts.seed_test_data import seed_roles


def sync_user(db, spec):
    user = db.query(User).filter(User.email == spec["email"]).first()

    if user is None:
        user = User(email=spec["email"])
        db.add(user)

    user.full_name = spec["full_name"]
    user.phone = spec.get("phone", "")
    user.password_hash = hash_password(spec["password"][:72])
    user.role = spec["role"]
    user.is_active = True

    db.flush()

    if spec["role"] != "resident":
        user.address_id = None
        clear_user_addresses(db, user.id)

    return user


def sync_address(db, spec):
    address = (
        db.query(Address)
        .filter(
            Address.street == spec["street"],
            Address.house == spec["house"],
            Address.entrance == spec["entrance"],
            Address.apartment == spec["apartment"],
        )
        .first()
    )

    if address is None:
        address = (
            db.query(Address)
            .filter(
                Address.street == spec["street"],
                Address.house == spec["house"],
                Address.apartment == spec["apartment"],
            )
            .first()
        )

    if address is None:
        address = Address()
        db.add(address)

    address.street = spec["street"]
    address.house = spec["house"]
    address.entrance = spec["entrance"]
    address.apartment = spec["apartment"]
    address.personal_account = spec.get("personal_account")

    db.flush()

    return address


def sync_user_address(db, user, address, *, is_primary, is_verified):
    link = (
        db.query(UserAddress)
        .filter(
            UserAddress.user_id == user.id,
            UserAddress.address_id == address.id,
        )
        .first()
    )

    if link is None:
        link = UserAddress(
            user_id=user.id,
            address_id=address.id,
        )
        db.add(link)

    link.is_primary = is_primary
    link.is_verified = is_verified

    if is_primary:
        user.address_id = address.id


def main():
    db = SessionLocal()

    try:
        seed_roles(db)

        users_by_email = {
            spec["email"]: sync_user(db, spec)
            for spec in USERS
        }

        addresses_by_key = {
            spec["key"]: sync_address(db, spec)
            for spec in ADDRESSES
        }

        for link_spec in USER_ADDRESS_LINKS:
            sync_user_address(
                db,
                users_by_email[link_spec["user_email"]],
                addresses_by_key[link_spec["address_key"]],
                is_primary=link_spec["is_primary"],
                is_verified=link_spec["is_verified"],
            )

        db.commit()

        for spec in USERS:
            print(f"{spec['email']} {spec['role']} synced")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()
