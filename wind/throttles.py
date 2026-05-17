"""
Límites de tasa por tipo de endpoint.
"""
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class AnonBurstThrottle(AnonRateThrottle):
    scope = "anon"


class UserBurstThrottle(UserRateThrottle):
    scope = "user"


class ProfileThrottle(UserRateThrottle):
    scope = "profile"


class SyncAdminThrottle(UserRateThrottle):
    scope = "sync_admin"
