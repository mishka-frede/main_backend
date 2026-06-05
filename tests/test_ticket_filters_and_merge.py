import os
from datetime import datetime
from datetime import timedelta

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.models.address import Address
from app.models.category import Category
from app.models.comment import Comment
from app.models.notification import Notification
from app.models.role import Role
from app.models.ticket import Ticket
from app.models.ticket_action_log import TicketActionLog
from app.models.ticket_feedback import TicketFeedback
from app.models.ticket_feedback import TicketFeedbackAttachment
from app.models.ticket_link import TicketLink
from app.models.ticket_merge_history import TicketMergeHistory
from app.models.ticket_status_history import TicketStatusHistory
from app.models.user import User
from app.models.user_address import UserAddress
from app.routes import tickets as ticket_routes
from app.schemas.linked_ticket_schema import TicketExecutorReportRequest
from app.schemas.linked_ticket_schema import TicketExecutorStatusRequest
from app.schemas.linked_ticket_schema import TicketMergeRequest


@pytest.fixture()
def db_session():

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(engine)

    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine
    )

    db = TestingSessionLocal()

    try:
        seed_data(db)
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def seed_data(db):

    db.add_all(
        [
            Role(code="resident", name="Resident"),
            Role(code="dispatcher", name="Dispatcher"),
            Role(code="executor", name="Executor"),
        ]
    )

    plumbing = Category(name="Plumbing")
    electric = Category(name="Electric")

    address_one = Address(
        street="Main Street",
        house="10",
        entrance="1",
        apartment="7",
        personal_account="PA-1"
    )
    address_two = Address(
        street="Oak Avenue",
        house="22",
        entrance="2",
        apartment="14",
        personal_account="PA-2"
    )

    dispatcher = User(
        id=1,
        full_name="Dispatcher User",
        email="dispatcher@example.com",
        password_hash="hash",
        role="dispatcher",
        is_active=True
    )
    resident = User(
        id=2,
        full_name="Resident User",
        email="resident@example.com",
        password_hash="hash",
        role="resident",
        is_active=True
    )
    other_resident = User(
        id=3,
        full_name="Other Resident",
        email="other@example.com",
        password_hash="hash",
        role="resident",
        is_active=True
    )
    executor = User(
        id=4,
        full_name="Executor User",
        email="executor@example.com",
        password_hash="hash",
        role="executor",
        is_active=True
    )

    db.add_all(
        [
            plumbing,
            electric,
            address_one,
            address_two,
            dispatcher,
            resident,
            other_resident,
            executor,
        ]
    )
    db.flush()

    now = datetime.utcnow()

    ticket_one = Ticket(
        id=1,
        description="Water leak in bathroom",
        status="new",
        priority="medium",
        created_at=now - timedelta(minutes=10),
        resident_id=resident.id,
        category_id=plumbing.id,
        address_id=address_one.id,
        assigned_executor_id=executor.id
    )
    ticket_two = Ticket(
        id=2,
        description="No light in hall",
        status="in_progress",
        priority="high",
        created_at=now - timedelta(minutes=5),
        resident_id=other_resident.id,
        category_id=electric.id,
        address_id=address_two.id
    )
    ticket_three = Ticket(
        id=3,
        description="Second water leak report",
        status="new",
        priority="low",
        created_at=now,
        resident_id=other_resident.id,
        category_id=plumbing.id,
        address_id=address_one.id
    )

    db.add_all([ticket_one, ticket_two, ticket_three])
    db.flush()

    db.add_all(
        [
            TicketLink(
                ticket_id=ticket_one.id,
                user_id=resident.id,
                is_creator=True
            ),
            TicketLink(
                ticket_id=ticket_two.id,
                user_id=other_resident.id,
                is_creator=True
            ),
            TicketLink(
                ticket_id=ticket_three.id,
                user_id=other_resident.id,
                is_creator=True
            ),
        ]
    )

    db.add_all(
        [
            TicketActionLog(
                ticket_id=ticket_one.id,
                user_id=dispatcher.id,
                action="executor_assigned",
                details="Executor User"
            ),
            TicketActionLog(
                ticket_id=ticket_two.id,
                user_id=dispatcher.id,
                action="status_changed",
                details="new -> in_progress"
            ),
        ]
    )

    db.commit()


def user(db, user_id):

    return db.query(User).filter(User.id == user_id).first()


def list_all(db, **filters):

    defaults = {
        "status": None,
        "priority": None,
        "category_id": None,
        "address_id": None,
        "assigned_executor_id": None,
        "search": None,
    }
    defaults.update(filters)

    return ticket_routes.get_all_tickets(
        db=db,
        current_user=user(db, 1),
        **defaults
    )


def test_dispatcher_can_filter_tickets_by_status_priority_and_executor(
    db_session
):

    by_status = list_all(db_session, status="new")
    assert [ticket["id"] for ticket in by_status] == [3, 1]

    by_priority = list_all(db_session, priority="high")
    assert [ticket["id"] for ticket in by_priority] == [2]

    by_executor = list_all(db_session, assigned_executor_id=4)
    assert [ticket["id"] for ticket in by_executor] == [1]


def test_dispatcher_search_matches_description_address_category_and_resident(
    db_session
):

    assert [ticket["id"] for ticket in list_all(db_session, search="bathroom")] == [1]
    assert [ticket["id"] for ticket in list_all(db_session, search="Oak")] == [2]
    assert [ticket["id"] for ticket in list_all(db_session, search="Plumbing")] == [3, 1]
    assert [ticket["id"] for ticket in list_all(db_session, search="Other Resident")] == [3, 2]


def test_resident_filters_only_linked_active_tickets(db_session):

    result = ticket_routes.get_my_tickets(
        status="new",
        priority=None,
        category_id=None,
        address_id=None,
        assigned_executor_id=None,
        search="water",
        db=db_session,
        current_user=user(db_session, 2)
    )

    assert [ticket["id"] for ticket in result] == [1]


def test_executor_can_list_only_assigned_tickets(db_session):

    result = ticket_routes.get_assigned_to_me_tickets(
        status=None,
        priority=None,
        category_id=None,
        address_id=None,
        search=None,
        db=db_session,
        current_user=user(db_session, 4)
    )

    assert [ticket["id"] for ticket in result] == [1]


def test_executor_can_change_assigned_ticket_status(db_session):

    result = ticket_routes.change_assigned_ticket_status(
        ticket_id=1,
        payload=TicketExecutorStatusRequest(status="in_progress"),
        db=db_session,
        current_user=user(db_session, 4)
    )

    assert result["status"] == "in_progress"

    log = db_session.query(TicketActionLog).filter(
        TicketActionLog.ticket_id == 1,
        TicketActionLog.user_id == 4,
        TicketActionLog.action == "executor_status_changed"
    ).first()

    assert log is not None
    assert log.details == "new -> in_progress"


def test_executor_cannot_change_unassigned_ticket_status(db_session):

    with pytest.raises(HTTPException) as exc:
        ticket_routes.change_assigned_ticket_status(
            ticket_id=2,
            payload=TicketExecutorStatusRequest(status="completed"),
            db=db_session,
            current_user=user(db_session, 4)
        )

    assert exc.value.status_code == 404


def test_executor_can_add_completion_report(db_session):

    result = ticket_routes.add_executor_report(
        ticket_id=1,
        payload=TicketExecutorReportRequest(text="  Fixed bathroom leak  "),
        db=db_session,
        current_user=user(db_session, 4)
    )

    assert result == {"message": "Executor report added"}

    comment = db_session.query(Comment).filter(
        Comment.ticket_id == 1,
        Comment.user_id == 4
    ).first()

    assert comment is not None
    assert comment.text == "Отчет исполнителя: Fixed bathroom leak"

    log = db_session.query(TicketActionLog).filter(
        TicketActionLog.ticket_id == 1,
        TicketActionLog.user_id == 4,
        TicketActionLog.action == "executor_report_added"
    ).first()

    assert log is not None
    assert log.details == "Fixed bathroom leak"


def test_dispatcher_can_read_action_log(db_session):

    result = ticket_routes.get_action_log(
        ticket_id=1,
        user_id=None,
        action=None,
        limit=100,
        db=db_session,
        current_user=user(db_session, 1)
    )

    assert len(result) == 1
    assert result[0]["action"] == "executor_assigned"
    assert result[0]["user_name"] == "Dispatcher User"


def test_dispatcher_can_export_filtered_csv_report(db_session):

    response = ticket_routes.export_tickets_report(
        status="new",
        priority=None,
        category_id=None,
        address_id=None,
        assigned_executor_id=None,
        search="bathroom",
        db=db_session,
        current_user=user(db_session, 1)
    )

    body = response.body.decode("utf-8")

    assert "id,status,priority" in body
    assert "Water leak in bathroom" in body
    assert "No light in hall" not in body


def test_merge_requires_non_blank_reason(db_session):

    payload = TicketMergeRequest(
        primary_ticket_id=1,
        secondary_ticket_id=3,
        reason="   "
    )

    with pytest.raises(HTTPException) as exc:
        ticket_routes.merge_tickets(
            payload=payload,
            db=db_session,
            current_user=user(db_session, 1)
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "Merge reason is required"


def test_merge_stores_normalized_reason_and_returns_history(db_session):

    payload = TicketMergeRequest(
        primary_ticket_id=1,
        secondary_ticket_id=3,
        reason="  duplicate leak report  "
    )

    result = ticket_routes.merge_tickets(
        payload=payload,
        db=db_session,
        current_user=user(db_session, 1)
    )

    assert result == {
        "message": "Tickets merged",
        "primary_ticket_id": 1,
        "archived_ticket_id": 3
    }

    history = db_session.query(TicketMergeHistory).first()
    assert history.reason == "duplicate leak report"

    secondary = db_session.query(Ticket).filter(Ticket.id == 3).first()
    assert secondary.status == "archived"
    assert secondary.merged_into_id == 1

    response = ticket_routes.build_ticket_response(
        db_session,
        db_session.query(Ticket).filter(Ticket.id == 1).first(),
        user(db_session, 1)
    )
    assert response["merge_history"][0]["reason"] == "duplicate leak report"
