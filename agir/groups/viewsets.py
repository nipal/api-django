import django_filters
from django_filters.rest_framework.backends import DjangoFilterBackend
from django.views.decorators.cache import cache_control
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action, authentication_classes

from agir.lib.permissions import (
    PermissionsOrReadOnly,
    RestrictViewPermissions,
    DjangoModelPermissions,
)
from agir.lib.pagination import LegacyPaginator
from agir.lib.filters import DistanceFilter, OrderByDistanceToBackend
from agir.lib.views import NationBuilderViewMixin, CreationSerializerMixin

from agir.authentication.models import Role

from . import serializers, models


class SupportGroupFilterSet(django_filters.rest_framework.FilterSet):
    close_to = DistanceFilter(field_name="coordinates", lookup_expr="distance_lte")
    path = django_filters.CharFilter(field_name="nb_path", lookup_expr="exact")

    class Meta:
        model = models.SupportGroup
        fields = ("contact_email", "close_to", "path")


class LegacySupportGroupViewSet(NationBuilderViewMixin, ModelViewSet):
    """
    Legacy endpoint for events that imitates the endpoint from Eve Python
    """

    permission_classes = (PermissionsOrReadOnly,)
    pagination_class = LegacyPaginator
    serializer_class = serializers.LegacySupportGroupSerializer
    queryset = models.SupportGroup.objects.all().prefetch_related("tags")
    filter_backends = (DjangoFilterBackend, OrderByDistanceToBackend)
    filterset_class = SupportGroupFilterSet

    def get_queryset(self):
        if not self.request.user.has_perm("groups.view_hidden_supportgroup"):
            return self.queryset.filter(published=True)
        return super(LegacySupportGroupViewSet, self).get_queryset()

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        group = models.SupportGroup.objects.get(pk=response.data["_id"])
        membership = models.Membership.objects.create(
            person=request.user.person,
            supportgroup=group,
            is_manager=True,
            is_referent=True,
        )

        return response

    @action(methods=["GET"], detail=False)
    @cache_control(max_age=60, public=True)
    @authentication_classes([])
    def summary(self, request, *args, **kwargs):
        supportgroups = (
            self.get_queryset().prefetch_related("tags").prefetch_related("subtypes")
        )
        serializer = serializers.SummaryGroupSerializer(
            instance=supportgroups, many=True, context=self.get_serializer_context()
        )
        return Response(data=serializer.data)


class SupportGroupTagViewSet(ModelViewSet):
    """
    EventTag viewset
    """

    serializer_class = serializers.SupportGroupTagSerializer
    queryset = models.SupportGroupTag.objects.all()
    permission_classes = (PermissionsOrReadOnly,)


class MembershipViewSet(ModelViewSet):
    """

    """

    serializer_class = serializers.MembershipSerializer
    queryset = models.Membership.objects.select_related("supportgroup", "person")
    creation_serializer_class = serializers.MembershipCreationSerializer
    permission_classes = (RestrictViewPermissions,)

    def get_queryset(self):
        queryset = super(MembershipViewSet, self).get_queryset()

        if not self.request.user.has_perm("groups.view_membership"):
            if (
                hasattr(self.request.user, "type")
                and self.request.user.type == Role.PERSON_ROLE
            ):
                return queryset.filter(person=self.request.user.person)
            else:
                return queryset.none()
        return queryset


class SupportGroupSubtypeViewSet(ModelViewSet):
    permission_classes = (PermissionsOrReadOnly,)
    serializer_class = serializers.SupportGroupSubtypeSerializer
    queryset = models.SupportGroupSubtype.objects.filter(
        visibility=models.SupportGroupSubtype.VISIBILITY_ALL
    )
