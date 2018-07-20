"""src URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.11/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path, include
from django.conf.urls.static import static
from ajax_select import urls as ajax_select_urls

from .metrics import get_metrics
from . import routers, admin, settings

from . import front_urls
from ..webhooks import urls as webhooks_urls

urlpatterns = [
    path('admin/', admin.admin_site.urls),
    path('webhooks/', include(webhooks_urls)),
    path('ajax_select/', include(ajax_select_urls)),
    path('metrics/', get_metrics)
]

if settings.ENABLE_API:
    urlpatterns.append(
        path('legacy/', include((routers.legacy_api.urls, 'legacy'), namespace='legacy'))
    )

if settings.ENABLE_FRONT:
    urlpatterns.append(path('', include(front_urls)))
    urlpatterns.append(path('nuntius/', include('nuntius.urls')))

if settings.ENABLE_MAP:
    urlpatterns.append(
        path('carte/', include('agir.carte.urls')),
    )

if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [
                      path('__debug__/', include(debug_toolbar.urls))
                  ] + urlpatterns
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += [path('silk/', include('silk.urls', namespace='silk'))]
