from django.contrib import admin
from .models import QuizSet, Question, Answer, GameSession, Player, PlayerAnswer


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 4


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1


@admin.register(QuizSet)
class QuizSetAdmin(admin.ModelAdmin):
    list_display = ['name', 'creator', 'question_count', 'created_at']
    search_fields = ['name', 'creator__username']
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['text', 'quiz_set', 'time_limit', 'points', 'order']
    inlines = [AnswerInline]


@admin.register(GameSession)
class GameSessionAdmin(admin.ModelAdmin):
    list_display = ['game_pin', 'quiz_set', 'host', 'status', 'created_at']


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ['nickname', 'avatar', 'score', 'session']
