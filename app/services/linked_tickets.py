from datetime import datetime
from datetime import timedelta

from sqlalchemy.orm import Session

from app.config.linked_tickets_settings import (
    INACTIVE_STATUSES,
    MATCH_SAME_BUILDING,
    PRIORITY_RULES,
    SEARCH_WINDOW_DAYS,
    SIMILARITY_THRESHOLD,
    STATUS_LABELS,
)
from app.models.address import Address
from app.models.notification import Notification
from app.models.ticket import Ticket
from app.models.ticket_action_log import TicketActionLog
from app.models.ticket_link import TicketLink
from app.models.user import User
from app.services.text_similarity import combined_similarity


def log_ticket_action(
    db: Session,
    *,
    ticket_id: int | None,
    user_id: int | None,
    action: str,
    details: str | None = None
):

    db.add(
        TicketActionLog(
            ticket_id=ticket_id,
            user_id=user_id,
            action=action,
            details=details
        )
    )


def priority_for_subscriber_count(count: int) -> str:

    for rule in PRIORITY_RULES:

        minimum = rule["min_subscribers"]
        maximum = rule["max_subscribers"]

        if count < minimum:
            continue

        if maximum is None or count <= maximum:
            return rule["priority"]

    return PRIORITY_RULES[-1]["priority"]


def recalculate_ticket_priority(
    db: Session,
    ticket: Ticket
):

    subscribers_count = db.query(TicketLink).filter(
        TicketLink.ticket_id == ticket.id
    ).count()

    ticket.priority = priority_for_subscriber_count(
        subscribers_count
    )


def ensure_creator_link(
    db: Session,
    ticket: Ticket
):

    exists = db.query(TicketLink).filter(
        TicketLink.ticket_id == ticket.id,
        TicketLink.user_id == ticket.resident_id
    ).first()

    if exists:
        return

    db.add(
        TicketLink(
            ticket_id=ticket.id,
            user_id=ticket.resident_id,
            is_creator=True
        )
    )


def get_active_ticket_candidates(
    db: Session,
    *,
    address_id: int,
    category_id: int,
    exclude_user_id: int | None = None
) -> list[Ticket]:

    window_start = datetime.utcnow() - timedelta(
        days=SEARCH_WINDOW_DAYS
    )

    address = db.query(Address).filter(
        Address.id == address_id
    ).first()

    if not address:

        return []

    query = db.query(Ticket).join(
        Address,
        Ticket.address_id == Address.id
    ).filter(
        Ticket.category_id == category_id,
        Ticket.created_at >= window_start,
        Ticket.merged_into_id.is_(None),
        ~Ticket.status.in_(INACTIVE_STATUSES)
    )

    if MATCH_SAME_BUILDING:

        query = query.filter(
            Address.street == address.street,
            Address.house == address.house,
            Address.entrance == address.entrance
        )

    else:

        query = query.filter(
            Ticket.address_id == address_id
        )

    if exclude_user_id is not None:

        linked_ticket_ids = [
            row[0]
            for row in db.query(TicketLink.ticket_id).filter(
                TicketLink.user_id == exclude_user_id
            ).all()
        ]

        if linked_ticket_ids:
            query = query.filter(
                ~Ticket.id.in_(linked_ticket_ids)
            )

    return query.order_by(
        Ticket.created_at.desc()
    ).all()


def find_similar_tickets(
    db: Session,
    *,
    description: str,
    address_id: int,
    category_id: int,
    current_user_id: int | None = None,
    threshold: float = SIMILARITY_THRESHOLD
) -> list[dict]:

    candidates = get_active_ticket_candidates(
        db,
        address_id=address_id,
        category_id=category_id,
        exclude_user_id=current_user_id
    )

    matches = []

    for ticket in candidates:

        score = combined_similarity(
            description,
            ticket.description
        )

        if score < threshold:
            continue

        subscribers_count = db.query(TicketLink).filter(
            TicketLink.ticket_id == ticket.id
        ).count()

        matches.append({
            "ticket": ticket,
            "similarity_score": round(score, 3),
            "subscribers_count": subscribers_count
        })

    matches.sort(
        key=lambda item: item["similarity_score"],
        reverse=True
    )

    return matches


def user_has_ticket_access(
    db: Session,
    ticket: Ticket,
    user: User
) -> bool:

    if user.role in ["dispatcher", "admin"]:
        return True

    if ticket.resident_id == user.id:
        return True

    if ticket.assigned_executor_id == user.id:
        return True

    link = db.query(TicketLink).filter(
        TicketLink.ticket_id == ticket.id,
        TicketLink.user_id == user.id
    ).first()

    return link is not None


def create_ticket_link(
    db: Session,
    *,
    ticket: Ticket,
    user: User,
    is_creator: bool = False
) -> TicketLink:

    existing = db.query(TicketLink).filter(
        TicketLink.ticket_id == ticket.id,
        TicketLink.user_id == user.id
    ).first()

    if existing:
        return existing

    link = TicketLink(
        ticket_id=ticket.id,
        user_id=user.id,
        is_creator=is_creator
    )

    db.add(link)

    return link


def notify_ticket_subscribers(
    db: Session,
    *,
    ticket: Ticket,
    title: str,
    message: str,
    exclude_user_id: int | None = None
):

    subscriber_ids = [
        row[0]
        for row in db.query(TicketLink.user_id).filter(
            TicketLink.ticket_id == ticket.id
        ).all()
    ]

    if ticket.resident_id not in subscriber_ids:
        subscriber_ids.append(ticket.resident_id)

    for user_id in set(subscriber_ids):

        if exclude_user_id is not None and user_id == exclude_user_id:
            continue

        db.add(
            Notification(
                user_id=user_id,
                ticket_id=ticket.id,
                channel="web",
                title=title,
                message=message
            )
        )


def notify_status_change(
    db: Session,
    *,
    ticket: Ticket,
    old_status: str,
    changed_by_user_id: int
):

    old_label = STATUS_LABELS.get(
        old_status,
        old_status
    )

    new_label = STATUS_LABELS.get(
        ticket.status,
        ticket.status
    )

    notify_ticket_subscribers(
        db,
        ticket=ticket,
        title=f"Заявка #{ticket.id}: изменение статуса",
        message=(
            f"Статус заявки изменён: {old_label} → {new_label}."
        ),
        exclude_user_id=changed_by_user_id
    )


def get_user_ticket_ids(
    db: Session,
    user_id: int
) -> set[int]:

    created_ids = {
        row[0]
        for row in db.query(Ticket.id).filter(
            Ticket.resident_id == user_id
        ).all()
    }

    linked_ids = {
        row[0]
        for row in db.query(TicketLink.ticket_id).filter(
            TicketLink.user_id == user_id
        ).all()
    }

    return created_ids | linked_ids
