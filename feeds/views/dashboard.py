from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse

from feeds.data.dashboard import get_dashboard_context
from feeds.services.dashboard_weekly_summary import get_current_week_summary_state


def index(request):
    context = get_dashboard_context()
    context['weekly_summary_status_url'] = reverse('feeds:dashboard_weekly_summary_status')
    return render(request, 'pages/dashboard/index.html', context)


def weekly_summary_status(request):
    return JsonResponse(get_current_week_summary_state(start_async=True))
