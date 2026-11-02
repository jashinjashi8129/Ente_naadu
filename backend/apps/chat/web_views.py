from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.utils.html import escape
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from apps.accounts.models import User, Area, UserLocation
from .models import FriendRequest, Friendship, Conversation, Message, SocialNotification


@login_required(login_url='web-login')
def web_find_friends(request):
    """
    User Discovery Page (/friends/find/):
    Allows citizens to discover other village members, view public details,
    and send/cancel friend requests.
    """
    current_user = request.user
    search_query = request.GET.get('q', '').strip()
    selected_area = request.GET.get('area', '').strip()
    selected_ward = request.GET.get('ward', '').strip()

    users_qs = User.objects.filter(is_active=True, is_blocked=False).exclude(id=current_user.id).select_related('area')

    if search_query:
        users_qs = users_qs.filter(
            Q(full_name__icontains=search_query) |
            Q(phone_number__icontains=search_query) |
            Q(area__name__icontains=search_query)
        )

    if selected_area and selected_area.isdigit():
        users_qs = users_qs.filter(area_id=int(selected_area))

    if selected_ward and selected_ward.isdigit():
        users_qs = users_qs.filter(ward_number=int(selected_ward))

    all_users = list(users_qs.order_by('full_name')[:60])

    # Pre-fetch existing friendships for fast O(1) lookup
    friend_ids = set()
    for f in Friendship.objects.filter(Q(user1=current_user) | Q(user2=current_user)):
        friend_ids.add(f.user2_id if f.user1_id == current_user.id else f.user1_id)

    # Pre-fetch pending requests in both directions
    pending_requests = FriendRequest.objects.filter(
        Q(sender=current_user) | Q(receiver=current_user),
        status=FriendRequest.Status.PENDING
    )
    sent_request_map = {}  # receiver_id -> req_id
    received_request_map = {}  # sender_id -> req_id

    for r in pending_requests:
        if r.sender_id == current_user.id:
            sent_request_map[r.receiver_id] = r.id
        else:
            received_request_map[r.sender_id] = r.id

    # Annotate users with relationship status
    for u in all_users:
        if u.id in friend_ids:
            u.rel_status = 'friends'
            u.req_id = None
        elif u.id in sent_request_map:
            u.rel_status = 'pending_sent'
            u.req_id = sent_request_map[u.id]
        elif u.id in received_request_map:
            u.rel_status = 'pending_received'
            u.req_id = received_request_map[u.id]
        else:
            u.rel_status = 'none'
            u.req_id = None

    all_areas = Area.objects.filter(is_active=True).order_by('name')

    context = {
        'users': all_users,
        'search_query': search_query,
        'selected_area': selected_area,
        'selected_ward': selected_ward,
        'all_areas': all_areas,
        'total_count': len(all_users)
    }
    return render(request, 'chat/find_friends.html', context)


@login_required(login_url='web-login')
def web_friends_list(request):
    """
    My Friends & Requests Page (/friends/):
    Lists accepted friends, incoming requests, and outgoing requests.
    """
    user = request.user
    q = request.GET.get('q', '').strip()
    active_tab = request.GET.get('tab', 'friends')

    friends_qs = Friendship.get_friends_for(user, search_query=q)

    # Pre-fetch conversations for unread counts and links
    friends_list = list(friends_qs)
    for friend in friends_list:
        conv = Conversation.get_or_create_between(user, friend)
        friend.conversation_id = conv.id
        friend.unread_count = conv.get_unread_count_for(user)
        friend.last_message = conv.latest_message

    incoming_requests = FriendRequest.objects.filter(
        receiver=user,
        status=FriendRequest.Status.PENDING
    ).select_related('sender', 'sender__area')

    outgoing_requests = FriendRequest.objects.filter(
        sender=user,
        status=FriendRequest.Status.PENDING
    ).select_related('receiver', 'receiver__area')

    context = {
        'friends': friends_list,
        'incoming_requests': incoming_requests,
        'outgoing_requests': outgoing_requests,
        'incoming_count': incoming_requests.count(),
        'outgoing_count': outgoing_requests.count(),
        'friends_count': len(friends_list),
        'search_query': q,
        'active_tab': active_tab
    }
    return render(request, 'chat/friends_list.html', context)


@login_required(login_url='web-login')
def web_chat_room(request, friend_id=None):
    """
    Private Chat Room (/chat/ or /chat/<friend_id>/):
    Responsive dual-pane chat on desktop, single-pane on mobile.
    Supports real-time polling updates.
    """
    user = request.user

    # Fetch all conversations for user
    conversations_qs = Conversation.objects.filter(
        Q(user1=user) | Q(user2=user)
    ).select_related('user1', 'user2', 'user1__area', 'user2__area').order_by('-updated_at')

    active_conversation = None
    active_friend = None
    messages_list = []
    are_still_friends = False

    # Annotate conversations with peer user and unread count
    annotated_convs = []
    for c in conversations_qs:
        peer = c.get_other_user(user)
        c.peer_user = peer
        c.peer_unread = c.get_unread_count_for(user)
        c.last_msg = c.latest_message
        c.are_friends = Friendship.are_friends(user, peer)
        annotated_convs.append(c)

    if friend_id:
        target_friend = get_object_or_404(User, id=friend_id, is_active=True, is_blocked=False)
        active_conversation = Conversation.get_or_create_between(user, target_friend)
        active_friend = target_friend
        are_still_friends = Friendship.are_friends(user, active_friend)

        # Mark all messages in active conversation as read
        active_conversation.mark_as_read_by(user)
        messages_list = active_conversation.messages.all().select_related('sender').order_by('created_at')[:150]

    elif annotated_convs:
        # Default to most recent conversation on desktop
        first_conv = annotated_convs[0]
        active_conversation = first_conv
        active_friend = first_conv.peer_user
        are_still_friends = first_conv.are_friends

        active_conversation.mark_as_read_by(user)
        messages_list = active_conversation.messages.all().select_related('sender').order_by('created_at')[:150]

    context = {
        'conversations': annotated_convs,
        'active_conversation': active_conversation,
        'active_friend': active_friend,
        'are_still_friends': are_still_friends,
        'chat_messages': messages_list,
        'total_conversations': len(annotated_convs),
    }
    return render(request, 'chat/chat_room.html', context)


# ==============================================================================
# HTML Form POST Actions
# ==============================================================================

@login_required(login_url='web-login')
@require_POST
def web_friend_request_send(request, user_id):
    """HTML form endpoint to send a friend request."""
    target_user = get_object_or_404(User, id=user_id, is_active=True, is_blocked=False)

    if target_user.id == request.user.id:
        messages.error(request, "നിങ്ങൾക്ക് സ്വന്തമായി ഫ്രണ്ട് റിക്വസ്റ്റ് അയക്കാൻ കഴിയില്ല.")
        return redirect('find-friends')

    if Friendship.are_friends(request.user, target_user):
        messages.info(request, "നിങ്ങൾ ഇതിനകം സുഹൃത്തുക്കളാണ്.")
        return redirect('friends-list')

    existing = FriendRequest.get_pending_between(request.user, target_user)
    if existing:
        if existing.sender_id == request.user.id:
            messages.info(request, "ഫ്രണ്ട് റിക്വസ്റ്റ് ഇതിനകം അയച്ചിട്ടുണ്ട്.")
        else:
            messages.info(request, "ഈ വ്യക്തി നിങ്ങൾക്ക് റിക്വസ്റ്റ് അയച്ചിട്ടുണ്ട്. അത് സ്വീകരിക്കുക.")
        return redirect('find-friends')

    FriendRequest.objects.create(
        sender=request.user,
        receiver=target_user,
        status=FriendRequest.Status.PENDING
    )
    SocialNotification.create_notification(
        recipient=target_user,
        actor=request.user,
        ntype=SocialNotification.Type.FRIEND_REQUEST,
        title=f"{request.user.full_name} ഫ്രണ്ട് റിക്വസ്റ്റ് അയച്ചു",
        body=f"{request.user.full_name} നിങ്ങളുമായി സൗഹൃദം സ്ഥാപിക്കാൻ ആഗ്രഹിക്കുന്നു.",
        link_url="/friends/?tab=incoming"
    )
    messages.success(request, f"'{target_user.full_name}'-ലേക്ക് ഫ്രണ്ട് റിക്വസ്റ്റ് അയച്ചു!")
    return redirect(request.META.get('HTTP_REFERER') or 'find-friends')


@login_required(login_url='web-login')
@require_POST
def web_friend_request_accept(request, request_id):
    """HTML form endpoint to accept an incoming friend request."""
    friend_req = get_object_or_404(FriendRequest, id=request_id)

    if friend_req.receiver_id != request.user.id:
        raise PermissionDenied("ഈ റിക്വസ്റ്റ് സ്വീകരിക്കാൻ നിങ്ങൾക്ക് അനുവാദമില്ല.")

    if friend_req.status == FriendRequest.Status.PENDING:
        Friendship.make_friends(friend_req.sender, friend_req.receiver)
        friend_req.status = FriendRequest.Status.ACCEPTED
        friend_req.save(update_fields=['status', 'updated_at'])

        SocialNotification.create_notification(
            recipient=friend_req.sender,
            actor=request.user,
            ntype=SocialNotification.Type.FRIEND_ACCEPT,
            title=f"{request.user.full_name} ഫ്രണ്ട് റിക്വസ്റ്റ് സ്വീകരിച്ചു!",
            body=f"ഇപ്പോൾ നിങ്ങൾക്ക് {request.user.full_name}-മായി സംസാരിക്കാം.",
            link_url=f"/chat/{request.user.id}/"
        )
        messages.success(request, f"'{friend_req.sender.full_name}'-ന്റെ ഫ്രണ്ട് റിക്വസ്റ്റ് സ്വീകരിച്ചു!")
    else:
        messages.info(request, "ഈ റിക്വസ്റ്റ് ഇതിനകം കൈകാര്യം ചെയ്തതാണ്.")

    return redirect('friends-list')


@login_required(login_url='web-login')
@require_POST
def web_friend_request_reject(request, request_id):
    """HTML form endpoint to reject an incoming friend request."""
    friend_req = get_object_or_404(FriendRequest, id=request_id)

    if friend_req.receiver_id != request.user.id:
        raise PermissionDenied("ഈ റിക്വസ്റ്റ് നിരസിക്കാൻ നിങ്ങൾക്ക് അനുവാദമില്ല.")

    if friend_req.status == FriendRequest.Status.PENDING:
        friend_req.status = FriendRequest.Status.REJECTED
        friend_req.save(update_fields=['status', 'updated_at'])
        messages.info(request, "ഫ്രണ്ട് റിക്വസ്റ്റ് നിരസിച്ചു.")

    return redirect('friends-list')


@login_required(login_url='web-login')
@require_POST
def web_friend_request_cancel(request, request_id):
    """HTML form endpoint to cancel an outgoing friend request."""
    friend_req = get_object_or_404(FriendRequest, id=request_id)

    if friend_req.sender_id != request.user.id:
        raise PermissionDenied("ഈ റിക്വസ്റ്റ് റദ്ദാക്കാൻ നിങ്ങൾക്ക് അനുവാദമില്ല.")

    if friend_req.status == FriendRequest.Status.PENDING:
        friend_req.status = FriendRequest.Status.CANCELLED
        friend_req.save(update_fields=['status', 'updated_at'])
        messages.info(request, "ഫ്രണ്ട് റിക്വസ്റ്റ് റദ്ദാക്കി.")

    return redirect(request.META.get('HTTP_REFERER') or 'friends-list')


@login_required(login_url='web-login')
@require_POST
def web_friend_unfriend(request, user_id):
    """HTML form endpoint to unfriend a user (preserves message history)."""
    target_user = get_object_or_404(User, id=user_id)

    if not Friendship.are_friends(request.user, target_user):
        messages.warning(request, "ഈ യൂസർ നിങ്ങളുടെ ഫ്രണ്ട്സ് ലിസ്റ്റിൽ ഇല്ല.")
        return redirect('friends-list')

    Friendship.remove_friends(request.user, target_user)
    messages.success(request, f"'{target_user.full_name}'-നെ ഫ്രണ്ട്സ് ലിസ്റ്റിൽ നിന്ന് നീക്കം ചെയ്തു.")
    return redirect('friends-list')


@login_required(login_url='web-login')
def web_nearby_friends(request):
    """
    Nearby Friends Map View (/friends/nearby/):
    Displays accepted friends on an interactive Leaflet map.
    Only friends who explicitly enabled sharing and whose location is fresh (<24h) appear.
    """
    user_location, _ = UserLocation.objects.get_or_create(user=request.user)

    radius = request.GET.get('radius', '10')
    try:
        radius_km = float(radius)
        if radius_km not in [1.0, 5.0, 10.0, 25.0, 50.0]:
            radius_km = 10.0
    except ValueError:
        radius_km = 10.0

    context = {
        'user_location': user_location,
        'selected_radius': radius_km,
        'radius_options': [1, 5, 10, 25, 50],
    }
    return render(request, 'chat/nearby_friends.html', context)


@login_required(login_url='web-login')
def web_location_settings(request):
    """
    User Location Privacy & Sharing Settings (/friends/location-settings/):
    Controls consent, pause, and precision (exact vs approximate).
    """
    user_location, _ = UserLocation.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        is_sharing = request.POST.get('is_sharing_enabled') == 'on'
        is_paused = request.POST.get('is_paused') == 'on'
        share_precision = request.POST.get('share_precision', UserLocation.Precision.EXACT)

        if share_precision not in [UserLocation.Precision.EXACT, UserLocation.Precision.APPROXIMATE]:
            share_precision = UserLocation.Precision.EXACT

        user_location.is_sharing_enabled = is_sharing
        user_location.is_paused = is_paused
        user_location.share_precision = share_precision
        user_location.save()

        messages.success(request, "ലൊക്കേഷൻ പ്രൈവസി ക്രമീകരണങ്ങൾ വിജയകരമായി സേവ് ചെയ്തു.")
        return redirect('location-settings')

    context = {
        'user_location': user_location,
    }
    return render(request, 'chat/location_settings.html', context)

