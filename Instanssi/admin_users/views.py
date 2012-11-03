# -*- coding: utf-8 -*-

from common.http import Http403
from django.shortcuts import render_to_response, get_object_or_404
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse
from Instanssi.admin_base.misc.custom_render import admin_render
from Instanssi.kompomaatti.models import Profile
from django.contrib.auth.models import User
from Instanssi.admin_users.forms import UserCreationForm, UserEditForm
from django_openid_auth.models import UserOpenID
from Instanssi.admin_base.misc.auth_decorator import staff_access_required, su_access_required

@staff_access_required
def superusers(request):
    # Check form
    if request.user.is_superuser:
        if request.method == "POST":
            userform = UserCreationForm(request.POST)
            if userform.is_valid():
                userform.save()
                return HttpResponseRedirect(reverse('admin-superusers'))
        else:
            userform = UserCreationForm()
    else:
        userform = None
    
    # Get users
    users = User.objects.exclude(username__contains="openiduser").exclude(username="arkisto")
    
    # Render response
    return admin_render(request, "admin_users/supers.html", {
        'superusers': users,
        'userform': userform,
    })

@su_access_required
def editsu(request, su_id):
    # Get user info and make sure it's not SU we're trying to edit
    user = get_object_or_404(User, pk=su_id)
    if user.is_superuser:
        raise Http403
    
    # Handle form
    if request.method == "POST":
        userform = UserEditForm(request.POST, instance=user)
        if userform.is_valid():
            userform.save()
            return HttpResponseRedirect(reverse('admin-superusers'))
    else:
        userform = UserEditForm(instance=user)
    
    # Render response
    return admin_render(request, "admin_users/suedit.html", {
        'userform': userform,
    })

@su_access_required
def deletesu(request, su_id):
    # Try to delete
    user = get_object_or_404(User, pk=su_id)
    if user.is_superuser or user.username == "arkisto":
        raise Http403
    else:
        user.is_active = False
        user.save()

    # All done, redirect
    return HttpResponseRedirect(reverse('admin-superusers'))

@staff_access_required
def openid(request):
    # Get users
    oid_userlist = UserOpenID.objects.all().values('user')
    db_users = User.objects.filter(pk__in=oid_userlist)
    
    # Create list
    users = []
    for user in db_users:
        # Get other information on the user
        try:
            profile = Profile.objects.get(user=user)
            otherinfo = profile.otherinfo
        except:
            otherinfo = u""
        
        # Append data
        users.append({
            'id': user.id,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'date_joined': user.date_joined,
            'last_login': user.last_login,
            'is_active': user.is_active,
            'otherinfo': otherinfo,
        })
    
    # Render response
    return admin_render(request, "admin_users/openid.html", {
        'openidusers': users,
    })
    
@staff_access_required
def deleteopenid(request, user_id):
    # Check for rights
    if not request.user.has_perm('auth.delete_user'):
        raise Http403
    
    # Try to delete
    user = get_object_or_404(User, pk=user_id)
    if not user.is_staff and not user.is_superuser:
        user.delete()
    else:
        raise Http403
    
    # All done, redirect
    return HttpResponseRedirect(reverse('admin-openid'))
