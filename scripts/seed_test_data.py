"""
Тестовые данные для демо и проверки UI.

Запуск из корня backend (с активированным .venv):
  cd main_backend
  python scripts/seed_test_data.py

Повторный запуск безопасен: существующие записи по email / адресу / метке [Тест] не дублируются.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from datetime import datetime
from datetime import timedelta

from app.config.categories import DEFAULT_CATEGORIES
from app.db.database import Base
from app.db.database import SessionLocal
from app.db.database import engine
from app.models import Address  # noqa: F401
from app.models import Category  # noqa: F401
from app.models import Notification  # noqa: F401
from app.models import Role
from app.models import Ticket  # noqa: F401
from app.models import TicketActionLog  # noqa: F401
from app.models import TicketFeedback  # noqa: F401
from app.models import TicketLink  # noqa: F401
from app.models import TicketStatusHistory  # noqa: F401
from app.models import User
from app.models import UserAddress  # noqa: F401
from app.models.comment import Comment  # noqa: F401 — регистрация ORM
from app.models.ticket import Ticket
from app.security.hashing import hash_password
from app.services import linked_tickets as linked_service

TEST_PASSWORD = "test1234"
ADMIN_PASSWORD = "admin123"
SEED_TAG = "[Тест]"

ROLES = [
    ("admin", "Администратор"),
    ("resident", "Жилец"),
    ("dispatcher", "Диспетчер"),
    ("executor", "Исполнитель"),
]

USERS = [
    {
        "email": "admin@example.com",
        "password": ADMIN_PASSWORD,
        "full_name": "Администратор Системы",
        "phone": "+7 900 000-00-01",
        "role": "admin",
    },
    {
        "email": "dispatcher@example.com",
        "password": TEST_PASSWORD,
        "full_name": "Иванова Мария",
        "phone": "+7 900 000-00-02",
        "role": "dispatcher",
    },
    {
        "email": "executor@example.com",
        "password": TEST_PASSWORD,
        "full_name": "Петров Алексей",
        "phone": "+7 900 000-00-03",
        "role": "executor",
    },
    {
        "email": "plumber@example.com",
        "password": TEST_PASSWORD,
        "full_name": "Смирнов Сергей",
        "phone": "+7 900 000-00-04",
        "role": "executor",
    },
    {
        "email": "electrician@example.com",
        "password": TEST_PASSWORD,
        "full_name": "Васильев Николай",
        "phone": "+7 900 000-00-05",
        "role": "executor",
    },
    {
        "email": "lift@example.com",
        "password": TEST_PASSWORD,
        "full_name": "Морозов Андрей",
        "phone": "+7 900 000-00-06",
        "role": "executor",
    },
    {
        "email": "resident1@example.com",
        "password": TEST_PASSWORD,
        "full_name": "Сидоров Иван",
        "phone": "+7 900 111-11-01",
        "role": "resident",
    },
    {
        "email": "resident2@example.com",
        "password": TEST_PASSWORD,
        "full_name": "Козлова Анна",
        "phone": "+7 900 111-11-02",
        "role": "resident",
    },
    {
        "email": "resident3@example.com",
        "password": TEST_PASSWORD,
        "full_name": "Новиков Дмитрий",
        "phone": "+7 900 111-11-03",
        "role": "resident",
    },
]

ADDRESSES = [
    {
        "key": "lenina-10-5",
        "street": "ул. Ленина",
        "house": "10",
        "entrance": "1",
        "apartment": "5",
        "personal_account": "10000005",
    },
    {
        "key": "lenina-10-12",
        "street": "ул. Ленина",
        "house": "10",
        "entrance": "2",
        "apartment": "12",
        "personal_account": "10000012",
    },
    {
        "key": "mira-3-1",
        "street": "ул. Мира",
        "house": "3",
        "entrance": "1",
        "apartment": "1",
        "personal_account": "20000001",
    },
]

USER_ADDRESS_LINKS = [
    {
        "user_email": "resident1@example.com",
        "address_key": "lenina-10-5",
        "is_primary": True,
        "is_verified": True,
    },
    {
        "user_email": "resident2@example.com",
        "address_key": "lenina-10-12",
        "is_primary": True,
        "is_verified": True,
    },
    {
        "user_email": "resident3@example.com",
        "address_key": "mira-3-1",
        "is_primary": True,
        "is_verified": False,
    },
]

TICKETS = [
    {
        "resident_email": "resident1@example.com",
        "address_key": "lenina-10-5",
        "category": "Сантехника",
        "status": "new",
        "priority": "medium",
        "description": f"{SEED_TAG} Протекает кран в ванной, нужен сантехник.",
    },
    {
        "resident_email": "resident1@example.com",
        "address_key": "lenina-10-5",
        "category": "Лифт",
        "status": "in_progress",
        "priority": "high",
        "description": f"{SEED_TAG} Лифт не работает, застрял на 5 этаже.",
        "days_ago": 2,
    },
    {
        "resident_email": "resident2@example.com",
        "address_key": "lenina-10-12",
        "category": "Лифт",
        "status": "new",
        "priority": "medium",
        "description": f"{SEED_TAG} Сломан лифт, не открываются двери кабины.",
        "days_ago": 1,
    },
    {
        "resident_email": "resident2@example.com",
        "address_key": "lenina-10-12",
        "category": "Электрика",
        "status": "completed",
        "priority": "medium",
        "description": f"{SEED_TAG} Не горит свет в подъезде на 3 этаже.",
        "days_ago": 10,
        "complete": True,
    },
    {
        "resident_email": "resident3@example.com",
        "address_key": "mira-3-1",
        "category": "Отопление и ГВС",
        "status": "new",
        "priority": "urgent",
        "description": f"{SEED_TAG} Батареи холодные, температура в квартире +16.",
    },
]

COMMENTS = [
    {
        "ticket_description_contains": f"{SEED_TAG} Лифт не работает",
        "author_email": "dispatcher@example.com",
        "text": "Приняли заявку, вызвали специалиста лифтовой компании.",
    },
    {
        "ticket_description_contains": f"{SEED_TAG} Протекает кран",
        "author_email": "resident1@example.com",
        "text": "Вода капает сильнее с вечера.",
    },
]


def seed_roles(db) -> None:

    for code, name in ROLES:

        if not db.query(Role).filter(Role.code == code).first():

            db.add(Role(code=code, name=name))

    db.commit()


def seed_categories(db) -> None:

    for name in DEFAULT_CATEGORIES:

        if not db.query(Category).filter(Category.name == name).first():

            db.add(Category(name=name))

    db.commit()


def get_or_create_user(db, spec: dict) -> User:

    user = db.query(User).filter(User.email == spec["email"]).first()

    if user:

        user.full_name = spec["full_name"]
        user.phone = spec.get("phone", "")
        user.password_hash = hash_password(spec["password"])
        user.role = spec["role"]
        user.is_active = True
        db.commit()
        db.refresh(user)

        return user

    user = User(
        full_name=spec["full_name"],
        email=spec["email"],
        phone=spec.get("phone", ""),
        password_hash=hash_password(spec["password"]),
        role=spec["role"],
        is_active=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def get_or_create_address(db, spec: dict) -> Address:

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

    if not address:

        address = (
            db.query(Address)
            .filter(
                Address.street == spec["street"],
                Address.house == spec["house"],
                Address.apartment == spec["apartment"],
            )
            .first()
        )

    if address:

        address.entrance = spec["entrance"]
        address.personal_account = spec.get("personal_account")
        db.commit()

        return address

    address = Address(
        street=spec["street"],
        house=spec["house"],
        entrance=spec["entrance"],
        apartment=spec["apartment"],
        personal_account=spec.get("personal_account"),
    )

    db.add(address)
    db.commit()
    db.refresh(address)

    return address


def link_user_address(
    db,
    user: User,
    address: Address,
    *,
    is_primary: bool,
    is_verified: bool,
) -> UserAddress:

    link = (
        db.query(UserAddress)
        .filter(
            UserAddress.user_id == user.id,
            UserAddress.address_id == address.id,
        )
        .first()
    )

    if link:

        link.is_primary = is_primary
        link.is_verified = is_verified

        db.commit()

        return link

    link = UserAddress(
        user_id=user.id,
        address_id=address.id,
        is_primary=is_primary,
        is_verified=is_verified,
    )

    db.add(link)
    db.commit()

    if is_primary:

        user.address_id = address.id

        db.commit()

    return link


def get_category(db, name: str) -> Category:

    category = db.query(Category).filter(Category.name == name).first()

    if not category:

        raise RuntimeError(f"Категория не найдена: {name}")

    return category


def ticket_exists(db, resident_id: int, description: str) -> bool:

    return (
        db.query(Ticket)
        .filter(
            Ticket.resident_id == resident_id,
            Ticket.description == description,
        )
        .first()
        is not None
    )


def create_ticket(
    db,
    *,
    resident: User,
    address: Address,
    category_name: str,
    description: str,
    status: str,
    priority: str,
    days_ago: int = 0,
    complete: bool = False,
) -> Ticket | None:

    if ticket_exists(db, resident.id, description):

        return None

    category = get_category(db, category_name)

    created_at = datetime.utcnow() - timedelta(days=days_ago)

    ticket = Ticket(
        description=description,
        status=status,
        priority=priority,
        created_at=created_at,
        resident_id=resident.id,
        category_id=category.id,
        address_id=address.id,
    )

    if complete:

        ticket.completed_at = created_at + timedelta(days=1)

    db.add(ticket)
    db.flush()

    linked_service.create_ticket_link(
        db,
        ticket=ticket,
        user=resident,
        is_creator=True,
    )

    linked_service.recalculate_ticket_priority(db, ticket)

    linked_service.log_ticket_action(
        db,
        ticket_id=ticket.id,
        user_id=resident.id,
        action="ticket_created",
        details="Создана тестовая заявка (seed)",
    )

    db.commit()
    db.refresh(ticket)

    return ticket


def add_comment_if_missing(
    db,
    *,
    ticket: Ticket,
    author: User,
    text: str,
) -> None:

    exists = (
        db.query(Comment)
        .filter(
            Comment.ticket_id == ticket.id,
            Comment.text == text,
        )
        .first()
    )

    if exists:

        return

    db.add(
        Comment(
            ticket_id=ticket.id,
            user_id=author.id,
            text=text,
        )
    )

    db.commit()


def print_accounts() -> None:

    print()
    print("=" * 60)
    print("Тестовые учётные записи (пароль test1234, кроме admin)")
    print("=" * 60)

    rows = [
        ("admin@example.com", ADMIN_PASSWORD, "admin", "Админ-панель, сотрудники"),
        ("dispatcher@example.com", TEST_PASSWORD, "dispatcher", "Диспетчер, заявки, адреса на проверке"),
        ("executor@example.com", TEST_PASSWORD, "executor", "Исполнитель"),
        ("plumber@example.com", TEST_PASSWORD, "executor", "Исполнитель: сантехник"),
        ("electrician@example.com", TEST_PASSWORD, "executor", "Исполнитель: электрик"),
        ("lift@example.com", TEST_PASSWORD, "executor", "Исполнитель: лифты"),
        ("resident1@example.com", TEST_PASSWORD, "resident", "Жилец, ул. Ленина 10-5"),
        ("resident2@example.com", TEST_PASSWORD, "resident", "Жилец, ул. Ленина 10-12"),
        ("resident3@example.com", TEST_PASSWORD, "resident", "Жилец, адрес на проверке (ул. Мира 3-1)"),
    ]

    for email, password, role, note in rows:

        print(f"  {email:28} {password:10}  [{role:11}]  {note}")

    print()
    print("Заявки с меткой [Тест]: новые, в работе, выполненная, две по лифту в одном доме.")
    print("У resident3 адрес не подтверждён — виден в «Адреса на проверке» у диспетчера.")
    print("=" * 60)


def main() -> None:

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    created_tickets = 0

    try:

        seed_roles(db)
        seed_categories(db)

        users_by_email: dict[str, User] = {}

        for spec in USERS:

            users_by_email[spec["email"]] = get_or_create_user(db, spec)

        addresses_by_key: dict[str, Address] = {}

        for spec in ADDRESSES:

            addresses_by_key[spec["key"]] = get_or_create_address(db, spec)

        for link_spec in USER_ADDRESS_LINKS:

            user = users_by_email[link_spec["user_email"]]
            address = addresses_by_key[link_spec["address_key"]]

            link_user_address(
                db,
                user,
                address,
                is_primary=link_spec["is_primary"],
                is_verified=link_spec["is_verified"],
            )

        for ticket_spec in TICKETS:

            resident = users_by_email[ticket_spec["resident_email"]]
            address = addresses_by_key[ticket_spec["address_key"]]

            ticket = create_ticket(
                db,
                resident=resident,
                address=address,
                category_name=ticket_spec["category"],
                description=ticket_spec["description"],
                status=ticket_spec["status"],
                priority=ticket_spec["priority"],
                days_ago=ticket_spec.get("days_ago", 0),
                complete=ticket_spec.get("complete", False),
            )

            if ticket:

                created_tickets += 1

        for comment_spec in COMMENTS:

            author = users_by_email[comment_spec["author_email"]]

            ticket = (
                db.query(Ticket)
                .filter(
                    Ticket.description.contains(
                        comment_spec["ticket_description_contains"]
                    )
                )
                .first()
            )

            if ticket:

                add_comment_if_missing(
                    db,
                    ticket=ticket,
                    author=author,
                    text=comment_spec["text"],
                )

        print(f"Готово. Новых заявок: {created_tickets}.")

        print_accounts()

    finally:

        db.close()


if __name__ == "__main__":

    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):

        print(__doc__)
        sys.exit(0)

    main()
