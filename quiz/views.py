import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import QuizSet, Question, Answer, GameSession, Player


# ── Public ────────────────────────────────────────────────────────────────────

def index(request):
    error = request.session.pop('join_error', None)
    return render(request, 'index.html', {'error': error})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('index')
    if request.method == 'POST':
        user = authenticate(request,
                            username=request.POST.get('username'),
                            password=request.POST.get('password'))
        if user:
            login(request, user)
            return redirect(request.POST.get('next', 'index'))
        return render(request, 'login.html', {'error': "Username yoki parol noto'g'ri"})
    return render(request, 'login.html', {'next': request.GET.get('next', '')})


def register_view(request):
    if request.user.is_authenticated:
        return redirect('index')
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')
        if password != password2:
            return render(request, 'register.html', {'error': "Parollar mos kelmadi"})
        if len(password) < 6:
            return render(request, 'register.html', {'error': "Parol kamida 6 ta belgi bo'lishi kerak"})
        if User.objects.filter(username=username).exists():
            return render(request, 'register.html', {'error': "Bu username band"})
        user = User.objects.create_user(username=username, password=password)
        login(request, user)
        return redirect('index')
    return render(request, 'register.html')


def logout_view(request):
    logout(request)
    return redirect('index')


# ── Join flow (no login required) ────────────────────────────────────────────

def join_game(request):
    if request.method == 'POST':
        pin = request.POST.get('game_pin', '').strip()
        session = GameSession.objects.filter(game_pin=pin, status='waiting').first()
        if session:
            return redirect('player_join', game_pin=pin)
        request.session['join_error'] = "Game PIN topilmadi yoki o'yin allaqachon boshlangan"
        return redirect('index')
    return redirect('index')

def player_join(request, game_pin):
    session = get_object_or_404(GameSession, game_pin=game_pin, status='waiting')
    avatars = ['🎮', '🚀', '⭐', '🦁', '🐯', '🦊', '🐸', '🎯', '🔥']
    if request.method == 'POST':
        nickname = request.POST.get('nickname', '').strip()  # ← bu qator kerak!
        avatar = request.POST.get('avatar', '🎮')
        if not nickname:
            return render(request, 'player_join.html',
                          {'session': session, 'avatars': avatars, 'error': 'Nickname kiriting'})
        if Player.objects.filter(session=session, nickname__iexact=nickname).exists():
            # Agar o'sha player channel_name bo'sh bo'lsa (offline) — eski recordni o'chirib yangi yaratamiz
            existing = Player.objects.filter(session=session, nickname__iexact=nickname).first()
            if existing and not existing.channel_name:
                existing.delete()
            else:
                return render(request, 'player_join.html',
                              {'session': session, 'avatars': avatars, 'error': 'Bu nickname band, boshqa nom tanlang'})
        player = Player.objects.create(session=session, nickname=nickname, avatar=avatar)
        request.session['player_id'] = player.id
        return redirect('player_lobby', game_pin=game_pin)
    return render(request, 'player_join.html', {'session': session, 'avatars': avatars})

def player_lobby(request, game_pin):
    session = get_object_or_404(GameSession, game_pin=game_pin)
    player_id = request.session.get('player_id')
    if not player_id:
        return redirect('player_join', game_pin=game_pin)
    player = get_object_or_404(Player, id=player_id, session=session)
    return render(request, 'player_lobby.html', {'session': session, 'player': player})


# ── Host / Admin (login required) ────────────────────────────────────────────

@login_required
def my_quizzes(request):
    q = request.GET.get('q', '').strip()
    quizzes = QuizSet.objects.filter(creator=request.user)
    if q:
        quizzes = quizzes.filter(name__icontains=q)
    return render(request, 'my_quizzes.html', {'quizzes': quizzes, 'query': q})


@login_required
def create_quiz(request):
    return render(request, 'create_quiz.html')


@login_required
def save_quiz(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    name = data.get('name', '').strip()
    if not name:
        return JsonResponse({'error': 'Quiz nomi kiritilmagan'}, status=400)

    questions_data = data.get('questions', [])
    if not questions_data:
        return JsonResponse({'error': 'Kamida bitta savol kerak'}, status=400)

    colors = ['red', 'blue', 'yellow', 'green']

    quiz_id = data.get('quiz_id')
    if quiz_id:
        quiz = get_object_or_404(QuizSet, id=quiz_id, creator=request.user)
        quiz.name = name
        quiz.save()
        quiz.questions.all().delete()
    else:
        quiz = QuizSet.objects.create(name=name, creator=request.user)

    for i, qd in enumerate(questions_data):
        question = Question.objects.create(
            quiz_set=quiz,
            text=qd.get('text', ''),
            time_limit=qd.get('time_limit', 15),
            points=qd.get('points', 1000),
            order=i,
        )
        for j, ad in enumerate(qd.get('answers', [])):
            Answer.objects.create(
                question=question,
                text=ad.get('text', ''),
                is_correct=bool(ad.get('is_correct', False)),
                color=colors[j % 4],
                order=j,
            )

    return JsonResponse({'success': True, 'quiz_id': quiz.id})


@login_required
def edit_quiz(request, quiz_id):
    quiz = get_object_or_404(QuizSet, id=quiz_id, creator=request.user)
    questions = quiz.questions.prefetch_related('answers').all()
    quiz_data = {
        'id': quiz.id,
        'name': quiz.name,
        'questions': [
            {
                'text': q.text,
                'time_limit': q.time_limit,
                'points': q.points,
                'answers': [{'text': a.text, 'is_correct': a.is_correct}
                             for a in q.answers.all()],
            }
            for q in questions
        ],
    }
    return render(request, 'create_quiz.html', {'quiz_data': json.dumps(quiz_data)})


@login_required
def delete_quiz(request, quiz_id):
    quiz = get_object_or_404(QuizSet, id=quiz_id, creator=request.user)
    quiz.delete()
    return redirect('my_quizzes')


@login_required
def host_start(request, quiz_id):
    quiz = get_object_or_404(QuizSet, id=quiz_id, creator=request.user)
    if quiz.question_count == 0:
        return redirect('my_quizzes')
    session = GameSession.objects.create(quiz_set=quiz, host=request.user)
    return redirect('host_lobby', game_pin=session.game_pin)


@login_required
def host_lobby(request, game_pin):
    session = get_object_or_404(GameSession, game_pin=game_pin, host=request.user)
    return render(request, 'host_lobby.html', {
        'session': session,
        'total_questions': session.quiz_set.question_count,
    })