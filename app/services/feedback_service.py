import os
import uuid
from datetime import datetime
from datetime import timedelta
from pathlib import Path

from fastapi import HTTPException
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.config.feedback_settings import (
    AUTO_CLOSE_FEEDBACK_DAYS,
    FEEDBACK_ALLOWED_STATUSES,
    FEEDBACK_TYPE_LABELS,
    FEEDBACK_TYPES,
    STATUS_AFTER_AUTO_CLOSE,
    STATUS_AFTER_DISPUTE,
    STATUS_AFTER_POSITIVE_FEEDBACK,
)
from app.models.notification import Notification
from app.models.ticket import Ticket
from app.models.ticket_feedback import TicketFeedback
from app.models.ticket_feedback import TicketFeedbackAttachment
from app.models.ticket_link import TicketLink
from app.models.user import User
from app.services import linked_tickets as linked_service

UPLOAD_ROOT = Path("uploads") / "feedback"


def ensure_upload_dir(ticket_id: int) -> Path:

    directory = UPLOAD_ROOT / str(ticket_id)
    directory.mkdir(parents=True, exist_ok=True)

    return directory


def user_can_leave_feedback(
    db: Session,
    ticket: Ticket,
    user: User
) -> bool:

    if user.role != "resident":
        return False

    if ticket.status not in FEEDBACK_ALLOWED_STATUSES:
        return False

    if ticket.status == "dispute_review":
        return False

    return linked_service.user_has_ticket_access(
        db,
        ticket,
        user
    )


def has_active_dispute(db: Session, ticket_id: int) -> bool:

    ticket = db.query(Ticket).filter(
        Ticket.id == ticket_id
    ).first()

    if not ticket:
        return False

    if ticket.status == STATUS_AFTER_DISPUTE:
        return True

    open_dispute = db.query(TicketFeedback).filter(
        TicketFeedback.ticket_id == ticket_id,
        TicketFeedback.feedback_type == "dispute",
        TicketFeedback.is_resolved == False
    ).first()

    return open_dispute is not None


def notify_user(
    db: Session,
    *,
    user_id: int,
    ticket_id: int,
    title: str,
    message: str
):

    db.add(
        Notification(
            user_id=user_id,
            ticket_id=ticket_id,
            channel="web",
            title=title,
            message=message
        )
    )


def notify_dispatchers(
    db: Session,
    *,
    ticket: Ticket,
    title: str,
    message: str
):

    dispatchers = db.query(User).filter(
        User.role.in_(["dispatcher", "admin"])
    ).all()

    for dispatcher in dispatchers:

        notify_user(
            db,
            user_id=dispatcher.id,
            ticket_id=ticket.id,
            title=title,
            message=message
        )


def notify_feedback_request(
    db: Session,
    ticket: Ticket
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

        notify_user(
            db,
            user_id=user_id,
            ticket_id=ticket.id,
            title=f"Заявка #{ticket.id}: оцените выполнение",
            message=(
                "Работы отмечены как выполненные. "
                "Оцените качество, оставьте комментарий "
                "или оспорьте результат."
            )
        )


def on_ticket_completed(
    db: Session,
    ticket: Ticket
):

    ticket.completed_at = datetime.utcnow()

    notify_feedback_request(db, ticket)


def build_feedback_response(
    db: Session,
    feedback: TicketFeedback
) -> dict:

    author = db.query(User).filter(
        User.id == feedback.user_id
    ).first()

    return {
        "id": feedback.id,
        "ticket_id": feedback.ticket_id,
        "user_id": feedback.user_id,
        "author_name": author.full_name if author else None,
        "feedback_type": feedback.feedback_type,
        "feedback_type_label": FEEDBACK_TYPE_LABELS.get(
            feedback.feedback_type,
            feedback.feedback_type
        ),
        "rating": feedback.rating,
        "comment": feedback.comment,
        "dispute_reason": feedback.dispute_reason,
        "is_resolved": feedback.is_resolved,
        "resolution_comment": feedback.resolution_comment,
        "resolved_at": feedback.resolved_at,
        "created_at": feedback.created_at,
        "attachments": feedback.attachments,
    }


async def save_attachments(
    db: Session,
    *,
    feedback: TicketFeedback,
    files: list[UploadFile]
) -> None:

    if not files:
        return

    directory = ensure_upload_dir(feedback.ticket_id)

    for upload in files:

        if not upload.filename:
            continue

        safe_name = os.path.basename(upload.filename)
        stored_name = f"{uuid.uuid4().hex}_{safe_name}"
        stored_path = directory / stored_name

        content = await upload.read()

        with open(stored_path, "wb") as file:
            file.write(content)

        db.add(
            TicketFeedbackAttachment(
                feedback_id=feedback.id,
                file_name=safe_name,
                stored_path=str(stored_path)
            )
        )


def create_feedback(
    db: Session,
    *,
    ticket: Ticket,
    user: User,
    feedback_type: str,
    rating: int | None,
    comment: str | None,
    dispute_reason: str | None,
    confirm_completion: bool
) -> TicketFeedback:

    if feedback_type not in FEEDBACK_TYPES:

        raise HTTPException(
            status_code=400,
            detail="Invalid feedback type"
        )

    if not user_can_leave_feedback(db, ticket, user):

        raise HTTPException(
            status_code=400,
            detail="Feedback is not allowed for this ticket"
        )

    if feedback_type == "dispute" and has_active_dispute(db, ticket.id):

        raise HTTPException(
            status_code=400,
            detail="Active dispute already exists for this ticket"
        )

    if feedback_type == "dispute":

        if not dispute_reason or not dispute_reason.strip():

            raise HTTPException(
                status_code=400,
                detail="Dispute reason is required"
            )

    if feedback_type == "review":

        if rating is None and not confirm_completion:

            raise HTTPException(
                status_code=400,
                detail="Rating or completion confirmation is required"
            )

    feedback = TicketFeedback(
        ticket_id=ticket.id,
        user_id=user.id,
        feedback_type=feedback_type,
        rating=rating,
        comment=comment,
        dispute_reason=dispute_reason
    )

    db.add(feedback)
    db.flush()

    old_status = ticket.status

    if feedback_type == "dispute":

        ticket.status = STATUS_AFTER_DISPUTE

        notify_dispatchers(
            db,
            ticket=ticket,
            title=f"Заявка #{ticket.id}: оспаривание",
            message=(
                f"Жилец оспорил результат. Причина: {dispute_reason}"
            )
        )

    else:

        if confirm_completion or rating is not None:

            ticket.status = STATUS_AFTER_POSITIVE_FEEDBACK

    linked_service.log_ticket_action(
        db,
        ticket_id=ticket.id,
        user_id=user.id,
        action="feedback_created",
        details=(
            f"type={feedback_type}, "
            f"status {old_status} -> {ticket.status}"
        )
    )

    return feedback


def resolve_dispute(
    db: Session,
    *,
    ticket: Ticket,
    dispatcher: User,
    resolution_comment: str,
    new_status: str
):

    if ticket.status != STATUS_AFTER_DISPUTE:

        raise HTTPException(
            status_code=400,
            detail="Ticket has no active dispute"
        )

    allowed = {"in_progress", "completed", "closed"}

    if new_status not in allowed:

        raise HTTPException(
            status_code=400,
            detail="Invalid status after dispute resolution"
        )

    dispute = db.query(TicketFeedback).filter(
        TicketFeedback.ticket_id == ticket.id,
        TicketFeedback.feedback_type == "dispute",
        TicketFeedback.is_resolved == False
    ).order_by(
        TicketFeedback.created_at.desc()
    ).first()

    if dispute:

        dispute.is_resolved = True
        dispute.resolution_comment = resolution_comment
        dispute.resolved_by = dispatcher.id
        dispute.resolved_at = datetime.utcnow()

    old_status = ticket.status
    ticket.status = new_status

    if new_status == "completed":
        ticket.completed_at = datetime.utcnow()

    linked_service.log_ticket_action(
        db,
        ticket_id=ticket.id,
        user_id=dispatcher.id,
        action="dispute_resolved",
        details=(
            f"{old_status} -> {new_status}; "
            f"{resolution_comment}"
        )
    )

    notify_user(
        db,
        user_id=ticket.resident_id,
        ticket_id=ticket.id,
        title=f"Заявка #{ticket.id}: оспаривание обработано",
        message=resolution_comment
    )


def auto_close_stale_tickets(db: Session):

    deadline = datetime.utcnow() - timedelta(
        days=AUTO_CLOSE_FEEDBACK_DAYS
    )

    tickets = db.query(Ticket).filter(
        Ticket.status == "completed",
        Ticket.completed_at.isnot(None),
        Ticket.completed_at <= deadline
    ).all()

    for ticket in tickets:

        has_feedback = db.query(TicketFeedback).filter(
            TicketFeedback.ticket_id == ticket.id
        ).first()

        if has_feedback:
            continue

        ticket.status = STATUS_AFTER_AUTO_CLOSE

        linked_service.log_ticket_action(
            db,
            ticket_id=ticket.id,
            user_id=None,
            action="auto_closed",
            details="Нет обратной связи в установленный срок"
        )

        notify_user(
            db,
            user_id=ticket.resident_id,
            ticket_id=ticket.id,
            title=f"Заявка #{ticket.id}: закрыта автоматически",
            message=(
                "Обратная связь не была оставлена в срок. "
                "Заявка закрыта автоматически."
            )
        )

    db.commit()
