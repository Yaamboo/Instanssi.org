# -*- coding: utf-8 -*-

from django.shortcuts import render_to_response
from django.http import Http404,HttpResponseRedirect
from django.contrib.auth.decorators import login_required
from Instanssi.admin_base.misc.custom_render import admin_render
from Instanssi.admin_profile.forms import PasswordChangeForm

@login_required(login_url='/control/auth/login/')
def password(request):
    # Make sure the user is staff.
    if not request.user.is_staff:
        raise Http404
    
    if request.method == "POST":
        pwform = PasswordChangeForm(request.POST, user=request.user)
        if pwform.is_valid():
            pwform.save()
            return HttpResponseRedirect("/control/profile/")
    else:
        pwform = PasswordChangeForm()
    
    # Render response
    return admin_render(request, "admin_profile/password.html", {
        'pwform': pwform,
    })

@login_required(login_url='/control/auth/login/')
def profile(request):
    # Make sure the user is staff.
    if not request.user.is_staff:
        raise Http404
    
    # Render response
    return admin_render(request, "admin_profile/profile.html", {
    })