# -*- coding: utf-8 -*-

from common.http import Http403
from django.shortcuts import get_object_or_404, render_to_response
from django.template import RequestContext
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.core.urlresolvers import reverse
from Instanssi.kompomaatti.misc.auth_decorator import user_access_required
from Instanssi.kompomaatti.forms import *
from Instanssi.kompomaatti.models import *
from Instanssi.ext_programme.models import ProgrammeEvent
from Instanssi.kompomaatti.misc.time_formatting import *
from Instanssi.kompomaatti.misc import awesometime
from django.contrib.auth import logout
from datetime import datetime
import time
    
def index(request, event_id):
    event = get_object_or_404(Event, pk=event_id)
    compos = Compo.objects.filter(event=event, compo_start__gt=datetime.now())
    progs = ProgrammeEvent.objects.filter(event=event, start__gt=datetime.now())
    comps = Competition.objects.filter(event=event, start__gt=datetime.now())
    
    # Handle compos
    events = []
    for compo in compos:
        events.append({
            'date': compo.adding_end,
            'title': compo.name+': kompon ilmoittautumisaika päättyy.',
            'url': reverse('km:compo', args=(event_id, compo.id,)),
            'formatted_time': awesometime.format_single(compo.adding_end)
        })
        events.append({
            'date': compo.compo_start,
            'title': compo.name+': kompo alkaa.',
            'url': reverse('km:compo', args=(event_id, compo.id,)),
            'formatted_time': awesometime.format_single(compo.compo_start)
        })
    
    # Handle competitions
    for comp in comps:
        events.append({
            'date': comp.participation_end,
            'title': comp.name+': kilpailun ilmoittautumisaika päättyy.',
            'url': reverse('km:competition', args=(event_id, comp.id,)),
            'formatted_time': awesometime.format_single(comp.participation_end)
        })
        events.append({
            'date': comp.start,
            'title': comp.name+': kilpailu alkaa.',
            'url': reverse('km:competition', args=(event_id, comp.id,)),
            'formatted_time': awesometime.format_single(comp.start)
        })
        
    # Handle programmeevents
    for prog in progs:
        events.append({
            'date': prog.start,
            'title': prog.title,
            'url': None,
            'formatted_time': awesometime.format_single(prog.start)
        })
        
    # Sort list 
    def helper(object):
        return time.mktime(object['date'].timetuple())
    events = sorted(events, key=helper)
    
    # Only pick first 10 (or less)
    if len(events) > 10:
        events = events[:10]
    
    # All done, dump template
    return render_to_response('kompomaatti/index.html', {
        'sel_event_id': int(event_id),
        'events': events,
    }, context_instance=RequestContext(request))
    
def compos(request, event_id):
    # Get compos, format times
    compos = []
    for compo in Compo.objects.filter(active=True, event_id=int(event_id)):
        compos.append(compo_times_formatter(compo))
    
    # Dump the template
    return render_to_response('kompomaatti/compos.html', {
        'sel_event_id': int(event_id),
        'compos': compos,
    }, context_instance=RequestContext(request))
    
def compo_details(request, event_id, compo_id):
    # Get compo
    compo = compo_times_formatter(get_object_or_404(Compo, pk=int(compo_id), active=True, event_id=int(event_id)))
    
    # Check if user may vote (voting open, user has code)
    can_vote = False
    if request.user.is_active and request.user.is_authenticated():
        try:
            vc = VoteCode.objects.get(associated_to=request.user, event_id=int(event_id))
            can_vote = True
        except VoteCode.DoesNotExist:
            pass
        
    # Handle entry adding
    if request.method == 'POST' and compo.is_adding_open() and can_vote:
        # Make sure user is authenticated
        if not request.user.is_active or not request.user.is_authenticated():
            raise Http403
        
        # Handle data
        entryform = EntryForm(request.POST, request.FILES, compo=compo)
        if entryform.is_valid():
            entry = entryform.save(commit=False)
            entry.user = request.user
            entry.compo = compo
            entry.save()
            return HttpResponseRedirect(reverse('km:compo', args=(event_id, compo_id,)))
    else:
        entryform = EntryForm(compo=compo)
    
    # Get entries, and only show them if voting has started
    # (only show results if it has been allowed in model)
    all_entries = []
    if compo.has_voting_started:
        if compo.show_voting_results:
            all_entries = entrysort.sort_by_score(Entry.objects.filter(compo=compo))
        else:
            all_entries = Entry.objects.filter(compo=compo).order_by('name')
    
    # Stuff for users that have logged in 
    my_entries = []
    has_voted = False
    if request.user.is_active and request.user.is_authenticated():
        # Get all entries added by the user
        my_entries = Entry.objects.filter(compo=compo, user=request.user)
    
        # Check if user has already voted
        if Vote.objects.filter(user=request.user, compo=compo).count() > 0:
            has_voted = True
    
    # Dump template
    return render_to_response('kompomaatti/compo_details.html', {
        'sel_event_id': int(event_id),
        'compo': compo,
        'entryform': entryform,
        'can_vote': can_vote,
        'all_entries': all_entries,
        'my_entries': my_entries,
        'has_voted': has_voted,
    }, context_instance=RequestContext(request))
    
@user_access_required
def compo_vote(request, event_id, compo_id):
    # Make sure the user has an active votecode
    try:
        vc = VoteCode.objects.get(associated_to=request.user, event_id=int(event_id))
    except VoteCode.DoesNotExist:
        raise Http403
    
    # Get compo
    compo = get_object_or_404(Compo, pk=int(compo_id))
    
    # Make sure voting is open
    if not compo.is_voting_open():
        raise Http403
    
    # Get votes cast by user
    votes = Vote.objects.filter(user=request.user, compo=compo).order_by('rank')
    
    # Check if user has already voted
    has_voted = False
    if votes.count() > 0:
        has_voted = True
    
    # Check if we have data!
    if request.method == 'POST':
        # Get as list, convert to ints
        results = []
        _results = request.POST.getlist('results[]')
        for result in _results:
            results.append(int(result))
        
        # Make sure we have right amount of entries (more than 0)
        if len(results) < 1:
            return HttpResponse("On äänestettävä vähintään yhtä entryä.")
        
        # Make sure there are no id's twice
        _checked = []
        for id in results:
            if id in _checked:
                return HttpResponse("Syötevirhe!")
            else:
                _checked.append(id)

        # See that all id's are entries belonging to this compo
        _cids = []
        for entry in Entry.objects.filter(compo=compo, disqualified=False):
            _cids.append(entry.id)
        for result in results:
            if result not in _cids:
                return HttpResponse("Syötevirhe!")
        
        # Remove old votes by this user, on this compo
        if has_voted:
            Vote.objects.filter(user=request.user, compo=compo).delete()
        
        # Cast new votes
        number = 1
        for id in results:
            vote = Vote()
            vote.user = request.user
            vote.compo = compo
            vote.entry_id = id
            vote.rank = number
            vote.save()
            number += 1
        
        # Return success message
        return HttpResponse("0")
    
    # Get entries. If user hasn't voted yet, make sure the entries are in random order to minimize bias
    # If user has already voted, sort entries in previously voted order.
    nvoted_entries = []
    voted_entries = []
    if has_voted:
        # Get voted entries. Add to "voted" list
        for vote in votes:
            if not vote.entry.disqualified:
                voted_entries.append(vote.entry)
                
        # Get all entries
        _nvoted_entries = Entry.objects.filter(compo=compo, disqualified=False).order_by('?')
        for entry in _nvoted_entries:
            if entry not in voted_entries:
                nvoted_entries.append(entry)
    else:
        nvoted_entries = Entry.objects.filter(compo=compo, disqualified=False).order_by('?')
    
    # Dump template
    return render_to_response('kompomaatti/compo_vote.html', {
        'sel_event_id': int(event_id),
        'compo': compo,
        'voted_entries': voted_entries,
        'nvoted_entries': nvoted_entries,
        'has_voted': has_voted,
    }, context_instance=RequestContext(request))
    
@user_access_required
def compoentry_edit(request, event_id, compo_id, entry_id):
    # Get compo
    compo = get_object_or_404(Compo, pk=int(compo_id))
    
    # Check if user is allowed to edit
    if datetime.now() >= compo.editing_end:
        raise Http403
    
    # Get entry (make sure the user owns it, too)
    entry = get_object_or_404(Entry, pk=int(entry_id), compo=compo, user=request.user)
    
    # Handle entry adding
    if request.method == 'POST':
        entryform = EntryForm(request.POST, request.FILES, instance=entry, compo=compo)
        if entryform.is_valid():
            entryform.save()
            return HttpResponseRedirect(reverse('km:compo', args=(event_id, compo_id,)))
    else:
        entryform = EntryForm(instance=entry, compo=compo)
    
    # Dump template
    return render_to_response('kompomaatti/entry_edit.html', {
        'sel_event_id': int(event_id),
        'compo': compo,
        'entry': entry,
        'entryform': entryform,
    }, context_instance=RequestContext(request))
    
@user_access_required
def compoentry_delete(request, event_id, compo_id, entry_id):
    # Get compo
    compo = get_object_or_404(Compo, pk=int(compo_id))
    
    # Check if user is allowed to edit
    if datetime.now() >= compo.adding_end:
        raise Http403
    
    # Get entry (make sure the user owns it, too)
    entry = get_object_or_404(Entry, pk=int(entry_id), compo=compo, user=request.user)
    
    # Delete entry
    entry.delete()
    
    # Redirect
    return HttpResponseRedirect(reverse('km:compo', args=(event_id, compo_id,)))
    
def competitions(request, event_id):
    # Get competitions
    competitions = []
    for competition in Competition.objects.filter(active=True, event_id=int(event_id)):
        competitions.append(competition_times_formatter(competition))
    
    # Dump the template
    return render_to_response('kompomaatti/competitions.html', {
        'sel_event_id': int(event_id),
        'competitions': competitions,
    }, context_instance=RequestContext(request))
    
def competition_details(request, event_id, competition_id):
    # Get competition
    competition = competition_times_formatter(get_object_or_404(Competition, pk=int(competition_id), active=True, event_id=int(event_id)))
    
    # Check if user can participate (deadline not caught yet)
    can_participate = False
    if datetime.now() < competition.participation_end:
        can_participate = True
        
    # Handle signup form
    if request.method == 'POST' and can_participate:
        # Make sure user is authenticated
        if not request.user.is_active or not request.user.is_authenticated():
            raise Http403
        
        # Handle post data
        participationform = ParticipationForm(request.POST)
        if participationform.is_valid():
            p = participationform.save(commit=False)
            p.competition = competition
            p.user = request.user
            p.save()
            return HttpResponseRedirect(reverse('km:competition', args=(event_id, competition_id,)))
    else:
        participationform = ParticipationForm()
    
    # Get all participants
    participants = CompetitionParticipation.objects.filter(competition=competition)
    
    # Check if user has participated
    signed_up = False
    participation = None
    if request.user.is_active and request.user.is_authenticated():
        try:
            participation = CompetitionParticipation.objects.get(competition=competition, user=request.user)
            signed_up = True
        except CompetitionParticipation.DoesNotExist:
            pass
    
    # All done, dump template
    return render_to_response('kompomaatti/competition_details.html', {
        'sel_event_id': int(event_id),
        'competition': competition,
        'participation': participation,
        'signed_up': signed_up,
        'can_participate': can_participate,
        'participationform': participationform,
        'participants': participants,
    }, context_instance=RequestContext(request))

@user_access_required
def competition_signout(request, event_id, competition_id):
    # Get competition
    competition = get_object_or_404(Competition, pk=int(competition_id))
    
    # Check if user is still allowed to sign up
    if datetime.now() >= competition.participation_end:
        raise Http403
    
    # Delete participation
    try:
        CompetitionParticipation.objects.get(competition=competition, user=request.user).delete()
    except CompetitionParticipation.DoesNotExist:
        pass
    
    # Redirect
    return HttpResponseRedirect(reverse('km:competition', args=(event_id, competition_id,)))

def entry_details(request, event_id, compo_id, entry_id):
    # Get compo
    compo = get_object_or_404(Compo, pk=int(compo_id))
    
    # Make sure voting has started before allowing this page to be shown
    if datetime.now() < compo.voting_start:
        raise Http404
    
    # Get entry
    entry = get_object_or_404(Entry, pk=int(entry_id), compo=compo)
    
    # Render
    return render_to_response('kompomaatti/entry_details.html', {
        'sel_event_id': int(event_id),
        'entry': entry,
        'compo': compo,
    }, context_instance=RequestContext(request))

@user_access_required
def profile(request, event_id):
    # Get event
    event = get_object_or_404(Event, pk=int(event_id))
        
    # Check if user has the right to vote
    reserved_code = None
    can_vote = False
    try:
        votecode = VoteCode.objects.get(event=event, associated_to=request.user)
        reserved_code = votecode.key
        can_vote = True
    except VoteCode.DoesNotExist:
        pass
        
    # Check if request for vote code has been made
    request_made = False
    try:
        vcreq = VoteCodeRequest.objects.get(event=event, user=request.user)
        request_made = True
    except VoteCodeRequest.DoesNotExist:
        pass
        
    # Profile form
    if request.method == 'POST' and 'submit-profile' in request.POST:
        profileform = ProfileForm(request.POST, instance=request.user, user=request.user)
        if profileform.is_valid():
            profileform.save()
            return HttpResponseRedirect(reverse('km:profile', args=(event_id,)))
    else:
        profileform = ProfileForm(instance=request.user, user=request.user)
    
    # Votecode Association form
    if request.method == 'POST' and 'submit-vcassoc' in request.POST:
        votecodeassocform = VoteCodeAssocForm(request.POST, event=event, user=request.user)
        if votecodeassocform.is_valid():
            votecodeassocform.save()
            return HttpResponseRedirect(reverse('km:profile', args=(event_id,)))
    else:
        votecodeassocform = VoteCodeAssocForm(event=event, user=request.user)
    
    # Votecode Request form
    if request.method == 'POST' and 'submit-vcreq' in request.POST:
        votecoderequestform = VoteCodeRequestForm(request.POST)
        if votecoderequestform.is_valid():
            vcr = votecoderequestform.save(commit=False)
            vcr.user = request.user
            vcr.event = event
            vcr.save()
            return HttpResponseRedirect(reverse('km:profile', args=(event_id,)))
    else:
        votecoderequestform = VoteCodeRequestForm()
    
    # Render
    return render_to_response('kompomaatti/profile.html', {
        'sel_event_id': int(event_id),
        'profileform': profileform,
        'votecodeassocform': votecodeassocform,
        'votecoderequestform': votecoderequestform,
        'reserved_code': reserved_code,
        'can_vote': can_vote,
        'request_made': request_made,
    }, context_instance=RequestContext(request))
    
def do_login(request, event_id):
    loginform = OpenIDLoginForm(next=reverse('km:index', args=(event_id,)))
    
    return render_to_response('kompomaatti/login.html', {
        'sel_event_id': int(event_id),
        'openidform': loginform,
    }, context_instance=RequestContext(request))
    
@user_access_required
def do_logout(request, event_id):
    logout(request)
    return HttpResponseRedirect(reverse('km:index', args=(event_id,)))

