# -*- coding: utf-8 -*-

from django.conf.urls.defaults import patterns, url

urlpatterns = patterns(
    'Instanssi.json_api.views',
    url(r'^happenings/', 'happenings_api', name="happenings-api"),
    url(r'^screen/np/', 'screen_np_get', name="happenings-api"),
    url(r'^screen/np/set/', 'screen_np_set', name="happenings-api"),
    url(r'^events/(?P<hid>\d+)/', 'events_api', name="events-api"),
)
