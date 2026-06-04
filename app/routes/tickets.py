from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload

from app.db.database import SessionLocal

from app.models.ticket import Ticket
from app.models.comment import Comment
from app.models.category import Category
from app.models.user_address import UserAddress
from app.models.ticket_link import TicketLink
from app.models.ticket_merge_history import TicketMergeHistory
from app.models.user import User

from app.schemas.ticket_schema import TicketResponse

from app.schemas.linked_ticket_schema import (
    CheckSimilarRequest,
    CheckSimilarResponse,
    SimilarTicketMatch,
    TicketCreateWithOptions,
    TicketExecutorAssignRequest,
    TicketJoinRequest,
    TicketMergeRequest,
    TicketSubscriberDispatcherResponse,
    TicketSubscriberResponse,
)

from app.schemas.comment_schema import (
    CommentCreate,
    CommentResponse
)

from app.security.dependencies import (
    get_current_user,
    require_dispatcher
)

from app.services import linked_tickets as linked_service
from app.services import feedback_service


router = APIRouter(
    prefix="/tickets",
    tags=["Tickets"]
)

PRIORITY_LABELS = {
    "low": "Низкий",
    "medium": "Средний",
    "high": "Высокий",
    "urgent": "Срочный",
}


def get_db():

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


def get_category_or_404(
    db: Session,
    category_id: int
) -> Category:

    category = db.query(Category).filter(
        Category.id == category_id
    ).first()

    if not category:

        raise HTTPException(
            status_code=400,
            detail="Invalid category"
        )

    return category


def verify_resident_address(
    db: Session,
    current_user: User,
    address_id: int
):

    address_link = db.query(UserAddress).filter(
        UserAddress.user_id == current_user.id,
        UserAddress.address_id == address_id,
        UserAddress.is_verified == True
    ).first()

    if not address_link:

        raise HTTPException(
            status_code=403,
            detail="Address is not verified or not linked to current user"
        )


def build_ticket_response(
    db: Session,
    ticket: Ticket,
    current_user: User | None = None
) -> dict:

    subscribers_count = db.query(TicketLink).filter(
        TicketLink.ticket_id == ticket.id
    ).count()

    merge_entries = db.query(TicketMergeHistory).filter(
        TicketMergeHistory.primary_ticket_id == ticket.id
    ).order_by(
        TicketMergeHistory.created_at.desc()
    ).all()

    is_creator = False
    is_linked = False

    if current_user is not None:

        link = db.query(TicketLink).filter(
            TicketLink.ticket_id == ticket.id,
            TicketLink.user_id == current_user.id
        ).first()

        if link:
            is_linked = True
            is_creator = link.is_creator
        elif ticket.resident_id == current_user.id:
            is_creator = True

    return {
        "id": ticket.id,
        "description": ticket.description,
        "status": ticket.status,
        "priority": PRIORITY_LABELS.get(ticket.priority, ticket.priority),
        "resident_id": ticket.resident_id,
        "category_id": ticket.category_id,
        "created_at": ticket.created_at,
        "subscribers_count": subscribers_count,
        "is_creator": is_creator,
        "is_linked": is_linked,
        "address": ticket.address,
        "category": ticket.category,
        "assigned_executor_id": ticket.assigned_executor_id,
        "assigned_executor": ticket.assigned_executor,
        "merge_history": [
            {
                "id": entry.id,
                "primary_ticket_id": entry.primary_ticket_id,
                "secondary_ticket_id": entry.secondary_ticket_id,
                "merged_by_user_id": entry.merged_by_user_id,
                "reason": entry.reason,
                "created_at": entry.created_at,
                "secondary_ticket_description": (
                    entry.secondary_ticket.description
                    if entry.secondary_ticket
                    else None
                ),
                "merged_by_name": (
                    entry.merged_by.full_name
                    if entry.merged_by
                    else None
                )
            }
            for entry in merge_entries
        ],
    }


def similar_match_to_schema(
    db: Session,
    match: dict
) -> SimilarTicketMatch:

    ticket = match["ticket"]

    category_name = None

    if ticket.category:
        category_name = ticket.category.name

    return SimilarTicketMatch(
        id=ticket.id,
        description=ticket.description,
        status=ticket.status,
        priority=PRIORITY_LABELS.get(ticket.priority, ticket.priority),
        category_id=ticket.category_id,
        category_name=category_name,
        created_at=ticket.created_at,
        similarity_score=match["similarity_score"],
        subscribers_count=match["subscribers_count"]
    )


@router.post(
    "/check-similar",
    response_model=CheckSimilarResponse
)
def check_similar_tickets(
    payload: CheckSimilarRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    if current_user.role in ["admin", "dispatcher"]:

        raise HTTPException(
            status_code=403,
            detail="This role cannot create tickets"
        )

    verify_resident_address(
        db,
        current_user,
        payload.address_id
    )

    category = get_category_or_404(
        db,
        payload.category_id
    )

    matches = linked_service.find_similar_tickets(
        db,
        description=payload.description,
        address_id=payload.address_id,
        category_id=category.id,
        current_user_id=current_user.id
    )

    return CheckSimilarResponse(
        similar_found=len(matches) > 0,
        matches=[
            similar_match_to_schema(db, match)
            for match in matches
        ]
    )


@router.post(
    "/",
    response_model=TicketResponse
)
def create_ticket(
    ticket: TicketCreateWithOptions,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    if current_user.role in ["admin", "dispatcher"]:

        raise HTTPException(
            status_code=403,
            detail="This role cannot create tickets"
        )

    category = get_category_or_404(
        db,
        ticket.category_id
    )

    verify_resident_address(
        db,
        current_user,
        ticket.address_id
    )

    if not ticket.force_create:

        matches = linked_service.find_similar_tickets(
            db,
            description=ticket.description,
            address_id=ticket.address_id,
            category_id=category.id,
            current_user_id=current_user.id
        )

        if matches:

            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Similar active tickets found",
                    "matches": [
                        similar_match_to_schema(db, match).model_dump()
                        for match in matches
                    ]
                }
            )

    new_ticket = Ticket(
        description=ticket.description,
        category_id=category.id,
        address_id=ticket.address_id,
        resident_id=current_user.id,
        status="new",
        priority="medium"
    )

    db.add(new_ticket)
    db.flush()

    linked_service.create_ticket_link(
        db,
        ticket=new_ticket,
        user=current_user,
        is_creator=True
    )

    linked_service.recalculate_ticket_priority(
        db,
        new_ticket
    )

    linked_service.log_ticket_action(
        db,
        ticket_id=new_ticket.id,
        user_id=current_user.id,
        action="ticket_created",
        details="Создана новая заявка"
    )

    db.commit()
    db.refresh(new_ticket)

    ticket_with_relations = db.query(Ticket).options(
        joinedload(Ticket.address),
        joinedload(Ticket.category)
    ).filter(
        Ticket.id == new_ticket.id
    ).first()

    return build_ticket_response(
        db,
        ticket_with_relations,
        current_user
    )


@router.post(
    "/{ticket_id}/join",
    response_model=TicketResponse
)
def join_existing_ticket(
    ticket_id: int,
    payload: TicketJoinRequest | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    if current_user.role in ["admin", "dispatcher"]:

        raise HTTPException(
            status_code=403,
            detail="This role cannot join tickets"
        )

    ticket = db.query(Ticket).options(
        joinedload(Ticket.address),
        joinedload(Ticket.category)
    ).filter(
        Ticket.id == ticket_id
    ).first()

    if not ticket:

        raise HTTPException(
            status_code=404,
            detail="Ticket not found"
        )

    if ticket.status in linked_service.INACTIVE_STATUSES:

        raise HTTPException(
            status_code=400,
            detail="Cannot join closed or archived ticket"
        )

    if ticket.merged_into_id is not None:

        raise HTTPException(
            status_code=400,
            detail="Cannot join merged ticket"
        )

    existing_link = db.query(TicketLink).filter(
        TicketLink.ticket_id == ticket.id,
        TicketLink.user_id == current_user.id
    ).first()

    if existing_link:

        raise HTTPException(
            status_code=400,
            detail="You are already subscribed to this ticket"
        )

    linked_service.create_ticket_link(
        db,
        ticket=ticket,
        user=current_user,
        is_creator=False
    )

    linked_service.recalculate_ticket_priority(
        db,
        ticket
    )

    if payload and payload.description:

        db.add(
            Comment(
                text=payload.description,
                ticket_id=ticket.id,
                user_id=current_user.id
            )
        )

    linked_service.log_ticket_action(
        db,
        ticket_id=ticket.id,
        user_id=current_user.id,
        action="ticket_joined",
        details="Жилец присоединился к существующей заявке"
    )

    linked_service.notify_ticket_subscribers(
        db,
        ticket=ticket,
        title=f"Заявка #{ticket.id}: новый подписчик",
        message="К заявке присоединился ещё один жилец.",
        exclude_user_id=current_user.id
    )

    db.commit()
    db.refresh(ticket)

    return build_ticket_response(
        db,
        ticket,
        current_user
    )


@router.get(
    "/",
    response_model=list[TicketResponse]
)
def get_my_tickets(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    ticket_ids = linked_service.get_user_ticket_ids(
        db,
        current_user.id
    )

    if not ticket_ids:
        return []

    tickets = db.query(Ticket).options(
        joinedload(Ticket.address),
        joinedload(Ticket.category)
    ).filter(
        Ticket.id.in_(ticket_ids),
        Ticket.merged_into_id.is_(None)
    ).order_by(
        Ticket.created_at.desc()
    ).all()

    return [
        build_ticket_response(db, ticket, current_user)
        for ticket in tickets
    ]


@router.get(
    "/all",
    response_model=list[TicketResponse]
)
def get_all_tickets(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    require_dispatcher(current_user)

    tickets = db.query(Ticket).options(
        joinedload(Ticket.address),
        joinedload(Ticket.category)
    ).filter(
        Ticket.merged_into_id.is_(None)
    ).order_by(
        Ticket.created_at.desc()
    ).all()

    return [
        build_ticket_response(db, ticket, current_user)
        for ticket in tickets
    ]


@router.post(
    "/merge"
)
def merge_tickets(
    payload: TicketMergeRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    require_dispatcher(current_user)

    primary = db.query(Ticket).filter(
        Ticket.id == payload.primary_ticket_id
    ).first()

    secondary = db.query(Ticket).filter(
        Ticket.id == payload.secondary_ticket_id
    ).first()

    if not primary or not secondary:

        raise HTTPException(
            status_code=404,
            detail="One or both tickets not found"
        )

    if primary.id == secondary.id:

        raise HTTPException(
            status_code=400,
            detail="Cannot merge ticket with itself"
        )

    if primary.category_id != secondary.category_id:

        raise HTTPException(
            status_code=400,
            detail="Cannot merge tickets with different categories"
        )

    if primary.status in linked_service.INACTIVE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail="Primary ticket is not active"
        )

    if secondary.status in linked_service.INACTIVE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail="Secondary ticket is not active"
        )

    secondary_links = db.query(TicketLink).filter(
        TicketLink.ticket_id == secondary.id
    ).all()

    for link in secondary_links:

        existing = db.query(TicketLink).filter(
            TicketLink.ticket_id == primary.id,
            TicketLink.user_id == link.user_id
        ).first()

        if existing:
            continue

        db.add(
            TicketLink(
                ticket_id=primary.id,
                user_id=link.user_id,
                is_creator=link.is_creator and link.user_id == secondary.resident_id,
                joined_at=link.joined_at
            )
        )

    secondary.merged_into_id = primary.id
    secondary.status = "archived"

    linked_service.recalculate_ticket_priority(db, primary)

    db.add(
        TicketMergeHistory(
            primary_ticket_id=primary.id,
            secondary_ticket_id=secondary.id,
            merged_by_user_id=current_user.id,
            reason=payload.reason
        )
    )

    linked_service.log_ticket_action(
        db,
        ticket_id=primary.id,
        user_id=current_user.id,
        action="tickets_merged",
        details=f"Заявка #{secondary.id} объединена в #{primary.id}"
    )

    linked_service.notify_ticket_subscribers(
        db,
        ticket=primary,
        title=f"Заявка #{primary.id}: объединение",
        message=f"Заявка #{secondary.id} объединена с текущей."
    )

    db.commit()

    return {
        "message": "Tickets merged",
        "primary_ticket_id": primary.id,
        "archived_ticket_id": secondary.id
    }


@router.patch(
    "/{ticket_id}/executor",
    response_model=TicketResponse
)
def assign_ticket_executor(
    ticket_id: int,
    payload: TicketExecutorAssignRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    require_dispatcher(current_user)

    ticket = db.query(Ticket).options(
        joinedload(Ticket.address),
        joinedload(Ticket.category),
        joinedload(Ticket.assigned_executor)
    ).filter(
        Ticket.id == ticket_id,
        Ticket.merged_into_id.is_(None)
    ).first()

    if not ticket:

        raise HTTPException(
            status_code=404,
            detail="Ticket not found"
        )

    if payload.executor_id is None:

        ticket.assigned_executor_id = None

        linked_service.log_ticket_action(
            db,
            ticket_id=ticket.id,
            user_id=current_user.id,
            action="executor_unassigned",
            details="Исполнитель снят"
        )

    else:

        executor = db.query(User).filter(
            User.id == payload.executor_id,
            User.role == "executor",
            User.is_active == True
        ).first()

        if not executor:

            raise HTTPException(
                status_code=400,
                detail="Invalid executor"
            )

        ticket.assigned_executor_id = executor.id

        linked_service.log_ticket_action(
            db,
            ticket_id=ticket.id,
            user_id=current_user.id,
            action="executor_assigned",
            details=f"Назначен исполнитель: {executor.full_name}"
        )

    db.commit()
    db.refresh(ticket)

    ticket = db.query(Ticket).options(
        joinedload(Ticket.address),
        joinedload(Ticket.category),
        joinedload(Ticket.assigned_executor)
    ).filter(
        Ticket.id == ticket_id
    ).first()

    return build_ticket_response(
        db,
        ticket,
        current_user
    )


@router.get(
    "/{ticket_id}",
    response_model=TicketResponse
)
def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    ticket = db.query(Ticket).options(
        joinedload(Ticket.address),
        joinedload(Ticket.category)
    ).filter(
        Ticket.id == ticket_id
    ).first()

    if not ticket:

        raise HTTPException(
            status_code=404,
            detail="Ticket not found"
        )

    if not linked_service.user_has_ticket_access(
        db,
        ticket,
        current_user
    ):

        raise HTTPException(
            status_code=403,
            detail="Access denied"
        )

    return build_ticket_response(
        db,
        ticket,
        current_user
    )


@router.get(
    "/{ticket_id}/subscribers",
    response_model=list[TicketSubscriberResponse]
)
def get_ticket_subscribers(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    ticket = db.query(Ticket).filter(
        Ticket.id == ticket_id
    ).first()

    if not ticket:

        raise HTTPException(
            status_code=404,
            detail="Ticket not found"
        )

    if current_user.role == "dispatcher":

        links = db.query(TicketLink).filter(
            TicketLink.ticket_id == ticket_id
        ).order_by(
            TicketLink.joined_at.asc()
        ).all()

        result = []

        for link in links:

            user = db.query(User).filter(
                User.id == link.user_id
            ).first()

            result.append(
                TicketSubscriberDispatcherResponse(
                    id=link.id,
                    user_id=link.user_id,
                    full_name=user.full_name if user else "—",
                    email=user.email if user else None,
                    joined_at=link.joined_at,
                    is_creator=link.is_creator
                )
            )

        return result

    if not linked_service.user_has_ticket_access(
        db,
        ticket,
        current_user
    ):

        raise HTTPException(
            status_code=403,
            detail="Access denied"
        )

    links = db.query(TicketLink).filter(
        TicketLink.ticket_id == ticket_id
    ).order_by(
        TicketLink.joined_at.asc()
    ).all()

    return [
        TicketSubscriberResponse(
            id=link.id,
            user_id=link.user_id,
            full_name=(
                db.query(User.full_name).filter(
                    User.id == link.user_id
                ).scalar() or "Жилец"
            ),
            joined_at=link.joined_at,
            is_creator=link.is_creator
        )
        for link in links
    ]


@router.delete(
    "/{ticket_id}/subscribers/{link_id}"
)
def unlink_subscriber(
    ticket_id: int,
    link_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    require_dispatcher(current_user)

    ticket = db.query(Ticket).filter(
        Ticket.id == ticket_id
    ).first()

    if not ticket:

        raise HTTPException(
            status_code=404,
            detail="Ticket not found"
        )

    link = db.query(TicketLink).filter(
        TicketLink.id == link_id,
        TicketLink.ticket_id == ticket_id
    ).first()

    if not link:

        raise HTTPException(
            status_code=404,
            detail="Subscription not found"
        )

    if link.is_creator:

        raise HTTPException(
            status_code=400,
            detail="Cannot unlink ticket creator"
        )

    db.delete(link)

    linked_service.recalculate_ticket_priority(db, ticket)

    linked_service.log_ticket_action(
        db,
        ticket_id=ticket.id,
        user_id=current_user.id,
        action="subscriber_unlinked",
        details=f"Отписан жилец user_id={link.user_id}"
    )

    db.commit()

    return {
        "message": "Subscriber unlinked"
    }


@router.patch(
    "/{ticket_id}/status"
)
def change_ticket_status(
    ticket_id: int,
    new_status: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    require_dispatcher(current_user)

    ticket = db.query(Ticket).filter(
        Ticket.id == ticket_id
    ).first()

    if not ticket:

        raise HTTPException(
            status_code=404,
            detail="Ticket not found"
        )

    old_status = ticket.status

    ticket.status = new_status

    if new_status == "completed" and old_status != "completed":

        feedback_service.on_ticket_completed(db, ticket)

    linked_service.notify_status_change(
        db,
        ticket=ticket,
        old_status=old_status,
        changed_by_user_id=current_user.id
    )

    linked_service.log_ticket_action(
        db,
        ticket_id=ticket.id,
        user_id=current_user.id,
        action="status_changed",
        details=f"{old_status} -> {new_status}"
    )

    db.commit()

    return {
        "message": "Status updated"
    }


@router.get(
    "/{ticket_id}/comments",
    response_model=list[CommentResponse]
)
def get_comments(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    ticket = db.query(Ticket).filter(
        Ticket.id == ticket_id
    ).first()

    if not ticket:

        raise HTTPException(
            status_code=404,
            detail="Ticket not found"
        )

    if not linked_service.user_has_ticket_access(
        db,
        ticket,
        current_user
    ):

        raise HTTPException(
            status_code=403,
            detail="Access denied"
        )

    comments = db.query(Comment).filter(
        Comment.ticket_id == ticket_id
    ).order_by(
        Comment.created_at.asc(),
        Comment.id.asc()
    ).all()

    users_by_id = {
        user.id: user
        for user in db.query(User).filter(
            User.id.in_([comment.user_id for comment in comments])
        ).all()
    }

    return [
        {
            "id": comment.id,
            "text": comment.text,
            "user_id": comment.user_id,
            "author_name": (
                users_by_id[comment.user_id].full_name
                if comment.user_id in users_by_id
                else None
            ),
            "author_role": (
                users_by_id[comment.user_id].role
                if comment.user_id in users_by_id
                else None
            ),
        }
        for comment in comments
    ]


@router.post(
    "/{ticket_id}/comments"
)
def add_comment(
    ticket_id: int,
    comment: CommentCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    ticket = db.query(Ticket).filter(
        Ticket.id == ticket_id
    ).first()

    if not ticket:

        raise HTTPException(
            status_code=404,
            detail="Ticket not found"
        )

    if not linked_service.user_has_ticket_access(
        db,
        ticket,
        current_user
    ):

        raise HTTPException(
            status_code=403,
            detail="Access denied"
        )

    new_comment = Comment(
        text=comment.text,
        ticket_id=ticket_id,
        user_id=current_user.id
    )

    db.add(new_comment)

    linked_service.log_ticket_action(
        db,
        ticket_id=ticket_id,
        user_id=current_user.id,
        action="comment_added",
        details=None
    )

    db.commit()

    return {
        "message": "Comment added"
    }
