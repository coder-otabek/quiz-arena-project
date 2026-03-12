import random
import string
from django.db import models
from django.contrib.auth.models import User


def generate_pin():
    while True:
        pin = ''.join(random.choices(string.digits, k=6))
        if not GameSession.objects.filter(game_pin=pin).exists():
            return pin


class QuizSet(models.Model):
    name = models.CharField(max_length=200)
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quizsets')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def question_count(self):
        return self.questions.count()


class Question(models.Model):
    quiz_set = models.ForeignKey(QuizSet, on_delete=models.CASCADE, related_name='questions')
    text = models.CharField(max_length=500)
    time_limit = models.IntegerField(default=15)
    points = models.IntegerField(default=1000)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.text


class Answer(models.Model):
    COLORS = [('red', 'Red'), ('blue', 'Blue'), ('yellow', 'Yellow'), ('green', 'Green')]
    SHAPES = ['triangle', 'diamond', 'circle', 'square']

    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers')
    text = models.CharField(max_length=300)
    is_correct = models.BooleanField(default=False)
    color = models.CharField(max_length=10, choices=COLORS, default='red')
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.text


class GameSession(models.Model):
    STATUS = [
        ('waiting', 'Waiting'),
        ('question', 'Question Active'),
        ('review', 'Review'),
        ('finished', 'Finished'),
    ]
    quiz_set = models.ForeignKey(QuizSet, on_delete=models.CASCADE)
    host = models.ForeignKey(User, on_delete=models.CASCADE)
    game_pin = models.CharField(max_length=6, unique=True)
    status = models.CharField(max_length=20, choices=STATUS, default='waiting')
    current_question_index = models.IntegerField(default=-1)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Game #{self.game_pin}"

    def save(self, *args, **kwargs):
        if not self.game_pin:
            self.game_pin = generate_pin()
        super().save(*args, **kwargs)


class Player(models.Model):
    session = models.ForeignKey(GameSession, on_delete=models.CASCADE, related_name='players')
    nickname = models.CharField(max_length=50)
    avatar = models.CharField(max_length=10, default='🎮')
    score = models.IntegerField(default=0)
    channel_name = models.CharField(max_length=255, blank=True)
    rank = models.IntegerField(default=0)

    class Meta:
        ordering = ['-score']

    def __str__(self):
        return self.nickname


class PlayerAnswer(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    answer = models.ForeignKey(Answer, on_delete=models.SET_NULL, null=True, blank=True)
    is_correct = models.BooleanField(default=False)
    time_taken = models.FloatField(default=0)
    points_earned = models.IntegerField(default=0)

    class Meta:
        unique_together = ['player', 'question']
