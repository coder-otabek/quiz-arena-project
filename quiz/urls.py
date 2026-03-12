from django.urls import path
from . import views

urlpatterns = [
    # Public
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),

    # Join flow
    path('join/', views.join_game, name='join_game'),
    path('join/<str:game_pin>/', views.player_join, name='player_join'),
    path('lobby/<str:game_pin>/', views.player_lobby, name='player_lobby'),

    # Host / Admin
    path('quizzes/', views.my_quizzes, name='my_quizzes'),
    path('quizzes/create/', views.create_quiz, name='create_quiz'),
    path('quizzes/save/', views.save_quiz, name='save_quiz'),
    path('quizzes/<int:quiz_id>/edit/', views.edit_quiz, name='edit_quiz'),
    path('quizzes/<int:quiz_id>/delete/', views.delete_quiz, name='delete_quiz'),
    path('quizzes/<int:quiz_id>/start/', views.host_start, name='host_start'),
    path('host/<str:game_pin>/', views.host_lobby, name='host_lobby'),
]
