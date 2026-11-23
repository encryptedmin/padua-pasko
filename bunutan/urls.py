from django.urls import path

from . import views

urlpatterns = [
    path("", views.enter_page, name="enter"),
    path("pick-name/", views.pick_name_page, name="pick_name"),
    path("bowl/", views.bowl_page, name="bowl"),
    path("my-pick/", views.my_pick_page, name="my_pick"),
    path("wishlists/", views.wishlists_page, name="wishlists"),
    path("reveals/", views.reveals_page, name="reveals"),
    path("api/state", views.api_state, name="api_state"),
    path("api/enter", views.api_enter, name="api_enter"),
    path("api/participants", views.api_participants, name="api_participants"),
    path("api/claim", views.api_claim, name="api_claim"),
    path("api/draw", views.api_draw, name="api_draw"),
    path("api/my-pick", views.api_my_pick, name="api_my_pick"),
    path("api/wishlist", views.api_wishlist, name="api_wishlist"),
    path("api/wishlists", views.api_wishlists, name="api_wishlists"),
    path("manage/login/", views.manage_login, name="manage_login"),
    path("manage/logout/", views.manage_logout, name="manage_logout"),
    path("manage/", views.manage_dashboard, name="manage_dashboard"),
]
